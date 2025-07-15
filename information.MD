I need to use some multimodal LLM for photo processing for things like injury charts and etc, but that is out of budget right now.




**Basic Chatbot Overview**
    * A dict containingthe message history is made:

    messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Hi AI, how are you today?"),
    AIMessage(content="I'm great thank you. How can I help you?"),
    HumanMessage(content="I'd like to understand machine learning.")
    ]     
    
    This allows the AI to use this message history dict as the item it pulls information from for the next queries the user might have. You then add to this dict for each response and question given, THEN you invoke the ai to answer by giving it the dict with a new line marked as the "HumanMessage" class and the AI will add its response to the dict, then return the dict.


**RAG Chatbot Overview**
    * One LLM searches through the vectorDB for relevant information, and returns mulitple sources it considers relevant, then the chatbot answers the question based on these sources.

    * Remember RAG is not always neccessary, if we are using a chatbot and a user asks "Hi, how are you?" We dont need to have the input go through RAG.


• **Set up Azure Resources**: Create Azure OpenAI (with an embedding model and a chat model deployment) and Azure AI Search instances in the Azure portal.

• **Prepare Data Source**: Create an Azure Blob Storage container and upload your raw successful lead documents (e.g., PDFs, DOCX, TXT files).

• **Configure Automated Indexing**: In Azure AI Studio, use the "Add your data" feature to connect Blob Storage and your OpenAI embedding model to Azure AI Search. This will create the indexer, data source, and skillset to automate the RAG pipeline.

• **Verify Index**: After the first run, go to your Azure AI Search resource in the portal and verify that the index has been populated with your documents.

• **Setup Python Project**: Create a virtual environment, a `.env` file for your API keys and endpoints, and install the required libraries: `langchain`, `langchain-openai`, `azure-search-documents`, `python-dotenv`.

• **Implement the Retriever**: In your Python code, write the logic to connect to the Azure AI Search index created in the previous steps. This will be your primary mechanism for retrieving relevant documents.

• **Build the RAG Chain**: In Python, create the end-to-end LangChain pipeline. This chain will:
  1. Take new lead data as input
  2. Use the Azure AI Search retriever to find similar past cases
  3. Format a detailed prompt with the retrieved cases as context
  4. Call the LLM to get the score and rationale

• **Develop User Interface (CLI)**: Create a simple command-line interface in your `chatbot.py` that allows you to paste in new lead information and see the generated score and rationale.

• **Test and Refine**: Test the entire system with various examples of new leads (good, bad, and borderline). Based on the results, refine the prompt template and the number of documents retrieved to improve accuracy.