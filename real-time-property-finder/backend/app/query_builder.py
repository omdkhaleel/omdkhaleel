"""Generates a set of complementary web-search queries for one request.

The entered area is the only geographic term used — nothing is added,
assumed, or substituted for it, and no city/locality is ever hard-coded
here. Every other query fragment is derived purely from the fields the
user actually set on the request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .models import (
    BHK,
    BrokeragePreference,
    Furnishing,
    FoodPreference,
    ParkingPreference,
    PropertyType,
    SearchRequest,
)

PORTAL_DOMAINS = [
    "housing.com",
    "nobroker.in",
    "magicbricks.com",
    "99acres.com",
]

_BHK_PHRASE = {
    BHK.ONE: "1 BHK",
    BHK.TWO: "2 BHK",
    BHK.THREE: "3 BHK",
    BHK.FOUR_PLUS: "4 BHK",
}

_PROPERTY_TYPE_PHRASE = {
    PropertyType.APARTMENT: "apartment",
    PropertyType.INDEPENDENT_HOUSE: "independent house",
    PropertyType.VILLA: "villa",
}

_FURNISHING_PHRASE = {
    Furnishing.UNFURNISHED: "unfurnished",
    Furnishing.SEMI_FURNISHED: "semi furnished",
    Furnishing.FULLY_FURNISHED: "fully furnished",
}


@dataclass(frozen=True)
class SearchQuery:
    text: str
    target_domain: Optional[str] = None


def _rent_phrase(req: SearchRequest) -> str:
    if req.min_rent is not None and req.max_rent is not None:
        return f"rent {req.min_rent} {req.max_rent}"
    if req.max_rent is not None:
        return f"rent under {req.max_rent}"
    if req.min_rent is not None:
        return f"rent above {req.min_rent}"
    return ""


def _clean(text: str) -> str:
    return " ".join(text.split())


def generate_queries(req: SearchRequest, max_queries: int = 10) -> List[SearchQuery]:
    area = req.area.strip()
    bhk_phrase = _BHK_PHRASE.get(req.bhk, "")
    ptype_phrase = _PROPERTY_TYPE_PHRASE.get(req.property_type, "")
    rent_phrase = _rent_phrase(req)

    queries: List[SearchQuery] = []

    # The four site: queries are placed right after the two broadest
    # queries, ahead of the optional preference-based ones, so they
    # always survive the max_queries cutoff below.
    queries.append(_clean(f"{area} {bhk_phrase} {ptype_phrase} rent {rent_phrase}"))
    queries.append(_clean(f"{area} {bhk_phrase} bedroom flat rent"))

    for domain in PORTAL_DOMAINS:
        queries.append(_clean(f"site:{domain} {area} {bhk_phrase} rent"))

    queries.append(_clean(f"{area} {ptype_phrase or 'apartment'} rent owner"))
    queries.append(_clean(f"{area} {bhk_phrase} rental {ptype_phrase} parking".replace("  ", " ")))

    if req.brokerage in (BrokeragePreference.PREFERRED, BrokeragePreference.ONLY):
        queries.append(_clean(f"{area} {bhk_phrase} no brokerage"))

    if req.furnishing != Furnishing.ANY:
        queries.append(_clean(f"{area} {bhk_phrase} {_FURNISHING_PHRASE[req.furnishing]} rent"))

    if req.parking == ParkingPreference.COVERED:
        queries.append(_clean(f"{area} {bhk_phrase} rent covered car parking"))
    elif req.parking == ParkingPreference.OPEN:
        queries.append(_clean(f"{area} {bhk_phrase} rent open parking"))

    if req.food_preference == FoodPreference.VEGETARIAN:
        queries.append(_clean(f"{area} {bhk_phrase} rent vegetarian only"))
    elif req.food_preference == FoodPreference.NON_VEGETARIAN:
        queries.append(_clean(f"{area} {bhk_phrase} rent non-vegetarian allowed"))

    seen = set()
    deduped: List[SearchQuery] = []
    for text in queries:
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        target = next((d for d in PORTAL_DOMAINS if f"site:{d}" in text), None)
        deduped.append(SearchQuery(text=text, target_domain=target))

    return deduped[:max_queries]
