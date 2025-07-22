from utils import *
import math
from scripts.vectordb import QdrantManager
import numpy


config = load_config()

#TODO, refactor  recency_multiplier to use a scalable system where the values are stored in the config

# add algorithm for scoring based on types of injuries sustained. Can do same thing as our data_completeness score but with a dict of all injuries in our database with their average settlement values per jurisdiction.

class JurisdictionScoreManager:
    def __init__(self, qdrant_manager: QdrantManager):
        self.config = config
        self.logger = setup_logger(__name__, config)
        self.field_weights = self.config.get('jurisdiction_scoring', {}).get('field_weights', {})
        self.recency_weights = self.config.get('jurisdiction_scoring', {}).get('recency_weights', {})

    def score_jurisdiction(self, case_weight: float, settlement_value: int):
        jurisdiction_score = 0

    def calculate_data_completeness(self, case_data: dict) -> float:
        """
        Calculate weighted data completeness score for a case.
        
        Args:
            case_data (dict): Case metadata dictionary from vectorDB
            
        Returns:
            float: Data completeness score between 0.0 and 1.0
        """

        total_weighted_present = 0.0
        total_possible_weight = 0.0
        for field_name, weight in self.field_weights.items():
            if weight == 0.0:
                continue

            field_present = self._is_field_present(case_data, field_name)
            total_weighted_present += weight * field_present
            total_possible_weight += weight
            
        # Calculate completeness (handle division by zero)
        if total_possible_weight == 0:
            return 0.0
        
        data_completeness_score = total_weighted_present / total_possible_weight
        return data_completeness_score
    
    def _is_field_present(self, case_data: dict, field_name: str) -> int:
        """
        Check if a field is present and has meaningful data, need method for this because different values are stored different when empty.
        
        Args:
            case_data (dict): Case metadata dictionary
            field_name (str): Name of field to check
            
        Returns:
            int: 1 if field is present and meaningful, 0 if missing/empty
        """
        value = case_data.get(field_name)

        if value is None:
            return 0
        elif isinstance(value, str) and value.strip() == "":
            return 0
        elif isinstance(value, list) and len(value) == 0:
            return 0
        elif isinstance(value, (int, float)) and value == 0:
            return 0
        else:
            return 1

    def calculate_quality_multiplier(self, case_data: dict) -> float:
        """
        Calculate a quality multiplier based on the data completeness score.

        The square root is used to make the multiplier increase more slowly as completeness improves,
        so that small improvements in low-completeness cases have a bigger effect than small improvements in already high-completeness cases.

        Args:
            case_data (dict): The metadata dictionary for a case.

        Returns:
            float: The quality multiplier, which is a function of the data completeness score.
        """
        data_completeness_score = self.calculate_data_completeness(case_data)
        # Reason: sqrt flattens the curve, so the multiplier grows quickly at first and then levels off as completeness approaches 1
        quality_multiplier = 0.6 * (0.4 * math.sqrt(data_completeness_score))
        return quality_multiplier

    def calculate_recency_multiplier(self, case_data: dict) -> float:
        """
        Calculate a recency multiplier based on the age of the case.

        Args:
            case_data (dict): Case metadata containing incident_date

        Returns:
            float: The recency multiplier, which decreases as the case gets older.
        """
        case_age_years = self._calculate_case_age_years(case_data)
        x = case_age_years

        conditionlist = [x <= 1, (x > 1) & (x <= 3), (x > 3) & (x <= 5), x > 5] 
        functionlist = [1.0, 0.8, 0.6, 0.4] # multiplier depending on given age
        
        recency_multiplier = numpy.piecewise(x, conditionlist, functionlist)
        return recency_multiplier
        
    def score_case_weight(self, recency_mult: float, quality_mult: float) -> float:
        """
        Calculate the weighted score for a case using recency and quality multipliers.
        Defined as (settlement_value * recency_mult * quality_mult)
        Cases that are more recent and contain more complete data hold more weight.

        Args:
            recency_mult (float): The multiplier based on the recency of the case.
            quality_mult (float): The multiplier based on the quality/completeness of the case data.

        Returns:
            float: The weighted score for the case.
        """

        case_weight = (recency_mult * quality_mult)
        return case_weight

    def _calculate_case_age_years(self, case_data: dict) -> float:
        """
        Calculate the age of a case in years from incident_date.
        
        Args:
            case_data (dict): Case metadata containing incident_date
            
        Returns:
            float: Age of case in years
        """
        from datetime import datetime
        
        incident_date = case_data.get('incident_date')
        if not incident_date:
            return 5.0  # Default to 5 years if no date (gets lower recency weight)
        
        try:
            # Assuming incident_date is in format like "2023-05-15" or datetime object
            if isinstance(incident_date, str):
                case_date = datetime.strptime(incident_date, "%Y-%m-%d")
            else:
                case_date = incident_date
                
            years_old = (datetime.now() - case_date).days / 365.25
            return years_old
        except:
            return 5.0  # Default if date parsing fails

    def save_to_json(self, jurisdiction_data: dict, filename: str = 'jurisdiction_scores.json'):
        """
        Saves jurisdiction scoring data to JSON file.
        
        Args:
            jurisdiction_data (dict): The jurisdiction data to save.
            filename (str): The filename to save to. Defaults to 'jurisdiction_scores.json'.
        """
        # Use the utils save_to_json function with jurisdiction-specific defaults
        save_to_json(jurisdiction_data, default_filename=filename)
        self.logger.info(f"Saved jurisdiction data to {filename}")