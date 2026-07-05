# Live Source Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conservative source URL discovery, manual URL registration, user-triggered HTML caching, and UI/CLI controls for BetExplorer/OddsPortal source links.

**Architecture:** Keep the current saved-HTML analysis path as the stable core. Add small source-discovery and source-fetch services that update existing `fixture_source_links` and `source_fetches` tables, then expose them through CLI and FastAPI endpoints. Live HTTP is best-effort and injected behind testable callables; automated tests use local fixture HTML or fake responses only.

**Tech Stack:** Python 3.11+, SQLite, httpx, BeautifulSoup, Typer, FastAPI, Jinja2, pytest.

---

## Scope Check

This plan implements `docs/superpowers/specs/2026-07-05-live-source-discovery-design.md`.

It includes:

- Manual registration of BetExplorer/OddsPortal URLs for seeded fixtures.
- Fixture listing HTML parsing plus best-effort default listing fetch to discover source links by team names.
- User-triggered URL fetching into ignored `data/cache`.
- Parser sanity checks before marking a source link `available`.
- CLI commands and UI endpoints/controls.
- Documentation and smoke verification.

It does not include:

- Login, CAPTCHA solving, paid pages, anti-bot bypass, browser-extension automation, background polling, or automated betting.
- Tests that depend on live source availability.

## File Structure

- `src/handicap_ai/source_discovery.py`: source URL registration, fixture lookup, default listing fetch, fixture-listing link parsing, source status result models.
- `tests/test_source_discovery.py`: URL registration and fixture-listing discovery tests.
- `tests/fixtures/source_listing_betexplorer.html`: local fixture listing containing an England/Ghana link.
- `tests/fixtures/source_listing_oddsportal.html`: local fixture listing containing an England/Ghana link.
- `src/handicap_ai/source_fetch.py`: fetch response models, httpx fetcher, cache writer, parser sanity checks, fixture source-link updates.
- `tests/test_source_fetch.py`: fetch/cache/status tests with fake HTTP responses.
- `src/handicap_ai/cli.py`: add `register-source-url`, `discover-sources`, and `fetch-source-html`.
- `tests/test_source_cli.py`: CLI coverage for register, local listing discovery, local response fetch.
- `src/handicap_ai/ui.py`: add request models and API endpoints for source registration/discovery/fetch.
- `tests/test_ui.py`: API endpoint tests for source controls.
- `src/handicap_ai/templates/dashboard.html`: add source rows, manual URL input, discover/register/fetch JS.
- `src/handicap_ai/static/dashboard.css`: add compact source-control styling.
- `README.md`: document source discovery, fetch cache, and saved-HTML fallback.

## Task 1: Add Source Discovery Service

**Files:**
- Create: `src/handicap_ai/source_discovery.py`
- Create: `tests/test_source_discovery.py`
- Create: `tests/fixtures/source_listing_betexplorer.html`
- Create: `tests/fixtures/source_listing_oddsportal.html`

- [ ] **Step 1: Add fixture-listing HTML files**

Create `tests/fixtures/source_listing_betexplorer.html`:

```html
<!doctype html>
<html>
  <body>
    <main data-source-listing="betexplorer">
      <a href="/football/world/world-championship-2026/england-ghana/KhgvzGjJ/">England - Ghana</a>
      <a href="/football/world/world-championship-2026/croatia-panama/abc123/">Croatia - Panama</a>
    </main>
  </body>
</html>
```

Create `tests/fixtures/source_listing_oddsportal.html`:

```html
<!doctype html>
<html>
  <body>
    <main data-source-listing="oddsportal">
      <a href="/football/world/world-championship-2026/england-ghana/">England v Ghana</a>
      <a href="/football/world/world-championship-2026/croatia-panama/">Croatia v Panama</a>
    </main>
  </body>
</html>
```

- [ ] **Step 2: Write failing discovery tests**

Create `tests/test_source_discovery.py`:

```python
from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_discovery import (
    DiscoveryHttpResponse,
    SourceLinkStatus,
    discover_fixture_source,
    discover_fixture_source_from_listing,
    register_fixture_source_url,
)
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def fake_listing_get(html: str, status_code: int = 200):
    def _get(url: str) -> DiscoveryHttpResponse:
        return DiscoveryHttpResponse(url=url, status_code=status_code, text=html)

    return _get


def test_register_fixture_source_url_updates_candidate_link(tmp_path):
    db = seeded_db(tmp_path)

    result = register_fixture_source_url(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        url="https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url.endswith("/england-ghana/KhgvzGjJ/")
    fixtures = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")
    links = db.list_fixture_source_links(int(fixtures[0]["fixture_id"]))
    assert links[0]["source"] == "betexplorer"
    assert links[0]["status"] == "pending"
    assert links[0]["url"] == result.url
    assert links[0]["html_path"] is None


def test_discover_fixture_source_from_betexplorer_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html=html,
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/"


def test_discover_fixture_source_from_oddsportal_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_oddsportal.html").read_text(encoding="utf-8")

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="oddsportal",
        listing_html=html,
        base_url="https://www.oddsportal.com",
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.oddsportal.com/football/world/world-championship-2026/england-ghana/"


def test_discover_fixture_source_fetches_default_listing(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get(html),
    )

    assert result.status is SourceLinkStatus.PENDING
    assert result.url == "https://www.betexplorer.com/football/world/world-championship-2026/england-ghana/KhgvzGjJ/"


def test_discover_fixture_source_marks_blocked_when_listing_blocked(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        http_get=fake_listing_get("<html>captcha required</html>", status_code=403),
    )

    assert result.status is SourceLinkStatus.BLOCKED
    assert result.url is None
    assert "blocked" in result.warnings[0]


def test_discovery_reports_manual_required_when_no_listing_match(tmp_path):
    db = seeded_db(tmp_path)

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html="<html><a href='/other'>Brazil - Morocco</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.MANUAL_REQUIRED
    assert result.url is None
    assert "No source URL found for England vs Ghana" in result.warnings


def test_discovery_failure_does_not_overwrite_available_source_link(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Ghana")[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="data/cache/betexplorer/england-ghana.html",
        url="https://example.test/england-ghana",
        status="available",
    )

    result = discover_fixture_source_from_listing(
        db,
        home_team="England",
        away_team="Ghana",
        source="betexplorer",
        listing_html="<html><a href='/other'>Brazil - Morocco</a></html>",
        base_url="https://www.betexplorer.com",
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    assert result.html_path == "data/cache/betexplorer/england-ghana.html"
    assert result.url == "https://example.test/england-ghana"
    assert "No source URL found for England vs Ghana" in result.warnings
```

- [ ] **Step 3: Run discovery tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_source_discovery.py -v
```

Expected: FAIL with missing `handicap_ai.source_discovery`.

- [ ] **Step 4: Implement source discovery service**

Create `src/handicap_ai/source_discovery.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


class SourceLinkStatus(str, Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    BLOCKED = "blocked"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True)
class SourceLinkResult:
    fixture_id: int | None
    source: str
    status: SourceLinkStatus
    url: str | None
    html_path: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryHttpResponse:
    url: str
    status_code: int | None
    text: str
    error_message: str | None = None


DEFAULT_LISTING_URLS = {
    "betexplorer": "https://www.betexplorer.com/football/world/world-championship-2026/fixtures/",
    "oddsportal": "https://www.oddsportal.com/football/world/world-championship-2026/",
}


def default_listing_get(url: str) -> DiscoveryHttpResponse:
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "handicap-ai/0.1"})
        return DiscoveryHttpResponse(url=str(response.url), status_code=response.status_code, text=response.text)
    except httpx.HTTPError as exc:
        return DiscoveryHttpResponse(url=url, status_code=None, text="", error_message=str(exc))


def register_fixture_source_url(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    url: str,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source=source,
        html_path=None,
        url=url,
        status=SourceLinkStatus.PENDING.value,
    )
    return SourceLinkResult(
        fixture_id=fixture_id,
        source=source,
        status=SourceLinkStatus.PENDING,
        url=url,
        html_path=None,
    )


def discover_fixture_source(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    http_get=default_listing_get,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    source_key = source.lower()
    listing_url = DEFAULT_LISTING_URLS.get(source_key)
    if listing_url is None:
        raise ValueError(f"unsupported source: {source}")

    response = http_get(listing_url)
    status, warning = _listing_fetch_status(response)
    if status is not SourceLinkStatus.PENDING:
        preserved = _available_result(db, fixture_id, source, warning)
        if preserved is not None:
            return preserved
        db.upsert_fixture_source_link(
            fixture_id=fixture_id,
            source=source,
            html_path=None,
            url=None,
            status=status.value,
        )
        return SourceLinkResult(
            fixture_id=fixture_id,
            source=source,
            status=status,
            url=None,
            html_path=None,
            warnings=(warning,),
        )

    parsed = urlparse(response.url or listing_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return discover_fixture_source_from_listing(
        db,
        home_team=home_team,
        away_team=away_team,
        source=source,
        listing_html=response.text,
        base_url=base_url,
        season=season,
    )


def discover_fixture_source_from_listing(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    listing_html: str,
    base_url: str,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    found_url = _find_listing_url(
        listing_html=listing_html,
        base_url=base_url,
        home_team=fixture["home_team"],
        away_team=fixture["away_team"],
    )
    if found_url is None:
        warning = f"No source URL found for {fixture['home_team']} vs {fixture['away_team']}"
        preserved = _available_result(db, fixture_id, source, warning)
        if preserved is not None:
            return preserved
        db.upsert_fixture_source_link(
            fixture_id=fixture_id,
            source=source,
            html_path=None,
            url=None,
            status=SourceLinkStatus.MANUAL_REQUIRED.value,
        )
        return SourceLinkResult(
            fixture_id=fixture_id,
            source=source,
            status=SourceLinkStatus.MANUAL_REQUIRED,
            url=None,
            html_path=None,
            warnings=(warning,),
        )
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source=source,
        html_path=None,
        url=found_url,
        status=SourceLinkStatus.PENDING.value,
    )
    return SourceLinkResult(
        fixture_id=fixture_id,
        source=source,
        status=SourceLinkStatus.PENDING,
        url=found_url,
        html_path=None,
    )


def _single_fixture(db: Database, home_team: str, away_team: str, season: str):
    fixtures = db.find_tournament_fixtures(
        tournament=FIFA_WORLD_CUP,
        season=season,
        home_team=home_team,
        away_team=away_team,
    )
    if not fixtures:
        raise ValueError(f"no seeded fixture found for {home_team} vs {away_team}")
    if len(fixtures) > 1:
        raise ValueError(f"multiple seeded fixtures found for {home_team} vs {away_team}")
    return fixtures[0]


def _available_result(
    db: Database,
    fixture_id: int,
    source: str,
    warning: str,
) -> SourceLinkResult | None:
    existing = _source_link(db, fixture_id, source)
    if existing is None or existing["status"] != SourceLinkStatus.AVAILABLE.value:
        return None
    return SourceLinkResult(
        fixture_id=fixture_id,
        source=source,
        status=SourceLinkStatus.AVAILABLE,
        url=existing["url"],
        html_path=existing["html_path"],
        warnings=(warning,),
    )


def _source_link(db: Database, fixture_id: int, source: str):
    for link in db.list_fixture_source_links(fixture_id):
        if link["source"] == source:
            return link
    return None


def _find_listing_url(
    listing_html: str,
    base_url: str,
    home_team: str,
    away_team: str,
) -> str | None:
    home = normalize_team_name(home_team)
    away = normalize_team_name(away_team)
    soup = BeautifulSoup(listing_html, "html.parser")
    for link in soup.select("a[href]"):
        text = normalize_team_name(link.get_text(" ", strip=True))
        href = link.get("href")
        if not href:
            continue
        if home in text and away in text:
            return urljoin(base_url, href)
    return None


def _listing_fetch_status(response: DiscoveryHttpResponse) -> tuple[SourceLinkStatus, str]:
    if response.error_message:
        return SourceLinkStatus.FAILED, response.error_message
    if response.status_code in {401, 402, 403, 429}:
        return SourceLinkStatus.BLOCKED, "listing fetch blocked by source"
    lowered = response.text.lower()
    if "captcha" in lowered or "access denied" in lowered or "login" in lowered:
        return SourceLinkStatus.BLOCKED, "listing fetch blocked by source"
    if response.status_code is None or response.status_code >= 400:
        return SourceLinkStatus.FAILED, f"listing fetch failed with status {response.status_code}"
    return SourceLinkStatus.PENDING, ""
```

- [ ] **Step 5: Run discovery tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_source_discovery.py tests/test_candidate_search.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/handicap_ai/source_discovery.py tests/test_source_discovery.py tests/fixtures/source_listing_betexplorer.html tests/fixtures/source_listing_oddsportal.html
git commit -m "feat: add fixture source discovery"
```

## Task 2: Add Source Fetch Cache Service

**Files:**
- Create: `src/handicap_ai/source_fetch.py`
- Create: `tests/test_source_fetch.py`

- [ ] **Step 1: Write failing fetch tests**

Create `tests/test_source_fetch.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.source_discovery import SourceLinkStatus, register_fixture_source_url
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    register_fixture_source_url(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        url="https://example.test/england-panama",
    )
    return db


def fake_get(html: str, status_code: int = 200):
    def _get(url: str) -> FetchHttpResponse:
        return FetchHttpResponse(url=url, status_code=status_code, text=html, error_message=None)

    return _get


def test_fetch_fixture_source_html_caches_available_html(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(html),
    )

    assert result.status is SourceLinkStatus.AVAILABLE
    assert result.html_path is not None
    assert Path(result.html_path).is_file()
    assert db.list_source_fetches("betexplorer")[0]["status_code"] == 200
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Panama")[0]
    link = db.list_fixture_source_links(int(fixture["fixture_id"]))[0]
    assert link["status"] == "available"
    assert link["html_path"] == result.html_path


def test_fetch_fixture_source_html_marks_blocked_without_overwriting_available(tmp_path):
    db = seeded_db(tmp_path)
    good_html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    first = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get(good_html),
    )

    blocked = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get("<html>captcha required</html>", status_code=403),
    )

    assert blocked.status is SourceLinkStatus.BLOCKED
    fixture = db.find_tournament_fixtures("fifa_world_cup", "2026", "England", "Panama")[0]
    link = db.list_fixture_source_links(int(fixture["fixture_id"]))[0]
    assert link["status"] == "available"
    assert link["html_path"] == first.html_path


def test_fetch_fixture_source_html_rejects_malformed_html(tmp_path):
    db = seeded_db(tmp_path)

    result = fetch_fixture_source_html(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        http_get=fake_get("<html>not a match page</html>"),
    )

    assert result.status is SourceLinkStatus.FAILED
    assert "missing BetExplorer match container" in result.warnings[0]
```

- [ ] **Step 2: Run fetch tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_source_fetch.py -v
```

Expected: FAIL with missing `handicap_ai.source_fetch`.

- [ ] **Step 3: Implement fetch service**

Create `src/handicap_ai/source_fetch.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

import httpx

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter
from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter
from handicap_ai.database import Database
from handicap_ai.scraping.models import SourceFetchRecord
from handicap_ai.source_discovery import SourceLinkResult, SourceLinkStatus
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


@dataclass(frozen=True)
class FetchHttpResponse:
    url: str
    status_code: int | None
    text: str
    error_message: str | None = None


def default_http_get(url: str) -> FetchHttpResponse:
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "handicap-ai/0.1"})
        return FetchHttpResponse(url=str(response.url), status_code=response.status_code, text=response.text)
    except httpx.HTTPError as exc:
        return FetchHttpResponse(url=url, status_code=None, text="", error_message=str(exc))


def fetch_fixture_source_html(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    cache_dir: Path = Path("data/cache"),
    http_get=default_http_get,
    season: str = SEASON_2026,
) -> SourceLinkResult:
    fixture = _single_fixture(db, home_team, away_team, season)
    fixture_id = int(fixture["fixture_id"])
    existing = _source_link(db, fixture_id, source)
    if existing is None or not existing["url"]:
        raise ValueError(f"no registered URL for {source} {home_team} vs {away_team}")

    url = existing["url"]
    response = http_get(url)
    content_hash = sha256(response.text.encode("utf-8")).hexdigest() if response.text else None
    status = _response_status(response)
    cache_path: Path | None = None
    warning: str | None = response.error_message
    if warning is None and status is SourceLinkStatus.BLOCKED:
        warning = "source fetch blocked by site response"
    elif warning is None and status is SourceLinkStatus.FAILED:
        warning = f"source fetch failed with status {response.status_code}"

    if status is SourceLinkStatus.PENDING:
        cache_path = _cache_path(cache_dir, source, fixture_id, url, response.text)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(response.text, encoding="utf-8")
        parse_warning = _parse_warning(source, response.text)
        if parse_warning:
            status = SourceLinkStatus.FAILED
            warning = parse_warning
        else:
            status = SourceLinkStatus.AVAILABLE

    db.upsert_source_fetch(
        SourceFetchRecord(
            source=source,
            url=url,
            fetched_at=datetime.now(timezone.utc),
            status_code=response.status_code,
            cache_path=str(cache_path) if cache_path else None,
            content_hash=content_hash,
            error_message=warning,
        )
    )

    if status is SourceLinkStatus.AVAILABLE and cache_path is not None:
        db.upsert_fixture_source_link(
            fixture_id=fixture_id,
            source=source,
            html_path=str(cache_path),
            url=url,
            status=status.value,
        )
        html_path = str(cache_path)
    else:
        html_path = existing["html_path"]
        if existing["status"] != SourceLinkStatus.AVAILABLE.value:
            db.upsert_fixture_source_link(
                fixture_id=fixture_id,
                source=source,
                html_path=html_path,
                url=url,
                status=status.value,
            )

    return SourceLinkResult(
        fixture_id=fixture_id,
        source=source,
        status=status,
        url=url,
        html_path=html_path,
        warnings=(warning,) if warning else (),
    )


def _response_status(response: FetchHttpResponse) -> SourceLinkStatus:
    if response.error_message:
        return SourceLinkStatus.FAILED
    if response.status_code in {401, 402, 403, 429}:
        return SourceLinkStatus.BLOCKED
    lowered = response.text.lower()
    if "captcha" in lowered or "access denied" in lowered or "login" in lowered:
        return SourceLinkStatus.BLOCKED
    if response.status_code is None or response.status_code >= 400:
        return SourceLinkStatus.FAILED
    return SourceLinkStatus.PENDING


def _parse_warning(source: str, html: str) -> str | None:
    try:
        if source == "betexplorer":
            _bundle, coverage = BetExplorerHtmlAdapter(Path("unused")).parse_html(html)
        elif source == "oddsportal":
            _bundle, coverage = OddsPortalHtmlAdapter(Path("unused")).parse_html(html)
        else:
            return f"unsupported source: {source}"
    except ValueError as exc:
        return str(exc)
    if not coverage.is_complete:
        return f"scraped markets are incomplete: {', '.join(coverage.missing_markets)}"
    return None


def _cache_path(cache_dir: Path, source: str, fixture_id: int, url: str, html: str) -> Path:
    digest = sha256(f"{url}\n{html}".encode("utf-8")).hexdigest()[:12]
    safe_source = re.sub(r"[^a-z0-9_-]+", "-", source.lower()).strip("-")
    return Path(cache_dir) / safe_source / f"fixture-{fixture_id}-{digest}.html"


def _single_fixture(db: Database, home_team: str, away_team: str, season: str):
    rows = db.find_tournament_fixtures(FIFA_WORLD_CUP, season, home_team, away_team)
    if not rows:
        raise ValueError(f"no seeded fixture found for {home_team} vs {away_team}")
    return rows[0]


def _source_link(db: Database, fixture_id: int, source: str):
    for link in db.list_fixture_source_links(fixture_id):
        if link["source"] == source:
            return link
    return None
```

- [ ] **Step 4: Run fetch tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_source_fetch.py tests/test_source_discovery.py -q
```

Expected: PASS.

- [ ] **Step 5: Run scraping-related tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_betexplorer_adapter.py tests/test_oddsportal_adapter.py tests/test_source_fetch.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/handicap_ai/source_fetch.py tests/test_source_fetch.py
git commit -m "feat: cache fixture source html"
```

## Task 3: Add Source CLI Commands

**Files:**
- Modify: `src/handicap_ai/cli.py`
- Create: `tests/test_source_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_source_cli.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from handicap_ai.cli import app


def seed_db(runner: CliRunner, db_path: Path):
    result = runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])
    assert result.exit_code == 0


def test_register_source_url_command(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_db(runner, db_path)

    result = runner.invoke(
        app,
        [
            "register-source-url",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Ghana",
            "--source",
            "betexplorer",
            "--url",
            "https://example.test/england-ghana",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: pending" in result.output
    assert "url=https://example.test/england-ghana" in result.output


def test_discover_sources_command_uses_listing_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    seed_db(runner, db_path)

    result = runner.invoke(
        app,
        [
            "discover-sources",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Ghana",
            "--source",
            "betexplorer",
            "--listing-html",
            "tests/fixtures/source_listing_betexplorer.html",
            "--base-url",
            "https://www.betexplorer.com",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: pending" in result.output
    assert "england-ghana/KhgvzGjJ/" in result.output


def test_fetch_source_html_command_uses_local_response_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    cache_dir = tmp_path / "cache"
    runner = CliRunner()
    seed_db(runner, db_path)
    register = runner.invoke(
        app,
        [
            "register-source-url",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Panama",
            "--source",
            "betexplorer",
            "--url",
            "https://example.test/england-panama",
        ],
    )
    assert register.exit_code == 0

    result = runner.invoke(
        app,
        [
            "fetch-source-html",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Panama",
            "--source",
            "betexplorer",
            "--cache-dir",
            str(cache_dir),
            "--response-html",
            "tests/fixtures/betexplorer_match.html",
        ],
    )

    assert result.exit_code == 0
    assert "betexplorer: available" in result.output
    assert "html=" in result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_source_cli.py -v
```

Expected: FAIL because CLI commands do not exist.

- [ ] **Step 3: Add CLI imports**

Modify `src/handicap_ai/cli.py` imports:

```python
from handicap_ai.source_discovery import (
    discover_fixture_source,
    discover_fixture_source_from_listing,
    register_fixture_source_url,
)
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
```

- [ ] **Step 4: Add source CLI helper and commands**

Add this helper before `_similar_matches`:

```python
def _print_source_result(result) -> None:
    details = [f"{result.source}: {result.status.value}"]
    if result.html_path:
        details.append(f"html={result.html_path}")
    if result.url:
        details.append(f"url={result.url}")
    console.print(" ".join(details))
    for warning in result.warnings:
        console.print(f"Warning: {warning}")
```

Add commands before `analyze`:

```python
@app.command("register-source-url")
def register_source_url(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    url: str = typer.Option(..., "--url"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    result = register_fixture_source_url(database, home, away, source, url)
    _print_source_result(result)


@app.command("discover-sources")
def discover_sources(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    listing_html: Path | None = typer.Option(None, "--listing-html"),
    base_url: str | None = typer.Option(None, "--base-url"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    if listing_html is None:
        result = discover_fixture_source(
            database,
            home_team=home,
            away_team=away,
            source=source,
        )
    else:
        if base_url is None:
            raise typer.BadParameter("--base-url is required with --listing-html")
        html = Path(listing_html).read_text(encoding="utf-8")
        result = discover_fixture_source_from_listing(
            database,
            home_team=home,
            away_team=away,
            source=source,
            listing_html=html,
            base_url=base_url,
        )
    _print_source_result(result)


@app.command("fetch-source-html")
def fetch_source_html(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    cache_dir: Path = typer.Option(Path("data/cache"), "--cache-dir"),
    response_html: Path | None = typer.Option(None, "--response-html"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    http_get = None
    if response_html is not None:
        html = Path(response_html).read_text(encoding="utf-8")

        def http_get(url: str) -> FetchHttpResponse:
            return FetchHttpResponse(url=url, status_code=200, text=html)

    kwargs = {"http_get": http_get} if http_get is not None else {}
    result = fetch_fixture_source_html(
        database,
        home_team=home,
        away_team=away,
        source=source,
        cache_dir=cache_dir,
        **kwargs,
    )
    _print_source_result(result)
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_source_cli.py tests/test_world_cup_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Run broader CLI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_cli.py tests/test_scrape_cli.py tests/test_ui_cli.py tests/test_source_cli.py tests/test_world_cup_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add src/handicap_ai/cli.py tests/test_source_cli.py
git commit -m "feat: add fixture source cli commands"
```

## Task 4: Add Source API Endpoints

**Files:**
- Modify: `src/handicap_ai/ui.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Write failing API tests**

Append to `tests/test_ui.py`:

```python
def test_register_source_url_endpoint_updates_candidate(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Ghana",
            "source": "betexplorer",
            "url": "https://example.test/england-ghana",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "betexplorer"
    assert body["status"] == "pending"
    assert body["url"] == "https://example.test/england-ghana"


def test_discover_sources_endpoint_uses_listing_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(encoding="utf-8")

    response = client.post(
        "/api/discover-sources",
        json={
            "home_team": "England",
            "away_team": "Ghana",
            "source": "betexplorer",
            "listing_html": html,
            "base_url": "https://www.betexplorer.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert "england-ghana/KhgvzGjJ/" in body["url"]


def test_fetch_source_html_endpoint_uses_response_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)
    client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "url": "https://example.test/england-panama",
        },
    )
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    response = client.post(
        "/api/fetch-source-html",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "response_html": html,
            "cache_dir": str(tmp_path / "cache"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert Path(body["html_path"]).is_file()
```

- [ ] **Step 2: Run UI tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py -v
```

Expected: FAIL with 404 for new endpoints.

- [ ] **Step 3: Add UI imports and request models**

Change the existing `from fastapi import FastAPI` import in `src/handicap_ai/ui.py`, then add the source-service imports:

```python
from fastapi import FastAPI, HTTPException

from handicap_ai.source_discovery import (
    SourceLinkResult,
    discover_fixture_source,
    discover_fixture_source_from_listing,
    register_fixture_source_url,
)
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
```

Add models near the existing request models:

```python
class SourceUrlRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
    url: str


class SourceDiscoveryRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
    listing_html: str | None = None
    base_url: str | None = None


class SourceFetchRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
    cache_dir: str = "data/cache"
    response_html: str | None = None
```

Add helper:

```python
def _source_link_payload(result: SourceLinkResult) -> dict[str, object]:
    return {
        "fixture_id": result.fixture_id,
        "source": result.source,
        "status": result.status.value,
        "url": result.url,
        "html_path": result.html_path,
        "warnings": list(result.warnings),
    }
```

- [ ] **Step 4: Add source endpoints**

Inside `create_app`, add:

```python
    @app.post("/api/register-source-url")
    def register_source_url_endpoint(payload: SourceUrlRequest):
        result = register_fixture_source_url(
            database,
            home_team=payload.home_team,
            away_team=payload.away_team,
            source=payload.source,
            url=payload.url,
        )
        return _source_link_payload(result)

    @app.post("/api/discover-sources")
    def discover_sources_endpoint(payload: SourceDiscoveryRequest):
        if payload.listing_html is None:
            result = discover_fixture_source(
                database,
                home_team=payload.home_team,
                away_team=payload.away_team,
                source=payload.source,
            )
        else:
            if payload.base_url is None:
                raise HTTPException(status_code=400, detail="base_url is required with listing_html")
            result = discover_fixture_source_from_listing(
                database,
                home_team=payload.home_team,
                away_team=payload.away_team,
                source=payload.source,
                listing_html=payload.listing_html,
                base_url=payload.base_url,
            )
        return _source_link_payload(result)

    @app.post("/api/fetch-source-html")
    def fetch_source_html_endpoint(payload: SourceFetchRequest):
        http_get = None
        if payload.response_html is not None:
            def http_get(url: str) -> FetchHttpResponse:
                return FetchHttpResponse(url=url, status_code=200, text=payload.response_html or "")
        kwargs = {"http_get": http_get} if http_get is not None else {}
        result = fetch_fixture_source_html(
            database,
            home_team=payload.home_team,
            away_team=payload.away_team,
            source=payload.source,
            cache_dir=Path(payload.cache_dir),
            **kwargs,
        )
        return _source_link_payload(result)
```

- [ ] **Step 5: Run UI API tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py tests/test_source_fetch.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add src/handicap_ai/ui.py tests/test_ui.py
git commit -m "feat: add fixture source api"
```

## Task 5: Add Dashboard Source Controls

**Files:**
- Modify: `src/handicap_ai/templates/dashboard.html`
- Modify: `src/handicap_ai/static/dashboard.css`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Add failing render assertions**

Extend `test_dashboard_route_renders_workspace` in `tests/test_ui.py`:

```python
    assert "Discover sources" in response.text
    assert "Register source URL" in response.text
    assert "Fetch source HTML" in response.text
    assert "Source links" in response.text
```

- [ ] **Step 2: Run route render test to verify it fails**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py::test_dashboard_route_renders_workspace -v
```

Expected: FAIL because new source controls are not rendered.

- [ ] **Step 3: Add source controls to dashboard**

In `src/handicap_ai/templates/dashboard.html`, add this panel near the candidate confirmation panel:

```html
          <article class="panel source-links-panel">
            <div class="panel-heading">
              <span class="label">Source links</span>
              <strong id="source-link-status">Not checked</strong>
            </div>
            <div class="source-actions">
              <label for="source-url">Manual source URL</label>
              <input id="source-url" type="url" placeholder="https://www.betexplorer.com/...">
              <button id="register-source-url-button" type="button">Register source URL</button>
              <button id="discover-sources-button" type="button">Discover sources</button>
              <button id="fetch-source-html-button" type="button">Fetch source HTML</button>
            </div>
            <div id="source-link-list" class="source-link-list">
              <p>Register or discover a source URL for the selected fixture.</p>
            </div>
          </article>
```

- [ ] **Step 4: Add dashboard JavaScript for source controls**

Add variables near existing button selectors:

```js
      const registerSourceUrlButton = document.querySelector("#register-source-url-button");
      const discoverSourcesButton = document.querySelector("#discover-sources-button");
      const fetchSourceHtmlButton = document.querySelector("#fetch-source-html-button");
```

Add helpers before the existing form submit listener:

```js
      function selectedSource() {
        return document.querySelector("#source").value;
      }

      function renderSourceResult(body) {
        setText("#source-link-status", body.status);
        const list = document.querySelector("#source-link-list");
        list.replaceChildren();
        const row = document.createElement("article");
        row.className = "source-link-card";
        const title = document.createElement("strong");
        title.textContent = `${body.source}: ${body.status}`;
        const detail = document.createElement("span");
        const parts = [];
        if (body.html_path) {
          parts.push(`html=${body.html_path}`);
          document.querySelector("#html-path").value = body.html_path;
        }
        if (body.url) {
          parts.push(`url=${body.url}`);
          document.querySelector("#source-url").value = body.url;
        }
        if (body.warnings && body.warnings.length) {
          parts.push(body.warnings.join("; "));
        }
        detail.textContent = parts.length ? parts.join(" ") : "No source URL yet";
        row.append(title, detail);
        list.appendChild(row);
      }

      async function postSourceAction(path, payload) {
        const response = await fetch(path, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const body = await response.json();
        renderSourceResult(body);
        return body;
      }

      registerSourceUrlButton.addEventListener("click", async () => {
        try {
          message.textContent = "Registering source URL";
          await postSourceAction("/api/register-source-url", {
            home_team: document.querySelector("#home-team").value,
            away_team: document.querySelector("#away-team").value,
            source: selectedSource(),
            url: document.querySelector("#source-url").value,
          });
          message.textContent = "Source URL registered";
        } catch (error) {
          message.textContent = error.message;
          setText("#source-link-status", "Error");
        }
      });

      discoverSourcesButton.addEventListener("click", async () => {
        try {
          message.textContent = "Discovering source URL";
          await postSourceAction("/api/discover-sources", {
            home_team: document.querySelector("#home-team").value,
            away_team: document.querySelector("#away-team").value,
            source: selectedSource(),
          });
          message.textContent = "Source discovery finished";
        } catch (error) {
          message.textContent = error.message;
          setText("#source-link-status", "Error");
        }
      });

      fetchSourceHtmlButton.addEventListener("click", async () => {
        try {
          message.textContent = "Fetching source HTML";
          await postSourceAction("/api/fetch-source-html", {
            home_team: document.querySelector("#home-team").value,
            away_team: document.querySelector("#away-team").value,
            source: selectedSource(),
            cache_dir: "data/cache",
          });
          message.textContent = "Source HTML fetched";
        } catch (error) {
          message.textContent = error.message;
          setText("#source-link-status", "Error");
        }
      });
```

- [ ] **Step 5: Add source CSS**

Append to `src/handicap_ai/static/dashboard.css`:

```css
.source-actions,
.source-link-list {
  display: grid;
  gap: 10px;
}

.source-link-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 6px;
  overflow-wrap: anywhere;
  padding: 12px;
}

.source-link-card span {
  color: var(--muted);
}

#register-source-url-button,
#discover-sources-button,
#fetch-source-html-button {
  background: #334155;
}

#register-source-url-button:hover,
#register-source-url-button:focus-visible,
#discover-sources-button:hover,
#discover-sources-button:focus-visible,
#fetch-source-html-button:hover,
#fetch-source-html-button:focus-visible {
  background: #1f2937;
}
```

- [ ] **Step 6: Run UI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add src/handicap_ai/templates/dashboard.html src/handicap_ai/static/dashboard.css tests/test_ui.py
git commit -m "feat: add dashboard source controls"
```

## Task 6: Documentation and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add this section after `Seed World Cup Candidates`:

```markdown
## Discover and Cache Source HTML

```bash
handicap-ai discover-sources --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer
handicap-ai register-source-url --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer --url https://example.test/match
handicap-ai fetch-source-html --db data/handicap_ai.sqlite --home England --away Ghana --source betexplorer
```

Source discovery and fetching are user-triggered. If a site blocks automated
access, paste a manually saved HTML path in the dashboard and use the saved-HTML
analysis flow.
```

Update `Source Boundaries` to mention that live fetching is best-effort and
does not bypass login, paywalls, CAPTCHA, or anti-bot controls.

- [ ] **Step 2: Run full test suite**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run CLI smoke**

Run:

```bash
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\live-source-discovery\src'
if (Test-Path 'data\source-smoke.sqlite') { Remove-Item -LiteralPath 'data\source-smoke.sqlite' }
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli seed-world-cup --db data/source-smoke.sqlite --season 2026
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli register-source-url --db data/source-smoke.sqlite --home England --away Panama --source betexplorer --url https://example.test/england-panama
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli fetch-source-html --db data/source-smoke.sqlite --home England --away Panama --source betexplorer --response-html tests/fixtures/betexplorer_match.html
```

Expected output includes:

```text
World Cup teams: 48
betexplorer: pending
betexplorer: available
html=
```

- [ ] **Step 4: Run UI smoke**

Start UI on a non-conflicting port:

```bash
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\live-source-discovery\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli ui --db data/source-smoke.sqlite --host 127.0.0.1 --port 8002
```

Open `http://127.0.0.1:8002` and verify:

- dashboard loads
- source controls render
- registering a manual URL updates the source status
- existing saved HTML analysis still returns all three picks

- [ ] **Step 5: Commit docs**

```bash
git add README.md
git commit -m "docs: document source discovery workflow"
```

## Final Verification

- [ ] `git status --short --ignored` shows no untracked source files except ignored caches/data.
- [ ] Full test suite passes.
- [ ] CLI smoke passes without live network.
- [ ] Browser smoke confirms source controls and saved-HTML fallback work.
- [ ] Final response states that live source fetching is best-effort and saved HTML remains the reliable fallback.
