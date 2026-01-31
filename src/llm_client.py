"""
LLM client with support for OpenAI-compatible APIs and mock mode.
"""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any

from .schemas import (
    TriageResult, ExtractedFields, ReplyDraft, GuardrailStatus,
    Urgency, Category, Sentiment, SupportTicket
)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a completion for the given prompt."""
        pass
    
    @abstractmethod
    def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        """Generate a JSON completion for the given prompt."""
        pass
    
    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Whether this is a mock provider."""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """Provider for OpenAI-compatible APIs."""
    
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Import here to avoid dependency issues in mock mode
        from openai import OpenAI
        
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self.client = OpenAI(**client_kwargs)
    
    @property
    def is_mock(self) -> bool:
        return False
    
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content or ""
    
    def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


class MockProvider(LLMProvider):
    """Deterministic mock provider for demos without API key."""
    
    @property
    def is_mock(self) -> bool:
        return True
    
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        # Return mock responses based on prompt content
        return "Mock response generated."
    
    def complete_json(self, prompt: str, system_prompt: str = "") -> dict[str, Any]:
        # Return mock JSON based on prompt content
        return {}
    
    def mock_triage(self, ticket: SupportTicket) -> tuple[TriageResult, ExtractedFields]:
        """Generate deterministic triage results based on ticket content."""
        text = f"{ticket.subject} {ticket.body}".lower()
        
        # Determine urgency and category based on keywords
        if any(kw in text for kw in ["outage", "down", "500 error", "production", "critical", "emergency"]):
            urgency = Urgency.p0
            category = Category.outage
            sentiment = Sentiment.negative
            confidence = 0.95
            rationale = "Customer reports production system issues with high business impact."
        elif any(kw in text for kw in ["invoice", "billing", "charge", "payment", "refund", "overcharge"]):
            urgency = Urgency.p2
            category = Category.billing
            sentiment = Sentiment.negative if "unexpected" in text or "wrong" in text else Sentiment.neutral
            confidence = 0.88
            rationale = "Customer has a billing-related inquiry about charges or invoices."
        elif any(kw in text for kw in ["bug", "error", "crash", "broken", "doesn't work", "issue"]):
            urgency = Urgency.p3 if "staging" in text or "dev" in text else Urgency.p2
            category = Category.bug
            sentiment = Sentiment.neutral
            confidence = 0.85
            rationale = "Customer reports a bug with technical details provided."
        elif any(kw in text for kw in ["security", "vulnerability", "breach", "unauthorized"]):
            urgency = Urgency.p1
            category = Category.security
            sentiment = Sentiment.negative
            confidence = 0.92
            rationale = "Customer reports a potential security concern."
        elif any(kw in text for kw in ["feature", "request", "would like", "suggestion"]):
            urgency = Urgency.p3
            category = Category.feature_request
            sentiment = Sentiment.positive
            confidence = 0.80
            rationale = "Customer is requesting a new feature or enhancement."
        elif any(kw in text for kw in ["setup", "getting started", "onboarding", "new account"]):
            urgency = Urgency.p3
            category = Category.onboarding
            sentiment = Sentiment.neutral
            confidence = 0.82
            rationale = "Customer needs help with initial setup or onboarding."
        else:
            urgency = Urgency.p3
            category = Category.other
            sentiment = Sentiment.neutral
            confidence = 0.70
            rationale = "General inquiry that doesn't fit specific categories."
        
        triage = TriageResult(
            urgency=urgency,
            category=category,
            sentiment=sentiment,
            confidence=confidence,
            rationale=rationale
        )
        
        # Extract fields based on patterns
        extracted = self._extract_fields(ticket, text)
        
        return triage, extracted
    
    def _extract_fields(self, ticket: SupportTicket, text: str) -> ExtractedFields:
        """Extract structured fields from ticket text."""
        missing_fields = []
        
        # Environment detection
        environment = None
        if "production" in text or "prod" in text:
            environment = "production"
        elif "staging" in text or "stage" in text:
            environment = "staging"
        elif "dev" in text or "development" in text:
            environment = "development"
        else:
            missing_fields.append("environment")
        
        # Region detection
        region = None
        region_patterns = [
            r"us-east-\d", r"us-west-\d", r"eu-west-\d", r"eu-central-\d",
            r"ap-southeast-\d", r"ap-northeast-\d"
        ]
        for pattern in region_patterns:
            match = re.search(pattern, text)
            if match:
                region = match.group()
                break
        if not region:
            missing_fields.append("region")
        
        # Error message extraction
        error_message = None
        error_patterns = [
            r"error[:\s]+([^\n.]+)",
            r"HTTP\s+\d{3}[^\n]*",
            r"exception[:\s]+([^\n.]+)",
        ]
        for pattern in error_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                error_message = match.group().strip()
                break
        
        # Reproduction steps
        reproduction_steps = None
        if "steps to reproduce" in text or "to reproduce" in text:
            # Try to extract steps
            steps_match = re.search(r"(?:steps to reproduce|to reproduce)[:\s]*(.+?)(?:\n\n|$)", text, re.IGNORECASE | re.DOTALL)
            if steps_match:
                reproduction_steps = steps_match.group(1).strip()
        elif any(f"{i}." in text or f"{i})" in text for i in range(1, 5)):
            reproduction_steps = "Steps provided in ticket body"
        else:
            if "bug" in text:
                missing_fields.append("reproduction_steps")
        
        # Impact extraction
        impact = None
        impact_keywords = ["affecting", "impact", "users affected", "revenue", "customers"]
        for kw in impact_keywords:
            if kw in text:
                impact_match = re.search(rf"{kw}[:\s]*([^\n.]+)", text, re.IGNORECASE)
                if impact_match:
                    impact = impact_match.group().strip()
                    break
        
        # Requested action
        requested_action = None
        action_keywords = ["please", "need", "want", "requesting", "can you"]
        for kw in action_keywords:
            if kw in text:
                action_match = re.search(rf"{kw}[:\s]*([^\n.]+)", text, re.IGNORECASE)
                if action_match:
                    requested_action = action_match.group().strip()
                    break
        
        # Order/Invoice ID
        order_id = None
        id_patterns = [
            r"INV-\d{4}-\d+",
            r"ORD-\d+",
            r"invoice\s*#?\s*(\w+-?\d+)",
            r"order\s*#?\s*(\w+-?\d+)",
        ]
        for pattern in id_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                order_id = match.group()
                break
        
        return ExtractedFields(
            environment=environment,
            region=region,
            error_message=error_message,
            reproduction_steps=reproduction_steps,
            impact=impact,
            requested_action=requested_action,
            order_id=order_id,
            missing_fields=missing_fields
        )
    
    def mock_reply(
        self,
        ticket: SupportTicket,
        triage: TriageResult,
        extracted: ExtractedFields,
        kb_hits: list,
        routing: Any
    ) -> ReplyDraft:
        """Generate a deterministic mock reply."""
        customer_name = ticket.customer_name.split()[0]  # First name
        
        # Build citations list
        citations = [hit.citation for hit in kb_hits[:3]] if kb_hits else []
        
        # Generate reply based on category
        if triage.category == Category.outage:
            reply = f"""Dear {customer_name},

Thank you for reporting this critical issue. We understand the severity and have immediately escalated this to our engineering team.

Based on our incident response procedures {citations[0] if citations else '[KB:outage_procedures#immediate-response]'}, we are:
1. Actively investigating the root cause
2. Monitoring system status in real-time
3. Preparing to deploy a fix as soon as identified

We will provide updates every 30 minutes until resolution. You can also monitor our status page for real-time updates.

{"Please provide the following to help us investigate faster: " + ", ".join(extracted.missing_fields) if extracted.missing_fields else ""}

We sincerely apologize for the disruption and are working urgently to restore service.

Best regards,
Support Team"""
            
            internal_notes = f"""- ESCALATED: P0 outage for {ticket.account_tier.value} customer
- Routed to {routing.team.value} team per escalation matrix
- SLA: {routing.sla_hours} hours
- Customer impact: {extracted.impact or 'Not specified - follow up required'}
- Error reported: {extracted.error_message or 'Not specified'}
- Next actions: Monitor incident channel, prepare customer update in 30 min"""
        
        elif triage.category == Category.billing:
            reply = f"""Dear {customer_name},

Thank you for reaching out about your billing concern. I understand how important it is to have clarity on your charges.

I've located your account and {"the invoice " + extracted.order_id if extracted.order_id else "am reviewing your recent charges"}. Per our billing policies {citations[0] if citations else '[KB:billing_policies#dispute-resolution]'}, I'll review this and provide a detailed breakdown.

{"To complete my review, could you please provide: " + ", ".join(extracted.missing_fields) + "?" if extracted.missing_fields else "I'll have a full response for you within 24 hours."}

If there was an error on our end, we will promptly issue a correction or refund as applicable.

Best regards,
Billing Support Team"""
            
            internal_notes = f"""- Billing inquiry for {ticket.account_tier.value} customer
- Invoice/Order: {extracted.order_id or 'Not provided - check account history'}
- Routed to {routing.team.value} team
- SLA: {routing.sla_hours} hours
- Action: Review invoice details, check for overages or billing errors
- If refund needed: Follow standard refund approval process"""
        
        elif triage.category == Category.bug:
            reply = f"""Dear {customer_name},

Thank you for the detailed bug report. We appreciate you taking the time to document this issue.

I've logged this with our engineering team for investigation. {"The reproduction steps you provided will help us identify the root cause quickly." if extracted.reproduction_steps else ""}

Per our bug handling process {citations[0] if citations else '[KB:bug_reporting#triage-process]'}, {"since this is in a " + extracted.environment + " environment, " if extracted.environment else ""}we'll prioritize this appropriately.

{"To help us investigate further, could you please provide: " + ", ".join(extracted.missing_fields) + "?" if extracted.missing_fields else ""}

We'll update you once we have more information on the timeline for a fix.

Best regards,
Technical Support Team"""
            
            internal_notes = f"""- Bug report from {ticket.account_tier.value} customer
- Environment: {extracted.environment or 'Unknown - clarify with customer'}
- Error: {extracted.error_message or 'See ticket body'}
- Reproduction steps: {'Provided' if extracted.reproduction_steps else 'Missing - requested'}
- Routed to {routing.team.value} team
- SLA: {routing.sla_hours} hours
- Priority: {triage.urgency.value} based on environment and impact"""
        
        else:
            reply = f"""Dear {customer_name},

Thank you for contacting us. I've reviewed your request and am here to help.

{"Based on our documentation " + citations[0] + ", " if citations else ""}I'll ensure your inquiry is handled promptly by the appropriate team.

{"To better assist you, could you please provide: " + ", ".join(extracted.missing_fields) + "?" if extracted.missing_fields else ""}

We'll follow up with you shortly.

Best regards,
Support Team"""
            
            internal_notes = f"""- General inquiry from {ticket.account_tier.value} customer
- Category: {triage.category.value}
- Routed to {routing.team.value} team
- SLA: {routing.sla_hours} hours
- Sentiment: {triage.sentiment.value}"""
        
        return ReplyDraft(
            customer_reply=reply,
            internal_notes=internal_notes,
            citations=citations
        )
    
    def mock_guardrail(self, reply: ReplyDraft, kb_hits: list) -> GuardrailStatus:
        """Run mock guardrail checks."""
        issues = []
        fixes = []
        
        reply_lower = reply.customer_reply.lower()
        
        # Check for potential hallucinations
        problematic_phrases = [
            ("guarantee", "Removed guarantee language - requires verification"),
            ("definitely will", "Softened commitment language"),
            ("100%", "Removed absolute percentage claim"),
            ("always", "Replaced 'always' with more accurate language"),
        ]
        
        for phrase, fix_desc in problematic_phrases:
            if phrase in reply_lower:
                issues.append(f"Found potentially problematic phrase: '{phrase}'")
                fixes.append(fix_desc)
        
        # Check for missing citations when making claims
        claim_indicators = ["per our policy", "according to", "our documentation states"]
        for indicator in claim_indicators:
            if indicator in reply_lower and not reply.citations:
                issues.append(f"Claim '{indicator}' made without KB citation")
        
        # Check for PII exposure
        if "@" in reply.customer_reply and ".com" in reply.customer_reply:
            issues.append("Potential email address in reply - verify it's appropriate")
        
        passed = len(issues) == 0 or len(fixes) >= len(issues)
        
        return GuardrailStatus(
            passed=passed,
            issues_found=issues,
            fixes_applied=fixes
        )


def get_llm_client() -> LLMProvider:
    """
    Factory function to get the appropriate LLM client.
    Returns MockProvider if OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    
    if api_key:
        try:
            return OpenAICompatibleProvider(api_key=api_key)
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client: {e}")
            print("Falling back to mock mode.")
            return MockProvider()
    else:
        print("Note: OPENAI_API_KEY not set. Running in mock mode with deterministic outputs.")
        return MockProvider()

