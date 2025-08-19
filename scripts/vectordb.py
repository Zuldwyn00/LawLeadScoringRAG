import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException
from typing import List, Dict, Any
import uuid
import json

from utils import load_config, setup_logger

# ─── LOGGER & CONFIG ────────────────────────────────────────────────────────────────
config = load_config()
logger = setup_logger(__name__, config)
load_dotenv("./.env")


class QdrantManager:
    def __init__(self):
        self.config = config
        self.client = self._initialize_client()
        self.vector_config = {
            "chunk": models.VectorParams(size=1536, distance=models.Distance.COSINE),
            "summar": models.VectorParams(
                size=1536, distance=models.Distance.COSINE
            ),  # temporary vector, can use in a Hyrbrid Search in the future if we want.
            # TODO: add a vector for images as well for a hybrid search in the future.
        }

    def _initialize_client(self):
        qclient = QdrantClient(
            url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_KEY")
        )
        return qclient

    def create_collection(
        self, collection_name: str, vector_config: dict = None
    ) -> bool:
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
                collection_name=collection_name, vectors_config=vector_config
            )
            return True

        except Exception as e:
            print(f"Error creating collection: {e}")
        return False

    def add_embedding(
        self,
        collection_name: str,
        embedding: List[float],
        metadata: dict,
        vector_name: str = "chunk",
    ):
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
            payload=metadata or {},
        )
        self.client.upsert(collection_name=collection_name, points=[point])

    def add_embeddings_batch(
        self,
        collection_name: str,
        embeddings: List[List[float]],
        metadatas: List[dict],
        vector_name: str = "chunk",
    ):
        """
        Adds a batch of embeddings to the collection.

        Args:
            collection_name (str): Name of the collection.
            embeddings (List[List[float]]): A list of embedding vectors to add.
            metadatas (List[dict]): A list of metadata dictionaries.
            vector_name (str): Name of the vector field. Defaults to "chunk".
        """
        logger.info(
            f"Uploading batch of {len(embeddings)} chunks to collection '{collection_name}'."
        )
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector={vector_name: embedding},
                payload=metadata or {},
            )
            for embedding, metadata in zip(
                embeddings, metadatas
            )  # zip combines the embeddings and metadatas into one iterable list, so for I in embedding and I in metadatas is basically what the loop is
        ]
        for attempt in range(2):  # One initial attempt and one retry
            try:
                self.client.upsert(collection_name=collection_name, points=points)
                logger.info(
                    f"Successfully uploaded {len(points)} chunks to collection '{collection_name}'."
                )
                return  # If successful, exit the function
            except ResponseHandlingException as e:
                if attempt == 0:
                    logger.warning(
                        f"Error uploading batch to collection '{collection_name}', retrying... Error: {e}"
                    )
                else:
                    logger.error(
                        f"Failed to upload batch to '{collection_name}' after retry. Halting. Error: {e}"
                    )
                    raise

    def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        vector_name: str = "chunk",
        limit: int = 10,
    ) -> list:
        """
        Searches for similar vectors in the collection.

        Args:
            collection_name (str): Name of the collection.
            query_vector (List[float]): The vector to search with.
            vector_name (str, optional): The name of the vector to search against. Defaults to "chunk".
            limit (int, optional): The maximum number of results to return.

        Returns:
            list: A list of search results.
        """
        try:
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=(vector_name, query_vector),
                limit=limit,
            )
            return search_result
        except Exception as e:
            raise Exception(f"Error searching vectors: {e}")

    def get_case_settlements(
        self, jurisdiction_cases: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract case IDs and their associated settlement values with corresponding sources from jurisdiction case data.

        Args:
            jurisdiction_cases (List[Dict[str, Any]]): List of case metadata dicts from get_cases_by_jurisdiction()

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary where keys are case_ids and values are dicts containing:
                                      - 'settlement_data': List of dicts with 'value' and 'source' for each settlement
                                      - 'case_count': Number of chunks for this case
        """
        case_data = {}
        processed_count = 0
        skipped_count = 0

        for case_metadata in jurisdiction_cases:
            case_id = case_metadata.get("case_id")
            settlement_value = case_metadata.get("settlement_value")
            source = case_metadata.get("source") or case_metadata.get(
                "communication_channel"
            )

            # Skip cases without case_id
            if not case_id:
                skipped_count += 1
                continue

            # Initialize case entry if it doesn't exist
            if case_id not in case_data:
                case_data[case_id] = {"settlement_data": [], "case_count": 0}

            # Increment case count (number of chunks/entries for this case)
            case_data[case_id]["case_count"] += 1

            # Handle settlement_value with its source
            if (
                settlement_value is not None
                and settlement_value != "null"
                and settlement_value != ""
            ):
                try:
                    settlement_numeric = float(settlement_value)
                    if settlement_numeric > 0:
                        settlement_entry = {
                            "value": settlement_value,
                            "source": source or "unknown",
                        }

                        # Add settlement entry if this exact combination doesn't already exist
                        if (
                            settlement_entry
                            not in case_data[case_id]["settlement_data"]
                        ):
                            case_data[case_id]["settlement_data"].append(
                                settlement_entry
                            )
                            processed_count += 1
                except (ValueError, TypeError):
                    # Skip invalid settlement values that can't be converted to numbers
                    pass

        logger.info(
            f"Processed {processed_count} settlement entries, skipped {skipped_count} cases without case_id"
        )
        logger.info(f"Found {len(case_data)} unique case IDs")

        return case_data

    def get_cases_by_jurisdiction(
        self, collection_name: str, jurisdiction: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all cases for a specific jurisdiction with their complete metadata.

        Args:
            collection_name (str): Name of the collection to search.
            jurisdiction (str): Jurisdiction to filter by (e.g., "Suffolk County").

        Returns:
            List[Dict[str, Any]]: List of case metadata dictionaries for the jurisdiction.
        """
        try:
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="jurisdiction",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            # Use Qdrant's filter functionality to get cases by jurisdiction
            search_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="jurisdiction", match=models.MatchValue(value=jurisdiction)
                    )
                ]
            )

            # Scroll through filtered results
            all_cases = []
            offset = None

            while True:
                result = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=search_filter,
                    limit=10000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                points, next_offset = result

                # Extract metadata from each point
                for point in points:
                    all_cases.append(point.payload)

                if next_offset is None:
                    break
                offset = next_offset

            logger.info(
                f"Found {len(all_cases)} cases for jurisdiction '{jurisdiction}'"
            )
            return all_cases

        except Exception as e:
            logger.error(
                f"Error retrieving cases for jurisdiction '{jurisdiction}': {e}"
            )
            raise Exception(f"Error retrieving cases by jurisdiction: {e}")

    def get_all_case_ids_by_jurisdiction(self, collection_name: str) -> Dict[str, List[str]]:
        """
        Retrieve all case_ids grouped by jurisdiction from the collection.
        
        Args:
            collection_name (str): Name of the collection to search.
            
        Returns:
            Dict[str, List[str]]: Dictionary where keys are jurisdiction names and 
                                values are lists of unique case_ids for that jurisdiction.
                                
        Example return format:
        {
            "Suffolk County": ["case_001", "case_045", "case_078"],
            "Nassau County": ["case_012", "case_023"],
            "Queens County": ["case_034", "case_056", "case_089", "case_091"]
        }
        """
        try:
            jurisdiction_cases = {}  # Dict to group case_ids by jurisdiction
            processed_pairs = set()  # Track (case_id, jurisdiction) pairs to avoid duplicates
            offset = None
            
            while True:
                result = self.client.scroll(
                    collection_name=collection_name,
                    limit=10000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,  # We don't need vectors, just payload data
                )
                
                points, next_offset = result
                
                # Extract case_id and jurisdiction from each point's payload
                for point in points:
                    case_id = point.payload.get("case_id")
                    jurisdiction = point.payload.get("jurisdiction")
                    
                    if case_id and jurisdiction:  # Only process if both fields exist
                        pair = (case_id, jurisdiction)
                        
                        # Skip if we've already processed this case_id + jurisdiction combination
                        if pair not in processed_pairs:
                            processed_pairs.add(pair)
                            
                            # Initialize jurisdiction list if it doesn't exist
                            if jurisdiction not in jurisdiction_cases:
                                jurisdiction_cases[jurisdiction] = []
                            
                            # Add case_id to the jurisdiction's list
                            jurisdiction_cases[jurisdiction].append(case_id)
                
                if next_offset is None:
                    break
                offset = next_offset
            
            # Log summary statistics
            total_cases = sum(len(case_ids) for case_ids in jurisdiction_cases.values())
            logger.info(f"Found {total_cases} unique case IDs across {len(jurisdiction_cases)} jurisdictions in collection '{collection_name}'")
            
            # Log case counts per jurisdiction
            for jurisdiction, case_ids in jurisdiction_cases.items():
                logger.info(f"  {jurisdiction}: {len(case_ids)} cases")
            
            return jurisdiction_cases
            
        except Exception as e:
            logger.error(f"Error retrieving case IDs by jurisdiction from collection '{collection_name}': {e}")
            raise Exception(f"Error retrieving case IDs by jurisdiction: {e}")

    def get_context(self, search_results: list) -> str:
        """
        Constructs a JSON-like context string from search results.

        Args:
            search_results (list): A list of search results from the vector database.

        Returns:
            str: A formatted string containing the context from the search results as a list of dictionaries.
        """
        contexts = []
        for result in search_results:
            payload = result.payload

            context_dict = {
                "case_id": payload.get("case_id"),
                "jurisdiction": payload.get("jurisdiction"),
                "case_type": payload.get("case_type"),
                "incident_date": payload.get("incident_date"),
                "incident_location": payload.get("incident_location"),
                "mentioned_locations": payload.get("mentioned_locations", []),
                "injuries_described": payload.get("injuries_described", []),
                "medical_treatment_mentioned": payload.get(
                    "medical_treatment_mentioned", []
                ),
                "employment_impact_mentioned": payload.get(
                    "employment_impact_mentioned", []
                ),
                "property_damage_mentioned": payload.get(
                    "property_damage_mentioned", []
                ),
                "entities_mentioned": payload.get("entities_mentioned", []),
                "insurance_mentioned": payload.get("insurance_mentioned"),
                "witnesses_mentioned": payload.get("witnesses_mentioned"),
                "prior_legal_representation_mentioned": payload.get(
                    "prior_legal_representation_mentioned"
                ),
                "case_outcome": payload.get("case_outcome"),
                "settlement_value": payload.get("settlement_value"),
                "communication_channel": payload.get("communication_channel"),
                "source": payload.get("source"),
                "key_phrases": payload.get("key_phrases", []),
                "summary": payload.get("summary"),
            }
            contexts.append(context_dict)
        return json.dumps(contexts, indent=4)
