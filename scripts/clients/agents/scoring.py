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
        self.tool_manager = ToolManager(tools=[get_file_context])
        self.summarizer = kwargs.pop('summarizer', None)
        if self.summarizer is not None:
            set_summarizer(self.summarizer.summarize_text)

        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )
        if 'temperature' in kwargs:
            self.client.client.temperature = kwargs['temperature']

        #bind tools to underlying langchain client    
        self.client.client = self.client.client.bind_tools(self.tool_manager.tools)

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
        self.logger.debug("Reset tool call count for new lead scoring session")
        
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

        tool_call_count = 0
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
            
            # Check confidence from the AI response to decide if we should continue with tools
            confidence_score = extract_confidence_from_response(response.content)
            if confidence_score >= 80 or tool_call_count >= 5:
                # Determine the reason for stopping tool usage
                if confidence_score >= 80:
                    reason = f'Your confidence score of {confidence_score} is >= 80, which meets the threshold for high confidence.'
                else:
                    reason = f'You have reached the maximum of 5 tool calls.'
                
                # Add instruction explaining why we're stopping tool usage
                instruction_message = SystemMessage(content=f'{reason} Proceed to provide your final analysis without additional tool calls.')
                messages_to_send.append(instruction_message)
                return self.client.invoke(messages_to_send).content
            
            tool_call_count += len(response.tool_calls)

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
