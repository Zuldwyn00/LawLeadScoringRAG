"""
UI Styles and Constants

This module contains all styling constants, color schemes, and theme configuration
for the Lead Scoring GUI application.
"""

import customtkinter as ctk


# ─── THEME CONFIGURATION ────────────────────────────────────────────────────────
def setup_theme():
    """Configure the global CustomTkinter theme."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")  # We'll override this with custom colors


# ─── COLOR SCHEME ───────────────────────────────────────────────────────────────
COLORS = {
    "primary_black": "#000000",
    "secondary_black": "#1a1a1a",
    "tertiary_black": "#2d2d2d",
    "accent_orange": "#ff6b35",
    "accent_orange_hover": "#ff5722",
    "accent_orange_light": "#ff8a65",
    "text_white": "#ffffff",
    "text_gray": "#e0e0e0",
    "text_dim": "#b0b0b0",
    "border_gray": "#404040",
}


# ─── FONTS ──────────────────────────────────────────────────────────────────────
def get_fonts():
    """Get font dictionary - creates fonts lazily after root window exists."""
    return {
        "title": ctk.CTkFont(family="Inter", size=32, weight="bold"),
        "subtitle": ctk.CTkFont(family="Inter", size=16),
        "heading": ctk.CTkFont(family="Inter", size=18, weight="bold"),
        "subheading": ctk.CTkFont(family="Inter", size=16, weight="bold"),
        "body": ctk.CTkFont(family="Inter", size=14),
        "small": ctk.CTkFont(family="Inter", size=12),
        "button": ctk.CTkFont(family="Inter", size=14, weight="bold"),
        "small_button": ctk.CTkFont(family="Inter", size=12),
    }


# Cache for fonts once created
_FONTS_CACHE = None


def FONTS():
    """Get cached fonts or create them if they don't exist."""
    global _FONTS_CACHE
    if _FONTS_CACHE is None:
        _FONTS_CACHE = get_fonts()
    return _FONTS_CACHE


# ─── WIDGET STYLES ──────────────────────────────────────────────────────────────
def get_primary_button_style():
    """Get styling for primary action buttons."""
    return {
        "fg_color": COLORS["accent_orange"],
        "hover_color": COLORS["accent_orange_hover"],
        "text_color": COLORS["text_white"],
        "font": FONTS()["button"],
    }


def get_secondary_button_style():
    """Get styling for secondary action buttons."""
    return {
        "fg_color": COLORS["tertiary_black"],
        "hover_color": COLORS["border_gray"],
        "border_color": COLORS["border_gray"],
        "border_width": 2,
        "text_color": COLORS["text_white"],
        "font": FONTS()["button"],
    }


def get_textbox_style():
    """Get styling for text input areas."""
    return {
        "fg_color": COLORS["tertiary_black"],
        "text_color": COLORS["text_white"],
        "border_color": COLORS["border_gray"],
        "border_width": 2,
        "font": FONTS()["body"],
    }


def get_frame_style(level="primary"):
    """Get styling for frames based on hierarchy level."""
    if level == "primary":
        return {"fg_color": COLORS["primary_black"]}
    elif level == "secondary":
        return {"fg_color": COLORS["secondary_black"]}
    elif level == "tertiary":
        return {"fg_color": COLORS["tertiary_black"]}
    else:
        return {"fg_color": "transparent"}


# ─── UTILITY FUNCTIONS ──────────────────────────────────────────────────────────
def get_score_color(score: int) -> str:
    """
    Get the color for a score using a gradient from red to green.

    Args:
        score (int): The numerical score (0-100)

    Returns:
        str: The color as a hex color string
    """
    score = max(0, min(100, score))
    red_component = int(255 * (100 - score) / 100)
    green_component = int(255 * score / 100)
    return f"#{red_component:02x}{green_component:02x}00"
