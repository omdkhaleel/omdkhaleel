from datetime import datetime, timezone

import pytest

from app.adapters.base import FetchOutcome
from app.models import PropertyRecord, SearchRequest
from app.orchestrator import SearchOrchestrator
from app.search_providers.base import SearchHit, SearchProvider


class FakeProvider(SearchProvider):
    name = "fake"

    def __init__(self, hits_by_query=None, fail_domains=None):
        self.hits_by_query = hits_by_query or {}
        self.fail_domains = fail_domains or set()
        self.calls = []

    async def search(self, query, num_results):
        self.calls.append(query)
        for domain in self.fail_domains:
            if domain in query:
                return []
        for keyword, hits in self.hits_by_query.items():
            if keyword in query:
                return hits
        return []


class FakeAdapter:
    def __init__(self, record_factory=None, fail_urls=None, exclude_urls=None):
        self.record_factory = record_factory
        self.fail_urls = fail_urls or set()
        self.exclude_urls = exclude_urls or set()
        self.fetch_calls = []

    async def fetch(self, url, client):
        self.fetch_calls.append(url)
        if url in self.fail_urls:
            return FetchOutcome(403, None)
        return FetchOutcome(200, "<html>fake</html>")

    def extract(self, url, html):
        if url in self.exclude_urls:
            return None
        if self.record_factory is None:
            return None
        return self.record_factory(url)


def make_good_record(url: str) -> PropertyRecord:
    return PropertyRecord(
        id=url,
        source="Housing.com",
        listing_url=url,
        last_checked=datetime.now(timezone.utc).isoformat(),
        locality="Adyar",
        bhk="2",
        monthly_rent=18000,
        source_confidence=0.8,
    )


@pytest.mark.asyncio
async def test_fresh_search_creates_new_session_each_time(monkeypatch):
    provider = FakeProvider(hits_by_query={"housing.com": [SearchHit(url="https://housing.com/l1")]})
    adapter = FakeAdapter(record_factory=make_good_record)
    monkeypatch.setattr("app.orchestrator.adapter_for_url", lambda url: adapter)

    orchestrator = SearchOrchestrator(provider=provider)
    req = SearchRequest(area="Adyar")

    response_1 = await orchestrator.run(req)
    response_2 = await orchestrator.run(req)

    assert response_1.search_id != response_2.search_id
    assert response_1.searched_at
    assert response_2.searched_at
    # Both runs performed their own fresh provider calls; nothing was cached.
    assert len(provider.calls) >= 2 * len(response_1.queries_used)


@pytest.mark.asyncio
async def test_one_failed_source_does_not_break_the_search(monkeypatch):
    provider = FakeProvider(
        hits_by_query={
            "housing.com": [SearchHit(url="https://housing.com/l1")],
            "magicbricks.com": [SearchHit(url="https://magicbricks.com/l2")],
        },
        fail_domains={"99acres.com", "nobroker.in"},
    )
    adapter = FakeAdapter(record_factory=make_good_record)
    monkeypatch.setattr("app.orchestrator.adapter_for_url", lambda url: adapter)

    orchestrator = SearchOrchestrator(provider=provider)
    response = await orchestrator.run(SearchRequest(area="Adyar"))

    assert len(response.results) > 0
    states = {s.name: s.state.value for s in response.sources}
    assert states["99acres"] == "unavailable"
    assert states["NoBroker"] == "unavailable"


@pytest.mark.asyncio
async def test_empty_search_returns_no_results_state(monkeypatch):
    provider = FakeProvider(hits_by_query={})
    adapter = FakeAdapter(record_factory=None)
    monkeypatch.setattr("app.orchestrator.adapter_for_url", lambda url: adapter)

    orchestrator = SearchOrchestrator(provider=provider)
    response = await orchestrator.run(SearchRequest(area="Nowhereville"))

    assert response.results == []
    assert len(response.no_results_suggestions) > 0


@pytest.mark.asyncio
async def test_location_not_hard_coded_in_live_run(monkeypatch):
    seen_queries = []

    class RecordingProvider(FakeProvider):
        async def search(self, query, num_results):
            seen_queries.append(query)
            return []

    provider = RecordingProvider()
    monkeypatch.setattr("app.orchestrator.adapter_for_url", lambda url: FakeAdapter())

    orchestrator = SearchOrchestrator(provider=provider)
    await orchestrator.run(SearchRequest(area="Koramangala"))

    assert all("velachery" not in q.lower() and "adyar" not in q.lower() for q in seen_queries)
    assert any("koramangala" in q.lower() for q in seen_queries)


@pytest.mark.asyncio
async def test_fetch_and_extract_breakdown_counts_each_outcome_separately(monkeypatch):
    """Discovering candidate URLs and turning them into usable records are
    different pipeline stages with different failure modes (network fetch
    vs. extraction exclusion) - the stats must distinguish them instead of
    collapsing everything into one "found nothing" number."""
    ok_url = "https://housing.com/ok"
    failed_url = "https://housing.com/fails"
    excluded_url = "https://housing.com/pg"

    provider = FakeProvider(hits_by_query={"housing.com": [
        SearchHit(url=ok_url), SearchHit(url=failed_url), SearchHit(url=excluded_url),
    ]})
    adapter = FakeAdapter(
        record_factory=make_good_record,
        fail_urls={failed_url},
        exclude_urls={excluded_url},
    )
    monkeypatch.setattr("app.orchestrator.adapter_for_url", lambda url: adapter)

    orchestrator = SearchOrchestrator(provider=provider)
    response = await orchestrator.run(SearchRequest(area="Adyar"))

    assert response.statistics.listings_discovered == 3
    assert len(response.results) == 1
    assert response.results[0].listing_url == ok_url
