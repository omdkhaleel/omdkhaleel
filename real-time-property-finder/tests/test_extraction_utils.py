from app.extraction_utils import extract_rent


def test_extract_rent_single_unambiguous_value():
    assert extract_rent("Rent: 18000. Deposit: 72000.") == 18000


def test_extract_rent_same_value_repeated_is_not_ambiguous():
    assert extract_rent("Rent: ₹18,000 per month. ... Rent ₹18,000 negotiable.") == 18000


def test_extract_rent_multiple_distinct_values_is_ambiguous_and_returns_none():
    """A locality/category hub page listing many properties, or showing
    price-tier facet links, contains several unrelated rent-like numbers.
    Per spec, an ambiguous rent field must not be guessed - and must not
    later cause a hard-filter exclusion - so it resolves to unverified."""
    text = "Rent: 20000. Similar flats nearby - Rent: 30000. Rent: 45000."
    assert extract_rent(text) is None


def test_extract_rent_no_match_returns_none():
    assert extract_rent("Contact us for details.") is None
