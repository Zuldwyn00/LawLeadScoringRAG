import os
import json
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
)
from typing import List

from utils import load_prompt, load_config, setup_logger

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)

class EmbeddingManager:
    def __init__(self):
        self.config = config
        self.client = self._initialize_client()

    def _initialize_client(self):
        client = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
            openai_api_version=os.getenv("OPENAI_API_EMBEDDING_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY")
        )
        return client

    def get_embeddings(self, text: str) -> List[float]:
        embedding = self.client.embed_query(text)
        return embedding
    



class ChatManager():
    def __init__(self, messages: list = []):
        self.config = config
        self.client = self._initialize_client()
        self.message_history = messages if messages else []

    def _initialize_client(self):
        client = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            openai_api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY")
        )
        return client
    
    def add_response(self, message: str) -> bool:
        message_obj = HumanMessage(content=message)
        try:
            self.message_history.append(message_obj)
            return True
        except Exception as e:
            logger.error("Issue adding message to message history: %s", e)
        return False
    
    def get_response(self, messages: list = None) -> str:
        messages_to_send = messages if messages else self.message_history
        response = self.client.invoke(messages_to_send).content
        return response
    
    def define_metadata(self, text: str, filepath: str, case_id: str) -> dict:
        """Extracts metadata from text as a dictionary.
        Args:
            text (str): The text to process.
        Returns:
            dict: A dictionary of the extracted metadata, or None on failure.
        """
        system_prompt_content = load_prompt('injury_metadata_extraction')
        system_message = SystemMessage(content=system_prompt_content)
        user_message = HumanMessage(content=text)
        messages_to_send = [system_message, user_message]
        
        try:
            logger.debug(f"Attempting to define metadata,Sending messages to client: {messages_to_send}")
            response = self.client.invoke(messages_to_send).content
            
            # Find the start and end of the JSON object
            start_index = response.find('{')
            end_index = response.rfind('}') + 1
            
            if start_index != -1 and end_index != 0:
                json_string = response[start_index:end_index]
                metadata = json.loads(json_string)
                metadata['source'] = filepath
                metadata['case_id'] = case_id
                return metadata
            else:
                logger.error("No JSON object found in the response: %s", response)
                return None

        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON from model response: %s. Response: %s", e, response)
            return None
        except Exception as e:
            logger.error("An unexpected error occurred in define_metadata: %s", e)
            return None
        
    def score_lead(self, new_lead_description: str, historical_context: str) -> str:
        """
        Scores a new lead by comparing it against historical data using a structured prompt.

        Args:
            new_lead_description (str): A detailed description of the new lead.
            historical_context (str): A formatted string containing search results of similar historical cases.

        Returns:
            str: The formatted analysis and score from the language model.
        """
        system_prompt_content = load_prompt('lead_scoring')
        system_message = SystemMessage(content=system_prompt_content)
        
        user_message_content = f"""
        **New Lead:**
        {new_lead_description}

        **Historical Case Summaries:**
        {historical_context}
        """
        user_message = HumanMessage(content=user_message_content)
        messages_to_send = [system_message, user_message]
        
        try:
            logger.debug(f"Attempting to score lead, sending messages to client...")
            response = self.client.invoke(messages_to_send).content
            return response
        except Exception as e:
            logger.error("An unexpected error occurred in score_lead: %s", e)
            return None
