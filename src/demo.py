"""
CLI demo runner for the support triage system.
Processes sample tickets and displays formatted results.
"""

import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from .schemas import SupportTicket, PipelineResult, AccountTier, AutoReplyInfo, GuardrailStatus
from .llm_client import get_llm_client, LLMProvider
from .kb.retriever import get_retriever, KBRetriever
from .kb.ticket_history import get_ticket_history, TicketHistoryStore
from .pipeline.triage import triage_and_extract
from .pipeline.routing import compute_routing, get_sla_description
from .pipeline.reply import draft_reply
from .pipeline.guardrail import check_guardrails
from .utils import (
    print_separator, print_section_header,
    format_urgency_badge, redact_email
)


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def load_sample_tickets() -> list[SupportTicket]:
    """Load sample tickets from the data directory."""
    data_path = get_project_root() / "data" / "sample_tickets.json"
    
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

    # Stage 0: Check for similar recent tickets (auto-reply)
    should_auto_reply, similarity_score, cached_reply, matched_info = \
        ticket_history.find_similar_ticket(ticket)

    auto_reply_info = AutoReplyInfo(
        is_auto_reply=False,
        similarity_score=similarity_score
    )

    if should_auto_reply and cached_reply and matched_info:
        # Calculate time since match
        from datetime import datetime
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
        guardrail_status=guardrail,
        processing_mode="mock" if llm.is_mock else "real",
        auto_reply=auto_reply_info
    )

    # Store processed ticket in history for future auto-replies
    ticket_history.add_ticket(ticket, result)

    return result


def print_ticket_result(ticket: SupportTicket, result: PipelineResult):
    """Print formatted results for a single ticket."""

    print_separator("=")
    print(f"TICKET: {ticket.ticket_id} | {ticket.subject[:50]}...")
    print(f"Customer: {ticket.customer_name} ({ticket.account_tier.value})")
    print(f"Mode: {result.processing_mode.upper()}")
    if result.auto_reply.is_auto_reply:
        print(f"AUTO-REPLY: YES (matched {result.auto_reply.matched_ticket_id}, "
              f"similarity: {result.auto_reply.similarity_score:.2%})")
    print_separator("=")
    
    # Triage section
    print_section_header("TRIAGE")
    urgency_display = format_urgency_badge(result.triage.urgency.value)
    print(f"Urgency: {urgency_display}")
    print(f"Category: {result.triage.category.value}")
    print(f"Sentiment: {result.triage.sentiment.value}")
    print(f"Confidence: {result.triage.confidence:.0%}")
    print(f"Rationale: \"{result.triage.rationale}\"")
    
    # Extracted fields section
    print_section_header("EXTRACTED FIELDS")
    ef = result.extracted_fields
    if ef.environment:
        print(f"Environment: {ef.environment}")
    if ef.region:
        print(f"Region: {ef.region}")
    if ef.error_message:
        print(f"Error: {ef.error_message[:80]}...")
    if ef.impact:
        print(f"Impact: {ef.impact[:80]}...")
    if ef.order_id:
        print(f"Order/Invoice: {ef.order_id}")
    if ef.reproduction_steps:
        print(f"Reproduction: {ef.reproduction_steps[:80]}...")
    if ef.missing_fields:
        print(f"Missing Fields: {ef.missing_fields}")
    else:
        print("Missing Fields: None - all critical info provided")
    
    # Routing section
    print_section_header("ROUTING")
    print(f"Team: {result.routing.team.value.upper()}")
    print(f"SLA: {get_sla_description(result.routing.sla_hours)}")
    print(f"Escalation: {'YES' if result.routing.escalation else 'No'}")
    print(f"Reasoning: {result.routing.reasoning}")
    
    # KB Citations section
    print_section_header("KB CITATIONS")
    if result.kb_hits:
        for i, hit in enumerate(result.kb_hits[:3], 1):
            print(f"{i}. {hit.citation}")
            print(f"   \"{hit.passage[:100]}...\"")
    else:
        print("No relevant KB passages found.")
    
    # Customer Reply section
    print_section_header("CUSTOMER REPLY")
    print(result.reply.customer_reply)
    
    # Internal Notes section
    print_section_header("INTERNAL NOTES")
    print(result.reply.internal_notes)
    
    # Guardrail Status section
    print_section_header("GUARDRAIL STATUS")
    status = "PASSED" if result.guardrail_status.passed else "FAILED"
    print(f"Status: {status}")
    if result.guardrail_status.issues_found:
        print(f"Issues: {result.guardrail_status.issues_found}")
    if result.guardrail_status.fixes_applied:
        print(f"Fixes: {result.guardrail_status.fixes_applied}")
    
    print()


def print_json_output(results: list[PipelineResult]):
    """Print full JSON output for all results."""
    print_separator("=")
    print("FULL JSON OUTPUT")
    print_separator("=")
    
    output = [result.model_dump(mode="json") for result in results]
    print(json.dumps(output, indent=2, default=str))


def run_demo(show_json: bool = True):
    """
    Run the full demo on all sample tickets.
    
    Args:
        show_json: Whether to print full JSON output at the end
    """
    print("\n" + "=" * 70)
    print("  CUSTOMER SUPPORT TRIAGE AND REPLY DRAFT SYSTEM")
    print("  Demo Mode")
    print("=" * 70 + "\n")
    
    # Initialize components
    print("Initializing system...")
    llm = get_llm_client()
    retriever = get_retriever(use_mock=llm.is_mock)
    print(f"LLM Mode: {'MOCK (deterministic)' if llm.is_mock else 'REAL (OpenAI)'}")
    print(f"KB Mode: {'MOCK embeddings' if llm.is_mock else 'OpenAI embeddings'}")
    print()
    
    # Load tickets
    print("Loading sample tickets...")
    tickets = load_sample_tickets()
    print(f"Loaded {len(tickets)} tickets\n")
    
    # Process each ticket
    results = []
    for i, ticket in enumerate(tickets, 1):
        print(f"Processing ticket {i}/{len(tickets)}: {ticket.ticket_id}")
        result = process_ticket(ticket, llm, retriever)
        results.append(result)
        print_ticket_result(ticket, result)
    
    # Summary
    print_separator("=")
    print("DEMO SUMMARY")
    print_separator("=")
    print(f"Tickets Processed: {len(results)}")
    print(f"Processing Mode: {'MOCK' if llm.is_mock else 'REAL'}")
    print()
    
    # Show routing diversity
    print("Routing Distribution:")
    for result in results:
        print(f"  - {result.ticket_id}: {result.triage.urgency.value} -> {result.routing.team.value} (escalate={result.routing.escalation})")
    print()
    
    # JSON output
    if show_json:
        print_json_output(results)
    
    return results


if __name__ == "__main__":
    run_demo()

