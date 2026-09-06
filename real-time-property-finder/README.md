# Real-Time Property Finder

A lightweight, local-first web app that searches the live web — right when
you click Search — for currently available residential rental properties
matching your requirements, and shows them ranked in your browser.

There is no property database. Every result is discovered, fetched, and
normalized in real time during that one search; nothing is preloaded,
cached across searches, or reused from an earlier run.

## 1. Requirements

- **Python 3.10 or newer** (3.11/3.12 also work).
- An internet connection when you click Search — the app itself runs
  entirely on your machine, but it needs to reach the public web to find
  listings.

## 2. Starting the application

**Windows:** double-click `run.bat` (or run it from a terminal).

**macOS / Linux:** run `./run.sh` from a terminal.

Either script will, the first time:
1. Check that Python is installed.
2. Create a local virtual environment (`.venv`).
3. Install the dependencies from `requirements.txt`.
4. Start the backend server.
5. Wait for it to report healthy.
6. Open your default browser to the app automatically.

On later runs it reuses the same virtual environment, so startup is fast.

## 3. Stopping the application

Close the terminal window running the script, or press `Ctrl+C` in it.

## 4. Local URL

By default the app runs at **http://localhost:8000**. If port 8000 is
already in use, it automatically tries the next few ports (8001, 8002, ...)
and opens your browser at whichever one it actually started on.

## 5. Optional configuration / API keys

None are required — the default search provider (DuckDuckGo's public
results page) needs no key at all.

If you'd rather use the Bing Web Search API, copy `.env.example` to `.env`
in the project root and set:

```
SEARCH_PROVIDER=bing
SEARCH_PROVIDER_API_KEY=your-key-here
```

Any key you set here stays on the backend — it is never sent to, or
readable from, the browser.

## 6. Internet requirement

The app needs outbound internet access at the moment you click **Search
Live Properties**: it generates search queries, hits a search provider,
fetches candidate property pages, and extracts data from them, all live.
Without internet access, searches will complete with zero results and the
sources panel will show every source as unavailable — this is the app
correctly refusing to invent data, not a bug.

## 7. Supported search sources

Query generation specifically targets:
- Housing.com
- NoBroker
- Magicbricks
- 99acres

Any other publicly indexed listing page turned up by the general (non
`site:`) queries is also fetched and parsed through a generic extractor.

## 8. Known limitations of individual portals

- Portal markup changes often and isn't consistent between listings, so
  extraction relies on Open Graph tags, embedded JSON-LD, and text
  pattern-matching rather than fixed CSS selectors — some fields will
  come back as "Not verified" / "Not publicly available" even for a real,
  active listing if the page simply didn't expose them in a
  machine-readable way.
- Sites that require login, block automated clients, or gate content
  behind CAPTCHA/heavy client-side JavaScript are not bypassed — the app
  marks that source unavailable/degraded for the search and continues
  with whatever else it could reach.
- A search engine or portal rate-limiting or temporarily blocking
  requests (common for shared/datacenter IPs, including inside some
  sandboxed or corporate networks) will show up as that source being
  unavailable for that search. Running the app from a normal home/office
  connection avoids this in most cases.
- Contact numbers, exact deposit/maintenance figures, and posted/updated
  dates are only ever filled in when the source page states them
  explicitly — they are never guessed.

## 9. How the live-search architecture works

```
Search inputs (frontend)
        │
        ▼
 POST /api/search  ──────────────────────────────────────────────┐
        │                                                          │
        ▼                                                          │
 query_builder.generate_queries()   — builds several complementary │
        │                              queries from the actual     │
        │                              request (no hard-coded      │
        │                              city/locality)              │
        ▼                                                          │
 SearchProvider.search()            — pluggable web-search backend │
        │                              (DuckDuckGo by default, or  │
        │                              Bing if configured)         │
        ▼                                                          │
 adapter_for_url() → PortalAdapter  — one adapter per known portal │
        │                              (Housing.com, NoBroker,     │
        │                              Magicbricks, 99acres) plus  │
        │                              a generic fallback adapter  │
        ▼                                                          │
 fetch() + extract()                — fetches the page, pulls      │
        │                              structured fields from      │
        │                              JSON-LD / meta tags / text  │
        ▼                                                          │
 filters.filter_candidates()        — hard filters: rent range,    │
        │                              BHK, property type,         │
        │                              location relevance,         │
        │                              PG/commercial exclusion     │
        ▼                                                          │
 dedup.deduplicate()                — multi-signal duplicate       │
        │                              detection across portals    │
        ▼                                                          │
 ranking.rank()                     — 0-100 match score, A/B/C     │
        │                              priority                    │
        ▼                                                          │
 SearchResponse ───────────────────────────────────────────────────┘
        │
        ▼
   Results page (frontend)
```

Every one of those steps runs fresh on every `POST /api/search` call. The
only persistent state is a small, in-memory, session-scoped store that
lets `GET /api/search/{search_id}` return a search's own results again
(e.g. if the page is refreshed) — it is capped in size, cleared on
restart, and never consulted as a source of new search results.

### Adding a new search provider or portal adapter

- Search providers implement `SearchProvider.search()` in
  `backend/app/search_providers/` and are picked via
  `SEARCH_PROVIDER` in `.env`.
- Portal adapters implement `PortalAdapter.extract()` in
  `backend/app/adapters/` and are registered in `adapters/registry.py`.

Both are plugged in without touching the orchestration pipeline itself.

## Project layout

```
real-time-property-finder/
├── frontend/           Plain HTML/CSS/JS UI (no build step)
├── backend/
│   ├── app/            FastAPI app, pipeline modules
│   └── run_server.py   Local launcher (port selection, health wait, browser open)
├── tests/               Automated tests (pytest)
├── .env.example
├── requirements.txt
├── run.bat / run.sh
└── LICENSE
```

## Running the tests

```
pip install -r requirements.txt
pytest
```

Tests cover query generation (including that different areas produce
different, non-hard-coded queries), filtering, deduplication, ranking,
and the search pipeline's resilience to source failures and empty
results — using fake providers/adapters so they run without needing a
live internet connection.
