#TODO:
# Include case_id in the metadata so we can link the chunks to the case, source only links the chunk to the one source file
# Currently all I did was add a case_id field, but no logic to connect the chunks to the case.

# get rid of or streamline DataChunk, it's pointless. Or we could use a pydantic model for it to give it some use for data validation.

# Batch process the chunks instead of one by one, go back to using embed_documents instead of embed_query but then we need to fix the metadata logic again. 
# We could also use the batch_size parameter in the embed_documents function to batch the chunks.

# Overall we need a better way to handle the metadata. We could temporalily remove a lot of the metadata fields and just use the case_id to link the chunks to the case and maybe 
# the source file and other mandatory fields. I also changed it right now after writing this to use the same metadata for all chunks, which is better because now we arent doing 100x api calls for every chunk. This might fix
# most of the metadata issues I just described, but I didnt look at the code yet.

# Add way to avoid processing the same file multiple times if processing is interrupted and we need to restart. Perhaps we just store them, then upload all vectors at once so if it fails we never uploaded anything anyways.
# Or we could use a flag to check if the file has already been processed in a json file, perhaps we can even use the qdrant database for this if it allows us to do so easily. Otherwise the JSON can also serve the double purpose
# of storing the case_id, source file, and other mandatory fields to make linking the chunks to the case and source file easier.

# Use a DB to store all the metadata, while qdrant only stores the ID, we use the ID to get the real metadata in the DB.

from scripts.filemanagement import FileManager, with_pdf, ChunkData, apply_ocr
from scripts.aiclients import EmbeddingManager, ChatManager
from scripts.vectordb import QdrantManager
from pathlib import Path
from utils import ensure_directories, load_config, setup_logger, find_files, load_from_json, save_to_json

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)

def embedding_test():
    ensure_directories()
    chat_manager = ChatManager()
    embeddingmanager = EmbeddingManager()
    filemanager = FileManager()
    qdrantmanager = QdrantManager()
    files = find_files(Path(r"C:\Users\Justin\Desktop\testdocs4"))
    print(f"Found {len(files)} files")

    processed_files_data = load_from_json()
    case_id = 3
    for file in files:
        filename_str = str(file)

        if processed_files_data.get(str(case_id)) and filename_str in processed_files_data[str(case_id)]:
            print(f"Skipping already processed file: {file.name}")
            continue
        print(f"Processing file {file.name}")
        file_text = filemanager.get_text_from_file(str(file))
        file_chunks = filemanager.text_splitter(file_text)
        text_metadata = chat_manager.define_metadata(file_text['content'], str(file), case_id)
        for chunk in file_chunks:
            datachunk = ChunkData()
            datachunk.set_case_id(case_id)
            datachunk.set_source(str(file))
            datachunk.set_text(chunk.page_content)
            datachunk.set_metadata(text_metadata)
            datachunk.set_embeddings(embeddingmanager.get_embeddings(chunk.page_content))
            qdrantmanager.add_embedding(collection_name="test_chunks", embedding=datachunk.get_embeddings(), metadata=datachunk.get_metadata(), vector_name="chunk")
            print(f"Added embedding to Qdrant for {file.stem}")

        if str(case_id) not in processed_files_data:
            processed_files_data[str(case_id)] = []
        
        processed_files_data[str(case_id)].append(filename_str)
        save_to_json(processed_files_data)
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

def main():
    embedding_test()


if __name__ == "__main__":
    main()

