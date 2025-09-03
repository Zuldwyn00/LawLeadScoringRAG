"""
Main Application Window

This module contains the main application window class that coordinates all UI components
and handles the overall application flow.
"""

import customtkinter as ctk
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
)
from .handlers import UIEventHandler
from .dialogs import LogViewerDialog
from .feedback_manager import FeedbackManager


# ─── MAIN APPLICATION CLASS ─────────────────────────────────────────────────────
class LeadScoringApp:
    """Main application window for the Lead Scoring System."""

    def __init__(self):
        # Set up theme first
        setup_theme()

        # Initialize main window
        self.root = ctk.CTk()
        self.setup_window()

        # Initialize data
        self.scored_leads = []
        self.current_session_start_time = None

        # Initialize event handler
        self.event_handler = UIEventHandler(self)

        # Initialize feedback manager for program close handling
        self.feedback_manager = FeedbackManager()
        print(
            f"DEBUG: Main window using FeedbackManager instance: {id(self.feedback_manager)}"
        )

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
        self.root.title("⚖️ Lead Scoring System")
        self.root.geometry("1500x1000")
        self.root.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights for responsive design
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Set minimum size
        self.root.minsize(1200, 800)

    def create_widgets(self):
        """Create and arrange all UI widgets."""
        self.create_title_section()
        self.create_main_content()

    def create_title_section(self):
        """Create the title section at the top of the window."""
        title_frame = ctk.CTkFrame(self.root, **get_frame_style("primary"))
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        title_frame.grid_columnconfigure(0, weight=1)

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

    def create_main_content(self):
        """Create the main content area with left and right panels."""
        main_frame = ctk.CTkFrame(self.root, **get_frame_style("primary"))
        main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=1)

        # Left panel - Input and results
        self.create_left_panel(main_frame)

        # Right panel - Guidelines and stats
        self.create_right_panel(main_frame)

    def create_left_panel(self, parent):
        """Create the left panel with input and results."""
        left_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        left_frame.grid_rowconfigure(6, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # Input section
        self.create_input_section(left_frame)

        # Button section
        self.create_button_section(left_frame)

        # Progress section
        self.create_progress_section(left_frame)

        # Results section
        self.create_results_section(left_frame)

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

        # Vector search settings section
        self.create_vector_search_settings(parent)

    def create_vector_search_settings(self, parent):
        """Create the vector search settings section."""
        # Load default chunk limit from config
        from utils import load_config
        config = load_config()
        default_limit = config.get("aiconfig", {}).get("vector_search", {}).get("default_chunk_limit", 10)
        
        # Settings frame
        settings_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        settings_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 0))
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Label for chunk limit
        chunk_limit_label = ctk.CTkLabel(
            settings_frame,
            text="Vector Search Chunks:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
        )
        chunk_limit_label.grid(row=0, column=0, sticky="w", padx=(15, 10), pady=10)
        
        # Chunk limit entry
        self.chunk_limit_var = ctk.StringVar(value=str(default_limit))
        self.chunk_limit_entry = ctk.CTkEntry(
            settings_frame,
            textvariable=self.chunk_limit_var,
            width=80,
            font=FONTS()["body"],
            placeholder_text="10",
        )
        self.chunk_limit_entry.grid(row=0, column=1, sticky="w", padx=(0, 15), pady=10)
        
        # Help text
        help_label = ctk.CTkLabel(
            settings_frame,
            text="Number of similar cases to retrieve (1-50)",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"],
        )
        help_label.grid(row=0, column=2, sticky="w", padx=(10, 15), pady=10)

    def create_button_section(self, parent):
        """Create the button section."""
        button_frame = ctk.CTkFrame(parent, **get_frame_style("transparent"))
        button_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
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

    def create_results_section(self, parent):
        """Create the results display section."""
        results_label = ctk.CTkLabel(
            parent,
            text="Scored Leads",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"],
        )
        results_label.grid(row=5, column=0, sticky="w", padx=20, pady=(20, 10))

        # Scrollable frame for results
        self.results_frame = ctk.CTkScrollableFrame(
            parent,
            **get_frame_style("secondary"),
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"],
        )
        self.results_frame.grid(row=6, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.results_frame.grid_columnconfigure(0, weight=1)

    def create_right_panel(self, parent):
        """Create the right panel with guidelines and stats."""
        right_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        right_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        right_frame.grid_rowconfigure(
            0, weight=1
        )  # Make the expandable area take most space
        right_frame.grid_columnconfigure(0, weight=1)

        # Container for expandable widgets that takes maximum available space
        expandable_container = ctk.CTkFrame(right_frame, fg_color="transparent")
        expandable_container.grid(
            row=0, column=0, sticky="nsew", padx=20, pady=(20, 10)
        )
        expandable_container.grid_rowconfigure(0, weight=0)  # Guidelines widget row
        expandable_container.grid_rowconfigure(1, weight=0)  # Feedback widget row
        expandable_container.grid_rowconfigure(
            2, weight=1
        )  # Spacer row - gets weight when nothing expanded
        expandable_container.grid_columnconfigure(0, weight=1)

        # Scoring Guidelines expandable widget
        self.guidelines_widget = GuidelinesWidget(expandable_container)
        self.guidelines_widget.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        # Feedback Guidelines expandable widget
        self.feedback_guidelines_widget = FeedbackGuidelinesWidget(expandable_container)
        self.feedback_guidelines_widget.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Spacer to fill remaining space and push stats to very bottom
        spacer = ctk.CTkFrame(expandable_container, fg_color="transparent", height=1)
        spacer.grid(row=2, column=0, sticky="nsew")

        # Statistics section (positioned at the very bottom with minimal space)
        self.stats_widget = StatsWidget(right_frame)
        self.stats_widget.grid(row=1, column=0, sticky="ew", padx=20, pady=(5, 20))

        # Set up mutual exclusion for expandable widgets
        self._setup_expandable_mutual_exclusion()

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
        LogViewerDialog(self.root, session_start_time=self.current_session_start_time)

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
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
                self.root.destroy()
            elif result is False:  # No - exit without saving
                self.root.destroy()
            # If cancel (None), do nothing - stay in application
        else:
            # No pending feedback, just close
            print("DEBUG: No pending feedback found, closing normally")
            self.root.destroy()

    def _setup_expandable_mutual_exclusion(self):
        """Set up mutual exclusion between expandable widgets in the right panel."""
        expandable_widgets = [self.guidelines_widget, self.feedback_guidelines_widget]

        def create_exclusive_toggle(target_widget):
            def exclusive_toggle():
                # First, collapse all other widgets if target is being expanded
                if not target_widget.is_expanded:
                    for other_widget in expandable_widgets:
                        if other_widget != target_widget and other_widget.is_expanded:
                            other_widget.collapse()  # Collapse others first

                # Now toggle the target widget
                if target_widget.is_expanded:
                    target_widget.collapse()
                else:
                    target_widget.expand()

                # Force layout update immediately to ensure proper space allocation
                self._update_expandable_layout()

            return exclusive_toggle

        # Replace the button commands directly with exclusive versions
        self.guidelines_widget.header_button.configure(
            command=create_exclusive_toggle(self.guidelines_widget)
        )
        self.feedback_guidelines_widget.header_button.configure(
            command=create_exclusive_toggle(self.feedback_guidelines_widget)
        )

    def _update_expandable_layout(self):
        """Update the layout when expandable widgets change state."""
        # Find which widget is currently expanded
        expanded_widget = None
        expandable_container = (
            self.guidelines_widget.master
        )  # Get the expandable container

        for widget in [self.guidelines_widget, self.feedback_guidelines_widget]:
            if widget.is_expanded:
                expanded_widget = widget
                break

        if expanded_widget:
            # Reset all row weights to 0 first
            expandable_container.grid_rowconfigure(0, weight=0)
            expandable_container.grid_rowconfigure(1, weight=0)
            expandable_container.grid_rowconfigure(2, weight=0)

            # Configure the expanded widget to take ALL available space
            if expanded_widget == self.guidelines_widget:
                # Guidelines widget gets all the space
                expandable_container.grid_rowconfigure(0, weight=1)
                self.guidelines_widget.grid_configure(sticky="nsew", pady=(0, 5))
                self.feedback_guidelines_widget.grid_configure(sticky="ew", pady=(0, 5))
            elif expanded_widget == self.feedback_guidelines_widget:
                # Feedback widget gets all the space
                expandable_container.grid_rowconfigure(1, weight=1)
                self.feedback_guidelines_widget.grid_configure(
                    sticky="nsew", pady=(0, 5)
                )
                self.guidelines_widget.grid_configure(sticky="ew", pady=(0, 5))

            # Ensure the expanded widget's internal layout is configured for full expansion
            expanded_widget.grid_rowconfigure(1, weight=1)  # Content row gets weight
            expanded_widget.content_frame.grid_rowconfigure(
                0, weight=1
            )  # Textbox row gets weight

        else:
            # No widget expanded - restore default layout with spacer
            expandable_container.grid_rowconfigure(0, weight=0)
            expandable_container.grid_rowconfigure(1, weight=0)
            expandable_container.grid_rowconfigure(
                2, weight=1
            )  # Spacer gets the weight

            # Restore normal spacing and layout
            self.guidelines_widget.grid_configure(sticky="ew", pady=(0, 10))
            self.feedback_guidelines_widget.grid_configure(sticky="ew", pady=(0, 10))

            # Reset internal weights
            self.guidelines_widget.grid_rowconfigure(1, weight=0)
            self.feedback_guidelines_widget.grid_rowconfigure(1, weight=0)

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
        return self.root.after(delay, callback)

    def run(self):
        """Start the application."""
        self.root.mainloop()


# ─── APPLICATION MAIN ───────────────────────────────────────────────────────────
def main():
    """Main function to run the application."""
    app = LeadScoringApp()
    app.run()


if __name__ == "__main__":
    main()
