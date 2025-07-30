# ─── FILE CONTENT TOOL ──────────────────────────────────────────────────────────
from typing import Optional, List, Callable
from utils import count_tokens, setup_logger, load_config
from scripts.filemanagement import get_text_from_file

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
def get_file_content(filepath: str, summarizer=None, max_tokens: int = 10000) -> str:
    """
    Gets the text content from a single file. If the content is too long,
    it will be summarized using the provided summarizer.

    Args:
        filepath (str): The path to the file to read.
        summarizer (object, optional): An agent with a summarize_text(text) method.
        max_tokens (int): The token threshold above which summarization is triggered.

    Returns:
        str: The text content of the file, possibly summarized, or an error message.
    """
    try:
        logger.info(f"Tool 'get_file_content' called for: {filepath}")
        parsed_content = get_text_from_file(filepath)

        if parsed_content and "content" in parsed_content:
            content = parsed_content["content"]
            
            if summarizer and count_tokens(content) > max_tokens:
                content = summarizer.summarize_text(content)
            elif not summarizer and count_tokens(content) > max_tokens:
                logger.warning(f"No summarizer provided for get_file_content; returning first 2000 characters only.")
                content = content[:2000]
                
            return content
        else:
            logger.warning(f"No content found in file: {filepath}")
            return f"Warning: No content found in file: {filepath}"

    except Exception as e:
        logger.error(f"Failed to read file '{filepath}': {type(e).__name__}: {str(e)}")
        return f"Error: Unable to read file {filepath}"
