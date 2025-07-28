from email import message
import os
import re
import json
import time

from attr import dataclass
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from metrics import MetricsCollector
from typing import Optional, List
from enum import Enum
from abc import ABC, abstractmethod
from scripts.aiclients import RateLimiter, ToolManager, get_file_content, extract_score_from_response, extract_jurisdiction_from_response
from scripts.jurisdictionscoring import JurisdictionScoreManager
from utils import load_config, setup_logger, load_prompt, count_tokens

#TODO:
# Architecture: BaseClient -> ClientTypeClient -> SpecificClient -> ClientAgent
# Example: BaseClient -> AzureClient -> ChatClient -> MetadataExtractionClient


class BaseClient(ABC):
    """
    Abstract base class defining the interface for all AI clients.
    
    This class provides the fundamental interface that all clients must implement,
    regardless of the underlying provider or specific functionality.
    """
    
    def __init__(self,
                 metrics: Optional[MetricsCollector] = None,
                 rate_limiter: Optional[RateLimiter] = None,
                 message_history: Optional[List[BaseMessage]] = None):
        
        if metrics is None:
            metrics = MetricsCollector() #TODO: Define default MetricsCollector
        if message_history is None:
            message_history = []
        if rate_limiter is None:
            rate_limiter = RateLimiter()  #TODO: define default rate limiter

        self.config = load_config()
        self.logger = setup_logger(self.__class__.__name__, self.config)
        self.metrics = metrics
        self.rate_limiter = rate_limiter
        self.message_history = message_history
    
    @abstractmethod
    def invoke(self, messages: Optional[List[BaseMessage]] = None) -> AIMessage:
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


class AzureClient(BaseClient):
    """
    Azure OpenAI specific client implementation.
    
    Handles Azure-specific configuration, authentication, and rate limiting.
    """
    
    def __init__(self,
                 deployment_name: Optional[str] = None,
                 api_version: Optional[str] = None, 
                 endpoint: Optional[str] = None,
                 api_key: Optional[str] = None,
                 temperature: float = 0.0,
                 **kwargs):
        
        super().__init__(**kwargs)
        
        # Azure configuration
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION") 
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.temperature = temperature
        
        # Initialize the langchain client
        self._client = self._create_langchain_client()
    
    def _create_langchain_client(self):
        """Create and configure the Azure langchain client."""
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=(20 / 60),  # 20 requests per minute
            check_every_n_seconds=5,
            max_bucket_size=20
        )
        
        return AzureChatOpenAI(
            azure_deployment=self.deployment_name,
            openai_api_version=self.api_version,
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            temperature=self.temperature,
            rate_limiter=rate_limiter,
        )
    
    def invoke(self, messages: Optional[List[BaseMessage]] = None) -> AIMessage:
        """Send messages and get response"""
        messages_to_send = messages if messages is not None else self.message_history
        response = self._client.invoke(messages_to_send)
        
        if messages is None:
            self.message_history.append(response)
        
        return response


class ChatClient(AzureClient):
    """
    Chat-specific client that adds conversation and tool management capabilities.
    
    Extends AzureClient with chat-specific functionality like tool binding,
    multi-turn conversations, and tool call handling.
    """
    
    def __init__(self, 
                 tools: Optional[List] = None,
                 **kwargs):
        
        super().__init__(**kwargs)
        
        # Initialize tools
        if tools is None:
            tools = [get_file_content]
        self.tool_manager = ToolManager(tools=tools)
        
        # Bind tools to the langchain client
        self._client = self._client.bind_tools(self.tool_manager.tools)
    
    def get_response_with_tools(self, messages: Optional[List[BaseMessage]] = None) -> str:
        """
        Gets a response from the chat model, handling tool calls automatically.
        
        This method handles the full conversation loop including tool calls,
        preserving the exact logic from the original ChatManager.
        """
        self.logger.debug(f"Getting response with tool access...")
        messages_to_send = messages if messages is not None else self.message_history
        
        # Calculate total token count for all messages
        total_tokens = 0
        for message in messages_to_send:
            if hasattr(message, 'content') and message.content:
                total_tokens += count_tokens(str(message.content))
        self.logger.debug(f"Total token count: {total_tokens}")

        while True:
            response = self._client.invoke(messages_to_send)
            
            if messages is None:
                self.message_history.append(response)
            else:
                messages_to_send.append(response)

            if not response.tool_calls:
                return response.content
            
            self.logger.info(f"Model made {len(response.tool_calls)} tool calls.")
            
            for tool_call in response.tool_calls:
                tool_output = self.tool_manager.call_tool(tool_call)
                tool_message = ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call['id']
                )
                if messages is None:
                    self.message_history.append(tool_message)
                else:
                    messages_to_send.append(tool_message)


class MetadataExtractionClient(ChatClient):
    """
    Client agent specialized for extracting metadata from legal documents.
    
    Inherits chat and tool capabilities from ChatClient and adds domain-specific
    business logic for metadata extraction with retry handling and rate limiting.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rate_limit_flag = False
    
    def extract_metadata(self, text: str, filepath: str, case_id: str, retries: int = 2) -> dict:
        """
        Extracts metadata from text as a dictionary using AI.
        
        Args:
            text: The document text to extract metadata from
            filepath: Source file path for the document
            case_id: Unique identifier for the case
            retries: Number of retry attempts on failure
            
        Returns:
            dict: Extracted metadata with source and case_id added
        """
        if self.rate_limit_flag:
            self.rate_limiter.wait_for_rate_limit()
            self.rate_limit_flag = False

        system_prompt_content = load_prompt('injury_metadata_extraction')
        self.logger.debug(f"Token count: {count_tokens(text) + count_tokens(system_prompt_content)}")
        
        system_message = SystemMessage(content=system_prompt_content)
        user_message = HumanMessage(content=text)
        messages_to_send = [system_message, user_message]
        
        for attempt in range(retries):
            try:
                self.logger.debug(f"Attempting to define metadata (Attempt {attempt + 1}/{retries})...")
                response = self._client.invoke(messages_to_send).content
                
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
                self.logger.error(f"An unexpected error occurred on attempt {attempt + 1}: {e}")
                self.rate_limit_flag = True

        self.logger.error("Failed to define metadata after %s attempts.", retries)
        raise Exception(f"Failed to extract metadata for {filepath} after {retries} attempts.")


class LeadScoringClient(ChatClient):
    """
    Client agent specialized for scoring legal leads.
    
    Inherits chat and tool capabilities from ChatClient and adds domain-specific
    business logic for lead scoring with jurisdiction-based score modification.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.jurisdiction_manager = JurisdictionScoreManager()
    
    def score_lead(self, new_lead_description: str, historical_context: str) -> str:
        """
        Scores a new lead by comparing it against historical data.
        
        Args:
            new_lead_description: Description of the new lead to score
            historical_context: Formatted string of similar historical cases
            
        Returns:
            str: Complete scoring response with jurisdiction-modified score
        """
        system_prompt_content = load_prompt('lead_scoring')
        self.logger.debug(f"Token count: {count_tokens(new_lead_description) + count_tokens(historical_context) + count_tokens(system_prompt_content)}")
        
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
                modifier = self.jurisdiction_manager.get_jurisdiction_modifier(jurisdiction)
                self.logger.debug(f"Jurisdiction modifier for {jurisdiction}: {modifier}")
                
                # Apply modifier to the score
                modified_score = int(round(original_score * modifier))
                modified_score = max(1, min(100, modified_score))
                self.logger.info(f"Score modified from {original_score} to {modified_score} using jurisdiction modifier {modifier}")
                
                # Replace the original score in the response with the modified score
                response = re.sub(
                    r"Lead Score:\s*\d+/100",
                    f"Lead Score: {modified_score}/100",
                    response,
                    flags=re.IGNORECASE
                )
            
            return response
            
        except Exception as e:
            self.logger.error("An unexpected error occurred in score_lead: %s", e)
            return f"An error occurred while scoring the lead: {e}"


class SummarizationClient(ChatClient):
    """
    Client agent specialized for text summarization.
    
    Inherits chat and tool capabilities from ChatClient and adds domain-specific
    business logic for summarizing legal documents and other text content.
    """
    
    def summarize_text(self, text: str) -> str:
        """
        Summarizes the given text using the language model.
        
        Args:
            text: The text content to summarize
            
        Returns:
            str: The summarized text or warning if text is too long
        """
        if count_tokens(text) > 13000:
            self.logger.warning("The text is too long to summarize.")
            return "The text is too long to summarize."
        
        self.logger.info("Summarizing text with LLM...")
        system_prompt = load_prompt('summarize_text')
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]
        summary = self.get_response_with_tools(messages)
        self.logger.debug(f"Summary: {summary}")
        return summary


class GeneralChatClient(ChatClient):
    """
    General purpose chat client agent for conversational interactions.
    
    Inherits chat and tool capabilities from ChatClient without additional
    domain-specific logic. Useful for general AI assistance tasks.
    """
    pass


# Usage examples:
# metadata_client = MetadataExtractionClient()
# metadata = metadata_client.extract_metadata(text, filepath, case_id)
#
# scoring_client = LeadScoringClient()  
# score = scoring_client.score_lead(description, historical_context)
#
# summary_client = SummarizationClient()
# summary = summary_client.summarize_text(long_text)
#
# chat_client = GeneralChatClient()
# response = chat_client.get_response_with_tools(messages)



