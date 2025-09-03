"""
Utility modules for AI agents.

This package contains utility classes and functions that support
the various AI agents in the system.
"""

from .context_enrichment import CaseContextEnricher
from .summarization_registry import get_summarization_client, set_summarization_client

__all__ = [
    "CaseContextEnricher",
    "get_summarization_client",
    "set_summarization_client",
]
