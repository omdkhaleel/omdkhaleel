from __future__ import annotations

from typing import Optional

from ..models import PropertyRecord
from .base import GenericExtractionMixin, PortalAdapter


class NinetyNineAcresAdapter(GenericExtractionMixin, PortalAdapter):
    source_name = "99acres"
    domains = ["99acres.com"]

    def extract(self, url: str, html: str) -> Optional[PropertyRecord]:
        listing_id = self.source_listing_id(url)
        return self._build_record(url, html, self.source_name, listing_id)
