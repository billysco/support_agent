# Technical Specification: AI-Powered Log Monitoring & Alerting

## 1. Technical Context

### 1.1 Technology Stack
- **Backend**: Python 3.x, FastAPI, Uvicorn
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **AI/ML**: OpenAI API (via existing `llm_client.py`)
- **Storage**: ChromaDB for KB entries, in-memory for events
- **Existing Dependencies**: pydantic, langchain, chromadb, openai

### 1.2 Existing Architecture Integration
This feature integrates with:
- **LLM Client** (`src/llm_client.py`): Reuse `get_llm_client()` for AI analysis
- **KB System** (`src/kb/`): Add AI-generated issues to ChromaDB collections
- **Ticket Pipeline** (`src/server.py`): Use `process_ticket()` for critical issues
- **UI Framework**: Follow existing navigation and styling patterns from `web/`

## 2. Implementation Approach

### 2.1 Backend Architecture

#### 2.1.1 Event Generation System
**Location**: `src/monitoring/event_generator.py`

**Design Pattern**: Background thread with controlled event rate
- Uses `threading.Thread` for non-blocking execution
- Event queue with configurable rate (30 events/min = ~2s interval)
- Thread-safe state management using `threading.Lock`
- Graceful start/stop without server restart

**Event Generation Strategy**:
```python
class LogEventGenerator:
    def __init__(self):
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._events_buffer = []  # Last 500 events
        
    def start(self):
        # Start background thread
        
    def stop(self):
        # Gracefully stop thread
        
    def _generate_event(self) -> LogEvent:
        # 85% normal, 15% anomalous distribution
        # Select random service type
        # Generate realistic metadata
```

**Event Types and Realistic Data**:
- **API Events**: Simulate REST endpoints with realistic latencies (50-800ms), status codes (200, 201, 400, 500)
- **Database Events**: Connection pool (5-50), query times (10-500ms), slow query counts
- **Frontend Events**: Page loads (500-8000ms), JS errors with stack traces, browser user agents
- **Infrastructure Events**: CPU (20-95%), memory (40-98%), disk I/O (10-500MB/s)

**Anomaly Generation**: 
- Inject threshold-exceeding values 15% of the time
- Create "cascading failures" where multiple related services show issues
- Simulate regional patterns (e.g., us-east-1 higher latency during certain periods)

#### 2.1.2 Threshold Monitoring
**Location**: `src/monitoring/threshold_checker.py`

**Design Pattern**: Stateful threshold analyzer with rolling baselines
```python
class ThresholdChecker:
    def __init__(self):
        self._baselines = {}  # {service_name: RollingBaseline}
        
    def check_event(self, event: LogEvent) -> ThresholdResult:
        # Compare against thresholds
        # Track consecutive violations for critical flagging
        # Return flagging decision
```

**Threshold Logic**:
- Maintain per-service rolling baseline (last 100 events)
- Hard-coded thresholds from FR-2 requirements
- Flag logic: Single threshold exceed = flagged, 3 consecutive = critical
- Return structured result with severity, threshold exceeded, baseline comparison

#### 2.1.3 AI Agent System
**Location**: `src/monitoring/ai_agent.py`

**Design Pattern**: Event-driven AI analyzer with KB integration
```python
class MonitoringAIAgent:
    def __init__(self, llm: OpenAIProvider, kb_retriever: KBRetriever):
        self._llm = llm
        self._kb_retriever = kb_retriever
        self._processed_issues = {}  # Cache to avoid duplicates
        
    def analyze_flagged_event(self, event: LogEvent, recent_events: list[LogEvent]) -> AIAnalysisResult:
        # Call LLM to analyze event + context
        # Search KB for similar issues
        # Determine if new issue or update to existing
        # Generate KB entry and alerts
```

**AI Processing Flow**:
1. **Context Building**: Aggregate last 10 flagged events for same service/region
2. **LLM Analysis**: Single LLM call with structured prompt:
   - Input: Event data, threshold info, recent history
   - Output: JSON with severity, root cause hypothesis, affected scope
3. **KB Search**: Query existing KB for similar issues (similarity search)
4. **Decision Logic**:
   - If similar issue exists (>0.85 similarity): Update existing
   - If new issue: Create new KB entry
5. **Content Generation**: 
   - KB entry (structured documentation)
   - Engineering alert email (technical details)
   - Customer notification (if critical, user-friendly language)

**LLM Prompts** (3 separate prompts):
- **Analysis Prompt**: "Analyze this log event anomaly..."
- **KB Entry Prompt**: "Create a technical knowledge base entry..."
- **Email Drafting Prompt**: "Draft an engineering alert email..."

#### 2.1.4 Data Models
**Location**: `src/monitoring/schemas.py`

Extend `src/schemas.py` with new models:
```python
class EventType(str, Enum):
    api = "api"
    database = "database"
    frontend = "frontend"
    infrastructure = "infrastructure"

class LogEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: EventType
    service_name: str
    region: str
    customer_id: Optional[str]
    severity: str  # info | warning | error | critical
    message: str
    metrics: dict  # Type-specific metrics
    flagged: bool = False
    critical: bool = False

class AIIssue(BaseModel):
    issue_id: str
    created_at: datetime
    title: str
    status: str  # investigating | identified | resolved
    severity: str  # critical | high | medium | low
    affected_services: list[str]
    affected_regions: list[str]
    description: str
    workaround: Optional[str]
    ai_generated: bool = True
    related_events: list[str]  # event_ids
    kb_document_id: Optional[str]  # ChromaDB document ID

class AIAlert(BaseModel):
    alert_id: str
    created_at: datetime
    alert_type: str  # engineering | customer
    subject: str
    body: str
    affected_service: str
    related_issue_id: str
    related_ticket_id: Optional[str]
```

#### 2.1.5 KB Integration
**Location**: Extend `src/kb/collections.py` and `src/kb/indexer.py`

**New Collection**: Add `MONITORING_ISSUES` to `KBCollection` enum
```python
class KBCollection(str, Enum):
    # ... existing collections
    MONITORING_ISSUES = "monitoring_issues"
```

**Storage Strategy**:
- Store AI-generated issues in dedicated ChromaDB collection
- Metadata fields: `issue_id`, `ai_generated=true`, `status`, `severity`, `created_at`
- Searchable text: Title + description + affected services
- Enable similarity search for duplicate detection

**KB Entry Format**:
```
Title: High API latency in auth-api (us-east-1)
Status: investigating
Severity: high
Affected: auth-api, us-east-1
Created: 2024-01-15T14:30:00Z

Description:
Detected sustained high latency (>500ms) in auth-api service in us-east-1 region.
Baseline: 120ms, Current: 650ms (+441%)

Impact:
- Authentication endpoints responding slowly
- Affects customers in us-east-1 region
- May cause login timeouts

Workaround:
Consider switching to backup region us-east-2 if issue persists.
```

#### 2.1.6 API Endpoints
**Location**: `src/server.py`

Add new endpoint group with state management:
```python
# Global state
monitoring_state = {
    "running": False,
    "generator": None,
    "ai_agent": None,
    "events": [],  # Last 500 events
    "issues": [],  # AI-generated issues
    "alerts": []   # AI-generated alerts
}

@app.post("/api/monitoring/start")
async def start_monitoring():
    # Initialize generator, start thread
    # Initialize AI agent
    # Return status

@app.post("/api/monitoring/stop")
async def stop_monitoring():
    # Stop generator thread gracefully
    # Return status

@app.get("/api/monitoring/status")
async def get_monitoring_status():
    # Return {"running": bool, "event_count": int}

@app.get("/api/monitoring/events")
async def get_events(limit: int = 50):
    # Return recent events sorted by timestamp desc

@app.get("/api/monitoring/flagged")
async def get_flagged_events():
    # Return only flagged/critical events

@app.get("/api/monitoring/ai-actions")
async def get_ai_actions():
    # Return {"issues": [...], "alerts": [...]}

@app.post("/api/monitoring/clear")
async def clear_monitoring_data():
    # Clear events, issues, alerts (keep KB entries)
```

**Error Handling**:
- 400 for invalid state transitions (e.g., start when already running)
- 500 for LLM failures (with graceful degradation message)
- Thread safety: Use locks when accessing shared state

### 2.2 Frontend Architecture

#### 2.2.1 Navigation Integration
**Location**: `web/index.html`

Add new navigation item between "New Ticket" and "Knowledge Base":
```html
<button class="nav-item" data-view="monitoring">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
    <span>Monitoring</span>
</button>
```

**Icon Choice**: Activity/pulse icon (represents real-time monitoring)

#### 2.2.2 Page Layout
**Location**: `web/index.html`

**Structure**:
```html
<section class="view view-monitoring" id="viewMonitoring">
    <header class="view-header">
        <div class="view-title">
            <h1>Log Monitoring</h1>
            <span class="view-subtitle">AI-powered anomaly detection</span>
        </div>
        <div class="monitoring-controls">
            <button class="btn" id="clearLogs">Clear Logs</button>
            <button class="btn btn-primary" id="toggleMonitoring">
                <span class="status-indicator"></span>
                <span class="toggle-text">Start</span>
            </button>
        </div>
    </header>
    
    <!-- Threshold Info Panel (collapsible) -->
    <div class="threshold-info" id="thresholdInfo">
        <button class="threshold-toggle">Thresholds ▼</button>
        <div class="threshold-content">
            <!-- Table from FR-2 requirements -->
        </div>
    </div>
    
    <div class="monitoring-layout">
        <!-- Left: Log Stream (60%) -->
        <div class="log-stream">
            <div class="stream-header">
                <h3>Event Stream</h3>
                <span class="event-count">0 events</span>
            </div>
            <div class="event-list" id="eventList">
                <!-- Auto-scrolling event cards -->
            </div>
        </div>
        
        <!-- Right: AI Actions (40%) -->
        <div class="ai-actions">
            <div class="action-tabs">
                <button class="action-tab active" data-tab="issues">Issues & KB</button>
                <button class="action-tab" data-tab="alerts">Alerts</button>
            </div>
            <div class="action-content">
                <div class="action-panel active" id="issuesPanel">
                    <!-- AI-generated issues list -->
                </div>
                <div class="action-panel" id="alertsPanel">
                    <!-- Email drafts list -->
                </div>
            </div>
        </div>
    </div>
</section>
```

**Event Card Template**:
```html
<div class="event-card" data-severity="{severity}">
    <div class="event-header">
        <span class="event-type-icon">{icon}</span>
        <span class="event-service">{service_name}</span>
        <span class="event-time">{timestamp}</span>
    </div>
    <div class="event-body">
        <div class="event-metric">{key_metric}: {value}</div>
        <div class="event-region">{region}</div>
        {if customer_id}<div class="event-customer">Customer: {customer_id}</div>{/if}
    </div>
    {if flagged}<div class="event-badge flagged">FLAGGED</div>{/if}
    {if critical}<div class="event-badge critical">CRITICAL</div>{/if}
</div>
```

**AI Issue Card Template**:
```html
<div class="ai-issue-card" data-status="{status}">
    <div class="issue-header">
        <h4>{title}</h4>
        <div class="issue-badges">
            <span class="badge badge-{status}">{status}</span>
            <span class="badge badge-{severity}">{severity}</span>
            <span class="badge badge-ai">AI Generated</span>
        </div>
    </div>
    <div class="issue-meta">
        <span>{affected_services.join(', ')}</span>
        <span>{created_timestamp}</span>
    </div>
    <button class="issue-expand">View Details ▼</button>
    <div class="issue-details" style="display: none;">
        <p>{description}</p>
        {if workaround}<div class="workaround"><strong>Workaround:</strong> {workaround}</div>{/if}
        <div class="related-events">{related_events.length} related events</div>
    </div>
</div>
```

**Alert Email Card Template**:
```html
<div class="alert-card" data-type="{alert_type}">
    <div class="alert-header">
        <span class="alert-type-badge">{alert_type === 'engineering' ? 'Engineering Alert' : 'Customer Notice'}</span>
        <span class="alert-time">{timestamp}</span>
    </div>
    <div class="alert-subject">{subject}</div>
    <div class="alert-service">{affected_service}</div>
    <button class="alert-expand">View Email ▼</button>
    <div class="alert-body" style="display: none;">
        <pre>{body}</pre>
        {if related_ticket_id}<div>Related Ticket: {related_ticket_id}</div>{/if}
    </div>
</div>
```

#### 2.2.3 Frontend Logic
**Location**: `web/app.js`

**State Management**:
```javascript
const monitoringState = {
    running: false,
    events: [],
    issues: [],
    alerts: [],
    pollInterval: null,
    autoScroll: true
};
```

**Key Functions**:
```javascript
// Initialize monitoring view
function initMonitoringView() {
    // Setup event listeners
    // Initialize UI state
}

// Toggle monitoring (start/stop)
async function toggleMonitoring() {
    // POST to /api/monitoring/start or /stop
    // Update UI state
    // Start/stop polling
}

// Poll for new events (when running)
async function pollMonitoringData() {
    // GET /api/monitoring/events
    // GET /api/monitoring/ai-actions
    // Update UI incrementally
}

// Render event card
function renderEventCard(event) {
    // Create DOM element from template
    // Auto-scroll to top if enabled
}

// Render AI issue/alert
function renderAIIssue(issue) { }
function renderAlert(alert) { }

// Auto-scroll management
function updateEventList(newEvents) {
    // Prepend new events
    // Remove old events (keep last 50)
    // Smooth scroll animation
}
```

**Polling Strategy**:
- Poll every 2 seconds when monitoring is running
- Fetch events + AI actions in parallel
- Incremental updates (only add new items)
- Stop polling when monitoring stopped

**Auto-scroll Behavior**:
- New events appear at top of list
- Smooth CSS transitions
- User can scroll freely (auto-scroll only for newest events)
- Visual "pulse" animation for new critical events

#### 2.2.4 Styling
**Location**: `web/style.css`

Follow existing design system:
- **Colors**: Use existing CSS variables (`--primary`, `--danger`, `--warning`, `--success`)
- **Typography**: DM Sans for UI, IBM Plex Mono for metrics
- **Spacing**: Consistent with existing cards (16px padding, 8px gaps)
- **Animations**: Subtle fade-in for new events, pulse for critical

**New CSS Classes**:
```css
.monitoring-layout {
    display: grid;
    grid-template-columns: 60% 40%;
    gap: 24px;
}

.event-card {
    /* Card styling with severity color coding */
}

.event-badge.flagged {
    background: var(--warning);
}

.event-badge.critical {
    background: var(--danger);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}
```

### 2.3 Integration Points

#### 2.3.1 Ticket System Integration
**Critical Issue Handling**: When AI agent detects critical severity:
1. Call `process_ticket()` with auto-generated ticket:
   ```python
   ticket = SupportTicket(
       ticket_id=f"MON-{int(datetime.now().timestamp())}-{event.service_name}",
       customer_name="System Monitor",
       customer_email="monitor@system.internal",
       account_tier=AccountTier.enterprise,
       product=event.service_name,
       subject=f"Critical issue: {issue.title}",
       body=f"Automated detection:\n\n{issue.description}\n\nMetrics:\n{json.dumps(event.metrics, indent=2)}"
   )
   result = process_ticket(ticket, llm, retriever, ticket_history, status_store, conversation_store)
   ```
2. Store ticket_id in AIAlert
3. Use ticket's reply draft as customer notification email
4. Display in UI with "Auto-Generated" badge

#### 2.3.2 Knowledge Base Integration
**AI Issue Storage**:
1. Create KB document in `MONITORING_ISSUES` collection
2. Metadata: `ai_generated=true`, issue details
3. Searchable from main KB search interface
4. Display with "AI Generated" badge in KB results

**KB Search for Similar Issues**:
- Before creating new issue, search KB with event description
- Threshold: 0.85 similarity for duplicate detection
- If found, update existing issue instead of creating new

## 3. Source Code Structure Changes

### 3.1 New Files
```
src/
├── monitoring/
│   ├── __init__.py           # Module exports
│   ├── schemas.py            # LogEvent, AIIssue, AIAlert models
│   ├── event_generator.py   # LogEventGenerator class
│   ├── threshold_checker.py # ThresholdChecker class
│   └── ai_agent.py          # MonitoringAIAgent class
```

### 3.2 Modified Files
```
src/
├── server.py                 # Add monitoring endpoints, global state
├── kb/
│   └── collections.py        # Add MONITORING_ISSUES collection

web/
├── index.html                # Add monitoring view + nav item
├── app.js                    # Add monitoring logic
└── style.css                 # Add monitoring styles
```

### 3.3 No New Dependencies
All required libraries already in `requirements.txt`:
- Threading: Python stdlib
- FastAPI: Existing
- ChromaDB: Existing
- OpenAI: Existing via llm_client

## 4. Data Flow

### 4.1 Event Generation Flow
```
[Generator Thread] --2s interval--> [Generate Event] --> [Check Thresholds] 
                                            |
                                            v
                                    [Flagged?] --No--> [Store Event]
                                            |
                                           Yes
                                            v
                                    [Queue for AI] --> [AI Agent] --> [Analysis]
                                                            |
                                                            v
                                            [Create/Update KB Entry]
                                            [Generate Alerts]
                                            [Create Ticket if Critical]
```

### 4.2 Frontend Data Flow
```
[Start Button] --> [POST /api/monitoring/start] --> [Backend starts generator]
                                                            |
                                                            v
[Poll Timer] --> [GET /api/monitoring/events] --> [Render Event Cards]
            --> [GET /api/monitoring/ai-actions] --> [Render Issues/Alerts]
```

### 4.3 AI Processing Flow
```
[Flagged Event] --> [Get Recent Context (10 events)]
                            |
                            v
                    [LLM: Analyze Event]
                            |
                            v
                    [KB: Search Similar Issues]
                            |
                            v
                [Duplicate?] --Yes--> [Update Existing Issue]
                            |
                           No
                            v
                    [LLM: Generate KB Entry]
                    [LLM: Draft Engineering Alert]
                    [If Critical: LLM: Draft Customer Email]
                            |
                            v
                    [Store in KB Collection]
                    [Add to Issues/Alerts Lists]
```

## 5. Delivery Phases

### Phase 1: Backend Foundation (Core Functionality)
**Goal**: Working event generation and threshold detection
- Implement `LogEvent`, `EventType` schemas
- Build `LogEventGenerator` with threading
- Implement `ThresholdChecker` with rolling baselines
- Add monitoring endpoints to `server.py`
- Manual testing with `/api/monitoring/events`

**Verification**: 
- Start monitoring, verify ~30 events/min
- Confirm 15% flagged events
- Check event variety (all 4 types represented)

### Phase 2: AI Agent Integration
**Goal**: AI analysis and KB integration
- Implement `AIIssue`, `AIAlert` schemas
- Build `MonitoringAIAgent` class
- Add `MONITORING_ISSUES` KB collection
- Implement LLM prompts for analysis, KB generation, email drafting
- Critical issue ticket creation

**Verification**:
- Trigger flagged event, verify AI issue created
- Check KB entry in ChromaDB
- Verify critical event creates ticket
- Validate LLM outputs are coherent

### Phase 3: Frontend UI
**Goal**: Complete user interface
- Add monitoring navigation item
- Build monitoring view HTML structure
- Implement event stream with auto-scroll
- Create issues/alerts panels with tabs
- Add threshold info panel
- Implement start/stop controls

**Verification**:
- Visual review: matches mockup layout
- Test start/stop functionality
- Verify auto-scroll and event display
- Check responsive layout

### Phase 4: Polish & Integration
**Goal**: Production-ready demo
- Styling refinement (animations, colors, badges)
- Error handling (LLM failures, network errors)
- Performance optimization (event buffer limits)
- KB search integration (show AI issues in main KB)
- Clear logs functionality
- Documentation comments

**Verification**:
- Run full demo: start → events → flagging → AI actions → ticket creation
- Test edge cases: stop/start, clear logs, LLM unavailable
- Performance: no lag with 500 events
- Integration: AI issues appear in KB search

## 6. Verification Approach

### 6.1 Unit Testing
Not explicitly required, but recommended for:
- `ThresholdChecker.check_event()`: Verify flagging logic
- Event generation distribution: 85/15 normal/anomalous split
- AI issue deduplication logic

### 6.2 Integration Testing
**Manual Test Cases**:
1. **Basic Flow**: Start → See events → Stop → Verify count
2. **Flagging**: Trigger anomalous event → See flagged badge
3. **AI Analysis**: Wait for flagged event → Verify issue created → Check KB
4. **Critical Path**: Trigger 3 consecutive critical → Verify ticket created
5. **UI Updates**: Verify real-time updates without manual refresh
6. **Clear Logs**: Clear data → Verify empty state

### 6.3 Demo Validation
**Success Criteria** (from PRD):
- ✓ Visual impact: Events streaming, AI taking action
- ✓ AI demonstration: Issues created, emails drafted
- ✓ Integration: Seamless navigation, consistent styling
- ✓ Reliability: Runs continuously, graceful LLM degradation

### 6.4 Commands to Run
```bash
# Start server
python -m src.server

# Verify endpoints (in separate terminal)
curl http://localhost:8000/api/monitoring/status
curl -X POST http://localhost:8000/api/monitoring/start
curl http://localhost:8000/api/monitoring/events?limit=10

# Frontend testing
# Open http://localhost:8000
# Navigate to Monitoring tab
# Click Start → Observe events → Check AI actions
```

## 7. Risk Mitigation

### 7.1 LLM Failures
**Risk**: OpenAI API unavailable or rate limited
**Mitigation**: 
- Try/except around LLM calls
- Return mock AI responses with "AI unavailable" note
- Continue event generation (don't block)

### 7.2 Performance Degradation
**Risk**: Too many events slow down UI
**Mitigation**:
- Limit buffer to 500 events (drop oldest)
- Lazy rendering (only render visible cards)
- Throttle polling to 2s intervals

### 7.3 Thread Safety
**Risk**: Race conditions in shared state
**Mitigation**:
- Use `threading.Lock()` for all state mutations
- FastAPI handles concurrent requests safely
- Test start/stop/clear rapid clicks

### 7.4 Demo Reliability
**Risk**: Random anomalies might not appear during demo
**Mitigation**:
- Seed event generator for predictable patterns
- Optional "force anomaly" button for demos
- Document recommended demo flow in README

## 8. Open Questions & Decisions

### 8.1 Resolved
- **Event persistence**: In-memory (no database needed)
- **AI model**: Use existing OpenAI client (gpt-4o-mini)
- **KB collection**: Dedicated `MONITORING_ISSUES` collection
- **Polling vs WebSockets**: Polling (simpler, no new dependencies)

### 8.2 Implementation Notes
- Use ISO datetime strings for all timestamps
- Event IDs: `EVT-{timestamp}-{random}`
- Issue IDs: `ISS-{timestamp}-{service}`
- Alert IDs: `ALR-{timestamp}-{type}`
- Ticket IDs: `MON-{timestamp}-{service}` (auto-generated)

## 9. Future Enhancements (Out of Scope)

Not implemented in this phase:
- Real log ingestion (external systems)
- Actual email sending
- User-configurable thresholds
- Historical analytics/charts
- Alert acknowledgment workflow
- Multi-user collaboration
- WebSocket real-time updates
