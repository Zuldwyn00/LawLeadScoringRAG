LEGAL LEAD SCORING AI SYSTEM
____________________________

USAGE:
Run by launching "legal_lead.bat" in the main folder.

DATA:
/scripts/data/


---LEAD SCORING---

****USE THE BUILT IN "START TUTORIAL BUTTON" FOR AN INTERACTIVE WALK-THROUGH!****

1. The first step to generating a lead-score for a legal case is by inputting the lead in plain-text in any format you like into the input text box. After waiting ~5 minutes or so a lead will be generated. 

2. The lead scores are now saved in the UI and will be re-loaded upon exiting and re-opening the application. The leads shown in the UI display just the data needed to understand at a first glance, but possess dropdown boxes for more extensive explanations.

3. Giving lead score FEEDBACK
* An extensive feedback system is in place as well to help refine the AI later with more data. The user can click on the given lead score and change this to whatever number they wish The original data is saved alongside the change for training purposes later. The user can even open the AI Analysis view and highlight text and edit it, this is also saved original and changed in a feedback file specific to the scored lead. 

* The leads generated go through an iterative scoring process, where the AI is able to continually refine its information and gather more through tool-useage to access the backend data. This process hits a pre-defined limit based on either the tool-usage or other back-end factors that can be chosen like the AI hitting a certain "confidence threshold" in it's given score to prevent unlimited costs. The tool_call limit which is the main defined limit can be easily changed from the UI to allow for longer lead-scoring sessions along with changing how much initial data is given to it. This extra data may have a trade-off between higher price, and better accuracy, but may actually also lead to worse accuracy depending if the data given back is junk. Too much data can be bad, so more extensive testing to find an optimized amount is needed but not feasible for my small-scale testing currently to find the perfect amount for business optimization on a large-scale balancing price, accuracy, and speed but this is why it exists to be able to do so.

* The final lead is then generated alongside some lead quick tips in order to provide a quick, concise summary of the lead at a glance but can also be expanded to show a detailed analysis, recommendations, and missing data along with direct comparisons to other cases along with their case IDs in order to find the data. All the data used by the AI can be backtracked to manually review easily, the chunk-view allows the user to see exactly what file what information was garnered from in the initial lead though does not currently show the iterative processes new data, but could be added with little difficulty by storing the data temporarily somewhere on the disk.

---LEAD DISCUSSION---

Building upon the modular AI framework I built this and my Legal Notebook application ontop of, I also added a discussion feature. This feature allows the user to discuss with an AI directly about the given lead. The AI receives data about the given lead-score that is to be discussed. 

1. Pressing "Discuss Lead" on any scored lead opens a chat window in which the user can request the AI to find more data, discuss existing data, and ask the AI for ideas and to assist in the next steps on what is missing, what is needed, why the score was scored as such, summaries for files, etc. Overall a tool that is much more than simple lead-discussion, but able to be easily expanded to a legal firms entire case data to be a knowledgebase for it all.

    * In order to expand this further, more complex categorization of the data would be needed 	like specific medical record categories, injury types, etc in order to search through 	a much larger amount of data more viably but this is not a matter of difficulty, just 	good data and scaling it up to be more refined.

    * The AI surrounds important sentences, and phrases with ** **, which is then colored in 	the UI and remove the asterisks to give an easier to skim through discussion about the 	lead so the user can focus more and not get bored by reading all the extra text. The 	colorful highlighting even serves as a good psychological factor to move the eye 	around without "dozing off" if we keep a bright, contrasting color for encouraging 	alertness. I understand just because we build a system, doesn't mean people will use 	it exactly as we want, so while I ensured to make all the data needed available, I 	made sure to provide easier ways to view it since there will not always be time, or 	human interest in reading it all.


DETAILS ABOUT THE BACKEND
________________________

On the backend the AI has a modular tool framework that can be easily added to for new tools, easily add new AI agents for specific tasks, add new configs for new AI agents easily, and more. 

JURISDICTION SCORING (DEFUNCT FOR NOW, BUT IMPORTANT)

The program also possesses a jurisdiction specific scoring algorithm to modify the AI's final lead score based on data derived from the historical cases. The reason it is no longer enabled, but still present in the code, is because the data I was using was at first faux, and upon using our real firms data there were not enough settlement values to determine a good jurisdiction score on how well they do.

The algorithm it uses is as so:

**High Case Count** (e.g., Suffolk County: 100 cases):
- `confidence = 100 / (100 + 10) = 0.909` (91% confident)
- `adjusted_score ≈ 0.91 × raw_score + 0.09 × global_average`
- **Result**: Minimal shrinkage, trusts the local average

**Low Case Count** (e.g., Queens County: 8 cases):
- `confidence = 8 / (8 + 10) = 0.444` (44% confident)  
- `adjusted_score ≈ 0.44 × raw_score + 0.56 × global_average`
- **Result**: Heavy shrinkage toward global average

NOTE: The "confidence" score ended up over-complicating things but is a great framework to have learned from and see what data to use. This includes the settlement_weights which were dictated by how many fields of data each "chunk" of a case found by a vector search contained in its metadata. This system is EASILY re-activated, all I would need to do is gather cases with real settlement_values and read down the settlement_value list and the jurisdiction. 

WHY I DIDN'T FIX IT:
The original system used faux data in preparation before I knew what the real data had. The real data in our system does not possess consistent Jurisdictions and is basically unuseable to figure out what case is from what specific jurisdiction from what I could find in SmartAdvocate. The field exists, but it is seldom filled out so the data is junk for jurisdiction scoring. Instead, a pre-defined "base" modifier for each jurisdiction can also be added, and actually already is present in a basic form where 0 settlement data gives back a default 1.0 modifier for the lead score. This way, even if settlement data for a jurisdiction doesnt exist, we still have the pre-defined modifiers based on our firms interests to fall back on rather than real data.

### Implementation Steps

1. **Calculate raw jurisdiction scores** using weighted settlements:
   - Data completeness weighting (`jurisdiction_scoring.field_weights`)
   - Recency multiplier (newer cases weighted higher)
   - Quality multiplier (complete data weighted higher)

2. **Apply Bayesian shrinkage**:
   - Calculate global average across all jurisdictions
   - For each jurisdiction: adjust raw score using shrinkage formula
   - Save adjusted scores to `jurisdiction_scores.json`

3. **Generate final modifiers**:
   - Compare adjusted scores to adjusted average
   - Apply modifier caps (0.8x to 1.15x)
   - Use in lead scoring to modify AI-generated scores

### Tuning Parameters

**Conservative Factor** (`conservative_factor`):
- **Lower values (5)**: Less shrinkage, trust local averages more
- **Higher values (50)**: More shrinkage, pull toward global average more
- **Default (10)**: Balanced approach

**Field Weights** (`config.jurisdiction_scoring.field_weights`):
```yaml
jurisdiction_scoring:
  field_weights:
    settlement_value: 1.0
    jurisdiction: 0.8
    case_type: 0.6
    # ... other metadata fields
```

### Example Impact

**Before Bayesian Shrinkage**:
- Suffolk County (100 cases): $124K → 1.20x modifier
- Queens County (8 cases): $350K → 3.40x modifier ❌ *Unreliable*

**After Bayesian Shrinkage** (conservative_factor=10):
- Suffolk County: $124K → $119K → 1.15x modifier  
- Queens County: $350K → $180K → 1.10x modifier ✅ *More realistic*

**Testing Different Conservative Factors**:
Run `python -m pytest tests/scripts/jurisdiction_scoring/test_jurisdictionscoring.py -v -s` to see how different conservative factors affect jurisdiction balance.


