from urllib.parse import quote

from app.search_providers.duckduckgo_provider import DuckDuckGoProvider, _resolve_result_url

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
