
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseClient
from utils import load_prompt, setup_logger, load_config



class TooltipAgent:
    """
    An agent for generating tooltips for scored leads using an LLM.
    
    This agent takes scored lead data and generates helpful tooltips
    that provide context and explanations for the scoring results.
    """

    def __init__(self, client: BaseClient):
        """
        Initialize the TooltipAgent with a client.

        Args:
            client (BaseClient): A concrete implementation of BaseClient
                                (e.g., AzureClient) for LLM communication.

        Raises:
            ValueError: If BaseClient is used directly instead of a concrete implementation.
        """
        # Prevent using the abstract BaseClient class directly
        if client.__class__ == BaseClient:
            raise ValueError(
                "Cannot use BaseClient directly. Please provide a concrete implementation "
                "that inherits from BaseClient (e.g., AzureClient)."
            )

        self.client = client
        self.prompt = load_prompt("lead_tooltips")
        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )

    def get_tooltips(self, scored_lead: str):
        """
        Generate tooltips for a scored lead using the LLM.

        Args:
            scored_lead (str): The scored lead data to generate tooltips for.

        Returns:
            str: Generated tooltips content, or error message if generation fails.
        """
        system_message = SystemMessage(content=self.prompt)
        user_message = HumanMessage(content=scored_lead)
        messages = [system_message, user_message]

        try:
            response = self.client.invoke(messages)
            tooltips = response.content
            return tooltips
        except Exception as e:
            error_msg = f"Error during tooltip creation: {e}"
            self.logger.error(error_msg)
            return error_msg
