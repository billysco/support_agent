"""
FastAPI server for the support triage web UI.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from .schemas import (
    SupportTicket, PipelineResult, AccountTier, AutoReplyInfo,
    GuardrailStatus, InputGuardrailStatus, TriageResult, ExtractedFields,
    RoutingDecision, ReplyDraft, Urgency, Category, Sentiment, Team, KBHit,
    StatusUpdateInfo, Conversation, ConversationInfo, ConversationStatus,
    ApprovedResponse
)
from .llm_client import get_llm_client, OpenAIProvider
from .kb.retriever import get_retriever, KBRetriever
from .kb.indexer import build_kb_index, add_approved_response
from .kb.ticket_history import get_ticket_history, TicketHistoryStore
from .kb.status_store import get_status_store, StatusUpdateStore, StatusUpdate
from .kb.conversation_store import get_conversation_store, ConversationStore
from .kb.collections import KBCollection
from .pipeline.triage import triage_and_extract, triage_and_extract_with_context
from .pipeline.routing import compute_routing
from .pipeline.reply import (
    draft_reply, generate_sla_notification, generate_review_notification,
    generate_followup_request, draft_reply_with_context
)
from .pipeline.guardrail import check_guardrails, check_input_guardrails, sanitize_input
from .monitoring.event_generator import LogEventGenerator
from .monitoring.threshold_checker import ThresholdChecker
from .monitoring.schemas import LogEvent, AIIssue, AIAlert


# Get project paths
def get_project_root() -> Path:
    return Path(__file__).parent.parent


def get_web_path() -> Path:
    return get_project_root() / "web"


def get_data_path() -> Path:
    return get_project_root() / "data"


def get_kb_path() -> Path:
    return get_project_root() / "kb"


def load_sample_tickets() -> list[SupportTicket]:
    """Load sample tickets from the data directory."""
    data_path = get_data_path() / "sample_tickets.json"
    
    with open(data_path, "r", encoding="utf-8") as f:
        tickets_data = json.load(f)
    
    tickets = []
    for data in tickets_data:
        # Parse datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )
        # Parse account tier
        if isinstance(data.get("account_tier"), str):
            data["account_tier"] = AccountTier(data["account_tier"])
        
        tickets.append(SupportTicket(**data))
    
    return tickets


# Initialize FastAPI app
app = FastAPI(
    title="Support Triage System",
    description="AI-powered customer support ticket triage and reply drafting",
    version="1.0.0"
)

# Global instances (lazy loaded)
_llm = None
_retriever = None
_ticket_history = None
_status_store = None
_conversation_store = None

# Monitoring state
import threading
_monitoring_lock = threading.Lock()
_monitoring_state = {
    "running": False,
    "generator": None,
    "threshold_checker": None,
    "ai_agent": None,
    "events": [],
    "issues": [],
    "alerts": []
}


def get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm_client()
    return _llm


def get_kb_retriever():
    global _retriever
    if _retriever is None:
        _retriever = get_retriever()
    return _retriever


def get_history():
    global _ticket_history
    if _ticket_history is None:
        _ticket_history = get_ticket_history()
    return _ticket_history


def get_status():
    global _status_store
    if _status_store is None:
        _status_store = get_status_store()
    return _status_store


def get_conversations():
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = get_conversation_store()
    return _conversation_store


def process_ticket(
    ticket: SupportTicket,
    llm: OpenAIProvider,
    retriever: KBRetriever,
    ticket_history: TicketHistoryStore | None = None,
    status_store: StatusUpdateStore | None = None,
    conversation_store: ConversationStore | None = None
) -> PipelineResult:
    """
    Process a single ticket through the full pipeline.
    Supports both new tickets and follow-up messages in existing conversations.

    Args:
        ticket: Support ticket to process
        llm: LLM provider instance
        retriever: KB retriever instance
        ticket_history: Optional ticket history store for auto-reply (PREVIOUS_QUERIES collection)
        status_store: Optional status update store (STATUS_UPDATES collection)
        conversation_store: Optional conversation store for Q&A threading

    Returns:
        Complete PipelineResult
    """
    # Initialize stores if not provided
    if ticket_history is None:
        ticket_history = get_ticket_history()
    if status_store is None:
        status_store = get_status_store()
    if conversation_store is None:
        conversation_store = get_conversation_store()

    # Stage 0a: Input guardrail check
    input_guardrail = check_input_guardrails(ticket, llm)

    # If input is blocked, return early with blocked response
    if input_guardrail.blocked:
        return _create_blocked_response(ticket, input_guardrail)

    # Sanitize input if needed
    if not input_guardrail.passed:
        ticket = sanitize_input(ticket, input_guardrail)

    # Stage 0b: Check if this is a follow-up to an existing conversation
    conversation = None
    conversation_info = None
    is_followup = ticket.is_followup or ticket.conversation_id is not None

    print(f"[DEBUG] Processing ticket: {ticket.ticket_id}")
    print(f"[DEBUG] is_followup: {is_followup}, conversation_id: {ticket.conversation_id}")

    if is_followup and ticket.conversation_id:
        conversation = conversation_store.get_conversation(ticket.conversation_id)
        print(f"[DEBUG] Found conversation: {conversation is not None}")
        if conversation:
            print(f"[DEBUG] Conversation has {len(conversation.messages)} messages, pending_fields: {conversation.pending_fields}")

    # Stage 0c: Check for relevant system status updates (STATUS_UPDATES collection)
    search_query = f"{ticket.subject} {ticket.body[:500]}"
    relevant_statuses = status_store.find_relevant_status(search_query, active_only=True, k=3)
    status_updates = [
        StatusUpdateInfo(
            status_id=s["status_id"],
            title=s["title"],
            status_type=s["status_type"],
            severity=s["severity"],
            affected_services=s["affected_services"],
            description=s["description"],
            is_active=s["is_active"],
            relevance_score=s["relevance_score"]
        )
        for s in relevant_statuses
    ]

    # Stage 0d: Check for similar recent tickets (auto-reply from PREVIOUS_QUERIES collection)
    # Skip auto-reply check for follow-ups
    auto_reply_info = AutoReplyInfo(is_auto_reply=False, similarity_score=0.0)

    if not is_followup:
        should_auto_reply, similarity_score, cached_reply, matched_info = \
            ticket_history.find_similar_ticket(ticket)

        auto_reply_info = AutoReplyInfo(
            is_auto_reply=False,
            similarity_score=similarity_score
        )

        if should_auto_reply and cached_reply and matched_info:
            # Calculate time since match
            processed_at = datetime.fromisoformat(matched_info["processed_at"])
            time_since = (datetime.now() - processed_at).total_seconds() / 3600

            auto_reply_info = AutoReplyInfo(
                is_auto_reply=True,
                similarity_score=matched_info["similarity_score"],
                matched_ticket_id=matched_info["matched_ticket_id"],
                time_since_match_hours=round(time_since, 2)
            )

            # Still do triage for classification purposes
            triage, extracted = triage_and_extract(ticket, llm)
            routing = compute_routing(triage, ticket.account_tier)

            # Use KB hits from search (for display)
            kb_hits = retriever.search_with_context(
                ticket_subject=ticket.subject,
                ticket_body=ticket.body,
                category=triage.category.value,
                k=5
            )

            # Use the cached reply with note about auto-reply
            reply = ReplyDraft(
                customer_reply=cached_reply.customer_reply,
                internal_notes=(
                    f"[AUTO-REPLY] Based on similar ticket {matched_info['matched_ticket_id']} "
                    f"(similarity: {matched_info['similarity_score']:.2%})\n\n"
                    f"{cached_reply.internal_notes}"
                ),
                citations=cached_reply.citations,
                should_send=True,
                suggested_draft=None
            )

            # Skip guardrails for auto-reply (already validated previously)
            guardrail = GuardrailStatus(
                passed=True,
                issues_found=[],
                fixes_applied=["Auto-reply from validated previous response"]
            )

            # Create conversation for tracking
            conversation = conversation_store.create_conversation(ticket, triage, extracted, routing)
            conversation_info = conversation_store.get_conversation_info(conversation)

            result = PipelineResult(
                ticket_id=ticket.ticket_id,
                triage=triage,
                extracted_fields=extracted,
                routing=routing,
                kb_hits=kb_hits,
                reply=reply,
                input_guardrail_status=input_guardrail,
                guardrail_status=guardrail,
                processing_mode="real",
                auto_reply=auto_reply_info,
                status_updates=status_updates,
                conversation=conversation_info
            )

            ticket_history.add_ticket(ticket, result)
            return result

    # Stage 1: Triage and extraction
    fields_received = []  # Track what fields the customer just provided

    if conversation:
        # This is a follow-up - use context-aware extraction
        print(f"[DEBUG] Using context-aware extraction for follow-up")
        conversation_context = conversation_store.get_conversation_context(ticket.conversation_id)
        pending_fields = conversation.pending_fields or []
        previous_triage = conversation.current_triage
        print(f"[DEBUG] Pending fields before extraction: {pending_fields}")

        # Extract with full context awareness
        triage, extracted, fields_received = triage_and_extract_with_context(
            ticket=ticket,
            conversation_context=conversation_context,
            pending_fields=pending_fields,
            previous_triage=previous_triage,
            llm=llm
        )
        print(f"[DEBUG] Fields received: {fields_received}")
        print(f"[DEBUG] Missing fields after extraction: {extracted.missing_fields}")

        # Add follow-up message to conversation with new extraction
        conversation = conversation_store.add_customer_message(
            ticket.conversation_id, ticket, extracted
        )

        # Use merged fields from conversation
        if conversation and conversation.merged_extracted_fields:
            extracted = conversation.merged_extracted_fields

        # Update triage/routing in conversation
        routing = compute_routing(triage, ticket.account_tier)
        conversation_store.update_triage(ticket.conversation_id, triage, routing)
    else:
        # New ticket - standard extraction
        triage, extracted = triage_and_extract(ticket, llm)
        routing = compute_routing(triage, ticket.account_tier)

    # Stage 2: KB retrieval
    # For follow-ups, use original subject and combine context for better matching
    if conversation:
        search_subject = conversation.subject
        # Combine original issue with follow-up for better context
        search_body = f"{conversation.messages[0].content}\n\nLatest update: {ticket.body}"
    else:
        search_subject = ticket.subject
        search_body = ticket.body

    kb_hits = retriever.search_with_context(
        ticket_subject=search_subject,
        ticket_body=search_body,
        category=triage.category.value,
        k=5
    )

    # Stage 3: Determine if we need more information (Q&A follow-up logic)
    pending_fields = extracted.missing_fields if extracted.missing_fields else []
    needs_followup = len(pending_fields) > 0

    # Stage 4: Reply drafting
    confidence_threshold = 0.7
    high_confidence_hits = [hit for hit in kb_hits if hit.relevance_score >= confidence_threshold]
    is_high_confidence = len(high_confidence_hits) > 0

    if needs_followup and not is_high_confidence:
        # Need more info and don't have high-confidence KB matches
        # Generate follow-up request instead of full reply
        reply = generate_followup_request(
            ticket=ticket,
            pending_fields=pending_fields,
            conversation=conversation,
            routing=routing,
            fields_received=fields_received
        )
    else:
        # Generate the AI draft reply
        if conversation:
            draft_reply_obj = draft_reply_with_context(
                ticket, triage, extracted, routing, kb_hits, llm, conversation,
                fields_received=fields_received
            )
        else:
            draft_reply_obj = draft_reply(ticket, triage, extracted, routing, kb_hits, llm)

        if is_high_confidence:
            # High confidence: Send the full AI response
            reply = ReplyDraft(
                customer_reply=draft_reply_obj.customer_reply,
                internal_notes=draft_reply_obj.internal_notes,
                citations=draft_reply_obj.citations,
                should_send=True,
                suggested_draft=None
            )
        else:
            # Low confidence: Send notification, keep draft for review
            notification_reply = generate_review_notification(ticket, routing)
            reply = ReplyDraft(
                customer_reply=notification_reply.customer_reply,
                internal_notes=(
                    f"{notification_reply.internal_notes}\n\n"
                    f"--- AI SUGGESTED REPLY (FOR AGENT REVIEW) ---\n"
                    f"{draft_reply_obj.internal_notes}"
                ),
                citations=[],
                should_send=True,
                suggested_draft=draft_reply_obj.customer_reply
            )

    # Stage 5: Guardrail check
    guardrail = check_guardrails(reply, kb_hits, llm)

    # Create or update conversation
    if not conversation:
        # New conversation
        conversation = conversation_store.create_conversation(ticket, triage, extracted, routing)

    # Add system reply to conversation
    conversation_store.add_system_reply(
        conversation.conversation_id,
        reply.customer_reply,
        is_auto_reply=auto_reply_info.is_auto_reply
    )

    # Update conversation status based on outcome
    if needs_followup:
        # Still waiting for customer info
        conversation.status = ConversationStatus.awaiting_customer
    elif not pending_fields and is_high_confidence:
        # Issue likely resolved
        conversation_store.resolve_conversation(conversation.conversation_id)

    conversation_info = conversation_store.get_conversation_info(conversation)

    # Assemble result
    result = PipelineResult(
        ticket_id=ticket.ticket_id,
        triage=triage,
        extracted_fields=extracted,
        routing=routing,
        kb_hits=kb_hits,
        reply=reply,
        input_guardrail_status=input_guardrail,
        guardrail_status=guardrail,
        processing_mode="real",
        auto_reply=auto_reply_info,
        status_updates=status_updates,
        conversation=conversation_info
    )

    # Store processed ticket in history for future auto-replies
    ticket_history.add_ticket(ticket, result)

    return result


def _create_blocked_response(
    ticket: SupportTicket,
    input_guardrail: InputGuardrailStatus
) -> PipelineResult:
    """
    Create a pipeline result for a blocked ticket.

    Args:
        ticket: The blocked ticket
        input_guardrail: Input guardrail results

    Returns:
        PipelineResult with blocked status
    """
    # Create minimal triage for blocked ticket
    triage = TriageResult(
        urgency=Urgency.p3,
        category=Category.other,
        sentiment=Sentiment.negative,
        confidence=0.0,
        rationale="Ticket blocked by input guardrails - not processed"
    )

    extracted = ExtractedFields(
        missing_fields=["Ticket not analyzed due to guardrail block"]
    )

    routing = RoutingDecision(
        team=Team.security,
        sla_hours=24,
        escalation=True,
        reasoning="Blocked by input guardrails - routed to security for review"
    )

    reply = ReplyDraft(
        customer_reply="""Thank you for contacting us.

We were unable to process your request at this time. If you believe this is an error, please resubmit your ticket with additional details about your issue.

For urgent matters, please contact our support team directly.""",
        internal_notes=f"""[BLOCKED BY INPUT GUARDRAILS]

Risk Level: {input_guardrail.risk_level}
Issues Detected: {', '.join(input_guardrail.issues_found)}

ACTION REQUIRED: Review this ticket manually before any response.
This ticket was flagged by automated security systems and requires human review.""",
        citations=[],
        should_send=False  # Blocked tickets should not be sent automatically
    )

    # Output guardrail passes since we control this response
    output_guardrail = GuardrailStatus(
        passed=True,
        issues_found=[],
        fixes_applied=[]
    )

    return PipelineResult(
        ticket_id=ticket.ticket_id,
        triage=triage,
        extracted_fields=extracted,
        routing=routing,
        kb_hits=[],
        reply=reply,
        input_guardrail_status=input_guardrail,
        guardrail_status=output_guardrail,
        processing_mode="real",
        auto_reply=AutoReplyInfo()
    )


# API Routes
@app.get("/api/mode")
async def get_mode():
    """Get the current processing mode."""
    return {"mode": "real"}


@app.get("/api/samples")
async def get_samples():
    """Get sample tickets for the demo."""
    samples_path = get_data_path() / "sample_tickets.json"
    
    try:
        with open(samples_path, "r", encoding="utf-8") as f:
            samples = json.load(f)
        return JSONResponse(content=samples)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Sample tickets not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid sample tickets file")


@app.post("/api/process", response_model=PipelineResult)
async def process_ticket_api(ticket_data: dict):
    """Process a support ticket through the triage pipeline."""
    try:
        # Parse datetime if string
        if isinstance(ticket_data.get("created_at"), str):
            ticket_data["created_at"] = datetime.fromisoformat(
                ticket_data["created_at"].replace("Z", "+00:00")
            )
        
        # Parse account tier if string
        if isinstance(ticket_data.get("account_tier"), str):
            ticket_data["account_tier"] = AccountTier(ticket_data["account_tier"])
        
        # Validate ticket
        ticket = SupportTicket(**ticket_data)
        
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Process ticket
    try:
        llm = get_llm()
        retriever = get_kb_retriever()
        ticket_history = get_history()
        status_store = get_status()
        conversation_store = get_conversations()
        result = process_ticket(
            ticket, llm, retriever, ticket_history, status_store, conversation_store
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.get("/api/ticket-history/stats")
async def get_ticket_history_stats():
    """Get statistics about the previous queries (ticket history) store."""
    try:
        history = get_history()
        return history.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# Status Updates API (STATUS_UPDATES collection)
@app.get("/api/status/active")
async def get_active_statuses():
    """Get all active system status updates."""
    try:
        status_store = get_status()
        return status_store.get_active_statuses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/status/stats")
async def get_status_stats():
    """Get statistics about the status updates store."""
    try:
        status_store = get_status()
        return status_store.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/api/status/search")
async def search_statuses(search_data: dict):
    """Search for relevant status updates."""
    query = search_data.get("query", "")
    active_only = search_data.get("active_only", True)
    k = search_data.get("k", 3)

    if not query or len(query) < 3:
        return []

    try:
        status_store = get_status()
        return status_store.find_relevant_status(query, active_only=active_only, k=k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.post("/api/admin/status")
async def create_status_update(status_data: dict):
    """Create a new system status update."""
    required_fields = ["status_id", "title", "status_type", "description"]
    for field in required_fields:
        if not status_data.get(field):
            raise HTTPException(status_code=422, detail=f"Missing required field: {field}")

    try:
        # Parse started_at if provided
        started_at = datetime.now()
        if status_data.get("started_at"):
            started_at = datetime.fromisoformat(status_data["started_at"].replace("Z", "+00:00"))

        status = StatusUpdate(
            status_id=status_data["status_id"],
            title=status_data["title"],
            status_type=status_data["status_type"],
            severity=status_data.get("severity", "info"),
            affected_services=status_data.get("affected_services", []),
            description=status_data["description"],
            started_at=started_at,
            is_active=status_data.get("is_active", True),
            updates=status_data.get("updates", [])
        )

        status_store = get_status()
        status_store.add_status(status)

        return {
            "success": True,
            "message": f"Status update {status.status_id} created successfully",
            "status_id": status.status_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating status: {str(e)}")


@app.put("/api/admin/status/{status_id}")
async def update_status(status_id: str, update_data: dict):
    """Add an update to an existing status."""
    message = update_data.get("message", "")
    if not message:
        raise HTTPException(status_code=422, detail="Update message is required")

    try:
        status_store = get_status()
        success = status_store.update_status(
            status_id=status_id,
            message=message,
            new_status_type=update_data.get("new_status_type"),
            resolved=update_data.get("resolved", False)
        )

        if not success:
            raise HTTPException(status_code=404, detail=f"Status {status_id} not found")

        return {
            "success": True,
            "message": f"Status {status_id} updated successfully",
            "resolved": update_data.get("resolved", False)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status: {str(e)}")


@app.post("/api/admin/approved-response")
async def add_approved_response_api(data: dict):
    """
    Add an approved response to the knowledge base.

    When an agent approves a high-quality response, it can be added to the KB
    so future similar tickets will find this response in search results.

    Required fields:
        - ticket_id: Original ticket ID
        - question_summary: Generalized version of the question
        - response: The approved response text
        - category: Category (billing, bug, outage, etc.)
        - approved_by: Agent ID who approved this

    Optional fields:
        - tags: List of searchable tags
    """
    # Validate required fields
    required_fields = ["ticket_id", "question_summary", "response", "category", "approved_by"]
    for field in required_fields:
        if not data.get(field):
            raise HTTPException(status_code=422, detail=f"Missing required field: {field}")

    # Validate category
    try:
        category = Category(data["category"])
    except ValueError:
        valid_categories = [c.value for c in Category]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category: {data['category']}. Must be one of: {valid_categories}"
        )

    try:
        # Parse approved_at if provided, otherwise use current time
        approved_at = datetime.now()
        if data.get("approved_at"):
            approved_at = datetime.fromisoformat(data["approved_at"].replace("Z", "+00:00"))

        # Get tags (default to empty list)
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Add to KB
        success = add_approved_response(
            ticket_id=data["ticket_id"],
            question_summary=data["question_summary"],
            response=data["response"],
            category=category.value,
            tags=tags,
            approved_by=data["approved_by"],
            approved_at=approved_at.isoformat()
        )

        if success:
            return {
                "success": True,
                "message": f"Approved response from ticket {data['ticket_id']} added to KB",
                "ticket_id": data["ticket_id"],
                "category": category.value
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add response to KB")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding approved response: {str(e)}")


# Collections info endpoint
@app.get("/api/collections")
async def get_collections_info():
    """Get information about all KB collections."""
    try:
        history = get_history()
        status_store = get_status()
        conversation_store = get_conversations()

        return {
            "collections": [
                {
                    "name": KBCollection.SUPPORT_KB.value,
                    "description": "Static knowledge base documents (procedures, policies, guides)",
                    "type": "static"
                },
                {
                    "name": KBCollection.PREVIOUS_QUERIES.value,
                    "description": "Previously processed tickets for auto-reply matching",
                    "type": "dynamic",
                    "stats": history.get_stats()
                },
                {
                    "name": KBCollection.STATUS_UPDATES.value,
                    "description": "System status updates, outages, and announcements",
                    "type": "dynamic",
                    "stats": status_store.get_stats()
                },
                {
                    "name": "conversations",
                    "description": "Multi-turn conversation threads for Q&A follow-up",
                    "type": "dynamic",
                    "stats": conversation_store.get_stats()
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# Conversation API endpoints
@app.get("/api/conversations")
async def list_conversations(status: str | None = None, limit: int = 50):
    """List conversations, optionally filtered by status."""
    try:
        conversation_store = get_conversations()

        if status == "active":
            conversations = conversation_store.get_active_conversations()
        elif status == "awaiting_customer":
            conversations = conversation_store.get_awaiting_customer()
        else:
            conversations = list(conversation_store._conversations.values())

        # Sort by updated_at descending
        conversations.sort(key=lambda c: c.updated_at, reverse=True)

        # Limit results
        conversations = conversations[:limit]

        return [
            {
                "conversation_id": c.conversation_id,
                "original_ticket_id": c.original_ticket_id,
                "customer_email": c.customer_email,
                "customer_name": c.customer_name,
                "subject": c.subject,
                "status": c.status.value,
                "message_count": len(c.messages),
                "pending_fields": c.pending_fields,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat()
            }
            for c in conversations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/conversations/stats")
async def get_conversation_stats():
    """Get statistics about conversations."""
    try:
        conversation_store = get_conversations()
        return conversation_store.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation by ID."""
    try:
        conversation_store = get_conversations()
        conversation = conversation_store.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        return conversation.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """Get all messages in a conversation."""
    try:
        conversation_store = get_conversations()
        conversation = conversation_store.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        return [msg.model_dump(mode="json") for msg in conversation.messages]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/conversations/{conversation_id}/context")
async def get_conversation_context(conversation_id: str):
    """Get the full conversation context as formatted text (for LLM use)."""
    try:
        conversation_store = get_conversations()
        context = conversation_store.get_conversation_context(conversation_id)

        if not context:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        return {"context": context}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/api/conversations/{conversation_id}/followup")
async def process_followup(conversation_id: str, ticket_data: dict):
    """Process a follow-up message in an existing conversation."""
    try:
        # Validate conversation exists
        conversation_store = get_conversations()
        conversation = conversation_store.get_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        # Parse datetime if string
        if isinstance(ticket_data.get("created_at"), str):
            ticket_data["created_at"] = datetime.fromisoformat(
                ticket_data["created_at"].replace("Z", "+00:00")
            )

        # Parse account tier if string
        if isinstance(ticket_data.get("account_tier"), str):
            ticket_data["account_tier"] = AccountTier(ticket_data["account_tier"])

        # Mark as follow-up and set conversation_id
        ticket_data["conversation_id"] = conversation_id
        ticket_data["is_followup"] = True

        # Use customer info from conversation if not provided
        if not ticket_data.get("customer_email"):
            ticket_data["customer_email"] = conversation.customer_email
        if not ticket_data.get("customer_name"):
            ticket_data["customer_name"] = conversation.customer_name
        if not ticket_data.get("account_tier"):
            ticket_data["account_tier"] = conversation.account_tier
        if not ticket_data.get("product"):
            ticket_data["product"] = conversation.product
        if not ticket_data.get("subject"):
            ticket_data["subject"] = f"Re: {conversation.subject}"

        # Validate ticket
        ticket = SupportTicket(**ticket_data)

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise

    # Process follow-up ticket
    try:
        llm = get_llm()
        retriever = get_kb_retriever()
        ticket_history = get_history()
        status_store = get_status()
        result = process_ticket(
            ticket, llm, retriever, ticket_history, status_store, conversation_store
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/api/conversations/{conversation_id}/resolve")
async def resolve_conversation(conversation_id: str):
    """Mark a conversation as resolved."""
    try:
        conversation_store = get_conversations()
        conversation = conversation_store.resolve_conversation(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        return {
            "success": True,
            "message": f"Conversation {conversation_id} marked as resolved",
            "conversation_id": conversation_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/customers/{customer_email}/conversations")
async def get_customer_conversations(customer_email: str):
    """Get all conversations for a specific customer."""
    try:
        conversation_store = get_conversations()
        conversations = conversation_store.get_conversations_by_customer(customer_email)

        return [
            {
                "conversation_id": c.conversation_id,
                "subject": c.subject,
                "status": c.status.value,
                "message_count": len(c.messages),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat()
            }
            for c in conversations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/api/kb/search")
async def search_kb(search_data: dict):
    """Search the knowledge base for relevant articles."""
    query = search_data.get("query", "")
    k = search_data.get("k", 5)
    
    if not query or len(query) < 3:
        return []
    
    try:
        retriever = get_kb_retriever()
        results = retriever.search(query, k=k)
        
        # Convert to dict for JSON response
        return [
            {
                "doc_name": hit.doc_name,
                "section": hit.section,
                "passage": hit.passage,
                "relevance_score": hit.relevance_score
            }
            for hit in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.post("/api/admin/known-issue")
async def add_known_issue(issue_data: dict):
    """Add a new known issue to the knowledge base."""
    global _retriever
    
    # Validate required fields
    required_fields = ["issue_id", "title", "status", "severity", "affected", "description", "workaround"]
    for field in required_fields:
        if not issue_data.get(field):
            raise HTTPException(status_code=422, detail=f"Missing required field: {field}")
    
    # Format the issue as markdown
    today = datetime.now().strftime("%Y-%m-%d")
    expected_resolution = issue_data.get("expected_resolution") or "TBD"
    
    # Format workaround steps as bullet points
    workaround_lines = issue_data["workaround"].strip().split("\n")
    workaround_formatted = "\n".join(f"- {line.strip().lstrip('-').strip()}" for line in workaround_lines if line.strip())
    
    issue_markdown = f"""

---

### {issue_data['issue_id']}: {issue_data['title']}

**Status**: {issue_data['status']}  
**Severity**: {issue_data['severity']}  
**Affected**: {issue_data['affected']}  
**First Reported**: {today}

**Description**:
{issue_data['description']}

**Workaround**:
{workaround_formatted}

**Expected Resolution**: {expected_resolution}
"""
    
    # Append to known_issues.md
    known_issues_path = get_kb_path() / "known_issues.md"
    
    try:
        # Read existing content
        with open(known_issues_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Find the "Recently Resolved" section and insert before it
        # If not found, append to the end
        resolved_marker = "## Recently Resolved"
        if resolved_marker in content:
            parts = content.split(resolved_marker)
            new_content = parts[0].rstrip() + issue_markdown + "\n" + resolved_marker + parts[1]
        else:
            new_content = content.rstrip() + issue_markdown
        
        # Write updated content
        with open(known_issues_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        # Rebuild the KB index to include the new issue
        _retriever = None  # Reset retriever to force rebuild
        build_kb_index(force_rebuild=True)
        
        return {
            "success": True,
            "message": f"Known issue {issue_data['issue_id']} added successfully",
            "issue_id": issue_data["issue_id"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add known issue: {str(e)}")


# Monitoring API Endpoints
@app.post("/api/monitoring/start")
async def start_monitoring():
    """Initialize and start the monitoring system."""
    global _monitoring_state
    
    with _monitoring_lock:
        if _monitoring_state["running"]:
            raise HTTPException(status_code=400, detail="Monitoring is already running")
        
        try:
            generator = LogEventGenerator(event_interval=2.0)
            threshold_checker = ThresholdChecker()
            
            generator.start()
            
            _monitoring_state["running"] = True
            _monitoring_state["generator"] = generator
            _monitoring_state["threshold_checker"] = threshold_checker
            _monitoring_state["events"] = []
            _monitoring_state["issues"] = []
            _monitoring_state["alerts"] = []
            
            return {
                "success": True,
                "message": "Monitoring started successfully",
                "running": True
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")


@app.post("/api/monitoring/stop")
async def stop_monitoring():
    """Stop the monitoring system gracefully."""
    global _monitoring_state
    
    with _monitoring_lock:
        if not _monitoring_state["running"]:
            raise HTTPException(status_code=400, detail="Monitoring is not running")
        
        try:
            generator = _monitoring_state["generator"]
            if generator:
                generator.stop()
            
            _monitoring_state["running"] = False
            _monitoring_state["generator"] = None
            _monitoring_state["threshold_checker"] = None
            
            return {
                "success": True,
                "message": "Monitoring stopped successfully",
                "running": False
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")


@app.get("/api/monitoring/status")
async def get_monitoring_status():
    """Get current monitoring status and event count."""
    with _monitoring_lock:
        running = _monitoring_state["running"]
        event_count = len(_monitoring_state["events"])
        
        return {
            "running": running,
            "event_count": event_count
        }


@app.get("/api/monitoring/events")
async def get_monitoring_events(limit: int = 50):
    """Get recent events sorted by timestamp descending."""
    with _monitoring_lock:
        generator = _monitoring_state["generator"]
        threshold_checker = _monitoring_state["threshold_checker"]
        
        if not generator:
            return []
        
        events = generator.get_events(limit=None)
        
        if threshold_checker:
            for event in events:
                if not event.flagged and not event.critical:
                    result = threshold_checker.check_event(event)
                    event.flagged = result.flagged
                    event.critical = result.critical
        
        _monitoring_state["events"] = events
        
        if limit:
            events = events[:limit]
        
        return [event.model_dump(mode='json') for event in events]


@app.get("/api/monitoring/flagged")
async def get_flagged_events():
    """Get only flagged or critical events."""
    with _monitoring_lock:
        events = _monitoring_state["events"]
        flagged_events = [e for e in events if e.flagged or e.critical]
        
        return [event.model_dump(mode='json') for event in flagged_events]


@app.get("/api/monitoring/ai-actions")
async def get_ai_actions():
    """Get AI-generated issues and alerts."""
    with _monitoring_lock:
        issues = _monitoring_state["issues"]
        alerts = _monitoring_state["alerts"]
        
        return {
            "issues": [issue.model_dump(mode='json') for issue in issues],
            "alerts": [alert.model_dump(mode='json') for alert in alerts]
        }


@app.post("/api/monitoring/clear")
async def clear_monitoring_data():
    """Clear all monitoring events, issues, and alerts."""
    with _monitoring_lock:
        generator = _monitoring_state["generator"]
        if generator:
            generator.clear_events()
        
        _monitoring_state["events"] = []
        _monitoring_state["issues"] = []
        _monitoring_state["alerts"] = []
        
        return {
            "success": True,
            "message": "Monitoring data cleared successfully"
        }


# Static file serving
@app.get("/")
async def serve_index():
    """Serve the main HTML page."""
    index_path = get_web_path() / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.get("/style.css")
async def serve_css():
    """Serve the CSS file."""
    css_path = get_web_path() / "style.css"
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS not found")
    return FileResponse(css_path, media_type="text/css")


@app.get("/app.js")
async def serve_js():
    """Serve the JavaScript file."""
    js_path = get_web_path() / "app.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript not found")
    # Disable caching for development
    return FileResponse(
        js_path,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the server using uvicorn."""
    import uvicorn
    
    print("\n" + "=" * 60)
    print("  SUPPORT TRIAGE SYSTEM - Web Server")
    print("=" * 60)
    print(f"\n  Starting server at http://{host}:{port}")
    print("  Press Ctrl+C to stop\n")
    
    # Pre-initialize LLM
    get_llm()
    print("  Mode: OpenAI")
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)

