"""
Collection definitions and management for the knowledge base.
Defines separate collections for different content types.
"""

from enum import Enum
from pathlib import Path


class KBCollection(str, Enum):
    """Knowledge base collection types."""
    SUPPORT_KB = "support_kb"           # Static KB docs (procedures, policies, etc.)
    PREVIOUS_QUERIES = "previous_queries"  # Processed tickets for auto-reply
    STATUS_UPDATES = "status_updates"      # System status, outages, announcements


# Collection metadata configurations
COLLECTION_CONFIGS = {
    KBCollection.SUPPORT_KB: {
        "description": "Static knowledge base documents (procedures, policies, guides)",
        "persist_subdir": "chroma_db",
        "similarity_threshold": 0.6,
    },
    KBCollection.PREVIOUS_QUERIES: {
        "description": "Previously processed tickets for auto-reply matching",
        "persist_subdir": "previous_queries",
        "similarity_threshold": 0.8,
    },
    KBCollection.STATUS_UPDATES: {
        "description": "System status updates, outages, and announcements",
        "persist_subdir": "status_updates",
        "similarity_threshold": 0.5,
    },
}


def get_collection_path(base_path: Path, collection: KBCollection) -> Path:
    """Get the persistence path for a specific collection."""
    config = COLLECTION_CONFIGS[collection]
    return base_path / config["persist_subdir"]


def get_similarity_threshold(collection: KBCollection) -> float:
    """Get the default similarity threshold for a collection."""
    return COLLECTION_CONFIGS[collection]["similarity_threshold"]
