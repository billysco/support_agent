"""
FastAPI server for the support triage web UI.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from .schemas import SupportTicket, PipelineResult, AccountTier
from .llm_client import get_llm_client
from .kb.retriever import get_retriever
from .kb.ticket_history import get_ticket_history
from .demo import process_ticket


# Get project paths
def get_project_root() -> Path:
    return Path(__file__).parent.parent


def get_web_path() -> Path:
    return get_project_root() / "web"


def get_data_path() -> Path:
    return get_project_root() / "data"


# Initialize FastAPI app
app = FastAPI(
    title="Support Triage System",
    description="AI-powered customer support ticket triage and reply drafting",
    version="1.0.0"
)

# Global instances (lazy loaded)
_llm = None
_retriever = None
_ticket_history = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm_client()
    return _llm


def get_kb_retriever():
    global _retriever
    if _retriever is None:
        llm = get_llm()
        _retriever = get_retriever(use_mock=llm.is_mock)
    return _retriever


def get_history():
    global _ticket_history
    if _ticket_history is None:
        llm = get_llm()
        _ticket_history = get_ticket_history(use_mock=llm.is_mock)
    return _ticket_history


# API Routes
@app.get("/api/mode")
async def get_mode():
    """Get the current processing mode (mock or real)."""
    llm = get_llm()
    return {"mode": "mock" if llm.is_mock else "real"}


@app.get("/api/samples")
async def get_samples():
    """Get sample tickets for the demo."""
    samples_path = get_data_path() / "sample_tickets.json"
    
    try:
        with open(samples_path, "r", encoding="utf-8") as f:
            samples = json.load(f)
        return JSONResponse(content=samples)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Sample tickets not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid sample tickets file")


@app.post("/api/process", response_model=PipelineResult)
async def process_ticket_api(ticket_data: dict):
    """Process a support ticket through the triage pipeline."""
    try:
        # Parse datetime if string
        if isinstance(ticket_data.get("created_at"), str):
            ticket_data["created_at"] = datetime.fromisoformat(
                ticket_data["created_at"].replace("Z", "+00:00")
            )
        
        # Parse account tier if string
        if isinstance(ticket_data.get("account_tier"), str):
            ticket_data["account_tier"] = AccountTier(ticket_data["account_tier"])
        
        # Validate ticket
        ticket = SupportTicket(**ticket_data)
        
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Process ticket
    try:
        llm = get_llm()
        retriever = get_kb_retriever()
        ticket_history = get_history()
        result = process_ticket(ticket, llm, retriever, ticket_history)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.get("/api/ticket-history/stats")
async def get_ticket_history_stats():
    """Get statistics about the ticket history store."""
    try:
        history = get_history()
        return history.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/api/kb/search")
async def search_kb(search_data: dict):
    """Search the knowledge base for relevant articles."""
    query = search_data.get("query", "")
    k = search_data.get("k", 5)
    
    if not query or len(query) < 3:
        return []
    
    try:
        retriever = get_kb_retriever()
        results = retriever.search(query, k=k)
        
        # Convert to dict for JSON response
        return [
            {
                "doc_name": hit.doc_name,
                "section": hit.section,
                "passage": hit.passage,
                "relevance_score": hit.relevance_score
            }
            for hit in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


# Static file serving
@app.get("/")
async def serve_index():
    """Serve the main HTML page."""
    index_path = get_web_path() / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.get("/style.css")
async def serve_css():
    """Serve the CSS file."""
    css_path = get_web_path() / "style.css"
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS not found")
    return FileResponse(css_path, media_type="text/css")


@app.get("/app.js")
async def serve_js():
    """Serve the JavaScript file."""
    js_path = get_web_path() / "app.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript not found")
    return FileResponse(js_path, media_type="application/javascript")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the server using uvicorn."""
    import uvicorn
    
    print("\n" + "=" * 60)
    print("  SUPPORT TRIAGE SYSTEM - Web Server")
    print("=" * 60)
    print(f"\n  Starting server at http://{host}:{port}")
    print("  Press Ctrl+C to stop\n")
    
    # Pre-initialize to show mode
    llm = get_llm()
    print(f"  Mode: {'MOCK (no API key)' if llm.is_mock else 'REAL (OpenAI)'}")
    print()
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)

