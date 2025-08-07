from typing import Optional, List
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
import re

from ..base import BaseClient
from utils import load_prompt, count_tokens, setup_logger, load_config
from scripts.jurisdictionscoring import JurisdictionScoreManager
from ..tools import get_file_context, ToolManager
from .utils.summarization_registry import set_summarizer



class LeadScoringClient:

    def __init__(self, client: BaseClient, **kwargs):
        """
        Initialize the LeadScoringClient.

        Args:
            client (BaseClient): The underlying AI client.
            summarizer (SummarizationClient, optional, in kwargs): Summarization agent for file content tool.
            temperature (float, optional): Temperature setting for the model. Will be passed to the client.
        """
        # Prevent using the abstract BaseClient class directly
        if client.__class__ == BaseClient:
            raise ValueError(
                "Cannot use BaseClient directly. Please provide a concrete implementation "
                "that inherits from BaseClient (e.g., AzureClient)."
            )

        self.client = client
        self.prompt = load_prompt('lead_scoring')
        self.tool_manager = ToolManager(tools=[get_file_context], tool_call_limit=5)
        # Extract summarizer from kwargs and register it globally for use across the application
        self.summarizer = kwargs.pop('summarizer', None)
        if self.summarizer is not None:
            # Register the summarizer's summarize_text method in the global registry (summarization_registry.py)
            # so other components can access it without passing it through every function call
            set_summarizer(self.summarizer.summarize_text)

        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )
        if 'temperature' in kwargs:
            self.client.client.temperature = kwargs['temperature']

        #bind tools to underlying langchain client    
        self.client.client = self.client.client.bind_tools(self.tool_manager.tools)
        self.logger.debug(f"Tools bound to client: {self.tool_manager.tools}")

    def score_lead(self, new_lead_description: str, historical_context: str) -> str:
        """
        Scores a new lead by comparing it against historical data using a structured prompt.

        Args:
            new_lead_description (str): A detailed description of the new lead.
            historical_context (str): A formatted string containing search results of similar historical cases.

        Returns:
            str: The response from the language model with jurisdiction-modified score.
        """
        # Reset tool call count for this new lead scoring session
        self.tool_manager.tool_call_count = 0
        
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
            
            # Add the messages to message_history first, then call with None to use message_history
            self.client.message_history.extend(messages_to_send)
            response = self.get_response_with_tools(None)

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
        
    def get_response_with_tools(self, messages: list = None) -> str:
        """
        Gets a response from the chat model, handling tool calls automatically.
        
        This method implements an iterative tool-calling process where:
        1. AI scores a lead and returns response with confidence score
        2. Check if tool_call_count exceeded limit (5) or confidence >= 80
        3. If criteria not met, instruct AI to continue with tool calls
        4. Process tool calls and restart until criteria fulfilled

        Args:
            messages (list, optional): Initial messages (system prompt + user message).
                 If not provided, the instance's message history will be used.

        Returns:
            str: The content of the model's final response.
        """
        self.logger.debug(f"Getting response with tool access...")
        
        # Initialize clean message history with initial messages
        if messages is not None:
            # Start with clean message history containing only initial messages
            self.client.message_history = messages.copy()
        
        # Calculate initial token count
        total_tokens = sum(
            count_tokens(str(message.content)) 
            for message in self.client.message_history 
            if hasattr(message, "content") and message.content
        )
        self.logger.debug(f"Initial token count: {total_tokens}")

        while True:
            # Step 1: Get AI response
            response = self._get_ai_response()
            
            # Step 2: Check if AI wants to use tools
            if not response.tool_calls:
                return response.content
            
            # Step 3: Process tool calls
            self._process_tool_calls(response.tool_calls)
            
            # Step 4: Check if we should continue or stop
            if self._should_stop_tool_usage(response.content):
                return self._get_final_response(response.content)
            
            # Step 5: Continue with more tool calls
            self._instruct_continue_tool_calls()

    def _get_ai_response(self):
        """Get response from AI and add to message history."""
        response = self.client.invoke(self.client.message_history)
        self.logger.debug(f"AI Response: {response.content}")
        self.logger.debug(f"Tool calls in response: {response.tool_calls}")
        self.client.message_history.append(response)
        return response

    def _process_tool_calls(self, tool_calls):
        """Process tool calls and add responses to message history."""
        self.logger.info(f"Processing {len(tool_calls)} tool calls...")
        
        for tool_call in tool_calls:
            tool_message = self.tool_manager.call_tool(tool_call)
            self.client.message_history.append(tool_message)

    def _should_stop_tool_usage(self, response_content: str) -> bool:
        """
        Check if tool usage should stop based on confidence score or tool call limit.
        
        Args:
            response_content (str): The AI's response content
            
        Returns:
            bool: True if tool usage should stop, False otherwise
        """
        # Check tool call limit
        if self.tool_manager.tool_call_count >= self.tool_manager.tool_call_limit:
            self.logger.info(f"Tool call limit ({self.tool_manager.tool_call_limit}) reached. Stopping tool usage.")
            return True
        
        # Check confidence score
        confidence_score = extract_confidence_from_response(response_content)
        if confidence_score >= 80:
            self.logger.info(f"Confidence score {confidence_score} >= 80, stopping tool usage")
            return True
        
        return False

    def _instruct_continue_tool_calls(self):
        """Add instruction to continue making tool calls."""
        instruction_message = SystemMessage(
            content=f"Continue making tool calls to gather more information. You have made {self.tool_manager.tool_call_count} tool calls so far."
        )
        self.client.message_history.append(instruction_message)

    def _get_final_response(self, last_response_content: str) -> str:
        """
        Get final response from AI after stopping tool usage.
        
        Args:
            last_response_content (str): Content of the last AI response
            
        Returns:
            str: Final AI response without tool calls
        """
        # Determine reason for stopping
        if self.tool_manager.tool_call_count >= self.tool_manager.tool_call_limit:
            reason = f'You have reached the maximum of {self.tool_manager.tool_call_limit} tool calls.'
        else:
            confidence_score = extract_confidence_from_response(last_response_content)
            reason = f'Your confidence score of {confidence_score} is >= 80, which meets the threshold for high confidence.'
        
        # Add instruction to continue without tools
        instruction_message = SystemMessage(
            content=f'{reason} Proceed to provide your final analysis without additional tool calls.'
        )
        self.client.message_history.append(instruction_message)
        
        # Get final response
        final_response = self.client.invoke(self.client.message_history)
        return final_response.content


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

def extract_confidence_from_response(response: str) -> int:
    """
    Extract the numerical confidence score from the AI response.

    Args:
        response (str): The AI response containing the confidence score

    Returns:
        int: The extracted confidence (1-100), or 50 if not found
    """
    # Look for "Confidence Score: X/100" pattern (primary format from prompt)
    pattern = r"Confidence Score:\s*(\d+)/100"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Look for "Confidence: X/100" pattern
    pattern = r"Confidence:\s*(\d+)/100"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Look for "Confidence Level: X%" pattern
    pattern = r"Confidence Level:\s*(\d+)%"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Look for "Confidence: X%" pattern
    pattern = r"Confidence:\s*(\d+)%"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    return 0  # Default to 0 confidence if not found
