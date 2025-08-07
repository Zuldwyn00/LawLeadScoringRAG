from typing import Optional, Callable

# ─── GLOBAL SUMMARIZATION REGISTRY ──────────────────────────────────────────────────
# This module implements a simple global registry pattern to store and retrieve
# summarization functions across the application. This allows different parts of
# the codebase to access the same summarization function without passing it
# through every function call and avoiding a circular import issue.

# Global variable to store the current summarization function
_summarizer: Optional[Callable[[str], str]] = None

def set_summarizer(fn: Callable[[str], str]):
    """
    Register a summarization function globally.
    
    This function stores a callable that takes a string and returns a summarized string.
    Once set, any part of the application can retrieve and use this summarizer.
    
    Args:
        fn: A function that takes a string input and returns a summarized string
    """
    global _summarizer
    _summarizer = fn

def get_summarizer() -> Optional[Callable[[str], str]]:
    """
    Retrieve the currently registered summarization function.
    
    Returns:
        The registered summarization function, or None if no function has been set
    """
    return _summarizer