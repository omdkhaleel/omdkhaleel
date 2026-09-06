"""Multi-level, similarity-based duplicate detection.

The same physical apartment often turns up on more than one portal. We
only ever merge two candidates when several independent signals agree
(never on name similarity alone) so that two different flats in the same
building are not accidentally collapsed into one result.
"""
from __future__ import annotations

import difflib
from typing import List, Optional
from urllib.parse import urlsplit, urlunsplit

from .models import PropertyRecord

_TEXT_SIMILARITY_THRESHOLD = 0.72
_MIN_CORROBORATING_SIGNALS = 2


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _text_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _numeric_close(a: Optional[float], b: Optional[float], tolerance: float) -> bool:
    if a is None or b is None:
        return False
    denom = max(abs(a), abs(b), 1)
    return abs(a - b) / denom <= tolerance


def are_duplicates(a: PropertyRecord, b: PropertyRecord) -> bool:
    if normalize_url(a.listing_url) == normalize_url(b.listing_url):
        return True

    if a.source_listing_id and b.source_listing_id and a.source != b.source:
        if a.source_listing_id == b.source_listing_id:
            return True

    if a.contact_number and b.contact_number and a.contact_number == b.contact_number:
        return True

    name_sim = _text_similarity(a.property_name, b.property_name)
    addr_sim = _text_similarity(a.address or a.locality, b.address or b.locality)
    text_score = max(name_sim, addr_sim)

    corroborating = sum(
        [
            bool(a.bhk and b.bhk and a.bhk == b.bhk),
            _numeric_close(a.monthly_rent, b.monthly_rent, 0.03),
            _numeric_close(a.size_sqft, b.size_sqft, 0.08),
            _numeric_close(a.security_deposit, b.security_deposit, 0.08),
        ]
    )

    return text_score >= _TEXT_SIMILARITY_THRESHOLD and corroborating >= _MIN_CORROBORATING_SIGNALS


def _more_complete(a: PropertyRecord, b: PropertyRecord) -> PropertyRecord:
    return a if a.source_confidence >= b.source_confidence else b


def _merge_pair(primary: PropertyRecord, other: PropertyRecord) -> PropertyRecord:
    keep, drop = (primary, other) if primary.source_confidence >= other.source_confidence else (other, primary)

    merged_field_names = [
        "photo_url", "property_name", "property_type", "bhk", "locality", "address",
        "monthly_rent", "maintenance", "security_deposit", "brokerage", "size_sqft",
        "furnishing", "parking", "lift", "water_supply", "food_preference",
        "owner_or_agent", "contact_number", "listed_date", "updated_date", "description",
    ]
    data = keep.model_dump()
    for field in merged_field_names:
        if data.get(field) is None:
            fallback = getattr(drop, field)
            if fallback is not None:
                data[field] = fallback

    sources = set(keep.merged_sources) | set(drop.merged_sources) | {keep.source, drop.source}
    data["merged_sources"] = sorted(sources)
    data["notes"] = list(dict.fromkeys(keep.notes + drop.notes + [f"Also listed on {drop.source}: {drop.listing_url}"]))
    data["id"] = keep.id
    return PropertyRecord(**data)


def deduplicate(records: List[PropertyRecord]) -> List[PropertyRecord]:
    clusters: List[PropertyRecord] = []
    for record in records:
        merged = False
        for i, existing in enumerate(clusters):
            if are_duplicates(existing, record):
                clusters[i] = _merge_pair(existing, record)
                merged = True
                break
        if not merged:
            clusters.append(record)
    return clusters
