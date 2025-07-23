from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
import logging.handlers
import yaml
import os
import json
import sys
import tiktoken


def ensure_directories(directories: List[Path] = None) -> None:
    """
    Ensures that a list of directories exists, creating them if necessary.

    Args:
        directories (List[Path], optional): A list of Path objects. 
            If None, directories are loaded from config. Defaults to None.
    """
    if not directories:
        directories = get_config_directories()
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_config_directories() -> List[Path]:
    """
    Loads directory paths from the config file, relative to the project directory.

    Returns:
        List[Path]: A list of Path objects for the directories.
    """
    try:
        config_data = load_config()
        if config_data and 'directories' in config_data:
            script_dir = Path(__file__).parent
            return [script_dir / Path(value) for value in config_data.get('directories', {}).values()]
    except Exception as e:
        print(f"Error reading or parsing config file: {e}")
    return []

def load_config(config_path: Path = None) -> dict:
    """
    Loads the YAML configuration file.

    Args:
        config_path (Path, optional): The path to the config file. 
            Defaults to 'config.yaml' in the same directory as this script.

    Returns:
        dict: The loaded configuration data.
    """
    if config_path is None:
        config_path = Path(__file__).parent / 'config.yaml'

    try:
        with config_path.open('r') as f:
            config = yaml.safe_load(f)
            return config or {}
    except FileNotFoundError:
        print(f"Warning: Config file not found at {config_path}")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
    return {}
                
def setup_logger(
    name: str, config: Dict[str, Any], level: Optional[str] = None, filename: Optional[str] = None
    ) -> logging.Logger:
    """
    Configure and return a logger that works with tqdm progress bars.

    Sets up a logger with console output that won't interfere with progress bars.
    Uses a custom TqdmLoggingHandler for output.

    Args:
        name (str): Name of the logger (typically __name__).
        config (Dict[str, Any]): Configuration dictionary containing logger settings.
        level (Optional[str]): Optional log level override.
        filename (Optional[str]): Optional custom filename. If None, uses config["logger"]["filename"].

    Returns:
        logging.Logger: Configured logger instance.

    Example:
        >>> logger = setup_logger(__name__, config)
        >>> logger.info("Processing started")
        >>> # Custom filename for specific class
        >>> logger = setup_logger(__name__, config, filename="custom_class.log")
    """
    logger = logging.getLogger(name)
    log_level = level or config["logger"]["level"]
    logger.setLevel(getattr(logging, log_level))

    # Prevent adding duplicate handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        config["logger"]["format"], datefmt=config["logger"]["datefmt"]
    )

    # Create file handler
    log_dir = Path(__file__).resolve().parent / config["directories"]["logs"]
    log_dir.mkdir(exist_ok=True)
    log_filename = filename or config["logger"]["filename"]
    log_file = log_dir / log_filename

    # Use RotatingFileHandler for log rotation
    max_bytes = int(config["logger"].get("max_bytes", 1024 * 1024 * 5))  # Default 5 MB
    backup_count = int(config["logger"].get("backup_count", 3)) # Default 5 backups

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        mode="a",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def load_prompt(prompt_name: str, prompts_path: Optional[Path] = None) -> str:
    """
    Loads a specific prompt from the YAML prompts file.

    Args:
        prompt_name (str): The name of the prompt to load (e.g., 'injury_metadata_extraction').
        prompts_path (Optional[Path]): The path to the prompts file.
            Defaults to 'prompts.yaml' in the script's parent directory.

    Returns:
        str: The loaded prompt text as a single string. Returns an empty string on error.
    """
    if prompts_path is None:
        prompts_path = Path(__file__).parent / 'prompts.yaml'

    try:
        with prompts_path.open('r') as f:
            prompts_data = yaml.safe_load(f)
        
        prompt_text = prompts_data[prompt_name]['prompt']
        return prompt_text

    except FileNotFoundError:
        logging.error(f"Prompts file not found at {prompts_path}")
        return ""
    except KeyError:
        logging.error(f"Prompt '{prompt_name}' not found in {prompts_path}")
        return ""
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML prompts file: {e}")
        return ""

def load_from_json(filepath: str = None, default_filename: str = 'processed_files.json') -> dict:
    """Loads data from a JSON file.

    If no filepath is provided, it defaults to a file in the 'jsons' directory.

    Args:
        filepath (str, optional): The path to the input JSON file. Defaults to None.
        default_filename (str, optional): The default filename to use if filepath is None.

    Returns:
        dict: The loaded data. Returns an empty dictionary if the file doesn't exist or is empty.
    """
    if filepath is None:
        try:
            config = load_config()
            json_dir_path = config.get('directories', {}).get('jsons')
            if not json_dir_path:
                print("Error: 'jsons' directory not found in configuration. Cannot determine default path.")
                return {}
            
            script_dir = Path(__file__).parent
            json_dir = script_dir / Path(json_dir_path)
            os.makedirs(json_dir, exist_ok=True)
            filepath = os.path.join(json_dir, default_filename)
        except Exception as e:
            print(f"Error: Could not determine JSON directory path: {e}")
            return {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading data from JSON file {filepath}: {e}")
        return {}

def find_files(directory: Path) -> List[Path]:
    """
    Finds all .pdf files in a specified directory and its subdirectories.

    Args:
        directory (Path): The directory to search.

    Returns:
        List[Path]: A list of Path objects for the found PDF files.
    """
    if not directory.is_dir():
        return []
    
    pdf_files = list(directory.rglob("*.pdf")) + list(directory.rglob("*.docx"))
    non_duplicate_pdf_files = []
    for file in pdf_files:
        if not file.stem.endswith(')'): #avoiding duplicate files that are copies ending with (1).pdf...(2).pdf...etc
            non_duplicate_pdf_files.append(file)
    return non_duplicate_pdf_files

def count_tokens(text: str) -> int:
    """
    Calculates the number of tokens in a text string using tiktoken.

    Args:
        text (str): The text to process.
        model_name (str): The name of the model to use. This is used to determine the encoding to use.

    Returns:
        int: The number of tokens in the text.
    """
    encoding = tiktoken.get_encoding("o200k_base")
    tokens = encoding.encode(text)
    return len(tokens)

def save_to_json(data: Any, filepath: str = None, default_filename: str = 'processed_files.json'):
    """Saves data to a JSON file.

    For testing purposes, if no filepath is provided, it defaults to
    a file in the project's 'jsons' directory.

    Args:
        data (Any): The data to save (must be JSON-serializable).
        filepath (str, optional): The path to the output JSON file. Defaults to None.
        default_filename (str, optional): The default filename to use if filepath is None.
    """
    if filepath is None:
        try:
            config = load_config()
            json_dir_path = config.get('directories', {}).get('jsons')
            if not json_dir_path:
                print("Error: 'jsons' directory not found in configuration. Please check config.yaml.")
                return
            
            script_dir = Path(__file__).parent
            json_dir = script_dir / Path(json_dir_path)
            os.makedirs(json_dir, exist_ok=True)
            filepath = os.path.join(json_dir, default_filename)
        except Exception as e:
            print(f"Error: Could not determine JSON directory path: {e}")
            return


    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved data to {filepath}")
    except (IOError, TypeError) as e:
        print(f"Error saving data to JSON file: {e}")

def get_jurisdiction_data(state: str, jurisdiction_name: str) -> Dict[str, Any]:
    """
    Retrieves the complete data dictionary for a specified jurisdiction within a state.

    Args:
        state (str): The state abbreviation (e.g., "NY").
        jurisdiction_name (str): The jurisdiction name (e.g., "Suffolk County").

    Returns:
        Dict[str, Any]: The jurisdiction's data dictionary containing score_modifier, 
                       notes, and other jurisdiction-specific information. 
                       Returns empty dict if not found.

    Example:
        >>> data = get_jurisdiction_data("NY", "Suffolk County")
        >>> print(data.get('score_modifier'))
        1.0
    """
    try:
        config = load_config()
        state_data = config.get('jurisdictions', {}).get(state, {})
        return state_data.get(jurisdiction_name, {})
    except Exception as e:
        print(f"Error retrieving jurisdiction data for '{jurisdiction_name}, {state}': {e}")
        return {}

