# ─── STANDARD LIBRARY IMPORTS ──────────────────────────────────────────────────────
import json
import os
from functools import wraps
from typing import Optional, List, Dict, Any

# ─── THIRD-PARTY IMPORTS ────────────────────────────────────────────────────────────
import ocrmypdf
from ocrmypdf.exceptions import SubprocessOutputError
import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tika import parser

# ─── LOCAL IMPORTS ──────────────────────────────────────────────────────────────────
from utils import load_config, get_config_directories, setup_logger


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
        ocrmypdf.ocr(filepath, filepath, force_ocr=True, invalidate_digital_signatures=True)
        logger.info(f"Successfully applied OCR and overwrote {filepath}")
    except SubprocessOutputError as e:
        logger.warning(
            f"Skipped OCR for {filepath} due to a Ghostscript error, likely a malformed or complex PDF. Error: {e}"
        )
    except Exception as e:
        logger.error(f"Failed to apply OCR to {filepath}: {e}")
        raise


class FileManager:

    def __init__(self):
        self.config = config
    
    def get_text_from_file(self, filepath: str):
         request_options = {'timeout': 300} # Set timeout to 5 minutes (300 seconds)
         parsed_pdf = parser.from_file(filepath, requestOptions=request_options)
         return parsed_pdf

    # TODO: Could tokenize first and then split using defined token chunks? Saw something like that in the documenatation
    #https://python.langchain.com/api_reference/text_splitters/base/langchain_text_splitters.base.Tokenizer.html
    def text_splitter(self, text: Dict[str, Any], chunkSize: int = 1000, chunkOverlap: int = 200) -> List[Any]:
        """
        Splits parsed PDF text into smaller chunks using RecursiveCharacterTextSplitter.

        Args:
            text (Dict[str, Any]): Parsed document dict from parser.from_file().
            chunkSize (int): Max characters per chunk. Defaults to 1000.
            chunkOverlap (int): Characters to overlap between chunks. Defaults to 200.

        Returns:
            List[Document]: LangChain Document objects with text chunks.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunkSize,
            chunk_overlap=chunkOverlap,
            length_function=len,
            is_separator_regex=False,
        )
        chunks = splitter.create_documents([text['content']])
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
        logger.debug("Getting text.")
        return self.text

    def set_text(self, value: str) -> None:
        """
        Sets the text content.

        Args:
            value (str): The text to set.
        """
        logger.debug(f"Setting text to: {value[:70]}...")
        self.text = value

    def get_source(self) -> str:
        """
        Returns the source.

        Returns:
            str: The source.
        """
        logger.debug(f"Getting source.")
        return self.source

    def set_source(self, value: str) -> None:
        """
        Sets the source.

        Args:
            value (str): The source to set.
        """
        logger.debug(f"Setting source to: {value}")
        self.source = value

    def get_metadata(self) -> dict:
        """
        Returns the metadata.

        Returns:
            dict: The metadata dictionary.
        """
        logger.debug(f"Getting metadata.")
        return self.metadata

    def set_metadata(self, value: dict) -> None:
        """
        Sets the metadata.

        Args:
            value (dict): The metadata dictionary to set.
        """
        logger.debug(f"Setting metadata to: {value}")
        self.metadata = value

    def get_embeddings(self) -> list:
        """
        Returns the embeddings.

        Returns:
            list: The embeddings list.
        """
        logger.debug("Getting embeddings.")
        return self.embeddings

    def set_embeddings(self, value: list) -> None:
        """
        Sets the embeddings.

        Args:
            value (list): The embeddings list to set.
        """
        logger.debug(f"Setting embeddings, count: {len(value)}")
        self.embeddings = value

    def get_case_id(self) -> str:
        """
        Returns the case ID.

        Returns:
            str: The case ID.d
        """
        logger.debug("Getting case ID.")
        return self.case_id
    
    def set_case_id(self, value: str) -> None:
        """
        Sets the case ID.

        Args:
            value (str): The case ID to set.
        """
        logger.debug(f"Setting case ID to: {value}")
        self.case_id = value