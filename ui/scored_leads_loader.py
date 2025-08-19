"""
Scored Leads Loader Module

This module provides functionality to load and parse already scored leads from
chat log JSON files, extracting case summaries and scoring responses for display
in the UI.
"""

import json
import re
import yaml
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import extraction functions from the scoring module
from scripts.clients.agents.scoring import (
    extract_score_from_response,
    extract_confidence_from_response,
    extract_jurisdiction_from_response,
)

# Prefer existing feedback if available for a chat log
from .feedback_manager import FeedbackManager


# ─── CONFIGURATION LOADING ───────────────────────────────────────────────────


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.yaml file.

    Returns:
        Dict[str, Any]: Configuration dictionary.
    """
    # Look for config.yaml in the project root (parent directory from ui/)
    config_paths = [
        Path(__file__).parent.parent / "config.yaml",  # From ui/ directory
        Path("config.yaml"),  # Current directory
        Path("../config.yaml"),  # Parent directory
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"Error loading config from {config_path}: {e}")
                continue

    # Return default config if no config file found
    return {"directories": {"chat_logs": "scripts/data/chat_logs"}}


def get_chat_logs_directory() -> Path:
    """
    Get the chat logs directory path from config.

    Returns:
        Path: Path to the chat logs directory.
    """
    config = load_config()
    chat_logs_dir = config.get("directories", {}).get(
        "chat_logs", "scripts/data/chat_logs"
    )

    # Make path relative to project root
    project_root = Path(__file__).parent.parent
    return project_root / chat_logs_dir


# ─── DATA MODELS ──────────────────────────────────────────────────────────────


@dataclass
class ScoredLead:
    """
    Data class representing a scored lead with essential information for UI display.

    Args:
        case_summary (str): The original case summary provided by the user.
        lead_score (int): The numerical lead score (1-100).
        confidence_score (int): The confidence score (1-100).
        detailed_rationale (str): The full AI analysis and scoring response (may include applied edits).
        file_path (str): Path to the source chat log file.
        timestamp (datetime): Timestamp when the scoring was completed.
        has_feedback (bool): Whether feedback exists for this lead.
        feedback_changes (Optional[List[Dict[str, Any]]]): Saved feedback text changes metadata used to re-apply highlights.
    """

    case_summary: str
    lead_score: int
    confidence_score: int
    detailed_rationale: str
    file_path: str
    timestamp: datetime
    has_feedback: bool = False
    feedback_changes: Optional[List[Dict[str, Any]]] = None
    edited_analysis: Optional[str] = None
    existing_feedback_filename: Optional[str] = None
    original_ai_score: Optional[int] = None


# ─── PARSING FUNCTIONS ────────────────────────────────────────────────────────


def parse_scoring_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the AI scoring response text and extract essential data.

    Args:
        response_text (str): The full AI response text.

    Returns:
        Dict[str, Any]: Dictionary containing parsed scoring data.
    """
    # Use existing extraction functions from scoring.py for consistency
    lead_score = extract_score_from_response(response_text)
    confidence_score = extract_confidence_from_response(response_text)

    return {
        "lead_score": lead_score,
        "confidence_score": confidence_score,
        "detailed_rationale": response_text,  # Keep the full response as detailed rationale
    }


# ─── MAIN LOADING FUNCTIONS ───────────────────────────────────────────────────


def load_scored_lead_from_file(file_path: Path) -> Optional[ScoredLead]:
    """
    Load and parse a single scored lead from a chat log JSON file.

    Args:
        file_path (Path): Path to the chat log JSON file.

    Returns:
        Optional[ScoredLead]: The parsed scored lead or None if parsing failed.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            chat_data = json.load(f)

        messages = chat_data.get("messages", [])
        if not messages:
            return None

        # Find the highest index user message (case summary)
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        if not user_messages:
            return None

        # Get the user message with the highest index
        latest_user_msg = max(user_messages, key=lambda x: x.get("index", 0))
        case_summary = latest_user_msg.get("content", "")

        # Find the highest index assistant message (scoring response)
        assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]
        if not assistant_messages:
            return None

        # Get the assistant message with the highest index
        latest_assistant_msg = max(assistant_messages, key=lambda x: x.get("index", 0))
        original_scoring_response = latest_assistant_msg.get("content", "")
        scoring_response = original_scoring_response

        # If feedback exists for this chat log, capture edited analysis separately
        chat_log_filename = file_path.name
        feedback_manager = FeedbackManager()
        feedback_entries = feedback_manager.load_feedback_for_chat_log(
            chat_log_filename
        )
        selected_feedback: Dict[str, Any] | None = None
        existing_feedback_filename: Optional[str] = None
        if feedback_entries:
            # Pick the most recent feedback by timestamp if available
            try:
                selected_feedback = max(
                    feedback_entries,
                    key=lambda e: datetime.fromisoformat(
                        e.get("timestamp", "1970-01-01T00:00:00")
                    ),
                )
            except Exception:
                # Fallback: just take the last entry
                selected_feedback = feedback_entries[-1]

            # Find the corresponding feedback filename for this lead
            # The lead_index should match what's in the feedback data
            lead_index = selected_feedback.get("lead_index", 0)
            key = f"{chat_log_filename}_{lead_index}"
            existing_feedback_filename = feedback_manager.saved_feedback_files.get(key)

        edited_analysis_text: Optional[str] = None
        if selected_feedback:
            # Keep original_scoring_response as the base AI analysis
            # Store the replaced text separately so the UI can apply it with highlights
            replaced_text = selected_feedback.get("replaced_analysis_text") or ""
            original_analysis_text = (
                selected_feedback.get("original_analysis_text") or ""
            )
            if replaced_text.strip():
                edited_analysis_text = replaced_text
            elif original_analysis_text.strip():
                edited_analysis_text = original_analysis_text

        # Parse the scoring response
        parsed_data = parse_scoring_response(scoring_response)
        original_ai_score = parsed_data["lead_score"]  # Store the original AI score

        # If feedback provided a corrected score, prefer it
        if selected_feedback:
            corrected_score = selected_feedback.get("corrected_score")
            if isinstance(corrected_score, int) and corrected_score > 0:
                parsed_data["lead_score"] = corrected_score
            # We keep confidence from the original assistant response

        # Extract timestamp: prefer feedback timestamp if available, else file mtime
        if selected_feedback and selected_feedback.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(selected_feedback["timestamp"])
            except Exception:
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
        else:
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Create simplified ScoredLead object
        scored_lead = ScoredLead(
            case_summary=case_summary,
            lead_score=parsed_data["lead_score"],
            confidence_score=parsed_data["confidence_score"],
            detailed_rationale=original_scoring_response,
            file_path=str(file_path),
            timestamp=timestamp,
            has_feedback=bool(selected_feedback),
            feedback_changes=(
                selected_feedback.get("text_feedback", [])
                if selected_feedback
                else None
            ),
            edited_analysis=edited_analysis_text,
            existing_feedback_filename=existing_feedback_filename,
        )

        return scored_lead

    except Exception as e:
        print(f"Error loading scored lead from {file_path}: {e}")
        return None


def load_all_scored_leads(
    chat_logs_directory: str | Path | None = None,
) -> List[ScoredLead]:
    """
    Load all scored leads from JSON files in the chat logs directory.

    Args:
        chat_logs_directory (str | Path | None): Path to the directory containing chat log files.
                                                If None, uses the path from config.yaml.

    Returns:
        List[ScoredLead]: List of successfully loaded scored leads.
    """
    if chat_logs_directory is None:
        chat_logs_path = get_chat_logs_directory()
    else:
        chat_logs_path = Path(chat_logs_directory)

    if not chat_logs_path.exists():
        print(f"Chat logs directory not found: {chat_logs_path}")
        return []

    scored_leads = []

    # Find all JSON files in the directory
    json_files = list(chat_logs_path.glob("*.json"))

    for json_file in json_files:
        scored_lead = load_scored_lead_from_file(json_file)
        if scored_lead:
            scored_leads.append(scored_lead)

    # Sort by timestamp (newest first)
    scored_leads.sort(key=lambda x: x.timestamp, reverse=True)

    return scored_leads


def get_scored_leads_summary(scored_leads: List[ScoredLead]) -> Dict[str, Any]:
    """
    Generate a summary of all scored leads for dashboard display.

    Args:
        scored_leads (List[ScoredLead]): List of scored leads.

    Returns:
        Dict[str, Any]: Summary statistics and data.
    """
    if not scored_leads:
        return {
            "total_leads": 0,
            "average_lead_score": 0,
            "average_confidence": 0,
            "high_score_leads": 0,
            "recent_leads": [],
        }

    total_leads = len(scored_leads)
    total_lead_score = sum(lead.lead_score for lead in scored_leads)
    total_confidence = sum(lead.confidence_score for lead in scored_leads)

    average_lead_score = round(total_lead_score / total_leads, 1)
    average_confidence = round(total_confidence / total_leads, 1)

    # Count high score leads (80+)
    high_score_leads = len([lead for lead in scored_leads if lead.lead_score >= 80])

    # Get 5 most recent leads
    recent_leads = scored_leads[:5]

    return {
        "total_leads": total_leads,
        "average_lead_score": average_lead_score,
        "average_confidence": average_confidence,
        "high_score_leads": high_score_leads,
        "recent_leads": recent_leads,
    }


# ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────


def filter_scored_leads(
    scored_leads: List[ScoredLead],
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    days_back: Optional[int] = None,
) -> List[ScoredLead]:
    """
    Filter scored leads based on various criteria.

    Args:
        scored_leads (List[ScoredLead]): List of scored leads to filter.
        min_score (Optional[int]): Minimum lead score to include.
        max_score (Optional[int]): Maximum lead score to include.
        days_back (Optional[int]): Only include leads from the last N days.

    Returns:
        List[ScoredLead]: Filtered list of scored leads.
    """
    filtered_leads = scored_leads.copy()

    if min_score is not None:
        filtered_leads = [
            lead for lead in filtered_leads if lead.lead_score >= min_score
        ]

    if max_score is not None:
        filtered_leads = [
            lead for lead in filtered_leads if lead.lead_score <= max_score
        ]

    if days_back is not None:
        cutoff_date = datetime.now() - timedelta(days=days_back)
        filtered_leads = [
            lead for lead in filtered_leads if lead.timestamp >= cutoff_date
        ]

    return filtered_leads


if __name__ == "__main__":
    # Example usage for testing
    leads = load_all_scored_leads()
    print(f"Loaded {len(leads)} scored leads")

    if leads:
        summary = get_scored_leads_summary(leads)
        print(f"Summary: {summary}")

        print("\nFirst lead:")
        print(f"Score: {leads[0].lead_score}")
        print(f"Confidence: {leads[0].confidence_score}")
        print(f"Timestamp: {leads[0].timestamp}")
