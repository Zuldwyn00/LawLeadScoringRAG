"""
Domain-specific AI client agents.

These agents inherit from ChatClient and add specialized business logic
for specific tasks like metadata extraction, lead scoring, etc.
"""

from .scoring import LeadScoringAgent
from .summarization import SummarizationAgent
from .metadata import MetadataAgent
from .lead_tooltips import TooltipAgent
from .chat_discussion import ChatDiscussionAgent

__all__ = [
    "LeadScoringAgent",
    "SummarizationAgent",
    "MetadataAgent",
    "TooltipAgent",
    "ChatDiscussionAgent",
]
