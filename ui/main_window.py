"""
Main Application Window

This module contains the main application window class that coordinates all UI components
and handles the overall application flow.
"""

import customtkinter as ctk
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
        """Create the main content area with left, middle, and right panels."""
        main_frame = ctk.CTkFrame(self, **get_frame_style("primary"))
        main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)  # Input panel
        main_frame.grid_columnconfigure(1, weight=2)  # Results panel  
        main_frame.grid_columnconfigure(2, weight=0, minsize=150)  # Retrieved chunks panel (starts collapsed)

        # Left panel - Input and controls
        self.create_left_panel(main_frame)

        # Middle panel - Scored leads results
        self.create_middle_panel(main_frame)
        
        # Right panel - Retrieved chunks display
        self.create_retrieved_chunks_panel(main_frame)

    def create_left_panel(self, parent):
        """Create the left panel with input and controls."""
        left_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        left_frame.grid_rowconfigure(5, weight=1)  # Give weight to progress section to fill space
        left_frame.grid_columnconfigure(0, weight=1)

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
        # Find the main frame to update its grid configuration
        main_frame = None
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkFrame) and child.grid_info().get('row') == 1:
                main_frame = child
                break
                
        if main_frame:
            if is_expanded:
                # Sidebar is expanded, give it more space
                main_frame.grid_columnconfigure(2, weight=0, minsize=400)
            else:
                # Sidebar is collapsed, minimize its space
                main_frame.grid_columnconfigure(2, weight=0, minsize=150)
            
            # Force layout update
            main_frame.update_idletasks()

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

        # Use event handler to process the lead
        success, message = self.event_handler.handle_score_lead_clicked(lead_text)

        if not success:
            # Re-enable button and show error
            self.score_button.configure(state="normal")
            messagebox.showwarning("Input Required", message)

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

    def after(self, delay, callback):
        """Wrapper for tkinter's after method."""
        return super().after(delay, callback)

    def run(self):
        """Start the application."""
        self.mainloop()
