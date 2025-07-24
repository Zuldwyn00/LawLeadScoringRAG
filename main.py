#TODO:
# Include case_id in the metadata so we can link the chunks to the case, source only links the chunk to the one source file
# Currently all I did was add a case_id field, but no logic to connect the chunks to the case.

# get rid of or streamline DataChunk, it's pointless. Or we could use a pydantic model for it to give it some use for data validation.

# Overall we need a better way to handle the metadata. We could temporalily remove a lot of the metadata fields and just use the case_id to link the chunks to the case and maybe 
# the source file and other mandatory fields.

# Use a DB to store all the metadata, while qdrant only stores the ID, we use the ID to get the real metadata in the DB.

# Make rate limiting logic more robust, perhaps gradually increasing the timer after each failed request.

#TODO: AI PROMPT CHANGE: Add steps for the scoring agent to perhaps score each section and then combine the scores to get a final score rather an one main arbitrary score. This might be better for the scoring agent.
# give the AI a more consistent output by following more well-defined scoring rules.


from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.aiclients import EmbeddingManager, ChatManager, extract_score_from_response
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from pathlib import Path
from utils import ensure_directories, load_config, setup_logger, find_files, load_from_json, save_to_json

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
    processed_files_data = load_from_json()
    case_id = case_id
    
    for file in files:
        filename_str = str(file)

        if processed_files_data.get(str(case_id)) and filename_str in processed_files_data[str(case_id)]:
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
        "The client, a 45-year-old construction worker from Hempstead, Nassau County, slipped and fell while exiting a Whole Foods in Garden City last month during a winter storm. "
        "He claims the automatic sliding doors created a 'wind tunnel effect' that blew snow and ice into the vestibule area, making it extremely slippery. "
        "The client sustained what appears to be a torn meniscus requiring arthroscopic surgery, but he admits he was wearing work boots with worn treads and was carrying heavy groceries in both hands while talking on his phone. "
        "Store security footage shows the incident, but also reveals the client walked past two 'Caution: Wet Floor' signs and a store employee was actively salting the area just 10 minutes before the fall. "
        "The client has a documented history of three prior workers' compensation claims for knee injuries over the past eight years, including one surgery on the same knee two years ago. "
        "Two witnesses saw the fall - one is the client's adult daughter who was shopping with him, and the other is an elderly customer who has since been diagnosed with early-stage dementia. "
        "The client waited four days to seek medical treatment, initially going to a chiropractor before seeing an orthopedic surgeon. "
        "Whole Foods' insurance carrier has already retained counsel and is claiming the client was intoxicated, though no sobriety testing was performed and the client denies drinking. "
        "The store manager claims they have a written snow removal protocol that was followed, but admits the specific area where the client fell had been problematic all winter due to the door design. "
        "The client's medical bills are currently at $35,000 and climbing, he's been out of work for six weeks, but he's also scheduled to retire with full pension benefits in eight months."
    )
    question_vector = embeddingmanager.get_embeddings(new_lead_description)
    search_results = qdrantmanager.search_vectors(collection_name="case_files", query_vector=question_vector, vector_name="chunk", limit=20)
    
    historical_context = qdrantmanager.get_context(search_results)

    final_analysis = chat_manager.score_lead(
        new_lead_description=new_lead_description,
        historical_context=historical_context
    )
    print(final_analysis)

def jurisdiction_score_test():
    qdrant_manager = QdrantManager()
    jurisdiction_manager = JurisdictionScoreManager()
    scores = {}

    jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction('case_files', 'Suffolk County')
    score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    scores['Suffolk County'] = score.get('jurisdiction_score')

    jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction('case_files', 'Nassau County')
    score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    scores['Nassau County'] = score.get('jurisdiction_score')
    
    jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction('case_files', 'Queens County')
    score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    scores['Queens County'] = score.get('jurisdiction_score')

    #jurisdiction_cases = qdrant_manager.get_cases_by_jurisdiction('case_files', 'Kings County')
    #score = jurisdiction_manager.score_jurisdiction(jurisdiction_cases)
    #scores['Kings County'] = score.get('jurisdiction_score')


    jurisdiction_manager.save_to_json(data=scores)

    mod = jurisdiction_manager.get_jurisdiction_modifier('Suffolk County')
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

    jurisdiction_score_test()
    


if __name__ == "__main__":
    main()

