"""Match scoring (0-100) and A/B/C priority assignment."""
from __future__ import annotations

from datetime import datetime, timezone

from .filters import location_overlap
from .models import (
    BHK,
    BrokeragePreference,
    ParkingPreference,
    Priority,
    PropertyRecord,
    SearchRequest,
)

_WEIGHTS = {
    "location": 20,
    "rent": 20,
    "bhk": 15,
    "brokerage": 10,
    "parking": 10,
    "lift": 5,
    "water": 10,
    "freshness": 5,
    "completeness": 5,
}


def _location_score(req: SearchRequest, record: PropertyRecord) -> float:
    overlap = location_overlap(req.area, record)
    if overlap < 0:
        return _WEIGHTS["location"] * 0.4
    return _WEIGHTS["location"] * overlap


def _rent_score(req: SearchRequest, record: PropertyRecord) -> float:
    if record.monthly_rent is None:
        return _WEIGHTS["rent"] * 0.5
    if req.min_rent is None and req.max_rent is None:
        return _WEIGHTS["rent"]
    lo = req.min_rent if req.min_rent is not None else 0
    hi = req.max_rent if req.max_rent is not None else record.monthly_rent
    if hi <= lo:
        return _WEIGHTS["rent"]
    midpoint = (lo + hi) / 2
    distance = abs(record.monthly_rent - midpoint) / max(hi - lo, 1)
    return max(0.0, _WEIGHTS["rent"] * (1 - min(distance, 1)))


def _bhk_score(req: SearchRequest, record: PropertyRecord) -> float:
    if req.bhk == BHK.ANY:
        return _WEIGHTS["bhk"]
    if record.bhk is None:
        return _WEIGHTS["bhk"] * 0.4
    if record.bhk == req.bhk.value or (req.bhk == BHK.FOUR_PLUS and record.bhk.isdigit() and int(record.bhk) >= 4):
        return _WEIGHTS["bhk"]
    return 0.0


def _brokerage_score(req: SearchRequest, record: PropertyRecord) -> float:
    if record.owner_or_agent == "owner":
        return _WEIGHTS["brokerage"]
    if record.owner_or_agent == "agent":
        return 0.0 if req.brokerage != BrokeragePreference.ANY else _WEIGHTS["brokerage"] * 0.4
    return _WEIGHTS["brokerage"] * 0.5


def _parking_score(req: SearchRequest, record: PropertyRecord) -> float:
    if record.parking == "covered":
        return _WEIGHTS["parking"]
    if record.parking == "open":
        return _WEIGHTS["parking"] * (0.9 if req.parking == ParkingPreference.OPEN else 0.6)
    if record.parking == "none":
        return _WEIGHTS["parking"] if req.parking == ParkingPreference.NONE else 0.0
    return _WEIGHTS["parking"] * 0.4


def _lift_score(record: PropertyRecord) -> float:
    if record.lift == "available":
        return _WEIGHTS["lift"]
    if record.lift == "not_available":
        return 0.0
    return _WEIGHTS["lift"] * 0.5


def _water_score(record: PropertyRecord) -> float:
    if record.water_supply == "reliable":
        return _WEIGHTS["water"]
    if record.water_supply == "unreliable":
        return 0.0
    return _WEIGHTS["water"] * 0.5


def _freshness_score(record: PropertyRecord) -> float:
    date_str = record.updated_date or record.listed_date
    if not date_str:
        return _WEIGHTS["freshness"] * 0.5
    try:
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - parsed).days
    except ValueError:
        return _WEIGHTS["freshness"] * 0.5
    if age_days <= 3:
        return _WEIGHTS["freshness"]
    if age_days <= 14:
        return _WEIGHTS["freshness"] * 0.7
    if age_days <= 30:
        return _WEIGHTS["freshness"] * 0.4
    return _WEIGHTS["freshness"] * 0.1


def _completeness_score(record: PropertyRecord) -> float:
    return _WEIGHTS["completeness"] * max(0.0, min(record.source_confidence, 1.0))


def score(req: SearchRequest, record: PropertyRecord) -> float:
    total = (
        _location_score(req, record)
        + _rent_score(req, record)
        + _bhk_score(req, record)
        + _brokerage_score(req, record)
        + _parking_score(req, record)
        + _lift_score(record)
        + _water_score(record)
        + _freshness_score(record)
        + _completeness_score(record)
    )
    return round(min(total, 100.0), 1)


def priority_for_score(match_score: float) -> Priority:
    if match_score >= 75:
        return Priority.A
    if match_score >= 50:
        return Priority.B
    return Priority.C


def rank(req: SearchRequest, records: list[PropertyRecord]) -> list[PropertyRecord]:
    for record in records:
        record.match_score = score(req, record)
        record.priority = priority_for_score(record.match_score)
    return sorted(records, key=lambda r: r.match_score or 0, reverse=True)
