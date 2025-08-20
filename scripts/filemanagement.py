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

# ─── LOCAL IMPORTS ──────────────────────────────────────────────────────────────────
from utils import load_config, setup_logger


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
    Discovers all case subfolders and extracts case IDs from filenames.
    
    This function scans a main folder containing subfolders of case documents.
    Each subfolder contains files named with a case ID prefix (e.g., "1989212 04-24-2024 (1).pdf" 
    or "1989212 04-24-2024.docx"). Supports PDF, DOC, and DOCX files.
    All files in a subfolder share the same case ID.
    
    Args:
        main_folder_path (str): Path to the main folder containing case subfolders
        
    Returns:
        List[Tuple[str, int]]: List of tuples containing (subfolder_path, case_id)
        
    Raises:
        FileNotFoundError: If the main folder doesn't exist
        ValueError: If no valid case ID can be extracted from any files in a subfolder
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
            logger.warning("No document files (PDF, DOC, DOCX) found in %s, skipping" % subfolder.name)
            continue
        
        # Extract case ID from the first document file (all should have the same case ID)
        first_file = document_files[0]
        case_id = extract_case_id_from_filename(first_file.name)
        
        if case_id is None:
            logger.warning("Could not extract case ID from %s, skipping folder %s" % (first_file.name, subfolder.name))
            continue
        
        case_folders.append((str(subfolder), case_id))
        logger.info("Found case folder: %s with case ID: %s" % (subfolder.name, case_id))
    
    logger.info("Discovered %s case folders" % len(case_folders))
    return case_folders


def extract_case_id_from_filename(filename: str) -> int | None:
    """
    Extracts the case ID from a filename.
    
    Case IDs are expected to be at the beginning of the filename,
    followed by a space (e.g., "1989212 04-24-2024 (1).pdf").
    
    Args:
        filename (str): The filename to extract the case ID from
        
    Returns:
        int | None: The extracted case ID, or None if no valid case ID found
    """
    # Match one or more digits at the start of the filename
    match = re.match(r'^(\d+)', filename)
    
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            logger.error("Failed to convert extracted case ID to int: %s" % match.group(1))
            return None
    
    logger.warning("No case ID pattern found in filename: %s" % filename)
    return None


class FileManager:

    def __init__(self):
        self.config = config

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


class ChunkData:
    def __init__(self):
        logger.debug("Initializing ChunkData object.")
        self.text = ""
        self.source = ""
        self.metadata = {}
        self.embeddings = []
        self.case_id = ""

    def get_text(self) -> str:
        """
        Returns the text content.

        Returns:
            str: The text content.
        """
        return self.text

    def set_text(self, value: str) -> None:
        """
        Sets the text content.

        Args:
            value (str): The text to set.
        """
        self.text = value

    def get_source(self) -> str:
        """
        Returns the source.

        Returns:
            str: The source.
        """
        return self.source

    def set_source(self, value: str) -> None:
        """
        Sets the source.

        Args:
            value (str): The source to set.
        """
        self.source = value

    def get_metadata(self) -> dict:
        """
        Returns the metadata.

        Returns:
            dict: The metadata dictionary.
        """
        return self.metadata

    def set_metadata(self, value: dict) -> None:
        """
        Sets the metadata.

        Args:
            value (dict): The metadata dictionary to set.
        """
        self.metadata = value

    def get_embeddings(self) -> list:
        """
        Returns the embeddings.

        Returns:
            list: The embeddings list.
        """
        return self.embeddings

    def set_embeddings(self, value: list) -> None:
        """
        Sets the embeddings.

        Args:
            value (list): The embeddings list to set.
        """
        self.embeddings = value

    def get_case_id(self) -> str:
        """
        Returns the case ID.

        Returns:
            str: The case ID.d
        """
        return self.case_id

    def set_case_id(self, value: str) -> None:
        """
        Sets the case ID.

        Args:
            value (str): The case ID to set.
        """
        self.case_id = value
