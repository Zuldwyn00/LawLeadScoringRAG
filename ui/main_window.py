"""
Main Application Window

This module contains the main application window class that coordinates all UI components
and handles the overall application flow.
"""

import customtkinter as ctk
import re
import tkinter as tk
from tkinter import messagebox

from .styles import (
    setup_theme,
    COLORS,
    FONTS,
    get_primary_button_style,
    get_secondary_button_style,
    get_textbox_style,
    get_frame_style,
)
from .widgets import (
    ProgressWidget,
    LeadItem,
    StatsWidget,
    GuidelinesWidget,
    FeedbackGuidelinesWidget,
    CostTrackingWidget,
    RetrievedChunksDisplayFrame,
)
from .handlers import UIEventHandler
from .dialogs import LogViewerDialog, ModelSelectionDialog
from .feedback_manager import FeedbackManager
from .widgets.model_selector import ModelSelectorWidget
from .widgets import LeadItem


# ─── MAIN APPLICATION CLASS ─────────────────────────────────────────────────────
class MainWindow(ctk.CTk):
    """Main application window for the Lead Scoring System."""

    def __init__(self):
        super().__init__()

        # Set up theme first
        setup_theme()
        self.setup_window()

        # Initialize data
        self.scored_leads = []
        self.current_session_start_time = None
        self._temporarily_stored_leads = []  # For tutorial functionality

        # Initialize event handler
        self.event_handler = UIEventHandler(self)

        # Initialize feedback manager for program close handling
        self.feedback_manager = FeedbackManager()

        # Initialize model selector
        self.model_selector = ModelSelectorWidget(self)
        
        # Initialize with example lead
        self.scored_leads = self.event_handler.get_initial_leads()

        # Create UI components
        self.create_widgets()

        # Set up window close event handler
        self.setup_close_handler()

        # Refresh initial display
        self.refresh_results()
        self.stats_widget.update(self.scored_leads)

        # Simple approach - no complex sizing needed!

    def setup_window(self):
        """Configure the main application window."""
        self.title("⚖️ Lead Scoring System")
        self.geometry("1500x1000")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights for responsive design
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Set minimum size
        self.minsize(1200, 800)

    def create_widgets(self):
        """Create and arrange all UI widgets."""
        self.create_title_section()
        self.create_main_content()

    def create_title_section(self):
        """Create the title section at the top of the window."""
        title_frame = ctk.CTkFrame(self, **get_frame_style("primary"))
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        title_frame.grid_columnconfigure(0, weight=1)
        title_frame.grid_columnconfigure(1, weight=0)
        title_frame.grid_columnconfigure(2, weight=0)

        title_label = ctk.CTkLabel(
            title_frame,
            text="⚖️ Lead Scoring System",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)

        subtitle_label = ctk.CTkLabel(
            title_frame,
            text="Enter a lead description to score its potential for success.",
            font=FONTS()["subtitle"],
            text_color=COLORS["text_gray"],
        )
        subtitle_label.grid(row=1, column=0, pady=(0, 10))

        # Top-right actions: Help and Start Tutorial
        # Make both buttons larger for visibility
        title_frame.grid_columnconfigure(2, weight=0)

        self.guidelines_button = ctk.CTkButton(
            title_frame,
            text="📖 HELP",
            command=self._open_guidelines_popup,
            **get_secondary_button_style(),
        )
        try:
            self.guidelines_button.configure(font=FONTS()["subtitle"], height=40, width=150)
        except Exception:
            pass
        self.guidelines_button.grid(row=0, column=1, rowspan=2, padx=(10, 10), pady=10, sticky="e")

        self.start_tutorial_button = ctk.CTkButton(
            title_frame,
            text="▶ START TUTORIAL",
            command=self._start_example_tutorial,
            **get_secondary_button_style(),
        )
        try:
            self.start_tutorial_button.configure(font=FONTS()["subtitle"], height=40, width=180)
        except Exception:
            pass
        self.start_tutorial_button.grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=10, sticky="e")

    def _start_example_tutorial(self):
        """Scroll to the bottom of scored leads and start the example lead tutorial."""
        # Temporarily clear non-example leads for tutorial
        self._temporarily_clear_leads_for_tutorial()
        
        # Wait for UI to be properly updated before starting tutorial
        def _launch_tutorial():
            # Ensure results are rendered
            try:
                self.update_idletasks()
            except Exception:
                pass

            # Find the example lead widget and trigger its tutorial
            example_widget = None
            for child in self.results_frame.winfo_children():
                try:
                    is_example = bool(getattr(child, "lead", {}).get("is_example", False))
                except Exception:
                    is_example = False
                if is_example:
                    example_widget = child
                    break

            if example_widget and hasattr(example_widget, "_start_feedback_tutorial"):
                try:
                    # Pass the restore callback to the tutorial
                    example_widget._start_feedback_tutorial(self._restore_leads_after_tutorial)
                except Exception:
                    try:
                        self.after(160, lambda: getattr(example_widget, "_start_feedback_tutorial", lambda: None)(self._restore_leads_after_tutorial))
                    except Exception:
                        pass
            else:
                try:
                    messagebox.showinfo("Tutorial", "Example lead not found. Add or load the example lead to start the tutorial.")
                    # Restore leads if tutorial can't start
                    self._restore_leads_after_tutorial()
                except Exception:
                    pass

        # Launch after a short delay to ensure UI is updated
        self.after(100, _launch_tutorial)

    def _temporarily_clear_leads_for_tutorial(self):
        """Temporarily store non-example leads and clear them from UI for tutorial."""
        # Store current leads (excluding example leads) for later restoration
        self._temporarily_stored_leads = [
            lead for lead in self.scored_leads 
            if not lead.get("is_example", False)
        ]
        
        # Keep only example leads in the UI (is_example == True)
        self.scored_leads = [
            lead for lead in self.scored_leads 
            if lead.get("is_example", False) == True
        ]
        
        # Refresh the UI to show only example leads
        self.refresh_results()
        self.stats_widget.update(self.scored_leads)

    def _restore_leads_after_tutorial(self):
        """Restore previously stored leads after tutorial completion."""
        # Restore the temporarily stored leads
        if self._temporarily_stored_leads:
            # Get the example lead (should be the only one currently in scored_leads)
            example_leads = [
                lead for lead in self.scored_leads 
                if lead.get("is_example", False)
            ]
            
            # Reconstruct the list: stored leads first, then example leads at bottom
            self.scored_leads = self._temporarily_stored_leads + example_leads
            
            # Clear the temporary storage
            self._temporarily_stored_leads = []
            
            # Refresh the UI to show all leads
            self.refresh_results()
            self.stats_widget.update(self.scored_leads)

    # Removed previous auto-scroll helpers per request

    def create_main_content(self):
        """Create the main content area with dynamic panel layout."""
        main_frame = ctk.CTkFrame(self, **get_frame_style("primary"))
        main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Store reference to main frame for dynamic layout changes
        self.main_frame = main_frame
        
        # Initially configure for 2 panels (left and middle only)
        self._configure_panel_layout(show_right_panel=False)

        # Create the three panels
        self.create_left_panel_simple(main_frame)
        self.create_middle_panel_simple(main_frame)
        self.create_right_panel_simple(main_frame)
        
        # Initially hide the right panel
        self.right_panel.grid_remove()
        
        # Show button for when right panel is hidden (initially hidden)
        self.right_panel_show_btn = ctk.CTkButton(
            self,
            text="▶",
            width=30,
            height=60,
            fg_color="#FFD700",  # Gold yellow
            hover_color="#FFA500",  # Orange hover (darker)
            font=ctk.CTkFont(size=14),
            command=self._show_right_panel,
            corner_radius=0
        )
        # Position the show button on the very right edge like a door handle
        self.right_panel_show_btn.place(relx=1.0, rely=0.5, anchor="e")  # Right edge of window
        # Initially visible since right panel is hidden by default

    def create_left_panel_simple(self, parent):
        """Create the left panel with input and controls."""
        left_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        left_frame.grid_rowconfigure(5, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Disable grid propagation to prevent content from affecting size
        left_frame.grid_propagate(False)

        # Input section
        self.create_input_section(left_frame)
        # Button section
        self.create_button_section(left_frame)
        # Progress section
        self.create_progress_section(left_frame)
        # Guidelines section
        self.create_left_guidelines_section(left_frame)

    def create_middle_panel_simple(self, parent):
        """Create the middle panel with scored leads results."""
        middle_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        middle_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=0)
        middle_frame.grid_rowconfigure(1, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)
        
        # Disable grid propagation to prevent content from affecting size
        middle_frame.grid_propagate(False)

        # Results section title
        results_label = ctk.CTkLabel(
            middle_frame,
            text="Scored Leads",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"],
        )
        results_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Scrollable frame for results
        self.results_frame = ctk.CTkScrollableFrame(
            middle_frame,
            **get_frame_style("secondary"),
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"],
        )
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.results_frame.grid_columnconfigure(0, weight=1)

    def create_right_panel_simple(self, parent):
        """Create the right panel with retrieved chunks display and chat."""
        right_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=0)
        right_frame.grid_rowconfigure(1, weight=1)  # Content area gets the weight
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Disable grid propagation to prevent content from affecting size
        right_frame.grid_propagate(False)
        
        # Store reference to right panel for dynamic layout changes
        self.right_panel = right_frame
        
        # Right panel header with buttons
        self.right_panel_header = ctk.CTkFrame(right_frame, **get_frame_style("transparent"))
        self.right_panel_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.right_panel_header.grid_columnconfigure(2, weight=1)
        
        # Hide button for right panel
        self.right_panel_hide_btn = ctk.CTkButton(
            self.right_panel_header,
            text="✕",
            width=30,
            height=30,
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            font=ctk.CTkFont(size=14),
            command=self._hide_right_panel
        )
        self.right_panel_hide_btn.grid(row=0, column=0, sticky="w")
        
        # Swap button for switching between chunks and chat
        self.right_panel_swap_btn = ctk.CTkButton(
            self.right_panel_header,
            text="🔄",
            width=30,
            height=30,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=ctk.CTkFont(size=14),
            command=self._swap_right_panel_view
        )
        self.right_panel_swap_btn.grid(row=0, column=1, sticky="w", padx=(5, 0))
        
        # Right panel title
        self.right_panel_title = ctk.CTkLabel(
            self.right_panel_header,
            text="Right Panel",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        self.right_panel_title.grid(row=0, column=2, sticky="w", padx=(10, 0))
        
        # Retrieved chunks display
        self.retrieved_chunks_frame = RetrievedChunksDisplayFrame(right_frame)
        self.retrieved_chunks_frame.grid(row=1, column=0, sticky="nsew")
        
        # Chat panel (initially hidden)
        self.chat_panel = ctk.CTkFrame(right_frame, **get_frame_style("secondary"))
        self.chat_panel.grid(row=1, column=0, sticky="nsew")
        self.chat_panel.grid_remove()  # Initially hidden
        
        # Configure chat panel grid
        self.chat_panel.grid_columnconfigure(0, weight=1)
        self.chat_panel.grid_rowconfigure(1, weight=1)
        
        # Chat header
        self.chat_header = ctk.CTkFrame(self.chat_panel, **get_frame_style("transparent"))
        self.chat_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.chat_header.grid_columnconfigure(1, weight=1)
        
        # Chat title
        self.chat_title = ctk.CTkLabel(
            self.chat_header,
            text="💬(WIP) Discuss Lead",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        self.chat_title.grid(row=0, column=0, sticky="w")
        
        # Close chat button
        self.close_chat_btn = ctk.CTkButton(
            self.chat_header,
            text="✕",
            width=30,
            height=30,
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            font=ctk.CTkFont(size=14),
            command=self.close_chat
        )
        self.close_chat_btn.grid(row=0, column=1, sticky="e")
        
        # Chat display area
        self.chat_display_frame = ctk.CTkFrame(self.chat_panel, fg_color=COLORS["secondary_black"])
        self.chat_display_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.chat_display_frame.grid_rowconfigure(0, weight=1)
        self.chat_display_frame.grid_columnconfigure(0, weight=1)
        
        # Chat input area
        self.chat_input_frame = ctk.CTkFrame(self.chat_panel, **get_frame_style("transparent"))
        self.chat_input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.chat_input_frame.grid_columnconfigure(0, weight=1)
        
        # Initialize chat components
        self.chat_client = None
        self.tool_manager = None
        self.current_lead = None
        self.current_lead_id = None
        self._last_lead_id = None
        self._chat_histories = {}
        
        # Create chat display and input components
        self._create_chat_components()

    def _configure_panel_layout(self, show_right_panel=True):
        """Configure the main frame layout for 2 or 3 panels."""
        if show_right_panel:
            # 3 panels: left, middle, right (each 1/3)
            self.main_frame.grid_columnconfigure(0, weight=1)  # Left panel (1/3)
            self.main_frame.grid_columnconfigure(1, weight=1)  # Middle panel (1/3)
            self.main_frame.grid_columnconfigure(2, weight=1)  # Right panel (1/3)
        else:
            # 2 panels: left, middle (each 1/2)
            self.main_frame.grid_columnconfigure(0, weight=1)  # Left panel (1/2)
            self.main_frame.grid_columnconfigure(1, weight=1)  # Middle panel (1/2)
            self.main_frame.grid_columnconfigure(2, weight=0)  # Right panel (hidden)

    def _hide_right_panel(self):
        """Hide the right panel and show the show button."""
        self._configure_panel_layout(show_right_panel=False)
        self.right_panel.grid_remove()
        self.right_panel_title.configure(text="Right Panel")
        # Show the show button
        self.right_panel_show_btn.place(relx=1.0, rely=0.5, anchor="e")

    def _show_right_panel(self):
        """Show the right panel with chunks view and hide the show button."""
        self._configure_panel_layout(show_right_panel=True)
        self.right_panel.grid()
        self.retrieved_chunks_frame.grid()
        self.chat_panel.grid_remove()
        self.right_panel_title.configure(text="Retrieved Chunks")
        # Hide the show button
        self.right_panel_show_btn.place_forget()

    def _swap_right_panel_view(self):
        """Swap between chunks and chat views in the right panel."""
        if not self.right_panel.winfo_viewable():
            # If panel is hidden, show chunks view
            self._configure_panel_layout(show_right_panel=True)
            self.right_panel.grid()
            self.retrieved_chunks_frame.grid()
            self.chat_panel.grid_remove()
            self.right_panel_title.configure(text="Retrieved Chunks")
        elif self.retrieved_chunks_frame.winfo_viewable():
            # Switch from chunks to chat
            self.retrieved_chunks_frame.grid_remove()
            self.chat_panel.grid()
            self.right_panel_title.configure(text="Chat Discussion")
        else:
            # Switch from chat to chunks
            self.chat_panel.grid_remove()
            self.retrieved_chunks_frame.grid()
            self.right_panel_title.configure(text="Retrieved Chunks")

    def _set_discuss_buttons_state(self, state):
        """Enable or disable all 'Discuss Lead' buttons."""
        try:
            # Find all lead items in the results frame
            for widget in self.results_frame.winfo_children():
                if hasattr(widget, 'discuss_lead_btn'):
                    widget.discuss_lead_btn.configure(state=state)
        except Exception as e:
            print(f"DEBUG: Error setting discuss buttons state: {e}")

    def create_left_panel_new(self):
        """Create the left panel with input and controls."""
        self.left_panel = ctk.CTkFrame(self.panels_frame, **get_frame_style("secondary"))
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        self.left_panel.grid_rowconfigure(5, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)
        
        # Input section
        self.create_input_section(self.left_panel)
        # Button section
        self.create_button_section(self.left_panel)
        # Progress section
        self.create_progress_section(self.left_panel)
        # Guidelines section
        self.create_left_guidelines_section(self.left_panel)

    def create_middle_panel_new(self):
        """Create the middle panel with scored leads results."""
        self.middle_panel = ctk.CTkFrame(self.panels_frame, **get_frame_style("secondary"))
        self.middle_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=0)
        self.middle_panel.grid_rowconfigure(1, weight=1)
        self.middle_panel.grid_columnconfigure(0, weight=1)
        
        # Results section title
        results_label = ctk.CTkLabel(
            self.middle_panel,
            text="Scored Leads",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"],
        )
        results_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Scrollable frame for results
        self.results_frame = ctk.CTkScrollableFrame(
            self.middle_panel,
            **get_frame_style("secondary"),
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"],
        )
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.results_frame.grid_columnconfigure(0, weight=1)

    def create_right_panel_new(self):
        """Create the right panel with retrieved chunks display and chat."""
        self.right_panel = ctk.CTkFrame(self.panels_frame, **get_frame_style("secondary"))
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=0)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)
        
        # Retrieved chunks display
        self.retrieved_chunks_frame = RetrievedChunksDisplayFrame(self.right_panel)
        self.retrieved_chunks_frame.grid(row=0, column=0, sticky="nsew")
        
        # Set up width change handler
        self.retrieved_chunks_frame.set_width_change_handler(self._handle_chunks_sidebar_width_change)
        
        # Chat panel (initially hidden)
        self.chat_panel = ctk.CTkFrame(self.right_panel, **get_frame_style("secondary"))
        self.chat_panel.grid(row=0, column=0, sticky="nsew")
        self.chat_panel.grid_remove()  # Initially hidden
        
        # Configure chat panel grid
        self.chat_panel.grid_columnconfigure(0, weight=1)
        self.chat_panel.grid_rowconfigure(1, weight=1)
        
        # Chat header
        self.chat_header = ctk.CTkFrame(self.chat_panel, **get_frame_style("transparent"))
        self.chat_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.chat_header.grid_columnconfigure(1, weight=1)
        
        # Chat title
        self.chat_title = ctk.CTkLabel(
            self.chat_header,
            text="💬 Discuss Lead",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        self.chat_title.grid(row=0, column=0, sticky="w")
        
        # Close chat button
        self.close_chat_btn = ctk.CTkButton(
            self.chat_header,
            text="✕",
            width=30,
            height=30,
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            font=ctk.CTkFont(size=14),
            command=self.close_chat
        )
        self.close_chat_btn.grid(row=0, column=1, sticky="e")
        
        # Chat display area
        self.chat_display_frame = ctk.CTkFrame(self.chat_panel, fg_color=COLORS["secondary_black"])
        self.chat_display_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.chat_display_frame.grid_rowconfigure(0, weight=1)
        self.chat_display_frame.grid_columnconfigure(0, weight=1)
        
        # Chat input area
        self.chat_input_frame = ctk.CTkFrame(self.chat_panel, **get_frame_style("transparent"))
        self.chat_input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.chat_input_frame.grid_columnconfigure(0, weight=1)
        
        # Initialize chat components
        self.chat_client = None
        self.tool_manager = None
        self.current_lead = None
        self.current_lead_id = None
        self._last_lead_id = None
        self._chat_histories = {}
        
        # Create chat display and input components
        self._create_chat_components()

    def _on_window_resize(self, event):
        """Handle window resize to maintain equal panel sizing."""
        # Only handle main window resize, not child widget resizes
        if event.widget == self:
            # Use after_idle to ensure the resize is complete before adjusting panels
            self.after_idle(self._update_panel_sizes)

    def _update_panel_sizes(self):
        """Update panel sizes to maintain equal width."""
        try:
            if hasattr(self, 'panels_frame'):
                # Get the available width for the main container first
                main_width = self.main_container.winfo_width()
                print(f"DEBUG: Main container width: {main_width}")
                
                if main_width > 100:  # Only adjust if we have a reasonable width
                    # Account for padding (20px on each side)
                    available_width = main_width - 40
                    print(f"DEBUG: Available width after padding: {available_width}")
                    
                    # Check if retrieved chunks is expanded or collapsed
                    is_expanded = getattr(self.retrieved_chunks_frame, 'is_expanded', True)
                    
                    if is_expanded:
                        # All panels get equal width
                        panel_width = available_width // 3
                        print(f"DEBUG: Setting equal panel widths: {panel_width}")
                        
                        # Set explicit widths for all panels
                        self.left_panel.configure(width=panel_width)
                        self.middle_panel.configure(width=panel_width)
                        self.right_panel.configure(width=panel_width)
                        
                        # Set grid column weights to 0 to prevent grid from overriding
                        self.panels_frame.grid_columnconfigure(0, weight=0)
                        self.panels_frame.grid_columnconfigure(1, weight=0)
                        self.panels_frame.grid_columnconfigure(2, weight=0)
                        
                    else:
                        # Right panel is collapsed, give more space to others
                        right_width = 200  # Fixed collapsed width
                        remaining_width = available_width - right_width
                        left_width = remaining_width // 2
                        middle_width = remaining_width - left_width
                        
                        print(f"DEBUG: Setting panel widths - left={left_width}, middle={middle_width}, right={right_width}")
                        
                        # Set explicit widths
                        self.left_panel.configure(width=left_width)
                        self.middle_panel.configure(width=middle_width)
                        self.right_panel.configure(width=right_width)
                        
                        # Set grid column weights
                        self.panels_frame.grid_columnconfigure(0, weight=0)
                        self.panels_frame.grid_columnconfigure(1, weight=0)
                        self.panels_frame.grid_columnconfigure(2, weight=0)
                    
                    # Force layout update
                    self.panels_frame.update_idletasks()
                    
                    # Log final panel sizes
                    print(f"DEBUG: Final panel widths - left={self.left_panel.winfo_width()}, middle={self.middle_panel.winfo_width()}, right={self.right_panel.winfo_width()}")
                    
        except Exception as e:
            print(f"DEBUG: Error updating panel sizes: {e}")

    def create_left_panel(self, parent):
        """Create the left panel with input and controls."""
        left_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        left_frame.grid_rowconfigure(5, weight=1)  # Give weight to progress section to fill space
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Panel will use grid weights for responsive sizing
        print(f"DEBUG: Left panel created, will use grid weights for sizing")

        # Input section
        self.create_input_section(left_frame)

        # Button section
        self.create_button_section(left_frame)

        # Progress section
        self.create_progress_section(left_frame)
        
        # Guidelines section (moved from right panel to left)
        self.create_left_guidelines_section(left_frame)

    def create_input_section(self, parent):
        """Create the lead description input section."""
        input_label = ctk.CTkLabel(
            parent,
            text="New Lead Description",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"],
        )
        input_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        self.lead_text = ctk.CTkTextbox(parent, height=120, **get_textbox_style())
        self.lead_text.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.lead_text.insert(
            "1.0", "Enter the detailed description of the potential case..."
        )

        # Clear placeholder text when clicked
        self.lead_text.bind("<Button-1>", self._clear_placeholder)

        # Model settings button
        self.create_model_settings_button(parent)

        # Vector search settings section
        self.create_vector_search_settings(parent)

    def create_model_settings_button(self, parent):
        """Create the model settings button."""
        # Model settings frame
        settings_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        settings_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 0))
        # Prevent entry column from expanding and pushing following controls
        settings_frame.grid_columnconfigure(1, weight=0)
        # Add a right-side spacer column to absorb extra width
        settings_frame.grid_columnconfigure(6, weight=1)
        
        # Model settings button
        self.model_settings_button = ctk.CTkButton(
            settings_frame,
            text="⚙️ AI Model Configuration",
            command=self._open_model_settings,
            **get_secondary_button_style(),
        )
        self.model_settings_button.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        
        
        # Status label showing current models
        self.model_status_label = ctk.CTkLabel(
            settings_frame,
            text="Models: Default Configuration",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
        )
        self.model_status_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))

    def create_vector_search_settings(self, parent):
        """Create the vector search settings section."""
        # Load default chunk limit from config
        from utils import load_config
        config = load_config()
        default_limit = config.get("aiconfig", {}).get("vector_search", {}).get("default_chunk_limit", 10)
        default_tool_limit = config.get("aiconfig", {}).get("tool_call_limit", 5)
        
        # Settings frame
        settings_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        settings_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(10, 0))
        # Configure grid to prevent expansion of entry columns
        settings_frame.grid_columnconfigure(0, weight=0)  # Labels
        settings_frame.grid_columnconfigure(1, weight=0)  # Entries
        settings_frame.grid_columnconfigure(2, weight=1)  # Spacer to absorb extra width
        
        # First row: Chunk limit controls
        chunk_limit_label = ctk.CTkLabel(
            settings_frame,
            text="Vector Search Chunks:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
        )
        chunk_limit_label.grid(row=0, column=0, sticky="w", padx=(15, 10), pady=10)
        
        self.chunk_limit_var = ctk.StringVar(value=str(default_limit))
        self.chunk_limit_entry = ctk.CTkEntry(
            settings_frame,
            textvariable=self.chunk_limit_var,
            width=80,
            font=FONTS()["body"],
            placeholder_text="10",
        )
        self.chunk_limit_entry.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=10)
        
        # Help text for chunks
        help_label = ctk.CTkLabel(
            settings_frame,
            text="Number of similar cases to retrieve (1-50)",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
        )
        help_label.grid(row=0, column=2, sticky="w", padx=(10, 15), pady=10)

        # Second row: Tool call limit controls  
        tool_limit_label = ctk.CTkLabel(
            settings_frame,
            text="Tool Call Limit:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
        )
        tool_limit_label.grid(row=1, column=0, sticky="w", padx=(15, 10), pady=(0, 10))

        self.tool_call_limit_var = ctk.StringVar(value=str(default_tool_limit))
        self.tool_call_limit_entry = ctk.CTkEntry(
            settings_frame,
            textvariable=self.tool_call_limit_var,
            width=80,
            font=FONTS()["body"],
            placeholder_text="6",
        )
        self.tool_call_limit_entry.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 10))

        # Help text for tool limit
        tool_help_label = ctk.CTkLabel(
            settings_frame,
            text="Max tool uses during scoring (1-20)",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
        )
        tool_help_label.grid(row=1, column=2, sticky="w", padx=(10, 15), pady=(0, 10))

    def create_middle_panel(self, parent):
        """Create the middle panel with scored leads results."""
        middle_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        middle_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=0)
        middle_frame.grid_rowconfigure(1, weight=1)  # Give weight to the results frame row
        middle_frame.grid_columnconfigure(0, weight=1)
        
        # Panel will use grid weights for responsive sizing
        print(f"DEBUG: Middle panel created, will use grid weights for sizing")

        # Results section title
        results_label = ctk.CTkLabel(
            middle_frame,
            text="Scored Leads",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"],
        )
        results_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Scrollable frame for results
        self.results_frame = ctk.CTkScrollableFrame(
            middle_frame,
            **get_frame_style("secondary"),
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"],
        )
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.results_frame.grid_columnconfigure(0, weight=1)

    def create_retrieved_chunks_panel(self, parent):
        """Create the right panel with retrieved chunks display and stats."""
        # Retrieved chunks display
        self.retrieved_chunks_frame = RetrievedChunksDisplayFrame(parent)
        self.retrieved_chunks_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=0)
        
        # Set up width change handler
        self.retrieved_chunks_frame.set_width_change_handler(self._handle_chunks_sidebar_width_change)

    def create_chat_panel(self, parent):
        """Create the chat panel for discussing leads."""
        # Chat panel (initially hidden)
        self.chat_panel = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        self.chat_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0), pady=0)
        self.chat_panel.grid_remove()  # Initially hidden
        
        # Panel will use grid weights for responsive sizing
        print(f"DEBUG: Chat panel created, will use grid weights for sizing")
        
        # Configure grid
        self.chat_panel.grid_columnconfigure(0, weight=1)
        self.chat_panel.grid_rowconfigure(1, weight=1)
        
        # Chat header
        self.chat_header = ctk.CTkFrame(self.chat_panel, **get_frame_style("transparent"))
        self.chat_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.chat_header.grid_columnconfigure(1, weight=1)
        
        # Chat title
        self.chat_title = ctk.CTkLabel(
            self.chat_header,
            text="💬 Discuss Lead",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        self.chat_title.grid(row=0, column=0, sticky="w")
        
        # Close chat button
        self.close_chat_btn = ctk.CTkButton(
            self.chat_header,
            text="✕",
            width=30,
            height=30,
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            font=ctk.CTkFont(size=14),
            command=self.close_chat
        )
        self.close_chat_btn.grid(row=0, column=1, sticky="e")
        
        # Chat display area
        self.chat_display_frame = ctk.CTkFrame(self.chat_panel, fg_color=COLORS["secondary_black"])
        self.chat_display_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.chat_display_frame.grid_rowconfigure(0, weight=1)
        self.chat_display_frame.grid_columnconfigure(0, weight=1)
        
        # Chat input area
        self.chat_input_frame = ctk.CTkFrame(self.chat_panel, **get_frame_style("transparent"))
        self.chat_input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.chat_input_frame.grid_columnconfigure(0, weight=1)
        
        # Initialize chat components
        self.chat_client = None
        self.tool_manager = None
        self.current_lead = None
        self.current_lead_id = None
        self._last_lead_id = None
        self._chat_histories = {}
        
        # Create chat display and input components
        self._create_chat_components()

    def create_left_guidelines_section(self, parent):
        """Create a compact guidelines section for the left panel."""
        # Cost tracking section (moved from old right panel)
        self.cost_tracking_widget = CostTrackingWidget(parent)
        self.cost_tracking_widget.grid(row=6, column=0, sticky="ew", padx=20, pady=(10, 5))

        # Statistics section (moved from old right panel)  
        self.stats_widget = StatsWidget(parent)
        self.stats_widget.grid(row=7, column=0, sticky="ew", padx=20, pady=(5, 20))
        
    def _handle_chunks_sidebar_width_change(self, is_expanded: bool):
        """
        Handle retrieved chunks sidebar width changes to update the grid layout.
        
        Args:
            is_expanded (bool): Whether the sidebar is expanded
        """
        # Update panel sizes using the new layout system
        self._update_panel_sizes()

    def create_button_section(self, parent):
        """Create the button section."""
        button_frame = ctk.CTkFrame(parent, **get_frame_style("transparent"))
        button_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=10)
        button_frame.grid_columnconfigure(3, weight=1)

        self.score_button = ctk.CTkButton(
            button_frame,
            text="Score Lead",
            command=self._score_lead_clicked,
            **get_primary_button_style(),
        )
        self.score_button.grid(row=0, column=0, padx=(0, 10))

        clear_button = ctk.CTkButton(
            button_frame,
            text="Clear All",
            command=self._clear_all_clicked,
            **get_secondary_button_style(),
        )
        clear_button.grid(row=0, column=1, padx=(0, 10))

        self.view_logs_button = ctk.CTkButton(
            button_frame,
            text="📋 View Logs",
            command=self._view_logs_clicked,
            **get_secondary_button_style(),
        )
        # Initially hidden - only show after Score Lead is pressed
        self.view_logs_button.grid_remove()

    def create_progress_section(self, parent):
        """Create the progress display section."""
        self.progress_widget = ProgressWidget(parent)
        # Place the progress widget in the layout (it will start hidden)
        self.progress_widget.place_in_layout(row=5, column=0)


    def _clear_placeholder(self, event):
        """Clear placeholder text when the user clicks on the text area."""
        current_text = self.lead_text.get("1.0", "end-1c")
        if (
            current_text.strip()
            == "Enter the detailed description of the potential case..."
        ):
            self.lead_text.delete("1.0", "end")

    def get_chunk_limit(self):
        """
        Get the chunk limit from the UI with validation.
        
        Returns:
            int: The validated chunk limit (1-50), defaults to 10 if invalid.
        """
        try:
            limit = int(self.chunk_limit_var.get())
            if 1 <= limit <= 50:
                return limit
            else:
                # Reset to default if out of range
                from utils import load_config
                config = load_config()
                default_limit = config.get("aiconfig", {}).get("vector_search", {}).get("default_chunk_limit", 10)
                self.chunk_limit_var.set(str(default_limit))
                return default_limit
        except (ValueError, TypeError):
            # Reset to default if invalid input
            from utils import load_config
            config = load_config()
            default_limit = config.get("aiconfig", {}).get("vector_search", {}).get("default_chunk_limit", 10)
            self.chunk_limit_var.set(str(default_limit))
            return default_limit

    def get_tool_call_limit(self):
        """
        Get the tool call limit from the UI with validation.

        Returns:
            int: The validated tool call limit (1-20), defaults to config if invalid.
        """
        try:
            limit = int(self.tool_call_limit_var.get())
            if 1 <= limit <= 20:
                return limit
            else:
                from utils import load_config
                config = load_config()
                default_tool_limit = config.get("aiconfig", {}).get("tool_call_limit", 6)
                self.tool_call_limit_var.set(str(default_tool_limit))
                return default_tool_limit
        except (ValueError, TypeError):
            from utils import load_config
            config = load_config()
            default_tool_limit = config.get("aiconfig", {}).get("tool_call_limit", 6)
            self.tool_call_limit_var.set(str(default_tool_limit))
            return default_tool_limit

    def get_selected_process_model(self):
        """
        Get the currently selected process AI model.
        
        Returns:
            str: The selected process model name.
        """
        if self.model_selector:
            return self.model_selector.get_selected_process_model()
        else:
            return "gpt-5"  # Default fallback

    def get_selected_final_model(self):
        """
        Get the currently selected final AI model.
        
        Returns:
            str: The selected final model name.
        """
        if self.model_selector:
            return self.model_selector.get_selected_final_model()
        else:
            return "gpt-5"  # Default fallback

    def get_process_model_config(self):
        """
        Get the configuration for the currently selected process model.
        
        Returns:
            dict: The process model configuration dictionary.
        """
        if self.model_selector:
            return self.model_selector.get_process_model_config()
        else:
            # Return default gpt-5 config as fallback
            return {
                "deployment_name": "gpt-5",
                "description": "GPT-5 model (default)",
                "pricing": {"input": 1.25, "output": 10.00}
            }

    def get_final_model_config(self):
        """
        Get the configuration for the currently selected final model.
        
        Returns:
            dict: The final model configuration dictionary.
        """
        if self.model_selector:
            return self.model_selector.get_final_model_config()
        else:
            # Return default gpt-5 config as fallback
            return {
                "deployment_name": "gpt-5",
                "description": "GPT-5 model (default)",
                "pricing": {"input": 1.25, "output": 10.00}
            }

    def get_process_temperature(self):
        """
        Get the currently selected process temperature.
        
        Returns:
            float or None: The process temperature, or None if not set.
        """
        if self.model_selector:
            return self.model_selector.get_process_temperature()
        else:
            return None  # Default fallback

    def get_final_temperature(self):
        """
        Get the currently selected final temperature.
        
        Returns:
            float or None: The final temperature, or None if not set.
        """
        if self.model_selector:
            return self.model_selector.get_final_temperature()
        else:
            return None  # Default fallback

    def _score_lead_clicked(self):
        """Handle the Score Lead button click."""
        lead_text = self.lead_text.get("1.0", "end-1c")

        # Disable the button during processing
        self.score_button.configure(state="disabled")
        
        # Disable model settings button during scoring
        self.model_settings_button.configure(state="disabled")
        
        # Show right panel and configure for 3 panels
        self._configure_panel_layout(show_right_panel=True)
        self.right_panel.grid()
        self.retrieved_chunks_frame.grid()
        self.chat_panel.grid_remove()
        self.right_panel_title.configure(text="Retrieved Chunks")
        self.right_panel_show_btn.place_forget()
        
        # Disable all "Discuss Lead" buttons during scoring
        self._set_discuss_buttons_state("disabled")

        # Use event handler to process the lead
        success, message = self.event_handler.handle_score_lead_clicked(lead_text)

        if not success:
            # Re-enable button and show error
            self.score_button.configure(state="normal")
            # Re-enable model settings button
            self.model_settings_button.configure(state="normal")
            # Re-enable discuss buttons
            self._set_discuss_buttons_state("normal")
            # Hide right panel if scoring failed
            self._configure_panel_layout(show_right_panel=False)
            self.right_panel.grid_remove()
            self.right_panel_title.configure(text="Right Panel")
            self.right_panel_show_btn.place(relx=1.0, rely=0.5, anchor="e")
            messagebox.showwarning("Input Required", message)
        else:
            # Scoring successful - re-enable discuss buttons and model settings
            self._set_discuss_buttons_state("normal")
            self.model_settings_button.configure(state="normal")

    def _clear_all_clicked(self):
        """Handle the Clear All button click."""
        self.event_handler.handle_clear_all_clicked()

    def _view_logs_clicked(self):
        """Handle the View Logs button click."""
        # Open log viewer with session filtering
        LogViewerDialog(self, session_start_time=self.current_session_start_time)
        
    def _open_model_settings(self):
        """Handle the Model Configuration button click."""
        result, new_model_selector = ModelSelectionDialog.show_dialog(self, self.model_selector)
        
        if result == 'ok' and new_model_selector:
            # Update the stored model selector
            self.model_selector = new_model_selector
            self._update_model_status_label()
            # Chat model selection is now handled by the model selector
            
            
    def _update_model_status_label(self):
        """Update the model status label to show current configuration."""
        if self.model_selector:
            process_model = self.model_selector.get_selected_process_model()
            final_model = self.model_selector.get_selected_final_model()
            
            # Show abbreviated model names if they're the same, otherwise show both
            if process_model == final_model:
                status_text = f"Models: {process_model}"
            else:
                status_text = f"Models: {process_model} | {final_model}"
                
            # Add temperature info if set
            process_temp = self.model_selector.get_process_temperature()
            final_temp = self.model_selector.get_final_temperature()
            
            if process_temp is not None or final_temp is not None:
                temp_parts = []
                if process_temp is not None:
                    temp_parts.append(f"Temp: {process_temp}")
                if final_temp is not None and final_temp != process_temp:
                    temp_parts.append(f"| {final_temp}")
                if temp_parts:
                    status_text += f" ({' '.join(temp_parts)})"
            
            self.model_status_label.configure(text=status_text)
        else:
            self.model_status_label.configure(text="Models: Default Configuration")

    def _open_guidelines_popup(self):
        """Open a pop-out window showing scoring and feedback guidelines."""
        popup = ctk.CTkToplevel(self)
        popup.title("Guidelines")
        popup.geometry("900x800")
        popup.minsize(700, 600)
        popup.configure(fg_color=COLORS["primary_black"])
        try:
            popup.transient(self)
            popup.lift()
            popup.focus_force()
            popup.attributes("-topmost", True)
            # Allow returning to normal stacking after it is visible
            popup.after(300, lambda: popup.attributes("-topmost", False))
        except Exception:
            pass

        # Container frame
        container = ctk.CTkScrollableFrame(popup, **get_frame_style("secondary"))
        container.pack(fill="both", expand=True, padx=20, pady=20)
        container.grid_columnconfigure(0, weight=1)
        try:
            container.grid_rowconfigure(0, weight=1)
            container.grid_rowconfigure(1, weight=1)
        except Exception:
            pass

        # Scoring Guidelines
        scoring_section = GuidelinesWidget(container)
        scoring_section.grid(row=0, column=0, sticky="nsew", padx=5, pady=(0, 10))
        try:
            scoring_section.expand()
            # Ensure textbox has enough initial height for visibility; scrolling will handle the rest
            if hasattr(scoring_section, "guidelines_textbox"):
                scoring_section.guidelines_textbox.configure(height=28, width=100)
        except Exception:
            pass

        # Feedback Guidelines
        feedback_section = FeedbackGuidelinesWidget(container)
        feedback_section.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 0))
        try:
            feedback_section.expand()
            if hasattr(feedback_section, "feedback_textbox"):
                feedback_section.feedback_textbox.configure(height=28, width=100)
        except Exception:
            pass

        # Make the popup modal to keep it in front and focused
        try:
            popup.grab_set()
            popup.protocol("WM_DELETE_WINDOW", lambda: (popup.grab_release(), popup.destroy()))
        except Exception:
            pass

    def show_view_logs_button(self):
        """Show the View Logs button after Score Lead is pressed."""
        self.view_logs_button.grid(row=0, column=2)

    def hide_view_logs_button(self):
        """Hide the View Logs button."""
        self.view_logs_button.grid_remove()

    def refresh_results(self):
        """Refresh the results display."""
        # Clear existing results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        if not self.scored_leads:
            no_results_label = ctk.CTkLabel(
                self.results_frame,
                text="Enter a lead description above to score it and see the results here.",
                font=FONTS()["body"],
                text_color=COLORS["text_gray"],
            )
            no_results_label.grid(row=0, column=0, pady=20)
            # If no scored leads, hide right panel and configure for 2 panels
            self._configure_panel_layout(show_right_panel=False)
            self.right_panel.grid_remove()
            self.right_panel_show_btn.place(relx=1.0, rely=0.5, anchor="e")
            return

        for i, lead in enumerate(self.scored_leads):
            lead_item = LeadItem(
                self.results_frame,
                lead,
                lead_index=i,
                feedback_manager=self.feedback_manager,
            )
            lead_item.grid(row=i, column=0, sticky="ew", padx=10, pady=5)

    def setup_close_handler(self):
        """Set up the window close event handler to save any pending feedback."""
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Handle application closing - save any pending feedback before exit."""
        # Check if there's any pending feedback
        pending_count = self.feedback_manager.get_pending_feedback_count()

        # Debug: Print feedback status for troubleshooting
        print(
            f"DEBUG: Closing application - found {pending_count} pending feedback entries"
        )
        for key, entry in self.feedback_manager.pending_feedback.items():
            print(
                f"  - {key}: has_feedback={entry.has_feedback()}, has_unsaved_changes={entry.has_unsaved_changes}"
            )

        if pending_count > 0:
            # Ask user if they want to save pending feedback
            result = messagebox.askyesnocancel(
                "Unsaved Feedback",
                f"You have unsaved feedback for {pending_count} lead(s).\n\n"
                "Would you like to save this feedback before closing?\n\n"
                "• Yes: Save feedback and exit\n"
                "• No: Exit without saving\n"
                "• Cancel: Return to application",
            )

            if result is True:  # Yes - save and exit
                # Before saving, capture current text state for all lead items with pending feedback
                self._capture_final_text_states()
                saved_count = self.feedback_manager.save_all_pending_feedback()
                messagebox.showinfo(
                    "Feedback Saved", f"Saved feedback for {saved_count} lead(s)."
                )
                self.destroy()
            elif result is False:  # No - exit without saving
                self.destroy()
            # If cancel (None), do nothing - stay in application
        else:
            # No pending feedback, just close
            print("DEBUG: No pending feedback found, closing normally")
            self.destroy()


    def _capture_final_text_states(self):
        """Capture the final text state from all lead items with pending feedback."""
        # Iterate through all lead items in the results frame
        for widget in self.results_frame.winfo_children():
            if hasattr(widget, "lead_index") and hasattr(widget, "analysis_textbox"):
                lead_index = widget.lead_index
                current_chat_log = widget.current_chat_log

                if current_chat_log and self.feedback_manager.has_pending_feedback(
                    current_chat_log, lead_index
                ):
                    # Get current text and update feedback entry
                    current_analysis_text = widget.analysis_textbox.get("1.0", "end-1c")
                    feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
                        current_chat_log, lead_index, widget.lead["analysis"]
                    )
                    feedback_entry.set_replaced_analysis_text(current_analysis_text)

    def _create_chat_components(self):
        """Create the chat display and input components."""
        import tkinter as tk
        from tkinter import scrolledtext
        
        # Chat display using scrolledtext
        self.chat_display = scrolledtext.ScrolledText(
            self.chat_display_frame,
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
        
        # Input text box
        self.chat_input_text = ctk.CTkTextbox(
            self.chat_input_frame,
            height=80,
            font=FONTS()["body"],
            fg_color=COLORS["secondary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["border_gray"],
            border_width=1,
            wrap="word"
        )
        self.chat_input_text.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        # Send button
        self.chat_send_button = ctk.CTkButton(
            self.chat_input_frame,
            text="Send",
            width=80,
            height=80,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self.send_chat_message
        )
        self.chat_send_button.grid(row=0, column=1, sticky="ns")
        
        # Bind Enter key to send message
        self.chat_input_text.bind("<Return>", lambda e: self.send_chat_message())
        self.chat_input_text.bind("<Control-Return>", lambda e: self.send_chat_message())

    def open_chat_for_lead(self, lead: dict):
        """Open chat panel for the specified lead."""
        # Ensure right panel is visible and configured for 3 panels
        self._configure_panel_layout(show_right_panel=True)
        self.right_panel.grid()
        self.right_panel_title.configure(text="Chat Discussion")
        self.right_panel_show_btn.place_forget()
        
        # Hide retrieved chunks panel and show chat panel
        self.retrieved_chunks_frame.grid_remove()
        self.chat_panel.grid()
        
        # Update chat title with lead information
        lead_title = self._extract_lead_title(lead)
        self.chat_title.configure(text=f"💬 Discuss: {lead_title}")
        
        # Initialize chat client for this lead
        self._initialize_chat_for_lead(lead)
        
        # Load initial context
        self._load_chat_initial_context(lead)
        
        # Update panel sizes to maintain equal sizing
        self._update_panel_sizes()

    def close_chat(self):
        """Close the chat panel and show retrieved chunks panel."""
        # Save current chat history
        if self.current_lead_id:
            self._save_chat_history()
        
        # Hide chat panel and show retrieved chunks panel
        self.chat_panel.grid_remove()
        self.retrieved_chunks_frame.grid()
        
        # Clear current lead
        self.current_lead = None
        self.current_lead_id = None
        
        # If no scored leads exist, hide the right panel entirely
        if not self.scored_leads:
            self._configure_panel_layout(show_right_panel=False)
            self.right_panel.grid_remove()
            self.right_panel_title.configure(text="Right Panel")
            self.right_panel_show_btn.place(relx=1.0, rely=0.5, anchor="e")
        else:
            # Show retrieved chunks
            self.retrieved_chunks_frame.grid()
            self.right_panel_title.configure(text="Retrieved Chunks")
            # Update panel sizes to maintain equal sizing
            self._update_panel_sizes()

    def _extract_lead_title(self, lead: dict) -> str:
        """Extract a title from the lead for display."""
        analysis_text = lead.get('_edited_analysis') or lead.get('analysis', '')
        if analysis_text:
            from scripts.clients.agents.scoring import extract_title_from_response
            title = extract_title_from_response(analysis_text)
            if title and title != "Title not available":
                return title
        
        # Fallback to score-based title
        score = lead.get('score', 'N/A')
        return f"Lead (Score: {score}/100)"

    def _initialize_chat_for_lead(self, lead: dict):
        """Initialize chat client for the specified lead."""
        try:
            from scripts.clients.azure import AzureClient
            from scripts.clients.agents import ChatDiscussionAgent
            
            # Get selected chat model from model selector
            selected_model = self.model_selector.get_selected_chat_model()
            
            # Set current lead
            self.current_lead = lead
            self.current_lead_id = lead.get('id') or id(lead)
            
            # Check if we need to create a new chat agent (model change or first time)
            if (not hasattr(self, 'chat_agent') or 
                not hasattr(self, 'chat_client') or 
                self.chat_client.client_config.get("deployment_name") != selected_model):
                
                # Create Azure client with selected model
                self.chat_client = AzureClient(selected_model)
                
                # Get pre-initialized clients from business logic to avoid expensive re-initialization
                handler = getattr(self, 'event_handler', None)
                business = getattr(handler, 'business_logic', None)
                qdrant_manager = getattr(business, 'qdrant_manager', None) if business else None
                embedding_client = getattr(business, 'embedding_client', None) if business else None
                
                # Create chat discussion agent with pre-initialized clients for better performance
                self.chat_agent = ChatDiscussionAgent(
                    self.chat_client, 
                    qdrant_manager=qdrant_manager,
                    embedding_client=embedding_client
                )
                
                print(f"DEBUG: Created new chat agent with model: {selected_model}")
            
            # Always clear the visual chat display first
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.configure(state=tk.DISABLED)
            
            # Check if this is a new lead - if so, clear chat history
            if self._last_lead_id != self.current_lead_id:
                # New lead - clear chat history
                self.chat_agent.clear_history()
                self._last_lead_id = self.current_lead_id
                print(f"DEBUG: New lead detected ({self.current_lead_id}), clearing chat history")
            else:
                # Same lead - restore previous chat history if available
                if self.current_lead_id in self._chat_histories:
                    self.chat_client.message_history = self._chat_histories[self.current_lead_id].copy()
                    print(f"DEBUG: Same lead ({self.current_lead_id}), restoring chat history")
                else:
                    print(f"DEBUG: Same lead ({self.current_lead_id}), but no previous history found")
            
            # Initialize the agent for this lead
            self.chat_agent.initialize_for_lead(lead)

            # Tag chat telemetry for display and add to cost managers
            try:
                handler = getattr(self, 'event_handler', None)
                business = getattr(handler, 'business_logic', None)
                if business is not None and hasattr(self.chat_client, 'telemetry_manager'):
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
            
        except Exception as e:
            print(f"ERROR: Failed to initialize chat client: {e}")

    def _load_chat_initial_context(self, lead: dict):
        """Load initial context for the chat."""
        try:
            # Load analysis and description
            analysis_text = lead.get('_edited_analysis') or lead.get('analysis', 'No analysis available')
            description_text = lead.get('description', 'No description available')
            
            # Only load initial context for new leads (not when restoring chat history)
            if self._last_lead_id == self.current_lead_id and self.current_lead_id in self._chat_histories:
                # Restoring chat history - don't add initial context
                print(f"DEBUG: Restoring chat history for lead {self.current_lead_id}, skipping initial context")
                # Display the restored chat history
                self._display_restored_chat_history()
            else:
                # New lead - add initial context
                print(f"DEBUG: New lead {self.current_lead_id}, loading initial context")
                
                # Add context to chat client (but don't display in chat)
                from langchain_core.messages import AIMessage, HumanMessage
                analysis_message = AIMessage(content=f"**AI Analysis:**\n{analysis_text}")
                description_message = HumanMessage(content=f"**Original Lead Description:**\n{description_text}")
                self.chat_client.add_message(analysis_message)
                self.chat_client.add_message(description_message)
                
                # Display only welcome message in chat
                self.add_message_to_chat_display("AI Assistant", "Hello! I'm here to help you discuss this lead. You can ask me questions about the analysis, request additional information, or explore related files. How can I assist you?")
                
                # Add a helpful tip
                self.add_message_to_chat_display("System", "💡 Tip: You can view the full analysis and description in the main lead display area.")
            
        except Exception as e:
            print(f"ERROR: Failed to load initial context: {e}")

    def _display_restored_chat_history(self):
        """Display the restored chat history in the chat display."""
        # Clear the chat display
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        
        # Display all messages from the restored history (skip system message)
        for message in self.chat_client.message_history:
            if hasattr(message, '__class__'):
                # Skip system/tool messages
                if message.__class__.__name__ in ('SystemMessage', 'ToolMessage'):
                    continue
                # Skip initial context messages that were added for reference only
                content = getattr(message, 'content', '') or ''
                if isinstance(content, str) and (
                    content.startswith("**AI Analysis:**") or
                    content.startswith("**Original Lead Description:**")
                ):
                    continue
                if message.__class__.__name__ == 'AIMessage':
                    self.add_message_to_chat_display("AI Assistant", content)
                elif message.__class__.__name__ == 'HumanMessage':
                    self.add_message_to_chat_display("User", content)

    def send_chat_message(self):
        """Send user message and get AI response."""
        user_input = self.chat_input_text.get("1.0", tk.END).strip()
        if not user_input:
            return

        # Clear input
        self.chat_input_text.delete("1.0", tk.END)

        # Add user message to display
        self.add_message_to_chat_display("User", user_input)

        try:
            # Get AI response using the chat agent
            self.chat_send_button.configure(text="Thinking...", state="disabled")
            self.update()
            
            response = self.chat_agent.send_message(user_input)
            self.add_message_to_chat_display("AI Assistant", response)
            
            # Save chat history for this lead
            self._save_chat_history()
            
            # Update cost tracking UI after each chat turn
            try:
                handler = getattr(self, 'event_handler', None)
                business = getattr(handler, 'business_logic', None)
                if business is not None and hasattr(self, 'cost_tracking_widget'):
                    current_cost = business.get_current_lead_cost()
                    self.cost_tracking_widget.update_current_lead_cost(current_cost)
                    # Update model breakdown as well
                    model_costs = business.get_current_lead_cost_by_model()
                    self.cost_tracking_widget.set_model_costs(model_costs)
            except Exception:
                pass
            
        except Exception as e:
            error_msg = f"Error getting AI response: {str(e)}"
            self.add_message_to_chat_display("System", error_msg)
            print(f"Chat error: {error_msg}")
        finally:
            self.chat_send_button.configure(text="Send", state="normal")

    def add_message_to_chat_display(self, sender: str, message: str):
        """Add a message to the chat display."""
        import tkinter as tk
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

    def _save_chat_history(self):
        """Save the current chat history for this lead."""
        try:
            # Save a copy of the current message history
            self._chat_histories[self.current_lead_id] = self.chat_client.message_history.copy()
            print(f"DEBUG: Saved chat history for lead {self.current_lead_id}")
        except Exception as e:
            print(f"DEBUG: Failed to save chat history: {e}")

    def _log_panel_sizes(self):
        """Log the current sizes of all panels for debugging."""
        try:
            # Find the main frame
            main_frame = None
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkFrame) and child.grid_info().get('row') == 1:
                    main_frame = child
                    break
            
            if main_frame:
                print("=" * 50)
                print("DEBUG: Current panel sizes:")
                for i, child in enumerate(main_frame.winfo_children()):
                    if hasattr(child, 'winfo_width'):
                        panel_type = ["Left (Input)", "Middle (Results)", "Right (Chunks/Chat)"][i] if i < 3 else f"Panel {i}"
                        print(f"  {panel_type}: width={child.winfo_width()}, height={child.winfo_height()}")
                print("=" * 50)
        except Exception as e:
            print(f"DEBUG: Error logging panel sizes: {e}")

    def _on_window_resize(self, event):
        """Handle window resize to maintain equal panel sizing."""
        # Only handle main window resize, not child widget resizes
        if event.widget == self:
            # Use after_idle to ensure the resize is complete before adjusting panels
            self.after_idle(self._force_equal_panel_sizing)

    def _force_equal_panel_sizing(self):
        """Force all panels to have equal width."""
        try:
            # Find the main frame
            main_frame = None
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkFrame) and child.grid_info().get('row') == 1:
                    main_frame = child
                    break
            
            if main_frame:
                # Get the available width for the main frame
                main_width = main_frame.winfo_width()
                if main_width > 100:  # Only adjust if we have a reasonable width
                    # Calculate equal width for all panels (accounting for padding)
                    padding = 20  # Total horizontal padding
                    available_width = main_width - padding
                    
                    # Check if retrieved chunks is expanded or collapsed
                    is_expanded = getattr(self.retrieved_chunks_frame, 'is_expanded', True)
                    
                    if is_expanded:
                        # All panels get equal width
                        panel_width = available_width // 3
                        print(f"DEBUG: Forcing equal panel sizing - width={panel_width} (expanded)")
                        
                        # Set explicit widths for all panels
                        for i, child in enumerate(main_frame.winfo_children()):
                            if hasattr(child, 'configure') and i < 3:
                                child.configure(width=panel_width)
                                child.grid_propagate(False)  # Prevent content from affecting size
                    else:
                        # Right panel is collapsed, give more space to others
                        right_width = 200  # Fixed collapsed width
                        remaining_width = available_width - right_width
                        left_width = remaining_width // 2
                        middle_width = remaining_width - left_width
                        
                        print(f"DEBUG: Forcing panel sizing - left={left_width}, middle={middle_width}, right={right_width} (collapsed)")
                        
                        # Set explicit widths
                        for i, child in enumerate(main_frame.winfo_children()):
                            if hasattr(child, 'configure') and i < 3:
                                if i == 0:  # Left panel
                                    child.configure(width=left_width)
                                elif i == 1:  # Middle panel
                                    child.configure(width=middle_width)
                                elif i == 2:  # Right panel
                                    child.configure(width=right_width)
                                child.grid_propagate(False)  # Prevent content from affecting size
                    
                    # Force layout update
                    main_frame.update_idletasks()
                    
        except Exception as e:
            print(f"DEBUG: Error in force equal panel sizing: {e}")

    def after(self, delay, callback):
        """Wrapper for tkinter's after method."""
        return super().after(delay, callback)

    def run(self):
        """Start the application."""
        self.mainloop()
