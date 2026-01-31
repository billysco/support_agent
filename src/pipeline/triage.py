"""
Triage and extraction pipeline stage.
Classifies tickets and extracts structured fields in a single LLM call.
"""

import json
from typing import Any

from ..schemas import (
    SupportTicket, TriageResult, ExtractedFields,
    Urgency, Category, Sentiment
)
from ..llm_client import LLMProvider, MockProvider


triage_system_prompt = """You are an expert support ticket triage system. Your job is to:
1. Classify the urgency, category, and sentiment of support tickets
2. Extract structured fields from the ticket text
3. Identify missing information that should be requested

You must respond with valid JSON only. Be conservative - only extract information that is explicitly stated.
Never fabricate details. If information is not present, leave the field null."""

triage_user_prompt_template = """Analyze this support ticket and provide classification and extraction.

TICKET:
- ID: {ticket_id}
- Customer: {customer_name}
- Account Tier: {account_tier}
- Product: {product}
- Subject: {subject}
- Body: {body}

Respond with JSON in this exact format:
{{
    "triage": {{
        "urgency": "P0|P1|P2|P3",
        "category": "billing|bug|outage|feature_request|security|onboarding|other",
        "sentiment": "negative|neutral|positive",
        "confidence": 0.0-1.0,
        "rationale": "Brief explanation grounded in ticket text"
    }},
    "extracted_fields": {{
        "environment": "production|staging|development|null",
        "region": "region string or null",
        "error_message": "error text or null",
        "reproduction_steps": "steps or null",
        "impact": "impact description or null",
        "requested_action": "what customer wants or null",
        "order_id": "order/invoice ID or null",
        "missing_fields": ["list", "of", "missing", "critical", "fields"]
    }}
}}

Classification guidelines:
- P0: Production down, security breach, data loss - requires immediate action
- P1: Major feature broken, significant impact - requires same-day response
- P2: Important issue with workaround - requires response within 24h
- P3: Minor issue, question, or feature request - standard response time

For missing_fields, only include fields that are:
1. Critical for resolving the issue
2. Not already provided in the ticket
3. Reasonable to ask the customer for"""


def triage_and_extract(
    ticket: SupportTicket,
    llm: LLMProvider
) -> tuple[TriageResult, ExtractedFields]:
    """
    Perform triage classification and field extraction on a ticket.
    
    Args:
        ticket: The support ticket to process
        llm: LLM provider instance
    
    Returns:
        Tuple of (TriageResult, ExtractedFields)
    """
    # Use mock provider's specialized method if available
    if isinstance(llm, MockProvider):
        return llm.mock_triage(ticket)
    
    # Build prompt
    prompt = triage_user_prompt_template.format(
        ticket_id=ticket.ticket_id,
        customer_name=ticket.customer_name,
        account_tier=ticket.account_tier.value,
        product=ticket.product,
        subject=ticket.subject,
        body=ticket.body
    )
    
    # Get LLM response
    try:
        response = llm.complete_json(prompt, triage_system_prompt)
        return _parse_triage_response(response)
    except Exception as e:
        print(f"Warning: LLM triage failed: {e}")
        # Fall back to mock provider
        mock = MockProvider()
        return mock.mock_triage(ticket)


def _parse_triage_response(response: dict[str, Any]) -> tuple[TriageResult, ExtractedFields]:
    """Parse the LLM response into structured objects."""
    
    triage_data = response.get("triage", {})
    extracted_data = response.get("extracted_fields", {})
    
    # Parse urgency
    urgency_str = triage_data.get("urgency", "P3").upper()
    urgency_map = {"P0": Urgency.p0, "P1": Urgency.p1, "P2": Urgency.p2, "P3": Urgency.p3}
    urgency = urgency_map.get(urgency_str, Urgency.p3)
    
    # Parse category
    category_str = triage_data.get("category", "other").lower()
    try:
        category = Category(category_str)
    except ValueError:
        category = Category.other
    
    # Parse sentiment
    sentiment_str = triage_data.get("sentiment", "neutral").lower()
    try:
        sentiment = Sentiment(sentiment_str)
    except ValueError:
        sentiment = Sentiment.neutral
    
    triage = TriageResult(
        urgency=urgency,
        category=category,
        sentiment=sentiment,
        confidence=float(triage_data.get("confidence", 0.7)),
        rationale=triage_data.get("rationale", "Classification based on ticket content.")
    )
    
    extracted = ExtractedFields(
        environment=extracted_data.get("environment"),
        region=extracted_data.get("region"),
        error_message=extracted_data.get("error_message"),
        reproduction_steps=extracted_data.get("reproduction_steps"),
        impact=extracted_data.get("impact"),
        requested_action=extracted_data.get("requested_action"),
        order_id=extracted_data.get("order_id"),
        missing_fields=extracted_data.get("missing_fields", [])
    )
    
    return triage, extracted

