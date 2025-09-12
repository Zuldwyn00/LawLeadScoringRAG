
from typing import Dict, Any, List


from scripts.vectordb import QdrantManager
from utils import load_config, setup_logger
from scripts.file_management.excel_processor import ExcelProcessor

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


    def build_context_message(self, case_ids: int | set[int]) -> List[Dict[str, Any]]:
        """
        Build context messages for given case IDs.
        
        Args:
            case_ids: Single case ID (int) or set of case IDs (set[int])
            
        Returns:
            List[Dict[str, Any]]: List of dictionaries containing case data for each case_id
        """
        # Convert single int to set for uniform processing
        if isinstance(case_ids, int):
            case_ids = {case_ids}
        
        context_messages = []
        #read excel file sets as a self value for excel_processor as the current_dataframe, though we could also use the returned dataframe
        # as an input if we want.
        self.excel_processor.read(r'C:\Users\Justin\Downloads\webDGCase.xlsx') #TODO: Require dataframe as an input instead possibly
        for case_id in case_ids:
            try:
                # Get case data from Excel processor
                case_data = self.excel_processor.get_row_caseid(case_id)
                
                if case_data:
                    context_messages.append(case_data)
                    self.logger.info("Retrieved context for case '%s'", case_id)
                else:
                    self.logger.warning("No data found for case '%s'", case_id)
                    # Add empty dict to maintain order/consistency
                    context_messages.append({"Case No": case_id, "error": "No data found"})
                    
            except Exception as e:
                self.logger.error("Error retrieving context for case '%s': %s", case_id, str(e))
                # Add error dict to maintain order/consistency
                context_messages.append({"Case No": case_id, "error": str(e)})
        
        return context_messages







        
