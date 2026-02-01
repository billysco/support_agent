"""
Integration tests for the support triage pipeline.
Tests the 3 sample tickets to verify different routing outcomes.

Note: These tests require OPENAI_API_KEY to be set.
"""

import os
import json
import pytest
from datetime import datetime
from pathlib import Path

from src.schemas import (
    SupportTicket, PipelineResult, AccountTier,
    Urgency, Category, Team
)
from src.llm_client import get_llm_client
from src.kb.retriever import KBRetriever
from src.server import process_ticket, load_sample_tickets


# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping integration tests"
)


@pytest.fixture
def llm():
    """Get an LLM provider."""
    return get_llm_client()


@pytest.fixture
def retriever():
    """Get a KB retriever."""
    return KBRetriever()


@pytest.fixture
def sample_tickets():
    """Load sample tickets."""
    return load_sample_tickets()


@pytest.fixture
def ticket_a(sample_tickets):
    """Enterprise outage ticket."""
    return sample_tickets[0]


@pytest.fixture
def ticket_b(sample_tickets):
    """Billing issue ticket."""
    return sample_tickets[1]


@pytest.fixture
def ticket_c(sample_tickets):
    """Bug report ticket."""
    return sample_tickets[2]


class TestTicketA:
    """Tests for Ticket A - Enterprise Outage."""

    def test_routes_to_engineering(self, ticket_a, llm, retriever):
        """Ticket A should route to engineering team."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.routing.team == Team.engineering

    def test_has_high_urgency(self, ticket_a, llm, retriever):
        """Ticket A should be classified as P0 or P1."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.triage.urgency in [Urgency.p0, Urgency.p1]

    def test_triggers_escalation(self, ticket_a, llm, retriever):
        """Ticket A should trigger escalation."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.routing.escalation is True

    def test_has_outage_category(self, ticket_a, llm, retriever):
        """Ticket A should be categorized as outage."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.triage.category == Category.outage

    def test_extracts_environment(self, ticket_a, llm, retriever):
        """Ticket A should extract production environment."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.extracted_fields.environment == "production"


class TestTicketB:
    """Tests for Ticket B - Billing Issue."""

    def test_routes_to_billing(self, ticket_b, llm, retriever):
        """Ticket B should route to billing team."""
        result = process_ticket(ticket_b, llm, retriever)
        assert result.routing.team == Team.billing

    def test_has_billing_category(self, ticket_b, llm, retriever):
        """Ticket B should be categorized as billing."""
        result = process_ticket(ticket_b, llm, retriever)
        assert result.triage.category == Category.billing

    def test_extracts_invoice_id(self, ticket_b, llm, retriever):
        """Ticket B should extract invoice ID."""
        result = process_ticket(ticket_b, llm, retriever)
        assert result.extracted_fields.order_id is not None


class TestTicketC:
    """Tests for Ticket C - Bug Report."""

    def test_routes_to_engineering(self, ticket_c, llm, retriever):
        """Ticket C should route to engineering team."""
        result = process_ticket(ticket_c, llm, retriever)
        assert result.routing.team == Team.engineering

    def test_has_bug_category(self, ticket_c, llm, retriever):
        """Ticket C should be categorized as bug."""
        result = process_ticket(ticket_c, llm, retriever)
        assert result.triage.category == Category.bug

    def test_extracts_staging_environment(self, ticket_c, llm, retriever):
        """Ticket C should extract staging environment."""
        result = process_ticket(ticket_c, llm, retriever)
        assert result.extracted_fields.environment == "staging"


class TestReplyCitations:
    """Tests for reply citations."""

    def test_kb_hits_returned(self, ticket_a, llm, retriever):
        """KB hits should be returned in results."""
        result = process_ticket(ticket_a, llm, retriever)
        assert len(result.kb_hits) > 0
        for hit in result.kb_hits:
            assert hit.doc_name is not None
            assert hit.section is not None
            assert hit.passage is not None


class TestRoutingDiversity:
    """Tests to verify different tickets route differently."""

    def test_all_tickets_route_differently(self, sample_tickets, llm, retriever):
        """Each ticket should have distinct routing characteristics."""
        results = [process_ticket(t, llm, retriever) for t in sample_tickets]

        # Check team diversity
        teams = [r.routing.team for r in results]
        assert len(set(teams)) >= 2, "Should have at least 2 different teams"

    def test_categories_are_different(self, sample_tickets, llm, retriever):
        """Each ticket should have a different category."""
        results = [process_ticket(t, llm, retriever) for t in sample_tickets]
        categories = [r.triage.category for r in results]

        # Should have outage, billing, and bug
        assert Category.outage in categories
        assert Category.billing in categories
        assert Category.bug in categories


class TestGuardrails:
    """Tests for guardrail checks."""

    def test_guardrail_runs(self, ticket_a, llm, retriever):
        """Guardrail check should run and return status."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.guardrail_status is not None
        assert isinstance(result.guardrail_status.passed, bool)

    def test_guardrail_has_issues_list(self, ticket_a, llm, retriever):
        """Guardrail should have issues list (even if empty)."""
        result = process_ticket(ticket_a, llm, retriever)
        assert isinstance(result.guardrail_status.issues_found, list)


class TestProcessingMode:
    """Tests for processing mode tracking."""

    def test_real_mode_indicated(self, ticket_a, llm, retriever):
        """Results should indicate real processing mode."""
        result = process_ticket(ticket_a, llm, retriever)
        assert result.processing_mode == "real"
