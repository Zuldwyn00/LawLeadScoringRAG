"""
Main Application Window

This module contains the main application window class that coordinates all UI components
and handles the overall application flow.
"""

import customtkinter as ctk
from tkinter import messagebox

from .styles import setup_theme, COLORS, FONTS, get_primary_button_style, get_secondary_button_style, get_textbox_style, get_frame_style
from .widgets import ProgressWidget, LeadItem, StatsWidget, GuidelinesWidget
from .handlers import UIEventHandler
from .dialogs import LogViewerDialog

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
        
        # Initialize with example lead
        self.scored_leads = self.event_handler.get_initial_leads()
        
        # Create UI components
        self.create_widgets()
        
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
            text_color=COLORS["accent_orange"]
        )
        title_label.grid(row=0, column=0, pady=10)
        
        subtitle_label = ctk.CTkLabel(
            title_frame,
            text="Enter a lead description to score its potential for success.",
            font=FONTS()["subtitle"],
            text_color=COLORS["text_gray"]
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
        left_frame.grid_rowconfigure(5, weight=1)
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
            text_color=COLORS["text_white"]
        )
        input_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        self.lead_text = ctk.CTkTextbox(
            parent,
            height=120,
            **get_textbox_style()
        )
        self.lead_text.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.lead_text.insert("1.0", "Enter the detailed description of the potential case...")
        
        # Clear placeholder text when clicked
        self.lead_text.bind("<Button-1>", self._clear_placeholder)
        
    def create_button_section(self, parent):
        """Create the button section."""
        button_frame = ctk.CTkFrame(parent, **get_frame_style("transparent"))
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        button_frame.grid_columnconfigure(3, weight=1)
        
        self.score_button = ctk.CTkButton(
            button_frame,
            text="Score Lead",
            command=self._score_lead_clicked,
            **get_primary_button_style()
        )
        self.score_button.grid(row=0, column=0, padx=(0, 10))
        
        clear_button = ctk.CTkButton(
            button_frame,
            text="Clear All",
            command=self._clear_all_clicked,
            **get_secondary_button_style()
        )
        clear_button.grid(row=0, column=1, padx=(0, 10))
        
        self.view_logs_button = ctk.CTkButton(
            button_frame,
            text="📋 View Logs",
            command=self._view_logs_clicked,
            **get_secondary_button_style()
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
            text_color=COLORS["text_white"]
        )
        results_label.grid(row=4, column=0, sticky="w", padx=20, pady=(20, 10))
        
        # Scrollable frame for results
        self.results_frame = ctk.CTkScrollableFrame(
            parent,
            **get_frame_style("secondary"),
            scrollbar_button_color=COLORS["accent_orange"],
            scrollbar_button_hover_color=COLORS["accent_orange_hover"]
        )
        self.results_frame.grid(row=5, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.results_frame.grid_columnconfigure(0, weight=1)
        
    def create_right_panel(self, parent):
        """Create the right panel with guidelines and stats."""
        right_frame = ctk.CTkFrame(parent, **get_frame_style("secondary"))
        right_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Guidelines expandable widget
        self.guidelines_widget = GuidelinesWidget(right_frame)
        self.guidelines_widget.grid(row=0, column=0, sticky="new", padx=20, pady=20)
        
        # Statistics section
        self.stats_widget = StatsWidget(right_frame)
        self.stats_widget.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        
    def _clear_placeholder(self, event):
        """Clear placeholder text when the user clicks on the text area."""
        current_text = self.lead_text.get("1.0", "end-1c")
        if current_text.strip() == "Enter the detailed description of the potential case...":
            self.lead_text.delete("1.0", "end")
            
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
                text_color=COLORS["text_gray"]
            )
            no_results_label.grid(row=0, column=0, pady=20)
            return
            
        for i, lead in enumerate(self.scored_leads):
            lead_item = LeadItem(
                self.results_frame,
                lead
            )
            lead_item.grid(row=i, column=0, sticky="ew", padx=10, pady=5)
            
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
