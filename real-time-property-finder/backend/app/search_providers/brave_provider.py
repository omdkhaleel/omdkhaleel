"""Optional Brave Search API provider.

An officially sanctioned, API-key-based alternative to the free
DuckDuckGo HTML scrape. Useful when DuckDuckGo is blocking/rate-limiting
a given network (increasingly common for any automated client hitting
its HTML results page) — Brave's API has a free tier and returns
results directly as JSON, no redirect-link unwrapping or bot-check
guessing required. Only used when SEARCH_PROVIDER=brave and
SEARCH_PROVIDER_API_KEY is set.
"""
from __future__ import annotations

from typing import List

import httpx

from .. import config
from ..logging_config import log_provider_query_outcome, logger
from .base import SearchHit, SearchProvider

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, num_results: int) -> List[SearchHit]:
        if not self._api_key:
            logger.warning("Brave provider selected but no API key configured")
            return []
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        params = {"q": query, "count": str(min(num_results, 20))}
        try:
            async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(_ENDPOINT, headers=headers, params=params)
            if response.status_code != 200:
                log_provider_query_outcome(query, f"Brave API returned HTTP {response.status_code}")
                return []
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log_provider_query_outcome(query, f"Brave API request failed: {exc!r}")
            return []

        hits: List[SearchHit] = []
        for item in data.get("web", {}).get("results", []):
            hits.append(
                SearchHit(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                )
            )
        log_provider_query_outcome(query, f"{len(hits)} result(s)")
        return hits
