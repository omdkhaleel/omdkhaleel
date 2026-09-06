"""Default, no-API-key search provider.

Uses DuckDuckGo's public HTML results page (no JavaScript, no login,
no API key needed) purely as a discovery mechanism for public listing
URLs. Requests are rate-limited, timed out, and retried a small, fixed
number of times; any failure or sign of blocking degrades this provider
to "no results for this query" rather than escalating to bypass
anything.
"""
from __future__ import annotations

import asyncio
from typing import List
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from .. import config
from ..logging_config import logger
from .base import SearchHit, SearchProvider

_ENDPOINT = "https://html.duckduckgo.com/html/"
_MIN_DELAY_SECONDS = 0.6


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(3)
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def _throttle(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._last_call + _MIN_DELAY_SECONDS - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = asyncio.get_event_loop().time()

    async def search(self, query: str, num_results: int) -> List[SearchHit]:
        await self._throttle()
        headers = {"User-Agent": config.USER_AGENT}
        params = {"q": query}
        attempts = 2
        async with self._semaphore:
            for attempt in range(1, attempts + 1):
                try:
                    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
                        response = await client.get(
                            f"{_ENDPOINT}?{urlencode(params)}", headers=headers
                        )
                    if response.status_code == 200:
                        return self._parse(response.text, num_results)
                    if response.status_code in (429, 202):
                        await asyncio.sleep(1.0 * attempt)
                        continue
                    logger.warning(
                        "DuckDuckGo search returned status %s for query %r",
                        response.status_code,
                        query,
                    )
                    return []
                except httpx.HTTPError as exc:
                    logger.warning("DuckDuckGo search failed (attempt %d): %s", attempt, exc)
                    await asyncio.sleep(0.5 * attempt)
            return []

    @staticmethod
    def _parse(html: str, num_results: int) -> List[SearchHit]:
        soup = BeautifulSoup(html, "lxml")
        hits: List[SearchHit] = []
        for anchor in soup.select("a.result__a"):
            url = anchor.get("href")
            if not url:
                continue
            title = anchor.get_text(strip=True)
            snippet_tag = anchor.find_parent("div", class_="result")
            snippet = ""
            if snippet_tag:
                snippet_el = snippet_tag.select_one(".result__snippet")
                if snippet_el:
                    snippet = snippet_el.get_text(strip=True)
            hits.append(SearchHit(url=url, title=title, snippet=snippet))
            if len(hits) >= num_results:
                break
        return hits
