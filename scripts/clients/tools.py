# ─── FILE CONTENT TOOL ──────────────────────────────────────────────────────────

from typing import List, Callable
from utils import count_tokens, setup_logger, load_config
from scripts.file_management.filemanagement import get_text_from_file, resolve_relative_path
from .agents.utils.summarization_registry import get_summarization_client

from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from scripts.vectordb import QdrantManager

config = load_config()
logger = setup_logger(__name__, config)


# ─── EXCEPTIONS ─────────────────────────────────────────────────────────────
class ToolCallLimitReached(Exception):
    pass


class ToolManager:
    def __init__(self, tools: List[Callable], tool_call_limit: int = None):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in self.tools}
        self.tool_call_count = 0
        # Use config value if no tool_call_limit is provided
        self.tool_call_limit = tool_call_limit if tool_call_limit is not None else config.get('aiconfig', {}).get('tool_call_limit', 5)
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
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            return ToolMessage(
                content="Error: Tool call must have a 'name'.",
                tool_call_id=tool_call.get("id", "unknown"),
            )

        tool_to_call = self.tool_map.get(tool_name)
        if not tool_to_call:
            return ToolMessage(
                content=f"Error: Tool '{tool_name}' not found.",
                tool_call_id=tool_call.get("id", "unknown"),
            )

        try:
            logger.debug("Calling tool '%s' with args: %s", tool_name, tool_args)
            output = tool_to_call.invoke(tool_args)
            self.tool_call_count += 1

            # Track the tool call in history
            self.tool_call_history.append(
                {
                    "tool_name": tool_name,
                    "args": tool_args,
                    "call_id": tool_call.get("id", "unknown"),
                }
            )

            # Handle tuple returns (content, token_count) for get_file_context
            if (
                isinstance(output, tuple)
                and len(output) == 2
                and isinstance(output[1], int)
            ):
                content, token_count = output
                
                # ─── TOOL SUCCESS/FAILURE DETECTION ──────────────────────────────────────
                # Check if this is an error result and adjust counter accordingly
                if token_count == 0 and (content.startswith("Error:") or content.startswith("Warning:")):
                    self.tool_call_count -= 1
                    self.tool_call_history.pop()  # Remove the last history entry too
                # ─────────────────────────────────────────────────────────────────────────
                
                return ToolMessage(
                    content=content,
                    tool_call_id=tool_call.get("id", "unknown"),
                    metadata={"token_count": token_count},
                )
            else:
                return ToolMessage(
                    content=str(output), tool_call_id=tool_call.get("id", "unknown")
                )
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return ToolMessage(
                content=f"Error executing tool '{tool_name}': {e}",
                tool_call_id=tool_call.get("id", "unknown"),
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

#TODO: Replace hard-coded limit and collection name
@tool
def query_vector_context(search_query: str):
    """
    Search vector database for relevant context using natural language query.
    
    This tool converts the search query to embeddings and searches the vector database
    for similar content, returning formatted context that can be used by the AI.
    Uses the same qdrant and embedding clients that were used for the initial historical context.
    
    Args:
        search_query (str): Natural language search query to find relevant context
        
    Returns:
        str: JSON-formatted context from search result chunks, or error message
    """
    try:
        from .agents.utils.vector_registry import get_vector_clients
        
        # Get the registered vector clients (same ones used for historical context)
        qdrant_manager, embedding_client = get_vector_clients()
        
        if not qdrant_manager or not embedding_client:
            return "Error: Vector clients not available. Make sure vector clients are registered."
        
        logger.info("Searching vector database with query: '%s'", search_query)
        
        # Convert search query to embedding using registered client
        embedding = embedding_client.get_embeddings(search_query)
        logger.debug("Generated embedding with %d dimensions", len(embedding))
        
        # Search vectors using registered qdrant_manager 
        search_results = qdrant_manager.search_vectors(
            collection_name="case_files_large",  # Fixed collection name
            query_vector=embedding,
            vector_name="chunk",  # Use default chunk vector (same as in score_test)
            limit=5  # Fixed limit
            score_threshold=0.80
        )
        
        logger.info("Found %d search results from vector database", len(search_results))
        
        # Format results using existing method (same as in score_test)
        context = qdrant_manager.get_context(search_results)
        
        # Log context info for debugging
        logger.debug("Formatted context length: %d characters", len(context))
        
        return context
        
    except Exception as e:
        error_msg = f"Error searching vector database: {e}"
        logger.error("Vector search failed: %s", e)
        return error_msg


@tool
def get_file_context(filepath: str) -> tuple:
    """
    Retrieves content from a file and returns it along with token count, summarizes the content
    if it surpasses token_threshold.

    Args:
        filepath (str): Path to the file to read (can be relative or absolute).

    Returns:
        tuple: A tuple containing (content, token_count). On error, returns (error_message, 0).
               - content (str): The text content extracted from the file or error message
               - token_count (int): Number of tokens in the content, or 0 on error
    """
    token_threshold: int = 2000
    try:
        # Convert relative paths to absolute paths
        absolute_filepath = resolve_relative_path(filepath)
        parsed = get_text_from_file(absolute_filepath)
        if not parsed or "content" not in parsed:
            error_msg = f"Warning: No content found in file: {filepath}"
            logger.warning(error_msg)
            return (error_msg, 0)

        content = parsed["content"]
        original_tokens = count_tokens(content)

        # Check if we need to summarize and have a summarization client
        summarization_client = get_summarization_client()

        if summarization_client and original_tokens > token_threshold:
            logger.info(
                "File '%s' has '%i' tokens > '%i'; summarising...",
                filepath,
                original_tokens,
                token_threshold,
            )

            # Use summarization client with caching support  
            content = summarization_client.summarize_text(content, source_file=absolute_filepath)
            token_count = count_tokens(content)
        else:
            logger.info(
                "File '%s' has '%i' tokens ≤ '%i'; summarization not required.",
                filepath,
                original_tokens,
                token_threshold,
            )
            token_count = original_tokens

        return (content, token_count)
    except Exception as e:
        error_msg = f"Error: Unable to read file {filepath}"
        logger.error(f"Failed to read file '{filepath}': {type(e).__name__}: {str(e)}")
        return (error_msg, 0)
