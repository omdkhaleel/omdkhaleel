"""Coordinates one complete, real-time search: generate queries -> search
the web -> fetch candidate pages -> extract -> filter -> deduplicate ->
rank -> return. Every call to ``run`` performs its own fresh network
activity; nothing here is ever satisfied from a previous search.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from . import config
from .adapters import adapter_for_url
from .dedup import deduplicate
from .filters import filter_candidates
from .logging_config import (
    log_candidate_urls,
    log_duplicates_removed,
    log_final_results,
    log_fetched,
    log_normalized,
    log_query_count,
    log_search_complete,
    log_search_start,
    log_source_search,
    logger,
)
from .models import (
    PropertyRecord,
    SearchRequest,
    SearchResponse,
    SearchStatistics,
    SourceState,
    SourceStatus,
)
from .query_builder import generate_queries
from .ranking import rank
from .search_providers import SearchProvider, get_search_provider

_SOURCE_DOMAIN_NAME = {
    "housing.com": "Housing.com",
    "nobroker.in": "NoBroker",
    "magicbricks.com": "Magicbricks",
    "99acres.com": "99acres",
}


def _label_for_url(url: str) -> Optional[str]:
    for domain, label in _SOURCE_DOMAIN_NAME.items():
        if domain in url:
            return label
    return None


class SearchOrchestrator:
    def __init__(self, provider: Optional[SearchProvider] = None) -> None:
        self._provider = provider or get_search_provider()

    async def run(self, req: SearchRequest) -> SearchResponse:
        search_id = str(uuid.uuid4())
        searched_at = datetime.now(timezone.utc).isoformat()
        log_search_start(search_id, req.area, req.min_rent, req.max_rent, req.bhk.value, req.property_type.value)

        queries = generate_queries(req, max_queries=config.MAX_QUERIES_PER_SEARCH)
        log_query_count(len(queries))

        source_stats: Dict[str, SourceStatus] = {
            label: SourceStatus(name=label, state=SourceState.OK)
            for label in _SOURCE_DOMAIN_NAME.values()
        }

        candidate_urls: Dict[str, str] = {}
        for q in queries:
            domain_label = _SOURCE_DOMAIN_NAME.get(q.target_domain or "", None)
            log_source_search(domain_label or "general web search")
            if domain_label:
                source_stats[domain_label].queries_attempted += 1
            hits = await self._provider.search(q.text, config.MAX_RESULTS_PER_SOURCE)
            for hit in hits:
                if not hit.url.startswith("http"):
                    continue
                candidate_urls.setdefault(hit.url, hit.url)
                label = _label_for_url(hit.url)
                if label:
                    source_stats[label].candidates_found += 1

        urls = list(candidate_urls.values())[: config.MAX_RESULTS_PER_SOURCE * 4]
        log_candidate_urls(len(urls))

        fetch_stats, fetched_records = await self._fetch_and_extract(urls, source_stats)
        log_fetched(fetch_stats["fetch_ok"])
        log_normalized(len(fetched_records))
        logger.info(
            "Fetch/extract breakdown: %d attempted, %d fetch failed, %d excluded during "
            "extraction (blocked page/PG/commercial/error), %d became usable records",
            len(urls),
            fetch_stats["fetch_failed"],
            fetch_stats["excluded"],
            len(fetched_records),
        )

        for stat in source_stats.values():
            if stat.queries_attempted == 0:
                continue
            if stat.candidates_found == 0:
                stat.state = SourceState.UNAVAILABLE
                stat.message = "no web results returned for this source during this search"
            elif stat.listings_extracted == 0:
                stat.state = SourceState.DEGRADED
                stat.message = "candidate pages were found but none could be verified"

        filtered = filter_candidates(fetched_records, req)
        after_filtering = len(filtered)

        deduped = deduplicate(filtered)
        log_duplicates_removed(after_filtering - len(deduped))

        ranked = rank(req, deduped)
        log_final_results(len(ranked))
        log_search_complete(search_id)

        stats = SearchStatistics(
            sources_searched=sum(1 for s in source_stats.values() if s.queries_attempted > 0),
            listings_discovered=len(urls),
            after_filtering=after_filtering,
            after_deduplication=len(ranked),
        )

        return SearchResponse(
            search_id=search_id,
            searched_at=searched_at,
            request=req,
            sources=list(source_stats.values()),
            statistics=stats,
            results=ranked,
            queries_used=[q.text for q in queries],
            no_results_suggestions=[] if ranked else self._suggestions(req),
        )

    async def _fetch_and_extract(
        self, urls: List[str], source_stats: Dict[str, SourceStatus]
    ) -> tuple[Dict[str, int], List[PropertyRecord]]:
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_FETCHES)
        records: List[PropertyRecord] = []
        stats = {"fetch_ok": 0, "fetch_failed": 0, "excluded": 0}

        async def handle(client: httpx.AsyncClient, url: str) -> None:
            adapter = adapter_for_url(url)
            async with semaphore:
                outcome = await adapter.fetch(url, client)
            if not outcome.ok:
                stats["fetch_failed"] += 1
                logger.info("Could not fetch %s (%s)", url, outcome.error or outcome.status_code)
                return
            stats["fetch_ok"] += 1
            try:
                record = adapter.extract(url, outcome.html)
            except Exception as exc:
                # A single malformed page must never take down the whole search.
                stats["excluded"] += 1
                logger.warning("Extraction failed for %s: %s", url, exc)
                return
            if record is None:
                stats["excluded"] += 1
                return
            records.append(record)
            label = _label_for_url(url)
            if label:
                source_stats[label].listings_extracted += 1

        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
            await asyncio.gather(*(handle(client, u) for u in urls))
        return stats, records

    @staticmethod
    def _suggestions(req: SearchRequest) -> List[str]:
        tips = ["Try broadening the locality text, e.g. a neighbouring area or a wider zone"]
        if req.max_rent is not None:
            tips.append("Increase the maximum rent")
        if req.bhk.value != "any":
            tips.append("Consider an adjacent BHK configuration")
        if req.property_type.value != "any":
            tips.append("Broaden the property type to 'Any'")
        if req.parking.value != "any":
            tips.append("Relax the parking requirement")
        if req.furnishing.value != "any":
            tips.append("Consider a different furnishing preference")
        return tips
