"""
Expandable and Guidelines Widgets

This module contains widgets that can expand/collapse and display guidelines with color coding.
"""

import customtkinter as ctk
import tkinter as tk
from ..styles import COLORS, FONTS


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
            command=self.toggle,
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
    """Widget for displaying scoring guidelines with color coding."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            title="Scoring Guidelines",
            fg_color=COLORS["tertiary_black"],
            **kwargs,
        )

        self.setup_content()

    def setup_content(self):
        """Set up the guidelines content with color coding."""
        # Use tkinter Text widget instead of CTkTextbox for color support
        import tkinter as tk

        self.guidelines_textbox = tk.Text(
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
            height=1,  # Minimum height to allow proper expansion
        )
        self.guidelines_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Configure color tags for different confidence levels
        self.guidelines_textbox.tag_configure(
            "high_confidence", foreground="#00ff00"
        )  # Green
        self.guidelines_textbox.tag_configure(
            "medium_confidence", foreground="#ffff00"
        )  # Yellow
        self.guidelines_textbox.tag_configure(
            "low_confidence", foreground="#ff8c00"
        )  # Orange
        self.guidelines_textbox.tag_configure(
            "very_low_confidence", foreground="#ff0000"
        )  # Red
        self.guidelines_textbox.tag_configure(
            "header", foreground=COLORS["accent_orange"]
        )  # Orange for headers

        # Insert content with color coding
        self._insert_colored_content()

        self.guidelines_textbox.configure(state="disabled")

        # Configure content frame grid to use all available space
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Force the textbox to update its layout after grid configuration
        self.guidelines_textbox.update_idletasks()

    def _insert_colored_content(self):
        """Insert the color-coded guidelines content."""
        # Insert headers and content with appropriate color tags
        self.guidelines_textbox.insert("end", "Score Ranges:\n", "header")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "75-100", "high_confidence")
        self.guidelines_textbox.insert("end", ": High potential\n", "")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "50-75", "medium_confidence")
        self.guidelines_textbox.insert("end", ": Medium potential\n", "")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "25-50", "low_confidence")
        self.guidelines_textbox.insert("end", ": Low potential\n", "")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "0-25", "very_low_confidence")
        self.guidelines_textbox.insert("end", ": Very low potential\n\n", "")

        self.guidelines_textbox.insert("end", "Border Colors:\n", "header")
        self.guidelines_textbox.insert(
            "end",
            "Each lead has a colored border based on the AI's confidence score:\n",
            "",
        )
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "Green border", "high_confidence")
        self.guidelines_textbox.insert("end", ": High confidence (75-100)\n", "")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "Yellow border", "medium_confidence")
        self.guidelines_textbox.insert("end", ": Medium confidence (50-75)\n", "")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "Orange border", "low_confidence")
        self.guidelines_textbox.insert("end", ": Low confidence (25-50)\n", "")
        self.guidelines_textbox.insert("end", "• ", "")
        self.guidelines_textbox.insert("end", "Red border", "very_low_confidence")
        self.guidelines_textbox.insert("end", ": Very low confidence (0-25)\n\n", "")

        self.guidelines_textbox.insert("end", "Instructions:\n", "header")
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert(
            "end", "1. Enter a detailed lead description\n", ""
        )
        self.guidelines_textbox.insert(
            "end",
            "   • Try different formats to experiment with AI analysis quality\n",
            "",
        )
        self.guidelines_textbox.insert(
            "end",
            "   • Test bulleted lists, paragraph summaries, or structured formats\n",
            "",
        )
        self.guidelines_textbox.insert(
            "end", "     - Vary your approach for testing results\n", ""
        )
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert("end", '2. Click "Score Lead" to analyze\n', "")
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert(
            "end", "3. Watch the progress bar and status updates\n", ""
        )
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert(
            "end", "4. AI Analysis Phase (3-5 minutes):\n", ""
        )
        self.guidelines_textbox.insert(
            "end", "   • The longest step with animated progress\n", ""
        )
        self.guidelines_textbox.insert("end", "   • Shows current analysis task\n", "")
        self.guidelines_textbox.insert("end", "   • Displays elapsed time\n", "")
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert("end", "5. View results in the main panel\n", "")
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert(
            "end", "6. Click on any scored lead to see full analysis\n", ""
        )
        self.guidelines_textbox.insert("end", "\n", "")
        self.guidelines_textbox.insert(
            "end", "7. Border color shows AI confidence in the analysis\n\n", ""
        )

        self.guidelines_textbox.insert("end", "AI Analysis Details:\n", "header")
        self.guidelines_textbox.insert(
            "end", "During the AI Analysis phase, the system:\n", ""
        )
        self.guidelines_textbox.insert(
            "end", "🧠 Analyzes case details and evidence strength\n", ""
        )
        self.guidelines_textbox.insert(
            "end", "📚 Compares with historical precedents\n", ""
        )
        self.guidelines_textbox.insert(
            "end", "⚖️ Evaluates liability factors and damages\n", ""
        )
        self.guidelines_textbox.insert(
            "end", "🔍 Reviews jurisdictional considerations\n", ""
        )
        self.guidelines_textbox.insert(
            "end", "📊 Calculates confidence and final scores\n", ""
        )
        self.guidelines_textbox.insert("end", "⏱️ Typical Duration: 3-5 minutes", "")


# ─── FEEDBACK GUIDELINES WIDGET ─────────────────────────────────────────────────
class FeedbackGuidelinesWidget(ExpandableFrame):
    """Widget for displaying feedback guidelines."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            title="📝 Feedback Guidelines",
            fg_color=COLORS["tertiary_black"],
            **kwargs,
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
            height=1,  # Minimum height to allow proper expansion
        )
        self.feedback_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Configure color tags - minimal and consistent with app theme
        self.feedback_textbox.tag_configure(
            "header", foreground=COLORS["accent_orange"]
        )  # Orange for main headers
        self.feedback_textbox.tag_configure(
            "important", foreground=COLORS["accent_orange"]
        )  # Orange for key actions
        self.feedback_textbox.tag_configure(
            "subtle", foreground=COLORS["text_gray"]
        )  # Gray for less important info

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
            "Save frequently",
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
            "actual sessions",
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
