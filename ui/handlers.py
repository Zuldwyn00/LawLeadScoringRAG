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

from scripts.file_management.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.clients import AzureClient, LeadScoringAgent, SummarizationAgent
from scripts.clients.agents.utils.context_enrichment import CaseContextEnricher
from scripts.clients.agents.utils.vector_registry import set_vector_clients
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
        self.current_lead_telemetry_managers = []  # Track telemetry managers for current lead

    def initialize_managers(self, process_model: str = "gpt-5-mini", final_model: str = "gpt-5", 
                           process_temperature: float = None, final_temperature: float = None):
        """Initialize all required managers using the new modular client/agent setup."""
        # Check if we need to reinitialize due to model or temperature change
        if (self.managers_initialized and 
            hasattr(self, 'current_process_model') and hasattr(self, 'current_final_model') and 
            hasattr(self, 'current_process_temperature') and hasattr(self, 'current_final_temperature') and
            self.current_process_model == process_model and self.current_final_model == final_model and
            self.current_process_temperature == process_temperature and self.current_final_temperature == final_temperature):
            return self.qdrant_manager, self.lead_scoring_client, self.embedding_client

        ensure_directories()
        self.qdrant_manager = QdrantManager()

        # Initialize embedding and chat clients using AzureClient
        embedding_client = AzureClient("text_embedding_3_large")
        chat_client = AzureClient(process_model)

        # Use a separate chat client for summarization (keep o4-mini for efficiency)
        summarizer_client = AzureClient("o4-mini")

        # Initialize agents
        summarization_client = SummarizationAgent(summarizer_client)
        context_enricher = CaseContextEnricher(self.qdrant_manager)
        scorer_kwargs = {
            "confidence_threshold": 90,
            "final_model": final_model,  # Use selected final model for final scoring
            "final_model_temperature": final_temperature,  # Use selected final temperature
        }
        
        # Add process temperature if specified
        if process_temperature is not None:
            scorer_kwargs["temperature"] = process_temperature
        # Register vector clients globally for query_vector_context tool (same pattern as summarization)
        set_vector_clients(self.qdrant_manager, embedding_client)
        
        self.lead_scoring_client = LeadScoringAgent(
            chat_client, 
            summarizer=summarization_client, 
            context_enricher=context_enricher,
            **scorer_kwargs
        )
        self.embedding_client = embedding_client

        # Collect telemetry managers for cost tracking
        self.current_lead_telemetry_managers = [
            embedding_client.telemetry_manager,
            chat_client.telemetry_manager,
            summarizer_client.telemetry_manager,
        ]
        
        # Add final_client telemetry manager if it exists
        if hasattr(self.lead_scoring_client, 'final_client') and self.lead_scoring_client.final_client:
            self.current_lead_telemetry_managers.append(self.lead_scoring_client.final_client.telemetry_manager)

        self.managers_initialized = True
        self.current_process_model = process_model
        self.current_final_model = final_model
        self.current_process_temperature = process_temperature
        self.current_final_temperature = final_temperature
        return self.qdrant_manager, self.lead_scoring_client, self.embedding_client

    def get_current_lead_cost(self) -> float:
        """Get the total cost for the current lead from all telemetry managers."""
        if not self.current_lead_telemetry_managers:
            return 0.0
        
        total_cost = sum(manager.total_price for manager in self.current_lead_telemetry_managers)
        print(f"Calculated total cost: ${total_cost:.6f} from {len(self.current_lead_telemetry_managers)} managers")  # Debug logging
        return total_cost

    def get_current_lead_cost_by_model(self) -> dict:
        """Get the cost breakdown by model for the current lead."""
        if not self.current_lead_telemetry_managers:
            return {}
        
        model_costs = {}
        for manager in self.current_lead_telemetry_managers:
            # Extract model name from client config
            model_name = manager.config.get("deployment_name", "unknown")
            if model_name not in model_costs:
                model_costs[model_name] = 0.0
            model_costs[model_name] += manager.total_price
        
        return model_costs

    def reset_current_lead_cost(self):
        """Reset the cost tracking for all telemetry managers."""
        for manager in self.current_lead_telemetry_managers:
            manager.total_price = 0.0

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
            """Recommendation: Moderate-to-high potential—recommend immediate follow-up, preserve/collect evidence (photos, site inspection, maintenance records, prior complaints), and continue medical documentation (MRI results, PT records) while preparing to address comparative negligence/aggravation defenses.

Title: Suffolk County — Apartment Courtyard Brick Defect Slip-and-Fall with Right Ankle Avulsion Fracture

Jurisdiction: [Suffolk County]

Lead Score: 70/100
Confidence Score: 50/100
Reasoning Assurance Score: 100/100


Missing Information:
* Damages Documentation: Specific medical bills, itemized treatment costs, and any lost wages are not provided; needed to quantify damages.
* Precedent Relevance: No historical cases in the provided context include a clear win or loss with comparable facts and recorded outcomes; outcome precedent is missing.
* MRI Results: Pending; needed to confirm extent of ligament injury/permanency.
* Maintenance/Notice History: No records yet of prior complaints, repair logs, or duration of the defect/overgrowth; needed to strengthen constructive notice.

Executive Summary:
This lead presents promising liability and injury elements: a privately owned apartment courtyard walkway with a described moss-covered, partially collapsed brick obscured by overgrowth; contemporaneous photos of the defect; and written notice to the property manager. Injury is specific and objectively corroborated (repeat imaging showing a lateral malleolus avulsion fracture, ongoing PT, persistent instability/clicking, MRI scheduled). These align with firm historical premises intakes where defect photographs and medical imaging supported claims. Key risks include plaintiff’s admission to drinking “a beer or two” pre-incident and post-accident participation in flag football, which the defense may argue contributed to or aggravated injury. Missing damages documentation and lack of outcome precedents in the case summaries constrain valuation and reduce data completeness. Overall, this is a viable case with moderate-to-high potential contingent on solid notice/maintenance evidence and comprehensive medical documentation.

Detailed Rationale:

1. Positive Indicators (Alignment with Past Successes):
* Defect photographs: The new lead has photos of the displaced brick and overgrown vegetation taken the day after the fall. This mirrors strong evidentiary value noted in case 2500275 (EMS/paramedic scene photos of raised sidewalk defect) and case 2500298 (intake indicates claimant took photographs of the hazard).
* Private property premises defect: Similar to 2500298 and 2500244, the hazard occurred on private property (apartment complex courtyard), avoiding some municipal defenses seen in 2500275 and 2500223. This alignment favors clearer duty and maintenance responsibility.
* Injury specificity and imaging: The lead’s avulsion fracture at the lateral malleolus confirmed on repeat imaging aligns with the emphasis on imaging-confirmed injuries reflected in 2500275 (wrist fracture, MRI/X-ray findings). Persistent symptoms and scheduled MRI parallel the documented focus on orthopedic follow-up and therapy in 2500275.
* Written notice to property manager: While post-incident, the existence of written notice and photos evidences the defect and may assist in establishing the condition and its persistence; 2500275 highlighted lack of prior notice as a defense target—here, documentation improves the evidentiary posture compared to 2500275.
* Ongoing treatment: PT and orthopedic follow-up support continuing injury, consistent with patterns of ongoing care documented in 2500275 and medical records within 2500182 (tool results highlight orthopedic recommendations; though 2500182 is an auto case, it demonstrates the firm’s emphasis on medical necessity).

2. Negative Indicators & Risk Factors (Alignment with Past Losses/Challenges):
* Notice/constructive notice: 2500275 shows defendants challenge notice absent prior complaints/311 records; the new lead currently lacks maintenance records, prior complaints, or evidence of defect duration. This is a risk until investigation yields constructive notice proof.
* Alcohol consumption admission: The lead admits “a beer or two” about an hour before. No historical case provided specifically addresses alcohol-comparative negligence; this remains an unmitigated risk in the present record (Information not provided in historical summaries).
* Post-accident activity/aggravation: Continued flag football in weeks 2–4 provides an aggravation/intervening cause argument. No directly comparable historical precedent in the provided summaries addresses this (Information not provided).
* Witnesses: No independent eyewitnesses are mentioned in the lead; 2500298 includes a witness. Absence of witnesses may weaken liability proof if defect was obscure; this increases reliance on photos and site conditions.
* Outcome/value gaps: All referenced historical cases are open or presign with no settlements/verdicts, curtailing precedent-based valuation and strategic expectations.

3. Strength of Precedent:
The precedents are categorically similar (premises slip/trip-and-fall with defect evidence and medical documentation) and provide useful guidance on evidence and notice, but they lack clear outcomes (wins/losses) and settlement values. Therefore, precedent strength for outcome prediction is moderate-to-weak.

4. Geographic & Jurisdictional Analysis:
Insufficient jurisdictional data provided in case summaries. No settlement amounts or verdict values are included for Suffolk County or comparable cases.

5. Case ID of cases given in the context:
* 2500275
* 2500182
* 2500202
* 2500305
* 2500310
* 2500244
* 2500267
* 2500223
* 2500298

6. Analysis Depth & Tool Usage:
* Tool Selection & Usage Strategy:
  - Information Gaps Identified:
    1. Lack of outcome data (settlements/verdicts) in similar premises cases.
    2. Need for references to defect photographs, written notice practices, and maintenance/complaint records in historical files.
    3. Medical-injury parallels for ankle fractures/orthopedic recommendations (to anticipate potential medical trajectory).
    4. Absence of jurisdictional settlement values for Suffolk County.
  - Tool Selection Rationale:
    - File retrieval targeted specific cases most analogous on liability/evidence (2500275) and premises defect with photos/witness (2500298).
    - Vector searches aimed to surface medical parallels for ankle injuries (avulsion fracture, orthopedic recommendations) and documents referencing notice and property-manager correspondence to understand evidentiary themes.

  - Tool Usage Summary: You made 5 tool calls out of 5 maximum. Tools used: get_file_context (2 times), query_vector_context (3 times).

* Tool Call Details (List any tools used in a bulleted list, one per call — DO NOT OMIT OR SUMMARIZE):
  - Call 1: get_file_context(case_data\\2500275\\LIABILITY SHEET PREMISES.docx) - Purpose: retrieve liability sheet for sidewalk trip-and-fall to compare defect/notice/evidence details - Result: Case summary showed a raised sidewalk defect, EMS/hospital records, imaging-confirmed wrist fracture, lack of formal written notice/311, and anticipated defense challenges on notice; helped highlight the importance of prior complaints/constructive notice and the value of photos/imaging.
  - Call 2: get_file_context(case_data\\2500298\\doc06389020250721074839.pdf) - Purpose: obtain intake for premises defect with photographic evidence/witness to compare injury severity and documentation - Result: Intake indicated private-property defect, photos taken, one witness, and claimed soft-tissue injuries with “No fractures, surgeries, or stitches,” which contrasts with supplemental data noting “Client had Surgery”; helped illustrate documentation practices (photos/witness) and revealed inconsistency regarding surgery.
  - Call 3: query_vector_context("Suffolk County slip and fall moss-covered brick overgrown vegetation photos written notice avulsion fracture ankle urgent care air-cast crutches physical therapy MRI scheduled beer two beers flag football activity weeks after fall") - Purpose: locate documents referencing similar notice/photo evidence and ankle injury treatment - Result: Returned 2500275 liability sheet, 2500182 medical records (orthopedic recommendations), 2500190 podiatry records, and 2500310 intake; helped confirm firm’s emphasis on medical imaging/orthopedic opinions and the role of photographic documentation; did not provide outcome values.
  - Call 4: query_vector_context("avulsion fracture lateral malleolus ankle air cast crutches PT MRI scheduled avulsion fracture photos written notice vegetation brick") - Purpose: find medical-record-heavy files and orthopedic recommendations related to ankle injuries - Result: Returned 2500182 orthopedic/pain-spine records and 2500190 podiatry notes, plus a letter to Allstate with medical packet; helped validate the importance of orthopedic opinions and comprehensive medical packets; no settlement outcomes provided.
  - Call 5: query_vector_context("premises liability written notice photos property manager overgrown vegetation displaced brick sidewalk courtyard Suffolk County avulsion fracture ankle") - Purpose: surface notices of claim and management correspondence relevant to premises defects and written notice - Result: Returned notice-of-claim documents (2500171; 2500291 mailed NOC to Suffolk Regional OTB) and letters of representation/green cards for 2500298; helped confirm procedural approaches for notice/defendant contact; no valuation data.

* Reasoning Assurance Rationale:
  - +40 Adherence to Context: Analysis relied only on the lead and provided historical/tool-derived context; no external facts introduced.
  - +30 Use of Precedent: Specific case IDs (e.g., 2500275, 2500298, 2500244) were explicitly referenced to support comparisons.
  - +20 Tool Usage Efficacy: Tools were targeted to liability/evidence and medical parallels; results directly informed notice/photography importance and medical documentation strategy.
  - +10 Framework Adherence: Followed all required steps (direct comparison via indicators, success/risk identification, evidence assessment, confidence scoring, jurisdiction analysis).
  - Total: 100/100.

* Overall Evidence Strength: Moderate"""
        )

        return {
            "timestamp": "Example Lead",
            "description": example_description,
            "score": 70,
            "confidence": 50,
            "analysis": example_analysis,
            "is_example": True,
            "chat_log_filename": "example_test_chat_log_fake.json",  # Fake chat log for testing feedback
        }

    def score_lead_process(
        self,
        lead_description: str,
        chunk_limit: int = 10,
        progress_callback=None,
        completion_callback=None,
        error_callback=None,
        cost_callback=None,
        chunks_callback=None,
    ):
        """
        Process the lead scoring with progress updates.

        Args:
            lead_description (str): The lead description to score
            chunk_limit (int): Number of chunks to retrieve from vector search (default: 10)
            progress_callback (callable): Callback for progress updates (progress, status, elapsed_time)
            completion_callback (callable): Callback for completion (score, confidence, analysis)
            error_callback (callable): Callback for errors (error_message)
            cost_callback (callable): Callback for cost updates (current_cost)
            chunks_callback (callable): Callback for chunks updates (retrieved_chunks)
        """
        try:
            start_time = time.time()

            # Note: Cost tracking reset happens at the start of process_lead() in UIEventHandler

            # Step 1: Use already initialized managers (initialized in process_lead with correct models)
            if progress_callback:
                progress_callback(
                    10,
                    "🔧 Using initialized AI clients and managers...",
                    time.time() - start_time,
                )
            qdrant_manager = self.qdrant_manager
            lead_scoring_client = self.lead_scoring_client
            embedding_client = self.embedding_client

            # Step 2: Generate embeddings
            if progress_callback:
                progress_callback(
                    25,
                    "🧠 Generating embeddings for lead description...",
                    time.time() - start_time,
                )
            question_vector = embedding_client.get_embeddings(lead_description)
            
            # Update cost tracking after embeddings
            if cost_callback:
                current_cost = self.get_current_lead_cost()
                cost_callback(current_cost)

            # Step 3: Search for similar cases
            if progress_callback:
                progress_callback(
                    45,
                    "🔍 Searching for similar historical cases...",
                    time.time() - start_time,
                )
            search_results = qdrant_manager.search_vectors(
                collection_name="case_files_large",
                query_vector=question_vector,
                vector_name="chunk",
                limit=chunk_limit,
            )
            
            # Display chunks immediately after retrieval
            if chunks_callback:
                chunks_callback(search_results)

            # Step 4: Get historical context
            if progress_callback:
                progress_callback(
                    60, "📚 Retrieving historical context...", time.time() - start_time
                )
            # Extract case_ids directly from search_results
            from scripts.clients.agents.scoring import extract_case_ids_from_search_results
            case_ids = extract_case_ids_from_search_results(search_results)

            # Get historical context for additional metadata like source
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
                    case_ids=case_ids,
                    historical_context=historical_context,
                )

            finally:
                self.ai_analysis_running = False
                time.sleep(0.5)
                
            # Update cost tracking after AI analysis
            if cost_callback:
                current_cost = self.get_current_lead_cost()
                cost_callback(current_cost)

            # Step 6: Extract metrics
            if progress_callback:
                progress_callback(
                    95,
                    "📊 Extracting score and confidence metrics...",
                    time.time() - start_time,
                )
            score = extract_score_from_response(final_analysis)
            confidence = extract_confidence_from_response(final_analysis)

            # Step 6.5: Generate indicators using the tooltip agent
            indicators = []
            if final_analysis:
                try:
                    if progress_callback:
                        progress_callback(
                            97,
                            "🎯 Generating lead indicators...",
                            time.time() - start_time,
                        )
                    
                    from scripts.clients.azure import AzureClient
                    from scripts.clients.agents.lead_tooltips import TooltipAgent
                    import json
                    
                    # Initialize tooltip agent with gpt-5-mini
                    tooltip_client = AzureClient("gpt-5-mini")
                    tooltip_agent = TooltipAgent(tooltip_client)
                    
                    # Generate tooltips/indicators
                    message_for_tooltips = (
                        "-Original Lead Description-\n"
                        + lead_description
                        + "\n\n-Scored Lead-\n"
                        + final_analysis
                    )
                    tooltips_response = tooltip_agent.get_tooltips(message_for_tooltips)
                    tooltips_data = json.loads(tooltips_response)
                    
                    # Convert to our indicator format (exclude lead_score category)
                    for tooltip in tooltips_data.get("tooltips", []):
                        category = tooltip.get("category", "other")
                        
                        # Skip lead score indicators since we don't want them
                        if category == "lead_score":
                            continue
                            
                        icon = tooltip.get("icon", "neutral")
                        text = tooltip.get("text", "")
                        weight = tooltip.get("weight", 50)
                        
                        # Map icons to our format
                        if icon == "up":
                            symbol, color, indicator_type = '▲', '#4CAF50', 'positive'
                        elif icon == "down":
                            symbol, color, indicator_type = '▼', '#F44336', 'negative' 
                        else:
                            symbol, color, indicator_type = '●', '#FF9800', 'neutral'
                        
                        indicators.append({
                            'type': indicator_type,
                            'symbol': symbol,
                            'text': text,
                            'color': color,
                            'weight': weight,
                            'category': category
                        })
                    
                    # Sort by weight (highest first) and limit to 6
                    indicators.sort(key=lambda x: x.get('weight', 0), reverse=True)
                    indicators = indicators[:6]
                    
                except Exception as e:
                    print(f"Error generating indicators: {e}")
                    # Fallback to confidence-based indicator
                    if confidence >= 70:
                        indicators = [{
                            'type': 'positive', 'symbol': '▲', 'text': f'High Confidence Score ({confidence}%)',
                            'color': '#4CAF50', 'weight': 70, 'category': 'confidence'
                        }]
                    elif confidence >= 50:
                        indicators = [{
                            'type': 'neutral', 'symbol': '●', 'text': f'Moderate Confidence ({confidence}%)', 
                            'color': '#FF9800', 'weight': 50, 'category': 'confidence'
                        }]
                    else:
                        indicators = [{
                            'type': 'negative', 'symbol': '▼', 'text': f'Low Confidence Score ({confidence}%)',
                            'color': '#F44336', 'weight': 40, 'category': 'confidence'
                        }]

            # Step 7: Complete
            if progress_callback:
                progress_callback(
                    100,
                    "✅ Lead scoring completed successfully!",
                    time.time() - start_time,
                )

            # Final cost update before completion
            if cost_callback:
                final_cost = self.get_current_lead_cost()
                cost_callback(final_cost)

            # Update the saved chat log with indicators
            if indicators and chat_log_filename:
                self._update_chat_log_with_indicators(chat_log_filename, indicators)
            
            if completion_callback:
                completion_callback(
                    score, confidence, final_analysis, chat_log_filename, search_results, indicators
                )

        except Exception as e:
            self.ai_analysis_running = False
            if error_callback:
                error_callback(str(e))

    def _update_chat_log_with_indicators(self, chat_log_filename: str, indicators: list):
        """Update the saved chat log file with indicators."""
        try:
            from utils import load_config
            from pathlib import Path
            import json
            
            # Get chat logs directory from config
            config = load_config()
            directories_cfg = config.get("directories", {})
            chat_logs_path_str = directories_cfg.get(
                "chat_logs", str(Path("scripts") / "data" / "chat_logs")
            )
            
            project_root = Path(__file__).resolve().parent.parent
            chat_logs_dir = project_root / chat_logs_path_str
            chat_log_path = chat_logs_dir / chat_log_filename
            
            if chat_log_path.exists():
                # Read existing chat log
                with open(chat_log_path, "r", encoding="utf-8") as f:
                    chat_data = json.load(f)
                
                # Add indicators
                chat_data["indicators"] = indicators
                
                # Save updated chat log
                with open(chat_log_path, "w", encoding="utf-8") as f:
                    json.dump(chat_data, f, ensure_ascii=False, indent=2)
                
                print(f"Updated chat log {chat_log_filename} with {len(indicators)} indicators")
            else:
                print(f"Chat log file not found: {chat_log_path}")
                
        except Exception as e:
            print(f"Error updating chat log with indicators: {e}")

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

    def _get_latest_info_log_line(self) -> str:
        """Return the most recent INFO log line (message) for this session.

        Uses the same log file location as the log viewer and filters
        by the session start time stored on the app (if present).

        Returns:
            str: The latest INFO log line's message text, or an empty string if none.
        """
        try:
            # Determine newest log file using config directory
            from utils import load_config
            config = load_config()
            logs_dir_rel = config.get("directories", {}).get("logs", "logs")
            project_root = Path(__file__).resolve().parents[1]
            logs_dir = project_root / logs_dir_rel
            if not logs_dir.exists():
                return ""

            log_files = sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not log_files:
                return ""

            log_path = log_files[0]

            latest_message = ""
            latest_time = None

            session_start = getattr(self.app, "current_session_start_time", None)

            with open(log_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.rstrip("\n")
                    if not line.strip():
                        continue

                    # Expected format: "YYYY-MM-DD HH:MM:SS - logger - LEVEL - message"
                    parts = line.split(" - ", 3)
                    if len(parts) < 3:
                        continue

                    # Parse timestamp
                    from datetime import datetime as _dt

                    try:
                        log_time = _dt.strptime(parts[0].strip(), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        log_time = None

                    # Filter by session start if available
                    if session_start and log_time and log_time < session_start:
                        continue

                    level_name = parts[2].strip()
                    if level_name != "INFO":
                        continue

                    # Extract message if present; else use entire line
                    message = parts[3].strip() if len(parts) >= 4 else line.strip()

                    # Keep the last INFO (by order; optionally compare timestamps)
                    latest_message = message
                    latest_time = log_time or latest_time

            return latest_message
        except Exception:
            return ""

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
            # Get selected models and temperatures from UI
            process_model = self.app.get_selected_process_model()
            final_model = self.app.get_selected_final_model()
            process_temperature = self.app.get_process_temperature()
            final_temperature = self.app.get_final_temperature()
            
            # Initialize managers with selected models and temperatures
            self.business_logic.initialize_managers(process_model, final_model, process_temperature, final_temperature)
            
            # Reset current lead cost at the start of processing
            self.app.after(0, self.app.cost_tracking_widget.reset_current_lead_cost)
            self.app.after(0, self.app.cost_tracking_widget.reset_model_costs)
            
            # Clear previous chunks display
            if hasattr(self.app, 'retrieved_chunks_frame'):
                self.app.after(0, self.app.retrieved_chunks_frame.clear)

            # Reset telemetry managers for new lead
            self.business_logic.reset_current_lead_cost()
            
            def progress_update(progress, status, elapsed_time):
                # Replace preset status with the most recent INFO log message if available
                latest_info = self._get_latest_info_log_line()
                display_status = latest_info if latest_info else status
                self.app.after(
                    0,
                    lambda: self.app.progress_widget.update(
                        progress, display_status, elapsed_time
                    ),
                )

            def cost_update(current_cost):
                print(f"Cost update called with: ${current_cost:.6f}")  # Debug logging
                self.app.after(
                    0,
                    lambda: self.app.cost_tracking_widget.update_current_lead_cost(current_cost)
                )
                
                # Update model-specific costs
                model_costs = self.business_logic.get_current_lead_cost_by_model()
                self.app.after(
                    0,
                    lambda: self.app.cost_tracking_widget.set_model_costs(model_costs)
                )

            def chunks_update(chunks):
                print(f"Chunks callback called with {len(chunks) if chunks else 0} chunks")  # Debug logging
                # Transform search results to display format
                transformed_chunks = self._transform_search_results_for_display(chunks)
                # Display retrieved chunks immediately when they're available
                if hasattr(self.app, 'retrieved_chunks_frame'):
                    self.app.after(0, lambda: self.app.retrieved_chunks_frame.display_chunks(transformed_chunks))

            def completion_callback(
                score, confidence, analysis, chat_log_filename=None, chunks=None, indicators=None
            ):
                # Get final cost for this lead
                final_cost = self.business_logic.get_current_lead_cost()
                self.app.after(
                    0,
                    lambda: self.app.cost_tracking_widget.add_to_session_total(final_cost)
                )
                
                # Create new lead
                new_lead = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "description": lead_text.strip(),
                    "score": score,
                    "confidence": confidence,
                    "analysis": analysis,
                    "chat_log_filename": chat_log_filename,  # Link to specific chat log
                    "cost": final_cost,  # Add cost to lead data
                    "retrieved_chunks": chunks,  # Add retrieved chunks data
                    "indicators": indicators or [],  # Add generated indicators
                }

                # Update UI on main thread
                self.app.after(0, lambda: self._handle_scoring_completion(new_lead, final_cost, chunks))

            def error_callback(error_message):
                self.app.after(0, lambda: self._handle_scoring_error(error_message))

            # Show progress and start processing
            self.app.after(0, self.app.progress_widget.show)

            # Get chunk limit from UI
            chunk_limit = self.app.get_chunk_limit()
            # Get tool call limit from UI
            tool_call_limit = self.app.get_tool_call_limit()
            
            # Before starting, set the tool_call_limit on the LeadScoringAgent's ToolManager
            try:
                if self.business_logic.lead_scoring_client and hasattr(self.business_logic.lead_scoring_client, 'tool_manager'):
                    self.business_logic.lead_scoring_client.tool_manager.tool_call_limit = tool_call_limit
            except Exception:
                pass

            self.business_logic.score_lead_process(
                lead_text.strip(),
                chunk_limit=chunk_limit,
                progress_callback=progress_update,
                completion_callback=completion_callback,
                error_callback=error_callback,
                cost_callback=cost_update,
                chunks_callback=chunks_update,
            )

        thread = threading.Thread(target=process_lead, daemon=True)
        thread.start()

        return True, "Processing started..."

    def _transform_search_results_for_display(self, search_results):
        """
        Transform Qdrant search results into the format expected by RetrievedChunksDisplayFrame.
        
        Args:
            search_results: List of Qdrant search result objects with .payload and .score attributes
            
        Returns:
            List[Dict]: Transformed chunks in display format
        """
        if not search_results:
            return []
            
        transformed_chunks = []
        
        for i, result in enumerate(search_results):
            payload = result.payload if hasattr(result, 'payload') else result
            score = getattr(result, 'score', 0.0)
            
            # Extract and format the metadata fields as content
            content = self._extract_content_from_payload(payload, i == 0)
            
            # Extract source information
            source = payload.get('source', 'Unknown Source')
            
            # Create page range information
            chunk_index = payload.get('chunk_index', 0)
            total_chunks = payload.get('total_chunks', 1)
            
            # Try to get page range info - check various possible keys
            page_range = (
                payload.get('page_range') or
                payload.get('pages') or 
                payload.get('page') or
                f"Chunk {chunk_index + 1}/{total_chunks}"
            )
            
            # Create transformed chunk in expected format
            transformed_chunk = {
                'content': content,
                'text': content,  # Backup key
                'source': source,
                'score': score,
                'page_range': str(page_range),
                'metadata': {
                    'source': source,
                    'score': score,
                    'page_range': str(page_range),
                    'chunk_index': chunk_index,
                    'total_chunks': total_chunks,
                    'case_id': payload.get('case_id'),
                    'token_count': payload.get('token_count', 0)
                }
            }
            
            transformed_chunks.append(transformed_chunk)
            
        print(f"Transformed {len(search_results)} search results into display format")  # Debug logging
        return transformed_chunks

    def _extract_content_from_payload(self, payload: dict, is_debug_result: bool = False) -> str:
        """
        Format the available metadata fields into readable content for display.
        
        Args:
            payload (dict): The payload from search result
            is_debug_result (bool): Whether to print debug info for this result
            
        Returns:
            str: Formatted content showing all available metadata fields
        """
        if is_debug_result:
            print(f"DEBUG: Formatting payload fields into content display")
        
        # Format the available fields into a readable display
        content_lines = []
        
        # Add case information
        if payload.get('case_id'):
            content_lines.append(f"📋 Case ID: {payload['case_id']}")
        
        if payload.get('Description'):
            content_lines.append(f"📝 Description: {payload['Description']}")
            
        # Add categorization
        if payload.get('Category'):
            category = payload['Category']
            if payload.get('Sub-Category'):
                category += f" - {payload['Sub-Category']}"
            content_lines.append(f"🏷️ Category: {category}")
        
        # Add date information
        if payload.get('Date'):
            content_lines.append(f"📅 Date: {payload['Date']}")
            
        # Add source information (From/To)
        if payload.get('From'):
            content_lines.append(f"👤 From: {payload['From']}")
        if payload.get('To'):
            content_lines.append(f"👥 To: {payload['To']}")
            
        # Add chunk information
        if payload.get('chunk_index') is not None and payload.get('total_chunks'):
            chunk_info = f"Chunk {payload['chunk_index'] + 1} of {payload['total_chunks']}"
            if payload.get('chunk_token_count'):
                chunk_info += f" ({payload['chunk_token_count']} tokens)"
            content_lines.append(f"📄 {chunk_info}")
        
        # Join all lines with double newlines for readability
        return "\n\n".join(content_lines) if content_lines else "No metadata available"

    def _handle_scoring_completion(self, new_lead, final_cost, chunks=None):
        """Handle successful completion of lead scoring."""
        # Add cost to session total
        self.app.cost_tracking_widget.add_to_session_total(final_cost)
        
        # Add model-specific costs to session total
        model_costs = self.business_logic.get_current_lead_cost_by_model()
        for model_name, model_cost in model_costs.items():
            self.app.cost_tracking_widget.add_model_cost(model_name, model_cost)
        
        # Note: Don't reset current lead cost here - it will be reset at the start of the next lead
        
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

        # Reset cost tracking
        self.app.cost_tracking_widget.reset_current_lead_cost()
        self.app.cost_tracking_widget.reset_session_total()
        self.app.cost_tracking_widget.reset_model_costs()

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
            "indicators": getattr(scored_lead, "indicators", []),  # Include pre-generated indicators
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
