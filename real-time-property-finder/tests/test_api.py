from fastapi.testclient import TestClient

from app.main import _orchestrator, app
from app.search_providers.base import SearchProvider

client = TestClient(app)


class NoopProvider(SearchProvider):
    name = "noop"

    async def search(self, query, num_results):
        return []


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_search_then_retrieve_by_id(monkeypatch):
    monkeypatch.setattr(_orchestrator, "_provider", NoopProvider())

    resp = client.post("/api/search", json={"area": "Adyar"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["request"]["area"] == "Adyar"

    search_id = data["search_id"]
    resp2 = client.get(f"/api/search/{search_id}")
    assert resp2.status_code == 200
    assert resp2.json()["search_id"] == search_id


def test_unknown_search_id_returns_404():
    resp = client.get("/api/search/does-not-exist")
    assert resp.status_code == 404


def test_blank_area_is_rejected_by_api():
    resp = client.post("/api/search", json={"area": "   "})
    assert resp.status_code == 422


def test_repeated_identical_search_creates_new_session(monkeypatch):
    monkeypatch.setattr(_orchestrator, "_provider", NoopProvider())

    resp1 = client.post("/api/search", json={"area": "Adyar"})
    resp2 = client.post("/api/search", json={"area": "Adyar"})
    assert resp1.json()["search_id"] != resp2.json()["search_id"]
