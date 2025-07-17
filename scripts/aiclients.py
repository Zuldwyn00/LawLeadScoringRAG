import os
import json
import time
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain.schema import (
    SystemMessage,
    HumanMessage,
)
from typing import List


from utils import load_prompt, load_config, setup_logger, count_tokens
from scripts.filemanagement import get_text_from_file

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
        self.rate_limit_flag = False # Flag to check if the client is rate limited, changes to true if the client is rate limited or we already ran a metadata extraction once.

    def _initialize_client(self):
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=(20 / 60), # 20 requests per minute = 20/60 requests per second
            check_every_n_seconds = 5,
            max_bucket_size=20
        )
        client = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            openai_api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            rate_limiter=rate_limiter
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
    
    def define_metadata(self, text: str, filepath: str, case_id: str, retries: int = 2) -> dict:
        """Extracts metadata from text as a dictionary using AI with a structured prompt.
        Args:
            text (str): The text to process.
            retries (int): The number of times to retry on failure.
            delay (int): The delay in seconds between retries.
        Returns:
            dict: A dictionary of the extracted metadata, or None on failure.
        """
        if self.rate_limit_flag: # If the client is rate limited, wait for 100 seconds and reset the flag. If we already ran a metadata extraction once, we need to wait for 100 seconds to avoid rate limiting.
            wait_for_rate_limit()
            self.rate_limit_flag = False


        system_prompt_content = load_prompt('injury_metadata_extraction')
        logger.debug(f"Token count: {count_tokens(text) + count_tokens(system_prompt_content)}")
        system_message = SystemMessage(content=system_prompt_content)
        user_message = HumanMessage(content=text)
        messages_to_send = [system_message, user_message]
        
        for attempt in range(retries):
            try:
                logger.debug(f"Attempting to define metadata (Attempt {attempt + 1}/{retries})...")
                response = self.client.invoke(messages_to_send).content
                
                start_index = response.find('{')
                end_index = response.rfind('}') + 1
                
                if start_index != -1 and end_index != 0:
                    json_string = response[start_index:end_index]
                    metadata = json.loads(json_string)
                    metadata['source'] = filepath
                    metadata['case_id'] = case_id

                    self.rate_limit_flag = False
                    return metadata
                else:
                    raise ValueError("No JSON object found in the response.")

            except Exception as e:
                logger.error(f"An unexpected error occurred on attempt {attempt + 1}: {e}")
                self.rate_limit_flag = True

        logger.error("Failed to define metadata after %s attempts.", retries)
        raise Exception(f"Failed to extract metadata for {filepath} after {retries} attempts.")
    
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
        logger.debug(f"Token count: {count_tokens(new_lead_description) + count_tokens(historical_context) + count_tokens(system_prompt_content)}")
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

    def get_more_context(self, filepath: List[str]) -> str: #TODO: Add a way to call tools like this, this is just a placeholder unusued method
        """
        Gets the context of a list of files by extracting their text content.

        Args:
            filepath (List[str]): List of file paths to extract text from.

        Returns:
            str: Combined text content from all files.
        """
        combined_text = ""
        
        for file in filepath:
            try:
                logger.info(f"Extracting text from: {file}")
                parsed_content = get_text_from_file(file)
                if parsed_content and 'content' in parsed_content:
                    file_text = parsed_content['content'] or ""
                    combined_text += f"\n\n--- Content from {file} ---\n"
                    combined_text += file_text
                else:
                    logger.warning(f"No content found in file: {file}")
            except Exception as e:
                logger.error(f"Error extracting text from {file}: {e}")
                combined_text += f"\n\n--- Error extracting content from {file}: {e} ---\n"
        
        return combined_text.strip()
            

def wait_for_rate_limit(seconds_to_wait: int = 120) -> None:
    """
    Waits for a specified amount of time to avoid rate limiting, defaults to 120 seconds.
    """
    logger.debug(f"Waiting for {seconds_to_wait} seconds to avoid rate limiting...")
    time.sleep(seconds_to_wait)
    logger.debug("Done waiting.")