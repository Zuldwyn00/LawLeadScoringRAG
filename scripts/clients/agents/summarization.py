"""
A client that gets a summarization of a given text.
"""

from pathlib import Path
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseClient
from ..caching.cacheschema import SummaryCacheEntry
from utils import load_prompt, count_tokens, setup_logger, load_config


class SummarizationClient:
    """
    A specialized client for text summarization tasks.

    Requires a client instance and provides summarization-specific functionality
    using the summarization prompt and logic from aiclients.py.
    """

    def __init__(self, client: BaseClient):
        """
        Initialize the summarization client.

        Args:
            client (BaseClient): A client instance from the clients package
                               (e.g., AzureClient, or any other client that implements BaseClient)

        Raises:
            ValueError: If the client is the BaseClient class itself (abstract class)
        """
        # Prevent using the abstract BaseClient class directly
        if client.__class__ == BaseClient:
            raise ValueError(
                "Cannot use BaseClient directly. Please provide a concrete implementation "
                "that inherits from BaseClient (e.g., AzureClient)."
            )

        self.client = client
        self.prompt = load_prompt("summarize_text")
        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            f"Initialized SummarizationClient with {client.__class__.__name__}"
        )

    def summarize_text(self, text: str, max_tokens: int = 15000, source_file: Optional[str] = None) -> str:
        """
        Summarizes the given text using the language model with caching support.

        Args:
            text (str): The text to summarize
            max_tokens (int): Maximum tokens allowed before summarization is skipped
            source_file (Optional[str]): Path to the source file being summarized (for caching)

        Returns:
            str: The summarized text, or error message if summarization fails
        """
        # Check if text is too long to summarize
        if count_tokens(text) > max_tokens:
            self.logger.warning(
                f"Text is too long to summarize ({count_tokens(text)} tokens > {max_tokens})"
            )
            return "The text is too long to summarize, returning first 4000 characters\n\n" + text[:4000]
        
        # Cache lookup: if we already summarized this file with this client, reuse it
        # Reason: Avoids redundant LLM calls to reduce latency and cost
        if source_file and hasattr(self.client, 'cache_manager') and hasattr(self.client, 'client_type'):
            source_path = Path(source_file)
            cached_entry = self.client.cache_manager.get_cached_entry(
                client=self.client.client_type,
                source_file=str(source_path),
                cache_type=SummaryCacheEntry
            )
            self.logger.debug(f"Cache lookup result for '{source_file}': {cached_entry}")
            if cached_entry:
                self.logger.info(f"Using cached summary for '{source_file}' (tokens: {cached_entry.tokens})")
                return cached_entry.summary
            else:
                self.logger.debug(f"No valid cache entry found for '{source_file}', proceeding with LLM call")
            
        try:
            self.logger.info("Summarizing text with LLM...")

            # Clear message history to avoid conflicts with tool calling
            self.client.clear_history()

            # Create messages
            system_message = SystemMessage(content=self.prompt)
            user_message = HumanMessage(content=text)
            messages = [system_message, user_message]

            # Get response from the client
            response = self.client.invoke(messages)
            summary = response.content
            
            # Cache write: persist the newly generated summary for future reuse
            # Reason: Ensures subsequent requests for the same (file, client) load from cache
            if source_file and hasattr(self.client, 'cache_manager') and hasattr(self.client, 'client_type'):
                try:
                    source_path = Path(source_file)
                    token_count = count_tokens(summary)
                    
                    cache_entry = SummaryCacheEntry(
                        source_file=source_path,
                        client=self.client.client_type,
                        summary=summary,
                        tokens=token_count
                    )
                    
                    self.client.cache_manager.cache_entry(cache_entry)
                    self.logger.info(f"Cached summarization result for '{source_file}' with client '{self.client.client_type}'")
                    
                except Exception as e:
                    self.logger.warning(f"Error caching result for '{source_file}': {e}")
                    # Continue normally if caching fails

            self.logger.debug(f"Successfully generated summary.")
            return summary

        except Exception as e:
            error_msg = f"Error during text summarization: {e}"
            self.logger.error(error_msg)
            return error_msg
