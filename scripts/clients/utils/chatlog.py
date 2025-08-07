from typing import List, Any
from langchain_core.messages import BaseMessage
import sys
import os

# Add the project root to the path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
from utils import save_to_json


def dump_chat_log(message_history: List[BaseMessage], filename: str = "chat_log.json") -> None:
    """
    Saves the message history to a JSON file using the save_to_json utility.
    
    Args:
        message_history (List[BaseMessage]): List of messages to save.
        filename (str, optional): Name of the file to save to. Defaults to "chat_log.json".
    
    Note:
        The file will be overwritten each time this method is called.
    """
    # Convert messages to serializable format
    serializable_messages = []
    for message in message_history:
        message_dict = {
            "type": message.__class__.__name__,
            "content": message.content if hasattr(message, 'content') else str(message),
            "additional_kwargs": message.additional_kwargs if hasattr(message, 'additional_kwargs') else {}
        }
        
        # Add tool-specific fields if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            message_dict["tool_calls"] = message.tool_calls
        if hasattr(message, 'tool_call_id') and message.tool_call_id:
            message_dict["tool_call_id"] = message.tool_call_id
            
        serializable_messages.append(message_dict)
    
    # Save to JSON file (will overwrite existing file)
    save_to_json(serializable_messages, default_filename=filename)
