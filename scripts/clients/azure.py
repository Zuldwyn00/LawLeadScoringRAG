from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
import os
from typing import List
from langchain_core.messages import (
    AIMessage,
)
from .base import BaseClient
import os
from dotenv import load_dotenv

from utils import *
from .telemetry_tracking.telemetry import TelemetryManager


class AzureClient(BaseClient):

    def __init__(self, client_config: str, **kwargs):
        """
        Initialize Azure client with configuration loaded from client_configs.json.

        The client type determines whether this becomes an embedding client or a chat client.
        Clients configured in the "embedding_clients" section become AzureOpenAIEmbeddings,
        while all other sections (e.g., "azure_clients") become AzureChatOpenAI.
        A single client instance cannot be both - it must be either embedding or chat.

        Args:
            client_config (str): The client configuration name from client_configs.json
                             The section this config belongs to determines the client type:
                             - "embedding_clients" section → AzureOpenAIEmbeddings (embedding only)
                             - Other sections → AzureChatOpenAI (chat only)
            **kwargs: Additional arguments passed to BaseClient constructor
        """
        super().__init__(**kwargs)

        # Load environment variables from .env file
        load_dotenv()

        self.client_config = self.load_client_config(client_config)
        self.client_type = client_config

        # Determine the LangChain client class based on the section
        section = self.client_config.get("_section", "")
        if section == "embedding_clients":
            self.langchain_client_class = AzureOpenAIEmbeddings
        else:
            # Default to chat client for all other sections (azure_clients, etc.)
            self.langchain_client_class = AzureChatOpenAI
    
        self.client = self._initialize_client()
        self.telemetry_manager = TelemetryManager(self.client_config)

    def _initialize_client(self):
        """Initialize the appropriate LangChain client based on configuration."""
        params = {
            "azure_deployment": self.client_config.get("deployment_name"),
            "openai_api_version": self.client_config.get("api_version"),
            "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        }

        client = self.langchain_client_class(**params)

        self.logger.info(
            f"Initialized {self.langchain_client_class.__name__} with deployment '{self.client_config.get('deployment_name')}'"
        )
        return client

    def invoke(self, messages=None) -> AIMessage:
        """
        Send messages and get response from the Azure client.
        Adds messages to message_history.

        Args:
            messages: List of messages to send to the client (optional)

        Returns:
            AIMessage: The response from the client
        """
        if messages is None:
            messages = self.message_history
        else:
            # When custom messages are provided, add any new ones to message_history
            # to maintain complete conversation context for chat logs
            for msg in messages:
                if msg not in self.message_history:
                    self.message_history.append(msg)

        self.telemetry_manager.calculate_price(messages, True) #calculate price of input text
        try:
            self.logger.info("Invoking message for '%s'.", self.client_type)
            response = self.client.invoke(messages)

            # Calculate price for output text - handle both content and tool calls
            if response.content:
                # Regular text response
                self.telemetry_manager.calculate_price(response.content, False)
            elif hasattr(response, 'tool_calls') and response.tool_calls:
                # Tool call response - count tokens for tool calls
                tool_calls_text = str(response.tool_calls)
                self.telemetry_manager.calculate_price(tool_calls_text, False)
            else:
                # Empty response
                self.telemetry_manager.calculate_price("", False)

            self.add_message(response)
            return response
        except Exception as e:
            self.logger.error("Failed to invoke client '%s': '%s'", self.client_type, e)
            raise

    def get_embeddings(self, text: str) -> List[float]:
        if not isinstance(self.client, AzureOpenAIEmbeddings):
            self.logger.error(
                "Embeddings are only available for embedding client types, not chat clients:"
            )
            raise ValueError("Embeddings not available for this client type")

        embedding = self.client.embed_query(text)
        return embedding
