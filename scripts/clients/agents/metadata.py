from pathlib import Path
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
import time
import json

from ..base import BaseClient
from utils import load_prompt, count_tokens, setup_logger, load_config


class MetadataAgent:
    """
    An agent for extracting specific metadata fields in a specified format with an LLM.
    """

    def __init__(self, client: BaseClient):

        if client.__class__ == BaseClient:
            raise ValueError(
                "Cannot use BaseClient directly. Please provide a concrete implementation "
                "that inherits from BaseClient (e.g., AzureClient)."
            )
        self.client = client
        self.prompt = load_prompt("metadata_extraction")
        self.rate_limit_flag = False
        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )

    def define_metadata(self, text: str, filepath: str, case_id: str, retries: int = 2):
        self.rate_limit_flag = False
        if (
            self.rate_limit_flag
        ):  # If the client is rate limited, wait for 100 seconds and reset the flag. If we already ran a metadata extraction once, we need to wait for 100 seconds to avoid rate limiting.
            self.wait_for_rate_limit()
            self.rate_limit_flag = False

        system_prompt_content = self.prompt
        self.logger.debug(
            f"Token count: {count_tokens(text) + count_tokens(system_prompt_content)}"
        )
        system_message = SystemMessage(content=system_prompt_content)
        user_message = HumanMessage(content=text)
        messages_to_send = [system_message, user_message]

        for attempt in range(retries):
            try:
                self.logger.debug(
                    f"Attempting to define metadata (Attempt {attempt + 1}/{retries})..."
                )
                response = self.client.invoke(messages_to_send).content

                start_index = response.find("{")
                end_index = response.rfind("}") + 1

                if start_index != -1 and end_index != 0:
                    json_string = response[start_index:end_index]
                    metadata = json.loads(json_string)
                    metadata["source"] = filepath
                    metadata["case_id"] = case_id

                    self.rate_limit_flag = False
                    return metadata
                else:
                    raise ValueError("No JSON object found in the response.")

            except Exception as e:
                self.logger.error(
                    f"An unexpected error occurred on attempt {attempt + 1}: {e}"
                )
                self.rate_limit_flag = True

        self.logger.error("Failed to define metadata after %s attempts.", retries)
        raise Exception(
            f"Failed to extract metadata for {filepath} after {retries} attempts."
        )

    def wait_for_rate_limit(self, seconds_to_wait: int = 120) -> None:
        """
        Waits for a specified amount of time to avoid rate limiting, defaults to 120 seconds.
        """
        self.logger.debug(
            f"Waiting for {seconds_to_wait} seconds to avoid rate limiting..."
        )
        time.sleep(seconds_to_wait)
        self.logger.debug("Done waiting.")
