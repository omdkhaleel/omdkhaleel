"""FastAPI application: three endpoints, a static frontend, nothing else.

There is no property database here. POST /api/search is the only way
results ever get produced, and it always runs the live pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import SearchRequest, SearchResponse
from .orchestrator import SearchOrchestrator
from .session_store import SearchSessionStore
from . import config

app = FastAPI(title="Real-Time Property Finder", version="1.0.0")

_session_store = SearchSessionStore(max_sessions=config.MAX_STORED_SESSIONS)
_orchestrator = SearchOrchestrator()

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/api/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    response = await _orchestrator.run(req)
    _session_store.save(response)
    return response


@app.get("/api/search/{search_id}", response_model=SearchResponse)
async def get_search(search_id: str) -> SearchResponse:
    response = _session_store.get(search_id)
    if response is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown or expired search session. Run a new search.",
        )
    return response


if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "index.html")
