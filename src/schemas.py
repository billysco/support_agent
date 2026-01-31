"""
Pydantic schemas for all inputs and outputs in the support triage system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Urgency(str, Enum):
    """Ticket urgency levels."""
    p0 = "P0"  # Critical - production down
    p1 = "P1"  # High - major feature broken
    p2 = "P2"  # Medium - important but workaround exists
    p3 = "P3"  # Low - minor issue or question


class Category(str, Enum):
    """Ticket category classification."""
    billing = "billing"
    bug = "bug"
    outage = "outage"
    feature_request = "feature_request"
    security = "security"
    onboarding = "onboarding"
    other = "other"


class Sentiment(str, Enum):
    """Customer sentiment analysis."""
    negative = "negative"
    neutral = "neutral"
    positive = "positive"


class Team(str, Enum):
    """Support team routing targets."""
    support = "support"
    engineering = "engineering"
    billing = "billing"
    security = "security"
    customer_success = "customer_success"


class AccountTier(str, Enum):
    """Customer account tiers."""
    enterprise = "enterprise"
    professional = "professional"
    starter = "starter"
    free = "free"


class SupportTicket(BaseModel):
    """Input schema for a support ticket."""
    ticket_id: str = Field(..., description="Unique ticket identifier")
    created_at: datetime = Field(default_factory=datetime.now, description="Ticket creation timestamp")
    customer_name: str = Field(..., description="Customer's name")
    customer_email: str = Field(..., description="Customer's email address")
    account_tier: AccountTier = Field(..., description="Customer's account tier")
    product: str = Field(..., description="Product the ticket is about")
    subject: str = Field(..., description="Ticket subject line")
    body: str = Field(..., description="Full ticket body text")
    attachments: Optional[list[str]] = Field(default=None, description="List of attachment URLs or filenames")


class TriageResult(BaseModel):
    """Output from the triage classification stage."""
    urgency: Urgency = Field(..., description="Urgency level P0-P3")
    category: Category = Field(..., description="Ticket category")
    sentiment: Sentiment = Field(..., description="Customer sentiment")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    rationale: str = Field(..., description="Short rationale grounded in ticket text")


class ExtractedFields(BaseModel):
    """Normalized fields extracted from the ticket."""
    environment: Optional[str] = Field(default=None, description="Environment (production, staging, dev)")
    region: Optional[str] = Field(default=None, description="Geographic region or cloud region")
    error_message: Optional[str] = Field(default=None, description="Error message if present")
    reproduction_steps: Optional[str] = Field(default=None, description="Steps to reproduce the issue")
    impact: Optional[str] = Field(default=None, description="Business or user impact description")
    requested_action: Optional[str] = Field(default=None, description="What the customer is asking for")
    order_id: Optional[str] = Field(default=None, description="Order ID or invoice ID if applicable")
    missing_fields: list[str] = Field(default_factory=list, description="Fields that need to be requested from customer")


class RoutingDecision(BaseModel):
    """Routing decision for the ticket."""
    team: Team = Field(..., description="Target team for routing")
    sla_hours: int = Field(..., description="SLA target in hours")
    escalation: bool = Field(default=False, description="Whether to escalate immediately")
    reasoning: str = Field(..., description="Explanation for routing decision")


class KBHit(BaseModel):
    """A knowledge base search result."""
    doc_name: str = Field(..., description="Source document name")
    section: str = Field(..., description="Section within the document")
    passage: str = Field(..., description="Relevant passage text")
    relevance_score: float = Field(default=0.0, description="Relevance score from retrieval")
    
    @property
    def citation(self) -> str:
        """Format as citation string."""
        return f"[KB:{self.doc_name}#{self.section}]"


class ReplyDraft(BaseModel):
    """Draft reply for the customer."""
    customer_reply: str = Field(..., description="Customer-facing reply text")
    internal_notes: str = Field(..., description="Internal notes for the support agent")
    citations: list[str] = Field(default_factory=list, description="KB citations used in the reply")


class GuardrailStatus(BaseModel):
    """Result of guardrail checks on the draft."""
    passed: bool = Field(..., description="Whether all guardrails passed")
    issues_found: list[str] = Field(default_factory=list, description="List of issues detected")
    fixes_applied: list[str] = Field(default_factory=list, description="List of fixes that were applied")


class AutoReplyInfo(BaseModel):
    """Information about auto-reply decision."""
    is_auto_reply: bool = Field(default=False, description="Whether this reply was auto-generated from similar ticket")
    similarity_score: float = Field(default=0.0, description="Similarity score with matched ticket (0-1)")
    matched_ticket_id: Optional[str] = Field(default=None, description="ID of the similar ticket that triggered auto-reply")
    time_since_match_hours: Optional[float] = Field(default=None, description="Hours since the matched ticket was processed")


class PipelineResult(BaseModel):
    """Complete output from the support triage pipeline."""
    ticket_id: str = Field(..., description="Original ticket ID")
    triage: TriageResult = Field(..., description="Triage classification results")
    extracted_fields: ExtractedFields = Field(..., description="Extracted and normalized fields")
    routing: RoutingDecision = Field(..., description="Routing decision")
    kb_hits: list[KBHit] = Field(default_factory=list, description="Knowledge base search results")
    reply: ReplyDraft = Field(..., description="Draft reply for customer")
    guardrail_status: GuardrailStatus = Field(..., description="Guardrail check results")
    processing_mode: str = Field(default="mock", description="Whether processed in 'real' or 'mock' mode")
    auto_reply: AutoReplyInfo = Field(default_factory=AutoReplyInfo, description="Auto-reply information")

