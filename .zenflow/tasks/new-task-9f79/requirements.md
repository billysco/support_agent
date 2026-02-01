# Product Requirements Document: AI-Powered Log Monitoring & Alerting

## Overview

Add a simulated log monitoring and alerting system that demonstrates AI agents proactively detecting issues, creating knowledge base entries, and drafting communications to both engineering teams and customers. This feature showcases AI for proactive support rather than reactive ticket handling.

## Feature Summary

A new "Monitoring" tab in the application that displays:
- **Left Panel**: Real-time log event stream with simulated metrics (latency, errors, region, customer data)
- **Right Panel**: AI agent actions with two sub-tabs:
  - **Issues & KB**: Known issues created by AI and added to knowledge base
  - **Alerts**: Email drafts for engineering team and customer notifications

The system includes:
- Data generator producing ~30 events/minute across multiple service types
- Threshold-based flagging (latency spikes, error rate increases)
- AI agent that reviews flagged events, creates KB entries, and drafts communications
- Automatic ticket creation for critical issues with customer email drafts

## User Personas

### Demo Viewer
**Goal**: See AI proactively monitoring systems and taking action  
**Needs**: Clear visualization of event stream, AI decisions, and outputs

### Engineering Manager
**Goal**: Understand how AI can assist with incident response  
**Needs**: See email summaries, known issue documentation, customer communication

## Functional Requirements

### FR-1: Log Event Data Generator

**Simulated Event Types**:
1. **API Events**: Endpoint calls with latency, status codes, customer ID
2. **Database Events**: Query performance, connection pool status
3. **Frontend Events**: Page load times, JavaScript errors
4. **Infrastructure Events**: CPU/memory usage, disk I/O

**Event Metadata** (all events):
- `timestamp`: ISO datetime
- `event_type`: api | database | frontend | infrastructure
- `service_name`: String (e.g., "auth-api", "payments-db")
- `region`: us-east-1 | us-west-2 | eu-west-1 | ap-south-1
- `customer_id`: Optional string for customer-affecting events
- `severity`: info | warning | error | critical
- `message`: Human-readable description
- `metrics`: Type-specific metrics object

**Type-Specific Metrics**:
- API: `{latency_ms, status_code, endpoint, method}`
- Database: `{query_time_ms, connection_count, slow_queries}`
- Frontend: `{load_time_ms, error_type, page_url, user_agent}`
- Infrastructure: `{cpu_percent, memory_percent, disk_io_mb}`

**Event Generation**:
- Generate ~30 events/minute (one every ~2 seconds)
- 85% normal events, 15% anomalous events
- Normal: Metrics within expected ranges
- Anomalous: Metrics exceeding thresholds (see FR-2)

**Controls**:
- Start/Stop button in UI
- Default state: Stopped

### FR-2: Threshold-Based Flagging

**Hardcoded Thresholds** (displayed in UI):

| Metric | Normal Range | Alert Threshold |
|--------|--------------|-----------------|
| API Latency | < 200ms | > 500ms (150% over) |
| API Error Rate | < 1% | > 5% (5x increase) |
| DB Query Time | < 100ms | > 300ms (200% over) |
| Frontend Load Time | < 2s | > 5s (150% over) |
| Infrastructure CPU | < 70% | > 90% |
| Infrastructure Memory | < 80% | > 95% |

**Flagging Logic**:
- Track rolling baseline (last 100 events per service)
- Flag event if threshold exceeded
- Flag critical if sustained over 3 consecutive events

### FR-3: AI Agent Review & Actions

**Triggered By**: Flagged events (threshold exceeded)

**AI Agent Tasks**:
1. **Analyze Event**: Review event + recent history (last 10 flagged events for that service)
2. **Determine Severity**: critical | high | medium | low
3. **Check for Existing Issue**: Search KB for similar issues
4. **Create/Update KB Entry** (if new or needs update):
   - Title: "High latency in auth-api (us-east-1)"
   - Status: investigating | identified | resolved
   - Affected services, regions, customers
   - Description of issue
   - Potential workaround (if known)
   - Mark as "AI-Generated"
5. **Draft Engineering Alert Email**:
   - Subject: "[ALERT] High latency detected - auth-api"
   - Summary of issue with metrics
   - Affected scope (regions, customers)
   - Recommended actions
   - Link to KB entry
6. **Create Support Ticket** (critical issues only):
   - Auto-generate support ticket using existing ticket schema
   - Draft customer notification email explaining issue and estimated resolution

**AI Decision Making**:
- Use LLM (existing `llm_client`) for analysis and drafting
- Prompt: Service context + event data + threshold info → Issue summary + KB entry + emails

### FR-4: User Interface

**Navigation**:
- Add "Monitoring" tab between "New Ticket" and "Knowledge Base"
- Icon: Activity/pulse icon
- Label: "Monitoring"

**Page Layout**:

```
┌─────────────────────────────────────────────────────────────┐
│  MONITORING                            [Start/Stop] [●]      │
├────────────────────────┬────────────────────────────────────┤
│ Log Stream (Left 60%)  │  AI Actions (Right 40%)            │
│                        │  ┌──────────────────────────────┐  │
│ [Event Cards]          │  │ [Issues & KB] [Alerts]       │  │
│ ┌──────────────────┐   │  └──────────────────────────────┘  │
│ │ API - auth-api   │   │                                    │
│ │ 12:30:45         │   │  Tab Content:                      │
│ │ Latency: 650ms   │   │  - Known issues list               │
│ │ us-east-1        │   │  - Email drafts list               │
│ │ ⚠️ FLAGGED       │   │                                    │
│ └──────────────────┘   │                                    │
│ ┌──────────────────┐   │                                    │
│ │ DB - payments-db │   │                                    │
│ │ 12:30:43         │   │                                    │
│ │ Query: 45ms      │   │                                    │
│ │ us-west-2        │   │                                    │
│ └──────────────────┘   │                                    │
└────────────────────────┴────────────────────────────────────┘
```

**Left Panel - Log Stream**:
- Auto-scrolling list of event cards (newest at top)
- Show last 50 events
- Scroll speed: Smooth, 2-second intervals between events
- Event card displays:
  - Service type icon + name
  - Timestamp
  - Key metric (latency, error rate, etc.)
  - Region
  - Badge: FLAGGED (yellow) or CRITICAL (red) when threshold exceeded
  - Customer ID (if customer-affecting)

**Right Panel - Issues & KB Tab**:
- List of AI-created known issues
- Each entry shows:
  - Issue title
  - Status badge (investigating/identified/resolved)
  - Severity badge
  - Affected services
  - Created timestamp
  - "AI Generated" badge
  - Click to expand: Full description, workaround, related events

**Right Panel - Alerts Tab**:
- List of draft emails (engineering + customer)
- Each entry shows:
  - Email type: "Engineering Alert" or "Customer Notice"
  - Subject line
  - Timestamp
  - Affected service
  - Click to expand: Full email body, related ticket ID (if customer notice)

**Threshold Display**:
- Small info panel at top showing active thresholds
- Collapsible/tooltip format

**Controls**:
- Start/Stop toggle button (top right)
- Status indicator: Running (green pulse) or Stopped (gray)
- Clear logs button (resets stream)

### FR-5: Integration with Existing System

**Knowledge Base Integration**:
- Add AI-generated issues to existing ChromaDB KB collection
- Schema addition: `ai_generated: bool` field
- KB search should include these entries
- Display "AI Generated" badge in KB view

**Ticket Creation Integration**:
- Critical issues → Call existing `process_ticket()` function
- Generate ticket with fields:
  - `ticket_id`: "MON-{timestamp}-{service}"
  - `customer_name`: "System Monitor"
  - `customer_email`: "monitor@system.internal"
  - `account_tier`: "enterprise"
  - `subject`: AI-generated summary
  - `body`: Event details + metrics
- Process through existing pipeline (triage, routing, reply)
- Store in tickets list with special badge "Auto-Generated"

**LLM Integration**:
- Use existing `get_llm_client()` from `src/llm_client.py`
- Create new prompts for:
  - Event analysis
  - KB entry generation
  - Email drafting

### FR-6: Backend API Endpoints

**New Endpoints**:

1. `POST /api/monitoring/start` - Start log generator
2. `POST /api/monitoring/stop` - Stop log generator
3. `GET /api/monitoring/status` - Get current status (running/stopped)
4. `GET /api/monitoring/events?limit=50` - Get recent events
5. `GET /api/monitoring/flagged` - Get flagged events
6. `GET /api/monitoring/ai-actions` - Get AI-created issues and alerts
7. `POST /api/monitoring/clear` - Clear event history

**Response Schemas**:
```python
class LogEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: str  # api | database | frontend | infrastructure
    service_name: str
    region: str
    customer_id: Optional[str]
    severity: str
    message: str
    metrics: dict
    flagged: bool
    critical: bool

class AIIssue(BaseModel):
    issue_id: str
    created_at: datetime
    title: str
    status: str  # investigating | identified | resolved
    severity: str
    affected_services: list[str]
    affected_regions: list[str]
    description: str
    workaround: Optional[str]
    ai_generated: bool
    related_events: list[str]  # event_ids

class AIAlert(BaseModel):
    alert_id: str
    created_at: datetime
    alert_type: str  # engineering | customer
    subject: str
    body: str
    affected_service: str
    related_issue_id: str
    related_ticket_id: Optional[str]  # if customer alert
```

## Non-Functional Requirements

### Performance
- Event generation: Consistent 30 events/min
- UI updates: No blocking, smooth scrolling
- AI processing: Process flagged events within 5 seconds

### Reliability
- Event generator runs in background thread
- AI failures don't stop event generation
- Graceful degradation to mock mode if LLM unavailable

### Demo Quality
- Events should look realistic with varied data
- AI outputs should be coherent and relevant
- System should showcase AI capabilities clearly

## Success Criteria

1. **Visual Impact**: Viewers immediately understand the system is monitoring and taking action
2. **AI Demonstration**: Clear examples of AI analyzing issues, creating documentation, and drafting communications
3. **Integration**: Seamlessly fits into existing app navigation and styling
4. **Reliability**: Demo runs continuously without errors or performance issues
5. **Educational Value**: Shows practical AI applications in support operations

## Out of Scope

- Real log ingestion from external systems
- Actual email sending
- Alert suppression/snoozing functionality
- User-configurable thresholds
- Historical analytics/dashboards
- Multi-user collaboration on alerts
- Alert acknowledgment workflow

## Open Questions

None - all clarified with user.

## Assumptions

1. Single-user demo environment (no concurrent access concerns)
2. In-memory storage acceptable for events (no persistence required)
3. Mock mode should generate deterministic anomalies for reliable demos
4. Event data doesn't need to correlate with actual ticket data in system
