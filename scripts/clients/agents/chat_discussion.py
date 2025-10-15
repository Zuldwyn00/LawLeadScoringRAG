"""
Chat Discussion Agent

This module contains the ChatDiscussionAgent class for handling lead discussions
with AI assistance using a dedicated agent pattern.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from ..base import BaseClient
from ..azure import AzureClient
from scripts.vectordb import QdrantManager
from .utils.vector_registry import set_vector_clients
from ..tools import ToolManager, get_file_context, query_vector_context, list_all_files_for_caseid
from utils import load_prompt, setup_logger, load_config


class ChatDiscussionAgent:
    """
    A specialized agent for handling lead discussions with AI assistance.
    
    This agent provides a conversational interface for discussing scored leads,
    with access to file context and vector search tools.
    """

    def __init__(self, client: BaseClient, qdrant_manager=None, embedding_client=None, tool_call_limit=9999):
        """
        Initialize the ChatDiscussionAgent with a client.

        Args:
            client (BaseClient): A concrete implementation of BaseClient
                                (e.g., AzureClient) for LLM communication.
            qdrant_manager (QdrantManager, optional): Pre-initialized vector database manager.
            embedding_client (BaseClient, optional): Pre-initialized embedding client.
            tool_call_limit (int): Maximum number of tool calls allowed (default: 50).

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
        self.prompt = load_prompt("lead_discussion")
        self.logger = setup_logger(self.__class__.__name__, load_config())
        
        # Initialize tool manager with reasonable tool call limit
        self.tool_manager = ToolManager(
            tools=[get_file_context, query_vector_context, list_all_files_for_caseid], 
            tool_call_limit=tool_call_limit
        )
        
        # Bind tools to the client
        self.client.client = self.client.client.bind_tools(self.tool_manager.tools)
        
        # Use provided clients or create new ones only if necessary
        if qdrant_manager and embedding_client:
            # Use pre-initialized clients (preferred for performance)
            set_vector_clients(qdrant_manager, embedding_client)
            self.logger.info(
                "Using provided vector clients for chat: qdrant='%s', embedding='%s'",
                qdrant_manager.__class__.__name__,
                embedding_client.client_config.get("deployment_name", "unknown"),
            )
        else:
            # Fallback: create new clients (less efficient)
            try:
                qdrant_manager = QdrantManager()
                embedding_client = AzureClient("text_embedding_3_large")
                set_vector_clients(qdrant_manager, embedding_client)
                self.logger.info(
                    "Created new vector clients for chat: qdrant='%s', embedding='%s'",
                    qdrant_manager.__class__.__name__,
                    embedding_client.client_config.get("deployment_name", "unknown"),
                )
            except Exception as e:
                self.logger.error("Failed to register vector clients for chat: %s", e)

        self.logger.info(
            "Initialized %s with %s", self.__class__.__name__, client.__class__.__name__
        )

    def initialize_for_lead(self, lead: Dict[str, Any]) -> None:
        """
        Initialize the agent for discussing a specific lead.
        
        Args:
            lead (Dict[str, Any]): The lead data to discuss
        """
        try:
            # Clear any existing history
            self.client.clear_history()
            
            # Add system message with the lead discussion prompt
            system_message = SystemMessage(content=self.prompt)
            self.client.add_message(system_message)
            
            # Load lead context
            self._load_lead_context(lead)
            
            # Get a meaningful identifier for the lead using the same logic as the UI
            try:
                # Extract title from analysis text if available
                analysis_text = lead.get('_edited_analysis') or lead.get('analysis', '')
                if analysis_text:
                    from .scoring import extract_title_from_response
                    title = extract_title_from_response(analysis_text)
                    if title and title != "Title not available":
                        lead_title = title
                    else:
                        # Fallback to score-based title
                        score = lead.get('score', 'N/A')
                        lead_title = f"Lead (Score: {score}/100)"
                else:
                    # Fallback to score-based title
                    score = lead.get('score', 'N/A')
                    lead_title = f"Lead (Score: {score}/100)"
            except Exception:
                # Fallback if title extraction fails
                lead_title = lead.get('id') or lead.get('timestamp') or 'unknown'
            
            self.logger.info("Initialized chat discussion for lead: %s", lead_title)
            
        except Exception as e:
            self.logger.error("Error initializing chat discussion: %s", e)
            raise

    def _load_lead_context(self, lead: Dict[str, Any]) -> None:
        """
        Load the lead context into the chat history.
        
        Args:
            lead (Dict[str, Any]): The lead data
        """
        try:
            # Get analysis text (prefer edited version if available)
            analysis_text = lead.get('_edited_analysis') or lead.get('analysis', '')
            description_text = lead.get('description', '')
            
            if analysis_text:
                analysis_message = AIMessage(content=f"**AI Analysis:**\n{analysis_text}")
                self.client.add_message(analysis_message)
            
            if description_text:
                description_message = HumanMessage(content=f"**Original Lead Description:**\n{description_text}")
                self.client.add_message(description_message)
                
        except Exception as e:
            self.logger.error("Error loading lead context: %s", e)

    def send_message(self, user_input: str) -> str:
        """
        Send a user message and get the AI response.
        
        Args:
            user_input (str): The user's message
            
        Returns:
            str: The AI's response
        """
        # Safeguard: prevent concurrent sends which can break tool-call protocol
        if getattr(self, "_in_flight", False):
            self.logger.info("Ignored send while previous request is in-flight")
            return "Please wait for the current response to finish."

        try:
            self._in_flight = True
            # Add user message to history
            user_message = HumanMessage(content=user_input)
            self.client.add_message(user_message)

            # Get AI response
            response = self.client.invoke()

            # Handle tool calls iteratively until resolved or limit reached
            final_text = ""
            while hasattr(response, "tool_calls") and response.tool_calls:
                if self.tool_manager.tool_call_count >= self.tool_manager.tool_call_limit:
                    self.logger.warning("Tool call limit reached, stopping tool usage")
                    final_text = response.content or "I've reached the tool usage limit for this conversation."
                    break

                try:
                    # Normalize tool calls to the dict format expected by ToolManager
                    normalized_calls = self._normalize_tool_calls(response.tool_calls)
                    # Execute tools and append tool messages to history to satisfy adjacency requirements
                    tool_msgs = self.tool_manager.batch_tool_call(normalized_calls)
                    self.client.add_message(tool_msgs)

                    # Re-invoke model after tool results are appended
                    response = self.client.invoke()
                except Exception as tool_err:
                    self.logger.error("Tool processing failed: %s", tool_err)
                    final_text = f"Tool error: {tool_err}"
                    break

            # If no further tool calls, capture final content
            if not final_text:
                final_text = response.content or ""

            # Record the final assistant message content
            ai_message = AIMessage(content=final_text)
            self.client.add_message(ai_message)

            return final_text

        except Exception as e:
            error_msg = f"Error during chat discussion: {e}"
            self.logger.error(error_msg)
            return error_msg
        finally:
            self._in_flight = False

    def _normalize_tool_calls(self, tool_calls: list) -> list:
        """Normalize tool call objects into {'name','args','id'} dicts for ToolManager.

        Handles both direct {'name','args','id'} and 'function' style with JSON string arguments.
        """
        normalized: list = []
        for call in tool_calls:
            try:
                # Extract id
                call_id = getattr(call, 'id', None) or (call.get('id') if isinstance(call, dict) else None) or 'unknown'

                # Extract name
                name = None
                if isinstance(call, dict):
                    name = call.get('name')
                else:
                    name = getattr(call, 'name', None)
                if not name:
                    function_obj = (call.get('function') if isinstance(call, dict) else getattr(call, 'function', None)) or {}
                    name = function_obj.get('name') if isinstance(function_obj, dict) else getattr(function_obj, 'name', None)

                # Extract args
                args = None
                if isinstance(call, dict):
                    args = call.get('args')
                else:
                    args = getattr(call, 'args', None)
                if not args:
                    function_obj = (call.get('function') if isinstance(call, dict) else getattr(call, 'function', None)) or {}
                    arguments = function_obj.get('arguments') if isinstance(function_obj, dict) else getattr(function_obj, 'arguments', None)
                    if isinstance(arguments, str):
                        try:
                            import json as _json
                            parsed = _json.loads(arguments)
                            args = parsed if isinstance(parsed, dict) else {"input": parsed}
                        except Exception:
                            args = {"input": arguments}
                    elif arguments is not None:
                        args = arguments
                if args is None:
                    args = {}

                if not name:
                    self.logger.error("Tool call missing name; id='%s'", call_id)
                    continue

                normalized.append({
                    'name': name,
                    'args': args,
                    'id': call_id,
                })
            except Exception as e:
                self.logger.error("Failed to normalize tool call: %s", e)
        return normalized

    def get_chat_history(self) -> list:
        """
        Get the current chat history.
        
        Returns:
            list: List of messages in the chat history
        """
        return self.client.message_history

    def clear_history(self) -> None:
        """
        Clear the chat history.
        """
        self.client.clear_history()

    def save_chat_history(self, lead_id: str) -> None:
        """
        Save the current chat history for a specific lead.
        
        Args:
            lead_id (str): The ID of the lead
        """
        # This method can be extended to persist chat history
        # For now, it's handled by the UI layer
        pass
