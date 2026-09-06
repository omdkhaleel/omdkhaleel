"""Runtime configuration loaded from environment variables / .env file.

Nothing secret ever reaches the frontend: the browser only ever talks to
our own backend, and any API key stays server-side.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    _project_root = Path(__file__).resolve().parents[2]
    load_dotenv(_project_root / ".env")
except ImportError:  # pragma: no cover - dotenv is a listed dependency
    pass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


SEARCH_PROVIDER = os.environ.get("SEARCH_PROVIDER", "duckduckgo").strip().lower()
SEARCH_PROVIDER_API_KEY = os.environ.get("SEARCH_PROVIDER_API_KEY", "").strip()
REQUEST_TIMEOUT_SECONDS = _int_env("REQUEST_TIMEOUT_SECONDS", 10)
MAX_RESULTS_PER_SOURCE = _int_env("MAX_RESULTS_PER_SOURCE", 20)
MAX_CONCURRENT_FETCHES = _int_env("MAX_CONCURRENT_FETCHES", 5)
MAX_QUERIES_PER_SEARCH = _int_env("MAX_QUERIES_PER_SEARCH", 12)
MAX_STORED_SESSIONS = _int_env("MAX_STORED_SESSIONS", 100)
DEFAULT_PORT = _int_env("PORT", 8000)
USER_AGENT = os.environ.get(
    "SEARCH_USER_AGENT",
    "RealTimePropertyFinder/1.0 (+local personal research assistant)",
)
