# ─── IMPORTS AND CONFIGURATION ──────────────────────────────────────────────────────────
from utils import *
import math
import numpy


# ─── TODO COMMENTS ───────────────────────────────────────────────────────────────────────
# TODO, refactor  recency_multiplier to use a scalable system where the values are stored in the config

# add algorithm for scoring based on types of injuries sustained. Can do same thing as our data_completeness score but with a dict of all injuries in our database with their average settlement values per jurisdiction.

# implement incremental updates for jurisdiction scoring rather than having to recalculate everything every time

# TODO: Implement system for AI to be able to pull specific data it can use. For example the AI might see that our current case is a slip and fall case, so we allow it
# to search for all slip and fall cases and perhaps their average settlement values, and specify the county, etc. We need to allow the AI a suite of well-defined tools that
# don't give too much garbage data, but allow for a better scoring system.

# TODO: Make the Jurisdiction Scoring more robust so that we account for jurisdictions with less amounts of cases, we currently have a "confidence" multiplier we dont use,
# perhaps we can use this in an opposite way where jurisdictions with less cases hold a higher weight, or we can figure out some other algorithm for normalizing
# juridictions with low case counts.

# TODO: MAGIC NUMBERS - Get ride of the magic numbers like 0.6, 0.4, etc and use the config or something else.

# TODO: Average out the places with less cases by maybe dividing by the total average amount of cases each jurisdiction has or something?


# ─── JURISDICTION SCORE MANAGER CLASS ────────────────────────────────────────────────────
class JurisdictionScoreManager:
    def __init__(self):
        self.config = load_config()
        self.logger = setup_logger(__name__, self.config)
        self.field_weights = self.config.get("jurisdiction_scoring", {}).get(
            "field_weights", {}
        )
        self.recency_weights = self.config.get("jurisdiction_scoring", {}).get(
            "recency_weights", {}
        )

        # Load Bayesian shrinkage configuration
        bayesian_config = self.config.get("jurisdiction_scoring", {}).get(
            "bayesian_shrinkage", {}
        )
        self.conservative_factor = bayesian_config.get("conservative_factor", 10)

    # ─── CORE SCORING METHODS ────────────────────────────────────────────────────────────
    def score_jurisdiction(self, jurisdiction_cases: list):
        """
        Calculate jurisdiction score based on historical settlement data.

        Processes cases from a specific jurisdiction to generate a weighted average
        settlement value. Only cases with valid settlement values are considered.
        Each case is weighted by recency and data quality factors.

        Note: Deduplicates cases by case_id to prevent counting the same settlement
        multiple times when a case has multiple chunks.

        Args:
            jurisdiction_cases (list): List of case dictionaries containing settlement
                and metadata information from get_cases_by_jurisdiction.

        Returns:
            dict: Contains jurisdiction_score (weighted average settlement),
                confidence (0.0-1.0 based on case count), case_count,
                total_case_weight, and cases_processed details.

        Raises:
            Exception: If no valid cases found or case_weight_sum is zero.
        """

        # Step 1: Deduplicate cases by case_id to prevent settlement value inflation
        unique_cases = {}
        total_chunks = len(jurisdiction_cases)

        for case_data in jurisdiction_cases:
            case_id = case_data.get("case_id")
            if case_id and case_id not in unique_cases:
                unique_cases[case_id] = case_data

        self.logger.info(
            f"Deduplicated {total_chunks} chunks into {len(unique_cases)} unique cases"
        )

        case_weight_sum = 0.0
        weighted_settlement_sum = 0.0
        valid_cases = 0
        cases_processed = []

        # Step 2: Process unique cases only
        for case_data in unique_cases.values():
            case_id = case_data.get("case_id")
            self.logger.debug(
                "calculating case_weight for case '%s', source: '%s'.",
                case_data.get("source"),
                case_id,
            )
            try:  # get the settlement value, ensure its valid, and convert it to a useable float if it has extra data attached to it like a $ or is a string.
                settlement_raw = case_data.get("settlement_value")
                self.logger.debug(
                    f"Case {case_id}: raw settlement_value = '{settlement_raw}'"
                )
                if not settlement_raw or settlement_raw == "null":
                    self.logger.debug(f"Case {case_id}: skipping - no settlement value")
                    continue
                settlement_value = float(
                    str(settlement_raw).replace("$", "").replace(",", "")
                )
                if settlement_value <= 0:
                    self.logger.debug(
                        f"Case {case_id}: skipping - settlement value <= 0: {settlement_value}"
                    )
                    continue
                self.logger.debug(
                    f"Case {case_id}: valid settlement value: {settlement_value}"
                )
            except (ValueError, TypeError) as e:
                self.logger.debug(
                    f"Case {case_id}: skipping - settlement value parsing error: {e}"
                )
                continue

            # Calculate case weight (recency x quality)
            recency_mult = self.calculate_recency_multiplier(case_data)
            quality_mult = 1 #self.calculate_quality_multiplier(case_data) #TODO: IS QUALITY MULTIPLIER NECESSARY?

            case_weight = (
                recency_mult * quality_mult
            )  # can define case_weight in a seperate method if we decide to make the logic for it more complicated, currently unnecessary.

            self.logger.debug(
                f"Case {case_id}: recency_mult={recency_mult}, quality_mult={quality_mult}, case_weight={case_weight}"
            )

            weighted_settlement_sum += settlement_value * case_weight
            case_weight_sum += case_weight

            valid_cases += 1

            cases_processed.append(
                {
                    "case_id": case_data.get("case_id"),
                    "settlement_value": settlement_value,
                    "recency_multiplier": recency_mult,
                    "quality_multiplier": quality_mult,
                    "case_weight": case_weight,
                    "weighted_contribution": settlement_value * case_weight,
                }
            )

        # Log processing summary
        self.logger.info(f"Jurisdiction scoring summary:")
        self.logger.info(f"  - Total chunks input: {total_chunks}")
        self.logger.info(f"  - Unique cases found: {len(unique_cases)}")
        self.logger.info(f"  - Valid cases processed: {valid_cases}")
        self.logger.info(f"  - Case weight sum: {case_weight_sum}")
        self.logger.info(
            f"  - Weighted settlement sum: ${weighted_settlement_sum:,.2f}"
        )

        if case_weight_sum == 0:
            self.logger.warning(
                f"No valid settlement data found for jurisdiction scoring"
            )
            if len(unique_cases) > 0:
                # Log a sample case to debug
                sample_case = next(iter(unique_cases.values()))
                self.logger.warning(
                    f"Sample case (no settlement): {sample_case.get('case_id', 'unknown')} - settlement_value: {sample_case.get('settlement_value', 'None')}"
                )

            # Return a result with zero score and zero confidence instead of throwing exception
            result = {
                "jurisdiction_score": 0.0,
                "confidence": 0.0,
                "case_count": 0,
                "total_case_weight": 0.0,
                "cases_processed": [],
                "total_chunks_input": total_chunks,
                "unique_cases_found": len(unique_cases),
            }

            self.logger.info(
                f"  - Final jurisdiction score: $0.00 (no settlement data)"
            )
            self.logger.info(f"  - Confidence level: 0.00")
            return result
        else:
            jurisdiction_score = weighted_settlement_sum / case_weight_sum

        confidence = min(
            1.0, valid_cases / 10
        )  # TODO: use the config to handle what our accepted amount of cases is for confidence currently is 10

        result = {
            "jurisdiction_score": jurisdiction_score,
            "confidence": confidence,
            "case_count": valid_cases,
            "total_case_weight": case_weight_sum,
            "cases_processed": cases_processed,
            "total_chunks_input": total_chunks,
            "unique_cases_found": len(unique_cases),
        }
        # Log final result
        self.logger.info(
            f"  - Final jurisdiction score: ${result['jurisdiction_score']:,.2f}"
        )
        self.logger.info(f"  - Confidence level: {result['confidence']:.2f}")

        return result

    # ─── JURISDICTION MODIFIER METHODS ───────────────────────────────────────────────────
    def calculate_modifier_jurisdiction(self) -> dict:
        """
        Calculate and return jurisdiction modifiers based on scores.

        This method loads jurisdiction scores from JSON file, computes the average score,
        and then calculates a modifier for each jurisdiction as the ratio of its score to the average.

        Returns:
            dict: A dictionary mapping jurisdiction names to their modifier values.
        """

        all_scores = load_from_json(default_filename="jurisdiction_scores.json")

        if not all_scores:
            self.logger.warning("No scores found in 'jurisdiction_scores.json'.")
            return {}

        # Exclude jurisdictions with no settlement data (score = 0.0) from average calculation
        valid_scores = [score for score in all_scores.values() if score > 0.0]
        if not valid_scores:
            self.logger.warning("No valid scores found for modifier calculation.")
            return {}

        average_score = sum(valid_scores) / len(valid_scores)
        self.logger.info(
            "Calculated reference average: $%.2f from %s jurisdictions with data.",
            average_score,
            len(valid_scores),
        )

        modifiers = {}
        for jurisdiction, score in all_scores.items():
            if score == 0.0:
                # Jurisdictions with no settlement data get neutral 1.0x modifier
                modifier = 1.0
                self.logger.debug(
                    "%s: $%.2f -> %.3fx (no data, default)",
                    jurisdiction,
                    score,
                    modifier,
                )
            else:
                modifier = score / average_score
                modifier = max(
                    0.8, min(1.15, modifier)
                )  # Cap modifiers between 0.8x and 1.15x
                self.logger.debug("%s: $%.2f -> %.3fx", jurisdiction, score, modifier)

            modifiers[jurisdiction] = modifier

        return modifiers

    def get_jurisdiction_modifier(self, jurisdiction_name: str) -> float:
        """
        Get the modifier for a specific jurisdiction.

        Args:
            jurisdiction_name (str): Name of the jurisdiction

        Returns:
            float: Modifier value (default 1.0 if jurisdiction not found)
        """
        modifiers = self.calculate_modifier_jurisdiction()
        return modifiers.get(jurisdiction_name, 1.0)

    def bayesian_shrinkage(self, jurisdiction_case_counts: dict) -> dict:
        """
        Apply Bayesian shrinkage to jurisdiction scores to handle sample size bias
        Running this overwrites the original data in the jurisdiction_scores.json file with the new values from this function.

        Args:
            jurisdiction_case_counts: Dict mapping jurisdiction names to lists of case IDs

        Returns:
            dict: Mapping of jurisdiction names to their Bayesian-adjusted scores

        Note:
            Conservative factor is loaded from config at jurisdiction_scoring.bayesian_shrinkage.conservative_factor
            Higher values = more conservative = more shrinkage toward global average
        """
        #TODO: This shouldnt overwrite the original data, we should change this to only return the dict and we handle saving seperately, for now we dont really need to as
        # this is never really used outside of here and we arent needing to track that original data for now, easy enough to change later though so not a priority.
        self.logger.info("Starting Bayesian shrinkage adjustment...")

        # Step 1: Load existing jurisdiction scores (raw averages)
        raw_scores = load_from_json(default_filename="jurisdiction_scores.json")
        if not raw_scores:
            self.logger.warning(
                "No existing jurisdiction scores found. Run score_jurisdiction first."
            )
            return {}

        # Step 2: Calculate global average from raw scores (excluding jurisdictions with no data)
        valid_scores = [score for score in raw_scores.values() if score > 0.0]
        if not valid_scores:
            self.logger.warning("No valid scores found for global average calculation")
            return raw_scores

        global_average = sum(valid_scores) / len(valid_scores)
        self.logger.info(
            f"Global average calculated: ${global_average:,.2f} from {len(valid_scores)} jurisdictions with data"
        )

        # Step 3: Apply Bayesian shrinkage to each jurisdiction
        adjusted_scores = {}
        shrinkage_details = {}

        for jurisdiction, case_list in jurisdiction_case_counts.items():
            if jurisdiction not in raw_scores:
                self.logger.warning(
                    f"No raw score found for {jurisdiction}, skipping..."
                )
                continue

            # Get data for this jurisdiction
            raw_score = raw_scores[jurisdiction]
            case_count = len(case_list)

            # Skip Bayesian shrinkage for jurisdictions with no settlement data
            if raw_score == 0.0:
                adjusted_score = 0.0
                self.logger.info(
                    f"{jurisdiction}: No settlement data, keeping score at $0.00"
                )
            else:
                # Calculate confidence based on sample size
                confidence = case_count / (case_count + self.conservative_factor)

                # Apply Bayesian shrinkage formula
                adjusted_score = (confidence * raw_score) + (
                    (1 - confidence) * global_average
                )

            # Store results
            adjusted_scores[jurisdiction] = adjusted_score

            if raw_score == 0.0:
                shrinkage_details[jurisdiction] = {
                    "raw_score": raw_score,
                    "adjusted_score": adjusted_score,
                    "case_count": case_count,
                    "confidence": 0.0,
                    "shrinkage_amount": 0.0,
                    "shrinkage_direction": "no_data",
                }
            else:
                confidence = case_count / (case_count + self.conservative_factor)
                shrinkage_details[jurisdiction] = {
                    "raw_score": raw_score,
                    "adjusted_score": adjusted_score,
                    "case_count": case_count,
                    "confidence": confidence,
                    "shrinkage_amount": abs(raw_score - adjusted_score),
                    "shrinkage_direction": (
                        "toward_global"
                        if abs(adjusted_score - global_average)
                        < abs(raw_score - global_average)
                        else "away_from_global"
                    ),
                }

                self.logger.info(
                    f"{jurisdiction}: ${raw_score:,.0f} → ${adjusted_score:,.0f} "
                    f"(confidence: {confidence:.3f}, cases: {case_count})"
                )

        # Step 4: Save adjusted scores (overwrite the original file)
        self.save_to_json(adjusted_scores, "jurisdiction_scores.json")

        self.logger.info(
            f"Bayesian shrinkage completed for {len(adjusted_scores)} jurisdictions"
        )
        return adjusted_scores

    # ─── DATA QUALITY ASSESSMENT METHODS ─────────────────────────────────────────────────
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
        # Range: 0.6 (minimum) to 1.0 (maximum) - ensures all cases get at least some weight
        quality_multiplier = 0.6 + (0.4 * math.sqrt(data_completeness_score))
        return quality_multiplier

    # ─── RECENCY CALCULATION METHODS ─────────────────────────────────────────────────────
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
        functionlist = [
            1.0,
            0.8,
            0.6,
            0.4,
        ]  # multiplier depending on given age, older cases are less valuable

        recency_multiplier = numpy.piecewise(x, conditionlist, functionlist)
        return recency_multiplier

    def _calculate_case_age_years(self, case_data: dict) -> float:
        """
        Calculate the age of a case in years from incident_date.

        Args:
            case_data (dict): Case metadata containing incident_date

        Returns:
            float: Age of case in years
        """
        from datetime import datetime

        incident_date = case_data.get("incident_date")
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

    # ─── FILE I/O METHODS ────────────────────────────────────────────────────────────────
    def save_to_json(self, data: dict, filename: str = "jurisdiction_scores.json"):
        """
        Wrapper for utils.save_to_json() with jurisdiction-specific defaults and logging.

        Args:
            data (dict): The jurisdiction data to save.
            filename (str): The filename to save to. Defaults to 'jurisdiction_scores.json'.
        """
        # Use the utils save_to_json function with jurisdiction-specific defaults
        data_path = self.config.get("directories").get("jsons")
        save_to_json(data, default_filename=filename)
        self.logger.info(f"Saved jurisdiction data to {data_path}: {filename}")
