# Full SDD workflow

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Requirements
<!-- chat-id: 64abb137-de1d-4245-9a5f-b8d121a0b417 -->

Create a Product Requirements Document (PRD) based on the feature description.

1. Review existing codebase to understand current architecture and patterns
2. Analyze the feature definition and identify unclear aspects
3. Ask the user for clarifications on aspects that significantly impact scope or user experience
4. Make reasonable decisions for minor details based on context and conventions
5. If user can't clarify, make a decision, state the assumption, and continue

Save the PRD to `{@artifacts_path}/requirements.md`.

### [x] Step: Technical Specification
<!-- chat-id: df315a88-7415-4d25-af32-29c616ca6719 -->

Create a technical specification based on the PRD in `{@artifacts_path}/requirements.md`.

1. Review existing codebase architecture and identify reusable components
2. Define the implementation approach

Save to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach referencing existing code patterns
- Source code structure changes
- Data model / API / interface changes
- Delivery phases (incremental, testable milestones)
- Verification approach using project lint/test commands

### [x] Step: Planning
<!-- chat-id: 0e0270c6-f4a7-4701-a904-10a15c83dcd7 -->

Create a detailed implementation plan based on `{@artifacts_path}/spec.md`.

1. Break down the work into concrete tasks
2. Each task should reference relevant contracts and include verification steps
3. Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function) or too broad (entire feature).

If the feature is trivial and doesn't warrant full specification, update this workflow to remove unnecessary steps and explain the reasoning to the user.

Save to `{@artifacts_path}/plan.md`.

---

## Implementation Tasks

### [ ] Step: Backend Data Models and Schemas

Create the monitoring data models as defined in spec.md section 2.1.4.

**Files to create**:
- `src/monitoring/__init__.py` - Module exports
- `src/monitoring/schemas.py` - Data models (LogEvent, AIIssue, AIAlert, EventType enum)

**Implementation details**:
- Define `EventType` enum with values: api, database, frontend, infrastructure
- Implement `LogEvent` with all metadata fields (event_id, timestamp, event_type, service_name, region, customer_id, severity, message, metrics, flagged, critical)
- Implement `AIIssue` with issue tracking fields (issue_id, created_at, title, status, severity, affected_services, affected_regions, description, workaround, ai_generated, related_events, kb_document_id)
- Implement `AIAlert` with alert fields (alert_id, created_at, alert_type, subject, body, affected_service, related_issue_id, related_ticket_id)
- Use Pydantic BaseModel for all schemas
- Ensure datetime fields use proper datetime types

**Verification**:
- Import schemas successfully
- Instantiate test objects with sample data
- Validate Pydantic validation works (e.g., invalid enum values raise errors)

### [ ] Step: Threshold Checker Implementation

Implement threshold monitoring system as defined in spec.md section 2.1.2.

**Files to create**:
- `src/monitoring/threshold_checker.py` - ThresholdChecker class

**Implementation details**:
- Create `ThresholdChecker` class with rolling baseline tracking
- Implement hard-coded thresholds from requirements.md FR-2 (API latency >500ms, DB query >300ms, etc.)
- Track per-service rolling baseline (last 100 events)
- Implement `check_event(event: LogEvent) -> ThresholdResult` method
- Flag single threshold exceed as "flagged", 3 consecutive as "critical"
- Return structured result with severity, threshold exceeded, baseline comparison

**Verification**:
- Test normal event → not flagged
- Test single anomalous event → flagged=True, critical=False
- Test 3 consecutive anomalous events → flagged=True, critical=True
- Verify rolling baseline tracks per service correctly

### [ ] Step: Event Generator Implementation

Implement log event generator as defined in spec.md section 2.1.1.

**Files to create**:
- `src/monitoring/event_generator.py` - LogEventGenerator class

**Implementation details**:
- Create `LogEventGenerator` class with threading support
- Implement background thread that generates ~30 events/min (~2s interval)
- Generate realistic event data for all 4 types (api, database, frontend, infrastructure)
- Use 85% normal / 15% anomalous distribution
- Implement thread-safe start/stop methods using threading.Lock
- Maintain buffer of last 500 events
- Generate realistic metadata (regions, customer IDs, service names, metrics)
- Create cascading failure patterns for realistic anomalies

**Event generation details**:
- API: latency 50-800ms, status codes 200/201/400/500, realistic endpoints
- Database: query times 10-500ms, connection pool 5-50
- Frontend: page loads 500-8000ms, JS errors with traces
- Infrastructure: CPU 20-95%, memory 40-98%, disk I/O 10-500MB/s

**Verification**:
- Start generator → verify thread starts
- Verify ~30 events/min generation rate
- Stop generator → verify thread stops gracefully
- Check event distribution: ~85% normal, ~15% anomalous
- Verify all 4 event types generated
- Test thread safety with rapid start/stop

### [ ] Step: Monitoring API Endpoints

Add monitoring API endpoints to server as defined in spec.md section 2.1.6.

**Files to modify**:
- `src/server.py` - Add monitoring endpoints and global state

**Implementation details**:
- Add global monitoring_state dict (running, generator, ai_agent, events, issues, alerts)
- Implement endpoints:
  - POST `/api/monitoring/start` - Initialize and start generator
  - POST `/api/monitoring/stop` - Stop generator gracefully
  - GET `/api/monitoring/status` - Return running status and event count
  - GET `/api/monitoring/events?limit=50` - Return recent events sorted by timestamp desc
  - GET `/api/monitoring/flagged` - Return only flagged/critical events
  - GET `/api/monitoring/ai-actions` - Return issues and alerts
  - POST `/api/monitoring/clear` - Clear events, issues, alerts
- Add thread safety with locks for shared state access
- Implement error handling (400 for invalid state, 500 for failures)

**Verification**:
- Test all endpoints with curl/httpie
- Verify start → status shows running=true
- Verify events endpoint returns events with correct limit
- Verify stop → generator thread stops
- Test rapid start/stop/clear for race conditions

### [ ] Step: KB Collection for Monitoring

Add monitoring issues collection to KB system as defined in spec.md section 2.1.5.

**Files to modify**:
- `src/kb/collections.py` - Add MONITORING_ISSUES collection enum

**Implementation details**:
- Add `MONITORING_ISSUES = "monitoring_issues"` to KBCollection enum
- Ensure collection is created on initialization
- Verify collection supports required metadata fields (issue_id, ai_generated, status, severity, created_at)

**Verification**:
- Start server → verify monitoring_issues collection created in ChromaDB
- Test adding a document to collection
- Test similarity search on collection

### [ ] Step: AI Agent Implementation

Implement AI agent for event analysis as defined in spec.md section 2.1.3.

**Files to create**:
- `src/monitoring/ai_agent.py` - MonitoringAIAgent class

**Implementation details**:
- Create `MonitoringAIAgent` class accepting LLM client and KB retriever
- Implement `analyze_flagged_event(event, recent_events)` method
- Build context from last 10 flagged events for same service/region
- Create LLM prompts for:
  1. Event analysis (severity, root cause, affected scope)
  2. KB entry generation (title, description, workaround)
  3. Engineering alert email drafting
  4. Customer notification drafting (critical only)
- Implement KB similarity search for duplicate detection (>0.85 threshold)
- Store AI-generated issues in ChromaDB MONITORING_ISSUES collection
- Integrate with ticket system for critical issues (call process_ticket)
- Handle LLM failures gracefully with mock responses
- Cache processed issues to avoid duplicates

**Verification**:
- Test analyze_flagged_event with sample event → verify AIIssue created
- Verify KB entry added to ChromaDB
- Test critical event → verify ticket created with MON-{timestamp}-{service} ID
- Test LLM failure → verify graceful degradation with mock response
- Verify duplicate detection prevents duplicate issues

### [ ] Step: Integrate AI Agent with Event Generator

Connect AI agent to event generator for automatic flagged event processing.

**Files to modify**:
- `src/monitoring/event_generator.py` - Add AI agent integration
- `src/server.py` - Initialize AI agent with generator

**Implementation details**:
- Add AI agent callback to generator for flagged events
- When event flagged by ThresholdChecker, queue for AI analysis
- Process AI analysis asynchronously (don't block event generation)
- Store resulting AIIssue and AIAlert objects in monitoring_state
- Handle errors without stopping event generation

**Verification**:
- Start monitoring → trigger flagged event → verify AI issue created
- Verify AI processing doesn't block event generation
- Test LLM failure → events continue generating
- Verify issues and alerts appear in /api/monitoring/ai-actions endpoint

### [ ] Step: Frontend Navigation and Structure

Add monitoring navigation item and view structure as defined in spec.md section 2.2.

**Files to modify**:
- `web/index.html` - Add navigation item and monitoring view structure

**Implementation details**:
- Add "Monitoring" nav button between "New Ticket" and "Knowledge Base" with activity/pulse icon
- Create `viewMonitoring` section with:
  - Header with title, subtitle, controls (Clear Logs, Start/Stop toggle)
  - Collapsible threshold info panel
  - Two-column layout: log stream (60%) and AI actions (40%)
  - Event list container for auto-scrolling cards
  - AI actions with tabs (Issues & KB, Alerts)
  - Empty state messages
- Follow existing HTML structure patterns from other views

**Verification**:
- Visual review: navigation item appears
- Click navigation → monitoring view displays
- Check layout: 60/40 split, header, controls
- Verify structure matches spec mockup

### [ ] Step: Frontend Event Stream Logic

Implement event stream display and auto-scrolling as defined in spec.md section 2.2.3.

**Files to modify**:
- `web/app.js` - Add monitoring view logic

**Implementation details**:
- Create `monitoringState` object (running, events, issues, alerts, pollInterval, autoScroll)
- Implement `initMonitoringView()` - setup event listeners
- Implement `toggleMonitoring()` - POST to start/stop, update UI state, start/stop polling
- Implement `pollMonitoringData()` - fetch events and AI actions every 2s when running
- Implement `renderEventCard(event)` - create event card DOM element with:
  - Service type icon and name
  - Timestamp, key metric, region
  - Customer ID (if present)
  - Flagged/critical badges
- Implement `updateEventList(newEvents)` - prepend new events, keep last 50, smooth scroll
- Add auto-scroll management with smooth transitions

**Verification**:
- Click Start → verify POST to /api/monitoring/start
- Verify polling starts (check Network tab)
- New events appear at top of list
- Auto-scroll works smoothly
- Stop → polling stops
- Verify last 50 events maintained (older events removed)

### [ ] Step: Frontend AI Actions Display

Implement AI issues and alerts display as defined in spec.md section 2.2.3.

**Files to modify**:
- `web/app.js` - Add AI actions rendering logic

**Implementation details**:
- Implement tab switching between "Issues & KB" and "Alerts"
- Implement `renderAIIssue(issue)` - create issue card with:
  - Title, status badge, severity badge, "AI Generated" badge
  - Affected services, timestamp
  - Expandable details (description, workaround, related events)
- Implement `renderAlert(alert)` - create alert card with:
  - Alert type badge (Engineering/Customer)
  - Subject, timestamp, affected service
  - Expandable email body
  - Related ticket ID (if customer notice)
- Render issues/alerts from polling data
- Handle empty states (no issues/alerts yet)

**Verification**:
- Trigger flagged event → AI issue appears in Issues & KB tab
- Click to expand issue → details display
- Switch to Alerts tab → engineering/customer emails display
- Expand alert → full email body shows
- Visual review: badges, formatting match spec

### [ ] Step: Frontend Styling

Add CSS styling for monitoring view as defined in spec.md section 2.2.4.

**Files to modify**:
- `web/style.css` - Add monitoring-specific styles

**Implementation details**:
- Add `.monitoring-layout` with 60/40 grid layout
- Style `.event-card` with severity color coding (info/warning/error/critical)
- Style `.event-badge.flagged` (yellow/warning color)
- Style `.event-badge.critical` (red/danger color with pulse animation)
- Add pulse keyframe animation for critical events
- Style `.ai-issue-card` and `.alert-card` with expand/collapse
- Style threshold info panel (collapsible)
- Style status indicator (green pulse for running, gray for stopped)
- Follow existing design system (CSS variables, DM Sans font, consistent spacing)

**Verification**:
- Visual review: layout matches spec (60/40 split)
- Event cards styled correctly with color coding
- Critical badges pulse animation works
- AI cards expand/collapse smoothly
- Threshold panel toggles properly
- Status indicator updates correctly (green pulse when running)
- Responsive design works on different screen sizes

### [ ] Step: Clear Logs and Controls

Implement remaining controls functionality.

**Files to modify**:
- `web/app.js` - Add clear logs and threshold toggle
- `web/index.html` - Ensure controls properly wired

**Implementation details**:
- Implement "Clear Logs" button → POST to `/api/monitoring/clear`
- Clear frontend state (events, issues, alerts)
- Update UI to empty state
- Implement threshold info panel toggle (expand/collapse)
- Update status indicator based on running state
- Add event count display

**Verification**:
- Click Clear Logs → events/issues/alerts cleared
- Threshold panel toggle works
- Status indicator shows correct state
- Event count updates in real-time

### [ ] Step: Integration Testing and Polish

Perform end-to-end testing and final polish.

**Tasks**:
- Test complete flow: start → events → flagging → AI actions → ticket creation
- Test edge cases: stop/start rapidly, clear logs, LLM unavailable
- Verify AI issues appear in main KB search
- Check performance with 500 events (no lag)
- Add error handling for network failures
- Optimize polling (handle server errors gracefully)
- Test integration with existing ticket system
- Verify KB collection integration
- Add any missing animations/transitions
- Final visual polish and responsive design check

**Manual test cases**:
1. Basic flow: Start → See events → Stop → Verify count
2. Flagging: Trigger anomalous event → See flagged badge
3. AI analysis: Wait for flagged event → Verify issue created → Check KB
4. Critical path: Trigger 3 consecutive critical → Verify ticket created
5. UI updates: Verify real-time updates without manual refresh
6. Clear logs: Clear data → Verify empty state
7. LLM failure: Disconnect/mock LLM error → Verify graceful degradation

**Verification**:
- All manual test cases pass
- Demo runs continuously without errors
- AI outputs are coherent and relevant
- Visual impact: clear monitoring and AI action visibility
- Navigation and styling consistent with existing app
- Performance: smooth scrolling, no lag
