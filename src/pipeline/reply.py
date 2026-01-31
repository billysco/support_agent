"""
Reply drafting pipeline stage.
Generates customer-facing replies with KB citations and internal notes.
"""

from ..schemas import (
    SupportTicket, TriageResult, ExtractedFields, RoutingDecision,
    KBHit, ReplyDraft
)
from ..llm_client import LLMProvider, MockProvider


reply_system_prompt = """You are an expert customer support agent drafting replies to support tickets.

Your replies must:
1. Be professional, empathetic, and helpful
2. Acknowledge the customer's issue
3. Reference knowledge base articles using [KB:doc_name#section] format
4. Only make claims supported by the provided KB passages
5. Ask for missing critical information politely
6. Provide clear next steps
7. Never fabricate policies, pricing, or commitments

You must also provide internal notes for the support agent handling this ticket."""

reply_user_prompt_template = """Draft a reply for this support ticket.

TICKET:
- ID: {ticket_id}
- Customer: {customer_name}
- Account Tier: {account_tier}
- Subject: {subject}
- Body: {body}

TRIAGE:
- Urgency: {urgency}
- Category: {category}
- Sentiment: {sentiment}

ROUTING:
- Team: {team}
- SLA: {sla_hours} hours
- Escalation: {escalation}

EXTRACTED FIELDS:
{extracted_fields}

MISSING INFORMATION:
{missing_fields}

RELEVANT KB PASSAGES:
{kb_passages}

Generate a JSON response with:
{{
    "customer_reply": "The full customer-facing reply text. Include [KB:doc#section] citations where appropriate.",
    "internal_notes": "Notes for the support agent: why routed this way, what to do next, any concerns.",
    "citations": ["KB:doc1#section1", "KB:doc2#section2"]
}}

Remember:
- Use the customer's first name
- Match tone to sentiment (more empathetic for negative)
- Be specific about next steps and timelines
- Only cite KB passages that are actually relevant"""


def draft_reply(
    ticket: SupportTicket,
    triage: TriageResult,
    extracted: ExtractedFields,
    routing: RoutingDecision,
    kb_hits: list[KBHit],
    llm: LLMProvider
) -> ReplyDraft:
    """
    Draft a customer reply with KB citations.
    
    Args:
        ticket: Original support ticket
        triage: Triage classification results
        extracted: Extracted fields
        routing: Routing decision
        kb_hits: Relevant KB passages
        llm: LLM provider instance
    
    Returns:
        ReplyDraft with customer reply, internal notes, and citations
    """
    # Use mock provider's specialized method if available
    if isinstance(llm, MockProvider):
        return llm.mock_reply(ticket, triage, extracted, kb_hits, routing)
    
    # Format extracted fields for prompt
    extracted_fields_str = _format_extracted_fields(extracted)
    
    # Format missing fields
    missing_fields_str = ", ".join(extracted.missing_fields) if extracted.missing_fields else "None identified"
    
    # Format KB passages
    kb_passages_str = _format_kb_passages(kb_hits)
    
    # Build prompt
    prompt = reply_user_prompt_template.format(
        ticket_id=ticket.ticket_id,
        customer_name=ticket.customer_name,
        account_tier=ticket.account_tier.value,
        subject=ticket.subject,
        body=ticket.body,
        urgency=triage.urgency.value,
        category=triage.category.value,
        sentiment=triage.sentiment.value,
        team=routing.team.value,
        sla_hours=routing.sla_hours,
        escalation="Yes" if routing.escalation else "No",
        extracted_fields=extracted_fields_str,
        missing_fields=missing_fields_str,
        kb_passages=kb_passages_str
    )
    
    # Get LLM response
    try:
        response = llm.complete_json(prompt, reply_system_prompt)
        return _parse_reply_response(response, kb_hits)
    except Exception as e:
        print(f"Warning: LLM reply generation failed: {e}")
        # Fall back to mock provider
        mock = MockProvider()
        return mock.mock_reply(ticket, triage, extracted, kb_hits, routing)


def _format_extracted_fields(extracted: ExtractedFields) -> str:
    """Format extracted fields for the prompt."""
    fields = []
    
    if extracted.environment:
        fields.append(f"- Environment: {extracted.environment}")
    if extracted.region:
        fields.append(f"- Region: {extracted.region}")
    if extracted.error_message:
        fields.append(f"- Error: {extracted.error_message}")
    if extracted.reproduction_steps:
        fields.append(f"- Reproduction steps: {extracted.reproduction_steps}")
    if extracted.impact:
        fields.append(f"- Impact: {extracted.impact}")
    if extracted.requested_action:
        fields.append(f"- Requested action: {extracted.requested_action}")
    if extracted.order_id:
        fields.append(f"- Order/Invoice ID: {extracted.order_id}")
    
    return "\n".join(fields) if fields else "No specific fields extracted"


def _format_kb_passages(kb_hits: list[KBHit]) -> str:
    """Format KB hits for the prompt."""
    if not kb_hits:
        return "No relevant KB passages found."
    
    passages = []
    for i, hit in enumerate(kb_hits[:5], 1):  # Limit to top 5
        passages.append(
            f"{i}. {hit.citation}\n"
            f"   \"{hit.passage[:300]}{'...' if len(hit.passage) > 300 else ''}\""
        )
    
    return "\n\n".join(passages)


def _parse_reply_response(response: dict, kb_hits: list[KBHit]) -> ReplyDraft:
    """Parse the LLM response into a ReplyDraft."""
    
    customer_reply = response.get("customer_reply", "")
    internal_notes = response.get("internal_notes", "")
    citations = response.get("citations", [])
    
    # Ensure citations are properly formatted
    formatted_citations = []
    for citation in citations:
        if not citation.startswith("["):
            citation = f"[{citation}]"
        formatted_citations.append(citation)
    
    # If no citations provided but KB hits exist, add them
    if not formatted_citations and kb_hits:
        formatted_citations = [hit.citation for hit in kb_hits[:3]]
    
    return ReplyDraft(
        customer_reply=customer_reply,
        internal_notes=internal_notes,
        citations=formatted_citations
    )

