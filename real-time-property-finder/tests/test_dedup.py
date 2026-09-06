from datetime import datetime, timezone

from app.dedup import are_duplicates, deduplicate
from app.models import PropertyRecord


def make_record(**overrides) -> PropertyRecord:
    defaults = dict(
        id="1",
        source="Housing.com",
        listing_url="https://housing.com/listing/1",
        last_checked=datetime.now(timezone.utc).isoformat(),
        source_confidence=0.5,
    )
    defaults.update(overrides)
    return PropertyRecord(**defaults)


def test_same_property_across_portals_is_merged():
    a = make_record(
        id="a",
        source="Housing.com",
        listing_url="https://housing.com/2bhk-adyar-1",
        property_name="Spacious 2 BHK in Adyar",
        address="Adyar, Chennai",
        monthly_rent=18000,
        bhk="2",
        size_sqft=800,
    )
    b = make_record(
        id="b",
        source="Magicbricks",
        listing_url="https://magicbricks.com/2bhk-adyar-1",
        property_name="Spacious 2 BHK Flat in Adyar",
        address="Adyar, Chennai",
        monthly_rent=18000,
        bhk="2",
        size_sqft=800,
    )
    assert are_duplicates(a, b)
    merged = deduplicate([a, b])
    assert len(merged) == 1
    assert set(merged[0].merged_sources) == {"Housing.com", "Magicbricks"}


def test_same_building_different_units_not_merged():
    a = make_record(
        id="a",
        listing_url="https://housing.com/unit-1",
        property_name="Green Towers Apartment",
        address="Green Towers, Adyar",
        monthly_rent=15000,
        bhk="1",
        size_sqft=450,
    )
    b = make_record(
        id="b",
        listing_url="https://magicbricks.com/unit-2",
        property_name="Green Towers Apartment",
        address="Green Towers, Adyar",
        monthly_rent=28000,
        bhk="3",
        size_sqft=1200,
    )
    assert not are_duplicates(a, b)
    merged = deduplicate([a, b])
    assert len(merged) == 2


def test_identical_canonical_url_is_duplicate():
    a = make_record(id="a", listing_url="https://housing.com/listing/1?utm_source=x")
    b = make_record(id="b", listing_url="https://housing.com/listing/1")
    assert are_duplicates(a, b)


def test_matching_phone_number_is_duplicate():
    a = make_record(id="a", listing_url="https://housing.com/l1", contact_number="9876543210")
    b = make_record(id="b", listing_url="https://nobroker.in/l2", contact_number="9876543210")
    assert are_duplicates(a, b)


def test_different_properties_stay_separate():
    a = make_record(id="a", listing_url="https://housing.com/l1", property_name="A", monthly_rent=12000, bhk="1")
    b = make_record(id="b", listing_url="https://magicbricks.com/l2", property_name="Z", monthly_rent=30000, bhk="3")
    merged = deduplicate([a, b])
    assert len(merged) == 2
