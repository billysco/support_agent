"""Knowledge base indexing and retrieval with ChromaDB + LangChain.

This module provides three collections:
- SUPPORT_KB: Static knowledge base documents (procedures, policies, guides)
- PREVIOUS_QUERIES: Previously processed tickets for auto-reply matching
- STATUS_UPDATES: System status updates, outages, and announcements

Plus conversation threading for multi-turn Q&A support.
"""

from .collections import KBCollection, get_collection_path, get_similarity_threshold
from .indexer import build_kb_index, get_kb_path, get_chroma_path, get_data_path
from .retriever import KBRetriever, get_retriever, reset_retriever
from .ticket_history import TicketHistoryStore, get_ticket_history, reset_ticket_history
from .status_store import StatusUpdateStore, StatusUpdate, get_status_store, reset_status_store
from .conversation_store import ConversationStore, get_conversation_store, reset_conversation_store

__all__ = [
    # Collections
    "KBCollection",
    "get_collection_path",
    "get_similarity_threshold",
    # Indexer
    "build_kb_index",
    "get_kb_path",
    "get_chroma_path",
    "get_data_path",
    # Retriever (SUPPORT_KB)
    "KBRetriever",
    "get_retriever",
    "reset_retriever",
    # Ticket History (PREVIOUS_QUERIES)
    "TicketHistoryStore",
    "get_ticket_history",
    "reset_ticket_history",
    # Status Updates (STATUS_UPDATES)
    "StatusUpdateStore",
    "StatusUpdate",
    "get_status_store",
    "reset_status_store",
    # Conversation Threading
    "ConversationStore",
    "get_conversation_store",
    "reset_conversation_store",
]

