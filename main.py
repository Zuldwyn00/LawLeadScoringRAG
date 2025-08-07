# TODO:

# Overall we need a better way to handle the metadata. We could temporalily remove a lot of the metadata fields and just use the case_id to link the chunks to the case and maybe
# the source file and other mandatory fields.

# Use a DB to store all the metadata, while qdrant only stores the ID, we use the ID to get the real metadata in the DB.

# Make rate limiting logic more robust, perhaps gradually increasing the timer after each failed request.

# TODO: AI PROMPT CHANGE: Add steps for the scoring agent to perhaps score each section and then combine the scores to get a final score rather an one main arbitrary score. This might be better for the scoring agent.
# give the AI a more consistent output by following more well-defined scoring rules.

# TODO: Unit tests

# TODO: Rest api integration for a function system.

# TODO: fix the mess that is our requirements file, currently it has all requirements listed for every import we use including the imports itself.

#TODO: The jurisdiction scoring is inflated i believe, as it adds together all the duplicated values of the settlement values to get the average, rather than just the unique values.

#TODO: Implement limit for lead-score so it doesnt go over 100 after modifiers



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
    qdrant_client = QdrantManager()
    embedding_client = AzureClient(client_config='text_embedding_3_small')
    # Create separate clients to avoid message history conflicts
    summarizer_client = AzureClient(client_config="gpt-o4-mini")
    scorer_client = AzureClient(client_config="gpt-o4-mini")
    
    summarizer = SummarizationClient(summarizer_client)
    scorer = LeadScoringClient(scorer_client, summarizer=summarizer)
    
    new_lead_description = (
            "Slip and fall at commercial property - liability facts sharply disputed. "
             "Client, a 45-year-old delivery driver, reports falling on a wet floor inside the vestibule "
             "of a strip-mall pharmacy in Suffolk County on a rainy afternoon "
             "three weeks ago (exact date unclear). Client claims the store failed to place warning signs "
             "or mats near the entrance during inclement weather. "
             "Incident resulted in immediate pain in lower back and left knee. Client drove self to urgent care "
             "where X-rays showed no fractures but noted 'soft tissue strain.' Follow-up with primary doctor "
             "recommended MRI but client has not yet scheduled due to insurance delays. "
             "Store manager provided incident report number but refused copy to client. Security camera footage "
             "allegedly exists but store claims it 'doesn't show the fall clearly' and won't release without subpoena. "
             "One witness - another customer - told client they 'saw water on the floor' but left before giving contact info. "
             "claiming client 'failed to watch where they were walking' and that 'rainy day procedures were in place.' "
             "Client has photos of the area taken day after incident showing wet floor signs now present, "
             "but no photos from actual incident time. "
             "Medical bills to date: $1,800 urgent care + ongoing physical therapy estimated $3,000-5,000. "
             "Two weeks lost work as delivery driver - income loss approximately $2,400. "
             "Client's shoes were rubber-soled work boots - store might argue they should have provided better traction. "
             "Client admits they were carrying a package and might not have been looking directly at floor. "
             "Store's maintenance logs for that day have not been provided despite request. "
             "Weather service confirms steady rain that afternoon, creating questions about reasonable care standards. "
             "No prior complaints about wet floors found in online reviews, but similar incident reported at "
             "different location of same pharmacy chain last year."
             "Your confidence should begin at a maximum score of 20 before tool calls"
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
