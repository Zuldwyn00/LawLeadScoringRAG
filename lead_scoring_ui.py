import streamlit as st
import re
from datetime import datetime
from pathlib import Path
import sys

# Add the project root to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.clients import AzureClient, LeadScoringClient, SummarizationClient
from scripts.clients.agents.scoring import extract_score_from_response, extract_confidence_from_response
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

# ─── PASSWORD AUTHENTICATION ───────────────────────────────────────────────────────
import os

def check_password():
    """Returns `True` if the user had the correct password."""
    
    # Get password from environment variable
    CORRECT_PASSWORD = os.getenv("STREAMLIT_PASSWORD")

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == CORRECT_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password.
        else:
            st.session_state["password_correct"] = False

    # First run, show inputs for username + password.
    if "password_correct" not in st.session_state:
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    # Password correct.
    elif st.session_state["password_correct"]:
        return True
    # Password incorrect, show input + error.
    else:
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False

# Check password before showing any content
if not check_password():
    st.stop()  # Do not continue if not authenticated.

# ─── INITIALIZATION ─────────────────────────────────────────────────────────────────
@st.cache_resource
def initialize_managers():
    """Initialize all required managers using the new modular client/agent setup."""
    ensure_directories()
    qdrant_manager = QdrantManager()

    # Initialize embedding and chat clients using AzureClient
    embedding_client = AzureClient("text_embedding_3_small")
    chat_client = AzureClient("gpt-o4-mini")

    # Use a separate chat client for summarization so its clear_history() doesn't
    # interfere with the lead scoring tool loop conversation state.
    summarizer_client = AzureClient("gpt-o4-mini")

    # Initialize agents
    summarization_client = SummarizationClient(summarizer_client)
    # Use non-tool final model for the last scoring pass (per client_configs.json)
    lead_scoring_client = LeadScoringClient(
        chat_client,
        summarizer=summarization_client,
        final_model="gpt-4.1",
    )

    return qdrant_manager, lead_scoring_client, embedding_client


# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────────────────
def get_current_processing_logs() -> str:
    """
    Get INFO log messages from the current processing session only.
    
    Returns:
        str: Formatted log messages for current processing session
    """
    if not st.session_state.processing_logs:
        return "No processing logs yet..."
    
    # Format the logs with timestamps
    formatted_logs = []
    for log_entry in st.session_state.processing_logs:
        timestamp = log_entry.get('timestamp', '')
        message = log_entry.get('message', '')
        formatted_logs.append(f"{timestamp}: {message}")
    
    return "\n".join(formatted_logs)


def start_processing_session():
    """Start a new processing session and clear previous logs."""
    st.session_state.processing_logs = []
    st.session_state.processing_start_time = time.time()


def add_processing_log(message: str):
    """Add a log message to the current processing session."""
    if st.session_state.processing_start_time is not None:
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        st.session_state.processing_logs.append({
            'timestamp': timestamp,
            'message': message
        })


def end_processing_session():
    """End the processing session and clear logs."""
    st.session_state.processing_logs = []
    st.session_state.processing_start_time = None


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
        add_processing_log("Initializing AI clients and managers...")
        qdrant_manager, lead_scoring_client, embedding_client = initialize_managers()

        add_processing_log("Generating embeddings for lead description...")
        # Get embeddings for the lead description
        question_vector = embedding_client.get_embeddings(lead_description)

        add_processing_log("Searching for similar historical cases...")
        # Search for similar historical cases
        search_results = qdrant_manager.search_vectors(
            collection_name="case_files",
            query_vector=question_vector,
            vector_name="chunk",
            limit=10,
        )

        add_processing_log("Retrieving historical context...")
        # Get historical context
        historical_context = qdrant_manager.get_context(search_results)

        add_processing_log("Analyzing lead with AI scoring system...")
        # Score the lead using the LeadScoringClient
        final_analysis = lead_scoring_client.score_lead(
            new_lead_description=lead_description, historical_context=historical_context
        )

        add_processing_log("Extracting score and confidence metrics...")
        # Extract numerical score and confidence
        score = extract_score_from_response(final_analysis)
        confidence = extract_confidence_from_response(final_analysis)

        add_processing_log("Lead scoring completed successfully!")
        return score, confidence, final_analysis

    except Exception as e:
        add_processing_log(f"Error occurred: {str(e)}")
        st.error(f"Error processing lead: {str(e)}")
        return 0, 50, f"Error: {str(e)}"


def score_lead_process_with_progress(lead_description: str) -> tuple[int, int, str]:
    """
    Run the complete lead scoring process with progress indicator and step-by-step status.

    Args:
        lead_description (str): The lead description to score

    Returns:
        tuple[int, int, str]: (score, confidence, full_response)
    """
    try:
        # Create progress bar and status text
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Initialize managers
        status_text.text("🔧 Initializing AI clients and managers...")
        progress_bar.progress(10)
        add_processing_log("Initializing AI clients and managers...")
        qdrant_manager, lead_scoring_client, embedding_client = initialize_managers()
        
        # Step 2: Generate embeddings
        status_text.text("🧠 Generating embeddings for lead description...")
        progress_bar.progress(25)
        add_processing_log("Generating embeddings for lead description...")
        question_vector = embedding_client.get_embeddings(lead_description)
        
        # Step 3: Search for similar cases
        status_text.text("🔍 Searching for similar historical cases...")
        progress_bar.progress(45)
        add_processing_log("Searching for similar historical cases...")
        search_results = qdrant_manager.search_vectors(
            collection_name="case_files",
            query_vector=question_vector,
            vector_name="chunk",
            limit=10,
        )
        
        # Step 4: Get historical context
        status_text.text("📚 Retrieving historical context...")
        progress_bar.progress(60)
        add_processing_log("Retrieving historical context...")
        historical_context = qdrant_manager.get_context(search_results)
        
        # Step 5: Score the lead
        status_text.text("⚖️ Analyzing lead with AI scoring system...")
        progress_bar.progress(80)
        add_processing_log("Analyzing lead with AI scoring system...")
        final_analysis = lead_scoring_client.score_lead(
            new_lead_description=lead_description, historical_context=historical_context
        )
        
        # Step 6: Extract metrics
        status_text.text("📊 Extracting score and confidence metrics...")
        progress_bar.progress(95)
        add_processing_log("Extracting score and confidence metrics...")
        score = extract_score_from_response(final_analysis)
        confidence = extract_confidence_from_response(final_analysis)
        
        # Step 7: Complete
        status_text.text("✅ Lead scoring completed successfully!")
        progress_bar.progress(100)
        add_processing_log("Lead scoring completed successfully!")
        
        # Clear progress indicators after a brief pause
        import time
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        
        return score, confidence, final_analysis

    except Exception as e:
        add_processing_log(f"Error occurred: {str(e)}")
        st.error(f"Error processing lead: {str(e)}")
        return 0, 50, f"Error: {str(e)}"


# ─── SESSION STATE INITIALIZATION ──────────────────────────────────────────────────
import json
import os
from pathlib import Path
import time

def get_example_lead():
    """Get the example lead data."""
    example_description = (
        "Potential client – Suffolk County slip-and-fall. A 28-year-old tenant was "
        "walking on the paved sidewalk that cuts across the landscaped courtyard of "
        "his apartment complex at about 7 p.m. when he stepped on what he describes "
        "as a 'moss-covered, partially collapsed brick' that was hidden by overgrown "
        "ground-cover plants. He lost footing, rolled his right ankle hard, and fell "
        "onto the adjacent flowerbed. He was able to limp back to his unit and iced "
        "the ankle overnight. Next morning the ankle was markedly swollen; he "
        "presented to an urgent-care clinic two days post-incident where an x-ray "
        "was read as negative for fracture and he was given an air-cast and crutches. "
        "Because pain and clicking persisted, he followed up with an orthopedist six "
        "days later; repeat imaging showed a small, already-healing avulsion fracture "
        "at the lateral malleolus. He has been in PT since week 3, but at the "
        "10-week mark still has intermittent swelling, instability on uneven ground, "
        "and a persistent click when descending stairs. MRI is scheduled for August "
        "12 (insurance-delayed) to rule out ligament tear. He has notified the "
        "property manager in writing and has photos of the displaced brick and "
        "overgrown vegetation taken the day after the fall. Two possible soft spots: "
        "(1) he admits he had consumed 'a beer or two' at a neighbor's barbecue "
        "about an hour before the incident, and (2) he continued to attend his "
        "flag-football league games in weeks 2–4 against medical advice, which the "
        "defense will argue aggravated the injury."
    )
    
    example_analysis = (
        "**Lead Score:** Lead Score: 77/100  \n"
        "**Confidence Score:** Confidence Score: 78/100  \n"
        "**Jurisdiction:** Jurisdiction: Suffolk County  \n"
        "**Recommendation:** Medium-potential case with moderate risks; recommend further investigation and medical follow-up before full commitment.\n\n"
        "**Executive Summary:**  \n"
        "This Suffolk County slip-and-fall case presents a viable claim based on photographic evidence of a defective, moss-covered, and partially collapsed brick on a residential sidewalk, resulting in a documented avulsion fracture and ongoing ankle instability. The lead aligns with successful premises liability cases in the jurisdiction, particularly those involving clear defects and persistent injury. However, moderate risks exist due to the claimant's admission of alcohol consumption prior to the incident and post-injury participation in sports against medical advice, both of which could be leveraged by the defense to argue comparative negligence or aggravation of injury. The strength of the evidence is solid but not overwhelming, and the injury, while real, is less severe than those in the highest-value precedents. Suffolk County is generally favorable to plaintiffs in premises cases, with average settlements for moderate ankle injuries typically ranging from $40,000 to $120,000, depending on permanency and liability clarity.\n\n"
        "**Detailed Rationale:**\n\n"
        "**1. Positive Indicators (Alignment with Past Successes):**  \n"
        "*   - The presence of a clear, physical defect (moss-covered, collapsed brick) and photographic evidence closely mirrors the successful fact patterns in Case-997000 (Coram, NY), where a defective step led to a fractured ankle and a strong liability argument.  \n"
        "*   - The injury (avulsion fracture at the lateral malleolus) is objectively documented, with ongoing symptoms and a scheduled MRI, similar to the persistent impairment and medical follow-up seen in Case-997000 (07-14-2022.pdf).  \n"
        "*   - The claimant promptly notified the property manager in writing and has photographic documentation, which strengthens notice and liability arguments, as seen in other successful Suffolk County premises cases.\n\n"
        "**2. Negative Indicators & Risk Factors (Alignment with Past Losses/Challenges):**  \n"
        "*   - The claimant's admission of consuming 'a beer or two' before the incident introduces a comparative negligence argument, which, while not necessarily fatal, could reduce recovery (noted as a complicating factor in other cases, though not directly in the provided summaries).  \n"
        "*   - Continued participation in flag-football against medical advice in the weeks following the injury may allow the defense to argue that the claimant aggravated his own injury, potentially reducing damages or complicating causation (a risk not directly mirrored in the provided cases, but a known defense tactic).  \n"
        "*   - The injury, while real, is less severe than the trimalleolar fracture and surgical cases (e.g., Case-997000, 07-14-2022.pdf), which may limit the upper value of the claim.\n\n"
        "**3. Strength of Precedent:**  \n"
        "The historical cases provided are highly relevant, especially those involving defective steps and ankle fractures in Suffolk County. The fact patterns, medical documentation, and liability arguments are closely aligned, though the injuries in the strongest precedents are somewhat more severe.\n\n"
        "**4. Geographic & Jurisdictional Analysis:**  \n"
        "*   Suffolk County is generally favorable to plaintiffs in premises liability cases, especially where there is clear evidence of a defect and notice. Average settlement values for moderate ankle injuries (avulsion fracture, persistent symptoms, but no major surgery) typically range from $40,000 to $120,000. More severe injuries with surgery and permanent impairment can exceed $150,000, but this case is likely to fall in the mid-range unless the MRI reveals a significant ligament tear or permanent disability.\n\n"
        "**5. Case ID of cases given in the context:**  \n"
        "*   ID:997000, ID:2207174, ID:2211830, ID:1660355\n\n"
        "**6. Analysis Depth & Tool Usage:**  \n"
        "*   **Tool Calls Made:**  \n"
        "    - Call 1: get_file_context(997000 02-14-2024.docx) - Sought detailed fact pattern and injury documentation for a similar premises case.  \n"
        "    - Call 2: get_file_context(997000 12-18-2024.docx) - Sought defendant testimony regarding notice, repairs, and property condition.  \n"
        "    - Call 3: get_file_context(2211830 12-30-2024.pdf) - Sought comparative settlement and liability data for a recent Suffolk County premises case.  \n"
        "    - Call 4: get_file_context(997000 07-14-2022.pdf) - Sought detailed medical and outcome data for a severe ankle injury premises case.  \n"
        "    - Call 5: get_file_context(997000 10-19-2022.docx) - Sought employment impact and damages data for a similar injury.  \n"
        "*   **Confidence Impact:**  \n"
        "    - Each tool call provided additional context on liability, injury severity, and damages, increasing confidence from moderate to high-moderate. The main limitation is the lack of a clear, high-value outcome for a case with similar injury severity and the presence of some complicating factors in the new lead.  \n"
        "*   **Overall Evidence Strength:** Moderate to High. The evidence base is solid for liability and injury, but the risks and moderate injury severity prevent a higher confidence score."
    )
    
    return {
        "timestamp": "Example Lead",
        "description": example_description,
        "score": 77,
        "confidence": 78,
        "analysis": example_analysis,
        "is_example": True,
    }

def save_example_lead(leads):
    """Save only example leads to the JSON file."""
    home_dir = Path.home()
    score_file = home_dir / "score_tests.json"
    
    try:
        with open(score_file, 'w', encoding='utf-8') as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Could not save example lead: {e}")

# Initialize session state with example lead
if "scored_leads" not in st.session_state:
    st.session_state.scored_leads = [get_example_lead()]

# Initialize processing logs tracking
if "processing_logs" not in st.session_state:
    st.session_state.processing_logs = []
if "processing_start_time" not in st.session_state:
    st.session_state.processing_start_time = None

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

    col1, col2, col3 = st.columns([1, 1, 6])

    with col1:
        if st.button("Score Lead", type="primary", disabled=not lead_text.strip()):
            if lead_text.strip():
                # Start processing session
                start_processing_session()
                
                # Process the lead scoring with progress indicator
                cleaned_lead_text = lead_text.strip().replace('"', '').replace("'", '')
                score, confidence, analysis = score_lead_process_with_progress(cleaned_lead_text)
                
                # Show processing logs if available
                if st.session_state.processing_logs:
                    with st.expander("📋 View Processing Logs", expanded=False):
                        log_text = get_current_processing_logs()
                        st.text_area(
                            "Processing Steps",
                            value=log_text,
                            height=200,
                            disabled=True,
                            key="processing_logs_display"
                        )
                
                # End processing session and clear logs
                end_processing_session()

                # Add to scored leads
                new_lead = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "description": cleaned_lead_text,
                    "score": score,
                    "confidence": confidence,
                    "analysis": analysis,
                }

                st.session_state.scored_leads.insert(
                    0, new_lead
                )  # Add to top of list

                st.success(f"Lead scored: {score}/100")
                st.rerun()

    with col2:
        if st.button("Clear All"):
            # Keep only example leads
            example_leads = [lead for lead in st.session_state.scored_leads if lead.get("is_example", False)]
            st.session_state.scored_leads = example_leads
            # Save only example leads to file
            save_example_lead(example_leads)
            st.rerun()

# Results section
st.subheader("Scored Leads")

# Always ensure example lead is present
example_lead = get_example_lead()
example_exists = any(lead.get("is_example", False) for lead in st.session_state.scored_leads)

if not example_exists:
    st.session_state.scored_leads.insert(0, example_lead)

if st.session_state.scored_leads:

    # Custom CSS for the score blocks, hover effects, and warning labels
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
    
    .warning-label {
        background: repeating-linear-gradient(
            45deg,
            rgba(255, 193, 7, 0.3),
            rgba(255, 193, 7, 0.3) 10px,
            rgba(255, 193, 7, 0.1) 10px,
            rgba(255, 193, 7, 0.1) 20px
        );
        border: 2px solid #ffc107;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 5px 0;
        font-weight: bold;
        color: #856404;
        text-align: center;
        font-size: 14px;
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
                # Show warning label for example leads
                if lead.get("is_example", False):
                    st.markdown(
                        '<div class="warning-label">⚠️ EXAMPLE LEAD - This is an already completed example lead.</div>',
                        unsafe_allow_html=True
                    )
                
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
        "Enter a lead description above to score it and see the results here."
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
    3. **Watch the progress bar** and status updates during processing
    4. **View processing logs** in the expandable section after completion
    5. View results in the main panel
    6. Click on any scored lead to see full analysis
    7. **Border color** shows AI confidence in the analysis
    """
    )

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
            # Save only example leads
            example_leads = [lead for lead in st.session_state.scored_leads if lead.get("is_example", False)]
            save_example_lead(example_leads)
            st.success("Example leads saved successfully!")
