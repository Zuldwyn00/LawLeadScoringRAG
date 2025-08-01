"""
A client that gets a summarization of a given text.
"""

from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseClient
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

    def summarize_text(self, text: str, max_tokens: int = 18000) -> str:
        """
        Summarizes the given text using the language model.

        Args:
            text (str): The text to summarize
            max_tokens (int): Maximum tokens allowed before summarization is skipped

        Returns:
            str: The summarized text, or error message if summarization fails
        """
        # Check if text is too long to summarize
        if count_tokens(text) > max_tokens:
            self.logger.warning(
                f"Text is too long to summarize ({count_tokens(text)} tokens > {max_tokens})"
            )
            return "The text is too long to summarize, returning first 4000 characters\n\n" + text[:4000]
            
        try:
            self.logger.info("Summarizing text with LLM...")

            # Create messages
            system_message = SystemMessage(content=self.prompt)
            user_message = HumanMessage(content=text)
            messages = [system_message, user_message]

            # Get response from the client
            response = self.client.invoke(messages)
            summary = response.content

            self.logger.debug(f"Generated summary: {summary}")
            return summary

        except Exception as e:
            error_msg = f"Error during text summarization: {e}"
            self.logger.error(error_msg)
            return error_msg
