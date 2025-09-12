# ─── STANDARD LIBRARY IMPORTS ──────────────────────────────────────────────────────

# ─── THIRD-PARTY IMPORTS ────────────────────────────────────────────────────────────
import pandas as pd

# ─── LOCAL IMPORTS ──────────────────────────────────────────────────────────────────
from utils import load_config, setup_logger



# ─── EXCEL PROCESSING CLASS ─────────────────────────────────────────────────────────
class ExcelProcessor:
    """
    A class for processing Excel files (.xlsx) and converting them to dictionary format.
    
    This class provides methods to read Excel files and convert them to various
    dictionary formats for easier data manipulation and analysis.
    """
    
    def __init__(self):
        """Initialize the ExcelProcessor with configuration and logging."""
        self.config = load_config()
        self.logger = setup_logger(__name__, self.config)
        self.logger.info("ExcelProcessor initialized successfully")

    def read(self, filepath: str):
        dataframe = pd.read_excel(filepath)
        return dataframe
    
    def get_row_filename(self, filename: str, df:pd.DataFrame) -> dict:
        if df is None:
            self.logger.debug("No dataframe given as value, using 'self.df' as dataframe.")
            df = self.df
        
        # Trim whitespace for comparison but preserve case sensitivity
        filename_clean = filename.strip()
        result = df.loc[df['File Name'].str.strip() == filename_clean]

        if not result.empty:
            if len(result) > 1:
                self.logger.warning("Found %d matches for filename '%s', using first match.", len(result), filename)
                # Add a suffix to the filename in the returned data to indicate it's one of multiple matches
                row_data = result.to_dict(orient = 'records')[0]
                original_filename = row_data['File Name']
                row_data['File Name'] = f"{original_filename} (1)"
                self.logger.info("Filename '%s' found in dataframe with %d matches, returning first match with suffix.", filename, len(result))
            else:
                row_data = result.to_dict(orient = 'records')[0]
                self.logger.info("Filename '%s' found in dataframe, returning row_data.", filename)
            return row_data
        else:
            self.logger.error("Filename '%s' could not be found in dataframe, returning 'None'.", filename)
            return None
    
    def get_row_caseid(self, case_id: int, df:pd.DataFrame = None):
        if df is None:
            self.logger.debug("No dataframe given as value, using 'self.df' as dataframe.")
            df = self.df

        result = df.loc[df['Case No'] == case_id]

        if not result.empty:
            self.logger.info("Case ID '%i' found in dataframe, returning row_data.", case_id)
            #create a nested dict structure
            row_data = result.to_dict(orient = 'records')[0]
            return row_data
        else:
            self.logger.info("Case ID '%i' could not be found in dataframe, returning 'None'.", case_id)
            return None
    
