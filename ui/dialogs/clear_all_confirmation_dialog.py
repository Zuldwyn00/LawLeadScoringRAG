"""
Clear All Confirmation Dialog

This module provides a confirmation dialog that warns users about the permanent
deletion of scored leads when using the "Clear All" functionality.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from ..styles import COLORS, FONTS


class ClearAllConfirmationDialog(ctk.CTkToplevel):
    """
    Confirmation dialog for the Clear All functionality.
    
    This dialog warns users that clearing all leads will permanently delete
    all previously scored leads and asks for confirmation before proceeding.
    """

    def __init__(self, parent, on_confirm: Callable[[], None], on_cancel: Optional[Callable[[], None]] = None):
        """
        Initialize the confirmation dialog.

        Args:
            parent: The parent window.
            on_confirm: Callback function to execute when user confirms.
            on_cancel: Optional callback function to execute when user cancels.
        """
        super().__init__(parent)
        
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        
        self.setup_dialog()
        self.create_widgets()
        
        # Center the dialog on the parent window
        self.center_on_parent()

    def setup_dialog(self):
        """Configure the dialog window properties."""
        self.title("⚠️ Clear All Leads - Confirmation Required")
        self.geometry("500x300")
        self.configure(fg_color=COLORS["primary_black"])
        
        # Make dialog modal
        self.transient(self.master)
        self.grab_set()
        
        # Configure grid weights
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Main container
        main_frame = ctk.CTkFrame(self, **self._get_frame_style())
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Warning icon and title
        title_frame = ctk.CTkFrame(main_frame, **self._get_frame_style("transparent"))
        title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        title_frame.grid_columnconfigure(1, weight=1)

        # Warning icon
        warning_icon = ctk.CTkLabel(
            title_frame,
            text="⚠️",
            font=("Arial", 48),
            text_color=COLORS["accent_orange"]
        )
        warning_icon.grid(row=0, column=0, padx=(0, 15), pady=10)

        # Title
        title_label = ctk.CTkLabel(
            title_frame,
            text="Clear All Leads",
            font=FONTS()["heading"],
            text_color=COLORS["text_white"]
        )
        title_label.grid(row=0, column=1, sticky="w", pady=10)

        # Warning message
        message_frame = ctk.CTkFrame(main_frame, **self._get_frame_style("transparent"))
        message_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        message_frame.grid_columnconfigure(0, weight=1)

        warning_text = ctk.CTkLabel(
            message_frame,
            text=(
                "This action will delete all scored leads by moving them into a seperate folder..\n\n"
                "• All chat logs will be moved to the deleted folder\n"
                "• All lead data will be removed from the UI\n"
                "• This action is not permanent and can be undone by moving the files back into the chat_logs folder\n"
                "• To PERMANATELY delete the scored leads you must delete the files manually for safety in 'scripts/data/chat_logs.'\n\n"
                "Are you sure you want to continue?"
            ),
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
            justify="left"
        )
        warning_text.grid(row=0, column=0, sticky="nsew", pady=10)

        # Button frame
        button_frame = ctk.CTkFrame(main_frame, **self._get_frame_style("transparent"))
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Cancel button
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            **self._get_secondary_button_style()
        )
        cancel_button.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        # Confirm button
        confirm_button = ctk.CTkButton(
            button_frame,
            text="Clear All Leads",
            command=self._on_confirm,
            **self._get_danger_button_style()
        )
        confirm_button.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        # Focus on cancel button by default for safety
        cancel_button.focus_set()

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()
        
        # Get parent window position and size
        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        
        # Calculate center position
        dialog_width = self.winfo_reqwidth()
        dialog_height = self.winfo_reqheight()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        # Set position
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    def _on_confirm(self):
        """Handle confirm button click."""
        self.destroy()
        if self.on_confirm:
            self.on_confirm()

    def _on_cancel(self):
        """Handle cancel button click."""
        self.destroy()
        if self.on_cancel:
            self.on_cancel()

    def _get_frame_style(self, style="secondary"):
        """Get frame styling based on style type."""
        if style == "transparent":
            return {
                "fg_color": "transparent",
                "corner_radius": 0
            }
        else:  # secondary
            return {
                "fg_color": COLORS["secondary_black"],
                "corner_radius": 10
            }

    def _get_secondary_button_style(self):
        """Get secondary button styling."""
        return {
            "fg_color": COLORS["secondary_black"],
            "hover_color": COLORS["tertiary_black"],
            "text_color": COLORS["text_white"],
            "corner_radius": 8,
            "height": 40,
            "font": FONTS()["button"]
        }

    def _get_danger_button_style(self):
        """Get danger button styling for destructive actions."""
        return {
            "fg_color": "#dc3545",  # Bootstrap danger red
            "hover_color": "#c82333",  # Darker red on hover
            "text_color": COLORS["text_white"],
            "corner_radius": 8,
            "height": 40,
            "font": FONTS()["button"]
        }
