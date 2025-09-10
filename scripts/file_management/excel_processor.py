# ─── STANDARD LIBRARY IMPORTS ──────────────────────────────────────────────────────
from pathlib import Path
from typing import Dict, Any, List, Union, Optional

# ─── THIRD-PARTY IMPORTS ────────────────────────────────────────────────────────────
import pandas as pd

# ─── LOCAL IMPORTS ──────────────────────────────────────────────────────────────────
from utils import load_config, setup_logger


# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)


# ─── EXCEL PROCESSING CLASS ─────────────────────────────────────────────────────────
class ExcelProcessor:
    """
    A class for processing Excel files (.xlsx) and converting them to dictionary format.
    
    This class provides methods to read Excel files and convert them to various
    dictionary formats for easier data manipulation and analysis.
    """
    
    def __init__(self):
        """Initialize the ExcelProcessor with configuration and logging."""
        self.config = config
        logger.info("ExcelProcessor initialized successfully")

        self.df = None

    def read(self, filepath: str):
        dataframe = pd.read_excel(filepath)
        self.df = dataframe
        return dataframe
    
    def get_row_caseid(self, caseid: int, df:pd.DataFrame = None):
        if df is None:
            df = self.df

        result = df.loc[df['Case No'] == caseid]

        if not result.empty:
            #create a nested dict structure
            row_data = result.to_dict(orient = 'records')[0]
            return row_data
        else:
            return None
