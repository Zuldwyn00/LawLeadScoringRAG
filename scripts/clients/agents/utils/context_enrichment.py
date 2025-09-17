
from typing import Dict, Any


from scripts.vectordb import QdrantManager
from utils import load_config, setup_logger
from scripts.file_management.excel_processor import ExcelProcessor
from scripts.file_management.filemanagement import resolve_relative_path

class CaseContextEnricher:
    """
    Enriches case data with additional metadata by calling specific retrieval methods.
    
    Each metadata field has its own dedicated method, making the code more maintainable
    and easier to understand than dynamic field handling.
    """
    
    def __init__(self, qdrant_manager: QdrantManager):
        self.config = load_config()
        self.logger = setup_logger(self.__class__.__name__, self.config)
        
        self.excel_processor = ExcelProcessor()


    def build_context_message(self, case_ids: int | set[int]) -> str:
        """
        Build context messages for given case IDs.
        
        Args:
            case_ids: Single case ID (int) or set of case IDs (set[int])
            
        Returns:
            str: Formatted string containing case data for all case_ids
        """
        # Convert single int to set for uniform processing
        if isinstance(case_ids, int):
            case_ids = {case_ids}
        
        context_parts = []

        filepath = self.config.get('lead_scoring', {}).get('case_enrichment', {}).get('primary_case_data_file_location')
        # Resolve relative path to absolute path for cross-platform compatibility
        absolute_filepath = resolve_relative_path(filepath)
        dataframe = self.excel_processor.read(absolute_filepath)
        
        for case_id in case_ids:
            try:
                # Get case data from Excel processor
                case_data = self.excel_processor.get_row_caseid(case_id, dataframe)
                
                if case_data:
                    # Format the case data as a readable string
                    case_info = f"**Case {case_id}:**\n"
                    for key, value in case_data.items():
                        if value is not None and str(value).strip():
                            case_info += f"  - {key}: {value}\n"
                    context_parts.append(case_info)
                    self.logger.info("Retrieved context for case '%s'", case_id)
                else:
                    self.logger.warning("No data found for case '%s'", case_id)
                    context_parts.append(f"**Case {case_id}:** No data found\n")
                    
            except Exception as e:
                self.logger.error("Error retrieving context for case '%s': %s", case_id, str(e))
                context_parts.append(f"**Case {case_id}:** Error - {str(e)}\n")
        
        # Join all case contexts with double newlines for separation
        return "\n".join(context_parts) if context_parts else "No case context available."







        
