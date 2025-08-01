# ─── FILE CONTENT TOOL ──────────────────────────────────────────────────────────
from calendar import c
from typing import Optional, List, Callable
from utils import count_tokens, setup_logger, load_config
from scripts.filemanagement import get_text_from_file
from .agents.utils.summarization_registry import set_summarizer, get_summarizer

from langchain_core.tools import tool

config = load_config()
logger = setup_logger(__name__, config)

# ─── EXCEPTIONS ─────────────────────────────────────────────────────────────
class ToolCallLimitReached(Exception):
    pass

class ToolManager:
    def __init__(self, tools: List[Callable]):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.tool_call_count = 0

    def call_tool(self, tool_call: dict) -> str:
        """
        Calls a tool with the given arguments.
        """
        if self.tool_call_count == 5:
            raise ToolCallLimitReached('Tool call limit reached, cannot use more tools.')
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
            self.tool_call_count += 1
            return str(output)
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return f"Error executing tool '{tool_name}': {e}"


@tool
def get_file_context(filepath: str, token_threshold: int = 4000) -> tuple:
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
        logger.info(f"Tool 'get_file_context' called for: {filepath}")
        parsed = get_text_from_file(filepath)
        if not parsed or 'content' not in parsed:
            return f"Warning: No content found in file: {filepath}"
        
        content = parsed['content']
        original_tokens = count_tokens(content)

        summarizer_fn = get_summarizer()
        if summarizer_fn and original_tokens > token_threshold:
            logger.info("File '%s' has '%i' tokens > '%i'; summarising...", filepath, original_tokens, token_threshold)
            content = summarizer_fn(content) 
            token_count = count_tokens(content)       
        else:
            token_count = original_tokens

        return(content, token_count)
    except Exception as e:
        logger.error(f"Failed to read file '{filepath}': {type(e).__name__}: {str(e)}")
        return f"Error: Unable to read file {filepath}"
