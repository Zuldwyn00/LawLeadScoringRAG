"""
Tutorial Overlay Widget

This module contains the interactive overlay that guides users through the
feedback workflow with animated highlights and step-by-step instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import customtkinter as ctk
import tkinter as tk

from ..styles import COLORS, FONTS


@dataclass
class TutorialStep:
    """Configuration for a single tutorial step."""

    title: str
    description: str
    target_resolver: Callable[[], Optional[tk.Widget]]
    bubble_position: str = "bottom"  # bottom, top, left, right
    highlight_padding: int = 12


class FeedbackTutorialOverlay(ctk.CTkToplevel):
    """Overlay that walks the user through providing lead feedback."""

    FADE_STEPS = 8

    def __init__(self, master: ctk.CTk, steps: list[TutorialStep]):
        super().__init__(master)
        self.steps = steps
        self.current_step_index = -1
        self.highlight_id: Optional[int] = None
        self.arrow_id: Optional[int] = None
        self.highlight_pulse_direction = 1
        self.highlight_width = 5
        self._highlight_job_id: Optional[str] = None
        self._animation_running = False
        self._in_redraw = False
        self._follow_job_id: Optional[str] = None
        self._fast_redraw_job_id: Optional[str] = None
        self._last_bbox: Optional[Tuple[int, int, int, int]] = None

        # Configure top-level overlay window
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # Use a magic transparent color for creating a true spotlight hole
        self._transparent_color = "#010203"
        try:
            # Windows supports per-color transparency; this creates a real hole
            self.wm_attributes("-transparentcolor", self._transparent_color)
        except tk.TclError:
            # If not supported on this platform, we silently continue
            pass
        self.configure(fg_color=self._transparent_color)
        self.withdraw()  # Show after geometry is set

        # Create canvas for drawing overlay elements
        self.canvas = tk.Canvas(
            self,
            # Match the magic transparent color so untouched areas are see-through
            bg=self._transparent_color,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Event bindings
        self.bind("<Button-1>", self._handle_click)
        # Remove Configure binding as it can cause infinite loops
        self._bind_scroll_listeners()

    def start(self):
        """Display the overlay and start the tutorial."""

        self._anchor_to_master()
        self.deiconify()
        # Ensure all mouse input is directed to this overlay, even over the transparent hole
        try:
            self.grab_set_global()
        except tk.TclError:
            # Fallback: local grab
            try:
                self.grab_set()
            except tk.TclError:
                pass
        try:
            self.focus_set()
        except tk.TclError:
            pass
        self.attributes("-alpha", 0.0)
        self._fade_in(step=0)
        self._show_step(0)
        self._start_follow_target()

    def _anchor_to_master(self):
        """Match the overlay geometry to the master window."""

        self.master.update_idletasks()
        x = self.master.winfo_rootx()
        y = self.master.winfo_rooty()
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _fade_in(self, step: int):
        """Fade the overlay in for a smooth appearance."""

        if not self.winfo_exists():
            return

        alpha = min(1.0, (step + 1) / self.FADE_STEPS)
        try:
            self.attributes("-alpha", alpha)
        except tk.TclError:
            return

        if alpha < 0.88:
            self.after(18, lambda: self._fade_in(step + 1))

    def _handle_click(self, _event):
        """Advance to the next tutorial step on click."""

        self._show_step(self.current_step_index + 1)

    def _show_step(self, index: int):
        """Render the provided step or close the overlay when finished."""

        if index >= len(self.steps):
            self.destroy()
            return

        self.current_step_index = index
        step = self.steps[index]

        self._anchor_to_master()
        self.master.update_idletasks()
        try:
            target = step.target_resolver()
        except Exception as e:
            print(f"DEBUG: Error resolving tutorial target: {e}")
            target = None

        try:
            target_exists = target and target.winfo_exists()
        except (AttributeError, tk.TclError):
            target_exists = False
            
        if target is None or not target or not target_exists:
            # Reason: Fallback ensures the tutorial does not crash if a widget is missing.
            self._render_message_only(
                "Tutorial paused",
                "Unable to locate the UI element for this step. Close the overlay and try again.",
            )
            return

        bbox = self._get_widget_bounds(target, padding=step.highlight_padding)
        if bbox is None:
            self._render_message_only(
                "Tutorial paused",
                "Unable to compute the position of the highlighted element.",
            )
            return

        self.canvas.delete("all")
        self._clear_highlight_animation()
        self._last_bbox = bbox

        # Create spotlight effect with a true transparent hole.
        # We rely on -transparentcolor so the canvas background shows through.
        # Draw four dimming rectangles around the clear area.

        spotlight_padding = 12
        clear_bbox = (
            max(0, bbox[0] - spotlight_padding),
            max(0, bbox[1] - spotlight_padding),
            min(self.winfo_width(), bbox[2] + spotlight_padding),
            min(self.winfo_height(), bbox[3] + spotlight_padding)
        )

        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        dim_color = "#000000"
        dim_stipple = "gray50"  # Adjust density to taste

        # Top dimming band
        if clear_bbox[1] > 0:
            self.canvas.create_rectangle(
                0, 0, canvas_width, clear_bbox[1],
                fill=dim_color, outline="", stipple=dim_stipple
            )

        # Bottom dimming band
        if clear_bbox[3] < canvas_height:
            self.canvas.create_rectangle(
                0, clear_bbox[3], canvas_width, canvas_height,
                fill=dim_color, outline="", stipple=dim_stipple
            )

        # Left dimming band
        if clear_bbox[0] > 0:
            self.canvas.create_rectangle(
                0, clear_bbox[1], clear_bbox[0], clear_bbox[3],
                fill=dim_color, outline="", stipple=dim_stipple
            )

        # Right dimming band
        if clear_bbox[2] < canvas_width:
            self.canvas.create_rectangle(
                clear_bbox[2], clear_bbox[1], canvas_width, clear_bbox[3],
                fill=dim_color, outline="", stipple=dim_stipple
            )

        # Highlight the focused area with orange outline
        self.highlight_id = self.canvas.create_rectangle(
            bbox[0],
            bbox[1],
            bbox[2],
            bbox[3],
            outline=COLORS["accent_orange"],
            width=self.highlight_width,
            dash=(8, 6),
            fill=""
        )

        self._render_instruction_panel(step, bbox)
        self._start_highlight_animation()

    def _bind_scroll_listeners(self):
        """Bind scroll-related events to trigger quick redraws when user scrolls."""
        try:
            self.bind_all("<MouseWheel>", self._on_scroll_event, add=True)
            self.bind_all("<Shift-MouseWheel>", self._on_scroll_event, add=True)
            # Linux scroll events
            self.bind_all("<Button-4>", self._on_scroll_event, add=True)
            self.bind_all("<Button-5>", self._on_scroll_event, add=True)
        except Exception:
            pass

    def _unbind_scroll_listeners(self):
        """Unbind scroll listeners when overlay is closed."""
        try:
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Shift-MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")
        except Exception:
            pass

    def _on_scroll_event(self, _event=None):
        """Schedule a quick redraw following a scroll action."""
        try:
            if self._fast_redraw_job_id is not None:
                self.after_cancel(self._fast_redraw_job_id)
        except tk.TclError:
            self._fast_redraw_job_id = None
        self._fast_redraw_job_id = self.after(30, self._redraw_step)

    def _start_follow_target(self):
        """Periodically check target position and redraw if it moved."""
        def _tick():
            if not self.winfo_exists():
                return
            if 0 <= self.current_step_index < len(self.steps):
                try:
                    target = self.steps[self.current_step_index].target_resolver()
                    if target and target.winfo_exists():
                        bbox = self._get_widget_bounds(
                            target, padding=self.steps[self.current_step_index].highlight_padding
                        )
                        if bbox and bbox != self._last_bbox:
                            # Redraw current step to update highlight/arrow
                            self._show_step(self.current_step_index)
                except Exception:
                    pass
            try:
                self._follow_job_id = self.after(120, _tick)
            except tk.TclError:
                self._follow_job_id = None

        # Kick off the follow loop
        try:
            self._follow_job_id = self.after(120, _tick)
        except tk.TclError:
            self._follow_job_id = None

    def _render_message_only(self, title: str, description: str):
        """Render a centered message when a step cannot be displayed."""

        self.canvas.delete("all")
        
        # Error messages use the same dark background as the canvas
        
        self.canvas.create_text(
            self.winfo_width() // 2,
            self.winfo_height() // 2,
            text=f"{title}\n\n{description}",
            fill=COLORS["text_white"],
            font=FONTS()["heading"],
            width=self.winfo_width() - 160,
            justify="center",
        )

    def _render_instruction_panel(self, step: TutorialStep, bbox: Tuple[int, int, int, int]):
        """Render instruction bubble and connecting arrow for a step."""

        padding = 24
        bubble_width = min(self.winfo_width() - 2 * padding, 520)
        bubble_height = 160

        bubble_position = step.bubble_position.lower()

        if bubble_position == "top":
            bubble_x = (self.winfo_width() - bubble_width) // 2
            bubble_y = padding
        elif bubble_position == "left":
            bubble_x = padding
            bubble_y = max(padding, bbox[1] - bubble_height - 20)
        elif bubble_position == "right":
            bubble_x = self.winfo_width() - bubble_width - padding
            bubble_y = max(padding, bbox[1] - bubble_height - 20)
        else:  # bottom (default)
            bubble_x = (self.winfo_width() - bubble_width) // 2
            bubble_y = self.winfo_height() - bubble_height - padding

        bubble = self.canvas.create_rectangle(
            bubble_x,
            bubble_y,
            bubble_x + bubble_width,
            bubble_y + bubble_height,
            fill=COLORS["secondary_black"],
            outline=COLORS["accent_orange"],
            width=2,
        )

        text_padding = 18
        self.canvas.create_text(
            bubble_x + text_padding,
            bubble_y + text_padding,
            anchor="nw",
            text=f"{step.title}\n\n{step.description}\n\nClick anywhere to continue...",
            fill=COLORS["text_white"],
            font=FONTS()["body"],
            width=bubble_width - 2 * text_padding,
            justify="left",
        )

        target_center_x = (bbox[0] + bbox[2]) / 2
        target_center_y = (bbox[1] + bbox[3]) / 2

        # Calculate the closest edge point of the bubble to the target
        bubble_center_x = bubble_x + bubble_width / 2
        bubble_center_y = bubble_y + bubble_height / 2
        
        # Determine which edge of the bubble is closest to the target
        dx = target_center_x - bubble_center_x
        dy = target_center_y - bubble_center_y
        
        # Calculate edge point based on the direction to target
        if abs(dx) > abs(dy):
            # Target is more to the left or right
            if dx > 0:
                # Target is to the right, arrow starts from right edge
                arrow_start_x = bubble_x + bubble_width
                arrow_start_y = bubble_center_y
            else:
                # Target is to the left, arrow starts from left edge
                arrow_start_x = bubble_x
                arrow_start_y = bubble_center_y
        else:
            # Target is more above or below
            if dy > 0:
                # Target is below, arrow starts from bottom edge
                arrow_start_x = bubble_center_x
                arrow_start_y = bubble_y + bubble_height
            else:
                # Target is above, arrow starts from top edge
                arrow_start_x = bubble_center_x
                arrow_start_y = bubble_y

        self.arrow_id = self.canvas.create_line(
            arrow_start_x,
            arrow_start_y,
            target_center_x,
            target_center_y,
            fill=COLORS["accent_orange"],
            width=3,
            arrow=tk.LAST,
            smooth=True,
        )

        # Place step counter badge at the bubble corner for orientation
        badge_radius = 18
        badge_x = bubble_x + bubble_width - badge_radius - 12
        badge_y = bubble_y + badge_radius + 12
        self.canvas.create_oval(
            badge_x - badge_radius,
            badge_y - badge_radius,
            badge_x + badge_radius,
            badge_y + badge_radius,
            fill=COLORS["accent_orange"],
            outline="",
        )
        self.canvas.create_text(
            badge_x,
            badge_y,
            text=str(self.current_step_index + 1),
            fill=COLORS["text_white"],
            font=FONTS()["heading"],
        )

    def _get_widget_bounds(self, widget: tk.Widget, padding: int) -> Optional[Tuple[int, int, int, int]]:
        """Get widget bounds relative to the overlay window."""

        if not widget.winfo_ismapped():
            widget.update_idletasks()

        try:
            widget_x = widget.winfo_rootx()
            widget_y = widget.winfo_rooty()
            widget_width = widget.winfo_width()
            widget_height = widget.winfo_height()
        except tk.TclError:
            return None

        overlay_x = self.winfo_rootx()
        overlay_y = self.winfo_rooty()

        rel_x = widget_x - overlay_x
        rel_y = widget_y - overlay_y

        return (
            max(0, rel_x - padding),
            max(0, rel_y - padding),
            min(self.winfo_width(), rel_x + widget_width + padding),
            min(self.winfo_height(), rel_y + widget_height + padding),
        )

    def _start_highlight_animation(self):
        """Begin pulsing the highlight outline."""

        if self._animation_running:
            return
        
        self._clear_highlight_animation()
        self._animation_running = True
        self._animate_highlight()

    def _animate_highlight(self):
        """Pulse the highlight outline to create a subtle animation."""

        if not self._animation_running or not self.highlight_id or not self.canvas.winfo_exists():
            self._animation_running = False
            return

        # Reason: Pulsing the outline guides the user's gaze without being distracting.
        self.highlight_width += self.highlight_pulse_direction
        if self.highlight_width >= 8:
            self.highlight_pulse_direction = -1
        elif self.highlight_width <= 4:
            self.highlight_pulse_direction = 1

        try:
            self.canvas.itemconfigure(self.highlight_id, width=self.highlight_width)
        except tk.TclError:
            self._animation_running = False
            return

        if self._animation_running:
            self._highlight_job_id = self.after(140, self._animate_highlight)

    def _clear_highlight_animation(self):
        """Cancel any scheduled highlight animation callbacks."""

        self._animation_running = False
        if self._highlight_job_id is not None:
            try:
                self.after_cancel(self._highlight_job_id)
            except tk.TclError:
                pass
            self._highlight_job_id = None

    def _redraw_step(self):
        """Force a redraw when the overlay or master window changes size."""

        if self._in_redraw:
            return
        
        self._in_redraw = True
        try:
            if 0 <= self.current_step_index < len(self.steps):
                self._show_step(self.current_step_index)
        finally:
            self._in_redraw = False

    def destroy(self):
        """Ensure scheduled callbacks are cancelled before destroying the window."""

        self._clear_highlight_animation()
        # Cancel follow/fast redraw jobs and unbind listeners
        try:
            if self._follow_job_id is not None:
                self.after_cancel(self._follow_job_id)
        except tk.TclError:
            pass
        self._follow_job_id = None
        try:
            if self._fast_redraw_job_id is not None:
                self.after_cancel(self._fast_redraw_job_id)
        except tk.TclError:
            pass
        self._fast_redraw_job_id = None
        self._unbind_scroll_listeners()
        # Release grabs so the app becomes interactive again
        try:
            self.grab_release()
        except tk.TclError:
            pass
        super().destroy()


