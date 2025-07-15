# Project Expansion: Ideas for Advanced RAG System

This document outlines potential features and architectural improvements to enhance the capabilities of the legal RAG project.

---

## 1. Dynamic Jurisdiction Scoring System

**Concept:**
Instead of relying on the AI's generalized knowledge to assess the value or difficulty of a legal jurisdiction, we should implement a programmatic scoring system. This provides consistent, data-driven, and easily updatable logic for evaluating a key factor in lead viability.

**Problem:**
The AI currently has no explicit guidance on which jurisdictions are more or less favorable. Its scoring is based on implicit knowledge from its training data, which can be inconsistent, outdated, or lack specific nuance for our use case.

**Proposed Solution:**
Create a dedicated module or configuration file that houses a "jurisdiction value algorithm." This would be a data structure (e.g., a dictionary, JSON object, or database table) that maps jurisdictions to a specific score, multiplier, or set of qualitative tags.

**Implementation Ideas:**
- **YAML/JSON Config File:** A simple `jurisdictions.yaml` could store the data.
  ```yaml
  # jurisdictions.yaml
  Suffolk County:
    score_modifier: 1.2
    notes: "Historically plaintiff-friendly juries."
  Nassau County:
    score_modifier: 0.9
    notes: "More conservative jury pool."
  New York County:
    score_modifier: 1.5
    notes: "High verdicts common, but high litigation costs."
  ```
- **Integration:** The lead scoring function would ingest this data and use the modifier when calculating the final lead score.

---

## 2. Context-Aware Summarization Agent

**Concept:**
Create a secondary AI agent that can be invoked by the main lead-scoring agent when the initial retrieved context is insufficient to make a high-confidence decision. This "Summarization Agent" would provide deeper, targeted summaries of source documents on demand.

**Problem:**
The initial vector search provides context chunks, but these snippets may lack the full story or specific critical details needed for an accurate lead analysis. Providing the full text of all source documents for every lead is prohibitively expensive in terms of token count.

**Proposed Solution:**
Implement a multi-agent workflow:

1.  **Initial Analysis:** The Lead Scoring Agent receives the lead and the top-k context chunks from the vector database.
2.  **Confidence Check:** The agent analyzes the lead with the given context and assesses its own confidence. It asks itself: "Do I have enough information to make a definitive recommendation?"
3.  **On-Demand Enrichment (Agent Invocation):** If confidence is low, the Lead Scoring Agent can trigger a `SummarizationAgent`. It would pass the source document identifiers for the most relevant chunks.
4.  **Targeted Summarization:** The `SummarizationAgent` fetches the full text of the requested document(s), reads them, and generates a new, concise summary tailored to the specifics of the lead being evaluated.
5.  **Final Analysis:** The summary is returned to the Lead Scoring Agent, which now has a much richer, more targeted context to complete its analysis and provide a final score.

**Benefits:**
- **Cost-Effective:** Keeps token usage low by default, only invoking the more expensive summarization process when necessary.
- **Improved Accuracy:** Provides a path to resolve ambiguity and get deeper insights, leading to better scoring.

---

## 3. Standardized Lead Intake and Formatting

**Concept:**
Develop a robust pre-processing system that ingests raw, unstructured lead information (e.g., from an email or a web form) and transforms it into a consistent, structured format before it reaches the scoring agent.

**Problem:**
The lead scoring AI's performance is highly dependent on the quality and format of the input. Unstructured text can lead to missed details, hallucinations, or inconsistent analysis. A lead described in a long paragraph is harder to analyze than one with clearly defined fields.

**Proposed Solution:**
Create a "Lead Formatting" module or Pydantic schema. This system would be the first point of contact for any new lead.

**Implementation Ideas:**
- **Pydantic Schemas:** Define a strict data model for what a "lead" looks like.
  ```python
  from pydantic import BaseModel, Field
  from typing import Optional

  class FormattedLead(BaseModel):
      jurisdiction: str = Field(..., description="The county and state where the incident occurred.")
      incident_date: Optional[str] = None
      injury_description: str
      case_summary: str
      has_reported_incident: Optional[bool] = None
      has_sought_medical_attention: Optional[bool] = None
  ```
- **Parsing Layer:** An initial AI call or a set of rules could be used to parse an incoming text blob and populate the fields of the `FormattedLead` model. This structured object would then be passed to the scoring pipeline.

**Benefits:**
- **Consistency:** Ensures the scoring AI always works with a predictable data structure.
- **Reliability:** Reduces the risk of the AI missing key information.
- **Clarity:** The structured data is easier to log, store, and debug. 