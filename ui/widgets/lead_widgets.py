"""
Lead Display Widgets

This module contains widgets for displaying lead items with score editing and feedback functionality.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import re
import json
from typing import Callable, List, Optional

from ..styles import COLORS, FONTS, get_score_color
from ..feedback_manager import (
    FeedbackManager,
    FeedbackEntry,
    extract_chat_log_filename_from_session,
)
from .score_widgets import ScoreBlock
from .text_widgets import InlineEditableText
from .tutorial_overlay import FeedbackTutorialOverlay, TutorialStep
from scripts.clients.agents.scoring import (
    extract_recommendation_from_response,
    extract_title_from_response,
    extract_jurisdiction_from_response
)


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
            corner_radius=15,
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
        # Main content frame with neutral professional styling
        main_frame = ctk.CTkFrame(
            self, 
            fg_color=COLORS["secondary_black"],
            corner_radius=12,
            border_color=COLORS["border_gray"],
            border_width=1
        )
        # Reduce left-right padding so the score block sits close to the card edge
        main_frame.grid(row=0, column=0, sticky="ew", padx=(5, 15), pady=15)
        # Make left metadata column narrower so it doesn't push content rightwards
        main_frame.grid_columnconfigure(0, minsize=140)
        main_frame.grid_columnconfigure(1, weight=1)

        # Score block (editable) - display corrected score but use original for editing baseline
        display_score = self.lead.get("score", 0)  # Use .get() for safety
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
        # Tighten left padding so the score sits near the card's left edge
        self.score_block.grid(row=0, column=0, padx=(8, 20), pady=(20, 10), sticky="n")

        # Metadata section - compact vertical display under score block
        analysis_text = self.lead.get("analysis", "")
        jurisdiction = extract_jurisdiction_from_response(analysis_text)
        jurisdiction_text = jurisdiction if jurisdiction else "Jurisdiction not found"
        timestamp_text = self.lead.get('timestamp', 'Timestamp unavailable')
        
        # Metadata section (bullet-style inline rows: icon + text)
        metadata_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        # Tighten horizontal padding so metadata hugs the score block
        metadata_frame.grid(row=1, column=0, padx=(10, 10), pady=(0, 8), sticky="new")
        metadata_frame.grid_columnconfigure(0, weight=1)

        # Jurisdiction line (icon + text)
        jurisdiction_item = ctk.CTkFrame(metadata_frame, fg_color="transparent")
        jurisdiction_item.grid(row=0, column=0, sticky="new", pady=(0, 2))
        jurisdiction_item.grid_columnconfigure(1, weight=1)

        jurisdiction_icon = ctk.CTkLabel(
            jurisdiction_item,
            text="🧭",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["accent_orange"],
            width=20,
            anchor="center"
        )
        jurisdiction_icon.grid(row=0, column=0, sticky="w")

        jurisdiction_text_label = ctk.CTkLabel(
            jurisdiction_item,
            text=jurisdiction_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_gray"],
            anchor="nw",
            justify="left",
            width=140,  # Narrower to reduce left column width
            wraplength=140  # Match width for consistent wrapping
        )
        jurisdiction_text_label.grid(row=0, column=1, sticky="nw", padx=(6, 0))

        # Timestamp line (icon + text)
        timestamp_item = ctk.CTkFrame(metadata_frame, fg_color="transparent")
        timestamp_item.grid(row=1, column=0, sticky="new", pady=(2, 0))
        timestamp_item.grid_columnconfigure(1, weight=1)

        timestamp_icon = ctk.CTkLabel(
            timestamp_item,
            text="📅",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["accent_orange"],
            width=20,
            anchor="center"
        )
        timestamp_icon.grid(row=0, column=0, sticky="w")

        timestamp_text_label = ctk.CTkLabel(
            timestamp_item,
            text=timestamp_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_gray"],
            anchor="nw",
            justify="left",
            width=140,  # Narrower to reduce left column width
            wraplength=140  # Match width for consistent wrapping
        )
        timestamp_text_label.grid(row=0, column=1, sticky="nw", padx=(6, 0))

        # Discuss Lead button - positioned below timestamp in metadata column
        discuss_lead_item = ctk.CTkFrame(metadata_frame, fg_color="transparent")
        discuss_lead_item.grid(row=2, column=0, sticky="new", pady=(8, 0))
        discuss_lead_item.grid_columnconfigure(1, weight=1)

        discuss_lead_icon = ctk.CTkLabel(
            discuss_lead_item,
            text="💬",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["accent_orange"],
            width=20,
            anchor="center"
        )
        discuss_lead_icon.grid(row=0, column=0, sticky="w")

        self.discuss_lead_btn = ctk.CTkButton(
            discuss_lead_item,
            text="Discuss Lead",
            width=120,
            height=25,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.discuss_lead,
            corner_radius=12
        )
        self.discuss_lead_btn.grid(row=0, column=1, sticky="w", padx=(6, 0))

        # Content frame with improved padding - spans all rows
        content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        # Bring content closer to the score/metadata by removing extra left padding
        content_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 15), pady=20)
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

        # Title section
        recommendation = extract_recommendation_from_response(analysis_text)
        lead_title = extract_title_from_response(analysis_text)
        
        # Title section with professional styling
        title_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        title_frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        title_frame.grid_columnconfigure(1, weight=1)
        
        # Title icon/indicator
        title_icon = ctk.CTkLabel(
            title_frame,
            text="⚖️",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"],
            width=30
        )
        title_icon.grid(row=0, column=0, sticky="w", padx=(0, 8))
        
        # Title text
        title_label = ctk.CTkLabel(
            title_frame,
            text=lead_title,
            font=FONTS()["subheading"],
            text_color=COLORS["text_white"],
            anchor="w",
            justify="left"
        )
        title_label.grid(row=0, column=1, sticky="ew")
        row += 1
        
        # Recommendation (displayed below title) - using textbox for proper wrapping
        recommendation_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        recommendation_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        recommendation_frame.grid_columnconfigure(0, weight=1)
        
        # Recommendation header
        rec_header = ctk.CTkLabel(
            recommendation_frame,
            text="📋 Recommendation:",
            font=FONTS()["small"],
            text_color=COLORS["accent_orange"],
            anchor="w"
        )
        rec_header.grid(row=0, column=0, sticky="w", pady=(0, 3))
        
        # Recommendation text using textbox for proper wrapping with professional styling
        recommendation_textbox = ctk.CTkTextbox(
            recommendation_frame,
            height=100,  # Increased height since we have more space now
            font=FONTS()["body"],
            fg_color=COLORS["primary_black"],
            text_color=COLORS["text_white"],
            border_color=COLORS["accent_orange"],
            border_width=1,
            wrap="word",
            corner_radius=8,
        )
        recommendation_textbox.grid(row=1, column=0, sticky="ew", pady=(0, 0))
        recommendation_textbox.insert("1.0", recommendation)
        recommendation_textbox.configure(state="disabled")  # Read-only
        row += 1

        # Key Indicators section
        indicators_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["secondary_black"], corner_radius=8)
        indicators_frame.grid(row=row, column=0, sticky="ew", pady=(5, 15))
        indicators_frame.grid_columnconfigure(0, weight=1)
        
        # Create indicators list
        self._create_lead_indicators(indicators_frame)
        row += 1

        # Buttons frame with equal column distribution - spans full width of lead item
        self.button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 20))

        has_chat_history = not self.lead.get("is_example", False) and self.current_chat_log

        # Build the list of primary buttons before gridding so we can size the columns evenly
        button_list = []

        self.view_analysis_btn = ctk.CTkButton(
            self.button_frame,
            text="📊 View AI Analysis",
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self.toggle_analysis,
        )
        button_list.append(self.view_analysis_btn)

        self.view_description_btn = ctk.CTkButton(
            self.button_frame,
            text="📋 View Original Description",
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            border_color=COLORS["border_gray"],
            border_width=2,
            font=FONTS()["small_button"],
            command=self.toggle_description,
        )
        button_list.append(self.view_description_btn)

        # View Chat History button - only for non-example leads with valid chat log
        if has_chat_history:
            self.view_chat_history_btn = ctk.CTkButton(
                self.button_frame,
                text="💬 View Chat History",
                fg_color=COLORS["tertiary_black"],
                hover_color=COLORS["border_gray"],
                border_color=COLORS["border_gray"],
                border_width=2,
                font=FONTS()["small_button"],
                command=self.view_chat_history,
            )
            button_list.append(self.view_chat_history_btn)
        else:
            self.view_chat_history_btn = None

        # Removed in favor of global Start Tutorial button in the title bar
        self.start_tutorial_btn = None

        # Grid the buttons with even spacing
        self.num_buttons = len(button_list)
        for index, button in enumerate(button_list):
            if self.num_buttons == 1:
                padx = (0, 0)
            elif index == 0:
                padx = (0, 5)
            elif index == self.num_buttons - 1:
                padx = (5, 0)
            else:
                padx = 5
            button.grid(row=0, column=index, sticky="ew", padx=padx)

        for col in range(self.num_buttons):
            self.button_frame.grid_columnconfigure(col, weight=1, uniform="button_group")
        # Configure column for save feedback button (smaller weight)
        self.button_frame.grid_columnconfigure(self.num_buttons, weight=0)

        # Save feedback button (initially hidden) - include test feedback button for examples
        feedback_button_text = (
            "💾 SAVE FEEDBACK (TEST)"
            if self.lead.get("is_example", False)
            else "💾 SAVE FEEDBACK"
        )
        self.save_feedback_btn = ctk.CTkButton(
            self.button_frame,
            text=feedback_button_text,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self._save_feedback,
        )
        # Don't grid initially - will be shown when feedback exists

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
        self.description_textbox.insert("1.0", self.lead.get("description", "No description available."))
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

    # ─── LEAD INDICATORS SYSTEM ────────────────────────────────────────────────
    
    def _create_lead_indicators(self, parent_frame):
        """
        Create a bulleted list of key indicators for the lead with visual symbols.
        
        This system is easily modifiable - add new indicators by extending the
        get_lead_indicators() method.
        """
        # Header for indicators section
        header_label = ctk.CTkLabel(
            parent_frame,
            text="📊 Key Indicators",
            font=FONTS()["small"],
            text_color=COLORS["accent_orange"],
            anchor="w"
        )
        header_label.grid(row=0, column=0, sticky="w", padx=15, pady=(10, 5))
        
        # Get indicators data
        indicators = self._get_lead_indicators()
        
        # Create scrollable frame for indicators if there are many
        indicators_container = ctk.CTkFrame(parent_frame, fg_color="transparent")
        indicators_container.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        indicators_container.grid_columnconfigure(0, weight=1)
        
        # Display each indicator
        for i, indicator in enumerate(indicators):
            self._create_indicator_item(indicators_container, indicator, i)
    
    def _get_lead_indicators(self):
        """
        Get indicators for this lead. Uses pre-generated indicators if available,
        otherwise falls back to confidence-based indicators.
        
        Returns:
            List[Dict]: List of indicator dictionaries with 'type', 'symbol', 'text', 'color' keys.
        """
        # Check if we have pre-generated indicators
        pre_generated_indicators = self.lead.get("indicators", [])
        if pre_generated_indicators:
            # Use pre-generated indicators - they're already in the correct format
            return pre_generated_indicators
        
        # Fallback to confidence-based indicator when no pre-generated indicators exist
        return self._get_fallback_confidence_indicator()
    
    def _get_fallback_confidence_indicator(self):
        """Fallback indicator based on confidence score when AI agent fails."""
        indicators = []
        confidence = self.lead.get("confidence", 0)
        
        if confidence >= 70:
            indicators.append({
                'type': 'positive',
                'symbol': '▲',
                'text': f'High Confidence Score ({confidence}%)',
                'color': '#4CAF50',  # Green
                'weight': 70
            })
        elif confidence >= 50:
            indicators.append({
                'type': 'neutral', 
                'symbol': '●',
                'text': f'Moderate Confidence ({confidence}%)',
                'color': '#FF9800',  # Orange
                'weight': 50
            })
        else:
            indicators.append({
                'type': 'negative',
                'symbol': '▼',
                'text': f'Low Confidence Score ({confidence}%)',
                'color': '#F44336',  # Red
                'weight': 40
            })
        
        return indicators
    
    def _convert_tooltip_to_indicator(self, tooltip):
        """
        Convert a tooltip from the AI agent to our indicator format.
        
        Args:
            tooltip (dict): Tooltip dictionary with icon, text, category, weight keys.
            
        Returns:
            dict: Indicator dictionary with type, symbol, text, color, weight keys.
        """
        try:
            icon = tooltip.get("icon", "neutral")
            text = tooltip.get("text", "")
            weight = tooltip.get("weight", 50)
            
            # Map AI agent icons to our symbols and colors
            if icon == "up":
                return {
                    'type': 'positive',
                    'symbol': '▲',
                    'text': text,
                    'color': '#4CAF50',  # Green
                    'weight': weight
                }
            elif icon == "down":
                return {
                    'type': 'negative',
                    'symbol': '▼',
                    'text': text,
                    'color': '#F44336',  # Red
                    'weight': weight
                }
            else:  # neutral
                return {
                    'type': 'neutral',
                    'symbol': '●',
                    'text': text,
                    'color': '#FF9800',  # Orange
                    'weight': weight
                }
        except Exception as e:
            print(f"Error converting tooltip to indicator: {e}")
            return None
    
    def _create_indicator_item(self, parent, indicator, row):
        """Create a single indicator item with symbol and text."""
        item_frame = ctk.CTkFrame(parent, fg_color="transparent")
        item_frame.grid(row=row, column=0, sticky="ew", pady=1)
        item_frame.grid_columnconfigure(1, weight=1)
        
        # Symbol
        symbol_label = ctk.CTkLabel(
            item_frame,
            text=indicator['symbol'],
            font=FONTS()["body"],
            text_color=indicator['color'],
            width=20
        )
        symbol_label.grid(row=0, column=0, sticky="w", padx=(5, 8))
        
        # Text
        text_label = ctk.CTkLabel(
            item_frame,
            text=indicator['text'],
            font=FONTS()["small"],
            text_color=COLORS["text_white"],
            anchor="w",
            justify="left"
        )
        text_label.grid(row=0, column=1, sticky="ew")

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
                # Show the save button in the column after the last main button
                self.save_feedback_btn.grid(row=0, column=self.num_buttons, sticky="ew", padx=(10, 0))
            else:
                # Hide the save button
                self.save_feedback_btn.grid_remove()

    def _start_feedback_tutorial(self, on_complete_callback=None):
        """Launch the feedback tutorial overlay on demand for the example lead."""

        if not self.lead.get("is_example", False):
            return

        main_window = self.winfo_toplevel()

        # Avoid creating multiple overlays if one is already running
        active_overlay = getattr(main_window, "_active_feedback_tutorial", None)
        if active_overlay is not None:
            return

        steps = self._build_feedback_tutorial_steps(main_window)
        if not steps:
            return

        overlay = FeedbackTutorialOverlay(main_window, steps, on_complete_callback)

        def _start_overlay():
            try:
                overlay.start()
            finally:
                # Reason: Release reference once the overlay is active to avoid leaks.
                setattr(main_window, "_active_feedback_tutorial", None)

        # Reason: Persist the reference so the overlay survives until the callback fires.
        main_window._active_feedback_tutorial = overlay
        main_window.after(350, _start_overlay)

    def _build_feedback_tutorial_steps(self, main_window) -> List[TutorialStep]:
        """Create the ordered steps for the feedback tutorial overlay.

        Args:
            main_window: The top-level window hosting the lead widgets.

        Returns:
            List[TutorialStep]: Step configurations for the overlay.
        """

        # Capture reference to this specific example lead to ensure tutorial
        # always points to the correct widgets regardless of lead ordering
        example_lead_widget = self
        
        steps: List[TutorialStep] = []

        def _view_analysis_target():
            # Ensure we're targeting the correct example lead
            if not example_lead_widget.lead.get("is_example", False):
                print("DEBUG: Tutorial targeting non-example lead - this shouldn't happen")
                return None
            return getattr(example_lead_widget, "view_analysis_btn", None)

        steps.append(
            TutorialStep(
                title="Step 1: Open AI Analysis",
                description="Click the \"📊 View AI Analysis\" button to review the full write-up.",
                target_resolver=_view_analysis_target,
                bubble_position="bottom",
            )
        )

        def _analysis_target():
            # Ensure we're targeting the correct example lead
            if not example_lead_widget.lead.get("is_example", False):
                print("DEBUG: Tutorial targeting non-example lead - this shouldn't happen")
                return None
            # Ensure the analysis section is visible so it can be highlighted
            try:
                example_lead_widget.show_analysis()
                return getattr(example_lead_widget, "analysis_textbox", None)
            except Exception as e:
                print(f"DEBUG: Error showing analysis for tutorial: {e}")
                return None

        steps.append(
            TutorialStep(
                title="Step 2: View The Analysis Text",
                description=(
                    "This is the AI's detailed analysis that you can edit. "
                    "The text appears with orange headings and detailed explanations."
                ),
                target_resolver=_analysis_target,
                bubble_position="right",
            )
        )

        def _text_selection_target():
            # Target the analysis textbox again but with different instructions
            if not example_lead_widget.lead.get("is_example", False):
                return None
            try:
                # Ensure analysis is still visible
                if not example_lead_widget.analysis_expanded:
                    example_lead_widget.show_analysis()
                return getattr(example_lead_widget, "analysis_textbox", None)
            except Exception as e:
                print(f"DEBUG: Error getting analysis for text selection tutorial: {e}")
                return None

        steps.append(
            TutorialStep(
                title="Step 3: Select Text To Edit",
                description=(
                    "To edit any part of the analysis:\n"
                    "1. Click and drag to highlight the sentence you want to change\n"
                    "2. Right-click the selected text\n" 
                    "3. Choose \"✏️ Edit Selected Text\" from the menu\n"
                    "4. Make your changes in the dialog that appears"
                ),
                target_resolver=_text_selection_target,
                bubble_position="right",
            )
        )

        def _score_target():
            # Ensure we're targeting the correct example lead
            if not example_lead_widget.lead.get("is_example", False):
                print("DEBUG: Tutorial targeting non-example lead - this shouldn't happen")
                return None
            
            score_block = getattr(example_lead_widget, "score_block", None)
            if score_block and hasattr(score_block, "score_label"):
                return score_block.score_label
            return score_block

        steps.append(
            TutorialStep(
                title="Step 4: Adjust The Score",
                description="Click the numeric score badge to enter an updated value (0-100).",
                target_resolver=_score_target,
                bubble_position="top",
            )
        )

        def _save_target():
            # Ensure we're targeting the correct example lead
            if not example_lead_widget.lead.get("is_example", False):
                print("DEBUG: Tutorial targeting non-example lead - this shouldn't happen")
                return None
            
            button = getattr(example_lead_widget, "save_feedback_btn", None)
            if button and hasattr(button, 'winfo_manager'):
                try:
                    if button.winfo_manager():
                        return button
                except:
                    pass
            # Reason: Highlight the button row when the save button has not appeared yet.
            return getattr(example_lead_widget, "button_frame", None)

        steps.append(
            TutorialStep(
                title="Step 5: Save Your Changes",
                description=(
                    "Press \"💾 SAVE FEEDBACK (TEST)\" once edits or score updates look good. "
                    "The button appears after you make changes."
                ),
                target_resolver=_save_target,
                bubble_position="top",
            )
        )

        steps.append(
            TutorialStep(
                title="Step 6: Continue To New Leads",
                description=(
                    "When you're done with this example, return to the left panel to score real leads."
                ),
                target_resolver=lambda: getattr(main_window, "score_button", None),
                bubble_position="bottom",
            )
        )

        return steps

    def view_chat_history(self):
        """Open the chat history dialog for this lead."""
        if not self.current_chat_log:
            messagebox.showwarning("No Chat History", "No chat log file available for this lead.")
            return

        try:
            # Import the dialog class
            from ..dialogs import ChatHistoryDialog
            
            # Open the chat history dialog
            dialog = ChatHistoryDialog(self.winfo_toplevel(), self.current_chat_log)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open chat history: {str(e)}")

    def discuss_lead(self):
        """Open the discuss lead chat panel for this lead."""
        try:
            # Get the main window instance
            main_window = self.winfo_toplevel()
            
            # Check if main window has the open_chat_for_lead method
            if hasattr(main_window, 'open_chat_for_lead'):
                main_window.open_chat_for_lead(self.lead)
            else:
                messagebox.showerror("Error", "Chat functionality not available in this window.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open chat for lead: {str(e)}")