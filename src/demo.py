"""
CLI demo runner for the support triage system.
Processes sample tickets and displays formatted results.
"""

import json
from datetime import datetime
from pathlib import Path

from .schemas import SupportTicket, PipelineResult, AccountTier
from .llm_client import get_llm_client, LLMProvider
from .kb.retriever import get_retriever, KBRetriever
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
    retriever: KBRetriever
) -> PipelineResult:
    """
    Process a single ticket through the full pipeline.
    
    Args:
        ticket: Support ticket to process
        llm: LLM provider instance
        retriever: KB retriever instance
    
    Returns:
        Complete PipelineResult
    """
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
    return PipelineResult(
        ticket_id=ticket.ticket_id,
        triage=triage,
        extracted_fields=extracted,
        routing=routing,
        kb_hits=kb_hits,
        reply=reply,
        guardrail_status=guardrail,
        processing_mode="mock" if llm.is_mock else "real"
    )


def print_ticket_result(ticket: SupportTicket, result: PipelineResult):
    """Print formatted results for a single ticket."""
    
    print_separator("=")
    print(f"TICKET: {ticket.ticket_id} | {ticket.subject[:50]}...")
    print(f"Customer: {ticket.customer_name} ({ticket.account_tier.value})")
    print(f"Mode: {result.processing_mode.upper()}")
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

