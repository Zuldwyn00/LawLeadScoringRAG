# ─── TODO: PROJECT ORGANIZATION ──────────────────────────────────────────────────

# ─── ARCHITECTURE & INFRASTRUCTURE ───────────────────────────────────────────────
# TODO: Implement database storage for metadata
#   - Use a DB to store all the metadata, while qdrant only stores the ID
#   - Use the ID to get the real metadata in the DB
#   - This will help with the metadata handling issues mentioned below

# TODO: Improve metadata handling system
#   - We need a better way to handle the metadata
#   - Could temporarily remove many metadata fields and just use case_id to link chunks to cases
#   - Include source file and other mandatory fields

# ─── AI & SCORING IMPROVEMENTS ──────────────────────────────────────────────────
# TODO: Enhance AI prompt for scoring agent
#   - Add steps for the scoring agent to score each section separately
#   - Combine section scores to get a final score rather than one main arbitrary score

# TODO: Implement settlement value/outcome retrieval
#   - Consider getting average value of similar case_type in same jurisdiction as fallback

# TODO: Complete jurisdiction scoring system
#   - Create better method for getting all jurisdiction data in one search
#   - Method should return dict of all required info for the jurisdiction scoring system
#   - Re-use data without weird calls and roundabout ways
#   - Complete the BAYESIAN_SHRINKAGE() method (currently placeholder based on hard-coded values)
#   - Currently overwrites original scores after processing and then applies bayesian

# ─── API & INTEGRATION ──────────────────────────────────────────────────────────
# TODO: REST API integration for function system

# ─── PERFORMANCE & OPTIMIZATION ──────────────────────────────────────────────────
# TODO: Improve rate limiting logic
#   - Make rate limiting logic more robust
#   - Perhaps gradually increase timer after each failed request

# TODO: Replace Tika with faster alternative
#   - Get rid of Tika, it's slow as hell
#   - Remember we changed to it because other options gave too much garbage text like /n/n/n
#   - Find better balance between speed and text quality

# ─── DATA TRACKING & METRICS ────────────────────────────────────────────────────
# TODO: Implement metrics tracking system
#   - Easily grab all needed data from AI instance rather than returning from functions
#   - Use elapsed time that manager tracks for better loading bar (though may not matter for non-UI usage)

# ─── DATA QUALITY & SECURITY ────────────────────────────────────────────────────
# TODO: Address sensitive data in chat logs
#   - Potentially sensitive data is being stored in chat logs
#   - This happens through get_context and summarization methods
#   - We don't summarize if too short, which means including sensitive data
#   - Implement system to avoid PPI without direct AI intervention
#   - Once we have DB access, could redact all names using case data from DB

# TODO: Evaluate quality multiplier necessity
#   - DISABLED QUALITY MULTIPLIER FOR NOW BY COMMENTING IT OUT
#   - Is it necessary? Seems like making scoring more complicated for no reason
#   - How does it help? Why would certain cases affect score less just because chunk has fewer data points?
#   - That doesn't mean entire case doesn't have that data, seems redundant
#   - We already have de-duplication implemented
#   - Leave for now and determine in future if we want it on case-level rather than chunk-level

# ─── UI & USER EXPERIENCE ───────────────────────────────────────────────────────
# TODO: Fix Clear All button functionality
#   - Clear All button does nothing

from multiprocessing import process

import qdrant_client
from scripts.filemanagement import (
    FileManager,
    ChunkData,
    apply_ocr,
    get_text_from_file,
    discover_case_folders,
)
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from pathlib import Path
from qdrant_client.http import models

from utils import *
from scripts.clients import (
    SummarizationAgent,
    LeadScoringAgent,
    MetadataAgent,
    AzureClient,
)
from scripts.clients.agents.utils import CaseContextEnricher

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)


def embedding_test(filepath: str, case_id: int):
    ensure_directories()
    metadata_agent = MetadataAgent(client=AzureClient(client_config="o4-mini"))
    embedding_agent = AzureClient(client_config="text_embedding_3_large")
    filemanager = FileManager()
    qdrantmanager = QdrantManager()

    vector_config = {
        "chunk": models.VectorParams(size=3072, distance=models.Distance.COSINE),
    }
    qdrantmanager.create_collection("case_files_large", vector_config=vector_config)
    files = find_files(Path(filepath))
    progress = len(files)
    print(f"Found {progress} files")
    processed_files_data = load_from_json()

    for file in files:
        filename_str = str(file)

        if (
            processed_files_data.get(str(case_id))
            and filename_str in processed_files_data[str(case_id)]
        ):
            progress -= 1
            print(f"Skipping already processed file: {file.name}")
            continue
        print(f"Processing file {file.name}")
        file_text = get_text_from_file(str(file))
        file_chunks = filemanager.text_splitter(file_text)

        datachunks = []
        for i, chunk in enumerate(file_chunks):
            chunk_embedding = embedding_agent.get_embeddings(chunk.page_content)

            datachunk = ChunkData()
            datachunk.set_case_id(case_id)
            datachunk.set_source(str(file))
            datachunk.set_text(chunk.page_content)

            chunk_metadata = metadata_agent.define_metadata(
                chunk.page_content, str(file), case_id
            )
            datachunk.set_metadata(chunk_metadata)

            datachunk.set_embeddings(chunk_embedding)
            datachunks.append(datachunk)

        embeddings = [chunk.get_embeddings() for chunk in datachunks]
        metadatas = [chunk.get_metadata() for chunk in datachunks]

        qdrantmanager.add_embeddings_batch(
            collection_name="case_files_large",
            embeddings=embeddings,
            metadatas=metadatas,
            vector_name="chunk",
        )
        print(f"Added {len(datachunks)} embeddings to Qdrant for {file.stem}")

        if str(case_id) not in processed_files_data:
            processed_files_data[str(case_id)] = []

        processed_files_data[str(case_id)].append(filename_str)
        save_to_json(processed_files_data)
        progress -= 1
        print(f"Progress: {len(files) - progress}/{len(files)}")
        print(f"Finished processing and marked {file.name} as complete.")


def process_all_case_folders(main_folder_path: str) -> None:
    """
    Automatically processes all case folders in a main directory.

    This function discovers all subfolders containing case documents,
    extracts the case ID from filenames, and runs embedding_test
    for each folder automatically.

    Args:
        main_folder_path (str): Path to the main folder containing case subfolders
                               (e.g., "C:\\Users\\Justin\\Desktop\\testdocsmain")

    Example:
        process_all_case_folders("C:\\Users\\Justin\\Desktop\\testdocsmain")

        This will automatically process:
        - testdocsmain/testdocs/ with case_id extracted from filenames
        - testdocsmain/testdocs2/ with case_id extracted from filenames
        - testdocsmain/testdocs3/ with case_id extracted from filenames
        - etc.
    """
    try:
        # Discover all case folders and their case IDs
        case_folders = discover_case_folders(main_folder_path)

        if not case_folders:
            print("No valid case folders found in %s" % main_folder_path)
            return

        print("Found %s case folders to process:" % len(case_folders))
        for folder_path, case_id in case_folders:
            print("  - %s: Case ID %s" % (Path(folder_path).name, case_id))

        # Process each case folder
        for i, (folder_path, case_id) in enumerate(case_folders, 1):
            folder_name = Path(folder_path).name
            print("\n" + "=" * 60)
            print("Processing folder %s/%s: %s" % (i, len(case_folders), folder_name))
            print("Case ID: %s" % case_id)
            print("Path: %s" % folder_path)
            print("=" * 60)

            try:
                # Apply OCR to all PDF files in the folder first
                print("Applying OCR to PDF files in %s..." % folder_name)
                run_ocr_on_folder(folder_path)
                print("✓ OCR processing completed for %s" % folder_name)
                
                # Call embedding_test for this folder
                embedding_test(folder_path, case_id)
                print("✓ Successfully processed %s" % folder_name)

            except Exception as e:
                print("✗ Error processing %s: %s" % (folder_name, e))
                logger.error("Failed to process folder %s: %s" % (folder_path, e))
                continue

        print("\n" + "=" * 60)
        print("Completed processing all %s case folders!" % len(case_folders))
        print("=" * 60)

    except Exception as e:
        print("Error in process_all_case_folders: %s" % e)
        logger.error("Failed to process case folders: %s" % e)


def score_test():
    ensure_directories()
    qdrant_client = QdrantManager()
    embedding_client = AzureClient(client_config="text_embedding_3_large")
    summarizer = SummarizationAgent(AzureClient(client_config="o4-mini"))

    scorer_kwargs = {
        "confidence_threshold": 85,
        "final_model": "gpt-5-chat",
        "final_model_temperature": 0.0,
    }
    scorer = LeadScoringAgent(
        AzureClient(client_config="gpt-5-mini"), summarizer=summarizer, **scorer_kwargs
    )

    new_lead_description = (
        "Potential client – Nassau County slip-and-fall. A 52-year-old office "
        "manager was attending a corporate holiday party at the Marriott Hotel "
        "in Garden City on December 15th at approximately 8:30 PM. The event "
        "was held in the hotel's main ballroom, which had been decorated with "
        "holiday lights and garlands. The plaintiff alleges she slipped on a "
        "wet spot near the bar area and fell, sustaining a fractured left "
        "wrist and torn rotator cuff in her right shoulder. She was taken by "
        "ambulance to Nassau University Medical Center where she underwent "
        "surgery to repair the wrist fracture with internal fixation. The "
        "shoulder injury required arthroscopic surgery three weeks later. "
        "She was out of work for 8 weeks and has ongoing physical therapy. "
        "The plaintiff claims the hotel failed to properly maintain the floor "
        "and should have had warning signs or mats in the bar area. However, "
        "security camera footage shows the plaintiff had consumed several "
        "cocktails over the course of the evening, and witnesses reported "
        "she appeared to be unsteady on her feet before the fall. The hotel "
        "maintains they had proper floor maintenance protocols in place, "
        "including regular inspections every 30 minutes, and that the wet "
        "spot was created by other patrons' spilled drinks, not by hotel "
        "negligence. The plaintiff's blood alcohol content was 0.12% when "
        "tested at the hospital. Additionally, the plaintiff was wearing "
        "high-heeled shoes with smooth soles, which the defense will argue "
        "contributed to the fall. The hotel has offered a $25,000 settlement, "
        "but the plaintiff's attorney believes the case is worth $150,000 "
        "given the surgeries and lost wages. The case hinges on whether the "
        "hotel had constructive notice of the dangerous condition and whether "
        "the plaintiff's own negligence was a substantial factor in causing "
        "her injuries."
    )
    question_vector = embedding_client.get_embeddings(new_lead_description)
    
    # Get chunk limit from config
    chunk_limit = config.get("aiconfig", {}).get("vector_search", {}).get("default_chunk_limit", 10)
    
    search_results = qdrant_client.search_vectors(
        collection_name="case_files",
        query_vector=question_vector,
        vector_name="chunk",
        limit=chunk_limit,
    )

    historical_context = qdrant_client.get_context(search_results)

    # score_lead now returns (analysis, chat_log_filename)
    final_analysis, chat_log_filename = scorer.score_lead(
        new_lead_description=new_lead_description, historical_context=historical_context
    )
    # No need to call dump_chat_log here since score_lead already does it
    print(final_analysis)
    print(f"Chat log saved as: {chat_log_filename}")

def jurisdiction_score_test():
    qdrant_manager = QdrantManager()
    jurisdiction_manager = JurisdictionScoreManager()
    scores = {}
    jurisdictions_to_process = [
        "Suffolk County",
        "Nassau County",
        "Queens County",
        "Kings County"
    ]

    for jurisdiction in jurisdictions_to_process:
        jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction('case_files_large', jurisdiction)
        score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
        scores[jurisdiction] = score.get("jurisdiction_score")

    jurisdiction_manager.save_to_json(data=scores)
    print("Raw jurisdiction scores:")
    for jurisdiction, score in scores.items():
        print(f"  {jurisdiction}: ${score:,.2f}")

    # Step 2: Apply Bayesian shrinkage
    print("\nApplying Bayesian shrinkage...")
    case_counts = qdrant_manager.get_all_case_ids_by_jurisdiction("case_files_large")
    adjusted_scores = jurisdiction_manager.bayesian_shrinkage(case_counts)

    print("\nFinal modifiers:")
    for jurisdiction in jurisdictions_to_process:
        print(f"{jurisdiction}: {jurisdiction_manager.get_jurisdiction_modifier(jurisdiction):.3f}x")

def run_ocr_on_folder(folder_path: str):
    """
    Applies OCR to all PDF files in a specified folder.

    Args:
        folder_path (str): The path to the folder containing PDF files.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        logger.error(f"Provided path '{folder_path}' is not a valid directory.")
        return

    pdf_files = list(folder.glob("*.pdf"))
    if not pdf_files:
        logger.info(f"No PDF files found in '{folder_path}'.")
        return

    logger.info(f"Found {len(pdf_files)} PDF files to process.")
    for pdf_file in pdf_files:
        try:
            apply_ocr(str(pdf_file))
        except Exception as e:
            logger.error(f"An error occurred while processing {pdf_file.name}: {e}")


def test_case_enrichment(case_id: int):
    qdrant_client = QdrantManager()
    context_enricher = CaseContextEnricher(qdrant_client)
    print(context_enricher.build_context_message(case_id))


def main():
    jurisdiction_score_test()

if __name__ == "__main__":
    main()
