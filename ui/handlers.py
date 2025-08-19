"""
Event Handlers and Business Logic

This module contains event handlers and business logic for the Lead Scoring GUI application.
It separates the UI from the core application logic.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
import sys

# Add the project root to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.clients import AzureClient, LeadScoringClient, SummarizationClient
from scripts.clients.agents.scoring import (
    extract_score_from_response,
    extract_confidence_from_response,
)
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
from .scored_leads_loader import load_all_scored_leads, ScoredLead


# ─── CORE BUSINESS LOGIC ────────────────────────────────────────────────────────
class LeadScoringHandler:
    """Handles the core business logic for lead scoring operations."""

    def __init__(self):
        self.managers_initialized = False
        self.qdrant_manager = None
        self.lead_scoring_client = None
        self.embedding_client = None
        self.processing_logs = []
        self.ai_analysis_running = False

    def initialize_managers(self):
        """Initialize all required managers using the new modular client/agent setup."""
        if self.managers_initialized:
            return self.qdrant_manager, self.lead_scoring_client, self.embedding_client

        ensure_directories()
        self.qdrant_manager = QdrantManager()

        # Initialize embedding and chat clients using AzureClient
        embedding_client = AzureClient("text_embedding_3_small")
        chat_client = AzureClient("gpt-o4-mini")

        # Use a separate chat client for summarization
        summarizer_client = AzureClient("gpt-o4-mini")

        # Initialize agents
        summarization_client = SummarizationClient(summarizer_client)
        scorer_kwargs = {
            "confidence_threshold": 80,
            "final_model": "gpt-4.1",
            "final_model_temperature": 0.0,
        }
        self.lead_scoring_client = LeadScoringClient(
            chat_client, summarizer=summarization_client, **scorer_kwargs
        )
        self.embedding_client = embedding_client

        self.managers_initialized = True
        return self.qdrant_manager, self.lead_scoring_client, self.embedding_client

    def get_example_lead(self):
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
            "**Lead Score:** Lead Score: 77/100\n"
            "**Confidence Score:** Confidence Score: 78/100\n"
            "**Jurisdiction:** Jurisdiction: Suffolk County\n"
            "**Recommendation:** Medium-potential case with moderate risks; recommend further investigation and medical follow-up before full commitment.\n\n"
            "**Executive Summary:**\n"
            "This Suffolk County slip-and-fall case presents a viable claim based on photographic evidence of a defective, moss-covered, and partially collapsed brick on a residential sidewalk, resulting in a documented avulsion fracture and ongoing ankle instability. The lead aligns with successful premises liability cases in the jurisdiction, particularly those involving clear defects and persistent injury. However, moderate risks exist due to the claimant's admission of alcohol consumption prior to the incident and post-injury participation in sports against medical advice, both of which could be leveraged by the defense to argue comparative negligence or aggravation of injury. The strength of the evidence is solid but not overwhelming, and the injury, while real, is less severe than those in the highest-value precedents. Suffolk County is generally favorable to plaintiffs in premises cases, with average settlements for moderate ankle injuries typically ranging from $40,000 to $120,000, depending on permanency and liability clarity.\n\n"
            "**Detailed Rationale:**\n\n"
            "**1. Positive Indicators (Alignment with Past Successes):**\n"
            "*   - The presence of a clear, physical defect (moss-covered, collapsed brick) and photographic evidence closely mirrors the successful fact patterns in Case-997000 (Coram, NY), where a defective step led to a fractured ankle and a strong liability argument.\n"
            "*   - The injury (avulsion fracture at the lateral malleolus) is objectively documented, with ongoing symptoms and a scheduled MRI, similar to the persistent impairment and medical follow-up seen in Case-997000 (07-14-2022.pdf).\n"
            "*   - The claimant promptly notified the property manager in writing and has photographic documentation, which strengthens notice and liability arguments, as seen in other successful Suffolk County premises cases.\n\n"
            "**2. Negative Indicators & Risk Factors (Alignment with Past Losses/Challenges):**\n"
            "*   - The claimant's admission of consuming 'a beer or two' before the incident introduces a comparative negligence argument, which, while not necessarily fatal, could reduce recovery (noted as a complicating factor in other cases, though not directly in the provided summaries).\n"
            "*   - Continued participation in flag-football against medical advice in the weeks following the injury may allow the defense to argue that the claimant aggravated his own injury, potentially reducing damages or complicating causation (a risk not directly mirrored in the provided cases, but a known defense tactic).\n"
            "*   - The injury, while real, is less severe than the trimalleolar fracture and surgical cases (e.g., Case-997000, 07-14-2022.pdf), which may limit the upper value of the claim.\n\n"
            "**3. Strength of Precedent:**\n"
            "The historical cases provided are highly relevant, especially those involving defective steps and ankle fractures in Suffolk County. The fact patterns, medical documentation, and liability arguments are closely aligned, though the injuries in the strongest precedents are somewhat more severe.\n\n"
            "**4. Geographic & Jurisdictional Analysis:**\n"
            "*   Suffolk County is generally favorable to plaintiffs in premises liability cases, especially where there is clear evidence of a defect and notice. Average settlement values for moderate ankle injuries (avulsion fracture, persistent symptoms, but no major surgery) typically range from $40,000 to $120,000. More severe injuries with surgery and permanent impairment can exceed $150,000, but this case is likely to fall in the mid-range unless the MRI reveals a significant ligament tear or permanent disability.\n\n"
            "**5. Case ID of cases given in the context:**\n"
            "*   ID:997000, ID:2207174, ID:2211830, ID:1660355\n\n"
            "**6. Analysis Depth & Tool Usage:**\n"
            "*   **Tool Calls Made:**\n"
            "    - Call 1: get_file_context(997000 02-14-2024.docx) - Sought detailed fact pattern and injury documentation for a similar premises case.\n"
            "    - Call 2: get_file_context(997000 12-18-2024.docx) - Sought defendant testimony regarding notice, repairs, and property condition.\n"
            "    - Call 3: get_file_context(2211830 12-30-2024.pdf) - Sought comparative settlement and liability data for a recent Suffolk County premises case.\n"
            "    - Call 4: get_file_context(997000 07-14-2022.pdf) - Sought detailed medical and outcome data for a severe ankle injury premises case.\n"
            "    - Call 5: get_file_context(997000 10-19-2022.docx) - Sought employment impact and damages data for a similar injury.\n"
            "*   **Confidence Impact:**\n"
            "    - Each tool call provided additional context on liability, injury severity, and damages, increasing confidence from moderate to high-moderate. The main limitation is the lack of a clear, high-value outcome for a case with similar injury severity and the presence of some complicating factors in the new lead.\n"
            "*   **Overall Evidence Strength:** Moderate to High. The evidence base is solid for liability and injury, but the risks and moderate injury severity prevent a higher confidence score."
        )

        return {
            "timestamp": "Example Lead",
            "description": example_description,
            "score": 77,
            "confidence": 78,
            "analysis": example_analysis,
            "is_example": True,
            "chat_log_filename": "example_test_chat_log_fake.json",  # Fake chat log for testing feedback
        }

    def score_lead_process(
        self,
        lead_description: str,
        progress_callback=None,
        completion_callback=None,
        error_callback=None,
    ):
        """
        Process the lead scoring with progress updates.

        Args:
            lead_description (str): The lead description to score
            progress_callback (callable): Callback for progress updates (progress, status, elapsed_time)
            completion_callback (callable): Callback for completion (score, confidence, analysis)
            error_callback (callable): Callback for errors (error_message)
        """
        try:
            start_time = time.time()

            # Step 1: Initialize managers
            if progress_callback:
                progress_callback(
                    10,
                    "🔧 Initializing AI clients and managers...",
                    time.time() - start_time,
                )
            qdrant_manager, lead_scoring_client, embedding_client = (
                self.initialize_managers()
            )

            # Step 2: Generate embeddings
            if progress_callback:
                progress_callback(
                    25,
                    "🧠 Generating embeddings for lead description...",
                    time.time() - start_time,
                )
            question_vector = embedding_client.get_embeddings(lead_description)

            # Step 3: Search for similar cases
            if progress_callback:
                progress_callback(
                    45,
                    "🔍 Searching for similar historical cases...",
                    time.time() - start_time,
                )
            search_results = qdrant_manager.search_vectors(
                collection_name="case_files",
                query_vector=question_vector,
                vector_name="chunk",
                limit=10,
            )

            # Step 4: Get historical context
            if progress_callback:
                progress_callback(
                    60, "📚 Retrieving historical context...", time.time() - start_time
                )
            historical_context = qdrant_manager.get_context(search_results)

            # Step 5: AI analysis with animation
            if progress_callback:
                progress_callback(
                    65,
                    "⚖️ Analyzing lead with AI scoring system...",
                    time.time() - start_time,
                )
            self.ai_analysis_running = True

            # Start animation thread
            if progress_callback:
                animation_thread = threading.Thread(
                    target=self._animate_ai_progress,
                    args=(start_time, progress_callback),
                    daemon=True,
                )
                animation_thread.start()

            try:
                # score_lead now returns (analysis, chat_log_filename)
                final_analysis, chat_log_filename = lead_scoring_client.score_lead(
                    new_lead_description=lead_description,
                    historical_context=historical_context,
                )

            finally:
                self.ai_analysis_running = False
                time.sleep(0.5)

            # Step 6: Extract metrics
            if progress_callback:
                progress_callback(
                    95,
                    "📊 Extracting score and confidence metrics...",
                    time.time() - start_time,
                )
            score = extract_score_from_response(final_analysis)
            confidence = extract_confidence_from_response(final_analysis)

            # Step 7: Complete
            if progress_callback:
                progress_callback(
                    100,
                    "✅ Lead scoring completed successfully!",
                    time.time() - start_time,
                )

            if completion_callback:
                completion_callback(
                    score, confidence, final_analysis, chat_log_filename
                )

        except Exception as e:
            self.ai_analysis_running = False
            if error_callback:
                error_callback(str(e))

    def _animate_ai_progress(self, start_time, progress_callback):
        """Animate progress during AI analysis."""
        animation_chars = ["⚖️", "🧠", "📊", "🔍", "📝", "⚡"]
        messages = [
            "Analyzing case details and evidence strength...",
            "Comparing with historical precedents...",
            "Evaluating liability factors...",
            "Assessing damages potential...",
            "Reviewing jurisdictional considerations...",
            "Calculating confidence metrics...",
            "Finalizing score and recommendations...",
        ]

        char_idx = 0
        msg_idx = 0
        ai_start_time = time.time()

        while self.ai_analysis_running:
            try:
                elapsed_ai = time.time() - ai_start_time

                # Update message every 30 seconds
                if elapsed_ai > 30 * (msg_idx + 1):
                    msg_idx = min(msg_idx + 1, len(messages) - 1)

                char = animation_chars[char_idx % len(animation_chars)]
                current_msg = messages[msg_idx % len(messages)]

                # Gradually increase progress from 65% to 90%
                estimated_duration = 300  # 5 minutes
                progress_increase = min(25, (elapsed_ai / estimated_duration) * 25)
                new_progress = min(90, 65 + progress_increase)

                status_text = f"{char} AI Analysis in Progress... {current_msg}"

                if progress_callback:
                    progress_callback(
                        new_progress, status_text, time.time() - start_time
                    )

                char_idx += 1
                time.sleep(2)

            except Exception:
                time.sleep(2)


# ─── UI EVENT HANDLERS ──────────────────────────────────────────────────────────
class UIEventHandler:
    """Handles UI events and coordinates between UI and business logic."""

    def __init__(self, app):
        self.app = app
        self.business_logic = LeadScoringHandler()

    def handle_score_lead_clicked(self, lead_text: str):
        """Handle the Score Lead button click."""
        if (
            not lead_text.strip()
            or lead_text.strip()
            == "Enter the detailed description of the potential case..."
        ):
            return False, "Please enter a lead description."

        # Set session start time for log filtering
        from datetime import datetime

        self.app.current_session_start_time = datetime.now()

        # Show the View Logs button now that scoring has started
        self.app.after(0, self.app.show_view_logs_button)

        # Start processing in a separate thread
        def process_lead():
            def progress_update(progress, status, elapsed_time):
                self.app.after(
                    0,
                    lambda: self.app.progress_widget.update(
                        progress, status, elapsed_time
                    ),
                )

            def completion_callback(
                score, confidence, analysis, chat_log_filename=None
            ):
                # Create new lead
                new_lead = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "description": lead_text.strip(),
                    "score": score,
                    "confidence": confidence,
                    "analysis": analysis,
                    "chat_log_filename": chat_log_filename,  # Link to specific chat log
                }

                # Update UI on main thread
                self.app.after(0, lambda: self._handle_scoring_completion(new_lead))

            def error_callback(error_message):
                self.app.after(0, lambda: self._handle_scoring_error(error_message))

            # Show progress and start processing
            self.app.after(0, self.app.progress_widget.show)

            self.business_logic.score_lead_process(
                lead_text.strip(),
                progress_callback=progress_update,
                completion_callback=completion_callback,
                error_callback=error_callback,
            )

        thread = threading.Thread(target=process_lead, daemon=True)
        thread.start()

        return True, "Processing started..."

    def _handle_scoring_completion(self, new_lead):
        """Handle successful completion of lead scoring."""
        # Extract example leads to keep them at the bottom
        example_leads = [
            lead for lead in self.app.scored_leads if lead.get("is_example", False)
        ]
        non_example_leads = [
            lead for lead in self.app.scored_leads if not lead.get("is_example", False)
        ]

        # Add new lead at the top of non-example leads
        non_example_leads.insert(0, new_lead)

        # Reconstruct list: non-example leads first, then example leads at bottom
        self.app.scored_leads = non_example_leads + example_leads

        # Update UI
        self.app.refresh_results()
        self.app.stats_widget.update(self.app.scored_leads)

        # Hide progress after a delay
        self.app.after(2000, self.app.progress_widget.hide)

        # Re-enable score button
        self.app.score_button.configure(state="normal")

        # Show success message
        from tkinter import messagebox

        messagebox.showinfo("Success", f"Lead scored: {new_lead['score']}/100")

    def _handle_scoring_error(self, error_message):
        """Handle error during lead scoring."""
        # Hide progress
        self.app.progress_widget.hide()

        # Re-enable score button
        self.app.score_button.configure(state="normal")

        # Show error message
        from tkinter import messagebox

        messagebox.showerror("Error", f"Error processing lead: {error_message}")

    def handle_clear_all_clicked(self):
        """Handle the Clear All button click."""
        # Keep only example leads
        example_leads = [
            lead for lead in self.app.scored_leads if lead.get("is_example", False)
        ]
        self.app.scored_leads = example_leads
        self.app.refresh_results()
        self.app.stats_widget.update(self.app.scored_leads)

        # Reset session time and hide view logs button since we're clearing results
        self.app.current_session_start_time = None
        self.app.hide_view_logs_button()

    def convert_scored_lead_to_ui_format(self, scored_lead: ScoredLead) -> dict:
        """Convert a ScoredLead dataclass to the UI's expected dictionary format."""
        return {
            "timestamp": scored_lead.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "description": scored_lead.case_summary,
            "score": scored_lead.lead_score,
            "confidence": scored_lead.confidence_score,
            # Use original AI analysis for base text; edited text will be layered as highlights if present
            "analysis": scored_lead.detailed_rationale,
            "chat_log_filename": str(
                Path(scored_lead.file_path).name
            ),  # Just filename, not full path
            "is_example": False,  # Real scored leads are not examples
            # Store additional data for potential future use
            "_scored_lead_data": scored_lead,  # Keep reference to full structured data
            "_has_feedback": getattr(scored_lead, "has_feedback", False),
            "_feedback_text_changes": getattr(scored_lead, "feedback_changes", None),
            "_edited_analysis": getattr(scored_lead, "edited_analysis", None),
            "_existing_feedback_filename": getattr(
                scored_lead, "existing_feedback_filename", None
            ),
        }

    def get_initial_leads(self):
        """Get the initial leads including both example lead and real scored leads from chat logs."""
        leads = []

        # Load and convert real scored leads first
        try:
            scored_leads = load_all_scored_leads()
            for scored_lead in scored_leads:
                ui_lead = self.convert_scored_lead_to_ui_format(scored_lead)
                leads.append(ui_lead)
        except Exception as e:
            print(f"Warning: Could not load scored leads: {e}")

        # Add the example lead last (at the bottom)
        leads.append(self.business_logic.get_example_lead())

        return leads
