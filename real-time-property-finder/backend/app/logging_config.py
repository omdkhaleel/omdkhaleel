"""Console + file logging helpers that mirror the pipeline stages.

Every message also goes to search_debug.log at the project root, in
full, with no console scrollback/word-wrap to lose lines to — that file
is what to attach/paste when diagnosing "why did this search find
nothing", rather than hand-copying from a terminal window.

Never pass secrets (API keys, tokens) into any of these helpers.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("property_finder")

if not logger.handlers:
    formatter = logging.Formatter("%(message)s")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        log_path = Path(__file__).resolve().parents[2] / "search_debug.log"
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(file_handler)
    except OSError:
        pass  # read-only filesystem or similar - console logging still works

    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_search_start(search_id: str, area: str, min_rent, max_rent, bhk: str) -> None:
    logger.info("")
    logger.info("SEARCH START [%s]", search_id)
    logger.info("Area: %s", area)
    if min_rent is not None or max_rent is not None:
        logger.info("Rent: %s-%s", min_rent if min_rent is not None else "any", max_rent if max_rent is not None else "any")
    logger.info("BHK: %s", bhk)


def log_query_count(count: int) -> None:
    logger.info("Generating %d web queries", count)


def log_source_search(source: str) -> None:
    logger.info("Searching source: %s", source)


def log_candidate_urls(count: int) -> None:
    logger.info("Found %d candidate URLs", count)


def log_fetched(count: int) -> None:
    logger.info("Fetched %d property pages", count)


def log_normalized(count: int) -> None:
    logger.info("Normalized %d listings", count)


def log_duplicates_removed(count: int) -> None:
    logger.info("Duplicates removed: %d", count)


def log_final_results(count: int) -> None:
    logger.info("Final results: %d", count)


def log_search_complete(search_id: str) -> None:
    logger.info("SEARCH COMPLETE [%s]", search_id)
    logger.info("")


def log_source_failure(source: str, reason: str) -> None:
    logger.warning("Source unavailable: %s (%s)", source, reason)


def log_provider_query_outcome(query: str, outcome: str) -> None:
    """One guaranteed line per search-provider call: query -> what happened.
    Always emitted, success or failure, so a search that finds nothing has
    a visible reason instead of silence."""
    logger.info("  query=%r -> %s", query, outcome)
