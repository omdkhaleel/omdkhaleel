"""Fallback adapter for any other publicly indexed property page.

Used whenever a discovered URL doesn't belong to one of the explicitly
known portals — the same generic extraction is applied, since we cannot
hard-code selectors for sites we don't know about ahead of time.
"""
from __future__ import annotations

from urllib.parse import urlparse

from typing import Optional

from ..models import PropertyRecord
from .base import GenericExtractionMixin, PortalAdapter


class GenericPropertyAdapter(GenericExtractionMixin, PortalAdapter):
    source_name = "Other listed source"
    domains: list = []

    @classmethod
    def matches(cls, url: str) -> bool:
        return True

    def extract(self, url: str, html: str) -> Optional[PropertyRecord]:
        listing_id = self.source_listing_id(url)
        record = self._build_record(url, html, urlparse(url).netloc or self.source_name, listing_id)
        return record
