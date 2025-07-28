from typing import Optional, List
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseClient
from utils import load_prompt, count_tokens, setup_logger, load_config


class ScoringClient:
    
    def __init__(self, client: BaseClient, **kwargs):

        # Prevent using the abstract BaseClient class directly
        if client.__class__ == BaseClient:
            raise ValueError(
                "Cannot use BaseClient directly. Please provide a concrete implementation "
                "that inherits from BaseClient (e.g., AzureClient)."
            )
        
        self.client = client
        self.prompt = load_prompt('lead_scoring')
        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info("Initialized %s with %s", self.__class__.__name__, client.__class__.__name__)