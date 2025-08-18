"""
Feedback Management System

This module handles saving and loading user feedback on lead scores and AI analysis.
Feedback is associated with chat log sessions and stored in JSON format.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys
import os

# Add parent directory to path for utils import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import load_config, ensure_directories


# ─── FEEDBACK DATA STRUCTURES ──────────────────────────────────────────────────

class FeedbackEntry:
    """Represents a single feedback entry for a lead analysis."""
    
    def __init__(self, chat_log_filename: str, lead_index: int, original_analysis_text: str = ""):
        self.timestamp = datetime.now().isoformat()
        self.chat_log_filename = chat_log_filename
        self.lead_index = lead_index
        self.original_score: Optional[int] = None
        self.corrected_score: Optional[int] = None
        self.original_analysis_text = original_analysis_text
        self.text_feedback: List[Dict[str, str]] = []
        self.has_unsaved_changes = False
    
    def set_score_feedback(self, original_score: int, corrected_score: int):
        """Set feedback for score correction."""
        self.original_score = original_score
        self.corrected_score = corrected_score
        self.has_unsaved_changes = True
    
    def add_text_feedback(self, selected_text: str, replacement_text: str, position_info: str = ""):
        """Add feedback for text replacement in AI analysis."""
        print(f"DEBUG: add_text_feedback called - selected: '{selected_text[:50]}...', replacement: '{replacement_text[:50]}...'")
        # Check if this change overlaps with existing changes
        self._handle_overlapping_changes(selected_text, replacement_text, position_info)
        self.has_unsaved_changes = True
        print(f"DEBUG: has_unsaved_changes set to: {self.has_unsaved_changes}")
    
    def _handle_overlapping_changes(self, selected_text: str, replacement_text: str, position_info: str):
        """
        Handle overlapping text changes by updating existing entries or adding new ones.
        
        Args:
            selected_text (str): The text being replaced.
            replacement_text (str): The replacement text.
            position_info (str): Position information for the change.
        """
        # Check if this change replaces text that was previously changed
        overlapping_index = None
        for i, existing_change in enumerate(self.text_feedback):
            if (existing_change["replacement_text"] in selected_text or 
                selected_text in existing_change["replacement_text"]):
                overlapping_index = i
                break
        
        feedback_item = {
            "selected_text": selected_text,
            "replacement_text": replacement_text,
            "position_info": position_info,
            "change_sequence": len(self.text_feedback) + 1
        }
        
        if overlapping_index is not None:
            # Update existing change to show the evolution
            existing_change = self.text_feedback[overlapping_index]
            feedback_item["replaces_previous_change"] = {
                "original_selected": existing_change["selected_text"],
                "original_replacement": existing_change["replacement_text"],
                "change_sequence": existing_change.get("change_sequence", 1)
            }
            # Replace the existing change
            self.text_feedback[overlapping_index] = feedback_item
        else:
            # Add as new change
            self.text_feedback.append(feedback_item)
    
    def has_feedback(self) -> bool:
        """Check if this entry has any feedback data."""
        return (self.original_score is not None or 
                self.corrected_score is not None or 
                len(self.text_feedback) > 0)
    
    def clear_unsaved_changes_flag(self):
        """Clear the unsaved changes flag after saving."""
        self.has_unsaved_changes = False
    
    def set_replaced_analysis_text(self, replaced_text: str):
        """Set the final replaced analysis text after all modifications."""
        self.replaced_analysis_text = replaced_text
        self.has_unsaved_changes = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feedback entry to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "chat_log_filename": self.chat_log_filename,
            "lead_index": self.lead_index,
            "original_score": self.original_score,
            "corrected_score": self.corrected_score,
            "original_analysis_text": self.original_analysis_text,
            "replaced_analysis_text": getattr(self, 'replaced_analysis_text', ''),
            "text_feedback": self.text_feedback,
            "training_metadata": {
                "total_text_changes": len(self.text_feedback),
                "has_score_changes": self.original_score is not None and self.corrected_score is not None,
                "feedback_complexity": "high" if len(self.text_feedback) > 3 else "medium" if len(self.text_feedback) > 0 else "low"
            }
        }


# ─── FEEDBACK MANAGER ──────────────────────────────────────────────────────────

class FeedbackManager:
    """Manages saving and loading of user feedback data."""
    
    def __init__(self):
        self.config = load_config()
        self.feedback_dir = self._get_feedback_directory()
        # In-memory storage for unsaved feedback entries
        self.pending_feedback: Dict[str, FeedbackEntry] = {}  # Key: f"{chat_log}_{lead_index}"
        # Track saved feedback files to avoid duplicates
        self.saved_feedback_files: Dict[str, str] = {}  # Key: f"{chat_log}_{lead_index}", Value: filename
        
        # Ensure all directories from config exist, including feedback
        ensure_directories()
        
        # If feedback dir wasn't created by ensure_directories, create it manually
        if not self.feedback_dir.exists():
            self.feedback_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_feedback_directory(self) -> Path:
        """Get the feedback directory from config."""
        feedback_dir_str = self.config.get("directories", {}).get("feedback", "scripts/data/feedback")
        project_root = Path(__file__).resolve().parents[1]  # Go up from ui/ to project root
        return project_root / Path(feedback_dir_str)
    
    def get_or_create_feedback_entry(self, chat_log_filename: str, lead_index: int, original_analysis_text: str = "") -> FeedbackEntry:
        """
        Get existing feedback entry or create a new one for the specified lead.
        
        Args:
            chat_log_filename (str): The chat log filename.
            lead_index (int): The index of the lead.
            original_analysis_text (str): The original analysis text.
            
        Returns:
            FeedbackEntry: The feedback entry for this lead.
        """
        key = f"{chat_log_filename}_{lead_index}"
        print(f"DEBUG: get_or_create_feedback_entry - key: {key}")
        if key not in self.pending_feedback:
            print(f"DEBUG: Creating new feedback entry for key: {key}")
            self.pending_feedback[key] = FeedbackEntry(chat_log_filename, lead_index, original_analysis_text)
        else:
            print(f"DEBUG: Found existing feedback entry for key: {key}")
        entry = self.pending_feedback[key]
        print(f"DEBUG: Entry state - has_feedback: {entry.has_feedback()}, has_unsaved_changes: {entry.has_unsaved_changes}")
        return entry
    
    def has_pending_feedback(self, chat_log_filename: str, lead_index: int) -> bool:
        """
        Check if there's pending feedback for a specific lead.
        
        Args:
            chat_log_filename (str): The chat log filename.
            lead_index (int): The index of the lead.
            
        Returns:
            bool: True if pending feedback exists for this lead.
        """
        key = f"{chat_log_filename}_{lead_index}"
        return key in self.pending_feedback and self.pending_feedback[key].has_feedback() and self.pending_feedback[key].has_unsaved_changes
    
    def save_feedback_for_lead(self, chat_log_filename: str, lead_index: int) -> bool:
        """
        Save the pending feedback for a specific lead to a JSON file.
        Updates existing file if feedback was previously saved for this lead.
        
        Args:
            chat_log_filename (str): The chat log filename.
            lead_index (int): The index of the lead.
            
        Returns:
            bool: True if saved successfully, False otherwise.
        """
        key = f"{chat_log_filename}_{lead_index}"
        if key not in self.pending_feedback:
            return False
            
        feedback_entry = self.pending_feedback[key]
        if not feedback_entry.has_feedback():
            return False
            
        try:
            # Check if we already have a saved file for this lead
            if key in self.saved_feedback_files:
                # Update existing file
                filename = self.saved_feedback_files[key]
                filepath = self.feedback_dir / filename
                
                # Load existing data and merge with new feedback
                existing_data = {}
                if filepath.exists():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                
                # Merge feedback data
                merged_data = self._merge_feedback_data(existing_data, feedback_entry.to_dict())
                
                print(f"Updating existing feedback file: {filepath}")
            else:
                # Create new file
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                chat_log_stem = Path(feedback_entry.chat_log_filename).stem
                filename = f"feedback_{chat_log_stem}_lead{lead_index}_{timestamp_str}.json"
                filepath = self.feedback_dir / filename
                merged_data = feedback_entry.to_dict()
                
                # Track this file for future updates
                self.saved_feedback_files[key] = filename
                
                print(f"Creating new feedback file: {filepath}")
            
            # Save feedback
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            
            # Clear the unsaved changes flag and remove from pending
            feedback_entry.clear_unsaved_changes_flag()
            del self.pending_feedback[key]
            
            print(f"Feedback saved successfully to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving feedback for lead {lead_index}: {e}")
            return False
    
    def _merge_feedback_data(self, existing_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge new feedback data with existing feedback data.
        Handles overlapping text changes and updates metadata.
        
        Args:
            existing_data (Dict[str, Any]): Previously saved feedback data.
            new_data (Dict[str, Any]): New feedback data to merge.
            
        Returns:
            Dict[str, Any]: Merged feedback data.
        """
        # Start with existing data as base
        merged = existing_data.copy()
        
        # Update basic fields with new data
        merged.update({
            "timestamp": new_data["timestamp"],  # Use latest timestamp
            "original_score": new_data.get("original_score") or existing_data.get("original_score"),
            "corrected_score": new_data.get("corrected_score") or existing_data.get("corrected_score"),
            "replaced_analysis_text": new_data.get("replaced_analysis_text", existing_data.get("replaced_analysis_text", ""))
        })
        
        # Merge text feedback - append new changes to existing ones
        existing_text_feedback = existing_data.get("text_feedback", [])
        new_text_feedback = new_data.get("text_feedback", [])
        
        # Combine all text feedback entries
        all_text_feedback = existing_text_feedback + new_text_feedback
        merged["text_feedback"] = all_text_feedback
        
        # Update training metadata
        merged["training_metadata"] = {
            "total_text_changes": len(all_text_feedback),
            "has_score_changes": merged.get("original_score") is not None and merged.get("corrected_score") is not None,
            "feedback_complexity": "high" if len(all_text_feedback) > 3 else "medium" if len(all_text_feedback) > 0 else "low",
            "total_save_sessions": existing_data.get("training_metadata", {}).get("total_save_sessions", 0) + 1,
            "has_overlapping_changes": any("replaces_previous_change" in change for change in all_text_feedback),
            "total_change_iterations": sum(1 + (1 if "replaces_previous_change" in change else 0) for change in all_text_feedback)
        }
        
        return merged
    
    def save_all_pending_feedback(self) -> int:
        """
        Save all pending feedback entries to JSON files.
        
        Returns:
            int: Number of feedback entries successfully saved.
        """
        saved_count = 0
        
        # Create a copy of keys to avoid modification during iteration
        pending_keys = list(self.pending_feedback.keys())
        
        for key in pending_keys:
            if key in self.pending_feedback:
                feedback_entry = self.pending_feedback[key]
                if feedback_entry.has_feedback() and feedback_entry.has_unsaved_changes:
                    if self.save_feedback_for_lead(feedback_entry.chat_log_filename, feedback_entry.lead_index):
                        saved_count += 1
        
        return saved_count
    
    def clear_pending_feedback_for_lead(self, chat_log_filename: str, lead_index: int):
        """
        Clear pending feedback for a specific lead after it's been saved.
        
        Args:
            chat_log_filename (str): The chat log filename.
            lead_index (int): The index of the lead.
        """
        key = f"{chat_log_filename}_{lead_index}"
        if key in self.pending_feedback:
            del self.pending_feedback[key]
    
    def get_pending_feedback_count(self) -> int:
        """
        Get the number of leads with pending feedback.
        
        Returns:
            int: Number of leads with unsaved feedback.
        """
        count = 0
        print(f"DEBUG: get_pending_feedback_count - checking {len(self.pending_feedback)} entries")
        for key, entry in self.pending_feedback.items():
            has_feedback = entry.has_feedback()
            has_unsaved = entry.has_unsaved_changes
            print(f"DEBUG: Entry {key}: has_feedback={has_feedback}, has_unsaved_changes={has_unsaved}")
            if has_feedback and has_unsaved:
                count += 1
        print(f"DEBUG: Final pending count: {count}")
        return count
    
    def save_feedback(self, feedback_entry: FeedbackEntry) -> bool:
        """
        Save a feedback entry to a JSON file (legacy method for backward compatibility).
        
        Args:
            feedback_entry (FeedbackEntry): The feedback to save.
            
        Returns:
            bool: True if saved successfully, False otherwise.
        """
        try:
            # Create filename based on chat log and timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            chat_log_stem = Path(feedback_entry.chat_log_filename).stem
            filename = f"feedback_{chat_log_stem}_{timestamp_str}.json"
            filepath = self.feedback_dir / filename
            
            # Save feedback
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(feedback_entry.to_dict(), f, ensure_ascii=False, indent=2)
            
            print(f"Feedback saved successfully to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving feedback: {e}")
            return False
    
    def load_feedback_for_chat_log(self, chat_log_filename: str) -> List[Dict[str, Any]]:
        """
        Load all feedback entries associated with a specific chat log.
        
        Args:
            chat_log_filename (str): The chat log filename to search for.
            
        Returns:
            List[Dict[str, Any]]: List of feedback entries.
        """
        feedback_entries = []
        chat_log_stem = Path(chat_log_filename).stem
        
        try:
            # Search for feedback files matching this chat log
            pattern = f"feedback_{chat_log_stem}_*.json"
            for feedback_file in self.feedback_dir.glob(pattern):
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    feedback_data = json.load(f)
                    feedback_entries.append(feedback_data)
                    
                    # Register this file in saved_feedback_files mapping for future updates
                    lead_index = feedback_data.get('lead_index', 0)
                    key = f"{chat_log_filename}_{lead_index}"
                    self.saved_feedback_files[key] = feedback_file.name
        
        except Exception as e:
            print(f"Error loading feedback for {chat_log_filename}: {e}")
        
        return feedback_entries
    
    def get_all_feedback(self) -> List[Dict[str, Any]]:
        """
        Load all feedback entries from the feedback directory.
        
        Returns:
            List[Dict[str, Any]]: List of all feedback entries.
        """
        all_feedback = []
        
        try:
            for feedback_file in self.feedback_dir.glob("feedback_*.json"):
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    feedback_data = json.load(f)
                    all_feedback.append(feedback_data)
        
        except Exception as e:
            print(f"Error loading all feedback: {e}")
        
        return all_feedback


# ─── UTILITY FUNCTIONS ─────────────────────────────────────────────────────────

def extract_chat_log_filename_from_session() -> Optional[str]:
    """
    Extract the current chat log filename from the most recent session.
    This function looks at the chat logs directory and returns the most recent file.
    
    Returns:
        Optional[str]: The filename of the most recent chat log, or None if not found.
    """
    try:
        config = load_config()
        chat_logs_dir_str = config.get("directories", {}).get("chat_logs", "scripts/data/chat_logs")
        project_root = Path(__file__).resolve().parents[1]  # Go up from ui/ to project root
        chat_logs_dir = project_root / Path(chat_logs_dir_str)
        
        # Find the most recent chat log file
        chat_log_files = list(chat_logs_dir.glob("chat_log_*.json"))
        if not chat_log_files:
            return None
        
        # Sort by modification time and get the most recent
        most_recent = max(chat_log_files, key=lambda f: f.stat().st_mtime)
        return most_recent.name
        
    except Exception as e:
        print(f"Error extracting chat log filename: {e}")
        return None
