from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
import os
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage, ToolMessage
from .base import BaseClient
import os

from utils import *

class AzureClient(BaseClient):

    def __init__(self, client_type: str, **kwargs):
        """
        Initialize Azure client with configuration loaded from client_configs.json.
        
        Args:
            client_type (str): The client configuration name from client_configs.json
                             (e.g., "gpt-o4-mini", "text_embedding_3_small")
            **kwargs: Additional arguments passed to BaseClient constructor
        """
        super().__init__(**kwargs)
        
        self.client_config = self.load_client_config(client_type)
        self.client_type = client_type
        self.deployment_name = self.client_config["deployment_name"]
        self.api_version = self.client_config["api_version"]
        
        # Determine the LangChain client class based on the section
        section = self.client_config.get("_section", "")
        if section == "embedding_clients":
            self.langchain_client_class = AzureOpenAIEmbeddings
        else:
            # Default to chat client for all other sections (azure_clients, etc.)
            self.langchain_client_class = AzureChatOpenAI
        
        self.client = self._initialize_client()

    def _initialize_client(self):
        """Initialize the appropriate LangChain client based on configuration."""
        params = {
            "azure_deployment": self.deployment_name,
            "openai_api_version": self.api_version,
            "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY")
        }
        
        client = self.langchain_client_class(**params)
        
        self.logger.info(f"Initialized {self.langchain_client_class.__name__} with deployment '{self.deployment_name}'")
        return client

    def invoke(self, messages=None) -> AIMessage:
        """
        Send messages and get response from the Azure client.
        
        Args:
            messages: List of messages to send to the client (optional)
            
        Returns:
            AIMessage: The response from the client
        """
        if messages is None:
            messages = self.message_history
        
        try:
            self.logger.info("Invoking message for %s.", self.client_type)
            response = self.client.invoke(messages)
            self.message_history.append(response)
            return response
        except Exception as e:
            self.logger.error("Failed to invoke client %s: %s", self.client_type, e)
            raise