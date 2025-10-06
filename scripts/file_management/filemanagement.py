# ─── STANDARD LIBRARY IMPORTS ──────────────────────────────────────────────────────
from functools import wraps
from typing import List, Dict, Any, Tuple
from pathlib import Path
import re

# ─── THIRD-PARTY IMPORTS ────────────────────────────────────────────────────────────
import ocrmypdf
from ocrmypdf.exceptions import SubprocessOutputError
import pymupdf
from langchain_text_splitters import TokenTextSplitter
from tika import parser
import tiktoken
import os

from warnings import deprecated
# ─── LOCAL IMPORTS ──────────────────────────────────────────────────────────────────
from utils import load_config, setup_logger, count_tokens


# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)


def with_pdf(func):
    """Decorator to manage the lifecycle of a PyMuPDF document.


    This decorator simplifies PDF handling for functions that operate on
    a PDF document. It ensures the document is opened and closed correctly,
    and handles cases where a document might already be open or creates one if an existing one
    is not given.

    -Args: Accepts 'pdfdoc(pymupdf.Document)' and 'filepath(str)' kwargs.

    Does not handle saving of the document, that must be handled seperately.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        pdfdoc = kwargs.get("pdfdoc")
        filepath = kwargs.get("filepath")

        if pdfdoc and isinstance(pdfdoc, pymupdf.Document):
            if not pdfdoc.is_closed:
                return func(*args, **kwargs)

        filepath = kwargs.get("filepath")
        managed_doc = None
        try:
            try:
                managed_doc = pymupdf.open(filepath)
            except (pymupdf.FileNotFoundError, TypeError, ValueError):
                print("filepath has no existing PDF or is invalid, creating new one.")
                managed_doc = pymupdf.open()  # create new blank PDF if none was given
                managed_doc.new_page(width=595.44, height=842.4)

            kwargs["pdfdoc"] = managed_doc
            result = func(*args, **kwargs)
            return result

        except Exception as e:
            print(f"Issue with PDF management for with_pdf(): {e}")
        finally:
            if managed_doc:
                managed_doc.close()

    return wrapper


def apply_ocr(filepath: str) -> None:
    """
    Applies OCR to a PDF file using ocrmypdf and overwrites the original file.

    Args:
        filepath (str): The path to the PDF file.
    """
    try:
        logger.info(f"Starting OCR for {filepath}...")
        # Using force_ocr=True to ensure that OCR is applied even if the tool
        # detects existing text. The input and output file are the same to
        # overwrite the original.
        ocrmypdf.ocr(
            filepath, filepath, force_ocr=True, invalidate_digital_signatures=True
        )
        logger.info(f"Successfully applied OCR and overwrote {filepath}")
    except SubprocessOutputError as e:
        logger.warning(
            f"Skipped OCR for {filepath} due to a Ghostscript error, likely a malformed or complex PDF. Error: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to apply OCR to {filepath}: {e}")


def get_text_from_file(filepath: str, **kwargs):
    request_options = {"timeout": 300}  # Set timeout to 5 minutes (300 seconds)
    parsed_file = parser.from_file(filepath, requestOptions=request_options, **kwargs)
    return parsed_file


def discover_case_folders(main_folder_path: str) -> List[Tuple[str, int]]:
    """
    Discovers all case subfolders and extracts case IDs from XLSX files in file_list folders.

    This function scans a main folder containing subfolders of case documents.
    Each subfolder contains document files (PDF, DOC, DOCX) and a nested "file_list" folder 
    with an XLSX file that has the case ID as a prefix in its filename 
    (e.g., "2500207 - Lorraine Richards v. Tiffany Cruz - DocumentsDocuments.xlsx").
    The case ID is extracted from this XLSX filename.

    Args:
        main_folder_path (str): Path to the main folder containing case subfolders

    Returns:
        List[Tuple[str, int]]: List of tuples containing (subfolder_path, case_id)

    Raises:
        FileNotFoundError: If the main folder doesn't exist
        ValueError: If no valid case ID can be extracted from any XLSX files in file_list folders
    """
    main_path = Path(main_folder_path)

    if not main_path.exists():
        raise FileNotFoundError("Main folder not found: %s" % main_folder_path)

    if not main_path.is_dir():
        raise ValueError("Path is not a directory: %s" % main_folder_path)

    case_folders = []

    # Iterate through all subdirectories
    for subfolder in main_path.iterdir():
        if not subfolder.is_dir():
            continue

        logger.info("Processing subfolder: %s" % subfolder.name)

        # Get all supported document files in the subfolder (PDF, DOC, DOCX)
        document_files = []
        document_files.extend(list(subfolder.glob("*.pdf")))
        document_files.extend(list(subfolder.glob("*.doc")))
        document_files.extend(list(subfolder.glob("*.docx")))

        if not document_files:
            logger.warning(
                "No document files (PDF, DOC, DOCX) found in %s, skipping"
                % subfolder.name
            )
            continue

        # Extract case ID from XLSX file in file_list folder
        case_id = extract_case_id_from_file_list(subfolder)

        if case_id is None:
            logger.warning(
                "Could not extract case ID from file_list folder, skipping %s"
                % subfolder.name
            )
            continue

        case_folders.append((str(subfolder), case_id))
        logger.info(
            "Found case folder: %s with case ID: %s" % (subfolder.name, case_id)
        )

    logger.info("Discovered %s case folders" % len(case_folders))
    return case_folders


def extract_case_id_from_file_list(subfolder_path: Path) -> int | None:
    """
    Extracts the case ID from an XLSX file in a nested file_list folder.

    This function looks for a 'file_list' subfolder within the given folder,
    finds XLSX files in it, and extracts the case ID from the first XLSX filename.

    Args:
        subfolder_path (Path): Path to the case subfolder containing the file_list folder

    Returns:
        int | None: The extracted case ID, or None if no valid case ID found

    Raises:
        None: Function handles all exceptions internally and returns None on failure
    """
    try:
        # Look for the nested file_list folder
        file_list_path = subfolder_path / "file_list"
        if not file_list_path.exists() or not file_list_path.is_dir():
            logger.warning(
                "No 'file_list' folder found in %s" % subfolder_path.name
            )
            return None

        # Get all XLSX files in the file_list folder
        xlsx_files = list(file_list_path.glob("*.xlsx"))

        if not xlsx_files:
            logger.warning(
                "No XLSX files found in file_list folder of %s"
                % subfolder_path.name
            )
            return None

        # Extract case ID from the first XLSX file
        first_xlsx = xlsx_files[0]
        case_id = extract_case_id_from_filename(first_xlsx.name)

        if case_id is None:
            logger.warning(
                "Could not extract case ID from %s in folder %s"
                % (first_xlsx.name, subfolder_path.name)
            )
            return None

        logger.debug(
            "Extracted case ID %s from %s in %s"
            % (case_id, first_xlsx.name, subfolder_path.name)
        )
        return case_id

    except Exception as e:
        logger.error(
            "Error extracting case ID from file_list in %s: %s"
            % (subfolder_path.name, str(e))
        )
        return None


def extract_case_id_from_filename(filename: str) -> int | None:
    """
    Extracts the case ID from a filename.

    Case IDs are expected to be at the beginning of the filename,
    followed by a space or other separator (e.g., "1989212 04-24-2024 (1).pdf" 
    or "2500207 - Lorraine Richards v. Tiffany Cruz - DocumentsDocuments.xlsx").

    Args:
        filename (str): The filename to extract the case ID from

    Returns:
        int | None: The extracted case ID, or None if no valid case ID found
    """
    # Match one or more digits at the start of the filename
    match = re.match(r"^(\d+)", filename)

    if match:
        try:
            return int(match.group(1))
        except ValueError:
            logger.error(
                "Failed to convert extracted case ID to int: %s" % match.group(1)
            )
            return None

    logger.warning("No case ID pattern found in filename: %s" % filename)
    return None


class FileManager:

    def __init__(self):
        self.config = config

    def smart_file_chunker(
        self, text: Dict[str, Any], token_threshold: int = 18000, chunk_size: int = 15000, chunk_overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Intelligently chunks a file based on token count.
        
        If the file has fewer tokens than the threshold, returns the original text as a single chunk.
        If the file exceeds the threshold, splits it into multiple chunks.
        
        Args:
            text (Dict[str, Any]): Parsed document dict from parser.from_file().
            token_threshold (int): Token count threshold for splitting. Defaults to 18000.
            chunk_size (int): Max tokens per chunk when splitting. Defaults to 15000.
            chunk_overlap (int): Tokens to overlap between chunks. Defaults to 200.
            
        Returns:
            List[Dict[str, Any]]: List of text chunks, each containing 'content', 'chunk_index', 
                                'total_chunks', and 'token_count' fields.
        """
        content = text["content"]
        total_tokens = count_tokens(content)
        
        logger.info('File token count: %d (threshold: %d)', total_tokens, token_threshold)
        
        if total_tokens <= token_threshold:
            # File is small enough, return as single chunk
            logger.debug('File is below token threshold, processing as single chunk')
            return [{
                'content': content,
                'chunk_index': 0,
                'total_chunks': 1,
                'token_count': total_tokens
            }]
        else:
            # File is too large, split into chunks
            logger.info('File exceeds token threshold (%d tokens), splitting into chunks', total_tokens)
            
            splitter = TokenTextSplitter(
                encoding_name="o200k_base",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            chunks = splitter.create_documents([content])
            
            chunked_data = []
            total_chunk_count = len(chunks)
            
            for i, chunk in enumerate(chunks):
                chunk_tokens = count_tokens(chunk.page_content)
                chunked_data.append({
                    'content': chunk.page_content,
                    'chunk_index': i,
                    'total_chunks': total_chunk_count,
                    'token_count': chunk_tokens
                })
                
            logger.info('Split file into %d chunks', total_chunk_count)
            return chunked_data

    def text_splitter(
        self, text: Dict[str, Any], chunkSize: int = 15000, chunkOverlap: int = 200
    ) -> List[Any]:
        """
        Splits parsed PDF text into smaller chunks using TokenTextSplitter.

        Args:
            text (Dict[str, Any]): Parsed document dict from parser.from_file().
            chunkSize (int): Max tokens per chunk. Defaults to 18000.
            chunkOverlap (int): Tokens to overlap between chunks. Defaults to 200.

        Returns:
            List[Document]: LangChain Document objects with text chunks.
        """
        splitter = TokenTextSplitter(
            encoding_name="o200k_base",
            chunk_size=chunkSize,
            chunk_overlap=chunkOverlap,
        )
        chunks = splitter.create_documents([text["content"]])
        logger.debug(f"Split into {len(chunks)} chunks.")
        return chunks


def get_case_id_filelist_path(case_id: int) -> str:
    """
    Locate the first .xlsx in the `file_list` folder for a given case.

    Args:
        case_id (int): The numeric case identifier.

    Returns:
        str: Path to the .xlsx file (relative to project root or as configured).

    Raises:
        FileNotFoundError: If the case folder, `file_list` folder, or .xlsx file is missing.
    """
    case_data_base = Path(config['directories']['case_data'])
    file_list_dir = case_data_base / str(case_id) / "file_list"

    if not file_list_dir.exists() or not file_list_dir.is_dir():
        logger.error("Missing 'file_list' directory for case '%i' at '%s'", case_id, str(file_list_dir))
        raise FileNotFoundError("Missing 'file_list' directory for case '%i'" % case_id)

    xlsx_files = list(file_list_dir.glob("*.xlsx"))
    if not xlsx_files:
        logger.error("No .xlsx files found in 'file_list' for case '%i'", case_id)
        raise FileNotFoundError("No .xlsx files found for case '%i'" % case_id)

    logger.info("Using file list '%s' for case '%i'", xlsx_files[0].name, case_id)
    return str(xlsx_files[0])

@deprecated("Redundant and overcomplicated, use a list of dicts like in main.")
class ChunkData:
    def __init__(self):
        logger.debug("Initializing ChunkData object.")
        self.text = ""
        self.source = ""
        self.metadata = {}
        self.embeddings = []
        self.case_id = ""

    @deprecated("Do not use ChunkData anymore")
    def get_text(self) -> str:
        """
        Returns the text content.

        Returns:
            str: The text content.
        """
        return self.text
    @deprecated("Do not use ChunkData anymore")
    def set_text(self, value: str) -> None:
        """
        Sets the text content.

        Args:
            value (str): The text to set.
        """
        self.text = value
    @deprecated("Do not use ChunkData anymore")
    def get_source(self) -> str:
        """
        Returns the source.

        Returns:
            str: The source.
        """
        return self.source
    @deprecated("Do not use ChunkData anymore")
    def set_source(self, value: str) -> None:
        """
        Sets the source.

        Args:
            value (str): The source to set.
        """
        self.source = value
    @deprecated("Do not use ChunkData anymore")
    def get_metadata(self) -> dict:
        """
        Returns the metadata.

        Returns:
            dict: The metadata dictionary.
        """
        return self.metadata
    @deprecated("Do not use ChunkData anymore")
    def set_metadata(self, value: dict) -> None:
        """
        Sets the metadata.

        Args:
            value (dict): The metadata dictionary to set.
        """
        self.metadata = value
    @deprecated("Do not use ChunkData anymore")
    def get_embeddings(self) -> list:
        """
        Returns the embeddings.

        Returns:
            list: The embeddings list.
        """
        return self.embeddings
    @deprecated("Do not use ChunkData anymore")
    def set_embeddings(self, value: list) -> None:
        """
        Sets the embeddings.

        Args:
            value (list): The embeddings list to set.
        """
        self.embeddings = value
    @deprecated("Do not use ChunkData anymore")
    def get_case_id(self) -> str:
        """
        Returns the case ID.

        Returns:
            str: The case ID.d
        """
        return self.case_id
    @deprecated("Do not use ChunkData anymore")
    def set_case_id(self, value: str) -> None:
        """
        Sets the case ID.

        Args:
            value (str): The case ID to set.
        """
        self.case_id = value


def move_case_files_to_case_data(source_folder_path: str, case_id: int) -> str:
    """
    Copies the entire source folder structure to case_data/{case_id}/ directory.
    
    This function creates an exact copy of the source folder and all its contents
    (including subfolders, documents, and metadata) under the case_data directory
    with the case_id as the folder name.
    
    Args:
        source_folder_path (str): Path to the source folder to copy
        case_id (int): The case ID to use for the destination folder name
        
    Returns:
        str: Path to the new case folder in case_data directory
        
    Raises:
        Exception: If copying the folder fails
    """
    import shutil
    
    source_path = Path(source_folder_path)
    case_data_base = Path(config['directories']['case_data'])
    case_folder = case_data_base / str(case_id)
    
    # Check if source folder exists
    if not source_path.exists():
        raise FileNotFoundError("Source folder not found: %s" % source_folder_path)
    
    # If destination already exists, remove it first (to ensure clean copy)
    if case_folder.exists():
        logger.info("Destination folder already exists, removing: %s" % case_folder)
        shutil.rmtree(str(case_folder))
    
    try:
        # Copy entire folder structure
        print("Copying folder structure from %s to %s..." % (source_path.name, case_folder))
        shutil.copytree(str(source_path), str(case_folder))
        logger.info("Successfully copied folder structure to: %s" % case_folder)
        
        # Count copied files for user feedback
        all_files = list(case_folder.rglob("*"))
        file_count = len([f for f in all_files if f.is_file()])
        folder_count = len([f for f in all_files if f.is_dir()])
        
        print("✓ Successfully copied %s files and %s folders to %s" % (file_count, folder_count, case_folder))
        return str(case_folder)
        
    except Exception as e:
        logger.error("Failed to copy folder structure: %s" % e)
        raise


def get_relative_path(file_path: Path) -> str:
    """
    Creates a relative path from the project root for a given file path.
    This ensures portability across different computers.
    
    Args:
        file_path (Path): The absolute path to the file
        
    Returns:
        str: Relative path from project root, or fallback path if conversion fails
    """
    project_root = Path.cwd()  # Current working directory (project root)
    try:
        return str(file_path.relative_to(project_root))
    except ValueError:
        # If file is not under project root, use relative to case_data directory
        case_data_base = Path(config['directories']['case_data'])
        try:
            return str(file_path.relative_to(case_data_base.parent))
        except ValueError:
            # Fallback to just filename if all else fails
            logger.warning("Could not create relative path for '%s', using filename only" % str(file_path))
            return str(file_path.name)


def resolve_relative_path(relative_path: str) -> str:
    """
    Converts a relative path back to an absolute path for file access.
    Complements get_relative_path() function.
    
    Args:
        relative_path (str): Relative file path (as stored in metadata)
        
    Returns:
        str: Absolute file path
        
    Raises:
        FileNotFoundError: If file cannot be found
    """
    file_path = Path(relative_path)
    
    # If already absolute, return as-is
    if file_path.is_absolute():
        if file_path.exists():
            return str(file_path)
        else:
            raise FileNotFoundError("File not found: '%s'" % relative_path)
    
    # Try relative to project root first
    project_root = Path.cwd()
    absolute_path = project_root / file_path
    if absolute_path.exists():
        return str(absolute_path)
    
    # If not found relative to project root, try relative to case_data directory
    # This handles paths like "case_data\2500174\MVA Intake_002.pdf"
    case_data_base = Path(config['directories']['case_data'])
    project_root = Path.cwd()
    
    # If the relative_path starts with "case_data", remove that prefix and use the configured case_data path
    if str(file_path).startswith('case_data'):
        # Remove the 'case_data' prefix and join with the configured case_data directory
        relative_to_case_data = Path(*file_path.parts[1:])  # Skip the first 'case_data' part
        case_data_absolute_path = project_root / case_data_base / relative_to_case_data
        if case_data_absolute_path.exists():
            logger.debug("Resolved path using case_data directory: '%s'", case_data_absolute_path)
            return str(case_data_absolute_path)
    
    # Final fallback: try the file path as-is under the configured case_data directory
    case_data_fallback = project_root / case_data_base / file_path
    if case_data_fallback.exists():
        logger.debug("Resolved path using case_data fallback: '%s'", case_data_fallback)
        return str(case_data_fallback)
    
    raise FileNotFoundError("File not found: '%s'" % relative_path)