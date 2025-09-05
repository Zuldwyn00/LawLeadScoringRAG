"""
Text Editing Widgets

This module contains custom text widgets that allow inline editing with visual feedback.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import re
from ..styles import COLORS, FONTS


# ─── TEXT PARSING UTILITIES ────────────────────────────────────────────────────
def parse_and_color_analysis_text(text_widget, text: str):
    """
    Parse analysis text and apply orange color coding to all text with ** ** formatting.
    Removes the ** markers from display while preserving the original data.
    Preserves all other formatting including blank lines and spacing.
    
    Args:
        text_widget: The tkinter Text widget to apply formatting to
        text: The analysis text to parse and format
    """
    # Configure the orange heading tag with font styling
    text_widget.tag_configure("orange_heading", foreground=COLORS["accent_orange"], font=FONTS()["small"])
    
    # Create a display version of the text with ** markers removed
    display_text = text
    pattern = r'\*\*(.*?)\*\*'
    
    # Find all ** ** patterns and prepare for replacement
    matches = list(re.finditer(pattern, text, re.MULTILINE | re.DOTALL))
    
    # Replace ** markers in display text (work backwards to maintain positions)
    for match in reversed(matches):
        # Extract the content between ** markers
        content = match.group(1)
        # Replace the full match (including ** markers) with just the content
        display_text = display_text[:match.start()] + content + display_text[match.end():]
    
    # Clear existing text and insert the display text (preserving all other formatting)
    text_widget.delete("1.0", "end")
    text_widget.insert("1.0", display_text)
    
    # Apply orange coloring to the content that was between ** markers
    # We need to find these positions in the display text
    current_pos = 0
    for match in matches:
        # Calculate the position in the display text (after ** removal)
        # The content starts at match.start() + 2 (after **) and ends at match.end() - 2 (before **)
        content_start = match.start() + 2
        content_end = match.end() - 2
        content_length = content_end - content_start
        
        # Find this content in the display text
        content_text = match.group(1)
        search_start = display_text.find(content_text, current_pos)
        if search_start != -1:
            start_pos = f"1.0+{search_start}c"
            end_pos = f"1.0+{search_start + content_length}c"
            
            # Apply the orange heading tag with font styling
            text_widget.tag_add("orange_heading", start_pos, end_pos)
            
            # Update current position to avoid overlapping matches
            current_pos = search_start + content_length


# ─── INLINE EDITABLE TEXT WIDGET ───────────────────────────────────────────────
class InlineEditableText(tk.Text):
    """Custom text widget that allows inline editing with visual feedback and auto-sizing."""

    def __init__(
        self,
        parent,
        on_text_edit=None,
        font=None,
        fg_color=None,
        text_color=None,
        **kwargs,
    ):
        # Remove height from kwargs if present - we'll manage it dynamically
        kwargs.pop("height", None)

        # Style the Text widget to match CustomTkinter appearance
        styled_kwargs = {
            "bg": fg_color or COLORS["tertiary_black"],
            "fg": text_color or COLORS["text_white"],
            "insertbackground": text_color or COLORS["text_white"],
            "selectbackground": COLORS["accent_orange"],
            "selectforeground": COLORS["text_white"],
            "borderwidth": 0,
            "highlightthickness": 0,
            "relief": "flat",
            "font": font,
            "wrap": "word",  # Explicitly set wrap mode
            "height": 1,  # Start with minimal height
            **kwargs,
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

        # Prevent scroll event propagation to parent to avoid scroll conflicts
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", self._on_mousewheel)
        self.bind("<Button-5>", self._on_mousewheel)

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
            font = self.cget("font")
            if isinstance(font, str):
                import tkinter.font as tkfont

                font_obj = tkfont.nametofont(font)
            else:
                font_obj = font

            char_width = font_obj.measure("M")  # Use 'M' as average character width
            chars_per_line = max(
                1, (widget_width - 20) // char_width
            )  # Account for padding

        except:
            chars_per_line = 80  # Fallback

        # Split text into lines and count wrapped lines
        lines = text.split("\n")
        total_lines = 0

        for line in lines:
            if not line:
                total_lines += 1  # Empty line
            else:
                # Calculate how many lines this text line will wrap to
                line_length = len(line)
                wrapped_lines = max(
                    1, (line_length + chars_per_line - 1) // chars_per_line
                )
                total_lines += wrapped_lines

        # Add a small buffer and set reasonable limits
        total_lines = max(3, min(total_lines + 1, 30))  # Between 3 and 30 lines

        return total_lines

    def set_text(self, text: str):
        """Set the initial text content and auto-size the widget."""
        # Use the color parsing function to apply formatting
        parse_and_color_analysis_text(self, text)
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
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Page_Up",
            "Page_Down",
            "Tab",
            "Escape",
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
                    command=lambda: self._start_inline_edit(selected_text),
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
            InlineEditDialog(
                self, selected_text, start_pos, end_pos, self._complete_edit
            )

        except tk.TclError:
            messagebox.showwarning("No Selection", "Please select text to edit.")

    def _complete_edit(
        self, original_text: str, new_text: str, start_pos: str, end_pos: str
    ):
        """Complete the inline edit and apply visual styling."""
        # Strip any unwanted whitespace/newlines from the new text
        new_text = new_text.strip()

        if new_text == original_text.strip():
            return  # No change made

        # Record the edit for hover tooltips
        edit_record = {
            "start_pos": start_pos,
            "end_pos": end_pos,
            "original_text": original_text,
            "new_text": new_text,
        }
        self.edit_history.append(edit_record)

        # Simple approach: delete and insert, then apply tag to exactly what was inserted
        self.delete(start_pos, end_pos)
        self.insert(start_pos, new_text)

        # Calculate end position simply by counting characters from start
        line, col = map(int, start_pos.split("."))

        # Handle multi-line text properly
        if "\n" in new_text:
            lines = new_text.split("\n")
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
        edit_record["new_end_pos"] = new_end_pos
        edit_record["start_pos"] = start_pos  # Update to use the original start_pos

        # Re-apply color coding to the entire text after edit
        current_text = self.get("1.0", "end-1c")
        parse_and_color_analysis_text(self, current_text)

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
            # Safely get end position - try new_end_pos first, then end_pos, then start_pos as fallback
            end_pos = (
                edit.get("new_end_pos") or edit.get("end_pos") or edit.get("start_pos")
            )
            if end_pos and self._is_position_in_range(
                mouse_pos, edit.get("start_pos", ""), end_pos
            ):
                self._show_tooltip(event, edit.get("original_text", ""))
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
            pady=4,
        )
        tooltip_label.pack()

    def _hide_tooltip(self, event=None):
        """Hide the tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _on_mousewheel(self, event):
        """Handle mousewheel events to prevent scroll conflicts with parent frames."""
        # Check if the text widget has content that can be scrolled
        total_lines = float(self.index("end-1c").split(".")[0])
        visible_lines = (
            self.winfo_height() / self.dlineinfo("1.0")[3]
            if self.dlineinfo("1.0")
            else 1
        )

        # Only handle scrolling if there's content to scroll within this widget
        if total_lines > visible_lines:
            # Handle scrolling within this text widget
            if event.delta:
                # Windows and MacOS
                self.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                # Linux scroll up
                self.yview_scroll(-1, "units")
            elif event.num == 5:
                # Linux scroll down
                self.yview_scroll(1, "units")
            # Consume the event to prevent propagation to parent
            return "break"
        else:
            # Let the parent handle scrolling if this widget doesn't need to scroll
            # Don't return "break" to allow event propagation
            pass


# ─── INLINE EDIT DIALOG ─────────────────────────────────────────────────────────
class InlineEditDialog(ctk.CTkToplevel):
    """Small dialog for inline text editing."""

    def __init__(
        self, parent, selected_text: str, start_pos: str, end_pos: str, callback
    ):
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
            text_color=COLORS["accent_orange"],
        )
        header_label.grid(row=0, column=0, pady=(20, 10))

        # Text editing area
        self.text_editor = ctk.CTkTextbox(
            self,
            font=FONTS()["body"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            height=120,
            wrap="word",
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
            command=self.destroy,
        )
        cancel_button.pack(side="left", padx=(0, 10))

        confirm_button = ctk.CTkButton(
            button_frame,
            text="Confirm",
            font=FONTS()["button"],
            fg_color=COLORS["accent_orange"],
            hover_color=COLORS["accent_orange_hover"],
            width=80,
            command=self._confirm_edit,
        )
        confirm_button.pack(side="left")

        # Bind Enter key to confirm
        self.bind("<Return>", lambda e: self._confirm_edit())
        self.bind("<Escape>", lambda e: self.destroy())

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
