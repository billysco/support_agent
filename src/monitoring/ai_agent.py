"""
AI Agent for monitoring event analysis and automated response generation.
"""

import json
from datetime import datetime
from typing import Optional
import uuid

from ..llm_client import OpenAIProvider
from ..kb.retriever import KBRetriever
from ..kb.collections import KBCollection
from .schemas import LogEvent, AIIssue, AIAlert, EventType


class MonitoringAIAgent:
    """
    AI agent that analyzes flagged monitoring events and generates:
    - KB entries for detected issues
    - Engineering alert emails
    - Customer notification emails (for critical issues)
    """

    def __init__(self, llm: OpenAIProvider, kb_retriever: KBRetriever):
        self._llm = llm
        self._kb_retriever = kb_retriever
        self._processed_event_ids: set[str] = set()

    def analyze_flagged_event(
        self,
        event: LogEvent,
        recent_events: list[LogEvent]
    ) -> tuple[Optional[AIIssue], list[AIAlert]]:
        """Analyze a flagged event and generate issue/alerts in ONE LLM call."""

        # Skip if already processed
        if event.event_id in self._processed_event_ids:
            print(f"[AIAgent] Event {event.event_id[:8]}... already processed, skipping")
            return None, []

        self._processed_event_ids.add(event.event_id)
        print(f"[AIAgent] Analyzing event {event.event_id[:8]}... service={event.service_name}")

        # Build context from recent flagged events
        context_events = [
            e for e in recent_events
            if e.service_name == event.service_name and e.flagged
        ][:5]

        # Single LLM call that returns everything
        print(f"[AIAgent] Calling LLM (single consolidated call)...")
        result = self._analyze_and_generate_all(event, context_events)

        if not result:
            print(f"[AIAgent] LLM call failed")
            return None, []

        print(f"[AIAgent] LLM returned: severity={result.get('severity', 'unknown')}")

        # Create issue from result
        issue = self._create_issue_from_result(event, result, context_events)
        print(f"[AIAgent] Issue created: {issue.issue_id}")

        # Create alerts from result
        alerts = self._create_alerts_from_result(event, issue, result)
        print(f"[AIAgent] Created {len(alerts)} alerts")

        return issue, alerts

    def _analyze_and_generate_all(
        self,
        event: LogEvent,
        context_events: list[LogEvent]
    ) -> Optional[dict]:
        """Single LLM call that analyzes event AND generates all content."""

        context_str = ""
        if context_events:
            context_str = "\n".join([
                f"- {e.service_name}: {e.message} (metrics: {json.dumps(e.metrics)})"
                for e in context_events[-3:]
            ])

        prompt = f"""Analyze this monitoring event and generate all required outputs in a single response.

EVENT:
- Type: {event.event_type.value}
- Service: {event.service_name}
- Region: {event.region}
- Message: {event.message}
- Metrics: {json.dumps(event.metrics)}
- Critical: {event.critical}

RECENT EVENTS (same service):
{context_str if context_str else "None"}

Generate a JSON response with ALL of the following:
{{
    "severity": "critical|high|medium|low",
    "root_cause": "Brief root cause hypothesis (1 sentence)",
    "customer_impact": "Impact on customers (1 sentence)",
    "recommended_action": "What to do (1 sentence)",
    "issue_description": "Technical description for KB (2-3 sentences)",
    "workaround": "Workaround if any, or null",
    "eng_alert_subject": "Engineering alert subject line",
    "eng_alert_body": "Engineering alert body (2-3 sentences with metrics)",
    "customer_alert_subject": "Customer notification subject",
    "customer_alert_body": "Customer-friendly notification (2-3 sentences, no technical jargon)"
}}"""

        system_prompt = "You are an SRE analyzing monitoring data. Respond with valid JSON only. Be concise."

        try:
            return self._llm.complete_json(prompt, system_prompt)
        except Exception as e:
            print(f"[AIAgent] LLM call failed: {e}")
            return None

    def _create_issue_from_result(
        self,
        event: LogEvent,
        result: dict,
        context_events: list[LogEvent]
    ) -> AIIssue:
        """Create an AIIssue from the consolidated LLM result."""

        issue_id = f"ISS-{int(datetime.now().timestamp())}-{event.service_name}"

        affected_regions = list(set(
            [event.region] + [e.region for e in context_events if e.region]
        ))

        related_events = [event.event_id] + [e.event_id for e in context_events[:5]]

        return AIIssue(
            issue_id=issue_id,
            created_at=datetime.now(),
            title=f"{result.get('severity', 'high').title()} {event.event_type.value} issue in {event.service_name} ({event.region})",
            status="investigating",
            severity=result.get("severity", "medium"),
            affected_services=[event.service_name],
            affected_regions=affected_regions,
            description=result.get("issue_description", result.get("root_cause", "Issue detected")),
            workaround=result.get("workaround"),
            ai_generated=True,
            related_events=related_events,
            kb_document_id=None
        )

    def _create_alerts_from_result(
        self,
        event: LogEvent,
        issue: AIIssue,
        result: dict
    ) -> list[AIAlert]:
        """Create alerts from the consolidated LLM result."""
        alerts = []
        ts = int(datetime.now().timestamp())

        # Engineering alert (always)
        eng_alert = AIAlert(
            alert_id=f"ALR-{ts}-eng",
            created_at=datetime.now(),
            alert_type="engineering",
            subject=result.get("eng_alert_subject", f"[ALERT] {issue.title}"),
            body=result.get("eng_alert_body", f"Issue detected in {event.service_name}"),
            affected_service=event.service_name,
            related_issue_id=issue.issue_id,
            related_ticket_id=None
        )
        alerts.append(eng_alert)

        # Customer alert (only for critical)
        if event.critical:
            cust_alert = AIAlert(
                alert_id=f"ALR-{ts}-cust",
                created_at=datetime.now(),
                alert_type="customer",
                subject=result.get("customer_alert_subject", f"Service Update: {event.service_name}"),
                body=result.get("customer_alert_body", "We are investigating an issue and will provide updates."),
                affected_service=event.service_name,
                related_issue_id=issue.issue_id,
                related_ticket_id=None
            )
            alerts.append(cust_alert)

        return alerts

    def _check_duplicate_issue(self, event: LogEvent, analysis: dict) -> bool:
        """Disabled for performance."""
        return False

    def _store_issue_in_kb(self, issue: AIIssue) -> None:
        """Store in KB (no-op for now)."""
        pass

    def clear_processed_events(self):
        """Clear the set of processed event IDs."""
        self._processed_event_ids.clear()

