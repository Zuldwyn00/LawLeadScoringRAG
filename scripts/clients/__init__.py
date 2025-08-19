"""
AI Clients Package

This package provides a layered architecture for AI clients:
- BaseClient: Abstract interface for all AI clients
- AzureClient: Azure OpenAI specific implementation
- ChatClient: Azure chat functionality with tool support
- Domain Agents: Specialized clients for specific tasks
- Caching: Cache management for client operations

Usage:
    from scripts.clients import LeadScoringAgent, ClientCacheManager
    client = LeadScoringAgent()
    cache_manager = ClientCacheManager()
"""

# ── CORE ARCHITECTURE ─────────────────────────────────────────────────────
# Import core classes (BaseClient, AzureClient, ChatClient)
from .base import BaseClient
from .azure import AzureClient

# ── DOMAIN AGENTS ─────────────────────────────────────────────────────────
# Import specialized client agents for specific business tasks
from .agents.scoring import LeadScoringAgent
from .agents.summarization import SummarizationAgent
from .agents.metadata import MetadataAgent

# ── CACHING FUNCTIONALITY ─────────────────────────────────────────────────
# Import caching classes for result storage and retrieval
from .caching import ClientCacheManager, CacheEntry, SummaryCacheEntry

# ── PACKAGE EXPORTS ───────────────────────────────────────────────────────
# Define what gets imported with "from scripts.clients import *"
__all__ = [
    # Core classes (for extending architecture)
    "BaseClient",
    "AzureClient",
    # Domain agents (for actual usage)
    "LeadScoringAgent",
    "SummarizationAgent",
    "MetadataAgent",
    # Caching functionality
    "ClientCacheManager",
    "CacheEntry",
    "SummaryCacheEntry",
]
