import logging
from urllib.parse import quote

import httpx
import pytest

from app.search_providers.duckduckgo_provider import DuckDuckGoProvider, _resolve_result_url

BLOCKED_PAGE = "<html><body><h1>Access Denied</h1><p>Please complete the CAPTCHA to continue.</p></body></html>"
EMPTY_RESULTS_PAGE = "<html><body><div class='results'><p>No results found for your search.</p></div></body></html>"

REAL_TARGET = "https://housing.com/in/buy/rent/adyar-chennai-2bhk"
WRAPPED_HREF = f"//duckduckgo.com/l/?uddg={quote(REAL_TARGET, safe='')}&rut=abc123"

SAMPLE_RESULTS_PAGE = f"""
<html><body>
<div class="results">
  <div class="result">
    <a class="result__a" href="{WRAPPED_HREF}">2 BHK for rent in Adyar - Housing.com</a>
    <div class="result__snippet">Spacious 2 BHK apartment available for rent in Adyar, Chennai.</div>
  </div>
  <div class="result">
    <a class="result__a" href="//duckduckgo.com/y.js?ad_provider=x">Sponsored result</a>
  </div>
</div>
</body></html>
"""


def test_resolve_result_url_unwraps_ddg_redirect():
    assert _resolve_result_url(WRAPPED_HREF) == REAL_TARGET


def test_resolve_result_url_passes_through_direct_links():
    assert _resolve_result_url("https://magicbricks.com/listing/1") == "https://magicbricks.com/listing/1"


def test_resolve_result_url_handles_missing_or_junk_href():
    assert _resolve_result_url("") is None
    assert _resolve_result_url("//duckduckgo.com/y.js?ad_provider=x") is None


def test_parse_extracts_real_target_urls_not_ddg_redirect_links():
    hits = DuckDuckGoProvider._parse(SAMPLE_RESULTS_PAGE, num_results=10)
    urls = [h.url for h in hits]
    assert REAL_TARGET in urls
    assert all("duckduckgo.com" not in u for u in urls)


def test_parse_captures_title_and_snippet():
    hits = DuckDuckGoProvider._parse(SAMPLE_RESULTS_PAGE, num_results=10)
    hit = next(h for h in hits if h.url == REAL_TARGET)
    assert "Housing.com" in hit.title
    assert "Adyar" in hit.snippet


def _mock_client_returning(html: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    class _Client(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    return _Client


@pytest.fixture
def property_finder_caplog(caplog):
    """The app logger disables propagation to the root logger (so it never
    double-prints if something else configures root logging), which means
    pytest's default caplog wiring - attached to the root logger - misses
    it. Attach caplog's handler directly to our named logger instead."""
    caplog.set_level(logging.INFO, logger="property_finder")
    app_logger = logging.getLogger("property_finder")
    app_logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        app_logger.removeHandler(caplog.handler)


@pytest.mark.asyncio
async def test_blocked_page_is_reported_as_a_block_not_a_silent_zero(monkeypatch, property_finder_caplog):
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_returning(BLOCKED_PAGE))

    hits = await DuckDuckGoProvider().search("Adyar 2 BHK rent", num_results=10)

    assert hits == []
    messages = [r.getMessage() for r in property_finder_caplog.records]
    assert any("bot-check" in m for m in messages)


@pytest.mark.asyncio
async def test_legitimate_empty_page_is_distinguished_from_a_block(monkeypatch, property_finder_caplog):
    monkeypatch.setattr(httpx, "AsyncClient", _mock_client_returning(EMPTY_RESULTS_PAGE))

    hits = await DuckDuckGoProvider().search("Adyar 2 BHK rent", num_results=10)

    assert hits == []
    messages = [r.getMessage() for r in property_finder_caplog.records]
    assert any("no result links found" in m for m in messages)
    assert not any("bot-check" in m for m in messages)
