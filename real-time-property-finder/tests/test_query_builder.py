from app.models import BHK, BrokeragePreference, SearchRequest
from app.query_builder import PORTAL_DOMAINS, generate_queries


def make_request(**overrides):
    defaults = dict(area="Adyar")
    defaults.update(overrides)
    return SearchRequest(**defaults)


def test_different_areas_generate_different_queries():
    q1 = generate_queries(make_request(area="Adyar"))
    q2 = generate_queries(make_request(area="Velachery"))
    texts1 = {q.text for q in q1}
    texts2 = {q.text for q in q2}
    assert texts1 != texts2
    assert all("adyar" in t.lower() for t in texts1)
    assert all("velachery" in t.lower() for t in texts2)


def test_no_locality_is_hard_coded():
    queries = generate_queries(make_request(area="Adyar"))
    for q in queries:
        assert "velachery" not in q.text.lower()
        assert "koramangala" not in q.text.lower()
        assert "indiranagar" not in q.text.lower()


def test_site_queries_present_for_every_portal_domain():
    queries = generate_queries(make_request(area="Adyar"))
    text_blob = " ".join(q.text for q in queries)
    for domain in PORTAL_DOMAINS:
        assert f"site:{domain}" in text_blob


def test_queries_adapt_to_bhk_and_rent():
    req = make_request(area="Whitefield", bhk=BHK.TWO, min_rent=15000, max_rent=20000)
    queries = generate_queries(req)
    blob = " ".join(q.text for q in queries)
    assert "2 BHK" in blob
    assert "15000" in blob and "20000" in blob


def test_no_brokerage_query_only_when_requested():
    with_pref = generate_queries(make_request(area="Mylapore", brokerage=BrokeragePreference.PREFERRED))
    without_pref = generate_queries(make_request(area="Mylapore", brokerage=BrokeragePreference.ANY))
    assert any("no brokerage" in q.text.lower() for q in with_pref)
    assert not any("no brokerage" in q.text.lower() for q in without_pref)


def test_queries_are_deduplicated_and_capped():
    queries = generate_queries(make_request(area="Adyar"), max_queries=3)
    assert len(queries) <= 3
    texts = [q.text.lower() for q in queries]
    assert len(texts) == len(set(texts))
