"""Maps a discovered URL to the adapter responsible for it.

Named portal adapters are tried first (most specific match wins); any
URL that doesn't belong to a known portal falls through to the generic
adapter so the pipeline never simply drops an otherwise-legitimate
public listing page.
"""
from __future__ import annotations

from typing import List

from .base import PortalAdapter
from .generic_property_adapter import GenericPropertyAdapter
from .housing_adapter import HousingAdapter
from .magicbricks_adapter import MagicbricksAdapter
from .ninety_nine_acres_adapter import NinetyNineAcresAdapter
from .nobroker_adapter import NoBrokerAdapter

NAMED_ADAPTERS: List[PortalAdapter] = [
    HousingAdapter(),
    NoBrokerAdapter(),
    MagicbricksAdapter(),
    NinetyNineAcresAdapter(),
]

_GENERIC = GenericPropertyAdapter()


def adapter_for_url(url: str) -> PortalAdapter:
    for adapter in NAMED_ADAPTERS:
        if adapter.matches(url):
            return adapter
    return _GENERIC


def all_named_sources() -> List[str]:
    return [adapter.source_name for adapter in NAMED_ADAPTERS]
