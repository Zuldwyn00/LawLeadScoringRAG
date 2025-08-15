"""
Custom UI Widgets

This module contains custom widget components for the Lead Scoring GUI application.
These widgets encapsulate common UI patterns and styling.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog
from .styles import COLORS, FONTS, get_score_color
import sys
import os

from .feedback_manager import FeedbackManager, FeedbackEntry, extract_chat_log_filename_from_session

# ─── PROGRESS DISPLAY WIDGET ────────────────────────────────────────────────────
class ProgressWidget:
    """Widget for displaying progress with status and timer updates."""
    
    def __init__(self, parent):
        self.parent = parent
        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["tertiary_black"])
        
        self.progress_bar = ctk.CTkProgressBar(
            self.frame,
            progress_color=COLORS["accent_orange"],
            fg_color=COLORS["border_gray"]
        )
        
        self.status_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"]
        )
        
        self.timer_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=FONTS()["small"],
            text_color=COLORS["text_gray"]
        )
        
        self.is_visible = False
        
    def show(self):
        """Show the progress widget."""
        if not self.is_visible:
            self.frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
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

# ─── SCORE BLOCK WIDGET ─────────────────────────────────────────────────────────
class ScoreBlock(ctk.CTkFrame):
    """Widget for displaying a score in a colored block."""
    
    def __init__(self, parent, score: int, editable: bool = False, on_score_change=None, **kwargs):
        self.original_score = score
        self.current_score = score
        self.editable = editable
        self.on_score_change = on_score_change
        color = get_score_color(score)
        
        super().__init__(
            parent,
            width=70,
            height=70,
            fg_color=color,
            corner_radius=12,
            **kwargs
        )
        
        self.grid_propagate(False)
        
        if editable:
            # Create clickable score for editing
            self.score_label = ctk.CTkLabel(
                self,
                text=str(score),
                font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
                text_color=COLORS["text_white"],
                cursor="hand2"
            )
            self.score_label.bind("<Button-1>", self._edit_score)
            
            # Add edit indicator
            self.edit_indicator = ctk.CTkLabel(
                self,
                text="✏️",
                font=ctk.CTkFont(size=10),
                text_color=COLORS["text_white"]
            )
            self.edit_indicator.place(relx=0.85, rely=0.15, anchor="center")
        else:
            self.score_label = ctk.CTkLabel(
                self,
                text=str(score),
                font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
                text_color=COLORS["text_white"]
            )
        
        self.score_label.place(relx=0.5, rely=0.5, anchor="center")
    
    def _edit_score(self, event=None):
        """Handle score editing when clicked."""
        new_score = simpledialog.askinteger(
            "Edit Score",
            f"Enter new score (0-100):\nOriginal score: {self.original_score}",
            initialvalue=self.current_score,
            minvalue=0,
            maxvalue=100
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

# ─── LEAD ITEM WIDGET ───────────────────────────────────────────────────────────
class LeadItem(ctk.CTkFrame):
    """Widget for displaying a single lead item with score and buttons that expand inline sections."""
    
    def __init__(self, parent, lead: dict, lead_index: int = 0, feedback_manager=None, **kwargs):
        confidence_color = get_score_color(lead.get("confidence", 50))
        
        super().__init__(
            parent,
            fg_color=COLORS["tertiary_black"],
            border_color=confidence_color,
            border_width=3,
            **kwargs
        )
        
        self.lead = lead
        self.lead_index = lead_index
        self.grid_columnconfigure(0, weight=1)
        self.analysis_expanded = False
        self.description_expanded = False
        
        # Feedback management - only for non-example leads
        self.feedback_manager = feedback_manager if feedback_manager is not None else FeedbackManager()
        self.feedback_entry = None
        print(f"DEBUG: LeadItem {lead_index} using FeedbackManager instance: {id(self.feedback_manager)}")
        
        # Associate chat logs - real leads get their actual chat log, examples get fake test chat log
        if lead.get("is_example", False):
            self.current_chat_log = lead.get("chat_log_filename", "example_test_chat_log_fake.json")  # Fake chat log for testing
        else:
            # For real leads, use the specific chat log if available, otherwise get most recent
            self.current_chat_log = lead.get("chat_log_filename") or extract_chat_log_filename_from_session()
            
        # Debug output to help diagnose the issue
        print(f"DEBUG: LeadItem #{lead_index} - is_example: {lead.get('is_example', False)}, current_chat_log: {self.current_chat_log}")
        
        self.setup_widgets()
        
    def setup_widgets(self):
        """Set up the lead item widgets."""
        # Main content frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        main_frame.grid_columnconfigure(1, weight=1)
        
        # Score block (editable)
        self.score_block = ScoreBlock(
            main_frame, 
            self.lead["score"], 
            editable=True, 
            on_score_change=self._on_score_change
        )
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
                corner_radius=5
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
            anchor="w"
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
            command=self.toggle_analysis
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
            command=self.toggle_description
        )
        self.view_description_btn.pack(side="left")
        
        # Save feedback button (initially hidden) - include test feedback button for examples
        feedback_button_text = "💾 SAVE FEEDBACK (TEST)" if self.lead.get("is_example", False) else "💾 SAVE FEEDBACK"
        self.save_feedback_btn = ctk.CTkButton(
            button_frame,
            text=feedback_button_text,
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            font=FONTS()["small_button"],
            command=self._save_feedback
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
            border_width=2
        )
        
        # Add analysis content header
        analysis_label = ctk.CTkLabel(
            self.analysis_section,
            text="📊 AI Analysis & Recommendation",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"]
        )
        analysis_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        
        # Create custom text widget with editing capabilities (auto-sizing)
        self.analysis_textbox = InlineEditableText(
            self.analysis_section,
            font=FONTS()["small"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            wrap="word",
            on_text_edit=self._on_text_edited
        )
        self.analysis_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.analysis_textbox.set_text(self.lead["analysis"])
        self.analysis_section.grid_columnconfigure(0, weight=1)
        self.analysis_section.grid_rowconfigure(1, weight=1)
        
        # Original Description expandable section
        self.description_section = ctk.CTkFrame(
            self.sections_frame,
            fg_color=COLORS["secondary_black"],
            border_color=COLORS["accent_orange"],
            border_width=2
        )
        
        # Add description content
        description_label = ctk.CTkLabel(
            self.description_section,
            text="📋 Original Lead Description",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"]
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
            height=150
        )
        self.description_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.description_textbox.insert("1.0", self.lead["description"])
        self.description_textbox.configure(state="disabled")
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
                self.sections_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
            
            # Show analysis section
            row = 0 if not self.description_expanded else 1
            self.analysis_section.grid(row=row, column=0, sticky="ew", pady=(0, 5) if self.description_expanded else (0, 0))
            
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
                self.sections_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
            
            # Show description section
            row = 1 if self.analysis_expanded else 0
            self.description_section.grid(row=row, column=0, sticky="ew", pady=(5, 0) if self.analysis_expanded else (0, 0))
            
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
    
    # ─── FEEDBACK HANDLING METHODS ─────────────────────────────────────────────
    
    def _on_score_change(self, original_score: int, new_score: int):
        """Handle score change from the editable score block."""
        if not self.current_chat_log:
            messagebox.showwarning("No Chat Log", "Cannot save feedback: No chat log found for this session.")
            return
        
        # Get or create feedback entry in memory
        feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
            self.current_chat_log, 
            self.lead_index, 
            self.lead["analysis"]
        )
        
        # Set score feedback (accumulates in memory)
        feedback_entry.set_score_feedback(original_score, new_score)
        
        # Update UI to show save button
        self._update_save_button_visibility()
        
        feedback_type = "TEST" if self.lead.get("is_example", False) else "REAL"
        print(f"Score feedback accumulated ({feedback_type}): {original_score} → {new_score}")
    
    def _on_text_edited(self, original_text: str, new_text: str, start_pos: str, end_pos: str):
        """Handle inline text editing from the custom text widget."""
        print(f"DEBUG: _on_text_edited called - current_chat_log: {self.current_chat_log}")
        if not self.current_chat_log:
            print(f"DEBUG: No chat log found, showing warning")
            messagebox.showwarning("No Chat Log", "Cannot save feedback: No chat log found for this session.")
            return
        
        # Get or create feedback entry in memory
        feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
            self.current_chat_log, 
            self.lead_index, 
            self.lead["analysis"]
        )
        
        # Add text feedback with position information (accumulates in memory)
        position_info = f"AI Analysis Section (pos: {start_pos} to {end_pos})"
        feedback_entry.add_text_feedback(original_text, new_text, position_info)
        
        # Update UI to show save button
        self._update_save_button_visibility()
        
        feedback_type = "TEST" if self.lead.get("is_example", False) else "REAL"
        print(f"Text feedback accumulated ({feedback_type}): '{original_text}' → '{new_text}'")
    
    def _save_feedback(self):
        """Save the accumulated feedback for this lead."""
        if not self.current_chat_log:
            messagebox.showwarning("No Chat Log", "Cannot save feedback: No chat log found for this session.")
            return
        
        # Get the current modified text from the analysis textbox
        current_analysis_text = self.analysis_textbox.get("1.0", "end-1c")
        
        # Update the feedback entry with the final replaced text
        feedback_entry = self.feedback_manager.get_or_create_feedback_entry(
            self.current_chat_log, 
            self.lead_index, 
            self.lead["analysis"]
        )
        feedback_entry.set_replaced_analysis_text(current_analysis_text)
        
        if self.feedback_manager.save_feedback_for_lead(self.current_chat_log, self.lead_index):
            messagebox.showinfo("Feedback Saved", f"Feedback for Lead #{self.lead_index + 1} saved successfully!")
            # Hide the save button after successful save
            self._update_save_button_visibility()
            # Reset the feedback entry for fresh changes after save
            self._reset_feedback_entry_after_save()
        else:
            messagebox.showerror("Error", "Failed to save feedback.")
    
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
            if self.feedback_manager.has_pending_feedback(self.current_chat_log, self.lead_index):
                # Show the save button
                self.save_feedback_btn.pack(side="left", padx=(10, 0))
            else:
                # Hide the save button
                self.save_feedback_btn.pack_forget()


# ─── INLINE EDITABLE TEXT WIDGET ───────────────────────────────────────────────

class InlineEditableText(tk.Text):
    """Custom text widget that allows inline editing with visual feedback and auto-sizing."""
    
    def __init__(self, parent, on_text_edit=None, font=None, fg_color=None, text_color=None, **kwargs):
        # Remove height from kwargs if present - we'll manage it dynamically
        kwargs.pop('height', None)
        
        # Style the Text widget to match CustomTkinter appearance
        styled_kwargs = {
            'bg': fg_color or COLORS["tertiary_black"],
            'fg': text_color or COLORS["text_white"],
            'insertbackground': text_color or COLORS["text_white"],
            'selectbackground': COLORS["accent_orange"],
            'selectforeground': COLORS["text_white"],
            'borderwidth': 0,
            'highlightthickness': 0,
            'relief': 'flat',
            'font': font,
            'wrap': 'word',  # Explicitly set wrap mode
            'height': 1,  # Start with minimal height
            **kwargs
        }
        
        super().__init__(parent, **styled_kwargs)
        self.on_text_edit = on_text_edit
        self.edit_history = []  # Track edits for hover tooltips
        self.tooltip_window = None
        self.font_metrics = None  # Will store font metrics for calculations
        
        # Configure text widget for inline editing
        self.bind("<Button-3>", self._show_context_menu)
        self.bind("<KeyPress>", self._prevent_unwanted_edits)
        self.bind("<Motion>", self._on_mouse_motion)
        self.bind("<Leave>", self._hide_tooltip)
        
        # Configure tags for styling edited text (only color change to avoid layout issues)
        self.tag_configure("edited", foreground="#ff4444", selectforeground="#ff6666")
        self.tag_configure("hover_edited", foreground="#ff6666")
    
    def _calculate_text_height(self, text: str) -> int:
        """
        Calculate the required height in lines for the given text.
        
        Args:
            text (str): The text to measure.
            
        Returns:
            int: Number of lines needed.
        """
        if not text.strip():
            return 1
        
        # Force an update to ensure the widget has been drawn
        self.update_idletasks()
        
        # Get the width of the text widget in characters
        widget_width = self.winfo_width()
        if widget_width <= 1:  # Widget not yet drawn
            widget_width = 400  # Default fallback width
        
        # Calculate characters per line based on font
        try:
            # Use the font to measure character width
            font = self.cget('font')
            if isinstance(font, str):
                import tkinter.font as tkfont
                font_obj = tkfont.nametofont(font)
            else:
                font_obj = font
            
            char_width = font_obj.measure('M')  # Use 'M' as average character width
            chars_per_line = max(1, (widget_width - 20) // char_width)  # Account for padding
            
        except:
            chars_per_line = 80  # Fallback
        
        # Split text into lines and count wrapped lines
        lines = text.split('\n')
        total_lines = 0
        
        for line in lines:
            if not line:
                total_lines += 1  # Empty line
            else:
                # Calculate how many lines this text line will wrap to
                line_length = len(line)
                wrapped_lines = max(1, (line_length + chars_per_line - 1) // chars_per_line)
                total_lines += wrapped_lines
        
        # Add a small buffer and set reasonable limits
        total_lines = max(3, min(total_lines + 1, 30))  # Between 3 and 30 lines
        
        return total_lines

    def set_text(self, text: str):
        """Set the initial text content and auto-size the widget."""
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self.configure(state="normal")  # Keep editable for selection
        
        # Auto-size the widget based on content
        # Schedule resize after the widget is fully rendered
        self.after_idle(self._resize_to_content)
    
    def _resize_to_content(self):
        """Resize the text widget to fit its content."""
        current_text = self.get("1.0", "end-1c")
        required_height = self._calculate_text_height(current_text)
        self.configure(height=required_height)
    
    def _prevent_unwanted_edits(self, event):
        """Prevent direct typing but allow selection and navigation."""
        # Allow navigation and selection keys
        allowed_keys = [
            'Left', 'Right', 'Up', 'Down', 'Home', 'End', 
            'Page_Up', 'Page_Down', 'Tab', 'Escape'
        ]
        
        # Allow Ctrl combinations for copy/select all
        if event.state & 0x4:  # Ctrl key pressed
            return
        
        if event.keysym in allowed_keys:
            return
        
        # Block all other key presses
        return "break"
    
    def _show_context_menu(self, event):
        """Show context menu for selected text editing."""
        print(f"DEBUG: _show_context_menu called")
        try:
            # Get selected text
            selected_text = self.selection_get()
            print(f"DEBUG: Selected text: '{selected_text}'")
            if selected_text.strip():
                # Create context menu
                context_menu = tk.Menu(self, tearoff=0)
                context_menu.add_command(
                    label="✏️ Edit Selected Text",
                    command=lambda: self._start_inline_edit(selected_text)
                )
                context_menu.tk_popup(event.x_root, event.y_root)
                print(f"DEBUG: Context menu shown")
        except tk.TclError as e:
            # No text selected
            print(f"DEBUG: TclError in _show_context_menu: {e}")
            pass
    
    def _start_inline_edit(self, selected_text: str):
        """Start inline editing of selected text."""
        try:
            # Get selection boundaries
            start_pos = self.index(tk.SEL_FIRST)
            end_pos = self.index(tk.SEL_LAST)
            
            # Create inline edit dialog
            InlineEditDialog(self, selected_text, start_pos, end_pos, self._complete_edit)
            
        except tk.TclError:
            messagebox.showwarning("No Selection", "Please select text to edit.")
    
    def _complete_edit(self, original_text: str, new_text: str, start_pos: str, end_pos: str):
        """Complete the inline edit and apply visual styling."""
        # Strip any unwanted whitespace/newlines from the new text
        new_text = new_text.strip()
        
        if new_text == original_text.strip():
            return  # No change made
        
        # Record the edit for hover tooltips
        edit_record = {
            'start_pos': start_pos,
            'end_pos': end_pos,
            'original_text': original_text,
            'new_text': new_text
        }
        self.edit_history.append(edit_record)
        
        # Simple approach: delete and insert, then apply tag to exactly what was inserted
        self.delete(start_pos, end_pos)
        self.insert(start_pos, new_text)
        
        # Calculate end position simply by counting characters from start
        line, col = map(int, start_pos.split('.'))
        
        # Handle multi-line text properly
        if '\n' in new_text:
            lines = new_text.split('\n')
            final_line = line + len(lines) - 1
            final_col = len(lines[-1]) if len(lines) > 1 else col + len(new_text)
            new_end_pos = f"{final_line}.{final_col}"
        else:
            # Single line text
            new_end_pos = f"{line}.{col + len(new_text)}"
        
        print(f"Simple calc: start={start_pos}, end={new_end_pos}, text='{new_text}'")
        
        # Apply highlighting only to the exact text that was inserted
        self.tag_add("edited", start_pos, new_end_pos)
        
        # Update edit record with new end position (use start_pos for consistency)
        edit_record['new_end_pos'] = new_end_pos
        edit_record['start_pos'] = start_pos  # Update to use the original start_pos
        
        # Resize to fit new content
        self._resize_to_content()
        
        # Call the callback if provided
        if self.on_text_edit:
            self.on_text_edit(original_text, new_text, start_pos, new_end_pos)
    
    def _on_mouse_motion(self, event):
        """Handle mouse motion for hover tooltips."""
        # Get mouse position in text coordinates
        mouse_pos = self.index(f"@{event.x},{event.y}")
        
        # Check if mouse is over edited text
        for edit in self.edit_history:
            if self._is_position_in_range(mouse_pos, edit['start_pos'], edit.get('new_end_pos', edit['end_pos'])):
                self._show_tooltip(event, edit['original_text'])
                return
        
        # Hide tooltip if not over edited text
        self._hide_tooltip()
    
    def _is_position_in_range(self, pos: str, start: str, end: str) -> bool:
        """Check if position is within a text range."""
        try:
            pos_float = float(pos)
            start_float = float(start)
            end_float = float(end)
            return start_float <= pos_float <= end_float
        except ValueError:
            return False
    
    def _show_tooltip(self, event, original_text: str):
        """Show tooltip with original text."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
        
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        
        # Create tooltip content
        tooltip_label = tk.Label(
            self.tooltip_window,
            text=f"Original: {original_text}",
            background="#2b2b2b",
            foreground="white",
            relief="solid",
            borderwidth=1,
            font=("Arial", 9),
            padx=8,
            pady=4
        )
        tooltip_label.pack()
    
    def _hide_tooltip(self, event=None):
        """Hide the tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# ─── INLINE EDIT DIALOG ─────────────────────────────────────────────────────────

class InlineEditDialog(ctk.CTkToplevel):
    """Small dialog for inline text editing."""
    
    def __init__(self, parent, selected_text: str, start_pos: str, end_pos: str, callback):
        super().__init__(parent)
        self.selected_text = selected_text
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.callback = callback
        
        self.setup_window()
        self.create_widgets()
        
        # Position near mouse cursor
        self.position_dialog()
        
        # Make it modal
        self.transient(parent)
        self.grab_set()
        self.focus()
    
    def setup_window(self):
        """Configure the dialog window."""
        self.title("Edit Text")
        self.geometry("400x250")
        self.configure(fg_color=COLORS["primary_black"])
        self.resizable(False, False)
        
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
    
    def create_widgets(self):
        """Create and arrange the dialog widgets."""
        # Header
        header_label = ctk.CTkLabel(
            self,
            text="Edit Selected Text",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"]
        )
        header_label.grid(row=0, column=0, pady=(20, 10))
        
        # Text editing area
        self.text_editor = ctk.CTkTextbox(
            self,
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            height=120,
            wrap="word"
        )
        self.text_editor.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.text_editor.insert("1.0", self.selected_text)
        self.text_editor.focus()
        
        # Select all text for easy replacement
        self.text_editor.tag_add("sel", "1.0", "end-1c")
        
        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(0, 20))
        
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            font=FONTS()["button"],
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            border_color=COLORS["border_gray"],
            border_width=2,
            width=80,
            command=self.destroy
        )
        cancel_button.pack(side="left", padx=(0, 10))
        
        confirm_button = ctk.CTkButton(
            button_frame,
            text="Confirm",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            width=80,
            command=self._confirm_edit
        )
        confirm_button.pack(side="left")
        
        # Bind Enter key to confirm
        self.bind('<Return>', lambda e: self._confirm_edit())
        self.bind('<Escape>', lambda e: self.destroy())
    
    def position_dialog(self):
        """Position dialog near the mouse cursor."""
        # Get mouse position
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        
        # Offset slightly so it doesn't cover the selection
        self.geometry(f"400x250+{x + 20}+{y - 50}")
    
    def _confirm_edit(self):
        """Confirm the edit and close dialog."""
        new_text = self.text_editor.get("1.0", "end-1c").strip()
        
        # Call the callback with the edit
        self.callback(self.selected_text, new_text, self.start_pos, self.end_pos)
        self.destroy()


# ─── STATISTICS WIDGET ──────────────────────────────────────────────────────────
class StatsWidget(ctk.CTkFrame):
    """Widget for displaying lead statistics."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["tertiary_black"], **kwargs)
        self.setup_widgets()
        
    def setup_widgets(self):
        """Set up the statistics display."""
        self.stats_label = ctk.CTkLabel(
            self,
            text="Statistics",
            font=FONTS()["subheading"],
            text_color=COLORS["text_white"]
        )
        self.stats_label.pack(pady=(10, 5))
        
        self.total_label = ctk.CTkLabel(
            self,
            text="Total Leads: 0",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"]
        )
        self.total_label.pack(pady=2)
        
        self.avg_score_label = ctk.CTkLabel(
            self,
            text="Average Score: 0.0",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"]
        )
        self.avg_score_label.pack(pady=2)
        
        self.avg_confidence_label = ctk.CTkLabel(
            self,
            text="Average Confidence: 0.0",
            font=FONTS()["body"],
            text_color=COLORS["text_gray"]
        )
        self.avg_confidence_label.pack(pady=(2, 10))
        
    def update(self, scored_leads: list):
        """Update the statistics display."""
        if not scored_leads:
            self.total_label.configure(text="Total Leads: 0")
            self.avg_score_label.configure(text="Average Score: 0.0")
            self.avg_confidence_label.configure(text="Average Confidence: 0.0")
            return
            
        scores = [lead["score"] for lead in scored_leads]
        confidences = [lead.get("confidence", 50) for lead in scored_leads]
        
        avg_score = sum(scores) / len(scores)
        avg_confidence = sum(confidences) / len(confidences)
        
        self.total_label.configure(text=f"Total Leads: {len(scored_leads)}")
        self.avg_score_label.configure(text=f"Average Score: {avg_score:.1f}")
        self.avg_confidence_label.configure(text=f"Average Confidence: {avg_confidence:.1f}")

# ─── EXPANDABLE WIDGET ──────────────────────────────────────────────────────────
class ExpandableFrame(ctk.CTkFrame):
    """Widget that can expand and collapse to show/hide content."""
    
    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.title = title
        self.is_expanded = False
        
        # Configure grid for proper expansion
        self.grid_columnconfigure(0, weight=1)
        # Note: Row weights are managed by the main window layout method
        
        # Create header button
        self.header_button = ctk.CTkButton(
            self,
            text=f"▶ {self.title}",
            font=FONTS()["subheading"],
            fg_color=COLORS["tertiary_black"],
            hover_color=COLORS["border_gray"],
            text_color=COLORS["text_white"],
            anchor="w",
            command=self.toggle
        )
        self.header_button.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # Content frame (initially hidden)
        self.content_frame = ctk.CTkFrame(self, fg_color=COLORS["secondary_black"])
        self.content_frame.grid_columnconfigure(0, weight=1)
        # Note: Content frame row weights are set in the specific widget implementations
        
    def toggle(self):
        """Toggle the expanded/collapsed state."""
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()
            
    def expand(self):
        """Expand to show content."""
        self.is_expanded = True
        self.header_button.configure(text=f"▼ {self.title}")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        # Note: Row weights are managed by the main window layout method
        
    def collapse(self):
        """Collapse to hide content."""
        self.is_expanded = False
        self.header_button.configure(text=f"▶ {self.title}")
        self.content_frame.grid_remove()
        # Note: Row weights are managed by the main window layout method
        
    def add_content(self, widget):
        """Add a widget to the content area."""
        widget.master = self.content_frame
        return widget

# ─── GUIDELINES WIDGET ──────────────────────────────────────────────────────────
class GuidelinesWidget(ExpandableFrame):
    """Widget for displaying scoring guidelines."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            title="Scoring Guidelines",
            fg_color=COLORS["tertiary_black"],
            **kwargs
        )
        
        self.setup_content()
        
    def setup_content(self):
        """Set up the guidelines content."""
        guidelines_text = """Score Ranges:
• 75-100: High potential
• 50-75: Medium potential  
• 25-50: Low potential
• 0-25: Very low potential

Border Colors:
Each lead has a colored border based on the AI's confidence score:
• Green border: High confidence (75-100)
• Yellow border: Medium confidence (50-75)
• Orange border: Low confidence (25-50)
• Red border: Very low confidence (0-25)

Instructions:
1. Enter a detailed lead description
2. Click "Score Lead" to analyze
3. Watch the progress bar and status updates
4. AI Analysis Phase (3-5 minutes):
   - The longest step with animated progress
   - Shows current analysis task
   - Displays elapsed time
5. View results in the main panel
6. Click on any scored lead to see full analysis
7. Border color shows AI confidence in the analysis

AI Analysis Details:
During the AI Analysis phase, the system:
🧠 Analyzes case details and evidence strength
📚 Compares with historical precedents
⚖️ Evaluates liability factors and damages
🔍 Reviews jurisdictional considerations
📊 Calculates confidence and final scores
⏱️ Typical Duration: 3-5 minutes"""

        self.guidelines_textbox = ctk.CTkTextbox(
            self.content_frame,
            font=FONTS()["small"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            wrap="word"
        )
        self.guidelines_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.guidelines_textbox.insert("1.0", guidelines_text)
        self.guidelines_textbox.configure(state="disabled")
        
        # Configure content frame grid to use all available space
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

# ─── FEEDBACK GUIDELINES WIDGET ─────────────────────────────────────────────────
class FeedbackGuidelinesWidget(ExpandableFrame):
    """Widget for displaying feedback guidelines."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            title="📝 Feedback Guidelines",
            fg_color=COLORS["tertiary_black"],
            **kwargs
        )
        
        self.setup_content()
        
    def setup_content(self):
        """Set up the feedback guidelines content with color coding."""
        # Use tkinter Text widget instead of CTkTextbox for color support
        import tkinter as tk
        
        self.feedback_textbox = tk.Text(
            self.content_frame,
            font=FONTS()["small"],
            bg=COLORS["tertiary_black"],
            fg=COLORS["text_white"],
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            insertbackground=COLORS["text_white"],
            selectbackground=COLORS["accent_orange"],
            selectforeground=COLORS["text_white"],
            width=1,  # Minimum width to allow proper expansion
            height=1   # Minimum height to allow proper expansion
        )
        self.feedback_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configure color tags - minimal and consistent with app theme
        self.feedback_textbox.tag_configure("header", foreground=COLORS["accent_orange"])  # Orange for main headers
        self.feedback_textbox.tag_configure("important", foreground=COLORS["accent_orange"])  # Orange for key actions
        self.feedback_textbox.tag_configure("subtle", foreground=COLORS["text_gray"])  # Gray for less important info
        
        # Insert content with color coding
        self._insert_colored_content()
        
        self.feedback_textbox.configure(state="disabled")
        
        # Configure content frame grid to use all available space
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # Force the textbox to update its layout after grid configuration
        self.feedback_textbox.update_idletasks()
    
    def _insert_colored_content(self):
        """Insert the minimally color-coded feedback guidelines content."""
        # Simple text with only strategic orange highlights for key actions
        feedback_text = """How to Provide Feedback:

✏️ EDIT TEXT:
1. Click "📊 View AI Analysis" on any lead
2. Select text you want to change  
3. Right-click → Edit Selected Text
4. Text highlights in orange when edited
5. Hover over highlighted text to see original

🔢 CHANGE SCORES:
1. Click the score number in the colored box
2. Enter new score (0-100)
3. Press Enter to confirm
4. Score box updates with new color

💾 SAVE YOUR WORK:
• Orange "SAVE FEEDBACK" button appears when changes made
• Each lead has its own save button
• Click to save all changes for that lead
• Button shows "(TEST)" for example leads

📁 WHERE FILES GO:
• Saved to: scripts/data/feedback/
• Contains original + your changes
• Each lead gets its own file

🔄 MULTIPLE EDITS:
• Edit → Save → Edit More → Save
• Changes accumulate in same file
• Perfect for iterative improvements

💡 BEST PRACTICES:
• Fix obvious errors or unclear language
• Adjust scores based on your expertise
• Save frequently to avoid losing work

⚠️ IMPORTANT NOTES:
• Example leads use fake data for testing
• Real leads link to actual sessions
• Program warns about unsaved feedback on exit"""

        # Insert the main text
        self.feedback_textbox.insert("1.0", feedback_text)
        
        # Only highlight truly important clickable elements in orange
        important_phrases = [
            "📊 View AI Analysis",
            "Right-click → Edit Selected Text", 
            "Click the score number",
            "SAVE FEEDBACK",
            "Save frequently"
        ]
        
        for phrase in important_phrases:
            start_idx = "1.0"
            while True:
                start_idx = self.feedback_textbox.search(phrase, start_idx, "end")
                if not start_idx:
                    break
                end_idx = f"{start_idx}+{len(phrase)}c"
                self.feedback_textbox.tag_add("important", start_idx, end_idx)
                start_idx = end_idx
        
        # Make file paths and technical details subtle gray
        technical_phrases = [
            "scripts/data/feedback/",
            "(TEST)",
            "fake data for testing",
            "actual sessions"
        ]
        
        for phrase in technical_phrases:
            start_idx = "1.0"
            while True:
                start_idx = self.feedback_textbox.search(phrase, start_idx, "end")
                if not start_idx:
                    break
                end_idx = f"{start_idx}+{len(phrase)}c"
                self.feedback_textbox.tag_add("subtle", start_idx, end_idx)
                start_idx = end_idx
