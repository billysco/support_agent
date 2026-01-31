"""
Reply drafting pipeline stage.
Generates customer-facing replies with KB citations and internal notes.
"""

from ..schemas import (
    SupportTicket, TriageResult, ExtractedFields, RoutingDecision,
    KBHit, ReplyDraft
)
from ..llm_client import LLMProvider, MockProvider
from .routing import get_sla_description


reply_system_prompt = """You are an expert customer support agent drafting replies to support tickets.

Your replies must:
1. Be professional, empathetic, and helpful
2. Acknowledge the customer's issue
3. Reference knowledge base articles using [KB:doc_name#section] format
4. Only make claims supported by the provided KB passages
5. If missing critical information, ask the customer to reply with the specific details needed
6. Provide clear next steps
7. Never fabricate policies, pricing, or commitments
8. DO NOT include any signature, closing, or sign-off (no "Best regards", "Thanks", "Sincerely", "[Your Name]", "Support Team", etc.)
9. End your reply with actionable content, not pleasantries

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
- Only cite KB passages that are actually relevant
- DO NOT include any signature or sign-off line - end with actionable content
- If you need more information from the customer, tell them to reply to this message"""


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


def generate_sla_notification(
    ticket: SupportTicket,
    routing: RoutingDecision
) -> ReplyDraft:
    """
    Generate a notification message to send to the customer when no KB hits are found.
    This message alerts the customer that the team has been notified and provides their SLA.
    
    Args:
        ticket: Original support ticket
        routing: Routing decision with SLA information
    
    Returns:
        ReplyDraft with notification message (should_send=True)
    """
    # Get customer's first name
    customer_first_name = ticket.customer_name.split()[0] if ticket.customer_name else "there"
    
    # Get human-readable SLA description
    sla_description = get_sla_description(routing.sla_hours)
    
    # Generate notification message
    notification_message = f"""Hi {customer_first_name},

Thank you for contacting us. We've received your ticket and our team has been alerted.

Your ticket has been assigned to our {routing.team.value} team, and we'll respond within {sla_description} per your service level agreement.

We're reviewing your request and will get back to you as soon as possible. If you have any additional information that might help us assist you, please reply to this message."""

    internal_notes = f"""No relevant KB articles found for this ticket. 
Customer has been automatically notified that the team has been alerted.
SLA: {sla_description}
Team: {routing.team.value}
This ticket requires manual review and response."""

    return ReplyDraft(
        customer_reply=notification_message,
        internal_notes=internal_notes,
        citations=[],
        should_send=True  # Always send the notification
    )


def generate_review_notification(
    ticket: SupportTicket,
    routing: RoutingDecision
) -> ReplyDraft:
    """
    Generate a notification message when confidence is low and the ticket needs human review.
    This informs the customer that their request has been flagged for additional review.
    
    Args:
        ticket: Original support ticket
        routing: Routing decision with SLA information
    
    Returns:
        ReplyDraft with notification message (should_send=True)
    """
    # Get customer's first name
    customer_first_name = ticket.customer_name.split()[0] if ticket.customer_name else "there"
    
    # Get human-readable SLA description
    sla_description = get_sla_description(routing.sla_hours)
    
    # Generate notification message
    notification_message = f"""Hi {customer_first_name},

Thank you for reaching out to us. We've received your ticket and want to let you know that your request requires additional review by our team.

Your ticket has been flagged for specialized attention and assigned to our {routing.team.value} team. A team member will review your case and respond within {sla_description} per your service level agreement.

We want to ensure we provide you with the most accurate and helpful response, which is why we're taking extra care with your request.

If you have any additional details that might help us assist you, please reply to this message."""

    internal_notes = f"""LOW CONFIDENCE - Ticket flagged for human review.
No high-confidence KB matches found (relevance threshold not met).
Customer has been notified that the ticket requires additional review.
SLA: {sla_description}
Team: {routing.team.value}

ACTION REQUIRED: Review the AI-suggested draft below and send an appropriate response."""

    return ReplyDraft(
        customer_reply=notification_message,
        internal_notes=internal_notes,
        citations=[],
        should_send=True  # Send the notification
    )


def _strip_signature(text: str) -> str:
    """Remove generic email signatures from LLM-generated replies."""
    import re

    # Common signature patterns to remove
    signature_patterns = [
        # "Best regards," followed by name/team (multi-line)
        r'\n*(?:Best regards|Kind regards|Warm regards|Regards|Sincerely|Thanks|Thank you|Cheers),?\s*\n+.*?(?:Support Team|Customer Support|Team|Staff|\[Your Name\]|Your Name).*$',
        # Just the closing line with brackets
        r'\n*(?:Best regards|Kind regards|Warm regards|Regards|Sincerely|Thanks|Thank you|Cheers),?\s*\n+\[.*?\].*$',
        # Standalone signature blocks
        r'\n+(?:Best regards|Kind regards|Warm regards|Regards|Sincerely|Thanks|Thank you|Cheers),?\s*$',
        # Common patterns with line breaks
        r'\n+Best,?\s*\n+.*$',
        # "We are here to help" followed by anything
        r'\n*(?:Thank you for your patience[^.]*\.)?\s*We are here to help!?\s*\n*(?:Best regards|Kind regards|Warm regards|Regards|Sincerely|Thanks|Thank you|Cheers).*$',
        # Just "We are here to help" at the end
        r'\n+(?:Thank you for your patience[^.]*\.)?\s*We are here to help!?\s*$',
        # Name placeholder patterns
        r'\n+\[Your Name\].*$',
        r'\n+Your Name.*$',
        # Customer Support Team on its own line
        r'\n+Customer Support(?: Team)?\s*$',
        # Generic filler endings
        r'\n+Thank you for your patience and understanding\.\s*$',
    ]

    result = text
    for pattern in signature_patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE | re.DOTALL)

    return result.rstrip()


def _parse_reply_response(response: dict, kb_hits: list[KBHit]) -> ReplyDraft:
    """Parse the LLM response into a ReplyDraft."""

    customer_reply = response.get("customer_reply", "")
    internal_notes = response.get("internal_notes", "")
    citations = response.get("citations", [])

    # Strip any signature blocks the LLM may have added
    customer_reply = _strip_signature(customer_reply)
    
    # Ensure citations are properly formatted
    formatted_citations = []
    for citation in citations:
        if not citation.startswith("["):
            citation = f"[{citation}]"
        formatted_citations.append(citation)
    
    # If no citations provided but KB hits exist, add them
    if not formatted_citations and kb_hits:
        formatted_citations = [hit.citation for hit in kb_hits[:3]]
    
    # Return the draft - the server will decide whether to send based on confidence
    return ReplyDraft(
        customer_reply=customer_reply,
        internal_notes=internal_notes,
        citations=formatted_citations,
        should_send=False  # Default to not sending - server will set based on confidence
    )

