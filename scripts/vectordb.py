import os
from dotenv import load_dotenv
from huggingface_hub import load_torch_model
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_openai import AzureOpenAIEmbeddings
from typing import List
import uuid

from utils import load_config, setup_logger

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)
load_dotenv('./.env')

class QdrantManager:
    def __init__(self):
        self.config = config
        self.client = self._initialize_client()
        self.vector_config = {
            "chunk": models.VectorParams(size=1536, distance=models.Distance.COSINE),
            "summar": models.VectorParams(size=1536, distance=models.Distance.COSINE)
        }

    def _initialize_client(self):
        qclient = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_KEY")
        )
        return qclient
    
    def create_collection(self, collection_name:str, vector_config:dict = None) -> bool:
        """
        Creates a new vector collection in the database.

        Args:
            collection_name (str): Name of the collection to create.
            vector_config (dict, optional): Vector configuration. Uses default if None.

        Returns:
            bool: True if collection created successfully, False otherwise.
        """
        if not vector_config:
            vector_config = self.vector_config
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=vector_config
            )
            return True
        
        except Exception as e:
            print(f"Error creating collection: {e}")
        return False

    def add_embedding(self, collection_name: str, embedding: List[float], metadata: dict, vector_name: str = "chunk"):
        """
        Adds a single embedding to the collection.

        Args:
            collection_name (str): Name of the collection.
            embedding (List[float]): The embedding vector to add.
            vector_name (str): Name of the vector field. Defaults to "chunk".
            metadata (dict): Optional metadata to store with the embedding.
        """
        point = models.PointStruct(
            id=str(uuid.uuid4()),
            vector={vector_name: embedding},
            payload=metadata or {}
        )
        self.client.upsert(collection_name=collection_name, points=[point])

    def add_embeddings_batch(self, collection_name: str, embeddings: List[List[float]], metadatas: List[dict], vector_name: str = "chunk"):
        """
        Adds a batch of embeddings to the collection.

        Args:
            collection_name (str): Name of the collection.
            embeddings (List[List[float]]): A list of embedding vectors to add.
            metadatas (List[dict]): A list of metadata dictionaries.
            vector_name (str): Name of the vector field. Defaults to "chunk".
        """
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector={vector_name: embedding},
                payload=metadata or {}
            )
            for embedding, metadata in zip(embeddings, metadatas) #zip combines the embeddings and metadatas into one iterable list, so for I in embedding and I in metadatas is basically what the loop is
        ]
        self.client.upsert(collection_name=collection_name, points=points)

    def search_vectors(self, collection_name: str, query_vector: List[float], vector_name: str = "chunk", limit: int = 5) -> list:
        """
        Searches for similar vectors in the collection.

        Args:
            collection_name (str): Name of the collection.
            query_vector (List[float]): The vector to search with.
            vector_name (str, optional): The name of the vector to search against. Defaults to "chunk".
            limit (int, optional): The maximum number of results to return. Defaults to 5.

        Returns:
            list: A list of search results.
        """
        try:
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=(vector_name, query_vector),
                limit=limit
            )
            return search_result
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            return []
        
    def get_context(self, search_results: list) -> str:
        """
        Constructs a well-structured context string from search results.

        Args:
            search_results (list): A list of search results from the vector database.

        Returns:
            str: A formatted string containing the context from the search results.
        """
        context = "Relevant information:\n"
        for result in search_results:
            
            # Construct a well-structured string with all metadata for the LLM
            payload = result.payload
            case_details = f"""- Source: {payload.get('source', 'N/A')}
            Case ID: {payload.get('case_id', 'N/A')}
            Case Type: {payload.get('case_type', 'N/A')}
            Outcome: {payload.get('case_outcome', 'N/A')}
            Settlement Value Score: {payload.get('settlement_value_score', 'N/A')}

            Summary: {payload.get('summary', 'N/A')}

            Incident Details:
                - Jurisdiction: {payload.get('jurisdiction', 'N/A')}
                - Date: {payload.get('incident_date', 'N/A')}
                - Location: {payload.get('incident_location', 'N/A')}
                - Injuries: {payload.get('injuries_described', 'N/A')}
                - Treatment: {payload.get('medical_treatment_mentioned', 'N/A')}
                - Employment Impact: {payload.get('employment_impact_mentioned', 'N/A')}
                - Property Damage: {payload.get('property_damage_mentioned', 'N/A')}

            Key Mentions:
                - Entities: {payload.get('entities_mentioned', 'N/A')}
                - Other Locations: {payload.get('mentioned_locations', 'N/A')}
                - Witnesses: {payload.get('witnesses_mentioned', 'N/A')}
                - Insurance: {payload.get('insurance_mentioned', 'N/A')}
                - Prior Representation: {payload.get('prior_legal_representation_mentioned', 'N/A')}

            Key Phrases from Document: {payload.get('key_phrases', 'N/A')}
            """
            context += case_details + "\n\n"
        return context

