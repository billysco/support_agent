"""
Status updates storage for system status, outages, and announcements.
Stores and retrieves time-sensitive status information.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from langchain_chroma import Chroma
from pydantic import BaseModel, Field

from .indexer import get_embeddings
from .collections import KBCollection, get_collection_path, get_similarity_threshold


class StatusUpdate(BaseModel):
    """A system status update or announcement."""
    status_id: str = Field(..., description="Unique status identifier")
    title: str = Field(..., description="Status title/headline")
    status_type: str = Field(..., description="Type: outage, maintenance, degradation, resolved, announcement")
    severity: str = Field(default="info", description="Severity: critical, high, medium, low, info")
    affected_services: list[str] = Field(default_factory=list, description="List of affected services/products")
    description: str = Field(..., description="Detailed description")
    started_at: datetime = Field(default_factory=datetime.now, description="When the status started")
    resolved_at: Optional[datetime] = Field(default=None, description="When resolved (if applicable)")
    is_active: bool = Field(default=True, description="Whether this status is still active")
    updates: list[dict] = Field(default_factory=list, description="List of update entries")


class StatusUpdateStore:
    """
    Stores system status updates and enables similarity search.
    Used for surfacing relevant status information when processing tickets.
    """

    def __init__(
        self,
        persist_dir: str | Path | None = None,
    ):
        """
        Initialize the status update store.

        Args:
            persist_dir: Base path to ChromaDB persistence directory
        """
        from .indexer import get_chroma_path
        base_path = Path(persist_dir) if persist_dir else get_chroma_path().parent
        self.persist_dir = get_collection_path(base_path, KBCollection.STATUS_UPDATES)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.similarity_threshold = get_similarity_threshold(KBCollection.STATUS_UPDATES)

        # Initialize embeddings (uses OpenAI)
        self.embeddings = get_embeddings()

        # Load vectorstore
        self.vectorstore = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_name=KBCollection.STATUS_UPDATES.value
        )

    def add_status(self, status: StatusUpdate) -> None:
        """
        Add a status update to the store.

        Args:
            status: The status update to add
        """
        # Create searchable text combining all relevant fields
        search_text = f"{status.title} {status.description} {' '.join(status.affected_services)}"

        # Add update history to search text
        for update in status.updates:
            if update.get("message"):
                search_text += f" {update['message']}"

        # Store metadata for retrieval
        metadata = {
            "status_id": status.status_id,
            "title": status.title,
            "status_type": status.status_type,
            "severity": status.severity,
            "affected_services": json.dumps(status.affected_services),
            "description": status.description,
            "started_at": status.started_at.isoformat(),
            "resolved_at": status.resolved_at.isoformat() if status.resolved_at else "",
            "is_active": str(status.is_active),
            "updates": json.dumps(status.updates),
            "created_at": datetime.now().isoformat(),
        }

        # Add to vectorstore (upsert by using status_id)
        self.vectorstore.add_texts(
            texts=[search_text],
            metadatas=[metadata],
            ids=[status.status_id]
        )

    def update_status(
        self,
        status_id: str,
        message: str,
        new_status_type: Optional[str] = None,
        resolved: bool = False
    ) -> bool:
        """
        Add an update to an existing status.

        Args:
            status_id: ID of the status to update
            message: Update message
            new_status_type: Optional new status type
            resolved: Whether this update resolves the issue

        Returns:
            True if update was successful
        """
        # Fetch existing status
        results = self.vectorstore.get(ids=[status_id], include=["metadatas"])

        if not results or not results.get("metadatas"):
            return False

        metadata = results["metadatas"][0]

        # Parse existing updates
        updates = json.loads(metadata.get("updates", "[]"))
        updates.append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "status_type": new_status_type
        })

        # Update metadata
        metadata["updates"] = json.dumps(updates)
        if new_status_type:
            metadata["status_type"] = new_status_type
        if resolved:
            metadata["is_active"] = "False"
            metadata["resolved_at"] = datetime.now().isoformat()

        # Rebuild search text
        affected_services = json.loads(metadata.get("affected_services", "[]"))
        search_text = f"{metadata['title']} {metadata['description']} {' '.join(affected_services)}"
        for update in updates:
            if update.get("message"):
                search_text += f" {update['message']}"

        # Delete and re-add (ChromaDB upsert pattern)
        self.vectorstore.delete(ids=[status_id])
        self.vectorstore.add_texts(
            texts=[search_text],
            metadatas=[metadata],
            ids=[status_id]
        )

        return True

    def find_relevant_status(
        self,
        query: str,
        active_only: bool = True,
        k: int = 3
    ) -> list[dict]:
        """
        Find status updates relevant to a query.

        Args:
            query: Search query (typically ticket subject + body)
            active_only: Only return active (unresolved) statuses
            k: Number of results to return

        Returns:
            List of relevant status updates with scores
        """
        results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k * 2)

        relevant = []
        for doc, score in results:
            if score < self.similarity_threshold:
                continue

            metadata = doc.metadata

            # Filter to active only if requested
            if active_only and metadata.get("is_active") != "True":
                continue

            relevant.append({
                "status_id": metadata.get("status_id"),
                "title": metadata.get("title"),
                "status_type": metadata.get("status_type"),
                "severity": metadata.get("severity"),
                "affected_services": json.loads(metadata.get("affected_services", "[]")),
                "description": metadata.get("description"),
                "started_at": metadata.get("started_at"),
                "resolved_at": metadata.get("resolved_at") or None,
                "is_active": metadata.get("is_active") == "True",
                "updates": json.loads(metadata.get("updates", "[]")),
                "relevance_score": score
            })

            if len(relevant) >= k:
                break

        return relevant

    def get_active_statuses(self) -> list[dict]:
        """Get all active (unresolved) status updates."""
        # Get all documents
        collection = self.vectorstore._collection
        all_results = collection.get(include=["metadatas"])

        active = []
        for metadata in all_results.get("metadatas", []):
            if metadata.get("is_active") == "True":
                active.append({
                    "status_id": metadata.get("status_id"),
                    "title": metadata.get("title"),
                    "status_type": metadata.get("status_type"),
                    "severity": metadata.get("severity"),
                    "affected_services": json.loads(metadata.get("affected_services", "[]")),
                    "description": metadata.get("description"),
                    "started_at": metadata.get("started_at"),
                    "is_active": True,
                    "updates": json.loads(metadata.get("updates", "[]")),
                })

        # Sort by severity and start time
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        active.sort(key=lambda x: (severity_order.get(x["severity"], 5), x["started_at"]))

        return active

    def get_stats(self) -> dict:
        """Get statistics about the status update store."""
        collection = self.vectorstore._collection
        count = collection.count()

        # Count active vs resolved
        all_results = collection.get(include=["metadatas"])
        active_count = sum(
            1 for m in all_results.get("metadatas", [])
            if m.get("is_active") == "True"
        )

        return {
            "total_statuses": count,
            "active_statuses": active_count,
            "resolved_statuses": count - active_count,
            "similarity_threshold": self.similarity_threshold
        }


# Singleton instance
_status_store: StatusUpdateStore | None = None


def get_status_store() -> StatusUpdateStore:
    """
    Get or create a singleton StatusUpdateStore instance.

    Returns:
        StatusUpdateStore instance
    """
    global _status_store

    if _status_store is None:
        _status_store = StatusUpdateStore()

    return _status_store


def reset_status_store():
    """Reset the singleton status store instance."""
    global _status_store
    _status_store = None
