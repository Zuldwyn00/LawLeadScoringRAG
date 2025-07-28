"""
AI Clients Package

This package provides a layered architecture for AI clients:
- BaseClient: Abstract interface for all AI clients
- AzureClient: Azure OpenAI specific implementation
- ChatClient: Azure chat functionality with tool support
- Domain Agents: Specialized clients for specific tasks

Usage:
    from scripts.clients import MetadataExtractionClient
    client = MetadataExtractionClient()
"""

# ── CORE ARCHITECTURE ─────────────────────────────────────────────────────
# Import core classes (BaseClient, AzureClient, ChatClient)
from .base import BaseClient
from .azure import AzureClient  

# ── DOMAIN AGENTS ─────────────────────────────────────────────────────────
# Import specialized client agents for specific business tasks
#from .agents.metadata import MetadataExtractionClient
from .agents.scoring import LeadScoringClient
from .agents.summarization import SummarizationClient

# ── PACKAGE EXPORTS ───────────────────────────────────────────────────────
# Define what gets imported with "from scripts.clients import *"
__all__ = [
    # Core classes (for extending architecture)
    'BaseClient',
    'AzureClient',
    
    # Domain agents (for actual usage)
    'MetadataExtractionClient',
    'LeadScoringClient', 
    'SummarizationClient',
]
