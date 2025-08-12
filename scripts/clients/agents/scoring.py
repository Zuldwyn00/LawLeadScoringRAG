from typing import Callable, Optional, List
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
import re
from pathlib import Path
import hashlib

from scripts.clients.utils.chatlog import dump_chat_log

from ..base import BaseClient
from ..azure import AzureClient
from utils import load_prompt, count_tokens, setup_logger, load_config
from scripts.jurisdictionscoring import JurisdictionScoreManager
from ..tools import get_file_context, ToolManager
from .utils.summarization_registry import set_summarizer
from ..caching.cacheschema import SummaryCacheEntry



class LeadScoringClient:

    def __init__(self, client: BaseClient, summarizer = None, **kwargs):
        """
        Initialize the LeadScoringClient.

        Args:
            client (BaseClient): The underlying AI client.
            summarizer (SummarizationClient, optional): Summarization agent for file content tool. If not given then get_file_context will get the first
            X characters from the file rather than summarize with an LLM call.

            **kwargs: Optional keyword arguments:
                temperature (float, optional): Temperature setting for the main client.
                confidence_threshold (int, optional): Confidence threshold for tool usage (default: 80).
                final_model (str, optional): Model name for final scoring pass without tools (default: None).
                final_model_temperature (float, optional): Temperature for final model (default: None).
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
        self.current_lead_score = None

        # Extract summarizer from kwargs and register it globally for use across the application
        self.summarizer = summarizer
        if self.summarizer is not None:
            # Register the summarizer's summarize_text method with caching wrapper in the global registry
            # so other components can access it without passing it through every function call
            def _create_content_signature(text: str) -> Path:
                """Create a content-based signature for cache keying."""
                digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
                return Path(f"content://{digest}")

            def summarize_with_cache(text: str) -> str:
                """Wrapper that adds caching to summarization calls."""
                cache_manager = self.summarizer.client.cache_manager
                signature = _create_content_signature(text)
                client_type = self.summarizer.client.client_type

                # Try to get cached result
                cached_entry = cache_manager.get_cached_entry(signature, client_type)
                if cached_entry:
                    self.logger.debug("Cache hit for content signature: %s", signature)
                    return cached_entry['summary']

                # Cache miss - perform summarization
                self.logger.debug("Cache miss for content signature: %s", signature)
                summary = self.summarizer.summarize_text(text)
                
                # Cache the result
                try:
                    entry = SummaryCacheEntry(
                        source_file=signature,
                        client=client_type,
                        tokens=count_tokens(text),
                        summary=summary,
                    )
                    cache_manager.cache_entry(entry)
                    self.logger.debug("Cached summary for signature: %s", signature)
                except Exception as e:
                    # Don't let cache failures break the main flow
                    self.logger.warning("Failed to cache summary: %s", e)
                
                return summary

            set_summarizer(summarize_with_cache)

        self.logger = setup_logger(self.__class__.__name__, load_config())
        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )

        self._initialize_kwargs(kwargs)

        #bind tools to underlying langchain client    
        self.client.client = self.client.client.bind_tools(self.tool_manager.tools)
        self.logger.debug(f"Tools bound to client: {self.tool_manager.tools}")

    def _initialize_kwargs(self, kwargs: dict) -> None:
        """
        Initialize all optional parameters from kwargs.
        
        Args:
            kwargs (dict): Keyword arguments passed to the constructor.
        """
        # Temperature for main client
        if 'temperature' in kwargs:
            self.client.client.temperature = kwargs['temperature']

        # Confidence threshold with default
        if 'confidence_threshold' in kwargs:
            self.confidence_threshold = kwargs.pop('confidence_threshold')
        else:
            self.confidence_threshold = 80

        # Final model configuration
        if 'final_model' in kwargs:
            self.final_model: str = kwargs.pop('final_model')
        else:
            self.final_model = None
            
        if 'final_model_temperature' in kwargs:
            self.final_model_temperature: Optional[float] = kwargs.pop('final_model_temperature')
        else:
            self.final_model_temperature = None
            
        # Initialize final client if final model is specified
        self.final_client: AzureClient | None = None
        if self.final_model:
            # Create a separate client that does not get tools bound
            self.final_client = AzureClient(self.final_model)
            # Apply separate temperature to final model if specified
            if self.final_model_temperature is not None:
                self.final_client.client.temperature = self.final_model_temperature

    def score_lead(self, new_lead_description: str, historical_context: str) -> str:
        """
        Scores a new lead by comparing it against historical data using a structured prompt.

        Args:
            new_lead_description (str): A detailed description of the new lead.
            historical_context (str): A formatted string containing search results of similar historical cases.

        Returns:
            str: The response from the language model with jurisdiction-modified score.
        """
        # Reset tool call count, history, and message history for this new lead scoring session
        self.tool_manager.tool_call_count = 0
        self.tool_manager.tool_call_history = []
        self.client.clear_history()
        
        system_prompt_content = load_prompt("lead_scoring")
        self.logger.debug(
            f"Token count: {count_tokens(new_lead_description) + count_tokens(historical_context) + count_tokens(system_prompt_content)}"
        )
        
        # Create system message with the main prompt
        system_message = SystemMessage(content=system_prompt_content)

        # Build an initial tool-usage system message so the model knows its starting budget
        initial_tool_usage_text = (
            f"Your tool usage count is at '{self.tool_manager.tool_call_count} out of "
            f"{self.tool_manager.tool_call_limit} maximum tool calls'."
        )
        initial_tool_usage_message = SystemMessage(content=initial_tool_usage_text)
        
        # Create historical context as a separate system message
        historical_context_message = SystemMessage(
            content=f"**Historical Case Summaries for Reference:**\n{historical_context}"
        )

        # Create user message with only the new lead description
        user_message = HumanMessage(content=new_lead_description)
        messages_to_send = [system_message, initial_tool_usage_message, historical_context_message, user_message]

        # Add all initial messages to message history so they appear in chat logs
        self.client.add_message([
            system_message,
            initial_tool_usage_message,
            historical_context_message,
            user_message,
        ])

        try:
            self.logger.debug("Attempting to score lead, sending messages to client...")
            response_message = self.recursive_tool_loop(messages_to_send)
            response = response_message.content

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

    def _build_tool_context_message(self, exclude_ids: set[str]) -> SystemMessage | None:
        """
        Build a compact SystemMessage of prior tool outputs, excluding any
        tool messages whose tool_call_id is in exclude_ids.

        Args:
            exclude_ids (set[str]): Tool call IDs to exclude (typically the current turn).

        Returns:
            SystemMessage | None: combined context or None if no prior tool messages.
        """
        prior_tool_msgs = [
            m for m in self.client.message_history
            if isinstance(m, ToolMessage) and getattr(m, "tool_call_id", None) not in exclude_ids
        ]
        if not prior_tool_msgs:
            return None

        # Keep it concise; format as a bulleted list.
        lines: List[str] = ["Tool Context So Far:"]
        for msg in prior_tool_msgs:
            content_snippet = msg.content #if len(msg.content) < 4000 else msg.content[:4000] + "..."
            lines.append(f"- {content_snippet}")

        content = "\n".join(lines)
        return SystemMessage(content=content)

    def _assemble_messages(
        self,
        base_messages: List[SystemMessage | HumanMessage],
        *,
        last_response: AIMessage | None = None,
        tool_call_responses: List[ToolMessage] | None = None,
        tool_context_msg: SystemMessage | None = None,
        extra_messages: List[SystemMessage | HumanMessage] | None = None,
    ) -> List:
        """
        Assemble messages for the next invoke, preserving tool-calls adjacency.

        Order rules:
        - If tool_call_responses exist:
          [base_messages, last_response, *tool_call_responses, tool_context_msg?, *extra_messages?]
        - Else:
          [base_messages, tool_context_msg?, last_response?, *extra_messages?]

        Args:
            base_messages: System/historical/user messages.
            last_response: The assistant message from the prior turn.
            tool_call_responses: Tool messages responding to last_response.tool_calls.
            tool_context_msg: Aggregated prior tool context as a single SystemMessage.
            extra_messages: Any additional instructions (e.g., continue/finalize).

        Returns:
            List: Ordered messages ready for invoke().
        """
        messages_to_send: List = [*base_messages]
        if tool_call_responses:
            if last_response is not None:
                messages_to_send.append(last_response)
            messages_to_send.extend(tool_call_responses)
            if tool_context_msg is not None:
                messages_to_send.append(tool_context_msg)
        else:
            if tool_context_msg is not None:
                messages_to_send.append(tool_context_msg)
            if last_response is not None:
                messages_to_send.append(last_response)

        if extra_messages:
            messages_to_send.extend(extra_messages)
        return messages_to_send

    def recursive_tool_loop(self, messages: list) -> AIMessage:
        """
        Drive the tool-use loop until either the confidence threshold is met or
        the tool-call limit is reached. Ensures tool messages are sent
        immediately after the assistant message that requested them.

        Args:
            messages (list): Initial message list to start the conversation.

        Returns:
            AIMessage: The final lead-scoring assistant message.
        """
        # If we haven't yet started the lead-scoring process, get our initial lead score.
        if self.current_lead_score is None:
            self.logger.info("No initial lead response, creating first response.")
            self.current_lead_score = self.client.invoke(messages)

        def get_response_recursive() -> AIMessage:
            def _validate_confidence_threshold_and_tool_limit() -> SystemMessage | None:
                if self.tool_manager.tool_call_limit == self.tool_manager.tool_call_count:
                    return SystemMessage(content="Tool call limit reached, provide your final lead score analysis.")
                confidence_score = extract_confidence_from_response(self.current_lead_score.content)
                if confidence_score >= self.confidence_threshold:
                    return SystemMessage(content=(
                        f"Confidence is {confidence_score} / {self.confidence_threshold} , "
                        "threshold for confidence reached, provide your final lead score analysis "
                    ))
                return None

            validation_msg = _validate_confidence_threshold_and_tool_limit()

            # If we've hit the confidence threshold or tool_call_limit, get the final lead.
            if validation_msg is not None:
                return self._get_final_lead_score(messages, validation_msg)

            # Use the most recent assistant message as the basis for tool handling.
            last_response: AIMessage = self.current_lead_score

            # If the model requested tools, call them and send tool messages
            # IMMEDIATELY after the assistant message with tool_calls.
            if getattr(last_response, "tool_calls", None):
                tool_call_responses = self.tool_manager.batch_tool_call(last_response.tool_calls)
                # Track tool messages in history for logging/debugging purposes
                self.client.add_message(tool_call_responses)

                current_ids = {tc["id"] for tc in last_response.tool_calls}
                tool_context_msg = self._build_tool_context_message(exclude_ids=current_ids)

                base_messages = messages  # [system, historical, user]
                messages_to_send = self._assemble_messages(
                    base_messages,
                    last_response=last_response,
                    tool_call_responses=tool_call_responses,
                    tool_context_msg=tool_context_msg,
                )
                self.current_lead_score = self.client.invoke(messages_to_send)
                return get_response_recursive()

            # If no tools were requested but we haven't met the threshold, instruct the model to continue.
            continue_message_text = (
                "You must continue using tools, your tool usage count is at "
                f"'{self.tool_manager.tool_call_count} out of {self.tool_manager.tool_call_limit} maximum tool calls, "
                "and confidence threshold had not been reached.'"
            )

            #if no tool calls were found, inform the AI it needs to make more and give it the historical context again.
            continue_message = SystemMessage(content=continue_message_text)
            base_messages = messages  # [system, historical, user]
            tool_context_msg = self._build_tool_context_message(exclude_ids=set())
            messages_to_send = self._assemble_messages(
                base_messages,
                last_response=last_response,
                tool_context_msg=tool_context_msg,
                extra_messages=[continue_message],
            )
            self.current_lead_score = self.client.invoke(messages_to_send)
            return get_response_recursive()

        final_lead = get_response_recursive()
        dump_chat_log(self.client.message_history)
        return final_lead

    def _get_final_lead_score(self, messages: list, validation_msg: SystemMessage) -> AIMessage:
        """
        Generate the final lead score when confidence threshold is met or tool call limit is reached.
        
        Args:
            messages (list): Base messages to start the conversation.
            validation_msg (SystemMessage): System message indicating why final scoring is triggered.
            
        Returns:
            AIMessage: The final lead scoring response.
        """
        base_messages = messages  # [system, historical, user]
        tool_context_msg = self._build_tool_context_message(exclude_ids=set())

        # Ensure any pending tool calls on the last assistant message are resolved
        tool_call_responses = None
        if getattr(self.current_lead_score, "tool_calls", None):
            tool_call_responses = self.tool_manager.batch_tool_call(self.current_lead_score.tool_calls)
            # Record tool messages in history
            self.client.add_message(tool_call_responses)

        # Create a detailed tool usage summary message for the AI to reference in its final response
        tool_usage_details = self.tool_manager.get_tool_usage_summary()
        tool_usage_summary_msg = SystemMessage(
            content=f"Tool Usage Summary: You made {self.tool_manager.tool_call_count} tool calls out of {self.tool_manager.tool_call_limit} maximum. "
                   f"{tool_usage_details}. Please include this exact information in your '**6. Analysis Depth & Tool Usage:**' section."
        )

        messages_to_send = self._assemble_messages(
            base_messages,
            last_response=self.current_lead_score,
            tool_call_responses=tool_call_responses,
            tool_context_msg=tool_context_msg,
            extra_messages=[validation_msg, tool_usage_summary_msg],
        )
        
        # Calculate and log token count for final lead scoring
        total_tokens = sum(count_tokens(str(message.content)) for message in messages_to_send)
        self.logger.info(f"Final lead scoring - Token count: {total_tokens}")
        
        # Use the final (no-tools) model for the last scoring pass
        if self.final_client is not None:
            final_lead = self.final_client.invoke(messages_to_send)
        else:
            final_lead = self.client.invoke(messages_to_send)
        return final_lead


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
