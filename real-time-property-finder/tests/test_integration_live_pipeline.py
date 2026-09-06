"""End-to-end proof that the real pipeline — the actual DuckDuckGoProvider
and the actual HousingAdapter, not fakes — turns a DuckDuckGo results page
into ranked PropertyRecords. Only the network transport is replaced (via
httpx.MockTransport, part of httpx itself) so this runs without internet
access while still exercising every real line of search/fetch/extract
code. This guards specifically against the class of bug where a provider
returns "results" that never survive into the final output.
"""
from urllib.parse import quote

import httpx
import pytest

from app.models import BHK, SearchRequest
from app.orchestrator import SearchOrchestrator
from app.search_providers.duckduckgo_provider import DuckDuckGoProvider

LISTING_URL = "https://housing.com/rent/2bhk-adyar-chennai-123"
WRAPPED_LISTING_HREF = f"//duckduckgo.com/l/?uddg={quote(LISTING_URL, safe='')}&rut=xyz"

DDG_RESULTS_HTML = f"""
<html><body><div class="results">
  <div class="result">
    <a class="result__a" href="{WRAPPED_LISTING_HREF}">2 BHK Flat for Rent in Adyar, Chennai</a>
    <div class="result__snippet">Semi furnished 2 BHK in Adyar with covered parking.</div>
  </div>
</div></body></html>
"""

LISTING_HTML = """
<html><head>
  <title>2 BHK Flat for Rent in Adyar, Chennai</title>
  <meta property="og:title" content="2 BHK Flat for Rent in Adyar, Chennai" />
  <meta property="og:description" content="Semi furnished 2 BHK apartment in Adyar with covered parking and lift." />
</head><body>
  <p>Rent: 18000. Deposit: 72000. Maintenance: 1000. Size: 800 sqft.
  Semi furnished. Covered parking available. Lift available. 24x7 water supply.
  Owner listed, no brokerage.</p>
</body></html>
"""


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "html.duckduckgo.com":
        return httpx.Response(200, text=DDG_RESULTS_HTML)
    if request.url.host == "housing.com":
        return httpx.Response(200, text=LISTING_HTML)
    return httpx.Response(404, text="not found")


class _MockTransportAsyncClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_mock_handler)
        super().__init__(*args, **kwargs)


@pytest.mark.asyncio
async def test_real_provider_and_adapter_produce_a_ranked_result(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _MockTransportAsyncClient)

    orchestrator = SearchOrchestrator(provider=DuckDuckGoProvider())
    req = SearchRequest(area="Adyar", bhk=BHK.TWO, min_rent=15000, max_rent=20000)

    response = await orchestrator.run(req)

    assert response.statistics.listings_discovered > 0, "DDG redirect links were not unwrapped into real URLs"
    assert len(response.results) == 1
    record = response.results[0]
    assert record.listing_url == LISTING_URL
    assert record.source == "Housing.com"
    assert record.monthly_rent == 18000
    assert record.bhk == "2"
    assert record.match_score is not None and record.match_score > 0
    assert record.priority is not None
