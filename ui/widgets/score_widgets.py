"""
Score Display Widgets

This module contains widgets for displaying and editing scores with visual feedback.
"""

import customtkinter as ctk
from tkinter import simpledialog
from ..styles import COLORS, FONTS, get_score_color


# ─── SCORE BLOCK WIDGET ─────────────────────────────────────────────────────────
class ScoreBlock(ctk.CTkFrame):
    """Widget for displaying a score in a colored block."""

    def __init__(
        self, parent, score: int, editable: bool = False, on_score_change=None, **kwargs
    ):
        self.original_score = score
        self.current_score = score
        self.editable = editable
        self.on_score_change = on_score_change
        color = get_score_color(score)

        super().__init__(
            parent, width=70, height=70, fg_color=color, corner_radius=12, **kwargs
        )

        self.grid_propagate(False)

        if editable:
            # Create clickable score for editing
            self.score_label = ctk.CTkLabel(
                self,
                text=str(score),
                font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
                text_color=COLORS["text_white"],
                cursor="hand2",
            )
            self.score_label.bind("<Button-1>", self._edit_score)

            # Add edit indicator
            self.edit_indicator = ctk.CTkLabel(
                self,
                text="✏️",
                font=ctk.CTkFont(size=10),
                text_color=COLORS["text_white"],
            )
            self.edit_indicator.place(relx=0.85, rely=0.15, anchor="center")
        else:
            self.score_label = ctk.CTkLabel(
                self,
                text=str(score),
                font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
                text_color=COLORS["text_white"],
            )

        self.score_label.place(relx=0.5, rely=0.5, anchor="center")

    def _edit_score(self, event=None):
        """Handle score editing when clicked."""
        new_score = simpledialog.askinteger(
            "Edit Score",
            f"Enter new score (0-100):\nOriginal score: {self.original_score}",
            initialvalue=self.current_score,
            minvalue=0,
            maxvalue=100,
        )

        if new_score is not None and new_score != self.current_score:
            self.update_score(new_score)
            if self.on_score_change:
                self.on_score_change(self.original_score, new_score)

    def update_score(self, new_score: int):
        """Update the displayed score and color."""
        self.current_score = new_score
        self.score_label.configure(text=str(new_score))

        # Update background color
        new_color = get_score_color(new_score)
        self.configure(fg_color=new_color)
