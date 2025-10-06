"""
Discuss Lead Dialog Module

This module contains the DiscussLeadDialog class for discussing leads with an AI assistant
using the gpt-5-chat model with access to file and vector context tools.
"""

import customtkinter as ctk
import re
import tkinter as tk
from tkinter import messagebox, scrolledtext
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..styles import COLORS, FONTS
from scripts.clients.azure import AzureClient
from scripts.clients.tools import ToolManager, get_file_context, query_vector_context
from scripts.vectordb import QdrantManager
from scripts.clients.agents.utils.vector_registry import set_vector_clients


class DiscussLeadDialog(ctk.CTkToplevel):
    """Modal dialog for discussing leads with AI assistant."""
    
    # Class variables to track chat history per lead
    _last_lead_id = None
    _chat_histories = {}  # Dictionary to store chat histories per lead ID

    def __init__(self, parent, lead: dict):
        super().__init__(parent)

        self.lead = lead
        self.chat_client = None
        self.tool_manager = None
        self.current_lead_id = lead.get('id') or id(lead)  # Use lead ID or object ID as unique identifier
        
        self.setup_window()
        self.create_widgets()
        self.initialize_chat_client()
        self.load_initial_context()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()
        
        # Set up close handler
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_window(self):
        """Configure the dialog window."""
        self.title("💬 Discuss Lead - AI Assistant")
        self.geometry("1600x900")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)  # Sidebar column

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        self.create_header()
        self.create_chat_area()
        self.create_sidebar()
        self.create_input_area()

    def create_header(self):
        """Create the dialog header."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="💬 Discuss Lead with AI Assistant",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Lead info
        lead_info = f"Score: {self.lead.get('score', 'N/A')}/100"
        if 'analysis' in self.lead:
            from scripts.clients.agents.scoring import extract_jurisdiction_from_response
            jurisdiction = extract_jurisdiction_from_response(self.lead['analysis'])
            if jurisdiction:
                lead_info += f" | Jurisdiction: {jurisdiction}"
        
        info_label = ctk.CTkLabel(
            header_frame,
            text=lead_info,
            font=FONTS()["small"],
            text_color=COLORS["text_gray"]
        )
        info_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # Action buttons frame
        buttons_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=1, sticky="ne", pady=(0, 5))
        
        # View Lead Details button (shows both analysis and description)
        self.view_details_btn = ctk.CTkButton(
            buttons_frame,
            text="📋 View Lead Details",
            width=140,
            height=30,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=ctk.CTkFont(size=11),
            command=self.toggle_sidebar
        )
        self.view_details_btn.grid(row=0, column=0, sticky="e", padx=(0, 5))
        
        # Close button
        close_button = ctk.CTkButton(
            buttons_frame,
            text="✕",
            width=30,
            height=30,
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            font=ctk.CTkFont(size=14),
            command=self.on_close
        )
        close_button.grid(row=0, column=1, sticky="e")

    def create_chat_area(self):
        """Create the chat display area."""
        chat_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 10))
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)

        # Chat display using scrolledtext for better text handling
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg=COLORS["secondary_black"],
            fg=COLORS["text_white"],
            insertbackground=COLORS["text_white"],
            selectbackground=COLORS["accent_orange"],
            state=tk.DISABLED,
            padx=15,
            pady=15
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew")
        
        # Configure text tags for different message types
        self.chat_display.tag_configure("assistant", foreground=COLORS["accent_orange"], font=("Consolas", 11, "bold"))
        self.chat_display.tag_configure("assistant_text", foreground=COLORS["text_white"], font=("Consolas", 11))
        self.chat_display.tag_configure("assistant_highlight", foreground=COLORS["accent_orange"], font=("Consolas", 11, "bold"))
        self.chat_display.tag_configure("user", foreground=COLORS["accent_orange_light"], font=("Consolas", 11, "bold"))
        self.chat_display.tag_configure("user_text", foreground=COLORS["text_white"], font=("Consolas", 11))
        self.chat_display.tag_configure("system", foreground=COLORS["accent_orange_light"], font=("Consolas", 11, "bold"))
        self.chat_display.tag_configure("system_text", foreground=COLORS["text_gray"], font=("Consolas", 11))

    def create_sidebar(self):
        """Create the collapsible sidebar for analysis and description."""
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"], width=400)
        self.sidebar_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 20), pady=(0, 10))
        self.sidebar_frame.grid_rowconfigure(1, weight=1)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        
        # Initially hidden
        self.sidebar_visible = False
        self.sidebar_frame.grid_remove()
        
        # Sidebar header
        sidebar_header = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        sidebar_header.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        sidebar_header.grid_columnconfigure(0, weight=1)
        
        sidebar_title = ctk.CTkLabel(
            sidebar_header,
            text="Lead Information",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        sidebar_title.grid(row=0, column=0, sticky="w")
        
        # Analysis section
        self.analysis_section = ctk.CTkFrame(self.sidebar_frame, fg_color=COLORS["tertiary_black"])
        self.analysis_section.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.analysis_section.grid_rowconfigure(1, weight=1)
        self.analysis_section.grid_columnconfigure(0, weight=1)
        
        analysis_header = ctk.CTkLabel(
            self.analysis_section,
            text="📊 AI Analysis",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"]
        )
        analysis_header.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        
        self.analysis_text = scrolledtext.ScrolledText(
            self.analysis_section,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=COLORS["tertiary_black"],
            fg=COLORS["text_white"],
            insertbackground=COLORS["text_white"],
            selectbackground=COLORS["accent_orange"],
            state=tk.DISABLED,
            padx=15,
            pady=15
        )
        self.analysis_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        # Description section
        self.description_section = ctk.CTkFrame(self.sidebar_frame, fg_color=COLORS["tertiary_black"])
        self.description_section.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.description_section.grid_rowconfigure(1, weight=1)
        self.description_section.grid_columnconfigure(0, weight=1)
        
        description_header = ctk.CTkLabel(
            self.description_section,
            text="📋 Original Description",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"]
        )
        description_header.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        
        self.description_text = scrolledtext.ScrolledText(
            self.description_section,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=COLORS["tertiary_black"],
            fg=COLORS["text_white"],
            insertbackground=COLORS["text_white"],
            selectbackground=COLORS["accent_orange"],
            state=tk.DISABLED,
            padx=15,
            pady=15
        )
        self.description_text.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

    def create_input_area(self):
        """Create the input area for user messages."""
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=(20, 10), pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)

        # Input text box
        self.input_text = ctk.CTkTextbox(
            input_frame,
            height=100,
            font=FONTS()["body"],
            fg_color=COLORS["secondary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["border_gray"],
            border_width=1,
            wrap="word"
        )
        self.input_text.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        # Send button
        self.send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            width=80,
            height=100,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self.send_message
        )
        self.send_button.grid(row=0, column=1, sticky="ns")

        # Bind Enter key to send message
        self.input_text.bind("<Control-Return>", lambda e: self.send_message())

    def initialize_chat_client(self):
        """Initialize the Azure chat client with gpt-5-chat model and tools."""
        try:
            # Create Azure client with gpt-5-chat model
            self.chat_client = AzureClient("gpt-5-chat")
            
            # Initialize tool manager with the same tools as scoring agent
            # Set a very high tool call limit for unlimited tool usage in chat
            self.tool_manager = ToolManager(tools=[get_file_context, query_vector_context], tool_call_limit=999999)
            
            # Bind tools to the client
            self.chat_client.client = self.chat_client.client.bind_tools(self.tool_manager.tools)

            # Add chat client's telemetry to main window cost tracking list
            try:
                parent = getattr(self, 'master', None)
                handler = getattr(parent, 'event_handler', None) if parent else None
                business = getattr(handler, 'business_logic', None) if handler else None
                if business is not None and hasattr(self.chat_client, 'telemetry_manager'):
                    # Label override for model breakdown clarity
                    try:
                        base_name = self.chat_client.client_config.get("deployment_name", "unknown")
                        self.chat_client.telemetry_manager.label_override = f"(discussion) {base_name}"
                    except Exception:
                        pass
                    managers = getattr(business, 'current_lead_telemetry_managers', [])
                    if self.chat_client.telemetry_manager not in managers:
                        managers.append(self.chat_client.telemetry_manager)
                        business.current_lead_telemetry_managers = managers
            except Exception:
                pass

            # Register vector clients so query_vector_context works in dialog
            try:
                qdrant_manager = QdrantManager()
                embedding_client = AzureClient("text_embedding_3_large")
                set_vector_clients(qdrant_manager, embedding_client)
            except Exception as reg_err:
                # Non-fatal: chat can still work without vector search
                print(f"ERROR: Failed to register vector clients for dialog chat: {reg_err}")
            
            # Check if this is a new lead - if so, clear chat history
            if DiscussLeadDialog._last_lead_id != self.current_lead_id:
                # New lead - clear chat history
                self.chat_client.clear_history()
                DiscussLeadDialog._last_lead_id = self.current_lead_id
                print(f"DEBUG: New lead detected ({self.current_lead_id}), clearing chat history")
            else:
                # Same lead - restore previous chat history if available
                if self.current_lead_id in DiscussLeadDialog._chat_histories:
                    self.chat_client.message_history = DiscussLeadDialog._chat_histories[self.current_lead_id].copy()
                    print(f"DEBUG: Same lead ({self.current_lead_id}), restoring chat history")
                else:
                    print(f"DEBUG: Same lead ({self.current_lead_id}), but no previous history found")
            
            # Add system message using the lead_discussion prompt
            from utils import load_prompt
            lead_discussion_prompt = load_prompt("lead_discussion")
            system_message = SystemMessage(content=lead_discussion_prompt)
            self.chat_client.add_message(system_message)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize chat client: {str(e)}")
            self.destroy()

    def load_initial_context(self):
        """Load the AI analysis and original description into sidebar and chat history."""
        try:
            # Load analysis and description into sidebar
            # Check for edited analysis first, then fall back to regular analysis
            analysis_text = self.lead.get('_edited_analysis') or self.lead.get('analysis', 'No analysis available')
            description_text = self.lead.get('description', 'No description available')
            
            # Debug: Print lead keys to see what's available
            print(f"DEBUG: Lead keys: {list(self.lead.keys())}")
            print(f"DEBUG: Analysis text length: {len(analysis_text) if analysis_text else 0}")
            print(f"DEBUG: Description text length: {len(description_text) if description_text else 0}")
            print(f"DEBUG: Analysis text preview: {analysis_text[:200] if analysis_text else 'None'}...")
            
            # Populate sidebar text widgets
            self.analysis_text.configure(state=tk.NORMAL)
            self.analysis_text.delete("1.0", tk.END)
            self.analysis_text.insert("1.0", analysis_text)
            self.analysis_text.configure(state=tk.DISABLED)
            
            self.description_text.configure(state=tk.NORMAL)
            self.description_text.delete("1.0", tk.END)
            self.description_text.insert("1.0", description_text)
            self.description_text.configure(state=tk.DISABLED)
            
            # Only load initial context for new leads (not when restoring chat history)
            if DiscussLeadDialog._last_lead_id == self.current_lead_id and self.current_lead_id in DiscussLeadDialog._chat_histories:
                # Restoring chat history - don't add initial context
                print(f"DEBUG: Restoring chat history for lead {self.current_lead_id}, skipping initial context")
                # Display the restored chat history
                self._display_restored_chat_history()
            else:
                # New lead - add initial context
                print(f"DEBUG: New lead {self.current_lead_id}, loading initial context")
                
                # Add context to chat client (but don't display in chat)
                analysis_message = AIMessage(content=f"**AI Analysis:**\n{analysis_text}")
                description_message = HumanMessage(content=f"**Original Lead Description:**\n{description_text}")
                self.chat_client.add_message(analysis_message)
                self.chat_client.add_message(description_message)
                
                # Display only welcome message in chat
                self.add_message_to_display("AI Assistant", "Hello! I'm here to help you discuss this lead. You can ask me questions about the analysis, request additional information, or explore related files. Use the 'View Lead Details' button above to see the full analysis and description. How can I assist you?")
                
                # Add a helpful tip
                self.add_message_to_display("System", "💡 Tip: Click 'View Lead Details' to see the full analysis and description in the sidebar.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load initial context: {str(e)}")

    def _display_restored_chat_history(self):
        """Display the restored chat history in the chat display."""
        # Clear the chat display
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        
        # Display all messages from the restored history (skip system message)
        for message in self.chat_client.message_history:
            # Skip SystemMessage and ToolMessage for display
            if isinstance(message, SystemMessage) or getattr(message, '__class__', None).__name__ == 'ToolMessage':
                continue
            # Skip initial context messages shown only as hidden context
            content = getattr(message, 'content', '') or ''
            if isinstance(content, str) and (
                content.startswith("**AI Analysis:**") or
                content.startswith("**Original Lead Description:**")
            ):
                continue
            if isinstance(message, AIMessage):
                self.add_message_to_display("AI Assistant", content)
            elif isinstance(message, HumanMessage):
                self.add_message_to_display("User", content)

    def send_message(self):
        """Send user message and get AI response."""
        user_input = self.input_text.get("1.0", tk.END).strip()
        if not user_input:
            return

        # Clear input
        self.input_text.delete("1.0", tk.END)

        # Add user message to display
        self.add_message_to_display("User", user_input)

        # Add user message to chat client
        user_message = HumanMessage(content=user_input)
        self.chat_client.add_message(user_message)

        try:
            # Get AI response
            self.send_button.configure(text="Thinking...", state="disabled")
            self.update()
            
            response = self.chat_client.invoke()
            
            # Handle tool calls if present
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Process tool calls
                tool_responses = self.tool_manager.batch_tool_call(response.tool_calls)
                self.chat_client.add_message(tool_responses)
                
                # Get final response after tool calls
                final_response = self.chat_client.invoke()
                self.add_message_to_display("AI Assistant", final_response.content)
            else:
                # Regular response without tool calls
                self.add_message_to_display("AI Assistant", response.content)
            
            # Save chat history for this lead
            self._save_chat_history()
            
        except Exception as e:
            error_msg = f"Error getting AI response: {str(e)}"
            self.add_message_to_display("System", error_msg)
            # Don't show error dialog for tool failures, just log them
            print(f"Chat error: {error_msg}")
        finally:
            self.send_button.configure(text="Send", state="normal")

        # Update cost tracking on the main window after each turn
        try:
            parent = getattr(self, 'master', None)
            handler = getattr(parent, 'event_handler', None) if parent else None
            business = getattr(handler, 'business_logic', None) if handler else None
            if business is not None and hasattr(parent, 'cost_tracking_widget'):
                current_cost = business.get_current_lead_cost()
                parent.cost_tracking_widget.update_current_lead_cost(current_cost)
                model_costs = business.get_current_lead_cost_by_model()
                parent.cost_tracking_widget.set_model_costs(model_costs)
        except Exception:
            pass

    def add_message_to_display(self, sender: str, message: str):
        """Add a message to the chat display."""
        self.chat_display.configure(state=tk.NORMAL)
        
        # Add sender and message
        if sender == "AI Assistant":
            self.chat_display.insert(tk.END, f"🤖 {sender}:\n", "assistant")
            # Render message with **highlighted** segments
            parts = re.split(r"(\*\*[^*]+\*\*)", message)
            for part in parts:
                if part.startswith("**") and part.endswith("**") and len(part) >= 4:
                    self.chat_display.insert(tk.END, part[2:-2], "assistant_highlight")
                else:
                    self.chat_display.insert(tk.END, part, "assistant_text")
            self.chat_display.insert(tk.END, "\n\n", "assistant_text")
        elif sender == "User":
            self.chat_display.insert(tk.END, f"👤 {sender}:\n", "user")
            self.chat_display.insert(tk.END, f"{message}\n\n", "user_text")
        else:
            self.chat_display.insert(tk.END, f"⚠️ {sender}:\n", "system")
            self.chat_display.insert(tk.END, f"{message}\n\n", "system_text")
        
        # Scroll to bottom
        self.chat_display.see(tk.END)
        self.chat_display.configure(state=tk.DISABLED)

    def center_window(self):
        """Center the dialog window on the parent."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def toggle_sidebar(self):
        """Toggle the sidebar visibility."""
        if self.sidebar_visible:
            self.sidebar_frame.grid_remove()
            self.sidebar_visible = False
            self.view_details_btn.configure(text="📋 View Lead Details")
        else:
            self.sidebar_frame.grid()
            self.sidebar_visible = True
            self.view_details_btn.configure(text="📋 Hide Lead Details")

    def _save_chat_history(self):
        """Save the current chat history for this lead."""
        try:
            # Save a copy of the current message history
            DiscussLeadDialog._chat_histories[self.current_lead_id] = self.chat_client.message_history.copy()
            print(f"DEBUG: Saved chat history for lead {self.current_lead_id}")
        except Exception as e:
            print(f"DEBUG: Failed to save chat history: {e}")

    def on_close(self):
        """Handle window close event."""
        # Save chat history before closing
        self._save_chat_history()
        self.destroy()
