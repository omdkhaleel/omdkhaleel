"""Console logging helpers that mirror the pipeline stages.

Never pass secrets (API keys, tokens) into any of these helpers.
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger("property_finder")

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


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
