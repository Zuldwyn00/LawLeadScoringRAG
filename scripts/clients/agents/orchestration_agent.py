
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseClient
from utils import load_prompt, setup_logger, load_config



class OrchestrationAgent:
    """
    An agent for generating tooltips for scored leads using an LLM.
    
    This agent takes scored lead data and generates helpful tooltips
    that provide context and explanations for the scoring results.
    """

    def __init__(self, client: BaseClient):
        """
        Initialize the OrchestrationAgent with a client.

        Args:
            client (BaseClient): A concrete implementation of BaseClient
                                (e.g., AzureClient) for LLM communication.

        Raises:
            ValueError: If BaseClient is used directly instead of a concrete implementation.
        """
        self.client = client
        self.prompt = load_prompt("orchestration")
        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )

    def request_agent(self):
        pass