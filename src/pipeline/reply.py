"""
Reply drafting pipeline stage.
Generates customer-facing replies with KB citations and internal notes.
Includes follow-up request generation for Q&A conversations.
"""

from typing import Optional

from ..schemas import (
    SupportTicket, TriageResult, ExtractedFields, RoutingDecision,
    KBHit, ReplyDraft, Conversation
)
from ..llm_client import OpenAIProvider
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
    llm: OpenAIProvider
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
    response = llm.complete_json(prompt, reply_system_prompt)
    return _parse_reply_response(response, kb_hits)


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


# Field descriptions for follow-up requests
FIELD_DESCRIPTIONS = {
    "environment": "which environment this is occurring in (production, staging, or development)",
    "region": "your geographic region or cloud region (e.g., us-east-1, EU, etc.)",
    "error_message": "the exact error message you're seeing",
    "reproduction_steps": "the steps to reproduce this issue",
    "impact": "how this is affecting your business or users",
    "requested_action": "what specific outcome you're looking for",
    "order_id": "your order ID or invoice number",
}


def generate_followup_request(
    ticket: SupportTicket,
    pending_fields: list[str],
    conversation: Optional[Conversation] = None,
    routing: Optional[RoutingDecision] = None,
    fields_received: list[str] | None = None
) -> ReplyDraft:
    """
    Generate a follow-up request asking the customer for specific missing information.

    Args:
        ticket: The support ticket (original or follow-up)
        pending_fields: List of fields still needed from customer
        conversation: Optional conversation context
        routing: Optional routing decision for SLA info
        fields_received: Optional list of fields just provided by customer

    Returns:
        ReplyDraft with follow-up request
    """
    customer_first_name = ticket.customer_name.split()[0] if ticket.customer_name else "there"

    # Determine if this is initial or continued follow-up
    message_count = len(conversation.messages) if conversation else 1
    is_continued = message_count > 2  # More than initial + first reply

    # Build the list of needed information
    info_requests = []
    for field in pending_fields:
        description = FIELD_DESCRIPTIONS.get(field, f"information about {field.replace('_', ' ')}")
        info_requests.append(f"• {description.capitalize()}")

    info_list = "\n".join(info_requests)

    # Build acknowledgment for received fields
    acknowledgment = ""
    if fields_received and is_continued:
        received_descriptions = []
        for field in fields_received:
            desc = FIELD_DESCRIPTIONS.get(field, field.replace('_', ' '))
            received_descriptions.append(desc)
        if received_descriptions:
            acknowledgment = f"Thank you for providing {', '.join(received_descriptions)}. "

    if is_continued:
        # Continued follow-up - acknowledge what they provided, ask for rest
        notification_message = f"""Hi {customer_first_name},

{acknowledgment}To continue helping you resolve this issue, we still need a few more details:

{info_list}

Please reply with this information and we'll continue investigating."""
    else:
        # Initial follow-up request
        notification_message = f"""Hi {customer_first_name},

Thank you for reaching out. To help us investigate your issue and provide the best solution, could you please provide the following information:

{info_list}

Once we have these details, we'll be able to assist you more effectively. Please reply to this message with the requested information."""

    # Build internal notes
    internal_notes = f"""FOLLOW-UP REQUEST SENT
Missing fields: {', '.join(pending_fields)}
Message count in conversation: {message_count}"""

    if fields_received:
        internal_notes += f"\nFields just received: {', '.join(fields_received)}"

    internal_notes += """

Customer has been asked to provide additional details.
Conversation will continue once they reply."""

    if routing:
        internal_notes += f"\nTeam: {routing.team.value}"
        internal_notes += f"\nSLA: {routing.sla_hours} hours"

    return ReplyDraft(
        customer_reply=notification_message,
        internal_notes=internal_notes,
        citations=[],
        should_send=True
    )


def generate_followup_acknowledgment(
    ticket: SupportTicket,
    conversation: Conversation,
    new_fields_received: list[str],
    still_pending: list[str]
) -> str:
    """
    Generate an acknowledgment for received follow-up information.

    Args:
        ticket: The follow-up ticket
        conversation: The conversation context
        new_fields_received: Fields that were just provided
        still_pending: Fields still missing

    Returns:
        Acknowledgment text to include in reply
    """
    customer_first_name = ticket.customer_name.split()[0] if ticket.customer_name else "there"

    if new_fields_received:
        fields_str = ", ".join(f.replace("_", " ") for f in new_fields_received)
        ack = f"Thank you for providing the {fields_str}. "
    else:
        ack = "Thank you for your reply. "

    if still_pending:
        pending_str = ", ".join(FIELD_DESCRIPTIONS.get(f, f.replace("_", " ")) for f in still_pending)
        ack += f"We still need: {pending_str}."
    else:
        ack += "We now have all the information we need to investigate your issue."

    return ack


contextual_reply_system_prompt = """You are an expert customer support agent continuing an ongoing conversation with a customer.

Your replies must:
1. Be professional, empathetic, and helpful
2. Acknowledge the information the customer just provided
3. Reference knowledge base articles using [KB:doc_name#section] format
4. Only make claims supported by the provided KB passages
5. Provide clear next steps based on all information gathered so far
6. Never fabricate policies, pricing, or commitments
7. DO NOT include any signature, closing, or sign-off
8. If still missing critical information, ask specifically for it

You have access to the full conversation history and should respond appropriately."""

contextual_reply_user_prompt_template = """Draft a reply for this ongoing support conversation.

CONVERSATION HISTORY:
{conversation_context}

CURRENT MESSAGE FROM CUSTOMER:
{current_message}

INFORMATION JUST PROVIDED:
{fields_received}

TRIAGE:
- Urgency: {urgency}
- Category: {category}
- Sentiment: {sentiment}

ROUTING:
- Team: {team}
- SLA: {sla_hours} hours

ALL EXTRACTED FIELDS (merged from entire conversation):
{extracted_fields}

STILL MISSING:
{missing_fields}

RELEVANT KB PASSAGES:
{kb_passages}

Generate a JSON response with:
{{
    "customer_reply": "The full customer-facing reply. Acknowledge what they provided, then address their issue using the KB info. Include [KB:doc#section] citations where appropriate.",
    "internal_notes": "Notes for the support agent about conversation progress and next steps.",
    "citations": ["KB:doc1#section1", "KB:doc2#section2"]
}}

Remember:
- Use the customer's first name
- Acknowledge the specific information they just provided
- Build on the conversation context - don't repeat information unnecessarily
- If you now have all needed info, provide a complete resolution
- If still missing info, explain what else you need and why
- DO NOT include any signature or sign-off line"""


def draft_reply_with_context(
    ticket: SupportTicket,
    triage: TriageResult,
    extracted: ExtractedFields,
    routing: RoutingDecision,
    kb_hits: list[KBHit],
    llm: OpenAIProvider,
    conversation: Conversation,
    fields_received: list[str] | None = None
) -> ReplyDraft:
    """
    Draft a reply using the full conversation context.

    Args:
        ticket: Current ticket/message
        triage: Triage classification
        extracted: Current extraction (merged across conversation)
        routing: Routing decision
        kb_hits: Relevant KB passages
        llm: LLM provider
        conversation: Full conversation context
        fields_received: Fields that were just provided in this message

    Returns:
        ReplyDraft with context-aware response
    """
    # Use merged fields from conversation if available
    merged_extracted = conversation.merged_extracted_fields or extracted

    # Format conversation context
    conversation_context = _format_conversation_context(conversation)

    # Format fields received
    if fields_received:
        fields_received_str = "\n".join(f"- {field}: {getattr(merged_extracted, field, 'provided')}" for field in fields_received)
    else:
        fields_received_str = "No specific fields identified as newly provided"

    # Format extracted fields
    extracted_fields_str = _format_extracted_fields(merged_extracted)

    # Format missing fields
    missing_fields_str = ", ".join(merged_extracted.missing_fields) if merged_extracted.missing_fields else "None - all required information gathered"

    # Format KB passages
    kb_passages_str = _format_kb_passages(kb_hits)

    # Build prompt
    prompt = contextual_reply_user_prompt_template.format(
        conversation_context=conversation_context,
        current_message=ticket.body,
        fields_received=fields_received_str,
        urgency=triage.urgency.value,
        category=triage.category.value,
        sentiment=triage.sentiment.value,
        team=routing.team.value,
        sla_hours=routing.sla_hours,
        extracted_fields=extracted_fields_str,
        missing_fields=missing_fields_str,
        kb_passages=kb_passages_str
    )

    # Get LLM response
    response = llm.complete_json(prompt, contextual_reply_system_prompt)
    return _parse_reply_response(response, kb_hits)


def _format_conversation_context(conversation: Conversation) -> str:
    """Format conversation history for the LLM prompt."""
    context_parts = [
        f"Subject: {conversation.subject}",
        f"Customer: {conversation.customer_name} ({conversation.account_tier.value} tier)",
        f"Product: {conversation.product}",
        ""
    ]

    for i, msg in enumerate(conversation.messages):
        sender_label = msg.sender_type.upper()
        timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M")
        context_parts.append(f"[{sender_label}] ({timestamp})")
        context_parts.append(msg.content)
        context_parts.append("")

    return "\n".join(context_parts)

