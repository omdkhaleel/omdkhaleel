from app import config
from app.search_providers.bing_provider import BingProvider
from app.search_providers.brave_provider import BraveProvider
from app.search_providers.duckduckgo_provider import DuckDuckGoProvider
from app.search_providers.factory import get_search_provider


def test_defaults_to_duckduckgo(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PROVIDER", "duckduckgo")
    assert isinstance(get_search_provider(), DuckDuckGoProvider)


def test_bing_selected_with_api_key(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PROVIDER", "bing")
    monkeypatch.setattr(config, "SEARCH_PROVIDER_API_KEY", "test-key")
    assert isinstance(get_search_provider(), BingProvider)


def test_brave_selected_with_api_key(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PROVIDER", "brave")
    monkeypatch.setattr(config, "SEARCH_PROVIDER_API_KEY", "test-key")
    assert isinstance(get_search_provider(), BraveProvider)


def test_falls_back_to_duckduckgo_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "SEARCH_PROVIDER", "brave")
    monkeypatch.setattr(config, "SEARCH_PROVIDER_API_KEY", "")
    assert isinstance(get_search_provider(), DuckDuckGoProvider)
