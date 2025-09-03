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

    def show(self):
        """Show the progress widget."""
        if not self.is_visible:
            self.frame.grid(row=4, column=0, sticky="ew", padx=20, pady=10)
            self.frame.grid_columnconfigure(0, weight=1)

            self.progress_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
            self.status_label.grid(row=1, column=0, padx=10, pady=(0, 5))
            self.timer_label.grid(row=2, column=0, padx=10, pady=(0, 10))

            self.is_visible = True

    def hide(self):
        """Hide the progress widget."""
        if self.is_visible:
            self.frame.grid_remove()
            self.is_visible = False

    def update(self, progress: float, status: str, elapsed_time: float):
        """Update the progress display."""
        self.progress_bar.set(progress / 100)
        self.status_label.configure(text=status)
        self.timer_label.configure(text=f"⏱️ Elapsed: {elapsed_time:.1f}s")
