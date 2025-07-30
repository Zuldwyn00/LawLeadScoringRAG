from langchain_core.tools import tool
import os
import re
import json
import time
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from typing import List, Callable
from functools import wraps

from utils import load_prompt, load_config, setup_logger, count_tokens
from scripts.filemanagement import get_text_from_file

from scripts.jurisdictionscoring import JurisdictionScoreManager

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)


# TODO: This file is doing too much, seperate concerns and the classes. We are handling too much here. Tools should be managed seperately, not by the AIChat it should have
# a tool class as part of its init perhaps.

# ChatManager can be seperated into AIClient (we can define the client to use for each tool, very nice), RateLimiter for handling all ratelimiting logic, and ToolOrchestrator
# This way we can reuse a lot of these for different tools and AI agents.


class EmbeddingManager:
    def __init__(self):
        self.config = config
        self.client = self._initialize_client()
        self.logger = setup_logger("EmbeddingManager", config)

    def _initialize_client(self):
        client = AzureOpenAIEmbeddings(
            azure_deployment="text-embedding-3-small",
            openai_api_version="2023-05-15",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
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

        self.logger.info(
            f"Processing first batch of {len(first_half)} documents for embeddings."
        )
        embeddings1 = self.client.embed_documents(first_half)

        self.logger.info("Waiting for 5 seconds before processing the next batch.")
        time.sleep(5)

        self.logger.info(
            f"Processing second batch of {len(second_half)} documents for embeddings."
        )
        embeddings2 = self.client.embed_documents(second_half)

        return embeddings1 + embeddings2


class RateLimiter:
    def __init__(self):
        self.config = config
        self.logger = setup_logger("RateLimiter", self.config)

    def wait_for_rate_limit(self, seconds_to_wait: int = 120) -> None:
        """
        Waits for a specified amount of time to avoid rate limiting, defaults to 120 seconds.
        """
        self.logger.debug(
            f"Waiting for {seconds_to_wait} seconds to avoid rate limiting..."
        )
        time.sleep(seconds_to_wait)
        self.logger.debug("Done waiting.")


class AIChat:
    def __init__(
        self,
        client_type: str = "azure_openai",
        deployment_name: str = None,
        api_version: str = None,
        endpoint: str = None,
        api_key: str = None,
        rate_limiter: RateLimiter = None,
    ):

        self.config = config
        self.logger = setup_logger("AIChat", self.config)
        self.client = self._initialize_client()

    def _prepare_client_config(self, deployment_name, api_version, endpoint, api_key):
        if self.client_Type == "azure_openai":
            return {
                "azure_deployment": deployment_name
                or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                "openai_api_version": api_version
                or os.getenv("AZURE_OPENAI_API_VERSION"),
                "azure_endpoint": endpoint or os.getenv("AZURE_OPENAI_ENDPOINT"),
                "api_key": api_key or os.getenv("AZURE_OPENAI_API_KEY"),
            }
        else:
            raise ValueError(f"Unsupported client type: {self.client_type}.")

    def _initialize_client(self):
        pass


class ChatManager:
    def __init__(
        self, messages: list = [], temperature: float = 0.0
    ):  # default temperature is 0.0 to be deterministic, implement logic later to make it able to be changed more easily.
        self.config = config
        self.logger = setup_logger(
            "ChatManager", self.config, filename="chatmanager.log"
        )
        self.tool_manager = ToolManager(tools=[get_file_content])
        self.temperature = temperature
        self.client = self._initialize_client()
        self.message_history = messages if messages else []
        self.rate_limit_flag = False  # Flag to check if the client is rate limited, changes to true if the client is rate limited or we already ran a metadata extraction once.

    def _initialize_client(self):
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=(
                20 / 60
            ),  # 20 requests per minute = 20/60 requests per second
            check_every_n_seconds=5,
            max_bucket_size=20,
        )
        client = AzureChatOpenAI(
            azure_deployment="o4-mini",
            openai_api_version="2025-01-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            rate_limiter=rate_limiter,
        ).bind_tools(self.tool_manager.tools)
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
            self.logger.error("Issue adding message to message history: %s", e)
        return False

    def get_response_with_tools(self, messages: list = None) -> str:
        """
        Gets a response from the chat model, handling tool calls automatically.

        Args:
            messages (list, optional): A list of messages to send to the model.
                 If not provided, the instance's message history will be used.

        Returns:
            str: The content of the model's response.
        """
        self.logger.debug(f"Getting response with tool access...")
        messages_to_send = messages if messages is not None else self.message_history

        # Calculate total token count for all messages
        total_tokens = 0
        for message in messages_to_send:
            if hasattr(message, "content") and message.content:
                total_tokens += count_tokens(str(message.content))
        self.logger.debug(f"Total token count: {total_tokens}")

        while True:
            response = self.client.invoke(messages_to_send)

            if messages is None:
                self.message_history.append(
                    response
                )  # if no messages are provided, add the response to the message history
            else:
                messages_to_send.append(
                    response
                )  # if messages are provided, add the response to the messages to send

            if not response.tool_calls:
                return (
                    response.content
                )  # if there are no tool calls, return the response content

            self.logger.info(f"Model made {len(response.tool_calls)} tool calls.")

            for tool_call in response.tool_calls:
                tool_output = self.tool_manager.call_tool(tool_call)
                tool_message = ToolMessage(
                    content=str(tool_output), tool_call_id=tool_call["id"]
                )
                if messages is None:
                    self.message_history.append(tool_message)
                else:
                    messages_to_send.append(tool_message)

    def define_metadata(
        self, text: str, filepath: str, case_id: str, retries: int = 2
    ) -> dict:
        """Extracts metadata from text as a dictionary using AI with a structured prompt.
        Args:
            text (str): The text to process.
            retries (int): The number of times to retry on failure.
            delay (int): The delay in seconds between retries.
        Returns:
            dict: A dictionary of the extracted metadata, or None on failure.
        """
        if (
            self.rate_limit_flag
        ):  # If the client is rate limited, wait for 100 seconds and reset the flag. If we already ran a metadata extraction once, we need to wait for 100 seconds to avoid rate limiting.
            wait_for_rate_limit()
            self.rate_limit_flag = False

        system_prompt_content = load_prompt("injury_metadata_extraction")
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

    def score_lead(self, new_lead_description: str, historical_context: str) -> str:
        """
        Scores a new lead by comparing it against historical data using a structured prompt.

        Args:
            new_lead_description (str): A detailed description of the new lead.
            historical_context (str): A formatted string containing search results of similar historical cases.

        Returns:
            str: The response from the language model with jurisdiction-modified score.
        """
        system_prompt_content = load_prompt("lead_scoring")
        self.logger.debug(
            f"Token count: {count_tokens(new_lead_description) + count_tokens(historical_context) + count_tokens(system_prompt_content)}"
        )
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
            self.logger.debug("Attempting to score lead, sending messages to client...")
            response = self.get_response_with_tools(messages_to_send)

            # Extract the original score from the response
            original_score = extract_score_from_response(response)
            self.logger.debug(f"Extracted original score: {original_score}")

            # Extract jurisdiction from the response
            jurisdiction = extract_jurisdiction_from_response(response)
            self.logger.debug(f"Extracted jurisdiction: {jurisdiction}")

            # Apply jurisdiction modifier if jurisdiction was found
            if len(jurisdiction) > 0 and original_score > 0:
                # Initialize jurisdiction scoring manager
                jurisdiction_manager = JurisdictionScoreManager()

                # Get jurisdiction modifier
                modifier = jurisdiction_manager.get_jurisdiction_modifier(jurisdiction)
                self.logger.debug(
                    f"Jurisdiction modifier for {jurisdiction}: {modifier}"
                )

                # Apply modifier to the score
                modified_score = int(round(original_score * modifier))

                # Ensure the score stays within bounds (1-100)
                modified_score = max(1, min(100, modified_score))
                self.logger.info(
                    f"Score modified from {original_score} to {modified_score} using jurisdiction modifier {modifier}"
                )

                # Replace the original score in the response with the modified score
                response = re.sub(
                    r"Lead Score:\s*\d+/100",
                    f"Lead Score: {modified_score}/100",
                    response,
                    flags=re.IGNORECASE,
                )

            return response

        except Exception as e:
            self.logger.error("An unexpected error occurred in score_lead: %s", e)
            return f"An error occurred while scoring the lead: {e}"


def extract_score_from_response(response: str) -> int:
    """
    Extract the numerical lead score from the AI response.

    Args:
        response (str): The AI response containing the lead score

    Returns:
        int: The extracted score (1-100), or 0 if not found
    """
    # Look for "Lead Score: X/100" pattern
    pattern = r"Lead Score:\s*(\d+)/100"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Fallback: look for any number followed by /100
    pattern = r"(\d+)/100"
    match = re.search(pattern, response)

    if match:
        return int(match.group(1))

    return 0


def extract_jurisdiction_from_response(response: str) -> str:
    """
    Extract the jurisdiction from the AI response using the structured format.

    Args:
        response (str): The AI response containing jurisdiction information

    Returns:
        str: The extracted jurisdiction name, or empty string if not found
    """
    # Look for "Jurisdiction: [County Name]" pattern
    pattern = r"Jurisdiction:\s*([A-Z][a-zA-Z\s]+County)"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    # Fallback: look for general county patterns in case format wasn't followed exactly
    pattern = r"([A-Z][a-zA-Z\s]+County)"
    match = re.search(pattern, response)

    if match:
        return match.group(1).strip()

    return ""


def wait_for_rate_limit(seconds_to_wait: int = 120) -> None:
    """
    Waits for a specified amount of time to avoid rate limiting, defaults to 120 seconds.
    """
    logger.debug(f"Waiting for {seconds_to_wait} seconds to avoid rate limiting...")
    time.sleep(seconds_to_wait)
    logger.debug("Done waiting.")


def summarize_text_with_llm(text: str) -> str:
    """
    Summarizes the given text using the language model.
    """
    if count_tokens(text) > 13000:
        logger.warning("The text is too long to summarize.")
        return "The text is too long to summarize."

    logger.info("Summarizing text with LLM...")
    chat_manager = ChatManager()
    system_prompt = load_prompt("summarize_text")
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=text)]
    summary = chat_manager.get_response_with_tools(messages)
    logger.debug(f"Summary: {summary}")
    return summary


# TODO: How to make this call an LLM to summarize the file text?
@tool
def get_file_content(filepath: str) -> str:
    """
    Gets the text content from a single file. If the content is too long,
    it will be summarized.

    Args:
        filepath (str): The path to the file to read.

    Returns:
        str: The text content of the file, or an error message if reading fails.
    """
    try:
        logger.info(f"Tool 'get_file_content' called for: {filepath}")
        parsed_content = get_text_from_file(filepath)

        if parsed_content and "content" in parsed_content:
            content = parsed_content["content"]
            if (
                count_tokens(content) > 1000
            ):  # Check if token count is over 2000, might need to remove this entirely and always summarize the text.
                content = summarize_text_with_llm(content)
            return content
        else:
            logger.warning(f"No content found in file: {filepath}")
            return f"Warning: No content found in file: {filepath}"

    except Exception as e:
        logger.error(f"Error reading file {filepath}: {e}")
        return f"Error: Failed to read file {filepath}. Reason: {e}"


class ToolManager:
    def __init__(self, tools: List[Callable]):
        self.config = config
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in self.tools}

    def call_tool(self, tool_call: dict) -> str:
        """
        Calls a tool with the given arguments.
        """
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            return "Error: Tool call must have a 'name'."

        tool_to_call = self.tool_map.get(tool_name)
        if not tool_to_call:
            return f"Error: Tool '{tool_name}' not found."

        try:
            logger.debug(f"Calling tool '{tool_name}' with args: {tool_args}")
            output = tool_to_call.invoke(tool_args)
            return str(output)
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return f"Error executing tool '{tool_name}': {e}"
