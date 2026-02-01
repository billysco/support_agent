# Implementation Plan for Remaining Gaps

This document outlines the implementation plan for addressing the identified gaps in the support system.

---

## Summary of Changes Made

### KB Collection Separation (Completed)

The knowledge base has been restructured into **3 separate collections**:

| Collection | Purpose | Location |
|------------|---------|----------|
| `support_kb` | Static KB docs (procedures, policies, guides) | `data/chroma_db/` |
| `previous_queries` | Processed tickets for auto-reply | `data/previous_queries/` |
| `status_updates` | System status, outages, announcements | `data/status_updates/` |

**New files created:**
- `src/kb/collections.py` - Collection definitions and configuration
- `src/kb/status_store.py` - Status update storage and retrieval

**Updated files:**
- `src/kb/indexer.py` - Uses collection enum for paths
- `src/kb/retriever.py` - Uses collection enum
- `src/kb/ticket_history.py` - Renamed conceptually to PREVIOUS_QUERIES
- `src/schemas.py` - Added `StatusUpdateInfo` and `status_updates` to `PipelineResult`
- `src/server.py` - Added status store integration and API endpoints

**New API endpoints:**
- `GET /api/status/active` - Get all active system statuses
- `GET /api/status/stats` - Get status store statistics
- `POST /api/status/search` - Search for relevant statuses
- `POST /api/admin/status` - Create a new status update
- `PUT /api/admin/status/{id}` - Update an existing status
- `GET /api/collections` - Get info about all KB collections

---

## Gap 9: Store Response in KB

### Current State
- Responses are stored in `previous_queries` collection for auto-reply matching
- Successful responses are NOT indexed in main KB for general knowledge retrieval

### Proposed Implementation

#### 9.1 Add Response Storage Endpoint
```
POST /api/admin/approved-response
```

When an agent approves a response as high-quality/reusable:
1. Store the Q&A pair in a new collection or append to `support_kb`
2. Format as a KB document with metadata (ticket category, resolution type, etc.)
3. Make it searchable for future similar queries

#### 9.2 Schema Changes

Add to `schemas.py`:
```python
class ApprovedResponse(BaseModel):
    """An approved response to add to the KB."""
    ticket_id: str
    question_summary: str  # Generalized version of the question
    response: str          # The approved response
    category: Category
    tags: list[str]        # Searchable tags
    approved_by: str       # Agent ID
    approved_at: datetime
```

#### 9.3 Storage Logic

In `src/kb/indexer.py`, add:
```python
def add_approved_response(
    response: ApprovedResponse,
    persist_dir: Path
) -> None:
    """Add an approved response to the support_kb collection."""
    # Create document from response
    doc = Document(
        page_content=f"Q: {response.question_summary}\n\nA: {response.response}",
        metadata={
            "source": "approved_responses",
            "section": response.category.value,
            "ticket_id": response.ticket_id,
            "tags": ",".join(response.tags),
            "approved_by": response.approved_by,
            "approved_at": response.approved_at.isoformat()
        }
    )
    # Add to vectorstore
    vectorstore.add_documents([doc])
```

#### 9.4 Server Integration

Add endpoint in `server.py`:
```python
@app.post("/api/admin/approved-response")
async def add_approved_response_api(data: dict):
    # Validate
    # Create ApprovedResponse
    # Call add_approved_response()
    # Return success
```

#### 9.5 Automatic Suggestion Flow

After human approval of a low-confidence response:
1. System prompts agent: "Add this response to KB for future use?"
2. If yes, agent provides generalized question summary
3. System stores response in KB
4. Future similar tickets will find this response in KB search

---

## Gap 10: Q&A Follow-up / Conversation Threading

### Current State
- Missing fields ARE identified in `extracted_fields.missing_fields`
- Replies DO request missing info
- NO conversation threading or context preservation
- Each ticket processed independently

### Proposed Implementation

#### 10.1 Schema Changes

Add to `schemas.py`:
```python
class ConversationMessage(BaseModel):
    """A message in a conversation thread."""
    message_id: str
    timestamp: datetime
    sender: str  # "customer" or "agent" or "system"
    content: str
    extracted_fields: Optional[ExtractedFields] = None


class Conversation(BaseModel):
    """A conversation thread linked to a ticket."""
    conversation_id: str
    original_ticket_id: str
    messages: list[ConversationMessage]
    status: str  # "awaiting_customer", "awaiting_agent", "resolved"
    pending_fields: list[str]  # Fields still needed
    created_at: datetime
    updated_at: datetime
```

Update `SupportTicket`:
```python
class SupportTicket(BaseModel):
    # ... existing fields ...
    conversation_id: Optional[str] = None  # Link to existing conversation
    is_followup: bool = False
```

Update `PipelineResult`:
```python
class PipelineResult(BaseModel):
    # ... existing fields ...
    conversation_id: str  # Always present
    follow_up_requested: bool  # Whether we're waiting for more info
    pending_fields: list[str]  # What we still need
```

#### 10.2 Conversation Store

Create `src/kb/conversation_store.py`:
```python
class ConversationStore:
    """Manages conversation threads across ticket follow-ups."""

    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir / "conversations"
        self.conversations: dict[str, Conversation] = {}
        self._load_conversations()

    def create_conversation(self, ticket: SupportTicket, result: PipelineResult) -> str:
        """Create a new conversation from an initial ticket."""
        conv_id = f"conv-{ticket.ticket_id}"
        conv = Conversation(
            conversation_id=conv_id,
            original_ticket_id=ticket.ticket_id,
            messages=[
                ConversationMessage(
                    message_id=ticket.ticket_id,
                    timestamp=ticket.created_at,
                    sender="customer",
                    content=f"{ticket.subject}\n\n{ticket.body}",
                    extracted_fields=result.extracted_fields
                )
            ],
            status="awaiting_customer" if result.extracted_fields.missing_fields else "resolved",
            pending_fields=result.extracted_fields.missing_fields,
            created_at=ticket.created_at,
            updated_at=datetime.now()
        )
        self.conversations[conv_id] = conv
        self._save_conversation(conv)
        return conv_id

    def add_followup(self, conv_id: str, ticket: SupportTicket) -> Conversation:
        """Add a follow-up message to an existing conversation."""
        conv = self.conversations[conv_id]
        conv.messages.append(
            ConversationMessage(
                message_id=ticket.ticket_id,
                timestamp=ticket.created_at,
                sender="customer",
                content=ticket.body,
            )
        )
        conv.updated_at = datetime.now()
        self._save_conversation(conv)
        return conv

    def get_conversation_context(self, conv_id: str) -> str:
        """Get full conversation history for context."""
        conv = self.conversations[conv_id]
        context = []
        for msg in conv.messages:
            context.append(f"[{msg.sender}] {msg.content}")
        return "\n\n---\n\n".join(context)

    def update_pending_fields(self, conv_id: str, new_extraction: ExtractedFields):
        """Update pending fields based on new extraction."""
        conv = self.conversations[conv_id]
        # Merge extracted fields from all messages
        # Remove fields that are now filled
        # Update status if all fields received
```

#### 10.3 Pipeline Changes

Update `process_ticket()` in `server.py`:

```python
def process_ticket(
    ticket: SupportTicket,
    llm: LLMProvider,
    retriever: KBRetriever,
    ticket_history: TicketHistoryStore | None = None,
    status_store: StatusUpdateStore | None = None,
    conversation_store: ConversationStore | None = None  # NEW
) -> PipelineResult:
    # ... existing stages ...

    # Stage 0d: Check if this is a follow-up
    if ticket.conversation_id:
        # Load existing conversation
        conv = conversation_store.get_conversation(ticket.conversation_id)

        # Get full conversation context
        context = conversation_store.get_conversation_context(ticket.conversation_id)

        # Re-run extraction with full context
        triage, extracted = triage_and_extract_with_context(
            ticket,
            conversation_context=context,
            pending_fields=conv.pending_fields,
            llm=llm
        )

        # Update conversation with new extraction
        conversation_store.add_followup(ticket.conversation_id, ticket)
        conversation_store.update_pending_fields(ticket.conversation_id, extracted)

        # Check if we now have all required info
        conv = conversation_store.get_conversation(ticket.conversation_id)
        if not conv.pending_fields:
            # All info received - generate full response
            # ... continue with normal pipeline ...
        else:
            # Still missing fields - generate follow-up request
            reply = generate_followup_request(ticket, conv.pending_fields)
            # Return early with follow-up response
    else:
        # New conversation - create one
        # ... normal pipeline ...

        if result.extracted_fields.missing_fields:
            # Create conversation for follow-up tracking
            conv_id = conversation_store.create_conversation(ticket, result)
            result.conversation_id = conv_id
            result.follow_up_requested = True
            result.pending_fields = result.extracted_fields.missing_fields
```

#### 10.4 New API Endpoints

```python
@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Get conversation details and history."""

@app.get("/api/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    """Get all messages in a conversation."""

@app.post("/api/conversations/{conv_id}/followup")
async def process_followup(conv_id: str, ticket_data: dict):
    """Process a follow-up message in an existing conversation."""
```

#### 10.5 Reply Generation Updates

Update `src/pipeline/reply.py`:
```python
def generate_followup_request(
    ticket: SupportTicket,
    missing_fields: list[str],
    conversation_context: str
) -> ReplyDraft:
    """Generate a reply requesting specific missing information."""
    # Use conversation context to avoid re-asking questions
    # Generate specific, targeted follow-up questions
    # Reference what they've already provided
```

---

## Additional Gaps

### Gap: Human-in-the-Loop Workflow

#### Current State
- Low-confidence drafts flagged but no approval UI/flow
- `should_send` field exists but no approval mechanism

#### Proposed Implementation

```python
# Schema
class DraftStatus(str, Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"

class DraftReview(BaseModel):
    draft_id: str
    ticket_id: str
    original_reply: str
    edited_reply: Optional[str]
    status: DraftStatus
    reviewer_id: str
    reviewed_at: datetime
    feedback: Optional[str]

# API Endpoints
@app.get("/api/admin/pending-drafts")
async def get_pending_drafts():
    """Get all drafts awaiting review."""

@app.post("/api/admin/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, data: dict):
    """Approve a draft (optionally with edits)."""
    # If edited, use edited version
    # Mark as approved
    # Send to customer
    # Optionally add to KB

@app.post("/api/admin/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str, data: dict):
    """Reject a draft with feedback."""
    # Mark as rejected
    # Store feedback for model improvement
```

### Gap: Feedback Integration

#### Proposed Implementation

```python
class CustomerFeedback(BaseModel):
    ticket_id: str
    conversation_id: str
    rating: int  # 1-5
    feedback_text: Optional[str]
    resolution_helpful: bool
    submitted_at: datetime

# Store feedback linked to responses
# Use for:
# 1. Flagging poor responses for review
# 2. Training data for model improvement
# 3. Identifying KB gaps

@app.post("/api/feedback")
async def submit_feedback(feedback: CustomerFeedback):
    """Customer submits feedback on resolution."""
```

### Gap: Async/Queue Processing

For production deployment, consider:
1. Use Celery/Redis for async task processing
2. Implement retry logic with exponential backoff
3. Add dead-letter queue for failed processing
4. Implement batch processing for high-volume periods

---

## Implementation Priority

| Priority | Gap | Effort | Impact |
|----------|-----|--------|--------|
| 1 | Q&A Follow-up (10) | High | High - Enables multi-turn resolution |
| 2 | Human-in-the-Loop | Medium | High - Required for low-confidence cases |
| 3 | Store Response in KB (9) | Low | Medium - Improves KB over time |
| 4 | Feedback Integration | Medium | Medium - Enables continuous improvement |
| 5 | Async Processing | High | Low - Only needed at scale |

---

## Files to Create/Modify

### New Files
- `src/kb/conversation_store.py` - Conversation threading
- `src/pipeline/followup.py` - Follow-up processing logic
- `tests/test_conversations.py` - Conversation tests
- `tests/test_status_store.py` - Status store tests

### Files to Modify
- `src/schemas.py` - Add Conversation, ConversationMessage, ApprovedResponse, CustomerFeedback
- `src/server.py` - Add new endpoints
- `src/pipeline/reply.py` - Add follow-up generation
- `src/pipeline/triage.py` - Add context-aware extraction

---

## Database Considerations

For production, consider migrating from ChromaDB file storage to:
- PostgreSQL with pgvector for vector search
- Redis for conversation state caching
- Dedicated queue (RabbitMQ/SQS) for async processing

This provides:
- ACID transactions
- Better concurrent access
- Horizontal scaling
- Proper backup/recovery
