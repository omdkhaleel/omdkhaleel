"""Session-scoped, in-memory storage only.

This deliberately holds nothing durable: it exists so a client can poll
GET /api/search/{id} for the result of a search it already ran, within
the lifetime of this server process. It is capped and FIFO-evicted, and
a server restart clears it entirely. It must never be read as the source
of results for a new search — every click of Search runs the live
pipeline again from scratch.
"""
from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Optional

from .models import SearchResponse


class SearchSessionStore:
    def __init__(self, max_sessions: int = 100) -> None:
        self._sessions: "OrderedDict[str, SearchResponse]" = OrderedDict()
        self._max_sessions = max_sessions
        self._lock = Lock()

    def save(self, response: SearchResponse) -> None:
        with self._lock:
            self._sessions[response.search_id] = response
            self._sessions.move_to_end(response.search_id)
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)

    def get(self, search_id: str) -> Optional[SearchResponse]:
        with self._lock:
            return self._sessions.get(search_id)
