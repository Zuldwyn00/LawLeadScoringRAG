from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import json
import os
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
)

from utils import *
from .caching.cachemanager import ClientCacheManager


class BaseClient(ABC):
    """
    Abstract base class defining the interface for all AI clients.

    This class provides the fundamental interface that all clients must implement,
    regardless of the underlying provider or specific functionality.
    """

    def __init__(
        self,
        # metrics: Optional[MetricsCollector] = None,
        # rate_limiter: Optional[RateLimiter] = None,
        message_history: Optional[List[BaseMessage]] = None,
    ):

        # if metrics is None:
        # metrics = MetricsCollector() #TODO: Define default MetricsCollector
        if message_history is None:
            message_history = []
        # if rate_limiter is None:
        # rate_limiter = RateLimiter()  #TODO: define default rate limiter

        self.config = load_config()
        self.logger = setup_logger(self.__class__.__name__, self.config)
        self.cache_manager = ClientCacheManager()
        # self.metrics = metrics
        # self.rate_limiter = rate_limiter
        self.message_history = message_history

    def load_client_config(self, client_type: str) -> Dict[str, Any]:
        """
        Load client configuration from client_configs.json based on client_type.

        Args:
            client_type (str): The name of the client configuration to load
                             (e.g., "gpt-o4-mini", "text_embedding_3_small")

        Returns:
            Dict[str, Any]: The configuration dictionary for the specified client

        Raises:
            FileNotFoundError: If client_configs.json is not found
            KeyError: If the specified client_type is not found in any section
            json.JSONDecodeError: If the JSON file is malformed
        """
        config_path = os.path.join(os.path.dirname(__file__), "client_configs.json")

        try:
            with open(config_path, "r") as f:
                configs = json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Client configuration file not found: {config_path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in client configuration file: {e}")
            raise

        for section_name, section_configs in configs.items():
            if client_type in section_configs:
                client_config = section_configs[client_type].copy()
                client_config["_section"] = (
                    section_name  # Add metadata about which section it came from
                )
                self.logger.debug(
                    f"Loaded client config for '{client_type}' from section '{section_name}'"
                )
                return client_config

        # If we get here, the client_type wasn't found
        available_clients = []
        for section_configs in configs.values():
            available_clients.extend(section_configs.keys())

        error_msg = f"Client type '{client_type}' not found. Available clients: {available_clients}"
        self.logger.error(error_msg)
        raise KeyError(error_msg)

    @abstractmethod
    def invoke(self, messages=None) -> AIMessage:
        """Send messages and get response"""
        pass

    def add_message(self, message: BaseMessage | List[BaseMessage]):
        """Add a single message or list of messages to the message history."""
        if isinstance(message, list):
            self.message_history.extend(message)
        else:
            self.message_history.append(message)

    def clear_history(self):
        """Clear conversation history"""
        self.message_history = []
