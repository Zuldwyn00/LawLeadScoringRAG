from typing import Optional, Callable

# ─── GLOBAL SUMMARIZATION REGISTRY ──────────────────────────────────────────────────
# Simple global registry to store the summarization client for use in tools

# Global variable to store the current summarization client
_summarization_client = None

def set_summarization_client(client):
    """
    Register a SummarizationClient globally for use in tools.
    
    Args:
        client: A SummarizationClient instance
    """
    global _summarization_client
    _summarization_client = client

def get_summarization_client():
    """
    Retrieve the currently registered SummarizationClient.
    
    Returns:
        The registered SummarizationClient, or None if no client has been set
    """
    return _summarization_client