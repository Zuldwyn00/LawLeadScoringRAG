#TODO:
# Include case_id in the metadata so we can link the chunks to the case, source only links the chunk to the one source file
# Currently all I did was add a case_id field, but no logic to connect the chunks to the case.

# get rid of or streamline DataChunk, it's pointless. Or we could use a pydantic model for it to give it some use for data validation.

# Overall we need a better way to handle the metadata. We could temporalily remove a lot of the metadata fields and just use the case_id to link the chunks to the case and maybe 
# the source file and other mandatory fields.

# Use a DB to store all the metadata, while qdrant only stores the ID, we use the ID to get the real metadata in the DB.

# Add a check for files that are too laege to process. Split them into chunks and process them then combine the final output though this may arise rate limit issues. Perhaps we process them completely seperately
# Maybe we can change the return type to a list of strings instead of a single string so it can handle multiple strings at once as a return.

#TODO: AI PROMPT CHANGE: Add steps for the scoring agent to perhaps score each section and then combine the scores to get a final score rather an one main arbitrary score. This might be better for the scoring agent.
# give the AI a more consistent output by following more well-defined scoring rules.

#CHECK IF SCORE IS ACTUALLY RECIEVING CASE DATA, IT SEEMS LIKE IT IS NOT. I ADDED A LINE TO THE PROMPT ASKING IT TO GET THE CASE IDS, BUT IT IS NOT DOING IT.

from scripts.filemanagement import FileManager, ChunkData, apply_ocr
from scripts.aiclients import EmbeddingManager, ChatManager
from scripts.vectordb import QdrantManager
from pathlib import Path
from utils import ensure_directories, load_config, setup_logger, find_files, load_from_json, save_to_json, count_tokens

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)

def embedding_test(filepath: str, case_id: int):
    ensure_directories()
    chat_manager = ChatManager()
    embeddingmanager = EmbeddingManager()
    filemanager = FileManager()
    qdrantmanager = QdrantManager()
    files = find_files(Path(filepath))
    progress = len(files)
    print(f"Found {progress} files")
    qdrantmanager.create_collection(collection_name="case_files")
    processed_files_data = load_from_json()
    case_id = case_id
    
    for file in files:
        filename_str = str(file)

        if processed_files_data.get(str(case_id)) and filename_str in processed_files_data[str(case_id)]:
            progress -= 1
            print(f"Skipping already processed file: {file.name}")
            continue
        print(f"Processing file {file.name}")
        file_text = filemanager.get_text_from_file(str(file))
        file_chunks = filemanager.text_splitter(file_text)

        datachunks = []
        for i, chunk in enumerate(file_chunks):
            chunk_embedding = embeddingmanager.get_embeddings(chunk.page_content)
            
            datachunk = ChunkData()
            datachunk.set_case_id(case_id)
            datachunk.set_source(str(file))
            datachunk.set_text(chunk.page_content)
            
            chunk_metadata = chat_manager.define_metadata(chunk.page_content, str(file), case_id)
            datachunk.set_metadata(chunk_metadata)
            
            datachunk.set_embeddings(chunk_embedding)
            datachunks.append(datachunk)

        embeddings = [chunk.get_embeddings() for chunk in datachunks]
        metadatas = [chunk.get_metadata() for chunk in datachunks]

        qdrantmanager.add_embeddings_batch(collection_name="case_files", embeddings=embeddings, metadatas=metadatas, vector_name="chunk")
        print(f"Added {len(datachunks)} embeddings to Qdrant for {file.stem}")

        if str(case_id) not in processed_files_data:
            processed_files_data[str(case_id)] = []
        
        processed_files_data[str(case_id)].append(filename_str)
        save_to_json(processed_files_data)
        progress -= 1
        print(f"Progress: {len(files) - progress}/{len(files)}")
        print(f"Finished processing and marked {file.name} as complete.")

def score_test():
    qdrantmanager = QdrantManager()
    chat_manager = ChatManager()
    embeddingmanager = EmbeddingManager()

    new_lead_description = (
        "A potential client from Nassau County is reporting a slip and fall that occurred four months ago inside a local shopping mall. "
        "The client claims they were walking near the food court on a weekday afternoon when they slipped on a recently mopped, wet floor that had no warning signs posted. "
        "They did not fall completely but their leg went out from under them, causing them to twist their knee before catching themselves on a nearby table. "
        "The client states they did not see the wet floor because the lighting in that area was dim and reflected off the polished surface, making it difficult to spot the water. "
        "No one witnessed the incident, and they did not report it to mall security or any of the storefronts at the time. "
        "The client has a pre-existing diagnosis of osteoarthritis in both knees. They first sought medical attention three weeks after the incident with their primary care physician. "
        "After the pain did not subside, they recently saw a specialist who diagnosed a medial meniscus tear, complicating their pre-existing arthritis. "
        "They are now facing recommendations for physical therapy and potentially arthroscopic surgery."
    )
    question_vector = embeddingmanager.get_embeddings(new_lead_description)
    search_results = qdrantmanager.search_vectors(collection_name="test_chunks", query_vector=question_vector, vector_name="chunk", limit=5)
    
    historical_context = qdrantmanager.get_context(search_results)

    final_analysis = chat_manager.score_lead(
        new_lead_description=new_lead_description,
        historical_context=historical_context
    )
    print(final_analysis)

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
    embedding_test(filepath=r"C:\Users\Justin\Desktop\testdocs", case_id=1050076)
    embedding_test(filepath=r"C:\Users\Justin\Desktop\testdocs2", case_id=2211830)
    embedding_test(filepath=r"C:\Users\Justin\Desktop\testdocs3", case_id=1637313)
    embedding_test(filepath=r"C:\Users\Justin\Desktop\testdocs4", case_id=1660355)
    embedding_test(filepath=r"C:\Users\Justin\Desktop\testdocs5", case_id=1508908)
    
if __name__ == "__main__":
    main()

