"""
Tests for knowledge base indexing and retrieval.

Note: Tests requiring embeddings need OPENAI_API_KEY to be set.
"""

import os
import pytest
from pathlib import Path

from src.kb.indexer import (
    get_kb_path, get_chroma_path, load_markdown_files,
    split_by_headers, build_kb_index
)
from src.kb.retriever import KBRetriever, get_retriever
from src.schemas import KBHit


class TestKBIndexer:
    """Tests for KB indexing functionality."""

    def test_kb_path_exists(self):
        """KB directory should exist."""
        kb_path = get_kb_path()
        assert kb_path.exists(), f"KB path {kb_path} does not exist"

    def test_kb_has_markdown_files(self):
        """KB should contain markdown files."""
        kb_path = get_kb_path()
        md_files = list(kb_path.glob("*.md"))
        assert len(md_files) >= 6, f"Expected at least 6 KB files, found {len(md_files)}"

    def test_load_markdown_files(self):
        """Should load all markdown files with metadata."""
        kb_path = get_kb_path()
        docs = load_markdown_files(kb_path)

        assert len(docs) >= 6
        for doc in docs:
            assert doc.page_content, "Document should have content"
            assert "source" in doc.metadata, "Document should have source metadata"

    def test_split_by_headers(self):
        """Should split documents by markdown headers."""
        kb_path = get_kb_path()
        docs = load_markdown_files(kb_path)
        chunks = split_by_headers(docs)

        # Should have more chunks than documents
        assert len(chunks) > len(docs)

        # Each chunk should have section metadata
        for chunk in chunks:
            assert "source" in chunk.metadata
            assert "section" in chunk.metadata


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping embedding tests"
)
class TestKBRetriever:
    """Tests for KB retrieval functionality."""

    @pytest.fixture
    def retriever(self):
        """Get a retriever."""
        return KBRetriever()

    def test_retriever_initializes(self, retriever):
        """Retriever should initialize successfully."""
        assert retriever is not None
        assert retriever.vectorstore is not None

    def test_search_returns_results(self, retriever):
        """Search should return KB hits."""
        results = retriever.search("billing invoice refund")

        assert isinstance(results, list)
        assert len(results) > 0

        for hit in results:
            assert isinstance(hit, KBHit)
            assert hit.doc_name
            assert hit.section
            assert hit.passage

    def test_search_with_context(self, retriever):
        """Search with context should return relevant results."""
        results = retriever.search_with_context(
            ticket_subject="Production outage",
            ticket_body="Our API is returning 500 errors",
            category="outage"
        )

        assert len(results) > 0

    def test_citation_format(self, retriever):
        """Citations should be properly formatted."""
        results = retriever.search("outage incident response")

        if results:
            hit = results[0]
            citation = hit.citation
            assert citation.startswith("[KB:")
            assert "#" in citation
            assert citation.endswith("]")

    def test_search_billing_topic(self, retriever):
        """Search for billing should return billing-related docs."""
        results = retriever.search("invoice payment refund billing")

        assert len(results) > 0
        # At least one result should be from billing docs
        sources = [r.doc_name for r in results]
        assert any("billing" in s.lower() for s in sources)

    def test_search_outage_topic(self, retriever):
        """Search for outage should return outage-related docs."""
        results = retriever.search("outage incident P0 emergency")

        assert len(results) > 0
        sources = [r.doc_name for r in results]
        assert any("outage" in s.lower() or "escalation" in s.lower() for s in sources)

    def test_search_bug_topic(self, retriever):
        """Search for bug should return bug-related docs."""
        results = retriever.search("bug report reproduction steps error")

        assert len(results) > 0
        sources = [r.doc_name for r in results]
        assert any("bug" in s.lower() or "known" in s.lower() for s in sources)


class TestKBContent:
    """Tests for KB content quality."""

    def test_billing_policies_content(self):
        """Billing policies should have key sections."""
        kb_path = get_kb_path()
        billing_file = kb_path / "billing_policies.md"

        assert billing_file.exists()
        content = billing_file.read_text()

        assert "refund" in content.lower()
        assert "invoice" in content.lower()
        assert "dispute" in content.lower()

    def test_outage_procedures_content(self):
        """Outage procedures should have key sections."""
        kb_path = get_kb_path()
        outage_file = kb_path / "outage_procedures.md"

        assert outage_file.exists()
        content = outage_file.read_text()

        assert "P0" in content
        assert "escalation" in content.lower()
        assert "response" in content.lower()

    def test_sla_tiers_content(self):
        """SLA tiers should define response times."""
        kb_path = get_kb_path()
        sla_file = kb_path / "sla_tiers.md"

        assert sla_file.exists()
        content = sla_file.read_text()

        assert "enterprise" in content.lower()
        assert "professional" in content.lower()
        assert "hour" in content.lower()
