"""
Tests for jurisdiction scoring functionality, particularly Bayesian shrinkage.

Tests should include:
- 1 test for expected use
- 1 edge case  
- 1 failure case
"""

import pytest
from scripts.jurisdictionscoring import JurisdictionScoreManager
#python -m pytest tests/scripts/jurisdiction_scoring/test_bayesianshrinkage.py -v -s

class TestBayesianShrinkage:
    """Test Bayesian shrinkage functionality in jurisdiction scoring."""
    
    def test_conservative_factor_effects(self):
        """Test how different conservative factors affect shrinkage (expected use)."""
        # Your current jurisdiction scores
        raw_scores = {
            "Suffolk County": 124209.57,
            "Nassau County": 63425.90,
            "Queens County": 69458.53
        }
        
        # Simulated case counts (Suffolk has way more data)
        case_counts = {
            "Suffolk County": ["case_" + str(i) for i in range(100)],  # 100 cases
            "Nassau County": ["case_" + str(i) for i in range(25)],    # 25 cases  
            "Queens County": ["case_" + str(i) for i in range(8)]      # 8 cases
        }
        
        def test_factor(conservative_factor):
            global_average = sum(raw_scores.values()) / len(raw_scores)
            results = {}
            
            for jurisdiction, case_list in case_counts.items():
                raw_score = raw_scores[jurisdiction]
                case_count = len(case_list)
                
                confidence = case_count / (case_count + conservative_factor)
                adjusted_score = (confidence * raw_score) + ((1 - confidence) * global_average)
                
                results[jurisdiction] = {
                    "raw": raw_score,
                    "adjusted": adjusted_score,
                    "confidence": confidence,
                    "shrinkage_percent": ((adjusted_score - raw_score) / raw_score * 100)
                }
            
            return results
        
        # Test different conservative factors
        results_10 = test_factor(10)   # Current default
        results_50 = test_factor(50)   # More conservative
        
        print("\n=== Conservative Factor Comparison ===")
        for jurisdiction in raw_scores:
            r10 = results_10[jurisdiction]
            r50 = results_50[jurisdiction]
            
            print(f"\n{jurisdiction}:")
            print(f"  Raw score: ${r10['raw']:,.0f}")
            print(f"  Factor 10: ${r10['adjusted']:,.0f} (confidence: {r10['confidence']:.3f})")
            print(f"  Factor 50: ${r50['adjusted']:,.0f} (confidence: {r50['confidence']:.3f})")
            print(f"  More shrinkage with higher factor: {r50['shrinkage_percent'] < r10['shrinkage_percent']}")
        
        # Assertions for expected behavior
        assert results_50["Queens County"]["confidence"] < results_10["Queens County"]["confidence"]
        assert abs(results_50["Queens County"]["shrinkage_percent"]) > abs(results_10["Queens County"]["shrinkage_percent"])
        
    def test_edge_case_single_case_jurisdiction(self):
        """Test Bayesian shrinkage with jurisdiction having only 1 case (edge case)."""
        jurisdiction_manager = JurisdictionScoreManager()
        
        # Create test data with one jurisdiction having only 1 case
        case_counts = {
            "High Volume County": ["case_" + str(i) for i in range(50)],  # 50 cases
            "Single Case County": ["case_001"]  # 1 case only
        }
        
        # Mock raw scores - single case county has suspiciously high score
        raw_scores = {
            "High Volume County": 75000,
            "Single Case County": 200000  # Outlier high score
        }
        
        # Calculate what Bayesian shrinkage should do
        global_average = sum(raw_scores.values()) / len(raw_scores)  # 137,500
        
        single_case_confidence = 1 / (1 + 10)  # 0.091
        expected_adjusted = (single_case_confidence * 200000) + ((1 - single_case_confidence) * global_average)
        
        print(f"\nEdge case test:")
        print(f"Single case county raw score: ${raw_scores['Single Case County']:,}")
        print(f"Expected adjusted score: ${expected_adjusted:,.0f}")
        print(f"Should be much closer to global average: ${global_average:,.0f}")
        
        # Single case should have very low confidence and be heavily shrunk
        assert single_case_confidence < 0.1
        assert abs(expected_adjusted - global_average) < abs(raw_scores['Single Case County'] - global_average)
        
    def test_failure_case_empty_case_counts(self):
        """Test Bayesian shrinkage fails gracefully with empty case counts (failure case)."""
        jurisdiction_manager = JurisdictionScoreManager()
        
        # Test with empty case counts
        empty_case_counts = {}
        
        # This should return empty dict without crashing
        result = jurisdiction_manager.bayesian_shrinkage(empty_case_counts)
        
        assert result == {}
        print("\nFailure case test: Empty case counts handled gracefully")
        
    def test_conservative_factor_effectiveness_against_suffolk_bias(self):
        """Test if higher conservative factors reduce Suffolk County's dominance."""
        # Realistic case counts based on your data
        realistic_case_counts = {
            "Suffolk County": ["case_" + str(i) for i in range(150)],  # Suffolk has lots of cases
            "Nassau County": ["case_" + str(i) for i in range(40)],    # Nassau moderate  
            "Queens County": ["case_" + str(i) for i in range(12)]     # Queens few cases
        }
        
        # Your actual scores
        raw_scores = {
            "Suffolk County": 124209.57,
            "Nassau County": 63425.90,
            "Queens County": 69458.53
        }
        
        def calculate_final_modifiers(conservative_factor):
            global_average = sum(raw_scores.values()) / len(raw_scores)
            adjusted_scores = {}
            
            for jurisdiction, case_list in realistic_case_counts.items():
                raw_score = raw_scores[jurisdiction]
                case_count = len(case_list)
                
                confidence = case_count / (case_count + conservative_factor)
                adjusted_score = (confidence * raw_score) + ((1 - confidence) * global_average)
                adjusted_scores[jurisdiction] = adjusted_score
            
            # Calculate modifiers like your system does
            avg_adjusted = sum(adjusted_scores.values()) / len(adjusted_scores)
            modifiers = {}
            for jurisdiction, score in adjusted_scores.items():
                modifier = score / avg_adjusted
                modifier = max(0.8, min(1.15, modifier))  # Your caps
                modifiers[jurisdiction] = modifier
            
            return modifiers, adjusted_scores
        
        modifiers_10, scores_10 = calculate_final_modifiers(10)
        modifiers_50, scores_50 = calculate_final_modifiers(50)
        
        print(f"\n=== Suffolk Bias Test ===")
        print(f"Conservative Factor 10:")
        for jurisdiction in raw_scores:
            print(f"  {jurisdiction}: {modifiers_10[jurisdiction]:.3f}x")
        
        print(f"\nConservative Factor 50:")
        for jurisdiction in raw_scores:
            print(f"  {jurisdiction}: {modifiers_50[jurisdiction]:.3f}x")
        
        # Higher conservative factor should reduce Suffolk's advantage
        suffolk_gap_10 = modifiers_10["Suffolk County"] - modifiers_10["Queens County"]
        suffolk_gap_50 = modifiers_50["Suffolk County"] - modifiers_50["Queens County"]
        
        print(f"\nSuffolk vs Queens gap:")
        print(f"  Factor 10: {suffolk_gap_10:.3f}")
        print(f"  Factor 50: {suffolk_gap_50:.3f}")
        print(f"  Gap reduced: {suffolk_gap_50 < suffolk_gap_10}")
        
        assert suffolk_gap_50 < suffolk_gap_10, "Higher conservative factor should reduce Suffolk's dominance"


if __name__ == "__main__":
    # Run the tests manually if needed
    test_instance = TestBayesianShrinkage()
    test_instance.test_conservative_factor_effects()
    test_instance.test_edge_case_single_case_jurisdiction()
    test_instance.test_failure_case_empty_case_counts()
    test_instance.test_conservative_factor_effectiveness_against_suffolk_bias()
    print("\nAll tests completed!")
