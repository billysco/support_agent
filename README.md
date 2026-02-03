# Customer Support Case Triage and Reply Draft System

An AI-powered system that automatically classifies support tickets, extracts key fields, routes to appropriate teams, and drafts customer replies with knowledge base citations.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run web server (mock mode - no API key needed)
python -m src.server
# Open http://localhost:8000

# Run with LLM
set OPENAI_API_KEY=sk-your-key-here  # Windows
export OPENAI_API_KEY=sk-your-key-here  # Linux/Mac
python -m src.server
```

## Features

- **Automatic Triage**: Classifies urgency (P0-P3), category, and sentiment
- **Field Extraction**: Extracts environment, region, error messages, order IDs, etc.
- **Smart Routing**: Routes to appropriate team with SLA calculation
- **Reply Drafting**: Generates customer-friendly replies with KB citations
- **Guardrails**: Checks for hallucinations and policy compliance
- **Mock Mode**: Works without API key for reliable demos

## Architecture

```
                    ┌─────────────────┐
                    │  Support Ticket │
                    │     (JSON)      │
                    └────────┬────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│                    PIPELINE                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Stage 1    │  │   Stage 2    │  │   Stage 3    │  │
│  │   Triage +   │─▶│     KB       │─▶│   Routing    │  │
│  │  Extraction  │  │  Retrieval   │  │   (Rules)    │  │
│  │   (LLM)      │  │  (ChromaDB)  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                                    │          │
│         ▼                                    ▼          │
│  ┌──────────────┐                   ┌──────────────┐   │
│  │   Stage 4    │                   │   Stage 5    │   │
│  │    Reply     │──────────────────▶│  Guardrail   │   │
│  │   Draft      │                   │    Check     │   │
│  │   (LLM)      │                   │   (LLM)      │   │
│  └──────────────┘                   └──────────────┘   │
└────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Pipeline Result │
                    │  (Structured)   │
                    └─────────────────┘
```

## Project Structure

```
tribe_interview/
├── src/
│   ├── __init__.py
│   ├── server.py             # FastAPI web server
│   ├── schemas.py            # Pydantic models
│   ├── llm_client.py         # LLM interface (OpenAI + Mock)
│   ├── utils.py              # Logging, redaction
│   ├── kb/
│   │   ├── indexer.py        # ChromaDB indexing
│   │   ├── retriever.py      # LangChain retrieval
│   │   └── ticket_history.py # Similar ticket detection
│   └── pipeline/
│       ├── triage.py         # Classification + extraction
│       ├── routing.py        # Team routing + SLA
│       ├── reply.py          # Reply generation
│       └── guardrail.py      # Safety checks
├── web/
│   ├── index.html            # Frontend UI
│   ├── style.css             # Styling
│   └── app.js                # Frontend logic
├── kb/                       # Knowledge base (8 docs)
├── data/
│   └── sample_tickets.json   # 3 sample tickets
├── tests/
│   ├── test_pipeline.py      # Integration tests
│   └── test_kb.py            # KB tests
├── requirements.txt
└── README.md
```

## Sample Tickets

The demo includes 3 tickets that demonstrate different routing:

| Ticket | Type | Urgency | Team | Escalation |
|--------|------|---------|------|------------|
| TKT-2024-001 | Enterprise Outage | P0 | Engineering | Yes |
| TKT-2024-002 | Billing Dispute | P2 | Billing | No |
| TKT-2024-003 | Bug Report | P3 | Engineering | No |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/process` | POST | Process a ticket |
| `/api/samples` | GET | Get sample tickets |
| `/api/mode` | GET | Get processing mode |
| `/health` | GET | Health check |

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | None (mock mode) |
| `OPENAI_BASE_URL` | Custom API endpoint | OpenAI default |

## Mock Mode

When `OPENAI_API_KEY` is not set, the system runs in mock mode:

- **LLM**: Deterministic keyword-based classification
- **Embeddings**: LangChain FakeEmbeddings (384-dim)
- **Results**: Consistent across runs for reliable demos

## Output Schema

```json
{
  "ticket_id": "TKT-2024-001",
  "triage": {
    "urgency": "P0",
    "category": "outage",
    "sentiment": "negative",
    "confidence": 0.95,
    "rationale": "Customer reports production system issues..."
  },
  "extracted_fields": {
    "environment": "production",
    "region": "us-east-1",
    "error_message": "HTTP 500 Internal Server Error",
    "missing_fields": ["reproduction_steps"]
  },
  "routing": {
    "team": "engineering",
    "sla_hours": 1,
    "escalation": true,
    "reasoning": "Routed to engineering due to outage..."
  },
  "kb_hits": [
    {
      "doc_name": "outage_procedures",
      "section": "immediate-response",
      "passage": "For P0 outages, immediately...",
      "relevance_score": 0.89
    }
  ],
  "reply": {
    "customer_reply": "Dear Sarah, Thank you for reporting...",
    "internal_notes": "ESCALATED: P0 outage for enterprise...",
    "citations": ["[KB:outage_procedures#immediate-response]"]
  },
  "guardrail_status": {
    "passed": true,
    "issues_found": [],
    "fixes_applied": []
  },
  "processing_mode": "mock"
}
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_pipeline.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Design Decisions

### Why ChromaDB + LangChain?

- **ChromaDB**: Lightweight, local vector store with no external dependencies
- **LangChain**: Provides clean abstractions for document loading, splitting, and retrieval
- **FakeEmbeddings**: Enables offline demo mode without API calls

### Why Rule-Based Routing?

- **Predictable**: SLA and team assignment follow clear business rules
- **Fast**: No LLM latency for routing decisions
- **Auditable**: Easy to explain why a ticket was routed a certain way

### Why Separate LLM Calls?

- **Triage + Extraction**: Combined for efficiency (1 call)
- **Reply Draft**: Separate to include KB context (1 call)
- **Guardrail**: Optional, can be skipped for speed (1 call)

Total: 2-3 LLM calls per ticket

## Productionization Plan

### Latency Optimization

| Current | Production |
|---------|------------|
| Sequential LLM calls | Parallel where possible |
| Full KB search | Cached common queries |
| Sync processing | Async with streaming |

**Target**: <3s end-to-end (currently ~5-8s with real LLM)

### Reliability

| Current | Production |
|---------|------------|
| Mock fallback | Circuit breakers |
| Single provider | Multi-provider failover |
| In-memory state | Persistent queue |

**Target**: 99.9% availability

### Cost Optimization

| Current | Production |
|---------|------------|
| GPT-4o-mini | Smaller models for triage |
| Per-request embeddings | Cached embeddings |
| Full context | Truncated context |

**Target**: <$0.01 per ticket

### Safety Enhancements

| Current | Production |
|---------|------------|
| Basic guardrails | PII detection |
| Mock mode | Human-in-the-loop for P0 |
| Console logging | Audit trail |

**Target**: Zero hallucinated commitments

### Scale

| Current | Production |
|---------|------------|
| Single process | Kubernetes deployment |
| Local ChromaDB | Managed vector DB |
| File-based KB | CMS integration |

**Target**: 1000+ tickets/minute

## Demo Script

> "This is a Customer Support Triage system that automatically classifies tickets, extracts key fields, routes to the right team, and drafts replies with knowledge base citations."

```bash
python -m src.server
```

> "Load a sample ticket, click Process, and see triage, routing, and the draft reply with KB citations."

> "Three tickets processed - the enterprise outage gets P0 with escalation, billing goes to billing team, and the bug report routes to engineering with low priority."

> "Works in mock mode without an API key - the demo never fails."

## License

MIT

