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

        # Maximum status length threshold based on provided sample message length
        # Reason: Prevent overly long log messages from expanding layout and cutting off timer
        self._max_status_length = len("Invoking message for 'gpt-5-mini'.")
        # Minimum height to ensure timer label is never clipped
        self._min_visible_height = 70

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
        # Ensure geometry propagates so height grows with content
        try:
            self.frame.grid_propagate(True)
        except Exception:
            pass

    def _truncate_status(self, text: str) -> str:
        """Truncate status text to prevent UI overflow.

        Args:
            text (str): Incoming status text.

        Returns:
            str: Possibly truncated text with ellipsis.
        """
        if not isinstance(text, str):
            return ""
        if len(text) <= self._max_status_length:
            return text
        # Leave room for the ellipsis
        cutoff = max(0, self._max_status_length - 3)
        return text[:cutoff] + "..."

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
            # After becoming visible, ensure minimum height to fit timer
            self.frame.update_idletasks()
            try:
                required = self.frame.winfo_reqheight()
                self.frame.configure(height=max(required, self._min_visible_height))
            except Exception:
                pass

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
        # Ensure widget is visible so timer is not cut off
        if not self.is_visible:
            self.show()

        self.progress_bar.set(progress / 100)
        truncated_status = self._truncate_status(status)
        # Dynamically wrap status based on available width
        try:
            width = self.frame.winfo_width() or self.parent.winfo_width()
            wrap = max(200, width - 40)
            self.status_label.configure(text=truncated_status, wraplength=wrap, justify="left")
        except Exception:
            self.status_label.configure(text=truncated_status)
        self.timer_label.configure(text=f"⏱️ Elapsed: {elapsed_time:.1f}s")
        # Ensure layout recalculates height to fit timer
        self.frame.update_idletasks()
        try:
            required = self.frame.winfo_reqheight()
            self.frame.configure(height=max(required, self._min_visible_height))
        except Exception:
            pass
