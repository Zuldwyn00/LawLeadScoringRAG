"""
Custom UI Widgets

This module contains custom widget components for the Lead Scoring GUI application.
These widgets encapsulate common UI patterns and styling.
"""

import customtkinter as ctk
import tkinter as tk
from .styles import COLORS, FONTS, get_score_color

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
    
    def __init__(self, parent, score: int, **kwargs):
        self.score = score
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
        
        self.score_label = ctk.CTkLabel(
            self,
            text=str(score),
            font=ctk.CTkFont(family="Inter", size=20, weight="bold"),
            text_color=COLORS["text_white"]
        )
        self.score_label.place(relx=0.5, rely=0.5, anchor="center")

# ─── LEAD ITEM WIDGET ───────────────────────────────────────────────────────────
class LeadItem(ctk.CTkFrame):
    """Widget for displaying a single lead item with score and buttons that expand inline sections."""
    
    def __init__(self, parent, lead: dict, **kwargs):
        confidence_color = get_score_color(lead.get("confidence", 50))
        
        super().__init__(
            parent,
            fg_color=COLORS["tertiary_black"],
            border_color=confidence_color,
            border_width=3,
            **kwargs
        )
        
        self.lead = lead
        self.grid_columnconfigure(0, weight=1)
        self.analysis_expanded = False
        self.description_expanded = False
        self.setup_widgets()
        
    def setup_widgets(self):
        """Set up the lead item widgets."""
        # Main content frame
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        main_frame.grid_columnconfigure(1, weight=1)
        
        # Score block
        score_block = ScoreBlock(main_frame, self.lead["score"])
        score_block.grid(row=0, column=0, padx=(0, 15), pady=0, sticky="n")
        
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
        
        # Add analysis content
        analysis_label = ctk.CTkLabel(
            self.analysis_section,
            text="📊 AI Analysis & Recommendation",
            font=FONTS()["subheading"],
            text_color=COLORS["accent_orange"]
        )
        analysis_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))
        
        self.analysis_textbox = ctk.CTkTextbox(
            self.analysis_section,
            font=FONTS()["small"],
            fg_color=COLORS["tertiary_black"],
            text_color=COLORS["text_white"],
            wrap="word",
            height=300
        )
        self.analysis_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.analysis_textbox.insert("1.0", self.lead["analysis"])
        self.analysis_textbox.configure(state="disabled")
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
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        
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
        self.content_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        
    def collapse(self):
        """Collapse to hide content."""
        self.is_expanded = False
        self.header_button.configure(text=f"▶ {self.title}")
        self.content_frame.grid_remove()
        
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
        
        # Configure content frame grid
        self.content_frame.grid_rowconfigure(0, weight=1)
