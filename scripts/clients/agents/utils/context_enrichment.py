from dataclasses import dataclass
from typing import Dict, Any, List, Callable
from functools import wraps


from scripts.vectordb import QdrantManager
from utils import load_config, setup_logger


class CaseContextEnricher:
    """
    Enriches case data with additional metadata by calling specific retrieval methods.
    
    Each metadata field has its own dedicated method, making the code more maintainable
    and easier to understand than dynamic field handling.
    """
    
    def __init__(self, qdrant_manager: QdrantManager):
        self.qdrant_manager = qdrant_manager
        self.config = load_config()
        self.logger = setup_logger(self.__class__.__name__, self.config)
        
        # Registry of available metadata retrieval methods
        self.metadata_methods = {
            'case_outcome': self._get_case_outcome,
            'settlement_value': self._get_settlement_value,
        }
        
        # Get which fields are actually required from config
        self.required_fields = self.config.get("lead_scoring", {}).get("case_enrichment", {}).get("required_fields", [])
        
        # Cache for chunks data to avoid repeated database calls
        self._current_case_id = None
        self._current_chunks = None
        
        self.logger.info("Available metadata methods: %s", list(self.metadata_methods.keys()))
        self.logger.info("Required fields for enrichment: %s", self.required_fields)

    def get_all_required_metadata(self, case_id: int) -> Dict[str, Any]:
        """
        Retrieves all required metadata fields for a given case.
        
        Args:
            case_id (int): The case identifier.
            
        Returns:
            Dict[str, Any]: Dictionary containing all required metadata fields.
        """
        metadata = {}
        
        for field in self.required_fields:
            if field in self.metadata_methods:
                try:
                    metadata[field] = self.metadata_methods[field](case_id)
                    self.logger.debug("Retrieved '%s' for case '%s'", field, case_id)
                except Exception as e:
                    self.logger.error("Failed to retrieve '%s' for case '%s': %s", field, case_id, e)
                    metadata[field] = None
            else:
                self.logger.warning("No method available for required field: '%s'", field)
                metadata[field] = None
                
        return metadata

    def _get_chunks_for_case(self, case_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves chunks for a case with caching to avoid repeated database calls.
        
        Args:
            case_id (int): The case identifier.
            
        Returns:
            List[Dict[str, Any]]: List of chunks for the case.
        """
        # Check if we already have chunks for this case
        if self._current_case_id != case_id:
            self.logger.debug("Fetching chunks for case '%s'", case_id)
            self._current_chunks = self.qdrant_manager.get_chunks_by_caseid(case_id)
            self._current_case_id = case_id
        else:
            self.logger.debug("Using cached chunks for case '%s'", case_id)
            
        return self._current_chunks

    @staticmethod
    def with_chunks(field_name: str):
        """
        Decorator that provides chunks data to metadata retrieval methods.
        
        Args:
            field_name (str): The field name to extract from chunks.
            
        Returns:
            Callable: Decorated method that receives chunks as first argument.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(self, case_id: int) -> str:
                chunks = self._get_chunks_for_case(case_id)
                return func(self, chunks, case_id, field_name)
            return wrapper
        return decorator

    def build_context_message(self, case_ids: int | set[int]) -> str:
        """
        Builds formatted messages combining all required fields for AI context.
        Can process either a single case or multiple cases.
        
        Args:
            case_ids (int | set[int]): Either a single case identifier or a set of case identifiers.
            
        Returns:
            str: Formatted context message that clearly identifies which context belongs to which case ID.
        """
        def build_single_case_context(case_id: int) -> str:
            """
            Builds a formatted context message for a single case.
            
            Args:
                case_id (int): The case identifier.
                
            Returns:
                str: Formatted context message for the case.
            """
            # Retrieve all required metadata for the case
            metadata = self.get_all_required_metadata(case_id)
            
            # Build the context message components
            context_parts = []
            
            for field, value in metadata.items():
                if value is not None and value != "":
                    # Format the field name for better readability
                    formatted_field = field.replace('_', ' ').title()
                    context_parts.append(f"{formatted_field}: {value}")
                else:
                    self.logger.debug("Skipping empty field '%s' for case '%s'", field, case_id)
            
            # Combine all parts into a single context string
            if context_parts:
                # Add introductory message to clarify the purpose of this context data
                intro_message = "Additional case context (supplements historical data with key information):"
                context_message = f"{intro_message} {' | '.join(context_parts)}"
            else:
                context_message = "No additional context available"
            
            return context_message
        
        # Handle single case
        if isinstance(case_ids, int):
            return build_single_case_context(case_ids)
        
        # Handle multiple cases - format for clear AI understanding
        case_contexts = []
        for case_id in case_ids:
            case_context = build_single_case_context(case_id)
            # Format each case context with clear case ID identification
            formatted_case_context = f"**Case ID {case_id}:** {case_context}"
            case_contexts.append(formatted_case_context)
        
        # Join all case contexts with clear separation
        return "\n\n".join(case_contexts)

    # ─── METADATA RETRIEVAL METHODS ──────────────────────────────────────────────────────────
    
    @with_chunks("case_outcome")
    def _get_case_outcome(self, chunks: List[Dict[str, Any]], case_id: int, field_name: str) -> str:
        """
        Retrieve the outcome of the case.
        
        Args:
            chunks (List[Dict[str, Any]]): List of chunks to search through.
            case_id (int): The case identifier.
            field_name (str): The field name to extract.
            
        Returns:
            str: Unique case outcome values found, or empty string if none found
            May return multiple outcomes from the same case as a comma seperated value list.
        """
        case_outcomes = set()
        
        for chunk in chunks:
            case_outcome = chunk.get(field_name)
            if case_outcome and case_outcome.strip():
                self.logger.debug("Found case outcome '%s' for '%s'", case_outcome, case_id)
                case_outcomes.add(case_outcome.strip())
        
        # Return unique values as a comma-separated string
        return ", ".join(sorted(case_outcomes)) if case_outcomes else ""
    
    @with_chunks("settlement_value")
    def _get_settlement_value(self, chunks: List[Dict[str, Any]], case_id: int, field_name: str) -> str:
        """
        Retrieve settlement values from the case chunks. We search through to find all the unique
        settlement_values as different chunks may contain different values from the case so we need to combine and find them all.
        We skip the duplicate values as some chunks may contain these duplicates.
        
        Args:
            chunks (List[Dict[str, Any]]): List of chunks to search through.
            case_id (int): The case identifier.
            field_name (str): The field name to extract.
            
        Returns:
            str: Settlement values found, or empty string if none found.
        """
        settlement_values = set()
        
        for chunk in chunks:
            settlement_value = chunk.get(field_name)
            if settlement_value and settlement_value.strip():
                # Remove commas and convert to float for normalization
                try:
                    normalized_value = float(settlement_value.strip().replace(',', ''))
                    if normalized_value not in settlement_values:
                        self.logger.debug("Found settlement value '%s' for '%s'", normalized_value, case_id)
                        settlement_values.add(normalized_value)
                except ValueError:
                    self.logger.warning("Could not convert settlement value '%s' to float for case '%s'", settlement_value, case_id)

        total_value = sum(settlement_values) if settlement_values else 0.0
        if total_value == 0.0:
            self.logger.debug("No settlement value found for case '%s', returning 'None/Unknown'", case_id)
            return "None/Unknown"
        
        return total_value






        
