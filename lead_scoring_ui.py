import streamlit as st
import re
from datetime import datetime
from pathlib import Path
import sys
import time

# Add the project root to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.clients import AzureClient, LeadScoringClient, SummarizationClient
from scripts.clients.agents.scoring import extract_score_from_response
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from utils import (
    ensure_directories,
    load_config,
    setup_logger,
    find_files,
    load_from_json,
    save_to_json,
)

# ─── PAGE CONFIGURATION ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lead Scoring System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── LOG MONITORING FUNCTIONS ──────────────────────────────────────────────────────
def get_recent_log_entries(max_lines: int = 10) -> list:
    """
    Read recent entries from the PDF scraper log file.
    
    Args:
        max_lines (int): Maximum number of recent log lines to return
        
    Returns:
        list: List of recent log entries as formatted strings
    """
    try:
        log_file = Path(__file__).parent / "logs" / "pdf_scraper.log"
        if not log_file.exists():
            return ["No log file found"]
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Get the last max_lines entries
        recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        
        # Format the log entries for display
        formatted_entries = []
        for line in recent_lines:
            line = line.strip()
            if line:
                # Extract timestamp and message for cleaner display
                # Format: 2025-07-30 10:44:01 - AzureClient - DEBUG - Loaded client config...
                parts = line.split(' - ', 3)
                if len(parts) >= 4:
                    timestamp = parts[0]
                    component = parts[1]
                    level = parts[2]
                    message = parts[3]
                    
                    # Format for tooltip display
                    formatted_entry = f"{timestamp} | {component} | {level}\n{message}"
                    formatted_entries.append(formatted_entry)
                else:
                    formatted_entries.append(line)
        
        return formatted_entries if formatted_entries else ["No recent log entries"]
        
    except Exception as e:
        return [f"Error reading log: {str(e)}"]


def create_log_tooltip() -> str:
    """
    Create HTML tooltip content with recent log entries.
    
    Returns:
        str: HTML string for the tooltip
    """
    log_entries = get_recent_log_entries(8)  # Show last 8 entries
    
    # Create tooltip content with proper HTML escaping
    tooltip_content = "<div style='max-width: 600px; max-height: 400px; overflow-y: auto;'>"
    tooltip_content += "<h4 style='margin: 0 0 10px 0; color: #1f77b4;'>Recent Activity Log</h4>"
    
    for entry in log_entries:
        if entry.startswith("Error") or entry.startswith("No"):
            # Escape HTML characters for safety
            safe_entry = entry.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
            tooltip_content += f"<div style='color: #d62728; margin: 5px 0; font-size: 12px;'>{safe_entry}</div>"
        else:
            # Escape HTML characters for safety
            safe_entry = entry.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
            tooltip_content += f"<div style='margin: 5px 0; font-size: 12px; line-height: 1.3;'>{safe_entry}</div>"
    
    tooltip_content += "</div>"
    return tooltip_content


# ─── INITIALIZATION ─────────────────────────────────────────────────────────────────
@st.cache_resource
def initialize_managers():
    """Initialize all required managers using the new modular client/agent setup."""
    ensure_directories()
    qdrant_manager = QdrantManager()

    # Initialize embedding and chat clients using AzureClient
    embedding_client = AzureClient("text_embedding_3_small")
    chat_client = AzureClient("gpt-o4-mini")

    # Initialize agents
    summarization_client = SummarizationClient(chat_client)
    lead_scoring_client = LeadScoringClient(chat_client, summarizer=summarization_client)

    return qdrant_manager, lead_scoring_client, embedding_client


# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────────────────
def extract_confidence_from_response(response: str) -> int:
    """
    Extract the numerical confidence score from the AI response.

    Args:
        response (str): The AI response containing the confidence score

    Returns:
        int: The extracted confidence (1-100), or 50 if not found
    """
    # Look for "Confidence: X/100" pattern
    pattern = r"Confidence:\s*(\d+)/100"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Look for "Confidence Score: X/100" pattern
    pattern = r"Confidence Score:\s*(\d+)/100"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Look for "Confidence Level: X%" pattern
    pattern = r"Confidence Level:\s*(\d+)%"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    # Look for "Confidence: X%" pattern
    pattern = r"Confidence:\s*(\d+)%"
    match = re.search(pattern, response, re.IGNORECASE)

    if match:
        return int(match.group(1))

    return 0  # Default to 0 confidence if not found


def get_score_color(score: int) -> str:
    """
    Get the color for a score using a gradient from red to green.

    Args:
        score (int): The numerical score (0-100)

    Returns:
        str: The color as a CSS color string (hex format)
    """
    # Clamp score to valid range
    score = max(0, min(100, score))

    # Calculate RGB values for gradient from red (255,0,0) to green (0,255,0)
    red_component = int(255 * (100 - score) / 100)
    green_component = int(255 * score / 100)
    blue_component = 0

    # Convert to hex color string
    return f"#{red_component:02x}{green_component:02x}{blue_component:02x}"


def score_lead_process(lead_description: str) -> tuple[int, int, str]:
    """
    Run the complete lead scoring process using the new modular client/agent setup.

    Args:
        lead_description (str): The lead description to score

    Returns:
        tuple[int, int, str]: (score, confidence, full_response)
    """
    try:
        qdrant_manager, lead_scoring_client, embedding_client = initialize_managers()

        # Get embeddings for the lead description
        question_vector = embedding_client.get_embeddings(lead_description)

        # Search for similar historical cases
        search_results = qdrant_manager.search_vectors(
            collection_name="case_files",
            query_vector=question_vector,
            vector_name="chunk",
            limit=10,
        )

        # Get historical context
        historical_context = qdrant_manager.get_context(search_results)

        # Score the lead using the LeadScoringClient
        final_analysis = lead_scoring_client.score_lead(
            new_lead_description=lead_description, historical_context=historical_context
        )

        # Extract numerical score and confidence
        score = extract_score_from_response(final_analysis)
        confidence = extract_confidence_from_response(final_analysis)

        return score, confidence, final_analysis

    except Exception as e:
        st.error(f"Error processing lead: {str(e)}")
        return 0, 50, f"Error: {str(e)}"


# ─── SESSION STATE INITIALIZATION ──────────────────────────────────────────────────
import json
import os
from pathlib import Path

def load_scored_leads():
    """Load scored leads from the temporary JSON file."""
    home_dir = Path.home()
    score_file = home_dir / "score_tests.json"
    
    if score_file.exists():
        try:
            with open(score_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Could not load previous scores: {e}")
            return []
    return []

def save_scored_leads(leads):
    """Save scored leads to the temporary JSON file."""
    home_dir = Path.home()
    score_file = home_dir / "score_tests.json"
    
    try:
        with open(score_file, 'w', encoding='utf-8') as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Could not save scores: {e}")

if "scored_leads" not in st.session_state:
    st.session_state.scored_leads = load_scored_leads()

# ─── MAIN UI ────────────────────────────────────────────────────────────────────────
st.title("⚖️ Lead Scoring System")
st.markdown("Enter a lead description to score its potential for success.")

# Input section
with st.container():
    st.subheader("New Lead Description")

    lead_text = st.text_area(
        label="Lead Description",
        placeholder="Enter the detailed description of the potential case...",
        height=150,
        help="Provide as much detail as possible about the incident, injuries, and circumstances.",
    )

    col1, col2, col3 = st.columns([1, 1, 4])

    with col1:
        if st.button("Score Lead", type="primary", disabled=not lead_text.strip()):
            if lead_text.strip():
                # Process the lead scoring with spinner
                with st.spinner("Analyzing lead..."):
                    score, confidence, analysis = score_lead_process(lead_text.strip())

                # Add to scored leads
                new_lead = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "description": lead_text.strip(),
                    "score": score,
                    "confidence": confidence,
                    "analysis": analysis,
                }

                st.session_state.scored_leads.insert(
                    0, new_lead
                )  # Add to top of list

                # Save to file
                save_scored_leads(st.session_state.scored_leads)

                st.success(f"Lead scored: {score}/100")
                st.rerun()

    with col2:
        if st.button("Clear All"):
            st.session_state.scored_leads = []
            # Save empty state to file
            save_scored_leads([])
            st.rerun()

# Log Monitoring Section
st.markdown("---")
with st.expander("📋 System Activity Log", expanded=False):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Log filtering options
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            show_debug = st.checkbox("Show DEBUG", value=False)
        with filter_col2:
            show_info = st.checkbox("Show INFO", value=True)
        with filter_col3:
            show_warnings = st.checkbox("Show WARNINGS", value=True)
        
        # Get log entries
        log_entries = get_recent_log_entries(20)  # Show more entries in main area
        
        if log_entries:
            st.markdown("**Recent System Activity:**")
            
            # Create a container for log entries with custom styling
            log_container = st.container()
            with log_container:
                displayed_count = 0
                for i, entry in enumerate(log_entries):
                    # Apply filters
                    if "DEBUG" in entry and not show_debug:
                        continue
                    if "INFO" in entry and not show_info:
                        continue
                    if "WARNING" in entry and not show_warnings:
                        continue
                    
                    displayed_count += 1
                    
                    # Format the entry for better display
                    if entry.startswith("Error") or entry.startswith("No"):
                        st.error(f"❌ {entry}")
                    elif "WARNING" in entry:
                        st.warning(f"⚠️ {entry}")
                    elif "INFO" in entry:
                        st.info(f"ℹ️ {entry}")
                    elif "DEBUG" in entry:
                        st.text(f"🔍 {entry}")
                    else:
                        st.text(f"📝 {entry}")
                
                if displayed_count == 0:
                    st.info("No log entries match the current filters")
        else:
            st.info("No recent log entries found")
    
    with col2:
        st.markdown("**Log Controls:**")
        
        # Auto-refresh toggle
        auto_refresh_main = st.checkbox("🔄 Auto-refresh", value=False, help="Automatically refresh log entries")
        
        # View mode toggle
        view_mode = st.selectbox("View Mode:", ["Detailed", "Compact Table"], key="log_view_mode")
        
        if st.button("🔄 Manual Refresh", key="main_refresh_log"):
            st.rerun()
        
        if st.button("📄 View Full Log", key="view_full_log"):
            # Show full log in a modal-like expander
            with st.expander("📄 Full Log File", expanded=True):
                try:
                    log_file = Path(__file__).parent / "logs" / "pdf_scraper.log"
                    if log_file.exists():
                        with open(log_file, 'r', encoding='utf-8') as f:
                            full_log = f.read()
                        st.text_area("Full Log Content:", value=full_log, height=400, disabled=True)
                    else:
                        st.error("Log file not found")
                except Exception as e:
                    st.error(f"Error reading log file: {e}")
        
        # Show log file info
        st.markdown("---")
        st.markdown("**Log File Info:**")
        try:
            log_file = Path(__file__).parent / "logs" / "pdf_scraper.log"
            if log_file.exists():
                file_size = log_file.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                st.text(f"Size: {file_size_mb:.2f} MB")
                
                # Count lines
                with open(log_file, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                st.text(f"Lines: {line_count:,}")
            else:
                st.text("File: Not found")
        except Exception as e:
            st.text(f"Error: {e}")

# Results section
if st.session_state.scored_leads:
    st.subheader("Scored Leads")

    # Custom CSS for the score blocks and hover effects
    st.markdown(
        """
    <style>
    .score-block {
        display: inline-block;
        width: 60px;
        height: 60px;
        border-radius: 8px;
        text-align: center;
        line-height: 60px;
        font-weight: bold;
        font-size: 18px;
        color: white;
        margin-right: 15px;
        vertical-align: top;
    }
    
    .lead-item {
        display: flex;
        align-items: flex-start;
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        background-color: #fafafa;
        transition: background-color 0.3s ease;
    }
    
    .lead-item:hover {
        background-color: #f0f0f0;
        cursor: pointer;
    }
    
    .lead-content {
        flex: 1;
    }
    
    .lead-description {
        font-size: 16px;
        margin-bottom: 8px;
        line-height: 1.4;
    }
    
    .lead-timestamp {
        font-size: 12px;
        color: #666;
        margin-bottom: 8px;
    }
    
    .lead-preview {
        font-size: 14px;
        color: #888;
        font-style: italic;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Generate CSS for confidence borders for each lead
    confidence_css = "<style>"
    for i, lead in enumerate(st.session_state.scored_leads):
        confidence_color = get_score_color(lead.get("confidence", 50))
        confidence_css += f"""
        div[data-testid="stExpander"]:nth-of-type({i+1}) {{
            border: 3px solid {confidence_color} !important;
            border-radius: 8px !important;
            margin: 10px 0 !important;
        }}
        div[data-testid="stExpander"]:nth-of-type({i+1}) > div[data-testid="stExpanderDetails"] {{
            border-top: none !important;
        }}
        """
    confidence_css += "</style>"

    st.markdown(confidence_css, unsafe_allow_html=True)

    for i, lead in enumerate(st.session_state.scored_leads):
        score_color = get_score_color(lead["score"])

        # Create a container for each lead with score block always visible
        lead_container = st.container()

        with lead_container:
            # Create columns: score block on left, expander on right
            score_col, content_col = st.columns([1, 8])

            with score_col:
                # Score block - always visible
                st.markdown(
                    f"""
                <div class="score-block" style="background-color: {score_color};">
                    {lead['score']}
                </div>
                """,
                    unsafe_allow_html=True,
                )

            with content_col:
                # Create expandable container for lead details
                with st.expander(
                    f"Score: {lead['score']}/100 | Confidence: {lead.get('confidence', 50)}/100 - {lead['timestamp']}",
                    expanded=False,
                ):
                    # Lead description
                    st.markdown("**Lead Description:**")
                    st.write(lead["description"])

                    # Show analysis details
                    st.markdown("**Analysis Details:**")
                    st.text_area(
                        label="Full Analysis",
                        value=lead["analysis"],
                        height=400,
                        disabled=True,
                        key=f"analysis_{i}",
                    )

else:
    st.info(
        "No leads have been scored yet. Enter a lead description above to get started."
    )

# ─── SIDEBAR INFORMATION ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Scoring Guidelines")

    st.markdown("### Score Ranges")
    st.markdown(
        """
    - **75-100**: High potential
    - **50-75**: Medium potential  
    - **25-50**: Low potential
    - **0-25**: Very low potential
    
    *Score colors gradually shift from red (0) to green (100)*
    """
    )

    st.markdown("### Border Colors")
    st.markdown(
        """
    Each lead has a **colored border** based on the AI's **confidence score**:
    
    - **Green border**: High confidence (75-100)
    - **Yellow border**: Medium confidence (50-75)
    - **Orange border**: Low confidence (25-50)
    - **Red border**: Very low confidence (0-25)
    
    *Border colors use the same gradient as scores*
    """
    )

    st.markdown("### Instructions")
    st.markdown(
        """
    1. Enter a detailed lead description
    2. Click "Score Lead" to analyze
    3. View results in the main panel
    4. Click on any scored lead to see full analysis
    5. **Border color** shows AI confidence in the analysis
    """
    )

    # Add real-time log monitoring section
    st.markdown("---")
    st.markdown("### 📊 System Monitoring")
    
    # Auto-refresh checkbox
    auto_refresh = st.checkbox("🔄 Auto-refresh logs", value=False, help="Automatically refresh log entries every few seconds")
    
    if auto_refresh:
        # Use st.empty() for real-time updates
        log_placeholder = st.empty()
        
        # Get recent log entries
        log_entries = get_recent_log_entries(5)  # Show last 5 entries for sidebar
        
        with log_placeholder.container():
            st.markdown("**Recent Activity:**")
            for entry in log_entries:
                if entry.startswith("Error") or entry.startswith("No"):
                    st.error(entry[:100] + "..." if len(entry) > 100 else entry)
                elif "WARNING" in entry:
                    st.warning(entry[:100] + "..." if len(entry) > 100 else entry)
                elif "INFO" in entry:
                    st.info(entry[:100] + "..." if len(entry) > 100 else entry)
                else:
                    st.text(entry[:100] + "..." if len(entry) > 100 else entry)
        
        # Auto-refresh every 3 seconds
        time.sleep(3)
        st.rerun()
    else:
        # Show static log entries
        log_entries = get_recent_log_entries(3)  # Show last 3 entries for sidebar
        
        st.markdown("**Recent Activity:**")
        for entry in log_entries:
            if entry.startswith("Error") or entry.startswith("No"):
                st.error(entry[:80] + "..." if len(entry) > 80 else entry)
            elif "WARNING" in entry:
                st.warning(entry[:80] + "..." if len(entry) > 80 else entry)
            elif "INFO" in entry:
                st.info(entry[:80] + "..." if len(entry) > 80 else entry)
            else:
                st.text(entry[:80] + "..." if len(entry) > 80 else entry)

    if st.session_state.scored_leads:
        st.markdown(f"### Statistics")
        scores = [lead["score"] for lead in st.session_state.scored_leads]
        confidences = [
            lead.get("confidence", 50) for lead in st.session_state.scored_leads
        ]

        avg_score = sum(scores) / len(scores)
        avg_confidence = sum(confidences) / len(confidences)

        st.metric("Total Leads", len(st.session_state.scored_leads))
        st.metric("Average Score", f"{avg_score:.1f}")
        st.metric("Average Confidence", f"{avg_confidence:.1f}")
        
        # Show file location and save button
        st.markdown("### Data Persistence")
        home_dir = Path.home()
        score_file = home_dir / "score_tests.json"
        st.text(f"File: {score_file}")
        
        if st.button("Save Current State"):
            save_scored_leads(st.session_state.scored_leads)
            st.success("Scores saved successfully!")
