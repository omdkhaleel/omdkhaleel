"""Picks the configured SearchProvider without the rest of the app caring
which one it is."""
from __future__ import annotations

from .. import config
from ..logging_config import logger
from .base import SearchProvider
from .bing_provider import BingProvider
from .brave_provider import BraveProvider
from .duckduckgo_provider import DuckDuckGoProvider


def get_search_provider() -> SearchProvider:
    provider_name = config.SEARCH_PROVIDER
    if provider_name == "bing":
        if config.SEARCH_PROVIDER_API_KEY:
            return BingProvider(config.SEARCH_PROVIDER_API_KEY)
        logger.warning("SEARCH_PROVIDER=bing but no API key set; falling back to duckduckgo")
    elif provider_name == "brave":
        if config.SEARCH_PROVIDER_API_KEY:
            return BraveProvider(config.SEARCH_PROVIDER_API_KEY)
        logger.warning("SEARCH_PROVIDER=brave but no API key set; falling back to duckduckgo")
    return DuckDuckGoProvider()
