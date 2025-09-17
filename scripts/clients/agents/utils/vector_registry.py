from typing import Optional, Tuple

# ─── GLOBAL VECTOR REGISTRY ──────────────────────────────────────────────────
# Simple global registry to store vector clients for use in tools
# Follows the same pattern as summarization_registry.py

# Global variables to store the current vector clients
_qdrant_manager = None
_embedding_client = None


def set_vector_clients(qdrant_manager, embedding_client):
    """
    Register QdrantManager and embedding client globally for use in tools.

    Args:
        qdrant_manager: A QdrantManager instance
        embedding_client: An embedding client with get_embeddings() method
    """
    global _qdrant_manager, _embedding_client
    _qdrant_manager = qdrant_manager
    _embedding_client = embedding_client


def get_vector_clients() -> Tuple[Optional[object], Optional[object]]:
    """
    Retrieve the currently registered vector clients.

    Returns:
        Tuple of (qdrant_manager, embedding_client), or (None, None) if no clients have been set
    """
    return _qdrant_manager, _embedding_client


def get_qdrant_manager():
    """
    Retrieve the currently registered QdrantManager.

    Returns:
        The registered QdrantManager, or None if no manager has been set
    """
    return _qdrant_manager


def get_embedding_client():
    """
    Retrieve the currently registered embedding client.

    Returns:
        The registered embedding client, or None if no client has been set
    """
    return _embedding_client
