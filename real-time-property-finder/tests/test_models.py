from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import PropertyRecord, SearchRequest


def test_blank_area_is_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(area="   ")


def test_min_rent_greater_than_max_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(area="Adyar", min_rent=30000, max_rent=15000)


def test_unspecified_fields_default_to_unknown_none():
    record = PropertyRecord(
        id="1",
        source="Housing.com",
        listing_url="https://housing.com/1",
        last_checked=datetime.now(timezone.utc).isoformat(),
    )
    assert record.monthly_rent is None
    assert record.bhk is None
    assert record.contact_number is None
    assert record.description is None
