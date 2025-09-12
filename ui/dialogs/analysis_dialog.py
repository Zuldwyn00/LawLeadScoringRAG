"""
Analysis Dialog Module

This module contains the AnalysisDialog class for displaying AI analysis results
in a modal dialog window.
"""

import customtkinter as ctk
from ..styles import COLORS, FONTS


class AnalysisDialog(ctk.CTkToplevel):
    """Modal dialog for displaying AI analysis results."""

    def __init__(self, parent, lead: dict):
        super().__init__(parent)

        self.lead = lead
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

    def setup_window(self):
        """Configure the dialog window."""
        self.title(f"AI Analysis - Score: {self.lead['score']}/100")
        self.geometry("900x700")
        self.configure(fg_color=COLORS["primary_black"])

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color=COLORS["primary_black"])
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="AI Analysis & Recommendation",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)

        # Score info
        score_info = f"Score: {self.lead['score']}/100 | Confidence: {self.lead.get('confidence', 50)}/100"
        score_label = ctk.CTkLabel(
            title_frame,
            text=score_info,
            font=FONTS()["heading"],
            text_color=COLORS["text_gray"],
        )
        score_label.grid(row=1, column=0, pady=(0, 10))

        # Analysis content
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self.analysis_text = ctk.CTkTextbox(
            content_frame,
            font=FONTS()["body"],
            fg_color=COLORS["secondary_black"],
            text_color=COLORS["text_white"],
            wrap="word",
        )
        self.analysis_text.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.analysis_text.insert("1.0", self.lead["analysis"])
        self.analysis_text.configure(state="disabled")

        # Close button
        close_button = ctk.CTkButton(
            self,
            text="Close",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.destroy,
        )
        close_button.grid(row=2, column=0, pady=(0, 20))

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
