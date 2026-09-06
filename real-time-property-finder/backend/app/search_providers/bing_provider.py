"""Optional Bing Web Search API provider.

Only used when the user has configured SEARCH_PROVIDER=bing and supplied
SEARCH_PROVIDER_API_KEY in their local .env file. The key is read purely
from the environment on the server side and is never sent to, or
readable from, the browser.
"""
from __future__ import annotations

from typing import List

import httpx

from .. import config
from ..logging_config import logger
from .base import SearchHit, SearchProvider

_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


class BingProvider(SearchProvider):
    name = "bing"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, num_results: int) -> List[SearchHit]:
        if not self._api_key:
            logger.warning("Bing provider selected but no API key configured")
            return []
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        params = {"q": query, "count": str(num_results), "responseFilter": "Webpages"}
        try:
            async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(_ENDPOINT, headers=headers, params=params)
            if response.status_code != 200:
                logger.warning("Bing search returned status %s for query %r", response.status_code, query)
                return []
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Bing search failed: %s", exc)
            return []

        hits: List[SearchHit] = []
        for item in data.get("webPages", {}).get("value", []):
            hits.append(
                SearchHit(
                    url=item.get("url", ""),
                    title=item.get("name", ""),
                    snippet=item.get("snippet", ""),
                )
            )
        return hits
