"""
Progress Display Widgets

This module contains widgets for displaying progress information with status and timer updates.
"""

import customtkinter as ctk
from ..styles import COLORS, FONTS


# ─── PROGRESS DISPLAY WIDGET ────────────────────────────────────────────────────
class ProgressWidget:
    """Widget for displaying progress with status and timer updates."""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["tertiary_black"])

        self.progress_bar = ctk.CTkProgressBar(
            self.frame,
            progress_color=COLORS["accent_orange"],
            fg_color=COLORS["border_gray"],
        )

        self.status_label = ctk.CTkLabel(
            self.frame, text="", font=FONTS()["small"], text_color=COLORS["text_gray"]
        )

        self.timer_label = ctk.CTkLabel(
            self.frame, text="", font=FONTS()["small"], text_color=COLORS["text_gray"]
        )

        self.is_visible = False
        self._setup_layout()

    def _setup_layout(self):
        """Set up the internal layout of the progress widget."""
        self.frame.grid_columnconfigure(0, weight=1)
        # Place internal widgets but start them hidden
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.status_label.grid(row=1, column=0, padx=10, pady=(0, 5))
        self.timer_label.grid(row=2, column=0, padx=10, pady=(0, 10))
        # Initially hide all internal widgets
        self.progress_bar.grid_remove()
        self.status_label.grid_remove()
        self.timer_label.grid_remove()

    def place_in_layout(self, row, column, **grid_options):
        """Place the progress widget in the parent's layout. Called during initialization."""
        default_options = {"sticky": "ew", "padx": 20, "pady": 0}  # No vertical padding when hidden
        default_options.update(grid_options)
        self.frame.grid(row=row, column=column, **default_options)
        # Configure frame to take minimal space when hidden
        self.frame.configure(height=1)

    def show(self):
        """Show the progress widget by making it visible."""
        if not self.is_visible:
            # Show all internal widgets and auto-size frame
            self.frame.configure(height=0)  # Auto-size based on content
            self.progress_bar.grid()
            self.status_label.grid()
            self.timer_label.grid()
            # Update grid options to include padding when visible
            self.frame.grid_configure(pady=10)
            self.is_visible = True

    def hide(self):
        """Hide the progress widget by making it invisible."""
        if self.is_visible:
            # Hide all internal widgets and minimize frame
            self.progress_bar.grid_remove()
            self.status_label.grid_remove()
            self.timer_label.grid_remove()
            self.frame.configure(height=1)  # Minimal height
            # Remove padding when hidden
            self.frame.grid_configure(pady=0)
            self.is_visible = False

    def update(self, progress: float, status: str, elapsed_time: float):
        """Update the progress display."""
        self.progress_bar.set(progress / 100)
        self.status_label.configure(text=status)
        self.timer_label.configure(text=f"⏱️ Elapsed: {elapsed_time:.1f}s")
