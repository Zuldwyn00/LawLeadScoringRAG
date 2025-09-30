"""
Chat Discussion Agent

This module contains the ChatDiscussionAgent class for handling lead discussions
with AI assistance using a dedicated agent pattern.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from ..base import BaseClient
from ..tools import ToolManager, get_file_context, query_vector_context
from utils import load_prompt, setup_logger, load_config


class ChatDiscussionAgent:
    """
    A specialized agent for handling lead discussions with AI assistance.
    
    This agent provides a conversational interface for discussing scored leads,
    with access to file context and vector search tools.
    """

    def __init__(self, client: BaseClient):
        """
        Initialize the ChatDiscussionAgent with a client.

        Args:
            client (BaseClient): A concrete implementation of BaseClient
                                (e.g., AzureClient) for LLM communication.

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
        
        # Initialize tool manager with unlimited tool calls
        self.tool_manager = ToolManager(
            tools=[get_file_context, query_vector_context], 
            tool_call_limit=999999
        )
        
        # Bind tools to the client
        self.client.client = self.client.client.bind_tools(self.tool_manager.tools)
        
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
            
            self.logger.info("Initialized chat discussion for lead: %s", lead.get('id', 'unknown'))
            
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
        try:
            # Add user message to history
            user_message = HumanMessage(content=user_input)
            self.client.add_message(user_message)
            
            # Get AI response
            response = self.client.invoke()
            
            # Add AI response to history
            ai_message = AIMessage(content=response.content)
            self.client.add_message(ai_message)
            
            return response.content
            
        except Exception as e:
            error_msg = f"Error during chat discussion: {e}"
            self.logger.error(error_msg)
            return error_msg

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
