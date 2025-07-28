"""
Domain-specific AI client agents.

These agents inherit from ChatClient and add specialized business logic
for specific tasks like metadata extraction, lead scoring, etc.
"""

#from .metadata import MetadataExtractionClient
from .scoring import LeadScoringClient
from .summarization import SummarizationClient

__all__ = [
    'MetadataExtractionClient',
    'LeadScoringClient', 
    'SummarizationClient',
] 