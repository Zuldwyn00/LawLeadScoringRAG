import os
import json
import time
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
)
from typing import List

from pydantic import NonNegativeInt

from utils import load_prompt, load_config, setup_logger, count_tokens

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
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            max_retries=5,
            retry_min_seconds=5,
            retry_max_seconds=60
        )
        return client

    def get_embeddings(self, text: str) -> List[float]:
        embedding = self.client.embed_query(text)
        return embedding
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a list of texts in batches to avoid rate limiting.

        The method splits the input list of texts into two halves, processes each half
        separately with a 5-second delay in between, and then combines the results.

        Args:
            texts (List[str]): A list of strings to be embedded.

        Returns:
            List[List[float]]: A list of embedding vectors for the input texts.
        """
        midpoint = len(texts) // 2
        first_half = texts[:midpoint]
        second_half = texts[midpoint:]

        logger.info(f"Processing first batch of {len(first_half)} documents for embeddings.")
        embeddings1 = self.client.embed_documents(first_half)
        
        logger.info("Waiting for 5 seconds before processing the next batch.")
        time.sleep(5)
        
        logger.info(f"Processing second batch of {len(second_half)} documents for embeddings.")
        embeddings2 = self.client.embed_documents(second_half)
        
        return embeddings1 + embeddings2
    



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
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            max_retries=5,
            retry_min_seconds=60,
            retry_max_seconds=300
        )
        return client
    
    def add_response(self, message: str) -> bool:
        """Adds a human message to the chat history.

        Args:
            message (str): The message content to add.

        Returns:
            bool: True if the message was added successfully, False otherwise.
        """
        message_obj = HumanMessage(content=message)
        try:
            self.message_history.append(message_obj)
            return True
        except Exception as e:
            logger.error("Issue adding message to message history: %s", e)
        return False
    
    def get_response(self, messages: list = None) -> str:
        """Gets a response from the chat model.

        Args:
            mes structured promptnal): A list of messages to send to the model. 
                                     If not provided, the instance's message history will be used.

        Returns:
            str: The content of the model's response.
        """
        messages_to_send = messages if messages else self.message_history
        response = self.client.invoke(messages_to_send).content
        return response
    
    def define_metadata(self, text: str, filepath: str, case_id: str) -> dict:
        """Extracts metadata from text as a dictionary using AI with a structured prompt.
        Args:
            text (str): The text to process.
            filepath (str): The path to the file being processed.
            case_id (str): The case ID for the document.
        Returns:
            dict: A dictionary of the extracted metadata, or raises an exception on failure.
        """
        logger.debug(f"Token count: {count_tokens(text) + count_tokens(load_prompt('injury_metadata_extraction'))}")

        system_prompt_content = load_prompt('injury_metadata_extraction')
        system_message = SystemMessage(content=system_prompt_content)
        user_message = HumanMessage(content=text)
        messages_to_send = [system_message, user_message]
        
        try:
            logger.debug("Attempting to define metadata...")
            response = self.client.invoke(messages_to_send).content
            
            start_index = response.find('{')
            end_index = response.rfind('}') + 1
            
            if start_index != -1 and end_index != 0:
                json_string = response[start_index:end_index]
                metadata = json.loads(json_string)
                metadata['source'] = filepath
                metadata['case_id'] = case_id
                return metadata
            else:
                raise ValueError("No JSON object found in the response.")

        except Exception as e:
            logger.error(f"Failed to define metadata for {filepath} after multiple retries: {e}")
            raise Exception(f"Failed to extract metadata for {filepath} after multiple retries.") from e

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