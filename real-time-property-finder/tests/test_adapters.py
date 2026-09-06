from app.adapters.generic_property_adapter import GenericPropertyAdapter
from app.adapters.housing_adapter import HousingAdapter
from app.adapters.registry import adapter_for_url

SAMPLE_HTML = """
<html>
<head>
  <title>2 BHK Flat for Rent in Adyar, Chennai</title>
  <meta property="og:title" content="2 BHK Flat for Rent in Adyar, Chennai" />
  <meta property="og:description" content="Spacious 2 BHK semi furnished apartment in Adyar with covered parking and lift." />
  <meta property="og:image" content="https://images.example.com/photo.jpg" />
  <script type="application/ld+json">
  {"@type": "Apartment", "name": "Adyar Residency", "description": "Nice place"}
  </script>
</head>
<body>
  <p>Rent: 18000. Deposit: 72000. Maintenance: 1000. Size: 800 sqft.
  Semi furnished. Covered parking available. Lift available. 24x7 water supply.
  Owner listed, no brokerage. Contact 9876543210.</p>
</body>
</html>
"""

PG_HTML = """
<html><head><title>PG for rent in Adyar</title></head>
<body><p>Paying guest accommodation, shared room, rent 8000 per month.</p></body></html>
"""

BLOCKED_HTML = """
<html><body><h1>Access Denied</h1><p>Please complete the CAPTCHA to continue.</p></body></html>
"""


def test_housing_adapter_extracts_known_fields():
    adapter = HousingAdapter()
    record = adapter.extract("https://housing.com/listing/abc123", SAMPLE_HTML)
    assert record is not None
    assert record.source == "Housing.com"
    assert record.monthly_rent == 18000
    assert record.bhk == "2"
    assert record.size_sqft == 800
    assert record.furnishing == "semi_furnished"
    assert record.parking == "covered"
    assert record.lift == "available"
    assert record.water_supply == "reliable"
    assert record.owner_or_agent == "owner"
    assert record.contact_number == "9876543210"
    assert record.photo_url == "https://images.example.com/photo.jpg"


def test_unknown_fields_stay_none_not_fabricated():
    adapter = HousingAdapter()
    minimal_html = "<html><head><title>Flat for rent</title></head><body><p>Contact for details.</p></body></html>"
    record = adapter.extract("https://housing.com/listing/xyz", minimal_html)
    assert record is not None
    assert record.monthly_rent is None
    assert record.security_deposit is None
    assert record.contact_number is None


def test_pg_listing_is_excluded():
    adapter = HousingAdapter()
    record = adapter.extract("https://housing.com/pg/1", PG_HTML)
    assert record is None


def test_blocked_page_is_not_extracted():
    adapter = HousingAdapter()
    record = adapter.extract("https://housing.com/listing/blocked", BLOCKED_HTML)
    assert record is None


def test_registry_routes_by_domain():
    assert isinstance(adapter_for_url("https://housing.com/x"), HousingAdapter)
    assert isinstance(adapter_for_url("https://randomsite.example/listing"), GenericPropertyAdapter)
