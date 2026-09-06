from datetime import datetime, timezone

from app.models import BHK, PropertyRecord, SearchRequest
from app.ranking import priority_for_score, rank, score


def make_record(**overrides) -> PropertyRecord:
    defaults = dict(
        id="1",
        source="Housing.com",
        listing_url="https://housing.com/listing/1",
        last_checked=datetime.now(timezone.utc).isoformat(),
        source_confidence=0.8,
    )
    defaults.update(overrides)
    return PropertyRecord(**defaults)


def test_exact_bhk_owner_covered_parking_scores_higher():
    req = SearchRequest(area="Adyar", bhk=BHK.TWO, min_rent=15000, max_rent=20000)
    strong = make_record(
        bhk="2",
        monthly_rent=17500,
        locality="Adyar",
        owner_or_agent="owner",
        parking="covered",
        lift="available",
        water_supply="reliable",
    )
    weak = make_record(
        id="2",
        bhk="1",
        monthly_rent=25000,
        locality=None,
        owner_or_agent="agent",
        parking=None,
        lift=None,
        water_supply=None,
    )
    assert score(req, strong) > score(req, weak)


def test_priority_thresholds():
    assert priority_for_score(90).value == "A"
    assert priority_for_score(60).value == "B"
    assert priority_for_score(30).value == "C"


def test_rank_sorts_descending_and_assigns_priority():
    req = SearchRequest(area="Adyar")
    records = [
        make_record(id="low", monthly_rent=None),
        make_record(id="high", bhk="2", locality="Adyar", owner_or_agent="owner", parking="covered", lift="available", water_supply="reliable"),
    ]
    ranked = rank(req, records)
    assert ranked[0].id == "high"
    assert all(r.match_score is not None and r.priority is not None for r in ranked)
