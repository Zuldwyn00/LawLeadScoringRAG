# Legal RAG Lead Scoring System (Law_RAG)

An AI-assisted legal lead scoring and retrieval system. The project ingests legal documents (PDF/DOCX), applies OCR when needed, chunks and embeds text, stores vectors in Qdrant, and scores new leads against similar historical cases using Azure OpenAI. A customtkiner UI provides an interactive lead scoring experience with progress, logging, and explainable outputs.

---

## Key Capabilities

- Document ingestion pipeline
  - OCR for PDFs via `ocrmypdf`
  - Parsing via Apache Tika (PDF/DOCX)
  - Token-based chunking with LangChain `TokenTextSplitter`
  - Optional AI metadata extraction (structured JSON) for each chunk
- Vector database
  - Qdrant-backed storage of chunk embeddings and rich payload metadata
  - Semantic search to build historical case context
- Lead scoring engine
  - Iterative tool-usage workflow with a bounded number of file reads
  - Jurisdiction-aware modifiers based on historical settlement data
  - Optional no-tools final pass on a separate model
- Summarization and caching
  - AI document summarization agent
  - File-backed, partitioned cache for summaries (cost and latency reduction)
- Persisted chat logs (JSON + human-readable text)
  - Progress status, logs, and color-coded score/confidence presentation
- Configurable via `config.yaml` and `prompts.yaml`


---

## Architecture Overview

- Core modules
  - Vector DB: `scripts/vectordb.py` (`QdrantManager`)
  - File handling & OCR: `scripts/filemanagement.py`
  - Jurisdiction scoring: `scripts/jurisdictionscoring.py`
  - Utilities: `utils.py` (config, logging, JSON IO, token counting)
  - Prompts: `prompts.yaml`
- Clients and agents (modular layering under `scripts/clients/`)
  - Base layer: `BaseClient` (`scripts/clients/base.py`)
  - Azure client: `AzureClient` (`scripts/clients/azure.py`) configured via `scripts/clients/client_configs.json`
  - Domain agents:
    - Lead scoring: `scripts/clients/agents/scoring.py` (`LeadScoringAgent`)
    - Summarization: `scripts/clients/agents/summarization.py` (`SummarizationAgent`)
  - Tools: `scripts/clients/tools.py` (e.g., `get_file_context` with optional summarization)
  - Caching: `scripts/clients/caching/` (file-partitioned summary cache)
  - Chat logs: `scripts/clients/utils/chatlog.py`
- UI
  - `scripts/ui/` (customtkinter based UI)
  - `run_ui.py` launcher (sets host/port and prints access URLs)
- CLI/entry points (ad-hoc)
  - `main.py` contains callable functions for embedding and scoring tests

High-level flow

1. Ingest documents → OCR (optional) → parse → chunk → embed → upsert to Qdrant with payload metadata
2. Score a new lead → embed lead description → semantic search in Qdrant → assemble historical context → iterative tool loop → modifiers → final analysis

---

## Requirements

- Python 3.10+
- Qdrant (cloud or self-hosted)
- Azure OpenAI credentials

Python dependencies are pinned in `requirements.txt`:
- LangChain, langchain-openai, langchain-text-splitters, tiktoken
- qdrant-client
- ocrmypdf, PyMuPDF, tika
- customtkinter
- numpy, PyYAML, python-dotenv, requests
- pytest

---

## Configuration

Edit `config.yaml`:

- `directories`: project-relative paths for data, logs, chat logs
- `logger`: level, format, filename, rotation
- `aiconfig.default_encoding`: token encoding base
- `jurisdiction_scoring.field_weights`: presence weights for metadata completeness
- `jurisdiction_scoring.bayesian_shrinkage`: fields involved in the bayesian shrinkage for jurisdiction scoring
- `caching.directories`: path forcache partitions

Prompts are defined in `prompts.yaml`:
- `injury_metadata_extraction`: JSON-structured extraction for chunk metadata
- `lead_scoring`: iterative tool-usage and final output format
- `summarize_text`: summarization with PII anonymization

Client model/deployment configs are in `scripts/clients/client_configs.json`.

---

## Environment Variables

Create a `.env` file in the project root or set environment variables in your shell:

- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY` — Azure OpenAI API key
- `QDRANT_URL` — Qdrant endpoint URL
- `QDRANT_KEY` — Qdrant API key (if required)

`qdrant_client` loads env via `python-dotenv` in `scripts/vectordb.py`.

---

## Setup

```bash
# from repo root
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Ensure Qdrant is reachable at `QDRANT_URL` with a valid key if required.



Notes
- `embedding_test` will:
  - Create (if missing) a `case_files` collection
  - Parse, chunk, embed, and upsert chunks with metadata payloads
  - Track processed files in `scripts/data/jsons/processed_files.json`
- Tika may require Java to be available in PATH when parsing PDFs/DOCX.

---

## Run the Lead Scoring UI

```bash
python run_ui.py
```

- Paste a lead description and click "Score Lead"
- The app shows progress, animated status, logs, and a final analysis with:
  - Lead Score (0–100)
  - Confidence (0–100)
  - Jurisdiction
  - Executive summary, detailed rationale, tool usage summary
- Scored leads list is retained in the current session; an example lead is provided

Chat logs are saved under the `directories.chat_logs` path configured in `config.yaml`.

---

## Programmatic Lead Scoring (no UI)

`main.py` contains a `score_test()` illustrating the end-to-end flow using:
- `QdrantManager.search_vectors` → historical context
- `LeadScoringAgent` → iterative tool loop and jurisdiction modifier

Run the example:

```bash
# Windows PowerShell
py -c "from main import score_test; score_test()"
```

This prints the full analysis to stdout and writes a chat log under `scripts/data/chat_logs/`.

---

## Caching

- Summary cache is file-backed and partitioned: `config.caching.directories.summary`
- Cache keys are `{source_file}#{client}` (client is the configured model key)
- The summarization agent checks cache before calling the model and writes after
- Tested under `tests/scripts/clients/caching/test_cachemanager.py`

---

## Jurisdiction Scoring

`JurisdictionScoreManager` computes jurisdiction modifiers using weighted historical settlements with **Bayesian shrinkage** to handle sample size bias. This prevents jurisdictions with few cases from having unreliably high or low scores.

### The Sample Size Bias Problem

Raw jurisdiction averages can be misleading:
- **High-volume jurisdictions** (e.g., Suffolk County): Many cases, stable averages
- **Low-volume jurisdictions** (e.g., Queens County): Few cases, potentially inflated/deflated averages
- **Without adjustment**: Low-volume jurisdictions with lucky high settlements get unrealistically high modifiers

### Bayesian Shrinkage Solution

**Core Concept**: Pull unreliable estimates toward a global average based on confidence.

**Mathematical Formula**:
```
confidence = case_count / (case_count + conservative_factor)
adjusted_score = (confidence × raw_score) + ((1 - confidence) × global_average)
```

**Where**:
- `case_count`: Number of cases for this jurisdiction
- `conservative_factor`: How much shrinkage to apply (default: 10)
- `raw_score`: Jurisdiction's weighted average settlement
- `global_average`: Average across all jurisdictions

### How It Works

**High Case Count** (e.g., Suffolk County: 100 cases):
- `confidence = 100 / (100 + 10) = 0.909` (91% confident)
- `adjusted_score ≈ 0.91 × raw_score + 0.09 × global_average`
- **Result**: Minimal shrinkage, trusts the local average

**Low Case Count** (e.g., Queens County: 8 cases):
- `confidence = 8 / (8 + 10) = 0.444` (44% confident)  
- `adjusted_score ≈ 0.44 × raw_score + 0.56 × global_average`
- **Result**: Heavy shrinkage toward global average

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

### Usage in Lead Scoring

The AI scoring system automatically uses Bayesian-adjusted jurisdiction modifiers:

1. AI generates base score (1-100)
2. AI extracts jurisdiction from case description  
3. System applies jurisdiction modifier: `final_score = base_score × modifier`
4. Final score is capped within bounds (1-100)

This ensures that **sample size bias doesn't artificially inflate scores** for jurisdictions with limited historical data.

---

## Data Stored in Qdrant Payloads

The system uses rich payloads per chunk. Typical fields include:
- `case_id`, `jurisdiction`, `case_type`, `incident_date`, `incident_location`
- `mentioned_locations`, `injuries_described`, `medical_treatment_mentioned`
- `employment_impact_mentioned`, `property_damage_mentioned`
- `entities_mentioned`, `insurance_mentioned`, `witnesses_mentioned`, `prior_legal_representation_mentioned`
- `case_outcome`, `settlement_value`, `communication_channel`
- `source`, `key_phrases`, `summary`

The historical context builder serializes these payloads to JSON and feeds them to the scoring prompt.

---

## Testing

```bash
pytest -q
```

Included tests cover the summary cache manager’s partitioning and retrieval logic.

---

## Logging

- Rotating file logging is configured via `config.yaml`
- Default log file: `logs/pdf_scraper.log`
- The UI also tracks a per-session processing log shown in an expander

---

## Project Structure (abridged)

```
Law_RAG/
  config.yaml
  main.py
  lead_scoring_ui.py
  run_ui.py
  prompts.yaml
  scripts/
    aiclients.py                 # legacy (deprecated)
    vectordb.py                  # QdrantManager
    filemanagement.py            # OCR, parsing, chunking
    jurisdictionscoring.py       # jurisdiction modifiers
    clients/
      base.py
      azure.py
      client_configs.json
      tools.py
      agents/
        scoring.py
        summarization.py
        utils/summarization_registry.py
      caching/
        cachemanager.py
        cacheschema.py
        hashing.py
      utils/chatlog.py
  tests/
    scripts/clients/caching/test_cachemanager.py
  logs/
  documentation/
```

---

## Common Issues & Troubleshooting

- Qdrant connection errors
  - Verify `QDRANT_URL` and `QDRANT_KEY`
  - Ensure the collection `case_files` exists (created by `embedding_test`)
- Empty or weak historical context
  - Ensure documents were ingested and payloads include useful fields
  - Consider OCR’ing scanned PDFs before ingestion
- Tika parsing failures or slowness
  - Ensure Java is installed and in PATH
- Azure OpenAI authentication failures
  - Verify `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY`
- UI password rejected

---

---

## License

See `LICENSE` for details.

