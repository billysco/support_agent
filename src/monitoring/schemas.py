"""
Pydantic schemas for monitoring log events, AI-generated issues, and alerts.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of log events in the monitoring system."""
    api = "api"
    database = "database"
    frontend = "frontend"
    infrastructure = "infrastructure"


class LogEvent(BaseModel):
    """A single log event from the monitoring system."""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    event_type: EventType = Field(..., description="Type of event")
    service_name: str = Field(..., description="Name of the service generating the event")
    region: str = Field(..., description="Geographic region or cloud region")
    customer_id: Optional[str] = Field(default=None, description="Customer ID if applicable")
    severity: str = Field(..., description="Event severity: info, warning, error, critical")
    message: str = Field(..., description="Human-readable event message")
    metrics: dict = Field(default_factory=dict, description="Event-specific metrics (latency, response time, etc.)")
    flagged: bool = Field(default=False, description="Whether event exceeded thresholds")
    critical: bool = Field(default=False, description="Whether event is critically flagged")


class AIIssue(BaseModel):
    """An AI-generated issue from flagged events."""
    issue_id: str = Field(..., description="Unique issue identifier")
    created_at: datetime = Field(default_factory=datetime.now, description="Issue creation timestamp")
    title: str = Field(..., description="Issue title")
    status: str = Field(default="active", description="Issue status: active, investigating, resolved")
    severity: str = Field(..., description="Issue severity: low, medium, high, critical")
    affected_services: list[str] = Field(default_factory=list, description="List of affected services")
    affected_regions: list[str] = Field(default_factory=list, description="List of affected regions")
    description: str = Field(..., description="Detailed issue description")
    workaround: Optional[str] = Field(default=None, description="Suggested workaround if available")
    ai_generated: bool = Field(default=True, description="Whether this issue was AI-generated")
    related_events: list[str] = Field(default_factory=list, description="List of related event IDs")
    kb_document_id: Optional[str] = Field(default=None, description="ID of the KB document created for this issue")


class AIAlert(BaseModel):
    """An AI-generated alert or notification."""
    alert_id: str = Field(..., description="Unique alert identifier")
    created_at: datetime = Field(default_factory=datetime.now, description="Alert creation timestamp")
    alert_type: str = Field(..., description="Alert type: engineering, customer")
    subject: str = Field(..., description="Alert subject line")
    body: str = Field(..., description="Alert body content")
    affected_service: str = Field(..., description="Primary affected service")
    related_issue_id: Optional[str] = Field(default=None, description="Related issue ID if applicable")
    related_ticket_id: Optional[str] = Field(default=None, description="Related support ticket ID if created")
