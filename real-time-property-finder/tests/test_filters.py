import logging
from datetime import datetime, timezone

from app.filters import filter_candidates, passes_hard_filters
from app.models import BHK, AvailabilityStatus, PropertyRecord, PropertyType, SearchRequest


def make_record(**overrides) -> PropertyRecord:
    defaults = dict(
        id="1",
        source="Housing.com",
        listing_url="https://housing.com/listing/1",
        last_checked=datetime.now(timezone.utc).isoformat(),
        locality="Adyar, Chennai",
        availability_status=AvailabilityStatus.ACTIVE,
    )
    defaults.update(overrides)
    return PropertyRecord(**defaults)


def make_request(**overrides) -> SearchRequest:
    defaults = dict(area="Adyar")
    defaults.update(overrides)
    return SearchRequest(**defaults)


def test_rent_within_range_passes():
    req = make_request(min_rent=15000, max_rent=20000)
    record = make_record(monthly_rent=18000)
    ok, _ = passes_hard_filters(record, req)
    assert ok


def test_rent_outside_range_excluded():
    req = make_request(min_rent=15000, max_rent=20000)
    record = make_record(monthly_rent=25000)
    ok, reason = passes_hard_filters(record, req)
    assert not ok
    assert "rent" in reason


def test_unknown_rent_is_not_excluded():
    req = make_request(min_rent=15000, max_rent=20000)
    record = make_record(monthly_rent=None)
    ok, _ = passes_hard_filters(record, req)
    assert ok


def test_bhk_mismatch_excluded():
    req = make_request(bhk=BHK.TWO)
    record = make_record(bhk="1")
    ok, reason = passes_hard_filters(record, req)
    assert not ok
    assert "BHK" in reason


def test_bhk_match_passes():
    req = make_request(bhk=BHK.TWO)
    record = make_record(bhk="2")
    ok, _ = passes_hard_filters(record, req)
    assert ok


def test_unknown_bhk_not_excluded():
    req = make_request(bhk=BHK.TWO)
    record = make_record(bhk=None)
    ok, _ = passes_hard_filters(record, req)
    assert ok


def test_property_type_mismatch_excluded():
    req = make_request(property_type=PropertyType.VILLA)
    record = make_record(property_type="apartment")
    ok, _ = passes_hard_filters(record, req)
    assert not ok


def test_inactive_listing_excluded():
    req = make_request()
    record = make_record(availability_status=AvailabilityStatus.INACTIVE)
    ok, reason = passes_hard_filters(record, req)
    assert not ok
    assert "active" in reason


def test_unrelated_locality_excluded():
    req = make_request(area="Velachery")
    record = make_record(locality="Anna Nagar", address="Anna Nagar", property_name="2 BHK flat", description=None)
    ok, reason = passes_hard_filters(record, req)
    assert not ok


def test_filter_candidates_keeps_only_matching():
    req = make_request(min_rent=15000, max_rent=20000)
    records = [
        make_record(id="a", monthly_rent=18000),
        make_record(id="b", monthly_rent=25000),
    ]
    filtered = filter_candidates(records, req)
    assert [r.id for r in filtered] == ["a"]


def test_filter_candidates_logs_rejection_reasons(caplog):
    """Regression guard: silently dropping every candidate with no logged
    reason was exactly the kind of gap that made an earlier real bug take
    three rounds of debugging to pin down. Rejections must be visible."""
    app_logger = logging.getLogger("property_finder")
    caplog.set_level(logging.INFO, logger="property_finder")
    app_logger.addHandler(caplog.handler)
    try:
        req = make_request(min_rent=15000, max_rent=20000)
        records = [make_record(id="a", monthly_rent=25000)]
        filter_candidates(records, req)
    finally:
        app_logger.removeHandler(caplog.handler)

    messages = [r.getMessage() for r in caplog.records]
    assert any("rejected 1 of 1" in m for m in messages)
    assert any("rent above requested range" in m for m in messages)
