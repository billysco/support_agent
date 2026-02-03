"""
LangChain retriever wrapper for knowledge base search with citation formatting.
Supports multiple collections: support_kb, previous_queries, status_updates.
"""

from pathlib import Path

from langchain_chroma import Chroma

from ..schemas import KBHit
from .indexer import get_chroma_path, get_embeddings, build_kb_index
from .collections import KBCollection, get_collection_path


class KBRetriever:
    """
    Knowledge base retriever using ChromaDB and LangChain.
    Provides search functionality with citation formatting.
    Primarily searches the SUPPORT_KB collection (static docs).
    """

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        k: int = 5
    ):
        """
        Initialize the KB retriever.

        Args:
            persist_dir: Base path to ChromaDB persistence directory
            k: Number of results to return
        """
        base_path = Path(persist_dir) if persist_dir else get_chroma_path().parent
        self.persist_dir = get_collection_path(base_path, KBCollection.SUPPORT_KB)
        self.k = k

        # Initialize embeddings (uses OpenAI)
        self.embeddings = get_embeddings()

        # Ensure index exists
        self._ensure_index()

        # Load vectorstore for support_kb collection
        self.vectorstore = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_name=KBCollection.SUPPORT_KB.value
        )

        # Create retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.k}
        )

    def _ensure_index(self):
        """Ensure the KB index exists, building it if necessary."""
        chroma_files = list(self.persist_dir.glob("*.sqlite3"))
        if not chroma_files:
            print("KB index not found, building...")
            build_kb_index()
    
    def search(self, query: str, k: int | None = None) -> list[KBHit]:
        """
        Search the knowledge base for relevant passages.
        
        Args:
            query: Search query text
            k: Number of results (overrides default)
        
        Returns:
            List of KBHit objects with citations
        """
        if k and k != self.k:
            # Use custom k for this search
            docs = self.vectorstore.similarity_search_with_relevance_scores(
                query, k=k
            )
        else:
            # Use retriever with default k
            docs_without_scores = self.retriever.invoke(query)
            # Get scores separately
            docs = self.vectorstore.similarity_search_with_relevance_scores(
                query, k=self.k
            )
        
        results = []
        for doc, score in docs:
            # Extract metadata
            source = doc.metadata.get("source", "unknown")
            section = doc.metadata.get("section", "general")
            
            # Create KBHit
            hit = KBHit(
                doc_name=source,
                section=section,
                passage=doc.page_content[:500],  # Truncate long passages
                relevance_score=float(score)
            )
            results.append(hit)
        
        return results
    
    def search_with_context(
        self,
        ticket_subject: str,
        ticket_body: str,
        category: str | None = None,
        k: int | None = None
    ) -> list[KBHit]:
        """
        Search with ticket context for better relevance.
        
        Args:
            ticket_subject: Ticket subject line
            ticket_body: Ticket body text
            category: Optional category to weight results
            k: Number of results
        
        Returns:
            List of KBHit objects
        """
        # Build contextual query
        query_parts = [ticket_subject]
        
        # Add key phrases from body (first 500 chars)
        body_snippet = ticket_body[:500]
        query_parts.append(body_snippet)
        
        # Add category context if available
        if category:
            category_context = {
                "billing": "billing payment invoice charge refund",
                "bug": "bug error crash issue fix",
                "outage": "outage down unavailable incident",
                "security": "security vulnerability breach access",
                "onboarding": "setup getting started configuration",
                "feature_request": "feature request enhancement",
            }
            if category in category_context:
                query_parts.append(category_context[category])
        
        query = " ".join(query_parts)
        return self.search(query, k=k)
    
    def get_citation(self, hit: KBHit) -> str:
        """
        Format a KB hit as a citation string.
        
        Args:
            hit: KBHit object
        
        Returns:
            Citation string in [KB:doc_name#section] format
        """
        return hit.citation
    
    def format_citations_for_reply(self, hits: list[KBHit]) -> str:
        """
        Format multiple KB hits as a citations block for replies.
        
        Args:
            hits: List of KBHit objects
        
        Returns:
            Formatted citations string
        """
        if not hits:
            return ""
        
        citations = []
        for hit in hits:
            citations.append(f"{hit.citation}: \"{hit.passage[:100]}...\"")
        
        return "\n".join(citations)


# Singleton instance for reuse
_retriever_instance: KBRetriever | None = None


def get_retriever() -> KBRetriever:
    """
    Get or create a singleton KBRetriever instance.

    Returns:
        KBRetriever instance
    """
    global _retriever_instance

    if _retriever_instance is None:
        _retriever_instance = KBRetriever()

    return _retriever_instance


def reset_retriever():
    """Reset the singleton retriever instance."""
    global _retriever_instance
    _retriever_instance = None



