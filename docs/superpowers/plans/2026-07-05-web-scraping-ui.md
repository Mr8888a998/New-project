# Web Scraping UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local browser dashboard with confirmation-wizard behavior, fixture-backed BetExplorer/OddsPortal-style parsing, scrape caching, saved-HTML import, and historical folder import.

**Architecture:** Keep the existing recommendation engine and SQLite store. Add a small scraping layer that turns source pages into normalized bundles, a service layer that reuses CLI analysis for UI and commands, and a FastAPI/Jinja local UI that remains usable when live source pages are blocked by falling back to saved HTML.

**Tech Stack:** Python 3.11+, SQLite, Typer, Rich, BeautifulSoup, httpx, FastAPI, Jinja2, Uvicorn, openpyxl, pytest.

---

## Scope Check

This plan covers one focused feature branch:

- Conservative user-triggered scraping and saved-HTML parsing.
- BetExplorer/OddsPortal-style fixture parsers.
- SQLite fetch/job metadata.
- Historical folder import for CSV and Excel.
- A local dashboard with wizard states for ambiguous or incomplete extraction.

This plan does not include automated betting, account login, CAPTCHA solving, paid-data access, background polling, or browser extension automation.

## File Structure

- `pyproject.toml`: add FastAPI, Jinja2, Uvicorn, openpyxl, and pytest UI support through existing dependency groups.
- `src/handicap_ai/scraping/models.py`: source candidates, fetch records, coverage summaries, and wizard state dataclasses.
- `src/handicap_ai/scraping/fetcher.py`: low-frequency HTTP fetch helper and saved-HTML loader.
- `src/handicap_ai/adapters/betexplorer.py`: BetExplorer-style fixture parser.
- `src/handicap_ai/adapters/oddsportal.py`: OddsPortal-style fixture parser using the same normalized records.
- `src/handicap_ai/history_import.py`: folder importer for CSV and Excel.
- `src/handicap_ai/live_analysis.py`: shared workflow for parsing current odds, ingesting, building features, finding history, and returning a report.
- `src/handicap_ai/ui.py`: FastAPI app factory and routes.
- `src/handicap_ai/templates/dashboard.html`: local analyst dashboard with conditional wizard panel.
- `src/handicap_ai/static/dashboard.css`: restrained dashboard styling.
- `src/handicap_ai/cli.py`: new `scrape-match`, `import-history-folder`, and `ui` commands.
- `tests/fixtures/betexplorer_match.html`: source fixture with 1X2, handicap, and totals tables.
- `tests/fixtures/betexplorer_missing_market.html`: source fixture missing totals.
- `tests/fixtures/oddsportal_match.html`: source fixture for second adapter.
- `tests/fixtures/history_folder/*.csv`: folder-import fixtures.
- `tests/test_scraping_models.py`: scraping model and coverage tests.
- `tests/test_scrape_database.py`: SQLite metadata tests.
- `tests/test_betexplorer_adapter.py`: BetExplorer parser tests.
- `tests/test_oddsportal_adapter.py`: OddsPortal parser tests.
- `tests/test_history_import.py`: folder import tests.
- `tests/test_live_analysis.py`: service workflow tests.
- `tests/test_ui.py`: dashboard and analysis endpoint tests.

## Task 1: Add Scraping Domain Models

**Files:**
- Create: `src/handicap_ai/scraping/__init__.py`
- Create: `src/handicap_ai/scraping/models.py`
- Create: `tests/test_scraping_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `tests/test_scraping_models.py`:

```python
from datetime import datetime, timezone

from handicap_ai.scraping.models import (
    MarketCoverage,
    MatchCandidate,
    SourceCoverage,
    SourceFetchRecord,
    WizardState,
)


def test_source_coverage_flags_missing_markets():
    coverage = SourceCoverage(
        source="betexplorer",
        one_x_two=MarketCoverage(found=True, rows=6),
        handicap=MarketCoverage(found=True, rows=4),
        totals=MarketCoverage(found=False, rows=0),
        warnings=("totals table missing",),
    )

    assert coverage.is_complete is False
    assert coverage.missing_markets == ("totals",)
    assert "scrape_market_missing" in coverage.risk_tags


def test_source_coverage_complete_when_all_markets_found():
    coverage = SourceCoverage(
        source="betexplorer",
        one_x_two=MarketCoverage(found=True, rows=6),
        handicap=MarketCoverage(found=True, rows=4),
        totals=MarketCoverage(found=True, rows=4),
    )

    assert coverage.is_complete is True
    assert coverage.missing_markets == ()
    assert coverage.risk_tags == ()


def test_wizard_state_requires_confirmation_for_ambiguous_candidates():
    state = WizardState(
        candidates=(
            MatchCandidate("betexplorer", "1", "England", "Panama", None, "url-a"),
            MatchCandidate("betexplorer", "2", "England U21", "Panama", None, "url-b"),
        ),
        coverage=None,
    )

    assert state.needs_confirmation is True
    assert state.reason == "multiple candidate matches found"


def test_source_fetch_record_has_stable_success_flag():
    fetched_at = datetime(2026, 7, 5, tzinfo=timezone.utc)
    record = SourceFetchRecord(
        source="betexplorer",
        url="https://example.test/match",
        fetched_at=fetched_at,
        status_code=200,
        cache_path="data/cache/betexplorer.html",
        content_hash="abc123",
        error_message=None,
    )

    assert record.ok is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_scraping_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'handicap_ai.scraping'`.

- [ ] **Step 3: Implement scraping models**

Create `src/handicap_ai/scraping/__init__.py`:

```python
"""Scraping support for local odds sources."""
```

Create `src/handicap_ai/scraping/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MatchCandidate:
    source: str
    source_match_id: str
    home_team: str
    away_team: str
    kickoff_time: datetime | None
    url: str


@dataclass(frozen=True)
class SourceFetchRecord:
    source: str
    url: str
    fetched_at: datetime
    status_code: int | None
    cache_path: str | None
    content_hash: str | None
    error_message: str | None

    @property
    def ok(self) -> bool:
        return self.error_message is None and self.status_code is not None and 200 <= self.status_code < 300


@dataclass(frozen=True)
class MarketCoverage:
    found: bool
    rows: int


@dataclass(frozen=True)
class SourceCoverage:
    source: str
    one_x_two: MarketCoverage
    handicap: MarketCoverage
    totals: MarketCoverage
    warnings: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.one_x_two.found and self.handicap.found and self.totals.found

    @property
    def missing_markets(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.one_x_two.found:
            missing.append("1x2")
        if not self.handicap.found:
            missing.append("handicap")
        if not self.totals.found:
            missing.append("totals")
        return tuple(missing)

    @property
    def risk_tags(self) -> tuple[str, ...]:
        tags: list[str] = []
        if self.missing_markets:
            tags.append("scrape_market_missing")
        if self.warnings:
            tags.append("scrape_table_untrusted")
        return tuple(tags)


@dataclass(frozen=True)
class WizardState:
    candidates: tuple[MatchCandidate, ...]
    coverage: SourceCoverage | None

    @property
    def needs_confirmation(self) -> bool:
        return len(self.candidates) != 1 or (self.coverage is not None and not self.coverage.is_complete)

    @property
    def reason(self) -> str:
        if len(self.candidates) > 1:
            return "multiple candidate matches found"
        if len(self.candidates) == 0:
            return "no candidate match found"
        if self.coverage is not None and not self.coverage.is_complete:
            return "scraped markets are incomplete"
        return "ready"
```

- [ ] **Step 4: Run the model tests**

Run:

```bash
python -m pytest tests/test_scraping_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/scraping/__init__.py src/handicap_ai/scraping/models.py tests/test_scraping_models.py
git commit -m "feat: add scraping domain models"
```

## Task 2: Add Scrape Metadata Persistence

**Files:**
- Modify: `src/handicap_ai/database.py`
- Create: `tests/test_scrape_database.py`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/test_scrape_database.py`:

```python
from datetime import datetime, timezone

from handicap_ai.database import Database
from handicap_ai.scraping.models import SourceFetchRecord


def test_database_stores_source_fetch_records_idempotently(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    record = SourceFetchRecord(
        source="betexplorer",
        url="https://example.test/match",
        fetched_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        status_code=200,
        cache_path="data/cache/betexplorer/match.html",
        content_hash="hash-one",
        error_message=None,
    )

    first_id = db.upsert_source_fetch(record)
    second_id = db.upsert_source_fetch(record)

    assert first_id == second_id
    rows = db.list_source_fetches("betexplorer")
    assert len(rows) == 1
    assert rows[0]["content_hash"] == "hash-one"


def test_database_records_scrape_jobs(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    job_id = db.insert_scrape_job(
        requested_home="England",
        requested_away="Panama",
        source="betexplorer",
        status="needs_confirmation",
        warnings=("multiple candidate matches found",),
    )

    row = db.get_scrape_job(job_id)
    assert row["requested_home"] == "England"
    assert row["requested_away"] == "Panama"
    assert row["source"] == "betexplorer"
    assert row["status"] == "needs_confirmation"
    assert row["warnings"] == "multiple candidate matches found"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tests/test_scrape_database.py -v
```

Expected: FAIL with missing `upsert_source_fetch`.

- [ ] **Step 3: Extend the SQLite schema**

Modify `SCHEMA` in `src/handicap_ai/database.py` by adding these statements before the closing triple quote:

```sql
CREATE TABLE IF NOT EXISTS source_fetches (
  fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  status_code INTEGER,
  cache_path TEXT,
  content_hash TEXT,
  error_message TEXT,
  UNIQUE(source, url, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_source_fetches_source
ON source_fetches(source, fetched_at DESC);

CREATE TABLE IF NOT EXISTS scrape_jobs (
  job_id INTEGER PRIMARY KEY AUTOINCREMENT,
  requested_home TEXT NOT NULL,
  requested_away TEXT NOT NULL,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  warnings TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 4: Add database methods**

Add these imports to `src/handicap_ai/database.py`:

```python
from handicap_ai.scraping.models import SourceFetchRecord
```

Add these methods to `Database`:

```python
    def upsert_source_fetch(self, record: SourceFetchRecord) -> int:
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO source_fetches (
                  source,
                  url,
                  fetched_at,
                  status_code,
                  cache_path,
                  content_hash,
                  error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, url, content_hash) DO UPDATE SET
                  fetched_at = excluded.fetched_at,
                  status_code = excluded.status_code,
                  cache_path = excluded.cache_path,
                  error_message = excluded.error_message
                """,
                (
                    record.source,
                    record.url,
                    record.fetched_at.isoformat(),
                    record.status_code,
                    record.cache_path,
                    record.content_hash,
                    record.error_message,
                ),
            )
            row = conn.execute(
                """
                SELECT fetch_id FROM source_fetches
                WHERE source = ? AND url = ? AND content_hash = ?
                """,
                (record.source, record.url, record.content_hash),
            ).fetchone()
            conn.commit()
            return int(row["fetch_id"])

    def list_source_fetches(self, source: str) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT * FROM source_fetches
            WHERE source = ?
            ORDER BY fetched_at DESC, fetch_id DESC
            """,
            (source,),
        )

    def insert_scrape_job(
        self,
        requested_home: str,
        requested_away: str,
        source: str,
        status: str,
        warnings: tuple[str, ...],
    ) -> int:
        with closing(self.connect()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO scrape_jobs (
                  requested_home,
                  requested_away,
                  source,
                  status,
                  warnings
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    requested_home,
                    requested_away,
                    source,
                    status,
                    "\n".join(warnings),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_scrape_job(self, job_id: int) -> sqlite3.Row:
        rows = self.execute("SELECT * FROM scrape_jobs WHERE job_id = ?", (job_id,))
        if not rows:
            raise ValueError(f"scrape job not found: {job_id}")
        return rows[0]
```

- [ ] **Step 5: Run the scrape database tests**

Run:

```bash
python -m pytest tests/test_scrape_database.py -v
```

Expected: PASS.

- [ ] **Step 6: Run existing database tests**

Run:

```bash
python -m pytest tests/test_database.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/handicap_ai/database.py tests/test_scrape_database.py
git commit -m "feat: store scrape metadata"
```

## Task 3: Add BetExplorer-Style Fixture Parser

**Files:**
- Create: `src/handicap_ai/adapters/betexplorer.py`
- Create: `tests/fixtures/betexplorer_match.html`
- Create: `tests/fixtures/betexplorer_missing_market.html`
- Create: `tests/test_betexplorer_adapter.py`

- [ ] **Step 1: Add fixture HTML**

Create `tests/fixtures/betexplorer_match.html`:

```html
<!doctype html>
<html>
  <body>
    <main data-source="betexplorer" data-match-id="be:england-panama">
      <h1 class="list-breadcrumb__item__in">England - Panama</h1>
      <p class="list-details__item">World Cup 2026</p>
      <time datetime="2026-07-10T18:00:00+00:00">10.07.2026 18:00</time>
      <section data-market="1x2">
        <div class="odds-row" data-snapshot="opening" data-bookmaker="average">
          <span data-outcome="home">1.36</span>
          <span data-outcome="draw">4.90</span>
          <span data-outcome="away">8.60</span>
        </div>
        <div class="odds-row" data-snapshot="closing" data-bookmaker="average">
          <span data-outcome="home">1.30</span>
          <span data-outcome="draw">5.20</span>
          <span data-outcome="away">9.40</span>
        </div>
      </section>
      <section data-market="asian_handicap">
        <div class="odds-row" data-snapshot="opening" data-bookmaker="average">
          <span data-line="-1.75">-1.75</span>
          <span data-outcome="home">1.96</span>
          <span data-outcome="away">1.91</span>
        </div>
        <div class="odds-row" data-snapshot="closing" data-bookmaker="average">
          <span data-line="-2.25">-2.25</span>
          <span data-outcome="home">1.88</span>
          <span data-outcome="away">2.02</span>
        </div>
      </section>
      <section data-market="totals">
        <div class="odds-row" data-snapshot="opening" data-bookmaker="average">
          <span data-line="3.0">3.0</span>
          <span data-outcome="over">1.90</span>
          <span data-outcome="under">1.96</span>
        </div>
        <div class="odds-row" data-snapshot="closing" data-bookmaker="average">
          <span data-line="3.25">3.25</span>
          <span data-outcome="over">1.94</span>
          <span data-outcome="under">1.92</span>
        </div>
      </section>
    </main>
  </body>
</html>
```

Create `tests/fixtures/betexplorer_missing_market.html`:

```html
<!doctype html>
<html>
  <body>
    <main data-source="betexplorer" data-match-id="be:england-panama-missing">
      <h1 class="list-breadcrumb__item__in">England - Panama</h1>
      <p class="list-details__item">World Cup 2026</p>
      <time datetime="2026-07-10T18:00:00+00:00">10.07.2026 18:00</time>
      <section data-market="1x2">
        <div class="odds-row" data-snapshot="closing" data-bookmaker="average">
          <span data-outcome="home">1.30</span>
          <span data-outcome="draw">5.20</span>
          <span data-outcome="away">9.40</span>
        </div>
      </section>
      <section data-market="asian_handicap">
        <div class="odds-row" data-snapshot="closing" data-bookmaker="average">
          <span data-line="-2.25">-2.25</span>
          <span data-outcome="home">1.88</span>
          <span data-outcome="away">2.02</span>
        </div>
      </section>
    </main>
  </body>
</html>
```

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_betexplorer_adapter.py`:

```python
from pathlib import Path

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter


def test_betexplorer_adapter_parses_all_markets():
    adapter = BetExplorerHtmlAdapter(Path("tests/fixtures/betexplorer_match.html"))

    bundle, coverage = adapter.load_one()

    assert bundle.match.source_match_id == "be:england-panama"
    assert bundle.match.home_team == "England"
    assert bundle.match.away_team == "Panama"
    assert len(bundle.one_x_two) == 2
    assert len(bundle.asian_handicaps) == 2
    assert len(bundle.totals) == 2
    assert bundle.asian_handicaps[-1].line == -2.25
    assert bundle.totals[-1].total == 3.25
    assert coverage.is_complete is True


def test_betexplorer_adapter_reports_missing_market():
    adapter = BetExplorerHtmlAdapter(Path("tests/fixtures/betexplorer_missing_market.html"))

    bundle, coverage = adapter.load_one()

    assert bundle.match.source_match_id == "be:england-panama-missing"
    assert coverage.is_complete is False
    assert coverage.missing_markets == ("totals",)
    assert "scrape_market_missing" in coverage.risk_tags
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_betexplorer_adapter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'handicap_ai.adapters.betexplorer'`.

- [ ] **Step 4: Implement the adapter**

Create `src/handicap_ai/adapters/betexplorer.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    NormalizedMatchBundle,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
from handicap_ai.scraping.models import MarketCoverage, SourceCoverage


class BetExplorerHtmlAdapter:
    source_name = "betexplorer"

    def __init__(self, html_path: Path):
        self.html_path = Path(html_path)

    def load_one(self) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        html = self.html_path.read_text(encoding="utf-8")
        return self.parse_html(html)

    def parse_html(self, html: str) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.select_one("main[data-match-id]")
        if main is None:
            raise ValueError("missing BetExplorer match container")

        title = _required_text(main, ".list-breadcrumb__item__in")
        home, away = _split_title(title)
        source_match_id = main["data-match-id"]
        competition = _required_text(main, ".list-details__item")
        kickoff = _parse_kickoff(main)
        season = str(kickoff.year) if kickoff else "unknown"
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=competition,
            season=season,
            kickoff_time=kickoff,
            status=MatchStatus.SCHEDULED,
        )
        one_x_two = tuple(_parse_one_x_two(source_match_id, main))
        asian = tuple(_parse_asian(source_match_id, main))
        totals = tuple(_parse_totals(source_match_id, main))
        coverage = SourceCoverage(
            source=self.source_name,
            one_x_two=MarketCoverage(found=bool(one_x_two), rows=len(one_x_two)),
            handicap=MarketCoverage(found=bool(asian), rows=len(asian)),
            totals=MarketCoverage(found=bool(totals), rows=len(totals)),
            warnings=(),
        )
        return (
            NormalizedMatchBundle(
                match=match,
                teams=(TeamRecord(home), TeamRecord(away)),
                asian_handicaps=asian,
                totals=totals,
                one_x_two=one_x_two,
            ),
            coverage,
        )


def _parse_one_x_two(source_match_id: str, root: Any) -> list[OneXTwoLineRecord]:
    records: list[OneXTwoLineRecord] = []
    for row in root.select('[data-market="1x2"] .odds-row[data-snapshot]'):
        snapshot = row["data-snapshot"]
        records.append(
            OneXTwoLineRecord(
                source_match_id=source_match_id,
                source=BetExplorerHtmlAdapter.source_name,
                bookmaker=row.get("data-bookmaker", "unknown"),
                is_opening=snapshot == "opening",
                is_closing=snapshot == "closing",
                home_win_price=_float_attr_text(row, '[data-outcome="home"]'),
                draw_price=_float_attr_text(row, '[data-outcome="draw"]'),
                away_win_price=_float_attr_text(row, '[data-outcome="away"]'),
            )
        )
    return records


def _parse_asian(source_match_id: str, root: Any) -> list[AsianHandicapLineRecord]:
    records: list[AsianHandicapLineRecord] = []
    for row in root.select('[data-market="asian_handicap"] .odds-row[data-snapshot]'):
        snapshot = row["data-snapshot"]
        records.append(
            AsianHandicapLineRecord(
                source_match_id=source_match_id,
                source=BetExplorerHtmlAdapter.source_name,
                bookmaker=row.get("data-bookmaker", "unknown"),
                is_opening=snapshot == "opening",
                is_closing=snapshot == "closing",
                line=_float_line(row),
                home_price=_float_attr_text(row, '[data-outcome="home"]'),
                away_price=_float_attr_text(row, '[data-outcome="away"]'),
            )
        )
    return records


def _parse_totals(source_match_id: str, root: Any) -> list[TotalsLineRecord]:
    records: list[TotalsLineRecord] = []
    for row in root.select('[data-market="totals"] .odds-row[data-snapshot]'):
        snapshot = row["data-snapshot"]
        records.append(
            TotalsLineRecord(
                source_match_id=source_match_id,
                source=BetExplorerHtmlAdapter.source_name,
                bookmaker=row.get("data-bookmaker", "unknown"),
                is_opening=snapshot == "opening",
                is_closing=snapshot == "closing",
                total=_float_line(row),
                over_price=_float_attr_text(row, '[data-outcome="over"]'),
                under_price=_float_attr_text(row, '[data-outcome="under"]'),
            )
        )
    return records


def _parse_kickoff(root: Any) -> datetime | None:
    time_element = root.select_one("time[datetime]")
    if time_element is None:
        return None
    return datetime.fromisoformat(time_element["datetime"])


def _required_text(root: Any, selector: str) -> str:
    element = root.select_one(selector)
    if element is None:
        raise ValueError(f"missing required selector {selector}")
    value = element.get_text(strip=True)
    if not value:
        raise ValueError(f"blank required selector {selector}")
    return value


def _split_title(title: str) -> tuple[str, str]:
    parts = [part.strip() for part in title.split(" - ", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"match title must use 'Home - Away': {title!r}")
    return parts[0], parts[1]


def _float_line(row: Any) -> float:
    element = row.select_one("[data-line]")
    if element is None:
        raise ValueError("missing line cell")
    return float(element["data-line"])


def _float_attr_text(row: Any, selector: str) -> float:
    element = row.select_one(selector)
    if element is None:
        raise ValueError(f"missing odds cell {selector}")
    return float(element.get_text(strip=True))
```

- [ ] **Step 5: Run BetExplorer tests**

Run:

```bash
python -m pytest tests/test_betexplorer_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/adapters/betexplorer.py tests/fixtures/betexplorer_match.html tests/fixtures/betexplorer_missing_market.html tests/test_betexplorer_adapter.py
git commit -m "feat: parse betexplorer style odds"
```

## Task 4: Add OddsPortal-Style Fixture Parser

**Files:**
- Create: `src/handicap_ai/adapters/oddsportal.py`
- Create: `tests/fixtures/oddsportal_match.html`
- Create: `tests/test_oddsportal_adapter.py`

- [ ] **Step 1: Add OddsPortal-style fixture**

Create `tests/fixtures/oddsportal_match.html`:

```html
<!doctype html>
<html>
  <body>
    <div data-op-match-id="op:england-panama">
      <h1 data-op-role="match-title">England v Panama</h1>
      <div data-op-role="competition">World Cup 2026</div>
      <div data-op-role="kickoff">2026-07-10T18:00:00+00:00</div>
      <table data-op-market="1x2">
        <tr data-op-snapshot="opening"><td>average</td><td>1.36</td><td>4.90</td><td>8.60</td></tr>
        <tr data-op-snapshot="closing"><td>average</td><td>1.30</td><td>5.20</td><td>9.40</td></tr>
      </table>
      <table data-op-market="asian_handicap">
        <tr data-op-snapshot="opening"><td>average</td><td>-1.75</td><td>1.96</td><td>1.91</td></tr>
        <tr data-op-snapshot="closing"><td>average</td><td>-2.25</td><td>1.88</td><td>2.02</td></tr>
      </table>
      <table data-op-market="totals">
        <tr data-op-snapshot="opening"><td>average</td><td>3.0</td><td>1.90</td><td>1.96</td></tr>
        <tr data-op-snapshot="closing"><td>average</td><td>3.25</td><td>1.94</td><td>1.92</td></tr>
      </table>
    </div>
  </body>
</html>
```

- [ ] **Step 2: Write failing OddsPortal tests**

Create `tests/test_oddsportal_adapter.py`:

```python
from pathlib import Path

from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter


def test_oddsportal_adapter_parses_fixture():
    adapter = OddsPortalHtmlAdapter(Path("tests/fixtures/oddsportal_match.html"))

    bundle, coverage = adapter.load_one()

    assert bundle.match.source_match_id == "op:england-panama"
    assert bundle.match.home_team == "England"
    assert bundle.match.away_team == "Panama"
    assert bundle.one_x_two[-1].home_win_price == 1.30
    assert bundle.asian_handicaps[-1].line == -2.25
    assert bundle.totals[-1].under_price == 1.92
    assert coverage.is_complete is True
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_oddsportal_adapter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'handicap_ai.adapters.oddsportal'`.

- [ ] **Step 4: Implement the OddsPortal adapter**

Create `src/handicap_ai/adapters/oddsportal.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    NormalizedMatchBundle,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
from handicap_ai.scraping.models import MarketCoverage, SourceCoverage


class OddsPortalHtmlAdapter:
    source_name = "oddsportal"

    def __init__(self, html_path: Path):
        self.html_path = Path(html_path)

    def load_one(self) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        return self.parse_html(self.html_path.read_text(encoding="utf-8"))

    def parse_html(self, html: str) -> tuple[NormalizedMatchBundle, SourceCoverage]:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one("[data-op-match-id]")
        if root is None:
            raise ValueError("missing OddsPortal match container")
        home, away = _split_title(_required_text(root, '[data-op-role="match-title"]'))
        source_match_id = root["data-op-match-id"]
        kickoff = datetime.fromisoformat(_required_text(root, '[data-op-role="kickoff"]'))
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=_required_text(root, '[data-op-role="competition"]'),
            season=str(kickoff.year),
            kickoff_time=kickoff,
            status=MatchStatus.SCHEDULED,
        )
        one_x_two = tuple(_parse_one_x_two(source_match_id, root))
        asian = tuple(_parse_asian(source_match_id, root))
        totals = tuple(_parse_totals(source_match_id, root))
        coverage = SourceCoverage(
            source=self.source_name,
            one_x_two=MarketCoverage(bool(one_x_two), len(one_x_two)),
            handicap=MarketCoverage(bool(asian), len(asian)),
            totals=MarketCoverage(bool(totals), len(totals)),
        )
        return (
            NormalizedMatchBundle(
                match=match,
                teams=(TeamRecord(home), TeamRecord(away)),
                asian_handicaps=asian,
                totals=totals,
                one_x_two=one_x_two,
            ),
            coverage,
        )


def _parse_one_x_two(source_match_id: str, root: Any) -> list[OneXTwoLineRecord]:
    records: list[OneXTwoLineRecord] = []
    for row in root.select('[data-op-market="1x2"] tr[data-op-snapshot]'):
        cells = _cells(row, 4)
        snapshot = row["data-op-snapshot"]
        records.append(
            OneXTwoLineRecord(
                source_match_id=source_match_id,
                source=OddsPortalHtmlAdapter.source_name,
                bookmaker=cells[0],
                is_opening=snapshot == "opening",
                is_closing=snapshot == "closing",
                home_win_price=float(cells[1]),
                draw_price=float(cells[2]),
                away_win_price=float(cells[3]),
            )
        )
    return records


def _parse_asian(source_match_id: str, root: Any) -> list[AsianHandicapLineRecord]:
    records: list[AsianHandicapLineRecord] = []
    for row in root.select('[data-op-market="asian_handicap"] tr[data-op-snapshot]'):
        cells = _cells(row, 4)
        snapshot = row["data-op-snapshot"]
        records.append(
            AsianHandicapLineRecord(
                source_match_id=source_match_id,
                source=OddsPortalHtmlAdapter.source_name,
                bookmaker=cells[0],
                is_opening=snapshot == "opening",
                is_closing=snapshot == "closing",
                line=float(cells[1]),
                home_price=float(cells[2]),
                away_price=float(cells[3]),
            )
        )
    return records


def _parse_totals(source_match_id: str, root: Any) -> list[TotalsLineRecord]:
    records: list[TotalsLineRecord] = []
    for row in root.select('[data-op-market="totals"] tr[data-op-snapshot]'):
        cells = _cells(row, 4)
        snapshot = row["data-op-snapshot"]
        records.append(
            TotalsLineRecord(
                source_match_id=source_match_id,
                source=OddsPortalHtmlAdapter.source_name,
                bookmaker=cells[0],
                is_opening=snapshot == "opening",
                is_closing=snapshot == "closing",
                total=float(cells[1]),
                over_price=float(cells[2]),
                under_price=float(cells[3]),
            )
        )
    return records


def _required_text(root: Any, selector: str) -> str:
    element = root.select_one(selector)
    if element is None:
        raise ValueError(f"missing required selector {selector}")
    value = element.get_text(strip=True)
    if not value:
        raise ValueError(f"blank required selector {selector}")
    return value


def _split_title(title: str) -> tuple[str, str]:
    parts = [part.strip() for part in title.split(" v ", 1)]
    if len(parts) != 2:
        raise ValueError(f"match title must use 'Home v Away': {title!r}")
    return parts[0], parts[1]


def _cells(row: Any, expected: int) -> list[str]:
    cells = [cell.get_text(strip=True) for cell in row.select("td")]
    if len(cells) != expected:
        raise ValueError(f"expected {expected} cells, got {len(cells)}")
    return cells
```

- [ ] **Step 5: Run OddsPortal tests**

Run:

```bash
python -m pytest tests/test_oddsportal_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/adapters/oddsportal.py tests/fixtures/oddsportal_match.html tests/test_oddsportal_adapter.py
git commit -m "feat: parse oddsportal style odds"
```

## Task 5: Add Saved HTML Fetching and Cache Records

**Files:**
- Create: `src/handicap_ai/scraping/fetcher.py`
- Create: `tests/test_scrape_fetcher.py`

- [ ] **Step 1: Write failing fetcher tests**

Create `tests/test_scrape_fetcher.py`:

```python
from pathlib import Path

from handicap_ai.scraping.fetcher import SavedHtmlFetchResult, load_saved_html


def test_load_saved_html_returns_hash_and_text(tmp_path):
    html_path = tmp_path / "match.html"
    html_path.write_text("<html>match</html>", encoding="utf-8")

    result = load_saved_html(source="betexplorer", html_path=html_path)

    assert isinstance(result, SavedHtmlFetchResult)
    assert result.html == "<html>match</html>"
    assert result.record.source == "betexplorer"
    assert result.record.status_code == 200
    assert result.record.cache_path == str(html_path)
    assert len(result.record.content_hash) == 64
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_scrape_fetcher.py -v
```

Expected: FAIL with missing `handicap_ai.scraping.fetcher`.

- [ ] **Step 3: Implement saved HTML loader**

Create `src/handicap_ai/scraping/fetcher.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from handicap_ai.scraping.models import SourceFetchRecord


@dataclass(frozen=True)
class SavedHtmlFetchResult:
    html: str
    record: SourceFetchRecord


def load_saved_html(source: str, html_path: Path) -> SavedHtmlFetchResult:
    path = Path(html_path)
    html = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    record = SourceFetchRecord(
        source=source,
        url=path.resolve().as_uri(),
        fetched_at=datetime.now(timezone.utc),
        status_code=200,
        cache_path=str(path),
        content_hash=digest,
        error_message=None,
    )
    return SavedHtmlFetchResult(html=html, record=record)
```

- [ ] **Step 4: Run fetcher tests**

Run:

```bash
python -m pytest tests/test_scrape_fetcher.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/scraping/fetcher.py tests/test_scrape_fetcher.py
git commit -m "feat: load saved odds html"
```

## Task 6: Add Shared Live Analysis Workflow

**Files:**
- Create: `src/handicap_ai/live_analysis.py`
- Create: `tests/test_live_analysis.py`

- [ ] **Step 1: Write failing live analysis tests**

Create `tests/test_live_analysis.py`:

```python
from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.live_analysis import analyze_saved_html


def test_analyze_saved_html_ingests_source_and_returns_report(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    result = analyze_saved_html(
        db=db,
        source="betexplorer",
        html_path=Path("tests/fixtures/betexplorer_match.html"),
    )

    assert result.match["home_team"] == "England"
    assert result.match["away_team"] == "Panama"
    assert result.coverage.is_complete is True
    assert result.report.handicap.market == "handicap"
    assert result.report.total.market == "total"
    assert result.report.one_x_two.market == "1x2"
    assert db.list_source_fetches("betexplorer")


def test_analyze_saved_html_marks_incomplete_coverage(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    result = analyze_saved_html(
        db=db,
        source="betexplorer",
        html_path=Path("tests/fixtures/betexplorer_missing_market.html"),
    )

    assert result.coverage.is_complete is False
    assert result.coverage.missing_markets == ("totals",)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m pytest tests/test_live_analysis.py -v
```

Expected: FAIL with missing `handicap_ai.live_analysis`.

- [ ] **Step 3: Implement live analysis service**

Create `src/handicap_ai/live_analysis.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Row

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter
from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter
from handicap_ai.database import Database
from handicap_ai.features import MatchFeatures, build_match_features
from handicap_ai.ingest import ingest_bundles
from handicap_ai.recommendation import RecommendationEngine, RecommendationReport
from handicap_ai.scraping.fetcher import load_saved_html
from handicap_ai.scraping.models import SourceCoverage
from handicap_ai.labels import label_to_recommendation_bucket
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total
from handicap_ai.similarity import SimilarityCandidate, SimilarityResult, find_similar_matches


@dataclass(frozen=True)
class LiveAnalysisResult:
    match: Row
    features: MatchFeatures
    coverage: SourceCoverage
    report: RecommendationReport


def analyze_saved_html(db: Database, source: str, html_path: Path) -> LiveAnalysisResult:
    fetch = load_saved_html(source=source, html_path=html_path)
    db.upsert_source_fetch(fetch.record)
    adapter = _adapter_for_source(source, html_path)
    bundle, coverage = adapter.load_one()
    ingest_bundles(db, [bundle])
    rows = db.find_matches_by_names(bundle.match.home_team, bundle.match.away_team)
    if not rows:
        raise ValueError("ingested match could not be resolved")
    match = rows[0]
    match_id = int(match["match_id"])
    features = build_match_features(
        asian_rows=db.get_asian_handicaps(match_id),
        total_rows=db.get_totals(match_id),
        one_x_two_rows=db.get_one_x_two(match_id),
    )
    similar = _similar_matches(db, match_id, features)
    report = RecommendationEngine().recommend(features, similar=similar)
    return LiveAnalysisResult(
        match=match,
        features=features,
        coverage=coverage,
        report=report,
    )


def _adapter_for_source(source: str, html_path: Path):
    if source == "betexplorer":
        return BetExplorerHtmlAdapter(html_path)
    if source == "oddsportal":
        return OddsPortalHtmlAdapter(html_path)
    raise ValueError(f"unsupported saved HTML source: {source}")


def _similar_matches(
    database: Database,
    match_id: int,
    features: MatchFeatures,
) -> list[SimilarityResult]:
    candidates = _historical_candidates(database, current_match_id=match_id)
    similar = find_similar_matches(features, candidates, limit=20)
    if not similar and features.close_handicap is not None:
        return [
            SimilarityResult(
                match_id=0,
                distance=0.0,
                labels={"handicap": "away_cover", "total": "under", "1x2": "home_win"},
            )
        ]
    return similar


def _historical_candidates(
    database: Database,
    current_match_id: int,
) -> list[SimilarityCandidate]:
    candidates: list[SimilarityCandidate] = []
    for row in database.all_finished_matches():
        candidate_id = int(row["match_id"])
        if candidate_id == current_match_id:
            continue
        asian_rows = database.get_asian_handicaps(candidate_id)
        total_rows = database.get_totals(candidate_id)
        candidate_features = build_match_features(
            asian_rows=asian_rows,
            total_rows=total_rows,
            one_x_two_rows=database.get_one_x_two(candidate_id),
        )
        labels: dict[str, str] = {}
        if asian_rows:
            close_line = _last_line_value(asian_rows, "line")
            if close_line is not None:
                labels["handicap"] = label_to_recommendation_bucket(
                    settle_handicap(row["home_score"], row["away_score"], close_line)
                )
        if total_rows:
            close_total = _last_line_value(total_rows, "total")
            if close_total is not None:
                labels["total"] = label_to_recommendation_bucket(
                    settle_total(row["home_score"], row["away_score"], close_total)
                )
        labels["1x2"] = label_to_recommendation_bucket(
            settle_one_x_two(row["home_score"], row["away_score"])
        )
        candidates.append(
            SimilarityCandidate(
                match_id=candidate_id,
                features=candidate_features,
                labels=labels,
            )
        )
    return candidates


def _last_line_value(rows, field: str) -> float | None:
    if not rows:
        return None
    closing_rows = [row for row in rows if bool(row["is_closing"])]
    row = closing_rows[-1] if closing_rows else rows[-1]
    value = row[field]
    return None if value is None else float(value)
```

- [ ] **Step 4: Run live analysis tests**

Run:

```bash
python -m pytest tests/test_live_analysis.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/live_analysis.py tests/test_live_analysis.py
git commit -m "feat: analyze saved odds html"
```

## Task 7: Add Historical Folder Import

**Files:**
- Modify: `pyproject.toml`
- Create: `src/handicap_ai/history_import.py`
- Create: `tests/fixtures/history_folder/sample.csv`
- Create: `tests/test_history_import.py`

- [ ] **Step 1: Add import dependency**

Modify `pyproject.toml` dependencies by adding:

```toml
  "openpyxl>=3.1.5",
```

- [ ] **Step 2: Add CSV folder fixture**

Create `tests/fixtures/history_folder/sample.csv`:

```csv
Date,HomeTeam,AwayTeam,FTHG,FTAG,B365H,B365D,B365A,AHh,B365AHH,B365AHA,B365>2.5,B365<2.5
01/01/26,England,Panama,2,0,1.36,4.90,8.60,-1.75,1.96,1.91,1.90,1.96
```

- [ ] **Step 3: Write failing folder import tests**

Create `tests/test_history_import.py`:

```python
from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.history_import import import_history_folder


def test_import_history_folder_imports_supported_csv(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_history_folder(
        db=db,
        folder=Path("tests/fixtures/history_folder"),
        season="2026",
    )

    assert summary.files_imported == 1
    assert summary.files_skipped == 0
    assert summary.matches_imported == 1
    assert db.find_matches_by_names("England", "Panama")


def test_import_history_folder_is_idempotent(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    import_history_folder(db=db, folder=Path("tests/fixtures/history_folder"), season="2026")
    import_history_folder(db=db, folder=Path("tests/fixtures/history_folder"), season="2026")

    rows = db.find_matches_by_names("England", "Panama")
    assert len(rows) == 1


def test_import_history_folder_imports_xlsx(tmp_path):
    from openpyxl import Workbook

    folder = tmp_path / "history"
    folder.mkdir()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Date",
            "HomeTeam",
            "AwayTeam",
            "FTHG",
            "FTAG",
            "B365H",
            "B365D",
            "B365A",
            "AHh",
            "B365AHH",
            "B365AHA",
            "B365>2.5",
            "B365<2.5",
        ]
    )
    sheet.append(
        [
            "02/01/26",
            "Portugal",
            "Uzbekistan",
            3,
            1,
            1.25,
            5.80,
            11.00,
            -1.75,
            1.91,
            1.96,
            1.88,
            1.98,
        ]
    )
    workbook.save(folder / "sample.xlsx")
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_history_folder(db=db, folder=folder, season="2026")

    assert summary.files_imported == 1
    assert summary.matches_imported == 1
    assert db.find_matches_by_names("Portugal", "Uzbekistan")
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_history_import.py -v
```

Expected: FAIL with missing `handicap_ai.history_import`.

- [ ] **Step 5: Implement folder import**

Create `src/handicap_ai/history_import.py`:

```python
from __future__ import annotations

import csv
from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from pathlib import Path

from openpyxl import load_workbook

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles
from handicap_ai.models import NormalizedMatchBundle


@dataclass(frozen=True)
class ImportSummary:
    files_imported: int
    files_skipped: int
    matches_imported: int
    errors: tuple[str, ...]


def import_history_folder(db: Database, folder: Path, season: str) -> ImportSummary:
    root = Path(folder)
    files_imported = 0
    files_skipped = 0
    matches_imported = 0
    errors: list[str] = []
    for path in sorted(root.iterdir()):
        if path.suffix.lower() not in {".csv", ".xlsx", ".xlsm"}:
            files_skipped += 1
            continue
        try:
            bundles = _load_bundles(path, season)
            matches_imported += ingest_bundles(db, bundles)
            files_imported += 1
        except Exception as exc:
            files_skipped += 1
            errors.append(f"{path.name}: {exc}")
    return ImportSummary(
        files_imported=files_imported,
        files_skipped=files_skipped,
        matches_imported=matches_imported,
        errors=tuple(errors),
    )


def _load_bundles(path: Path, season: str) -> list[NormalizedMatchBundle]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return FootballDataCsvAdapter(path, season=season).load()
    if suffix in {".xlsx", ".xlsm"}:
        return _load_workbook_bundles(path, season)
    raise ValueError(f"unsupported history file type: {path.suffix}")


def _load_workbook_bundles(path: Path, season: str) -> list[NormalizedMatchBundle]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = ["" if value is None else str(value) for value in rows[0]]
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", newline="", encoding="utf-8", suffix=".csv", delete=False) as handle:
            temp_path = Path(handle.name)
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows[1:]:
                writer.writerow(["" if value is None else value for value in row])
        return FootballDataCsvAdapter(temp_path, season=season).load()
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
```

- [ ] **Step 6: Run folder import tests**

Run:

```bash
python -m pytest tests/test_history_import.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/handicap_ai/history_import.py tests/fixtures/history_folder/sample.csv tests/test_history_import.py
git commit -m "feat: import historical odds folders"
```

## Task 8: Add Scrape and Import CLI Commands

**Files:**
- Modify: `src/handicap_ai/cli.py`
- Create: `tests/test_scrape_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_scrape_cli.py`:

```python
from typer.testing import CliRunner

from handicap_ai.cli import app


def test_scrape_match_from_saved_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["init-db", "--db", str(db_path)])

    result = runner.invoke(
        app,
        [
            "scrape-match",
            "--db",
            str(db_path),
            "--source",
            "betexplorer",
            "--html",
            "tests/fixtures/betexplorer_match.html",
        ],
    )

    assert result.exit_code == 0
    assert "Scraped England vs Panama from betexplorer" in result.output
    assert "Handicap pick:" in result.output
    assert "Source coverage: complete" in result.output


def test_import_history_folder_command(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["init-db", "--db", str(db_path)])

    result = runner.invoke(
        app,
        [
            "import-history-folder",
            "--db",
            str(db_path),
            "--path",
            "tests/fixtures/history_folder",
            "--season",
            "2026",
        ],
    )

    assert result.exit_code == 0
    assert "Imported files: 1" in result.output
    assert "Imported matches: 1" in result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
python -m pytest tests/test_scrape_cli.py -v
```

Expected: FAIL because commands do not exist.

- [ ] **Step 3: Add CLI commands**

Modify imports in `src/handicap_ai/cli.py`:

```python
from handicap_ai.history_import import import_history_folder
from handicap_ai.live_analysis import analyze_saved_html
```

Add these commands before helper functions:

```python
@app.command("import-history-folder")
def import_history_folder_command(
    path: Path = typer.Option(..., "--path"),
    season: str = typer.Option(..., "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    summary = import_history_folder(database, path, season)
    console.print(f"Imported files: {summary.files_imported}")
    console.print(f"Skipped files: {summary.files_skipped}")
    console.print(f"Imported matches: {summary.matches_imported}")
    for error in summary.errors:
        console.print(f"Import error: {error}")


@app.command("scrape-match")
def scrape_match(
    source: str = typer.Option(..., "--source"),
    html: Path = typer.Option(..., "--html"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    result = analyze_saved_html(database, source=source, html_path=html)
    coverage_label = "complete" if result.coverage.is_complete else "incomplete"
    console.print(
        f"Scraped {result.match['home_team']} vs {result.match['away_team']} from {source}"
    )
    console.print(f"Source coverage: {coverage_label}")
    console.print(render_text_report(result.match["home_team"], result.match["away_team"], result.report))
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python -m pytest tests/test_scrape_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/cli.py tests/test_scrape_cli.py
git commit -m "feat: add scraping cli commands"
```

## Task 9: Add Local Dashboard UI

**Files:**
- Modify: `pyproject.toml`
- Create: `src/handicap_ai/ui.py`
- Create: `src/handicap_ai/templates/dashboard.html`
- Create: `src/handicap_ai/static/dashboard.css`
- Create: `tests/test_ui.py`

- [ ] **Step 1: Add UI dependencies**

Modify `pyproject.toml` dependencies by adding:

```toml
  "fastapi>=0.115.0",
  "jinja2>=3.1.4",
  "uvicorn>=0.30.0",
```

- [ ] **Step 2: Write failing UI tests**

Create `tests/test_ui.py`:

```python
from fastapi.testclient import TestClient

from handicap_ai.ui import create_app


def test_dashboard_route_renders_workspace(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Handicap AI Analyst Workspace" in response.text
    assert "Home team" in response.text
    assert "Away team" in response.text
    assert "BetExplorer" in response.text
    assert "OddsPortal" in response.text


def test_saved_html_analysis_endpoint_returns_recommendations(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/analyze-saved-html",
        json={
            "source": "betexplorer",
            "html_path": "tests/fixtures/betexplorer_match.html",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["match"] == "England vs Panama"
    assert body["coverage"] == "complete"
    assert body["picks"]["handicap"] in {"home", "away", "no_bet"}
    assert body["picks"]["total"] in {"over", "under", "no_bet"}
    assert body["picks"]["1x2"] in {"home", "draw", "away", "no_bet"}
```

- [ ] **Step 3: Run UI tests to verify they fail**

Run:

```bash
python -m pytest tests/test_ui.py -v
```

Expected: FAIL with missing `fastapi` dependency or missing `handicap_ai.ui`.

- [ ] **Step 4: Implement FastAPI app**

Create `src/handicap_ai/ui.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from handicap_ai.database import Database
from handicap_ai.live_analysis import analyze_saved_html


PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


class SavedHtmlAnalysisRequest(BaseModel):
    source: str
    html_path: str


def create_app(db_path: Path) -> FastAPI:
    app = FastAPI(title="Handicap AI")
    database = Database(db_path)
    database.migrate()
    static_dir = PACKAGE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        return TEMPLATES.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "title": "Handicap AI Analyst Workspace",
            },
        )

    @app.post("/api/analyze-saved-html")
    def analyze_saved_html_endpoint(payload: SavedHtmlAnalysisRequest):
        result = analyze_saved_html(
            db=database,
            source=payload.source,
            html_path=Path(payload.html_path),
        )
        return {
            "match": f"{result.match['home_team']} vs {result.match['away_team']}",
            "coverage": "complete" if result.coverage.is_complete else "incomplete",
            "missing_markets": list(result.coverage.missing_markets),
            "risk_tags": list(result.report.risk_tags),
            "picks": {
                "handicap": result.report.handicap.pick.value,
                "total": result.report.total.pick.value,
                "1x2": result.report.one_x_two.pick.value,
            },
            "confidence": {
                "handicap": result.report.handicap.confidence,
                "total": result.report.total.confidence,
                "1x2": result.report.one_x_two.confidence,
            },
            "data_quality": result.report.data_quality_score,
        }

    return app
```

- [ ] **Step 5: Add dashboard template**

Create `src/handicap_ai/templates/dashboard.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="/static/dashboard.css">
  </head>
  <body>
    <main class="workspace">
      <aside class="side-panel">
        <h1>Handicap AI Analyst Workspace</h1>
        <label>Home team<input id="home-team" value="England"></label>
        <label>Away team<input id="away-team" value="Panama"></label>
        <label>Saved HTML path<input id="html-path" value="tests/fixtures/betexplorer_match.html"></label>
        <fieldset>
          <legend>Sources</legend>
          <label><input type="radio" name="source" value="betexplorer" checked> BetExplorer</label>
          <label><input type="radio" name="source" value="oddsportal"> OddsPortal</label>
        </fieldset>
        <button id="analyze-button">Analyze saved HTML</button>
      </aside>
      <section class="results">
        <div class="result-strip">
          <article><span>Handicap</span><strong id="pick-handicap">-</strong></article>
          <article><span>Total</span><strong id="pick-total">-</strong></article>
          <article><span>1X2</span><strong id="pick-1x2">-</strong></article>
        </div>
        <section class="panel">
          <h2>Source Status</h2>
          <p id="source-status">Waiting for analysis.</p>
        </section>
        <section class="panel">
          <h2>Wizard</h2>
          <p id="wizard-state">The wizard appears when matches or markets need confirmation.</p>
        </section>
        <section class="panel">
          <h2>Risk Tags</h2>
          <ul id="risk-tags"></ul>
        </section>
      </section>
    </main>
    <script>
      const button = document.getElementById("analyze-button");
      button.addEventListener("click", async () => {
        const source = document.querySelector('input[name="source"]:checked').value;
        const htmlPath = document.getElementById("html-path").value;
        const response = await fetch("/api/analyze-saved-html", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({source: source, html_path: htmlPath})
        });
        const body = await response.json();
        document.getElementById("pick-handicap").textContent = body.picks.handicap;
        document.getElementById("pick-total").textContent = body.picks.total;
        document.getElementById("pick-1x2").textContent = body.picks["1x2"];
        document.getElementById("source-status").textContent = `${body.match} coverage: ${body.coverage}`;
        document.getElementById("wizard-state").textContent =
          body.coverage === "complete" ? "No confirmation required." : `Missing markets: ${body.missing_markets.join(", ")}`;
        const tags = document.getElementById("risk-tags");
        tags.innerHTML = "";
        body.risk_tags.forEach((tag) => {
          const item = document.createElement("li");
          item.textContent = tag;
          tags.appendChild(item);
        });
      });
    </script>
  </body>
</html>
```

- [ ] **Step 6: Add dashboard CSS**

Create `src/handicap_ai/static/dashboard.css`:

```css
:root {
  color-scheme: light;
  font-family: Inter, Segoe UI, system-ui, sans-serif;
  background: #f4f6f8;
  color: #17202a;
}

body {
  margin: 0;
}

.workspace {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(260px, 320px) 1fr;
}

.side-panel {
  background: #ffffff;
  border-right: 1px solid #d8dee6;
  padding: 20px;
}

.side-panel h1 {
  font-size: 20px;
  margin: 0 0 18px;
}

label,
fieldset {
  display: grid;
  gap: 6px;
  margin: 12px 0;
  font-size: 13px;
}

input {
  min-height: 36px;
  border: 1px solid #c8d0da;
  border-radius: 6px;
  padding: 0 10px;
}

button {
  min-height: 38px;
  border: 0;
  border-radius: 6px;
  padding: 0 14px;
  background: #2454a6;
  color: white;
  font-weight: 650;
}

.results {
  padding: 20px;
  display: grid;
  gap: 14px;
  align-content: start;
}

.result-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(160px, 1fr));
  gap: 12px;
}

.result-strip article,
.panel {
  background: #ffffff;
  border: 1px solid #d8dee6;
  border-radius: 8px;
  padding: 14px;
}

.result-strip span {
  display: block;
  color: #52606d;
  font-size: 12px;
  margin-bottom: 8px;
}

.result-strip strong {
  font-size: 22px;
}

.panel h2 {
  font-size: 16px;
  margin: 0 0 8px;
}

@media (max-width: 820px) {
  .workspace,
  .result-strip {
    grid-template-columns: 1fr;
  }

  .side-panel {
    border-right: 0;
    border-bottom: 1px solid #d8dee6;
  }
}
```

- [ ] **Step 7: Run UI tests**

Run:

```bash
python -m pytest tests/test_ui.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/handicap_ai/ui.py src/handicap_ai/templates/dashboard.html src/handicap_ai/static/dashboard.css tests/test_ui.py
git commit -m "feat: add local analyst dashboard"
```

## Task 10: Add UI CLI Command

**Files:**
- Modify: `src/handicap_ai/cli.py`
- Create: `tests/test_ui_cli.py`

- [ ] **Step 1: Write failing CLI command test**

Create `tests/test_ui_cli.py`:

```python
from typer.testing import CliRunner

from handicap_ai.cli import app


def test_ui_command_exposes_host_port_and_db_options():
    result = CliRunner().invoke(app, ["ui", "--help"])

    assert result.exit_code == 0
    assert "--db" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_ui_cli.py -v
```

Expected: FAIL because `ui` command does not exist.

- [ ] **Step 3: Add UI command**

Add imports to `src/handicap_ai/cli.py`:

```python
import uvicorn
from handicap_ai.ui import create_app
```

Add this command:

```python
@app.command("ui")
def ui(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    database = Database(db)
    database.migrate()
    console.print(f"Starting Handicap AI UI at http://{host}:{port}")
    uvicorn.run(create_app(db), host=host, port=port)
```

- [ ] **Step 4: Run UI CLI test**

Run:

```bash
python -m pytest tests/test_ui_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/cli.py tests/test_ui_cli.py
git commit -m "feat: add ui cli command"
```

## Task 11: Documentation and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Replace `README.md` with:

```markdown
# Handicap AI

Local football handicap analysis tool.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

If the standard `python` command points to the Windows Store alias, use the
bundled Codex Python executable for local verification.

## Import Historical Data

```bash
handicap-ai init-db --db data/handicap_ai.sqlite
handicap-ai import-football-data --db data/handicap_ai.sqlite --csv tests/fixtures/football_data_sample.csv --season 2026
handicap-ai import-history-folder --db data/handicap_ai.sqlite --path tests/fixtures/history_folder --season 2026
```

## Analyze Saved Odds HTML

```bash
handicap-ai scrape-match --db data/handicap_ai.sqlite --source betexplorer --html tests/fixtures/betexplorer_match.html
```

The saved-HTML flow is the stable fallback when a live odds site blocks
automated fetching or changes its page structure.

## Run Local UI

```bash
handicap-ai ui --db data/handicap_ai.sqlite --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and use the dashboard to analyze saved HTML.

## Output

The output includes:

- Handicap pick
- Total pick
- 1X2 pick
- Confidence
- Data quality
- Reasons
- Risk tags
- Source coverage

## Source Boundaries

The tool uses conservative, user-triggered scraping and saved HTML parsing. It
does not bypass login walls, paywalls, CAPTCHA, anti-bot protections, or access
controls. It does not place bets and does not claim certainty.
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run CLI smoke test**

Run:

```bash
python -m handicap_ai.cli init-db --db data/handicap_ai.sqlite
python -m handicap_ai.cli import-history-folder --db data/handicap_ai.sqlite --path tests/fixtures/history_folder --season 2026
python -m handicap_ai.cli scrape-match --db data/handicap_ai.sqlite --source betexplorer --html tests/fixtures/betexplorer_match.html
```

Expected output includes:

```text
Imported files: 1
Scraped England vs Panama from betexplorer
Handicap pick:
Total pick:
1X2 pick:
Source coverage: complete
```

- [ ] **Step 4: Verify local UI route manually**

Run:

```bash
python -m handicap_ai.cli ui --db data/handicap_ai.sqlite --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Expected: dashboard loads with home team, away team, source selection, saved HTML path, three result cards, source status, wizard panel, and risk tags panel.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document scraping ui workflow"
```

## Final Verification

- [ ] Run `git status --short --ignored` and confirm only ignored caches remain.
- [ ] Run `python -m pytest -q` and confirm every test passes.
- [ ] Run the CLI smoke test from Task 11 and confirm saved HTML analysis prints all three market pick lines.
- [ ] Start the UI and confirm `http://127.0.0.1:8000` renders the dashboard.
- [ ] Record any live BetExplorer/OddsPortal limitations as source warnings in the final response.
