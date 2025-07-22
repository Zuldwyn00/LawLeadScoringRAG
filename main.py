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


from numpy import False_
from scripts.filemanagement import FileManager, ChunkData, apply_ocr, get_text_from_file
from scripts.aiclients import EmbeddingManager, ChatManager
from scripts.vectordb import QdrantManager
from scripts.jurisdictionscoring import JurisdictionScoreManager
from pathlib import Path
from utils import ensure_directories, load_config, setup_logger, find_files, load_from_json, save_to_json
from qdrant_client.http import models

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
        "The client, a resident of Suffolk County, was attending a backyard barbecue at their neighbor's house last weekend. "
        "They claim they slipped and fell on wet grass near a children's sprinkler that had been running for several hours, resulting in a dislocated shoulder. "
        "The client admits to having consumed a couple of beers over the course of the afternoon. "
        "The neighbor, a close friend, is hesitant to involve their homeowner's insurance and has not provided any details. "
        "The client received initial treatment at an urgent care clinic but has not yet seen an orthopedic specialist. "
        "It is unclear if any of the other party guests directly witnessed the fall."
    )
    question_vector = embeddingmanager.get_embeddings(new_lead_description)
    search_results = qdrantmanager.search_vectors(collection_name="case_files", query_vector=question_vector, vector_name="chunk", limit=10)
    
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

def cleanup_settlement_score_data(dry_run=True):
    """
    Removes all data related to files that have settlement_value chunks.
    
    This function will:
    1. Find all chunks with settlement_value field
    2. Collect unique source files from those chunks
    3. Remove those source files from processed_files.json
    4. Delete ALL chunks from the database that have those source files
    
    Args:
        dry_run (bool): If True, shows what would be deleted without making changes
    """
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"Starting settlement score data cleanup ({mode})...")
    
    try:
        qdrant_manager = QdrantManager()
        
        # Get all chunks and find ones with settlement_value
        all_chunks = []
        offset = None
        
        print("Fetching all chunks from case_files collection...")
        while True:
            result = qdrant_manager.client.scroll(
                collection_name="case_files",
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = result
            all_chunks.extend(points)
            
            if next_offset is None:
                break
            offset = next_offset
        
        print(f"Fetched {len(all_chunks)} total chunks")
        
        # Find chunks with settlement_value and collect their source files
        source_files_to_remove = set()
        settlement_score_chunks = []
        
        for point in all_chunks:
            settlement_score = point.payload.get('settlement_value')
            if settlement_score is not None and settlement_score != 'null' and settlement_score != '':
                settlement_score_chunks.append(point)
                source = point.payload.get('source')
                if source:
                    source_files_to_remove.add(source)
        
        print(f"Found {len(settlement_score_chunks)} chunks with settlement_value")
        print(f"Found {len(source_files_to_remove)} unique source files to remove")
        
        if len(source_files_to_remove) == 0:
            print("No source files to remove.")
            return
        
        # Show which files will be removed
        print("\nSource files to be removed:")
        for source_file in sorted(source_files_to_remove):
            print(f"  - {source_file}")
        
        # Find ALL chunks that have any of these source files
        all_chunks_to_delete = []
        for point in all_chunks:
            source = point.payload.get('source')
            if source in source_files_to_remove:
                all_chunks_to_delete.append(point)
        
        print(f"\nTotal chunks to delete from database: {len(all_chunks_to_delete)}")
        
        if not dry_run:
            # Remove source files from processed_files.json
            processed_files_data = load_from_json()
            files_removed_count = 0
            
            print("\nRemoving files from processed_files.json...")
            for case_id, file_list in processed_files_data.items():
                files_to_keep = []
                for file_path in file_list:
                    if file_path not in source_files_to_remove:
                        files_to_keep.append(file_path)
                    else:
                        print(f"  Removing {file_path} from case {case_id}")
                        files_removed_count += 1
                
                processed_files_data[case_id] = files_to_keep
            
            # Remove empty case entries
            processed_files_data = {k: v for k, v in processed_files_data.items() if v}
            
            # Save updated processed_files.json
            save_to_json(processed_files_data)
            print(f"Removed {files_removed_count} files from processed_files.json")
            
            # Delete chunks from Qdrant database
            print(f"\nDeleting {len(all_chunks_to_delete)} chunks from database...")
            chunk_ids = [point.id for point in all_chunks_to_delete]
            
            # Delete in batches to avoid overwhelming the API
            batch_size = 100
            deleted_count = 0
            
            for i in range(0, len(chunk_ids), batch_size):
                batch_ids = chunk_ids[i:i + batch_size]
                try:
                    qdrant_manager.client.delete(
                        collection_name="case_files",
                        points_selector=models.PointIdsList(points=batch_ids)
                    )
                    deleted_count += len(batch_ids)
                    print(f"  Deleted batch {i//batch_size + 1}: {len(batch_ids)} chunks")
                except Exception as e:
                    print(f"  Error deleting batch {i//batch_size + 1}: {e}")
            
            print(f"Successfully deleted {deleted_count} chunks from database")
        
        else:
            # Dry run - show what would be removed from processed_files.json
            processed_files_data = load_from_json()
            files_to_remove_count = 0
            
            print("\nFiles that would be removed from processed_files.json:")
            for case_id, file_list in processed_files_data.items():
                for file_path in file_list:
                    if file_path in source_files_to_remove:
                        print(f"  Case {case_id}: {file_path}")
                        files_to_remove_count += 1
            
            print(f"\nWould remove {files_to_remove_count} files from processed_files.json")
            print(f"Would delete {len(all_chunks_to_delete)} chunks from database")
        
        print(f"\nCleanup complete!")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        logger.error(f"Settlement score cleanup failed: {e}")

def main():
    embedding_test(r'C:\Users\Justin\Desktop\testdocs', 1050076)
    embedding_test(r'C:\Users\Justin\Desktop\testdocs2', 2211830)
    embedding_test(r'C:\Users\Justin\Desktop\testdocs3', 1637313)
    embedding_test(r'C:\Users\Justin\Desktop\testdocs4', 1660355)
    embedding_test(r'C:\Users\Justin\Desktop\testdocs5', 1508908)

if __name__ == "__main__":
    main()

