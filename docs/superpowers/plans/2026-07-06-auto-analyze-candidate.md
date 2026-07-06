# Auto Analyze Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automatic dashboard path where home team, away team, and source can produce handicap, total, and 1X2 recommendations by using cached HTML or by user-triggered discovery and fetch.

**Architecture:** Add a small `auto_analysis` orchestration module that composes existing candidate search, source discovery, source fetch, and saved HTML analysis functions. FastAPI exposes this orchestration through `/api/auto-analyze-candidate`, and the dashboard adds one `Auto analyze` button that renders the same candidate, source-link, and recommendation panels already used by the current workflow.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite-backed `Database`, existing BetExplorer/OddsPortal adapters, plain HTML/CSS/JavaScript dashboard, pytest, FastAPI TestClient.

---

## File Structure

- Create `src/handicap_ai/auto_analysis.py`
  - Owns auto-analysis statuses, result dataclass, dependency callables, and `auto_analyze_candidate()`.
  - Keeps orchestration out of `ui.py`.
- Create `tests/test_auto_analysis.py`
  - Unit-style tests for cached HTML, injected discovery/fetch success, manual-required discovery, blocked fetch, unsupported source, and preservation of available HTML.
- Modify `src/handicap_ai/ui.py`
  - Imports `auto_analyze_candidate()`.
  - Adds `AutoAnalyzeRequest`.
  - Adds optional server-side injection parameters to `create_app()` for deterministic tests.
  - Adds `/api/auto-analyze-candidate`.
  - Adds payload helpers for auto-analysis results.
- Modify `tests/test_ui.py`
  - API tests for success and blocked/manual states.
  - Dashboard markup/script assertions for the new button and endpoint.
- Modify `src/handicap_ai/templates/dashboard.html`
  - Adds `Auto analyze` button.
  - Adds rendering helpers so saved-HTML and auto-analysis share result rendering.
  - Adds `autoAnalyze()` event handler.
- Modify `src/handicap_ai/static/dashboard.css`
  - Gives the auto button the same restrained action styling as nearby controls.
- Modify `README.md`
  - Documents the automatic UI path and manual fallback.

---

### Task 1: Backend Auto-Analysis Orchestrator

**Files:**
- Create: `src/handicap_ai/auto_analysis.py`
- Create: `tests/test_auto_analysis.py`

- [ ] **Step 1: Write failing cached-HTML test**

Create `tests/test_auto_analysis.py` with this initial test:

```python
from pathlib import Path

import pytest

from handicap_ai.auto_analysis import AutoAnalyzeStatus, auto_analyze_candidate
from handicap_ai.database import Database
from handicap_ai.source_discovery import SourceLinkResult
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def england_panama_fixture(db):
    return db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]


def test_auto_analyze_uses_cached_available_html_without_network(tmp_path):
    db = seeded_db(tmp_path)
    fixture = england_panama_fixture(db)
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url="https://www.betexplorer.com/england-panama",
        status="available",
    )

    def discovery_runner(*args, **kwargs):
        raise AssertionError("cached auto-analysis must not discover")

    def fetch_runner(*args, **kwargs):
        raise AssertionError("cached auto-analysis must not fetch")

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert result.status is AutoAnalyzeStatus.ANALYSIS_READY
    assert result.stage == "analyzed"
    assert result.analysis is not None
    assert result.source_link is not None
    assert result.source_link.html_path == "tests/fixtures/betexplorer_match.html"
    assert result.candidate is not None
    assert result.candidate.home_team == "England"
    assert result.candidate.away_team == "Panama"
    assert result.warnings == ()
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_auto_analysis.py::test_auto_analyze_uses_cached_available_html_without_network -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'handicap_ai.auto_analysis'`.

- [ ] **Step 3: Implement minimal orchestrator for cached HTML**

Create `src/handicap_ai/auto_analysis.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from handicap_ai.candidate_search import FixtureCandidate, find_world_cup_candidates
from handicap_ai.database import Database
from handicap_ai.live_analysis import LiveAnalysisResult, analyze_saved_html
from handicap_ai.source_discovery import (
    SourceLinkResult,
    SourceLinkStatus,
    discover_fixture_source,
)
from handicap_ai.source_fetch import fetch_fixture_source_html
from handicap_ai.world_cup_seed import SEASON_2026


class AutoAnalyzeStatus(str, Enum):
    ANALYSIS_READY = "analysis_ready"
    INVALID_TEAM = "invalid_team"
    NOT_IN_GROUP_STAGE = "not_in_group_stage"
    NEEDS_MANUAL_SOURCE = "needs_manual_source"
    SOURCE_PENDING = "source_pending"
    FETCH_BLOCKED = "fetch_blocked"
    FETCH_FAILED = "fetch_failed"


DiscoveryRunner = Callable[
    [Database, str, str, str],
    SourceLinkResult,
]
FetchRunner = Callable[
    [Database, str, str, str, str | Path],
    SourceLinkResult,
]


@dataclass(frozen=True)
class AutoAnalyzeResult:
    status: AutoAnalyzeStatus
    stage: str
    warnings: tuple[str, ...]
    candidate: FixtureCandidate | None
    source_link: SourceLinkResult | None
    analysis: LiveAnalysisResult | None


def auto_analyze_candidate(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    cache_dir: str | Path,
    discovery_runner: DiscoveryRunner | None = None,
    fetch_runner: FetchRunner | None = None,
    season: str = SEASON_2026,
) -> AutoAnalyzeResult:
    discovery_runner = discovery_runner or _default_discovery_runner
    fetch_runner = fetch_runner or _default_fetch_runner
    candidates = find_world_cup_candidates(db, home_team, away_team, season)
    if candidates.status.value == AutoAnalyzeStatus.INVALID_TEAM.value:
        return AutoAnalyzeResult(
            status=AutoAnalyzeStatus.INVALID_TEAM,
            stage="candidate_checked",
            warnings=candidates.warnings,
            candidate=None,
            source_link=None,
            analysis=None,
        )
    if candidates.status.value == AutoAnalyzeStatus.NOT_IN_GROUP_STAGE.value:
        return AutoAnalyzeResult(
            status=AutoAnalyzeStatus.NOT_IN_GROUP_STAGE,
            stage="candidate_checked",
            warnings=candidates.warnings,
            candidate=None,
            source_link=None,
            analysis=None,
        )

    candidate = candidates.candidates[0]
    source_key = source.strip().lower()
    cached_link = candidate.sources.get(source_key)
    if (
        cached_link is not None
        and cached_link.status == SourceLinkStatus.AVAILABLE.value
        and cached_link.html_path
        and Path(cached_link.html_path).is_file()
    ):
        source_link = SourceLinkResult(
            status=SourceLinkStatus.AVAILABLE,
            fixture_id=candidate.fixture_id,
            source=source_key,
            html_path=cached_link.html_path,
            url=cached_link.url,
        )
        return _analysis_ready(db, candidate, source_link)

    return AutoAnalyzeResult(
        status=AutoAnalyzeStatus.NEEDS_MANUAL_SOURCE,
        stage="manual_required",
        warnings=("No cached HTML found",),
        candidate=candidate,
        source_link=None,
        analysis=None,
    )


def _analysis_ready(
    db: Database,
    candidate: FixtureCandidate,
    source_link: SourceLinkResult,
) -> AutoAnalyzeResult:
    analysis = analyze_saved_html(
        db=db,
        source=source_link.source,
        html_path=Path(source_link.html_path or ""),
    )
    return AutoAnalyzeResult(
        status=AutoAnalyzeStatus.ANALYSIS_READY,
        stage="analyzed",
        warnings=source_link.warnings,
        candidate=candidate,
        source_link=source_link,
        analysis=analysis,
    )


def _default_discovery_runner(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
) -> SourceLinkResult:
    return discover_fixture_source(db, home_team, away_team, source)


def _default_fetch_runner(
    db: Database,
    home_team: str,
    away_team: str,
    source: str,
    cache_dir: str | Path,
) -> SourceLinkResult:
    return fetch_fixture_source_html(db, home_team, away_team, source, cache_dir)
```

- [ ] **Step 4: Run cached-HTML test and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_auto_analysis.py::test_auto_analyze_uses_cached_available_html_without_network -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src\handicap_ai\auto_analysis.py tests\test_auto_analysis.py
git commit -m "feat: add cached auto analysis flow"
```

---

### Task 2: Discovery and Fetch Automation Paths

**Files:**
- Modify: `src/handicap_ai/auto_analysis.py`
- Modify: `tests/test_auto_analysis.py`

- [ ] **Step 1: Add failing tests for injected discovery and fetch**

Append to `tests/test_auto_analysis.py`:

```python
from handicap_ai.source_discovery import SourceLinkStatus, register_fixture_source_url
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html


def test_auto_analyze_discovers_fetches_and_analyzes_html(tmp_path):
    db = seeded_db(tmp_path)
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")
    calls = []

    def discovery_runner(db, home_team, away_team, source):
        calls.append("discover")
        return register_fixture_source_url(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        calls.append("fetch")

        def http_get(url):
            return FetchHttpResponse(url=url, status_code=200, text=html)

        return fetch_fixture_source_html(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            cache_dir=cache_dir,
            http_get=http_get,
        )

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert calls == ["discover", "fetch"]
    assert result.status is AutoAnalyzeStatus.ANALYSIS_READY
    assert result.stage == "analyzed"
    assert result.source_link is not None
    assert result.source_link.status is SourceLinkStatus.AVAILABLE
    assert result.source_link.html_path is not None
    assert Path(result.source_link.html_path).is_file()
    assert result.analysis is not None
```

- [ ] **Step 2: Add failing tests for manual-required and blocked states**

Append to `tests/test_auto_analysis.py`:

```python
def test_auto_analyze_returns_manual_source_when_discovery_has_no_url(tmp_path):
    db = seeded_db(tmp_path)

    def discovery_runner(db, home_team, away_team, source):
        fixture = england_panama_fixture(db)
        return SourceLinkResult(
            status=SourceLinkStatus.MANUAL_REQUIRED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url=None,
            warnings=("No source URL found for England vs Panama",),
        )

    def fetch_runner(*args, **kwargs):
        raise AssertionError("manual-required discovery must not fetch")

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert result.status is AutoAnalyzeStatus.NEEDS_MANUAL_SOURCE
    assert result.stage == "manual_required"
    assert result.analysis is None
    assert "No source URL found" in result.warnings[0]


def test_auto_analyze_returns_fetch_blocked_when_fetch_is_blocked(tmp_path):
    db = seeded_db(tmp_path)

    def discovery_runner(db, home_team, away_team, source):
        return register_fixture_source_url(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        fixture = england_panama_fixture(db)
        return SourceLinkResult(
            status=SourceLinkStatus.BLOCKED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url="https://www.betexplorer.com/england-panama",
            warnings=("source fetch blocked by source",),
        )

    result = auto_analyze_candidate(
        db,
        home_team="England",
        away_team="Panama",
        source="betexplorer",
        cache_dir=tmp_path / "cache",
        discovery_runner=discovery_runner,
        fetch_runner=fetch_runner,
    )

    assert result.status is AutoAnalyzeStatus.FETCH_BLOCKED
    assert result.stage == "manual_required"
    assert result.analysis is None
    assert result.source_link is not None
    assert result.source_link.status is SourceLinkStatus.BLOCKED
    assert result.warnings == ("source fetch blocked by source",)


def test_auto_analyze_rejects_unsupported_source(tmp_path):
    db = seeded_db(tmp_path)

    with pytest.raises(ValueError, match="unsupported source: unknown"):
        auto_analyze_candidate(
            db,
            home_team="England",
            away_team="Panama",
            source="unknown",
            cache_dir=tmp_path / "cache",
        )
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_auto_analysis.py -q
```

Expected: the new discovery/fetch tests fail because `auto_analyze_candidate()` stops at `needs_manual_source` after missing cached HTML, and the unsupported-source test fails because unsupported sources are not normalized before returning.

- [ ] **Step 4: Implement discovery/fetch path and status mapping**

Replace the final `NEEDS_MANUAL_SOURCE` return in `auto_analyze_candidate()` with this logic:

```python
    discovered = discovery_runner(db, home_team, away_team, source_key)
    if discovered.status is SourceLinkStatus.AVAILABLE and discovered.html_path:
        return _analysis_ready(db, candidate, discovered)
    if discovered.url is None:
        return _manual_result(candidate, discovered)

    fetched = fetch_runner(db, home_team, away_team, source_key, cache_dir)
    if (
        fetched.status is SourceLinkStatus.AVAILABLE
        and fetched.html_path
        and Path(fetched.html_path).is_file()
    ):
        return _analysis_ready(db, candidate, fetched)
    return _manual_result(candidate, fetched)
```

Add helper in `src/handicap_ai/auto_analysis.py`:

```python
def _manual_result(
    candidate: FixtureCandidate,
    source_link: SourceLinkResult,
) -> AutoAnalyzeResult:
    return AutoAnalyzeResult(
        status=_status_for_source_link(source_link),
        stage="manual_required",
        warnings=source_link.warnings,
        candidate=candidate,
        source_link=source_link,
        analysis=None,
    )


def _status_for_source_link(source_link: SourceLinkResult) -> AutoAnalyzeStatus:
    if source_link.status is SourceLinkStatus.BLOCKED:
        return AutoAnalyzeStatus.FETCH_BLOCKED
    if source_link.status is SourceLinkStatus.FAILED:
        return AutoAnalyzeStatus.FETCH_FAILED
    if source_link.status is SourceLinkStatus.PENDING:
        return AutoAnalyzeStatus.SOURCE_PENDING
    return AutoAnalyzeStatus.NEEDS_MANUAL_SOURCE
```

Also update the existing source-discovery import:

```python
from handicap_ai.source_discovery import (
    SourceLinkResult,
    SourceLinkStatus,
    discover_fixture_source,
    normalize_source,
)
```

Replace:

```python
    source_key = source.strip().lower()
```

with:

```python
    source_key = normalize_source(source)
```

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_auto_analysis.py -q
```

Expected: all `tests/test_auto_analysis.py` tests pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add src\handicap_ai\auto_analysis.py tests\test_auto_analysis.py
git commit -m "feat: automate source discovery and fetch analysis"
```

---

### Task 3: FastAPI Endpoint

**Files:**
- Modify: `src/handicap_ai/ui.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Add failing UI API tests**

Append to `tests/test_ui.py`:

```python
from handicap_ai.source_discovery import SourceLinkResult, SourceLinkStatus
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html


def test_auto_analyze_candidate_endpoint_uses_cached_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    db = Database(db_path)
    db.migrate()
    import_world_cup_2026_seed(db)
    fixture = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        "2026",
        "England",
        "Panama",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url="https://www.betexplorer.com/england-panama",
        status="available",
    )
    app = create_app(db_path=db_path, cache_dir=tmp_path / "cache")
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "analysis_ready"
    assert body["stage"] == "analyzed"
    assert body["candidate"]["home_team"] == "England"
    assert body["candidate"]["away_team"] == "Panama"
    assert body["source_link"]["status"] == "available"
    assert body["analysis"]["match"] == "England vs Panama"
    assert body["analysis"]["picks"]["handicap"] in {"home", "away", "no_bet"}
    assert body["analysis"]["picks"]["total"] in {"over", "under", "no_bet"}
    assert body["analysis"]["picks"]["1x2"] in {"home", "draw", "away", "no_bet"}
```

- [ ] **Step 2: Add failing injected discovery/fetch API test**

Append to `tests/test_ui.py`:

```python
def test_auto_analyze_candidate_endpoint_can_discover_and_fetch(tmp_path):
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    def discovery_runner(db, home_team, away_team, source):
        from handicap_ai.source_discovery import register_fixture_source_url

        return register_fixture_source_url(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        def http_get(url):
            return FetchHttpResponse(url=url, status_code=200, text=html)

        return fetch_fixture_source_html(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            cache_dir=cache_dir,
            http_get=http_get,
        )

    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
        auto_discovery_runner=discovery_runner,
        auto_fetch_runner=fetch_runner,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "analysis_ready"
    assert body["source_link"]["status"] == "available"
    assert Path(body["source_link"]["html_path"]).is_file()
    assert body["analysis"]["coverage"] == "complete"
```

- [ ] **Step 3: Add failing manual-state API test**

Append to `tests/test_ui.py`:

```python
def test_auto_analyze_candidate_endpoint_returns_manual_state(tmp_path):
    def discovery_runner(db, home_team, away_team, source):
        fixture = db.find_tournament_fixtures(
            FIFA_WORLD_CUP,
            "2026",
            "England",
            "Panama",
        )[0]
        return SourceLinkResult(
            status=SourceLinkStatus.MANUAL_REQUIRED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url=None,
            warnings=("No source URL found for England vs Panama",),
        )

    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
        auto_discovery_runner=discovery_runner,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_manual_source"
    assert body["stage"] == "manual_required"
    assert body["analysis"] is None
    assert "No source URL found" in body["warnings"][0]


def test_auto_analyze_candidate_endpoint_rejects_unsupported_source(tmp_path):
    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "unknown",
        },
    )

    assert response.status_code == 400
    assert "unsupported source" in response.json()["detail"]
```

- [ ] **Step 4: Run tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py::test_auto_analyze_candidate_endpoint_uses_cached_html tests/test_ui.py::test_auto_analyze_candidate_endpoint_can_discover_and_fetch tests/test_ui.py::test_auto_analyze_candidate_endpoint_returns_manual_state tests/test_ui.py::test_auto_analyze_candidate_endpoint_rejects_unsupported_source -q
```

Expected: FAIL with 404 for `/api/auto-analyze-candidate` or `TypeError` for unsupported `create_app()` keyword arguments.

- [ ] **Step 5: Implement endpoint and payload helpers**

Modify imports in `src/handicap_ai/ui.py`:

```python
from collections.abc import Callable

from handicap_ai.auto_analysis import AutoAnalyzeResult, auto_analyze_candidate
```

Add request model:

```python
class AutoAnalyzeRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
```

Add helper:

```python
def _auto_analyze_payload(result: AutoAnalyzeResult) -> dict[str, object]:
    return {
        "status": result.status.value,
        "stage": result.stage,
        "warnings": list(result.warnings),
        "candidate": (
            _candidate_payload(result.candidate)
            if result.candidate is not None
            else None
        ),
        "source_link": (
            _source_link_payload(result.source_link)
            if result.source_link is not None
            else None
        ),
        "analysis": (
            _report_payload(result.analysis)
            if result.analysis is not None
            else None
        ),
    }
```

Change `create_app()` signature:

```python
def create_app(
    db_path: Path,
    cache_dir: Path = Path("data/cache"),
    auto_discovery_runner: Callable | None = None,
    auto_fetch_runner: Callable | None = None,
) -> FastAPI:
```

Add endpoint inside `create_app()`:

```python
    @app.post("/api/auto-analyze-candidate")
    def auto_analyze_candidate_endpoint(payload: AutoAnalyzeRequest):
        try:
            result = auto_analyze_candidate(
                database,
                home_team=payload.home_team,
                away_team=payload.away_team,
                source=payload.source,
                cache_dir=cache_dir,
                discovery_runner=auto_discovery_runner,
                fetch_runner=auto_fetch_runner,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _auto_analyze_payload(result)
```

- [ ] **Step 6: Run endpoint tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_auto_analysis.py tests/test_ui.py -q
```

Expected: all tests in these files pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src\handicap_ai\ui.py tests\test_ui.py
git commit -m "feat: expose auto analyze api"
```

---

### Task 4: Dashboard Auto Analyze Button

**Files:**
- Modify: `src/handicap_ai/templates/dashboard.html`
- Modify: `src/handicap_ai/static/dashboard.css`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Add failing dashboard markup/script assertions**

Update `test_dashboard_route_renders_workspace()` in `tests/test_ui.py` with:

```python
    assert "Auto analyze" in response.text
    assert 'id="auto-analyze-button"' in response.text
    assert "/api/auto-analyze-candidate" in response.text
    assert "autoAnalyzeButton.disabled" in response.text
```

- [ ] **Step 2: Run dashboard test and verify RED**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py::test_dashboard_route_renders_workspace -q
```

Expected: FAIL because `Auto analyze` is not rendered.

- [ ] **Step 3: Add button and shared renderer**

In `src/handicap_ai/templates/dashboard.html`, add button after `Find candidates`:

```html
          <button id="find-candidates-button" type="button">Find candidates</button>
          <button id="auto-analyze-button" type="button">Auto analyze</button>
          <button type="submit">Analyze saved HTML</button>
```

Add constant near existing button constants:

```javascript
      const autoAnalyzeButton = document.querySelector("#auto-analyze-button");
```

Update `setSourceBusy()`:

```javascript
      function setSourceBusy(isBusy) {
        registerSourceUrlButton.disabled = isBusy;
        discoverSourcesButton.disabled = isBusy;
        fetchSourceHtmlButton.disabled = isBusy;
        autoAnalyzeButton.disabled = isBusy;
      }
```

Extract rendering helper above the `form.addEventListener()` block:

```javascript
      function renderAnalysis(body) {
        const teams = splitMatch(body.match);
        document.querySelector("#home-team").value = teams.home;
        document.querySelector("#away-team").value = teams.away;
        setText("#match-title", body.match);
        setText("#coverage-status", body.coverage);
        setText("#data-quality", Number(body.data_quality).toFixed(2));
        setText("#handicap-pick", body.picks.handicap);
        setText("#total-pick", body.picks.total);
        setText("#one-x-two-pick", body.picks["1x2"]);
        setText("#handicap-confidence", `${body.confidence.handicap} confidence`);
        setText("#total-confidence", `${body.confidence.total} confidence`);
        setText("#one-x-two-confidence", `${body.confidence["1x2"]} confidence`);

        const riskTags = document.querySelector("#risk-tags");
        riskTags.replaceChildren();
        const tags = body.risk_tags.length ? body.risk_tags : ["none"];
        for (const tag of tags) {
          const chip = document.createElement("span");
          chip.textContent = tag;
          riskTags.appendChild(chip);
        }
        setText("#risk-summary", `${tags.length} shown`);
      }
```

Add auto function:

```javascript
      async function autoAnalyze() {
        const requestId = sourceRequestId + 1;
        sourceRequestId = requestId;
        setSourceBusy(true);
        message.textContent = "Candidate confirmation";

        try {
          const response = await fetch("/api/auto-analyze-candidate", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(selectedFixture()),
          });

          if (!response.ok) {
            throw new Error(await errorMessage(response));
          }

          const body = await response.json();
          if (requestId !== sourceRequestId) {
            return;
          }

          if (body.candidate) {
            renderCandidates({
              status: body.status,
              warnings: body.warnings || [],
              candidates: [body.candidate],
            });
          }
          if (body.source_link) {
            renderSourceResult(body.source_link);
          }
          if (body.analysis) {
            setText("#source-status", body.source_link?.source || selectedSource());
            renderAnalysis(body.analysis);
            message.textContent = "Analysis ready";
          } else {
            message.textContent = body.warnings?.[0] || body.status;
            setText("#source-status", body.status);
          }
        } finally {
          if (requestId === sourceRequestId) {
            setSourceBusy(false);
          }
        }
      }
```

Add listener:

```javascript
      autoAnalyzeButton.addEventListener("click", async () => {
        try {
          await autoAnalyze();
        } catch (error) {
          message.textContent = error.message;
          setText("#source-status", "Error");
        }
      });
```

Replace duplicated rendering inside the existing saved-HTML submit handler with:

```javascript
          renderAnalysis(body);
          message.textContent = "Analysis ready";
```

Add CSS to `src/handicap_ai/static/dashboard.css` near existing source buttons:

```css
#auto-analyze-button {
  background: #153e75;
}

#auto-analyze-button:hover,
#auto-analyze-button:focus-visible {
  background: #0f2f5a;
}
```

- [ ] **Step 4: Run dashboard/UI tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py -q
```

Expected: all `tests/test_ui.py` tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add src\handicap_ai\templates\dashboard.html src\handicap_ai\static\dashboard.css tests\test_ui.py
git commit -m "feat: add dashboard auto analyze action"
```

---

### Task 5: Documentation, Verification, and Browser Smoke

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add this section after `## Discover and Cache Source HTML`:

```markdown
## Auto Analyze From UI

The dashboard can run the candidate workflow automatically after you enter home
and away teams. Click `Auto analyze` to check the seeded World Cup fixture,
reuse cached source HTML when available, or attempt source discovery and HTML
fetch for the selected source. If the source blocks automation or no URL is
found, the dashboard keeps the manual URL, fetch, and saved-HTML controls ready.
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_auto_analysis.py tests/test_ui.py tests/test_source_discovery.py tests/test_source_fetch.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run full tests**

Run:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q
```

Expected: all tests pass with only the existing Starlette deprecation warning.

- [ ] **Step 4: Start local UI for browser smoke**

Seed a deterministic smoke database and use an unused local port:

```powershell
$env:PYTHONPATH='C:\Users\30613\Documents\New project\.worktrees\auto-analyze-candidate\src'
$py='C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m handicap_ai.cli seed-world-cup --db data\auto-analyze-smoke.sqlite
& $py -m handicap_ai.cli register-source-url --db data\auto-analyze-smoke.sqlite --home England --away Panama --source betexplorer --url https://www.betexplorer.com/england-panama
& $py -m handicap_ai.cli fetch-source-html --db data\auto-analyze-smoke.sqlite --home England --away Panama --source betexplorer --cache-dir data\cache\auto-analyze-smoke --response-html tests\fixtures\betexplorer_match.html
& $py -m handicap_ai.cli ui --db data\auto-analyze-smoke.sqlite --host 127.0.0.1 --port 8004
```

Keep the process running only for the browser smoke, then stop it.

- [ ] **Step 5: Browser smoke**

Use the in-app browser:

1. Open `http://127.0.0.1:8004/`.
2. Confirm `Auto analyze` is visible.
3. Enter `England` as home team.
4. Enter `Panama` as away team.
5. Keep source as `BetExplorer`.
6. Click `Auto analyze`.
7. Confirm the recommendation cards do not show `No pick` for Handicap, Total, or 1X2.

- [ ] **Step 6: Commit Task 5**

```powershell
git add README.md
git commit -m "docs: document auto analyze workflow"
```

- [ ] **Step 7: Final review checkpoint**

Run:

```powershell
git status --short --branch
git log --oneline -6
```

Then request code review for the full feature range:

```powershell
git diff --stat 70fe1dcc73a5ac6a0aaab8f6359705944f0c8f30..HEAD
git diff 70fe1dcc73a5ac6a0aaab8f6359705944f0c8f30..HEAD
```

Review must check:

- Auto endpoint status mapping.
- No client-supplied `cache_dir`.
- Discovery/fetch failures preserve existing available HTML.
- UI does not hide manual fallback controls.
- Tests cover cached, discovery/fetch success, manual-required, blocked, and unsupported source paths.
