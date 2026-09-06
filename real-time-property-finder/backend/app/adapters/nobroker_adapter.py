from __future__ import annotations

from typing import Optional

from ..models import PropertyRecord
from .base import GenericExtractionMixin, PortalAdapter


class NoBrokerAdapter(GenericExtractionMixin, PortalAdapter):
    source_name = "NoBroker"
    domains = ["nobroker.in"]

    def extract(self, url: str, html: str) -> Optional[PropertyRecord]:
        listing_id = self.source_listing_id(url)
        record = self._build_record(url, html, self.source_name, listing_id)
        if record and record.owner_or_agent is None and record.brokerage is None:
            record.notes.append("NoBroker platform listings are typically owner-direct, but this was not confirmed on the page")
        return record
