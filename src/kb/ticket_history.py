"""
Previous queries storage and similarity search for auto-reply functionality.
Stores processed tickets and enables finding similar past tickets.
This is part of the KB collections system - specifically the PREVIOUS_QUERIES collection.
"""

from datetime import datetime
from pathlib import Path
import json

from langchain_chroma import Chroma

from ..schemas import SupportTicket, PipelineResult, ReplyDraft
from .indexer import get_embeddings, get_chroma_path
from .collections import KBCollection, get_collection_path, get_similarity_threshold


class TicketHistoryStore:
    """
    Stores processed tickets in the PREVIOUS_QUERIES collection.
    Enables similarity search for auto-reply functionality.
    """

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        similarity_threshold: float | None = None
    ):
        """
        Initialize the ticket history store.

        Args:
            persist_dir: Base path to ChromaDB persistence directory
            similarity_threshold: Minimum similarity score for auto-reply (default from collection config)
        """
        base_path = Path(persist_dir) if persist_dir else get_chroma_path().parent
        self.persist_dir = get_collection_path(base_path, KBCollection.PREVIOUS_QUERIES)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Use collection default threshold if not specified
        self.similarity_threshold = similarity_threshold or get_similarity_threshold(KBCollection.PREVIOUS_QUERIES)

        # Initialize embeddings (uses OpenAI)
        self.embeddings = get_embeddings()

        # Load vectorstore with collection name from enum
        self.vectorstore = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_name=KBCollection.PREVIOUS_QUERIES.value
        )

    def add_ticket(
        self,
        ticket: SupportTicket,
        result: PipelineResult
    ) -> None:
        """
        Add a processed ticket to the history store.

        Args:
            ticket: The original support ticket
            result: The pipeline result with reply
        """
        # Create searchable text from ticket
        search_text = f"{ticket.subject} {ticket.body}"

        # Store metadata for retrieval
        metadata = {
            "ticket_id": ticket.ticket_id,
            "created_at": ticket.created_at.isoformat(),
            "processed_at": datetime.now().isoformat(),
            "category": result.triage.category.value,
            "urgency": result.triage.urgency.value,
            "customer_reply": result.reply.customer_reply,
            "internal_notes": result.reply.internal_notes,
            "citations": json.dumps(result.reply.citations),
        }

        # Add to vectorstore
        self.vectorstore.add_texts(
            texts=[search_text],
            metadatas=[metadata],
            ids=[ticket.ticket_id]
        )

    def find_similar_ticket(
        self,
        ticket: SupportTicket
    ) -> tuple[bool, float, ReplyDraft | None, dict | None]:
        """
        Find a similar ticket based on similarity score.

        Args:
            ticket: The new ticket to find matches for

        Returns:
            Tuple of (should_auto_reply, similarity_score, reply_draft, matched_ticket_info)
        """
        search_text = f"{ticket.subject} {ticket.body}"

        # Search for similar tickets
        results = self.vectorstore.similarity_search_with_relevance_scores(
            search_text, k=5
        )

        if not results:
            return False, 0.0, None, None

        for doc, score in results:
            # Skip if below similarity threshold
            if score < self.similarity_threshold:
                continue

            # Skip if it's the same ticket
            if doc.metadata.get("ticket_id") == ticket.ticket_id:
                continue

            # Found a match - create reply draft from stored data
            processed_at_str = doc.metadata.get("processed_at")
            citations = json.loads(doc.metadata.get("citations", "[]"))
            reply = ReplyDraft(
                customer_reply=doc.metadata.get("customer_reply", ""),
                internal_notes=doc.metadata.get("internal_notes", ""),
                citations=citations,
                should_send=True  # Auto-replies should be sent
            )

            matched_info = {
                "matched_ticket_id": doc.metadata.get("ticket_id"),
                "processed_at": processed_at_str,
                "category": doc.metadata.get("category"),
                "similarity_score": score
            }

            return True, score, reply, matched_info

        # No matching ticket found
        best_score = results[0][1] if results else 0.0
        return False, best_score, None, None

    def get_stats(self) -> dict:
        """Get statistics about the ticket history store."""
        collection = self.vectorstore._collection
        count = collection.count()
        return {
            "total_tickets": count,
            "similarity_threshold": self.similarity_threshold
        }


# Singleton instance
_history_store: TicketHistoryStore | None = None


def get_ticket_history() -> TicketHistoryStore:
    """
    Get or create a singleton TicketHistoryStore instance.

    Returns:
        TicketHistoryStore instance
    """
    global _history_store

    if _history_store is None:
        _history_store = TicketHistoryStore()

    return _history_store


def reset_ticket_history():
    """Reset the singleton ticket history instance."""
    global _history_store
    _history_store = None
