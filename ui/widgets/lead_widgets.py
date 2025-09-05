"""
Lead Display Widgets

This module contains widgets for displaying lead items with score editing and feedback functionality.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import re

from ..styles import COLORS, FONTS, get_score_color
from ..feedback_manager import (
    FeedbackManager,
    FeedbackEntry,
    extract_chat_log_filename_from_session,
)
from .score_widgets import ScoreBlock
from .text_widgets import InlineEditableText


# ─── LEAD ITEM WIDGET ───────────────────────────────────────────────────────────
class LeadItem(ctk.CTkFrame):
    """Widget for displaying a single lead item with score and buttons that expand inline sections."""

    def __init__(
        self, parent, lead: dict, lead_index: int = 0, feedback_manager=None, **kwargs
    ):
        confidence_color = get_score_color(lead.get("confidence", 50))

        super().__init__(
            parent,
            fg_color=COLORS["tertiary_black"],
            border_color=confidence_color,
            border_width=3,
            **kwargs,
        )

        self.lead = lead
        self.lead_index = lead_index
        self.grid_columnconfigure(0, weight=1)
        self.analysis_expanded = False
        self.description_expanded = False

        # Feedback management - only for non-example leads
        self.feedback_manager = (
            feedback_manager if feedback_manager is not None else FeedbackManager()
        )
        self.feedback_entry = None
        print(
            f"DEBUG: LeadItem {lead_index} using FeedbackManager instance: {id(self.feedback_manager)}"
        )

        # Associate chat logs - real leads get their actual chat log, examples get fake test chat log
        if lead.get("is_example", False):
            self.current_chat_log = lead.get(
                "chat_log_filename", "example_test_chat_log_fake.json"
            )  # Fake chat log for testing
        else:
            # For real leads, use the specific chat log if available, otherwise get most recent
            self.current_chat_log = (
                lead.get("chat_log_filename")
                or extract_chat_log_filename_from_session()
            )

        # Debug output to help diagnose the issue
        print(
            f"DEBUG: LeadItem #{lead_index} - is_example: {lead.get('is_example', False)}, current_chat_log: {self.current_chat_log}"
        )

        # Register existing feedback file if available
        existing_feedback_filename = lead.get("_existing_feedback_filename")
        if existing_feedback_filename and self.current_chat_log:
            key = f"{self.current_chat_log}_{lead_index}"
            self.feedback_manager.saved_feedback_files[key] = existing_feedback_filename
            print(
                f"DEBUG: Registered existing feedback file for {key}: {existing_feedback_filename}"
            )

        self.setup_widgets()

    def setup_widgets(self):
        """Set up the lead item widgets."""
        # Main content frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        main_frame.grid_columnconfigure(1, weight=1)

        # Score block (editable) - display corrected score but use original for editing baseline
        display_score = self.lead["score"]  # This is the corrected score
        original_score_for_editing = display_score  # Default to same value

        # If this lead has feedback, get the original AI score for the edit dialog
        scored_lead_data = self.lead.get("_scored_lead_data")
        if (
            scored_lead_data
            and hasattr(scored_lead_data, "feedback_changes")
            and scored_lead_data.feedback_changes
        ):
            from scripts.clients.agents.scoring import extract_score_from_response

            original_score_for_editing = extract_score_from_response(
                scored_lead_data.detailed_rationale
            )
            if original_score_for_editing <= 0:
                original_score_for_editing = display_score  # Fallback

        self.score_block = ScoreBlock(
            main_frame,
            display_score,
            editable=True,
            on_score_change=self._on_score_change,
        )
        # Set the original score for the edit dialog
        self.score_block.original_score = original_score_for_editing
        self.score_block.grid(row=0, column=0, padx=(0, 15), pady=0, sticky="n")

        # Content frame
        content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        content_frame.grid(row=0, column=1, sticky="ew")
        content_frame.grid_columnconfigure(0, weight=1)

        row = 0

        # Warning label for example leads
        if self.lead.get("is_example", False):
            warning_label = ctk.CTkLabel(
                content_frame,
                text="⚠️ EXAMPLE LEAD - This is an already completed example lead.",
                font=ctk.CTkFont(family="Inter", size=12, weight="bold"),
                text_color=COLORS["accent_orange_light"],
                fg_color=COLORS["secondary_black"],
                corner_radius=5,
            )
            warning_label.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            row += 1

        # Title
        title_text = f"Score: {self.lead['score']}/100 | Confidence: {self.lead.get('confidence', 50)}/100 - {self.lead['timestamp']}"
        title_label = ctk.CTkLabel(
            content_frame,
            text=title_text,
            font=FONTS()["subheading"],
            text_color=COLORS["text_white"],
            anchor="w",
        )
        title_label.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        # Buttons frame
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.grid(row=row, column=0, sticky="ew")

        self.view_analysis_btn = ctk.CTkButton(
            button_frame,
            text="📊 View AI Analysis",
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self.toggle_analysis,
        )
        self.view_analysis_btn.pack(side="left", padx=(0, 10))

        self.view_description_btn = ctk.CTkButton(
            button_frame,
            text="📋 View Original Description",
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            border_color=COLORS["border_gray"],
            border_width=2,
            font=FONTS()["small_button"],
            command=self.toggle_description,
        )
        self.view_description_btn.pack(side="left")

        # Save feedback button (initially hidden) - include test feedback button for examples
        feedback_button_text = (
            "💾 SAVE FEEDBACK (TEST)"
            if self.lead.get("is_example", False)
            else "💾 SAVE FEEDBACK"
        )
        self.save_feedback_btn = ctk.CTkButton(
            button_frame,
            text=feedback_button_text,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self._save_feedback,
        )
        # Don't pack initially - will be shown when feedback exists

        # Expandable sections frame (initially hidden)
        self.sections_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sections_frame.grid_columnconfigure(0, weight=1)

        # AI Analysis expandable section
        self.analysis_section = ctk.CTkFrame(
            self.sections_frame,
            fg_color=COLORS["secondary_black"],
            border_color=COLORS["accent_orange"],
            border_width=2,
        )

        # Add analysis content header
        analysis_label = ctk.CTkLabel(
            self.analysis_section,
            text="📊 AI Analysis & Recommendation",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"],
        )
        analysis_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        # Create custom text widget with editing capabilities (auto-sizing)
        self.analysis_textbox = InlineEditableText(
            self.analysis_section,
            font=FONTS()["small"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            wrap="word",
            on_text_edit=self._on_text_edited,
        )
        self.analysis_textbox.grid(
            row=1, column=0, sticky="nsew", padx=15, pady=(0, 15)
        )
        # Use edited analysis if available so content matches post-edit state
        initial_analysis_text = self.lead.get("_edited_analysis") or self.lead.get(
            "analysis", ""
        )
        # Keep baseline in lead dict consistent with visible text for subsequent edits
        self.lead["analysis"] = initial_analysis_text
        self.analysis_textbox.set_text(initial_analysis_text)
        # Re-apply saved feedback highlights if available
        self._apply_feedback_highlights_if_any()
        self.analysis_section.grid_columnconfigure(0, weight=1)
        self.analysis_section.grid_rowconfigure(1, weight=1)

        # Original Description expandable section
        self.description_section = ctk.CTkFrame(
            self.sections_frame,
            fg_color=COLORS["secondary_black"],
            border_color=COLORS["accent_orange"],
            border_width=2,
        )

        # Add description content
        description_label = ctk.CTkLabel(
            self.description_section,
            text="📋 Original Lead Description",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"],
        )
        description_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        self.description_textbox = ctk.CTkTextbox(
            self.description_section,
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["border_gray"],
            border_width=1,
            wrap="word",
            height=150,
        )
        self.description_textbox.grid(
            row=1, column=0, sticky="nsew", padx=15, pady=(0, 15)
        )
        self.description_textbox.insert("1.0", self.lead["description"])
        self.description_textbox.configure(state="disabled")

        # Prevent scroll event propagation to parent to avoid scroll conflicts
        self._bind_description_scroll_events()

        self.description_section.grid_columnconfigure(0, weight=1)
        self.description_section.grid_rowconfigure(1, weight=1)

    def toggle_analysis(self):
        """Toggle the AI analysis section."""
        if self.analysis_expanded:
            self.hide_analysis()
        else:
            self.show_analysis()

    def show_analysis(self):
        """Show the AI analysis section."""
        if not self.analysis_expanded:
            # Show sections frame if not already shown
            if not self.description_expanded:
                self.sections_frame.grid(
                    row=1, column=0, sticky="ew", padx=15, pady=(0, 15)
                )

            # Show analysis section
            row = 0 if not self.description_expanded else 1
            self.analysis_section.grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(0, 5) if self.description_expanded else (0, 0),
            )

            self.analysis_expanded = True
            self.view_analysis_btn.configure(text="📊 Hide AI Analysis")

    def hide_analysis(self):
        """Hide the AI analysis section."""
        if self.analysis_expanded:
            self.analysis_section.grid_remove()
            self.analysis_expanded = False
            self.view_analysis_btn.configure(text="📊 View AI Analysis")

            # Hide sections frame if nothing is expanded
            if not self.description_expanded:
                self.sections_frame.grid_remove()

    def toggle_description(self):
        """Toggle the original description section."""
        if self.description_expanded:
            self.hide_description()
        else:
            self.show_description()

    def show_description(self):
        """Show the original description section."""
        if not self.description_expanded:
            # Show sections frame if not already shown
            if not self.analysis_expanded:
                self.sections_frame.grid(
                    row=1, column=0, sticky="ew", padx=15, pady=(0, 15)
                )

            # Show description section
            row = 1 if self.analysis_expanded else 0
            self.description_section.grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(5, 0) if self.analysis_expanded else (0, 0),
            )

            self.description_expanded = True
            self.view_description_btn.configure(text="📋 Hide Original Description")

    def hide_description(self):
        """Hide the original description section."""
        if self.description_expanded:
            self.description_section.grid_remove()
            self.description_expanded = False
            self.view_description_btn.configure(text="📋 View Original Description")

            # Hide sections frame if nothing is expanded
            if not self.analysis_expanded:
                self.sections_frame.grid_remove()

    def _bind_description_scroll_events(self):
        """Bind scroll event handlers to the description textbox to prevent conflicts."""
        try:
            # Get the underlying tkinter Text widget from CTkTextbox
            text_widget = self.description_textbox._textbox

            # Bind scroll events to prevent propagation
            text_widget.bind("<MouseWheel>", self._on_description_mousewheel)
            text_widget.bind("<Button-4>", self._on_description_mousewheel)
            text_widget.bind("<Button-5>", self._on_description_mousewheel)
        except AttributeError:
            # Fallback if CTkTextbox structure changes
            self.description_textbox.bind(
                "<MouseWheel>", self._on_description_mousewheel
            )
            self.description_textbox.bind("<Button-4>", self._on_description_mousewheel)
            self.description_textbox.bind("<Button-5>", self._on_description_mousewheel)

    def _on_description_mousewheel(self, event):
        """Handle mousewheel events for the description textbox."""
        try:
            # Check if the description textbox needs scrolling
            text_widget = getattr(
                self.description_textbox, "_textbox", self.description_textbox
            )

            # Check if content exceeds visible area
            total_lines = float(text_widget.index("end-1c").split(".")[0])
            textbox_height = self.description_textbox.winfo_height()
            line_height = (
                text_widget.dlineinfo("1.0")[3] if text_widget.dlineinfo("1.0") else 14
            )
            visible_lines = textbox_height / line_height

            if total_lines > visible_lines:
                # Content needs scrolling - handle it within this textbox
                if hasattr(event, "delta") and event.delta:
                    # Windows and MacOS
                    text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
                elif hasattr(event, "num"):
                    if event.num == 4:
                        # Linux scroll up
                        text_widget.yview_scroll(-1, "units")
                    elif event.num == 5:
                        # Linux scroll down
                        text_widget.yview_scroll(1, "units")
                # Consume the event to prevent propagation to parent
                return "break"
            else:
                # Let the parent handle scrolling if this widget doesn't need to scroll
                pass
        except Exception:
            # If anything goes wrong, let the parent handle scrolling
            pass

    # ─── FEEDBACK HANDLING METHODS ─────────────────────────────────────────────

    def _on_score_change(self, original_score: int, new_score: int):
        """Handle score change from the editable score block."""
        if not self.current_chat_log:
            messagebox.showwarning(
                "No Chat Log",
                "Cannot save feedback: No chat log found for this session.",
            )
            return

        # Get or create feedback entry in memory
        feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
            self.current_chat_log, self.lead_index, self.lead["analysis"]
        )

        # Set score feedback (accumulates in memory)
        feedback_entry.set_score_feedback(original_score, new_score)

        # Update UI to show save button
        self._update_save_button_visibility()

        feedback_type = "TEST" if self.lead.get("is_example", False) else "REAL"
        print(
            f"Score feedback accumulated ({feedback_type}): {original_score} → {new_score}"
        )

    def _on_text_edited(
        self, original_text: str, new_text: str, start_pos: str, end_pos: str
    ):
        """Handle inline text editing from the custom text widget."""
        print(
            f"DEBUG: _on_text_edited called - current_chat_log: {self.current_chat_log}"
        )
        if not self.current_chat_log:
            print(f"DEBUG: No chat log found, showing warning")
            messagebox.showwarning(
                "No Chat Log",
                "Cannot save feedback: No chat log found for this session.",
            )
            return

        # Get or create feedback entry in memory
        feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
            self.current_chat_log, self.lead_index, self.lead["analysis"]
        )

        # Add text feedback with position information (accumulates in memory)
        position_info = f"AI Analysis Section (pos: {start_pos} to {end_pos})"
        feedback_entry.add_text_feedback(original_text, new_text, position_info)

        # Update UI to show save button
        self._update_save_button_visibility()

        feedback_type = "TEST" if self.lead.get("is_example", False) else "REAL"
        print(
            f"Text feedback accumulated ({feedback_type}): '{original_text}' → '{new_text}'"
        )

    def _save_feedback(self):
        """Save the accumulated feedback for this lead."""
        if not self.current_chat_log:
            messagebox.showwarning(
                "No Chat Log",
                "Cannot save feedback: No chat log found for this session.",
            )
            return

        # Get the current modified text from the analysis textbox
        current_analysis_text = self.analysis_textbox.get("1.0", "end-1c")

        # Update the feedback entry with the final replaced text
        feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
            self.current_chat_log, self.lead_index, self.lead["analysis"]
        )
        feedback_entry.set_replaced_analysis_text(current_analysis_text)

        if self.feedback_manager.save_feedback_for_lead(
            self.current_chat_log, self.lead_index
        ):
            messagebox.showinfo(
                "Feedback Saved",
                f"Feedback for Lead #{self.lead_index + 1} saved successfully!",
            )
            # Hide the save button after successful save
            self._update_save_button_visibility()
            # Reset the feedback entry for fresh changes after save
            self._reset_feedback_entry_after_save()
        else:
            messagebox.showerror("Error", "Failed to save feedback.")

    def _apply_feedback_highlights_if_any(self):
        """Apply orange highlight tags for previously saved feedback edits if present.

        Parses saved position info strings (e.g., "AI Analysis Section (pos: 3.7 to 3.25)")
        and re-applies the "edited" tag to the edited ranges. Also populates
        the InlineEditableText.edit_history so hover tooltips show original text.
        """
        try:
            # Prefer original AI analysis as base (already set), then overlay edits
            # Optionally could diff _edited_analysis to confirm, but we trust saved positions
            changes = self.lead.get("_feedback_text_changes") or []
            if not changes:
                return

            pos_regex = re.compile(r"pos:\s*([0-9]+\.[0-9]+)\s*to\s*([0-9]+\.[0-9]+)")

            for change in changes:
                position_info = change.get("position_info", "") or ""
                m = pos_regex.search(position_info)
                if not m:
                    continue
                start_pos, end_pos = m.group(1), m.group(2)

                # Apply highlight tag
                try:
                    self.analysis_textbox.tag_add("edited", start_pos, end_pos)
                except Exception:
                    continue

                # Populate edit history for hover tooltips
                original_text = change.get("selected_text", "") or ""
                new_text = change.get("replacement_text", "") or ""

                # Add to edit history for hover functionality - this recreates the edit record
                # Must match the structure expected by _on_mouse_motion
                edit_record = {
                    "start_pos": start_pos,
                    "end_pos": end_pos,  # Original end position
                    "new_end_pos": end_pos,  # Updated end position (same for reloaded)
                    "original_text": original_text,
                    "new_text": new_text,
                }
                self.analysis_textbox.edit_history.append(edit_record)
                
            # Re-apply color coding after loading feedback highlights
            from .text_widgets import parse_and_color_analysis_text
            current_text = self.analysis_textbox.get("1.0", "end-1c")
            parse_and_color_analysis_text(self.analysis_textbox, current_text)
        except Exception:
            # Best-effort; ignore failures silently to avoid breaking UI
            pass

    def _reset_feedback_entry_after_save(self):
        """Reset the feedback entry after saving to start fresh for new changes."""
        # Update the lead's analysis text to the current modified text as the new baseline
        current_analysis_text = self.analysis_textbox.get("1.0", "end-1c")
        self.lead["analysis"] = current_analysis_text

        # Clear the local feedback entry reference to start fresh
        self.feedback_entry = None
        # The next change will create a new feedback entry starting from the current state

    def _update_save_button_visibility(self):
        """Update the visibility of the save feedback button based on pending feedback."""
        if self.save_feedback_btn:
            if self.feedback_manager.has_pending_feedback(
                self.current_chat_log, self.lead_index
            ):
                # Show the save button
                self.save_feedback_btn.pack(side="left", padx=(10, 0))
            else:
                # Hide the save button
                self.save_feedback_btn.pack_forget()
