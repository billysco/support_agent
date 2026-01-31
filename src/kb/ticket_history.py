"""
Ticket history storage and similarity search for auto-reply functionality.
Stores processed tickets and enables finding similar past tickets.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import os

from langchain_chroma import Chroma

from ..schemas import SupportTicket, PipelineResult, ReplyDraft
from .indexer import get_embeddings, get_chroma_path


class TicketHistoryStore:
    """
    Stores processed tickets and enables similarity search for auto-reply.
    """

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        use_mock: bool | None = None,
        similarity_threshold: float = 0.8,
        time_window_hours: int = 12
    ):
        """
        Initialize the ticket history store.

        Args:
            persist_dir: Path to ChromaDB persistence directory
            use_mock: Use mock embeddings
            similarity_threshold: Minimum similarity score for auto-reply (default 0.8)
            time_window_hours: Time window in hours for auto-reply eligibility (default 12)
        """
        base_path = Path(persist_dir) if persist_dir else get_chroma_path()
        self.persist_dir = base_path.parent / "ticket_history"
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.similarity_threshold = similarity_threshold
        self.time_window_hours = time_window_hours

        # Auto-detect mock mode if not specified
        if use_mock is None:
            use_mock = not bool(os.getenv("OPENAI_API_KEY"))
        self.use_mock = use_mock

        # Initialize embeddings
        self.embeddings = get_embeddings(use_mock=use_mock)

        # Load vectorstore
        self.vectorstore = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_name="ticket_history"
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
        Find a similar ticket within the time window.

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

        now = datetime.now()
        cutoff_time = now - timedelta(hours=self.time_window_hours)

        for doc, score in results:
            # Skip if below similarity threshold
            if score < self.similarity_threshold:
                continue

            # Skip if it's the same ticket
            if doc.metadata.get("ticket_id") == ticket.ticket_id:
                continue

            # Check if within time window
            processed_at_str = doc.metadata.get("processed_at")
            if processed_at_str:
                processed_at = datetime.fromisoformat(processed_at_str)
                if processed_at < cutoff_time:
                    continue

            # Found a match - create reply draft from stored data
            citations = json.loads(doc.metadata.get("citations", "[]"))
            reply = ReplyDraft(
                customer_reply=doc.metadata.get("customer_reply", ""),
                internal_notes=doc.metadata.get("internal_notes", ""),
                citations=citations
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
            "similarity_threshold": self.similarity_threshold,
            "time_window_hours": self.time_window_hours
        }


# Singleton instance
_history_store: TicketHistoryStore | None = None


def get_ticket_history(use_mock: bool | None = None) -> TicketHistoryStore:
    """
    Get or create a singleton TicketHistoryStore instance.

    Args:
        use_mock: Use mock embeddings

    Returns:
        TicketHistoryStore instance
    """
    global _history_store

    if _history_store is None:
        _history_store = TicketHistoryStore(use_mock=use_mock)

    return _history_store


def reset_ticket_history():
    """Reset the singleton ticket history instance."""
    global _history_store
    _history_store = None
