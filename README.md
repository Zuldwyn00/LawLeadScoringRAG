# Legal RAG Lead Scoring System (Law_RAG)

An AI-assisted legal lead scoring and retrieval system. The project ingests legal documents (PDF/DOCX), applies OCR when needed, chunks and embeds text, stores vectors in Qdrant, and scores new leads against similar historical cases using Azure OpenAI. A Streamlit UI provides an interactive lead scoring experience with progress, logging, and explainable outputs.

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
- Streamlit web UI
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
    - Lead scoring: `scripts/clients/agents/scoring.py` (`LeadScoringClient`)
    - Summarization: `scripts/clients/agents/summarization.py` (`SummarizationClient`)
  - Tools: `scripts/clients/tools.py` (e.g., `get_file_context` with optional summarization)
  - Caching: `scripts/clients/caching/` (file-partitioned summary cache)
  - Chat logs: `scripts/clients/utils/chatlog.py`
- UI
  - `lead_scoring_ui.py` (Streamlit-based)
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
- streamlit
- numpy, PyYAML, python-dotenv, requests
- pytest

---

## Configuration

Edit `config.yaml`:

- `directories`: project-relative paths for data, logs, chat logs
- `logger`: level, format, filename, rotation
- `aiconfig.default_encoding`: token encoding base
- `jurisdiction_scoring.field_weights`: presence weights for metadata completeness
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
- `STREAMLIT_PASSWORD` — Password required by the UI

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

- Default server binds on `0.0.0.0:3000` and prints local and LAN URLs
- Authenticate using the `STREAMLIT_PASSWORD` environment variable
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
- `LeadScoringClient` → iterative tool loop and jurisdiction modifier

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

`JurisdictionScoreManager` computes a jurisdiction modifier using weighted historical settlements:
- Data completeness weighting driven by `jurisdiction_scoring.field_weights`
- Recency multiplier and quality multiplier
- Per-jurisdiction score is compared to the average to produce a bounded modifier applied to the lead score

Utilities exist to fetch cases by jurisdiction and extract highest settlements from payloads.

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
  - Confirm `STREAMLIT_PASSWORD` is set in environment

---

---

## License

See `LICENSE` for details.

