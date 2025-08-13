# ─── FILE CONTENT TOOL ──────────────────────────────────────────────────────────

from typing import List, Callable
from utils import count_tokens, setup_logger, load_config
from scripts.filemanagement import get_text_from_file
from .agents.utils.summarization_registry import get_summarization_client
from .caching import SummaryCacheEntry

from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

config = load_config()
logger = setup_logger(__name__, config)

# ─── EXCEPTIONS ─────────────────────────────────────────────────────────────
class ToolCallLimitReached(Exception):
    pass

class ToolManager:
    def __init__(self, tools: List[Callable], tool_call_limit: int = 5):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.tool_call_count = 0
        self.tool_call_limit = tool_call_limit
        self.tool_call_history = []  # Track which tools were called

    def call_tool(self, tool_call: dict) -> ToolMessage:
        """
        Calls a tool with the given arguments and returns a ToolMessage.
        
        Handles different return types intelligently:
        - For tuple returns (content, token_count): Returns ToolMessage with content as the first element
          and token_count stored in metadata for usage tracking
        - For other types: Returns ToolMessage with str(output) as content
        
        Args:
            tool_call (dict): Tool call dictionary containing 'name', 'args', and 'id'
            
        Returns:
            ToolMessage: A properly formatted tool message with content and optional metadata
        """
        #if self.tool_call_count >= self.tool_call_limit: #TODO: Should call_tool handle the limiting, or should the agent
           # return ToolCallLimitReached(f'Tool call limit ({self.tool_call_limit}) reached, cannot use more tools.')
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            return ToolMessage(
                content="Error: Tool call must have a 'name'.",
                tool_call_id=tool_call.get("id", "unknown")
            )

        tool_to_call = self.tool_map.get(tool_name)
        if not tool_to_call:
            return ToolMessage(
                content=f"Error: Tool '{tool_name}' not found.",
                tool_call_id=tool_call.get("id", "unknown")
            )

        try:
            logger.debug(f"Calling tool '{tool_name}' with args: {tool_args}")
            output = tool_to_call.invoke(tool_args)
            self.tool_call_count += 1
            
            # Track the tool call in history
            self.tool_call_history.append({
                "tool_name": tool_name,
                "args": tool_args,
                "call_id": tool_call.get("id", "unknown")
            })
            
            # Handle tuple returns (content, token_count) for get_file_context
            if isinstance(output, tuple) and len(output) == 2 and isinstance(output[1], int):
                content, token_count = output
                return ToolMessage(
                    content=content,
                    tool_call_id=tool_call.get("id", "unknown"),
                    metadata={"token_count": token_count}
                )
            else:
                return ToolMessage(
                    content=str(output),
                    tool_call_id=tool_call.get("id", "unknown")
                )
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return ToolMessage(
                content=f"Error executing tool '{tool_name}': {e}",
                tool_call_id=tool_call.get("id", "unknown")
            )

            
    def batch_tool_call(self, tool_calls_batch: List[Callable]) -> List:
        logger.info("Batch tool call for '%i' tools.", len(tool_calls_batch))
        tool_calls_data = []
        for tool_call in tool_calls_batch:
            tool_output = self.call_tool(tool_call)
            tool_calls_data.append(tool_output)
        return tool_calls_data
    
    def get_tool_usage_summary(self) -> str:
        """
        Generate a summary of tool usage for reporting.
        
        Returns:
            str: A formatted summary of which tools were used and how many times.
        """
        if not self.tool_call_history:
            return "No tool calls were made."
        
        # Count tool usage by name
        tool_counts = {}
        for call in self.tool_call_history:
            tool_name = call["tool_name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        # Format the summary
        tool_list = []
        for tool_name, count in tool_counts.items():
            if count == 1:
                tool_list.append(f"{tool_name} (1 time)")
            else:
                tool_list.append(f"{tool_name} ({count} times)")
        
        return f"Tools used: {', '.join(tool_list)}"
    
@tool
def get_file_context(filepath: str, token_threshold: int = 1000) -> tuple:
    """
    Retrieves content from a file and returns it along with token count, summarizes the content
    if it surpasses token_threshold.

    Args:
        filepath (str): Path to the file to read.
        token_threshold (int): Maximum tokens allowed before summarization client is triggered

    Returns:
        tuple: A tuple containing (content, token_count) on success, or a string error message on failure for a clean fallback rather than raising an error.
               - content (str): The text content extracted from the file
               - token_count (int): Number of tokens in the content
    """
    try:
        parsed = get_text_from_file(filepath)
        if not parsed or 'content' not in parsed:
            return f"Warning: No content found in file: {filepath}"
        
        content = parsed['content']
        original_tokens = count_tokens(content)

        # Check if we need to summarize and have a summarization client
        summarization_client = get_summarization_client()
        
        if summarization_client and original_tokens > token_threshold:
            logger.info("File '%s' has '%i' tokens > '%i'; summarising...", filepath, original_tokens, token_threshold)
            
            # Use summarization client with caching support
            content = summarization_client.summarize_text(content, source_file=filepath)
            token_count = count_tokens(content)       
        else:
            logger.info("File '%s' has '%i' tokens ≤ '%i'; summarization not required.", filepath, original_tokens, token_threshold)
            token_count = original_tokens

        return(content, token_count)
    except Exception as e:
        logger.error(f"Failed to read file '{filepath}': {type(e).__name__}: {str(e)}")
        return f"Error: Unable to read file {filepath}"

