"""
Model Selection Dialog Module

This module contains the ModelSelectionDialog class for configuring AI models
in a separate popup window.
"""

import customtkinter as ctk
from ..styles import COLORS, FONTS, get_primary_button_style, get_secondary_button_style, get_frame_style
from ..widgets import ModelSelectorWidget


class ModelSelectionDialog(ctk.CTkToplevel):
    """Modal dialog for selecting AI models and configuring settings."""

    def __init__(self, parent, current_model_selector=None):
        super().__init__(parent)
        
        # Store reference to current model selector to preserve settings
        self.current_model_selector = current_model_selector
        self.model_selector = None
        self.result = None  # Will store 'ok' or 'cancel'
        
        self.setup_window()
        self.create_widgets()
        
        # Center the window
        self.center_window()
        
        # Make it modal
        self.transient(parent)
        self.grab_set()
        
        # Set up close handler
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
    def setup_window(self):
        """Configure the dialog window."""
        self.title("⚙️ AI Model Configuration")
        self.geometry("800x400")
        self.configure(fg_color=COLORS["primary_black"])
        self.resizable(False, False)
        
        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        self.create_header()
        self.create_model_selection()
        self.create_buttons()
        
    def create_header(self):
        """Create the dialog header."""
        header_frame = ctk.CTkFrame(self, **get_frame_style("primary"))
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="⚙️ AI Model Configuration",
            font=FONTS()["heading"],
            text_color=COLORS["accent_orange"],
        )
        title_label.grid(row=0, column=0, pady=10)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Configure AI models and temperature settings for lead scoring.",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"],
        )
        subtitle_label.grid(row=1, column=0, pady=(0, 10))
        
    def create_model_selection(self):
        """Create the model selection section."""
        content_frame = ctk.CTkFrame(self, **get_frame_style("secondary"))
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # Create model selector widget
        self.model_selector = ModelSelectorWidget(content_frame)
        self.model_selector.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        
        # If we have current settings, copy them to the new selector
        if self.current_model_selector:
            self._copy_current_settings()
            
    def create_buttons(self):
        """Create the OK/Cancel button section."""
        button_frame = ctk.CTkFrame(self, **get_frame_style("transparent"))
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            **get_secondary_button_style(),
        )
        cancel_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="e")
        
        ok_button = ctk.CTkButton(
            button_frame,
            text="Apply Settings",
            command=self._on_ok,
            **get_primary_button_style(),
        )
        ok_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="w")
        
    def center_window(self):
        """Center the dialog window on the parent."""
        self.update_idletasks()
        
        # Get window dimensions
        width = self.winfo_width()
        height = self.winfo_height()
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Calculate position
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        
    def _copy_current_settings(self):
        """Copy settings from the current model selector to the dialog."""
        if not self.current_model_selector or not self.model_selector:
            return
            
        # Copy model selections
        self.model_selector.set_process_model(
            self.current_model_selector.get_selected_process_model()
        )
        self.model_selector.set_final_model(
            self.current_model_selector.get_selected_final_model()
        )
        
        # Copy temperature settings
        self.model_selector.set_process_temperature(
            self.current_model_selector.get_process_temperature()
        )
        self.model_selector.set_final_temperature(
            self.current_model_selector.get_final_temperature()
        )
        
    def _on_ok(self):
        """Handle OK button click."""
        self.result = 'ok'
        self.destroy()
        
    def _on_cancel(self):
        """Handle Cancel button click or window close."""
        self.result = 'cancel'
        self.destroy()
        
    def get_model_selector(self):
        """
        Get the model selector widget from this dialog.
        
        Returns:
            ModelSelectorWidget: The model selector widget.
        """
        return self.model_selector
        
    @staticmethod
    def show_dialog(parent, current_model_selector=None):
        """
        Show the model selection dialog and return the result.
        
        Args:
            parent: The parent window.
            current_model_selector: Current ModelSelectorWidget to copy settings from.
            
        Returns:
            tuple: (result, model_selector) where result is 'ok'/'cancel' and
                  model_selector is the ModelSelectorWidget instance (if OK was clicked).
        """
        dialog = ModelSelectionDialog(parent, current_model_selector)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        if dialog.result == 'ok':
            return 'ok', dialog.get_model_selector()
        else:
            return 'cancel', None
