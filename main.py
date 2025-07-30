# TODO:
# Include case_id in the metadata so we can link the chunks to the case, source only links the chunk to the one source file
# Currently all I did was add a case_id field, but no logic to connect the chunks to the case.

# get rid of or streamline DataChunk, it's pointless. Or we could use a pydantic model for it to give it some use for data validation.

# Overall we need a better way to handle the metadata. We could temporalily remove a lot of the metadata fields and just use the case_id to link the chunks to the case and maybe
# the source file and other mandatory fields.

# Use a DB to store all the metadata, while qdrant only stores the ID, we use the ID to get the real metadata in the DB.

# Make rate limiting logic more robust, perhaps gradually increasing the timer after each failed request.

# TODO: AI PROMPT CHANGE: Add steps for the scoring agent to perhaps score each section and then combine the scores to get a final score rather an one main arbitrary score. This might be better for the scoring agent.
# give the AI a more consistent output by following more well-defined scoring rules.

# TODO: Unit tests

# TODO: Rest api integration for a function system.

# TODO: fix the mess that is our requirements file, currently it has all requirements listed for every import we use including the imports itself.I

import qdrant_client
from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.aiclients import EmbeddingManager, ChatManager
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from pathlib import Path
from utils import (
    ensure_directories,
    load_config,
    setup_logger,
    find_files,
    load_from_json,
    save_to_json,
)

from scripts.clients import SummarizationClient, LeadScoringClient, AzureClient, BaseClient

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
    azure_client = AzureClient(client_type="gpt-o4-mini")

    embedding_client = AzureClient(client_type='text_embedding_3_small')
    lead_client = LeadScoringClient(client=azure_client)
    
    new_lead_description = (
        "The client located in Suffolk County was involved in a slip and fall. The client states that they were in their apartment complex on the sidewalk walking over to meet their girlfriend."
        "The client states that they went to pick up their girlfriend with a large hug, and in doing so after walking 2 steps forward with her in his arms he stepped badly on a flowerbed next to the sidewalk and sprained his ankle"
        "The client went to an urgent care after 3 days with an issue of his ankle clicking with every step and had an x-ray done, the initial x-ray found nothing."
        "The client went to an orthpedist after 1 week after the initial injury and got another x-ray which showed a very small alread-healing fracture."
        "After 2 months with the injury the clients ankle stated by them to be weakened and gets injured much more easily where walking on uneven terrain can cause another near-ankle sprain if not careful, the clicking in the ankle persists"
        "The client is scheduled for an MRI on their ankle on August 12th, 3 months after the initial injury as they had to wait for insurance approval. The medical invervention has been kept up-date as necessary and the client has gotten medical care as fast as they have been allowed."
    )
    question_vector = embedding_client.get_embeddings(new_lead_description)
    search_results = qdrant_client.search_vectors(
        collection_name="case_files",
        query_vector=question_vector,
        vector_name="chunk",
        limit=10,
    )
    
    historical_context = qdrant_client.get_context(search_results)

    final_analysis = lead_client.score_lead(
        new_lead_description=new_lead_description, historical_context=historical_context
    )
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

    mod = jurisdiction_manager.get_jurisdiction_modifier("Suffolk County")
    print(mod)


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


def main():
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs', 10550076)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs2', 2211830)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs3', 1637313)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs4', 1660355)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs5', 1508908)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs6', 1550736)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs7', 2369954)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs8', 1989212)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs9', 997000)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs10', 1885788)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs11', 2081492)
    embedding_test(r'C:\Users\Justin\Desktop\testdocsmain\testdocs12', 2207174)
    

if __name__ == "__main__":
    main()
