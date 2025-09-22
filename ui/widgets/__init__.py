"""
UI Widgets Package

This package contains all custom UI widgets for the Lead Scoring GUI application.
Widgets are organized into logical modules for better maintainability.
"""

# ─── PROGRESS WIDGETS ───────────────────────────────────────────────────────────
from .progress_widgets import ProgressWidget

# ─── SCORE WIDGETS ──────────────────────────────────────────────────────────────
from .score_widgets import ScoreBlock

# ─── TEXT WIDGETS ───────────────────────────────────────────────────────────────
from .text_widgets import InlineEditableText, InlineEditDialog

# ─── LEAD WIDGETS ───────────────────────────────────────────────────────────────
from .lead_widgets import LeadItem

# ─── TRACKING WIDGETS ───────────────────────────────────────────────────────────
from .tracking_widgets import CostTrackingWidget, StatsWidget

# ─── EXPANDABLE WIDGETS ─────────────────────────────────────────────────────────
from .expandable_widgets import (
    ExpandableFrame,
    GuidelinesWidget,
    FeedbackGuidelinesWidget,
)

# ─── MODEL SELECTION WIDGETS ────────────────────────────────────────────────────
from .model_selector import ModelSelectorWidget

# ─── RETRIEVED CHUNKS DISPLAY WIDGETS ───────────────────────────────────────────
from .retrieved_chunks_display import RetrievedChunksDisplayFrame

# ─── EXPORT ALL WIDGETS ─────────────────────────────────────────────────────────
__all__ = [
    # Progress widgets
    "ProgressWidget",
    
    # Score widgets
    "ScoreBlock",
    
    # Text widgets
    "InlineEditableText",
    "InlineEditDialog",
    
    # Lead widgets
    "LeadItem",
    
    # Tracking widgets
    "CostTrackingWidget",
    "StatsWidget",
    
    # Expandable widgets
    "ExpandableFrame",
    "GuidelinesWidget",
    "FeedbackGuidelinesWidget",
    
    # Model selection widgets
    "ModelSelectorWidget",
    
    # Retrieved chunks display widgets
    "RetrievedChunksDisplayFrame",
]
