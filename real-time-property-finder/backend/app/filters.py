"""Hard filters applied to normalized candidates before ranking.

A hard filter only ever excludes a listing when the page gave us a clear,
unambiguous signal that it doesn't match. Whenever a field is unknown we
keep the listing in (it just scores lower later) instead of guessing —
per spec, ambiguous/unverifiable data must not silently disappear from a
"we don't know" result.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import BHK, LiftPreference, PropertyType, AvailabilityStatus, PropertyRecord, SearchRequest, WaterPreference

_STOPWORDS = {"the", "a", "an", "of", "in", "near", "at", "for", "rent", "chennai", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi"}


def tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if len(w) > 2]


def _location_tokens(area: str) -> List[str]:
    return [w for w in tokenize(area) if w not in _STOPWORDS] or tokenize(area)


def location_overlap(area: str, record: PropertyRecord) -> float:
    """Fraction of the area's tokens found anywhere in the record's
    location-ish text. Returns None-equivalent (-1.0) when we have no
    location text at all to compare against."""
    haystack_parts = [record.locality, record.address, record.property_name, record.description]
    haystack = " ".join(p for p in haystack_parts if p)
    if not haystack.strip():
        return -1.0
    area_tokens = _location_tokens(area)
    if not area_tokens:
        return 1.0
    haystack_tokens = set(tokenize(haystack))
    hits = sum(1 for t in area_tokens if t in haystack_tokens)
    return hits / len(area_tokens)


_BHK_NUMBER_RE = re.compile(r"\d+")


def _bhk_conflicts(requested: BHK, actual: str) -> bool:
    if requested == BHK.ANY or not actual:
        return False
    match = _BHK_NUMBER_RE.search(actual)
    if not match:
        return False
    actual_n = int(match.group(0))
    if requested == BHK.FOUR_PLUS:
        return actual_n < 4
    return str(actual_n) != requested.value


def _property_type_conflicts(requested: PropertyType, actual: str) -> bool:
    if requested == PropertyType.ANY or not actual:
        return False
    return actual != requested.value


_EXCLUDED_AVAILABILITY = {
    AvailabilityStatus.STALE,
    AvailabilityStatus.INACTIVE,
    AvailabilityStatus.UNAVAILABLE,
}


def passes_hard_filters(record: PropertyRecord, req: SearchRequest) -> Tuple[bool, str]:
    if record.availability_status in _EXCLUDED_AVAILABILITY:
        return False, "listing no longer appears active"

    if record.monthly_rent is not None:
        if req.min_rent is not None and record.monthly_rent < req.min_rent:
            return False, "rent below requested range"
        if req.max_rent is not None and record.monthly_rent > req.max_rent:
            return False, "rent above requested range"

    if _bhk_conflicts(req.bhk, record.bhk):
        return False, "BHK does not match requested configuration"

    if _property_type_conflicts(req.property_type, record.property_type):
        return False, "property type does not match"

    overlap = location_overlap(req.area, record)
    if overlap == 0.0:
        return False, "does not appear to be in the requested area"

    if req.brokerage.value == "only" and record.owner_or_agent == "agent":
        return False, "listing is agent/broker mediated"

    if req.lift == LiftPreference.REQUIRED and record.lift == "not_available":
        return False, "no lift, which was required"

    if req.water == WaterPreference.REQUIRED and record.water_supply == "unreliable":
        return False, "unreliable water supply, which conflicts with a required preference"

    return True, ""


def filter_candidates(records: List[PropertyRecord], req: SearchRequest) -> List[PropertyRecord]:
    kept = []
    for record in records:
        ok, _reason = passes_hard_filters(record, req)
        if ok:
            kept.append(record)
    return kept
