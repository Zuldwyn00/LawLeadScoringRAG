# TODO:

# Overall we need a better way to handle the metadata. We could temporalily remove a lot of the metadata fields and just use the case_id to link the chunks to the case and maybe
# the source file and other mandatory fields.

# Use a DB to store all the metadata, while qdrant only stores the ID, we use the ID to get the real metadata in the DB.

# Make rate limiting logic more robust, perhaps gradually increasing the timer after each failed request.

# TODO: AI PROMPT CHANGE: Add steps for the scoring agent to perhaps score each section and then combine the scores to get a final score rather an one main arbitrary score. This might be better for the scoring agent.
# give the AI a more consistent output by following more well-defined scoring rules.

# TODO: Unit tests

# TODO: Rest api integration for a function system.

#TODO: The jurisdiction scoring is inflated i believe, as it adds together all the duplicated values of the settlement values to get the average, rather than just the unique values.

#TODO: Finish Caching system


from numpy import save
import qdrant_client
from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.aiclients import EmbeddingManager, ChatManager
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from pathlib import Path
from utils import *

from scripts.clients.utils.chatlog import dump_chat_log
from scripts.clients import SummarizationClient, LeadScoringClient, AzureClient

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)


def embedding_test(filepath: str, case_id: int):
    ensure_directories()
    chat_manager = ChatManager()
    embeddingmanager = EmbeddingManager()
    filemanager = FileManager()
    qdrantmanager = QdrantManager()
    qdrantmanager.create_collection('case_files')
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
            chunk_embedding = embeddingmanager.get_embeddings(chunk.page_content)

            datachunk = ChunkData()
            datachunk.set_case_id(case_id)
            datachunk.set_source(str(file))
            datachunk.set_text(chunk.page_content)

            chunk_metadata = chat_manager.define_metadata(
                chunk.page_content, str(file), case_id
            )
            datachunk.set_metadata(chunk_metadata)

            datachunk.set_embeddings(chunk_embedding)
            datachunks.append(datachunk)

        embeddings = [chunk.get_embeddings() for chunk in datachunks]
        metadatas = [chunk.get_metadata() for chunk in datachunks]

        qdrantmanager.add_embeddings_batch(
            collection_name="case_files",
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


def score_test():
    ensure_directories()
    qdrant_client = QdrantManager()
    embedding_client = AzureClient(client_config='text_embedding_3_small')
    summarizer = SummarizationClient(AzureClient(client_config="gpt-o4-mini"))
    
    scorer_kwargs = {'confidence_threshold': 80, 'final_model': 'gpt-4.1', 'final_model_temperature': 0.0}
    scorer = LeadScoringClient(AzureClient(client_config="gpt-o4-mini"), sumarizer=summarizer, **scorer_kwargs)
    
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
    search_results = qdrant_client.search_vectors(
        collection_name="case_files",
        query_vector=question_vector,
        vector_name="chunk",
        limit=10,
    )
    
    historical_context = qdrant_client.get_context(search_results)

    final_analysis = scorer.score_lead(
        new_lead_description=new_lead_description, historical_context=historical_context
    )
    dump_chat_log(scorer.client.message_history)
    print(final_analysis)


def jurisdiction_score_test():
    qdrant_manager = QdrantManager()
    jurisdiction_manager = JurisdictionScoreManager()
    scores = {}

    jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction(
        "case_files", "Suffolk County"
    )
    score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    scores["Suffolk County"] = score.get("jurisdiction_score")

    jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction(
        "case_files", "Nassau County"
    )
    score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    scores["Nassau County"] = score.get("jurisdiction_score")

    jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction(
        "case_files", "Queens County"
    )
    score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    scores["Queens County"] = score.get("jurisdiction_score")

    # jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction('case_files', 'Kings County')
    # score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    # scores['Kings County'] = score.get('jurisdiction_score')

    jurisdiction_manager.save_to_json(data=scores)

    print(jurisdiction_manager.get_jurisdiction_modifier("Suffolk County"))
    print(jurisdiction_manager.get_jurisdiction_modifier("Nassau County"))
    print(jurisdiction_manager.get_jurisdiction_modifier("Queens County"))


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

def settlement_value_test():
    qdrant_manager = QdrantManager()
    cases = qdrant_manager.get_cases_by_jurisdiction('case_files', 'Suffolk County')
    settlements = qdrant_manager.get_case_settlements(cases)
    #give the AI the information from extract_highest_settlements so it always knows the outcome of cases it gets
    values = extract_highest_settlements(settlements)
    print(values)

def main():
   score_test()

if __name__ == "__main__":
    main()