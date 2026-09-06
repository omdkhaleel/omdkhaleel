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
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import httpx
from bs4 import BeautifulSoup

from .. import config
from ..logging_config import logger
from .base import SearchHit, SearchProvider

_ENDPOINT = "https://html.duckduckgo.com/html/"
_MIN_DELAY_SECONDS = 0.6


def _resolve_result_url(href: str) -> Optional[str]:
    """DuckDuckGo's HTML results page never hands back the target URL
    directly — every result link is a same-site redirect of the form
    ``//duckduckgo.com/l/?uddg=<url-encoded target>&rut=...``. Unwrap that
    so the pipeline gets the real listing/portal URL instead of a
    DuckDuckGo link it can never fetch a property page from.
    """
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com"):
        if parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            return unquote(target) if target else None
        # Any other duckduckgo.com link (ad tracking, internal nav, etc.)
        # is DDG's own chrome, never an actual result.
        return None
    return href


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
                    async with httpx.AsyncClient(
                        timeout=config.REQUEST_TIMEOUT_SECONDS, follow_redirects=True
                    ) as client:
                        response = await client.get(
                            f"{_ENDPOINT}?{urlencode(params)}", headers=headers
                        )
                    if response.status_code == 200:
                        hits = self._parse(response.text, num_results)
                        if not hits:
                            logger.info(
                                "DuckDuckGo returned 200 but no parseable results for query %r "
                                "(page may be a bot-check interstitial or markup has changed)",
                                query,
                            )
                        return hits
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
        anchors = soup.select("a.result__a")
        if not anchors:
            # DuckDuckGo has changed this markup before; fall back to any
            # outbound link that isn't DuckDuckGo's own chrome so a purely
            # cosmetic markup change doesn't silently zero out every search.
            anchors = [
                a
                for a in soup.select("div.results a[href]")
                if "duckduckgo.com" not in (a.get("href") or "") or "/l/?" in (a.get("href") or "")
            ]
        for anchor in anchors:
            resolved = _resolve_result_url(anchor.get("href"))
            if not resolved or not resolved.startswith("http"):
                continue
            title = anchor.get_text(strip=True)
            snippet_tag = anchor.find_parent("div", class_="result")
            snippet = ""
            if snippet_tag:
                snippet_el = snippet_tag.select_one(".result__snippet")
                if snippet_el:
                    snippet = snippet_el.get_text(strip=True)
            hits.append(SearchHit(url=resolved, title=title, snippet=snippet))
            if len(hits) >= num_results:
                break
        return hits
