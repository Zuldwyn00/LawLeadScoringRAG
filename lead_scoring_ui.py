import streamlit as st
import re
from datetime import datetime
from pathlib import Path
import sys

# Add the project root to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.aiclients import EmbeddingManager, ChatManager
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from utils import ensure_directories, load_config, setup_logger, find_files, load_from_json, save_to_json

# ─── PAGE CONFIGURATION ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lead Scoring System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── INITIALIZATION ─────────────────────────────────────────────────────────────────
@st.cache_resource
def initialize_managers():
    """Initialize all required managers."""
    ensure_directories()
    qdrant_manager = QdrantManager()
    chat_manager = ChatManager()
    embedding_manager = EmbeddingManager()
    return qdrant_manager, chat_manager, embedding_manager

# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────────────────
def extract_score_from_response(response: str) -> int:
    """
    Extract the numerical lead score from the AI response.
    
    Args:
        response (str): The AI response containing the lead score
        
    Returns:
        int: The extracted score (1-100), or 0 if not found
    """
    # Look for "Lead Score: X/100" pattern
    pattern = r"Lead Score:\s*(\d+)/100"
    match = re.search(pattern, response, re.IGNORECASE)
    
    if match:
        return int(match.group(1))
    
    # Fallback: look for any number followed by /100
    pattern = r"(\d+)/100"
    match = re.search(pattern, response)
    
    if match:
        return int(match.group(1))
    
    return 0

def get_score_color(score: int) -> str:
    """
    Get the color for a score based on the specified ranges.
    
    Args:
        score (int): The numerical score (0-100)
        
    Returns:
        str: The color as a CSS color string
    """
    if 0 <= score < 25:
        return "#FF4444"  # Red
    elif 25 <= score < 50:
        return "#FF8800"  # Orange
    elif 50 <= score < 75:
        return "#FFDD00"  # Yellow
    elif 75 <= score <= 100:
        return "#44AA44"  # Green
    else:
        return "#888888"  # Gray for invalid scores

def score_lead_process(lead_description: str) -> tuple[int, str]:
    """
    Run the complete lead scoring process.
    
    Args:
        lead_description (str): The lead description to score
        
    Returns:
        tuple[int, str]: (score, full_response)
    """
    try:
        qdrant_manager, chat_manager, embedding_manager = initialize_managers()
        
        # Get embeddings for the lead description
        question_vector = embedding_manager.get_embeddings(lead_description)
        
        # Search for similar historical cases
        search_results = qdrant_manager.search_vectors(
            collection_name="case_files", 
            query_vector=question_vector, 
            vector_name="chunk", 
            limit=10
        )
        
        # Get historical context
        historical_context = qdrant_manager.get_context(search_results)
        
        # Score the lead
        final_analysis = chat_manager.score_lead(
            new_lead_description=lead_description,
            historical_context=historical_context
        )
        
        # Extract numerical score
        score = extract_score_from_response(final_analysis)
        
        return score, final_analysis
        
    except Exception as e:
        st.error(f"Error processing lead: {str(e)}")
        return 0, f"Error: {str(e)}"

# ─── SESSION STATE INITIALIZATION ──────────────────────────────────────────────────
if "scored_leads" not in st.session_state:
    st.session_state.scored_leads = []

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
        help="Provide as much detail as possible about the incident, injuries, and circumstances."
    )
    
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("Score Lead", type="primary", disabled=not lead_text.strip()):
            if lead_text.strip():
                with st.spinner("Analyzing lead..."):
                    score, analysis = score_lead_process(lead_text.strip())
                    
                    # Add to scored leads
                    new_lead = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "description": lead_text.strip(),
                        "score": score,
                        "analysis": analysis
                    }
                    
                    st.session_state.scored_leads.insert(0, new_lead)  # Add to top of list
                    
                    st.success(f"Lead scored: {score}/100")
                    st.rerun()
    
    with col2:
        if st.button("Clear All"):
            st.session_state.scored_leads = []
            st.rerun()

# Results section
if st.session_state.scored_leads:
    st.subheader("Scored Leads")
    
    # Custom CSS for the score blocks and hover effects
    st.markdown("""
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
    """, unsafe_allow_html=True)
    
    for i, lead in enumerate(st.session_state.scored_leads):
        score_color = get_score_color(lead["score"])
        
        # Create expandable container for each lead
        with st.expander(f"Score: {lead['score']}/100 - {lead['timestamp']}", expanded=False):
            col1, col2 = st.columns([1, 4])
            
            with col1:
                # Score block
                st.markdown(f"""
                <div class="score-block" style="background-color: {score_color};">
                    {lead['score']}
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
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
                    key=f"analysis_{i}"
                )

else:
    st.info("No leads have been scored yet. Enter a lead description above to get started.")

# ─── SIDEBAR INFORMATION ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Scoring Guidelines")
    
    st.markdown("### Score Ranges")
    st.markdown("""
    - 🟢 **75-100**: High potential
    - 🟡 **50-75**: Medium potential  
    - 🟠 **25-50**: Low potential
    - 🔴 **0-25**: Very low potential
    """)
    
    st.markdown("### Instructions")
    st.markdown("""
    1. Enter a detailed lead description
    2. Click "Score Lead" to analyze
    3. View results in the main panel
    4. Click on any scored lead to see full analysis
    """)
    
    if st.session_state.scored_leads:
        st.markdown(f"### Statistics")
        scores = [lead["score"] for lead in st.session_state.scored_leads]
        avg_score = sum(scores) / len(scores)
        st.metric("Total Leads", len(st.session_state.scored_leads))
        st.metric("Average Score", f"{avg_score:.1f}") 