from typing import List, Any, Dict, Tuple, Optional
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add the project root to the path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
from utils import load_config


def _message_role(message: BaseMessage) -> str:
    """
    Map a LangChain message class to a simple chat role.

    Args:
        message (BaseMessage): LangChain message.

    Returns:
        str: One of 'system', 'user', 'assistant', or 'tool'.
    """
    if isinstance(message, SystemMessage):
        return "system"
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, ToolMessage):
        return "tool"
    return message.__class__.__name__.lower()


def _extract_tool_calls(message: AIMessage) -> List[Dict[str, Any]]:
    """
    Extract normalized tool call records from an AIMessage.

    Supports both message.tool_calls (preferred) and additional_kwargs["tool_calls"].

    Args:
        message (AIMessage): Assistant message that may contain tool calls.

    Returns:
        List[Dict[str, Any]]: List of {id, name, args} dicts.
    """
    tool_calls: List[Dict[str, Any]] = []

    # Preferred normalized attr present in many LangChain/OpenAI responses
    if hasattr(message, "tool_calls") and getattr(message, "tool_calls"):
        for tc in message.tool_calls:
            # Expected shape: {"id": str, "name": str, "args": dict}
            call_id = tc.get("id")
            name = tc.get("name")
            args = tc.get("args")
            # Some providers return args as a JSON string
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            tool_calls.append({"id": call_id, "name": name, "args": args})

    # Fallback to provider-specific structure under additional_kwargs
    elif isinstance(getattr(message, "additional_kwargs", None), dict):
        raw_calls = message.additional_kwargs.get("tool_calls") or []
        for raw in raw_calls:
            call_id = raw.get("id")
            fn = raw.get("function") or {}
            name = fn.get("name")
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            tool_calls.append({"id": call_id, "name": name, "args": args})

    return tool_calls


def _unique_log_filename(base_filename: Optional[str] = None) -> str:
    """
    Create a unique JSON filename using an optional base and a timestamp suffix.

    Args:
        base_filename (Optional[str]): Optional base filename (e.g., "chat_log.json").

    Returns:
        str: Filename with a timestamp suffix to ensure uniqueness.
    """
    default_base = "chat_log.json"
    raw = base_filename or default_base

    # Split stem and extension safely
    stem = Path(raw).stem or "chat_log"
    ext = Path(raw).suffix or ".json"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}{ext}"


def dump_chat_log(
    message_history: List[BaseMessage], filename: str = "chat_log.json"
) -> None:
    """
    Saves the complete message history as a human-readable JSON using the project's
    save_to_json utility. Includes full content for all messages without truncation.

    Args:
        message_history (List[BaseMessage]): List of messages to save.
        filename (str, optional): Output filename in the configured jsons dir.
            Defaults to "chat_log.json".

    File naming and location:
        - The output directory is resolved from config.yaml under `directories.chat_logs`.
          If not present, it defaults to `<directories.data>/chat_logs`.
        - A unique filename is generated for each run using a timestamp suffix.
    """
    # Pre-scan for tool call id -> name mapping to enrich ToolMessage entries
    tool_id_to_name: Dict[str, str] = {}
    for msg in message_history:
        if isinstance(msg, AIMessage):
            for tc in _extract_tool_calls(msg):
                if tc.get("id"):
                    tool_id_to_name[tc["id"]] = tc.get("name") or ""

    # Build structured entries with full content
    entries: List[Dict[str, Any]] = []
    tools_used: set[str] = set()

    for idx, message in enumerate(message_history):
        role = _message_role(message)
        entry: Dict[str, Any] = {
            "index": idx,
            "role": role,
            "type": message.__class__.__name__,
        }

        # Get full content for all message types
        content_text = getattr(message, "content", "") or ""
        entry["content"] = content_text

        # Assistant messages: include tool-call details if present
        if isinstance(message, AIMessage):
            tool_calls = _extract_tool_calls(message)
            if tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "tool": tc.get("name"),
                        "args": tc.get("args"),
                    }
                    for tc in tool_calls
                ]
                for tc in tool_calls:
                    if tc.get("name"):
                        tools_used.add(tc["name"])

        # Tool messages: show which tool-call they answer and tool name if known
        elif isinstance(message, ToolMessage):
            entry["tool_call_id"] = getattr(message, "tool_call_id", None)
            tool_name = tool_id_to_name.get(getattr(message, "tool_call_id", ""))
            if tool_name:
                entry["tool_name"] = tool_name
                tools_used.add(tool_name)

        entries.append(entry)

    # Compose top-level object with metadata
    output: Dict[str, Any] = {
        "meta": {
            "total_messages": len(message_history),
            "tools_used": sorted(tools_used),
        },
        "messages": entries,
    }

    # Determine destination directory from config directly
    config = load_config()
    directories_cfg: Dict[str, Any] = config.get("directories", {})
    chat_logs_path_str: str = directories_cfg.get(
        "chat_logs", str(Path("scripts") / "data" / "chat_logs")
    )

    project_root = Path(__file__).resolve().parents[3]
    destination_dir = project_root / Path(chat_logs_path_str)
    unique_name = _unique_log_filename(filename)
    destination_path = destination_dir / unique_name

    # Save JSON version
    try:
        with open(destination_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved chat log to {destination_path}")
    except (IOError, TypeError) as e:
        print(f"Error saving chat log: {e}")
        return None

    # Also save a human-readable text version
    text_path = destination_path.with_suffix(".txt")
    try:
        with open(text_path, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("CHAT LOG - LEAD SCORING SESSION\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Total Messages: {output['meta']['total_messages']}\n")
            f.write(
                f"Tools Used: {', '.join(output['meta']['tools_used']) if output['meta']['tools_used'] else 'None'}\n"
            )
            f.write("\n" + "=" * 80 + "\n\n")

            for msg in output["messages"]:
                # Header for each message
                f.write(f"[{msg['index']}] {msg['role'].upper()} ({msg['type']})\n")
                f.write("-" * 40 + "\n")

                # Content
                if msg["content"]:
                    f.write(msg["content"])
                    f.write("\n")

                # Tool call information for assistant messages
                if "tool_calls" in msg and msg["tool_calls"]:
                    f.write("\nTOOL CALLS:\n")
                    for tc in msg["tool_calls"]:
                        f.write(f"  • {tc['tool']} (ID: {tc['id']})\n")
                        if tc["args"]:
                            f.write(f"    Args: {tc['args']}\n")

                # Tool information for tool messages
                if "tool_name" in msg:
                    f.write(f"\nTOOL: {msg['tool_name']}\n")
                    f.write(f"RESPONDING TO: {msg['tool_call_id']}\n")

                f.write("\n" + "=" * 80 + "\n\n")

        print(f"Successfully saved readable chat log to {text_path}")
    except (IOError, TypeError) as e:
        print(f"Error saving readable chat log: {e}")

    # Return the filename (without path) for reference
    return unique_name
