"""
Chat History Dialog Module

This module contains the ChatHistoryDialog class for displaying chat history
of selected leads in a well-formatted, readable view.
"""

import customtkinter as ctk
import json
from pathlib import Path
from ..styles import COLORS, FONTS


class ChatHistoryDialog(ctk.CTkToplevel):
    """Modal dialog for viewing chat history of a selected lead."""

    def __init__(self, parent, chat_log_filename: str):
        super().__init__(parent)

        self.chat_log_filename = chat_log_filename
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Load chat history
        self.load_chat_history()

    def setup_window(self):
        """Configure the dialog window."""
        self.title(f"💬 Chat History - {self.chat_log_filename}")
        self.geometry("1200x800")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color=COLORS["primary_black"])
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="💬 Chat History",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)

        # File info
        file_info = f"File: {self.chat_log_filename}"
        file_label = ctk.CTkLabel(
            title_frame,
            text=file_info,
            font=FONTS()["heading"],
            text_color=COLORS["text_gray"],
        )
        file_label.grid(row=1, column=0, pady=(0, 10))

        # Chat content frame
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # Chat text display with scrollbar
        self.chat_text = ctk.CTkTextbox(
            content_frame,
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            wrap="word",
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"],
        )
        self.chat_text.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        # Close button
        close_button = ctk.CTkButton(
            self,
            text="Close",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.on_close,
        )
        close_button.grid(row=2, column=0, pady=(0, 20))

    def load_chat_history(self):
        """Load and display the chat history from the JSON file."""
        try:
            # Get the chat logs directory path
            from ..scored_leads_loader import get_chat_logs_directory
            chat_logs_dir = get_chat_logs_directory()
            chat_log_path = chat_logs_dir / self.chat_log_filename

            if not chat_log_path.exists():
                self.chat_text.insert("1.0", f"❌ Chat log file not found: {self.chat_log_filename}")
                return

            # Load the JSON file
            with open(chat_log_path, "r", encoding="utf-8") as f:
                chat_data = json.load(f)

            # Parse and format messages
            self.format_chat_messages(chat_data)

        except Exception as e:
            self.chat_text.insert("1.0", f"❌ Error loading chat history: {str(e)}")

    def format_chat_messages(self, chat_data):
        """Format chat messages for display."""
        messages = chat_data.get("messages", [])
        meta = chat_data.get("meta", {})

        # Add header information
        self.chat_text.insert("end", "=" * 80 + "\n")
        self.chat_text.insert("end", f"CHAT HISTORY - {self.chat_log_filename}\n")
        self.chat_text.insert("end", "=" * 80 + "\n\n")

        # Add meta information if available
        if meta:
            self.chat_text.insert("end", "📊 SESSION INFO\n")
            self.chat_text.insert("end", "-" * 40 + "\n")
            total_messages = meta.get("total_messages", len(messages))
            self.chat_text.insert("end", f"Total Messages: {total_messages}\n")
            
            tools_used = meta.get("tools_used", [])
            if tools_used:
                self.chat_text.insert("end", f"Tools Used: {', '.join(tools_used)}\n")
            
            self.chat_text.insert("end", "\n")

        # Format each message
        for i, message in enumerate(messages):
            self.format_single_message(message, i + 1)

        # Scroll to top
        self.chat_text.see("1.0")

    def format_single_message(self, message, message_num):
        """Format a single chat message for display."""
        role = message.get("role", "unknown")
        content = message.get("content", "")
        msg_type = message.get("type", "")
        index = message.get("index", message_num - 1)

        # Message header
        self.chat_text.insert("end", f"Message #{message_num} (Index: {index})\n")
        self.chat_text.insert("end", "-" * 60 + "\n")

        # Role and type information
        role_display = role.upper()
        if msg_type:
            role_display += f" ({msg_type})"
        
        self.chat_text.insert("end", f"Role: {role_display}\n\n")

        # Content formatting based on role
        if role == "system":
            # System messages - format as instructions
            self.chat_text.insert("end", "🤖 SYSTEM INSTRUCTIONS:\n")
            self.chat_text.insert("end", "=" * 50 + "\n")
            self.chat_text.insert("end", content)
            self.chat_text.insert("end", "\n" + "=" * 50 + "\n\n")

        elif role == "user":
            # User messages - format as case description
            self.chat_text.insert("end", "👤 USER INPUT (Case Description):\n")
            self.chat_text.insert("end", "=" * 50 + "\n")
            self.chat_text.insert("end", content)
            self.chat_text.insert("end", "\n" + "=" * 50 + "\n\n")

        elif role == "assistant":
            # Assistant messages - format as AI response
            self.chat_text.insert("end", "🤖 AI RESPONSE:\n")
            self.chat_text.insert("end", "=" * 50 + "\n")
            
            # Check if there are tool calls
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                self.chat_text.insert("end", "🔧 TOOL CALLS:\n")
                for j, tool_call in enumerate(tool_calls):
                    tool_name = tool_call.get("tool", "unknown")
                    tool_id = tool_call.get("id", "unknown")
                    args = tool_call.get("args", {})
                    self.chat_text.insert("end", f"  {j+1}. {tool_name} (ID: {tool_id})\n")
                    if args:
                        # Show key arguments for context
                        for key, value in list(args.items())[:2]:  # Show first 2 args
                            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                            self.chat_text.insert("end", f"     {key}: {value_str}\n")
                self.chat_text.insert("end", "\n")
            
            # Main content
            if content.strip():
                # Truncate very long responses for readability
                if len(content) > 5000:
                    truncated_content = content[:5000] + "\n\n[Content truncated for readability - full content available in raw JSON file]"
                    self.chat_text.insert("end", truncated_content)
                else:
                    self.chat_text.insert("end", content)
            else:
                self.chat_text.insert("end", "[No text content - see tool calls above]")
            
            self.chat_text.insert("end", "\n" + "=" * 50 + "\n\n")

        else:
            # Other message types
            self.chat_text.insert("end", f"📝 {role_display} MESSAGE:\n")
            self.chat_text.insert("end", "=" * 50 + "\n")
            self.chat_text.insert("end", content)
            self.chat_text.insert("end", "\n" + "=" * 50 + "\n\n")

        # Add separator between messages
        self.chat_text.insert("end", "\n" + "🔹" * 40 + "\n\n")

    def on_close(self):
        """Handle window close event."""
        self.destroy()

    def center_window(self):
        """Center the dialog window on the parent."""
        self.update_idletasks()

        # Get parent window position and size
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Get dialog size
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")
