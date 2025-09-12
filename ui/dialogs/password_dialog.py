"""
Password Dialog Module

This module contains the PasswordDialog class for password authentication
in a modal dialog window.
"""

import customtkinter as ctk
from ..styles import COLORS, FONTS


class PasswordDialog(ctk.CTkToplevel):
    """Modal dialog for password authentication."""

    def __init__(self, parent):
        super().__init__(parent)

        self.password_correct = False
        self.setup_window()
        self.create_widgets()

        # Center the window
        self.center_window()

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Focus on password entry
        self.password_entry.focus()

    def setup_window(self):
        """Configure the dialog window."""
        self.title("Authentication Required")
        self.geometry("400x250")
        self.configure(fg_color=COLORS["primary_black"])
        self.resizable(False, False)

        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Title
        title_label = ctk.CTkLabel(
            self,
            text="🔐 Authentication Required",
            font=FONTS()["title"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=20)

        # Content frame
        content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_columnconfigure(0, weight=1)

        # Instructions
        instruction_label = ctk.CTkLabel(
            content_frame,
            text="Please enter the password to access the Lead Scoring System:",
            font=FONTS()["body"],
            text_color=COLORS["text_white"],
            wraplength=350,
        )
        instruction_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Password entry
        self.password_entry = ctk.CTkEntry(
            content_frame,
            placeholder_text="Enter password...",
            show="*",
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["border_gray"],
            border_width=2,
        )
        self.password_entry.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        self.password_entry.bind("<Return>", lambda e: self.check_password())

        # Error label (initially hidden)
        self.error_label = ctk.CTkLabel(
            content_frame, text="", font=FONTS()["small"], text_color="#ef4444"
        )
        self.error_label.grid(row=2, column=0, padx=20, pady=5)

        # Button frame
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=20)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Cancel button
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            font=FONTS()["button"],
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            border_color=COLORS["border_gray"],
            border_width=2,
            command=self.cancel,
        )
        cancel_button.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        # Login button
        login_button = ctk.CTkButton(
            button_frame,
            text="Login",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            command=self.check_password,
        )
        login_button.grid(row=0, column=1, padx=(10, 0), sticky="ew")

    def check_password(self):
        """Check if the entered password is correct."""
        import os

        correct_password = os.getenv("STREAMLIT_PASSWORD")
        entered_password = self.password_entry.get()

        if not correct_password:
            # No password required
            self.password_correct = True
            self.destroy()
            return

        if entered_password == correct_password:
            self.password_correct = True
            self.destroy()
        else:
            self.error_label.configure(text="❌ Incorrect password. Please try again.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus()

    def cancel(self):
        """Cancel authentication and close the application."""
        self.password_correct = False
        self.destroy()

    def center_window(self):
        """Center the dialog window on the screen."""
        self.update_idletasks()

        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Get dialog dimensions
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")
