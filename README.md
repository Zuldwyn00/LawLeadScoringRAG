# RAG-Based Lead Scoring System

## Overview

This project is an AI-powered lead scoring system that analyzes new leads against historical successful cases to predict the likelihood of success. The system uses a Retrieval-Augmented Generation (RAG) architecture to find similar past wins from a vector database and uses that context to generate evidence-based scores.

## Key Features

### Document Processing
- Supports multiple document formats (PDF, DOCX, TXT).
- Intelligently chunks text for effective processing.
- Extracts and stores metadata alongside document chunks.
- Automatically generates embeddings for text data.

### Lead Scoring
- Uses semantic similarity search to find relevant historical cases.
- Provides an evidence-based score.
- Generates a detailed rationale for each score.
- References the historical cases used for the analysis.

## Technology Stack

### Cloud Services
- **Azure OpenAI**: Used for text embeddings and chat completion models.
- **Qdrant Cloud**: Vector database for storing and retrieving document embeddings.

### Python Libraries
- `qdrant-client`
- `langchain`
- `langchain-openai`
- `pypdf2`
- `python-docx`
- `tiktoken`
- `python-dotenv`

## Architecture

### Client Architecture
The system uses a layered client architecture for AI interactions:

```
BaseClient (Abstract) → AzureClient → LeadScoringClient/SummarizationClient
```

- **BaseClient**: Abstract interface defining the contract for all AI clients
- **AzureClient**: Concrete implementation for Azure OpenAI services with message history management
- **Domain Clients**: Specialized clients (LeadScoringClient, SummarizationClient) that wrap the base client with domain-specific functionality

### Message History Management
Each client maintains a complete conversation history that includes:
- **System Messages**: Initial instructions and prompts
- **User Messages**: Input queries and lead descriptions
- **AI Responses**: Model-generated responses
- **Tool Calls**: AI requests to use external tools
- **Tool Outputs**: Results from tool executions

The message history is automatically populated during conversations and can be exported to JSON for analysis or debugging:

```python
from scripts.clients.utils.chatlog import dump_chat_log

# Export complete conversation history
dump_chat_log(client.message_history, "conversation_log.json")
```

## Setup and Installation

1.  **Clone the repository:**
    ```sh
    git clone <repository-url>
    cd Law_RAG
    ```

2.  **Create a virtual environment:**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    Install the required Python packages.
    ```sh
    pip install -requirements.txt
    ```

4.  **Configure environment variables:**
    Create a `.env` file in the root directory and add your API keys and endpoints. The project expects keys for Azure OpenAI and Qdrant.

## Usage

### Web Interface (Recommended)

The easiest way to use the lead scoring system is through the web interface:

1.  **Launch the UI:**
    ```sh
    python run_ui.py
    ```
    This will start a Streamlit web interface that automatically opens in your browser at `http://localhost:8501`.

2.  **Score Leads:**
    - Enter a detailed lead description in the text area
    - Click "Score Lead" to analyze the lead
    - View results with color-coded score blocks:
      - 🟢 **75-100**: High potential (Green)
      - 🟡 **50-75**: Medium potential (Yellow)  
      - 🟠 **25-50**: Low potential (Orange)
      - 🔴 **0-25**: Very low potential (Red)
    - Click on any scored lead to see the full detailed analysis

3.  **Features:**
    - Persistent session storage of scored leads
    - Color-coded visual scoring system
    - Expandable detailed analysis for each lead
    - Statistics sidebar showing total leads and average scores

### Command Line Interface

For advanced users, the primary functionalities can also be executed through `main.py`:

1.  **Process Documents:**
    Place your source documents into a directory. You will need to update the path inside the `embedding_test` function in `main.py` to point to your document directory. Then, run the function to process and store them in the vector database.

2.  **Score a New Lead:**
    To score a new lead, use the `score_test` function in `main.py`. You can modify the `new_lead_description` variable with the details of the lead you want to analyze.

To run either function, call it from the `main()` function in `main.py` and execute the script:
```sh
python main.py
```
The output will be printed to the console. 