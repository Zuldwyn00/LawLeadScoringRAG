#TODO: Create a cluster analysis of the jurisdictions using a stratified analysis approach. We can then take each of these "groups" defined by their 
# data like case type, injuries, medical treatment, etc, and create a scoring algorithm that scores each group and then we can use this to get a total averaged
# score for the jurisdiction based on the weighted average of the scores of the groups. Maybe different weights for different things like types of injuries.

# We need to figure out the minimum viable product for this before delving deeper and making it more complex. How can we do this as simply as possible?
# Maybe we can start simple with just scoring the jurisdictions based on the average settlement values before adding in the other factors and introduce more logic as we go.


injury_severity_weights = {
    "none": 0,
    "minor": 1,
    "moderate": 2,
    "serious": 3,
    "severe": 4
}

case_type_weights = {
    #needs to be scored off of the historical data of the jurisdiction, maybe this is a seperate scoring algorithm were each jurisdiction has its own weights.
}

medical_treatment_weights = {
    "none": 0,
    "outpatient": 1,
    "inpatient": 2,
    "emergency": 3,
    "surgical": 4
}

employment_impact_weights = {
    "none": 0,
    "partial": 1,
    "full": 2
}

property_damage_weights = {
    "none": 0,
    "minor": 1,
    "moderate": 2,
    "serious": 3,
    "severe": 4
}





