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
    RoutingDecision, ReplyDraft, Urgency, Category, Sentiment, Team
)
from .llm_client import get_llm_client, LLMProvider
from .kb.retriever import get_retriever, KBRetriever
from .kb.indexer import build_kb_index
from .kb.ticket_history import get_ticket_history, TicketHistoryStore
from .pipeline.triage import triage_and_extract
from .pipeline.routing import compute_routing
from .pipeline.reply import draft_reply
from .pipeline.guardrail import check_guardrails, check_input_guardrails, sanitize_input


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


def get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm_client()
    return _llm


def get_kb_retriever():
    global _retriever
    if _retriever is None:
        llm = get_llm()
        _retriever = get_retriever(use_mock=llm.is_mock)
    return _retriever


def get_history():
    global _ticket_history
    if _ticket_history is None:
        llm = get_llm()
        _ticket_history = get_ticket_history(use_mock=llm.is_mock)
    return _ticket_history


def process_ticket(
    ticket: SupportTicket,
    llm: LLMProvider,
    retriever: KBRetriever,
    ticket_history: TicketHistoryStore | None = None
) -> PipelineResult:
    """
    Process a single ticket through the full pipeline.

    Args:
        ticket: Support ticket to process
        llm: LLM provider instance
        retriever: KB retriever instance
        ticket_history: Optional ticket history store for auto-reply

    Returns:
        Complete PipelineResult
    """
    # Initialize ticket history if not provided
    if ticket_history is None:
        ticket_history = get_ticket_history(use_mock=llm.is_mock)

    # Stage 0a: Input guardrail check
    input_guardrail = check_input_guardrails(ticket, llm)
    
    # If input is blocked, return early with blocked response
    if input_guardrail.blocked:
        return _create_blocked_response(ticket, input_guardrail, llm.is_mock)
    
    # Sanitize input if needed
    if not input_guardrail.passed:
        ticket = sanitize_input(ticket, input_guardrail)

    # Stage 0b: Check for similar recent tickets (auto-reply)
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
        reply = cached_reply
        reply.internal_notes = (
            f"[AUTO-REPLY] Based on similar ticket {matched_info['matched_ticket_id']} "
            f"(similarity: {matched_info['similarity_score']:.2%})\n\n"
            f"{reply.internal_notes}"
        )

        # Skip guardrails for auto-reply (already validated previously)
        guardrail = GuardrailStatus(
            passed=True,
            issues_found=[],
            fixes_applied=["Auto-reply from validated previous response"]
        )

        result = PipelineResult(
            ticket_id=ticket.ticket_id,
            triage=triage,
            extracted_fields=extracted,
            routing=routing,
            kb_hits=kb_hits,
            reply=reply,
            input_guardrail_status=input_guardrail,
            guardrail_status=guardrail,
            processing_mode="mock" if llm.is_mock else "real",
            auto_reply=auto_reply_info
        )

        # Store this ticket in history too
        ticket_history.add_ticket(ticket, result)

        return result

    # Stage 1: Triage and extraction
    triage, extracted = triage_and_extract(ticket, llm)

    # Stage 2: KB retrieval
    kb_hits = retriever.search_with_context(
        ticket_subject=ticket.subject,
        ticket_body=ticket.body,
        category=triage.category.value,
        k=5
    )

    # Stage 3: Routing
    routing = compute_routing(triage, ticket.account_tier)

    # Stage 4: Reply drafting
    reply = draft_reply(ticket, triage, extracted, routing, kb_hits, llm)

    # Stage 5: Guardrail check
    guardrail = check_guardrails(reply, kb_hits, llm)

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
        processing_mode="mock" if llm.is_mock else "real",
        auto_reply=auto_reply_info
    )

    # Store processed ticket in history for future auto-replies
    ticket_history.add_ticket(ticket, result)

    return result


def _create_blocked_response(
    ticket: SupportTicket,
    input_guardrail: InputGuardrailStatus,
    is_mock: bool
) -> PipelineResult:
    """
    Create a pipeline result for a blocked ticket.
    
    Args:
        ticket: The blocked ticket
        input_guardrail: Input guardrail results
        is_mock: Whether running in mock mode
    
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

For urgent matters, please contact our support team directly.

Best regards,
Support Team""",
        internal_notes=f"""[BLOCKED BY INPUT GUARDRAILS]

Risk Level: {input_guardrail.risk_level}
Issues Detected: {', '.join(input_guardrail.issues_found)}

ACTION REQUIRED: Review this ticket manually before any response.
This ticket was flagged by automated security systems and requires human review.""",
        citations=[]
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
        processing_mode="mock" if is_mock else "real",
        auto_reply=AutoReplyInfo()
    )


# API Routes
@app.get("/api/mode")
async def get_mode():
    """Get the current processing mode (mock or real)."""
    llm = get_llm()
    return {"mode": "mock" if llm.is_mock else "real"}


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
        result = process_ticket(ticket, llm, retriever, ticket_history)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.get("/api/ticket-history/stats")
async def get_ticket_history_stats():
    """Get statistics about the ticket history store."""
    try:
        history = get_history()
        return history.get_stats()
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
        llm = get_llm()
        _retriever = None  # Reset retriever to force rebuild
        build_kb_index(use_mock=llm.is_mock, force_rebuild=True)
        
        return {
            "success": True,
            "message": f"Known issue {issue_data['issue_id']} added successfully",
            "issue_id": issue_data["issue_id"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add known issue: {str(e)}")


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
    return FileResponse(js_path, media_type="application/javascript")


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
    
    # Pre-initialize to show mode
    llm = get_llm()
    print(f"  Mode: {'MOCK (no API key)' if llm.is_mock else 'REAL (OpenAI)'}")
    print()
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)

