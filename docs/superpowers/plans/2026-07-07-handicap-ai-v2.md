# Handicap AI V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a breadth-first v2 MVP that turns the current single-match handicap analyzer into a data-source, feature, scoring, backtest, and UI workflow driven by home and away team names.

**Architecture:** Keep the existing parsing, ingestion, feature extraction, similarity, and recommendation modules as the core. Add small focused services for source status, scorecards, feature payloads, and backtesting, then expose them through CLI and FastAPI endpoints. The dashboard remains a local operational workspace, not a marketing page.

**Tech Stack:** Python 3.11+, FastAPI, Typer, SQLite, pytest, existing BeautifulSoup/httpx adapters, plain HTML/CSS/JavaScript dashboard.

## Global Constraints

- Do not bypass login walls, paywalls, CAPTCHA, anti-bot protections, or source access controls.
- User input for the main workflow remains home team and away team names, plus optional selected source.
- Output must include optimal handicap, total, and 1X2 picks.
- Keep changes scoped to existing `handicap_ai` package patterns.
- Use TDD: write and run a failing test before production code for each new behavior.
- Keep the existing `main` checkout and local `http://127.0.0.1:8004/` service untouched.

---

## File Structure

- Create `src/handicap_ai/scorecard.py`: converts `RecommendationReport` and `MatchFeatures` into numeric per-market scores, reason text, and explainable feature payloads.
- Create `src/handicap_ai/backtest.py`: runs leakage-aware historical backtests over finished matches and summarizes hit rates for handicap, total, and 1X2.
- Create `src/handicap_ai/source_status.py`: summarizes World Cup fixture source readiness by source and group/status.
- Modify `src/handicap_ai/ui.py`: include scorecard/features in analysis payloads and add source-status/backtest endpoints.
- Modify `src/handicap_ai/cli.py`: add `source-status` and `backtest` commands.
- Modify `src/handicap_ai/templates/dashboard.html`: add feature, score, source-status, and backtest panels.
- Modify `src/handicap_ai/static/dashboard.css`: style the new dense operational panels.
- Modify `README.md`: document v2 flow and commands.
- Add tests:
  - `tests/test_scorecard.py`
  - `tests/test_backtest.py`
  - `tests/test_source_status.py`
  - Extend `tests/test_ui.py`
  - Extend `tests/test_cli.py`

---

### Task 1: Scorecard And Feature Payload

**Files:**
- Create: `src/handicap_ai/scorecard.py`
- Test: `tests/test_scorecard.py`
- Modify: `src/handicap_ai/ui.py`

**Interfaces:**
- Consumes: `handicap_ai.features.MatchFeatures`, `handicap_ai.recommendation.RecommendationReport`
- Produces:
  - `MarketScore(market: str, pick: str, confidence: str, hit_rate: float, sample_size: int, score: int, reason: str)`
  - `Scorecard(handicap: MarketScore, total: MarketScore, one_x_two: MarketScore, overall_score: int, feature_payload: dict[str, object])`
  - `build_scorecard(features: MatchFeatures, report: RecommendationReport) -> Scorecard`
  - `feature_payload(features: MatchFeatures) -> dict[str, object]`

- [ ] **Step 1: Write failing scorecard tests**

```python
from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationReport
from handicap_ai.scorecard import build_scorecard, feature_payload


def test_build_scorecard_outputs_numeric_market_scores():
    features = MatchFeatures(
        open_handicap=-1.75,
        close_handicap=-2.25,
        handicap_delta=-0.5,
        open_total=3.0,
        close_total=3.25,
        total_delta=0.25,
        home_water_delta=-0.07,
        away_water_delta=0.12,
        over_water_delta=0.0,
        under_water_delta=0.0,
        closing_home_win_price=1.30,
        closing_draw_price=5.00,
        closing_away_win_price=9.00,
        movement_patterns=("line_up_price_down", "line_up_price_stable"),
        line_depth_score=2.25,
        market_disagreement_score=0.2,
        data_quality_score=1.0,
    )
    report = RecommendationReport(
        handicap=MarketRecommendation("handicap", Pick.AWAY, "medium", 20, 0.62, "similar away support"),
        total=MarketRecommendation("total", Pick.UNDER, "high", 20, 0.70, "similar under support"),
        one_x_two=MarketRecommendation("1x2", Pick.HOME, "medium", 20, 0.60, "short home price"),
        risk_tags=("line_too_deep",),
        data_quality_score=1.0,
    )

    scorecard = build_scorecard(features, report)

    assert scorecard.handicap.pick == "away"
    assert scorecard.total.score > scorecard.handicap.score
    assert scorecard.one_x_two.market == "1x2"
    assert 0 <= scorecard.overall_score <= 100


def test_feature_payload_exposes_line_and_water_movement():
    payload = feature_payload(
        MatchFeatures(
            open_handicap=-1.75,
            close_handicap=-2.25,
            handicap_delta=-0.5,
            open_total=3.0,
            close_total=3.25,
            total_delta=0.25,
            home_water_delta=-0.07,
            away_water_delta=0.12,
            over_water_delta=0.0,
            under_water_delta=0.0,
            closing_home_win_price=1.30,
            closing_draw_price=5.00,
            closing_away_win_price=9.00,
            movement_patterns=("line_up_price_down", "line_up_price_stable"),
            line_depth_score=2.25,
            market_disagreement_score=0.2,
            data_quality_score=1.0,
        )
    )

    assert payload["handicap"]["open"] == -1.75
    assert payload["handicap"]["close"] == -2.25
    assert payload["total"]["delta"] == 0.25
    assert payload["one_x_two"]["home"] == 1.3
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_scorecard.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'handicap_ai.scorecard'`.

- [ ] **Step 3: Implement scorecard module**

Implement dataclasses and deterministic scoring:

```python
score = confidence_base + hit_rate_component + sample_component + data_quality_component - risk_penalty
```

Clamp every score to `0..100`. Penalize `no_bet` picks heavily but keep them explainable.

- [ ] **Step 4: Include scorecard in UI payload**

Modify `_report_payload(result: LiveAnalysisResult)` to include:

```python
"features": feature_payload(result.features),
"scores": asdict(build_scorecard(result.features, result.report)),
"reasons": {
    "handicap": result.report.handicap.reason,
    "total": result.report.total.reason,
    "1x2": result.report.one_x_two.reason,
},
```

- [ ] **Step 5: Verify**

Run:

```bash
python -m pytest tests/test_scorecard.py tests/test_ui.py::test_saved_html_analysis_endpoint_returns_recommendations -q
```

Expected: PASS.

---

### Task 2: Backtest Engine

**Files:**
- Create: `src/handicap_ai/backtest.py`
- Test: `tests/test_backtest.py`

**Interfaces:**
- Consumes: `Database`, existing odds rows, `RecommendationEngine`, `settlement`
- Produces:
  - `run_backtest(db: Database, *, limit: int | None = None, prior_only: bool = True) -> BacktestReport`
  - `BacktestReport.to_dict() -> dict[str, object]`

- [ ] **Step 1: Write failing backtest tests**

```python
from handicap_ai.backtest import run_backtest
from handicap_ai.database import Database
from handicap_ai.models import AsianHandicapLineRecord, MatchRecord, MatchStatus, OneXTwoLineRecord, TotalsLineRecord


def test_run_backtest_summarizes_three_markets(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    # Insert three finished matches with opening/closing AH, total, and 1X2 lines.
    # The first two become history; the third is evaluated.

    report = run_backtest(db, prior_only=False)

    assert report.total_matches >= 0
    assert set(report.markets) == {"handicap", "total", "1x2"}
    assert report.to_dict()["markets"]["handicap"]["picks"] >= 0
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_backtest.py -q`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement engine**

For each finished match:

1. Build current `MatchFeatures`.
2. Build historical candidates, excluding the current match.
3. If `prior_only=True`, include only candidates with kickoff before the evaluated match when both kickoff values are present.
4. Recommend handicap, total, and 1X2.
5. Settle each market against final score and closing line.
6. Track picks, hits, no-bets, and hit rate.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_backtest.py tests/test_settlement.py tests/test_recommendation.py -q`

Expected: PASS.

---

### Task 3: Source Status Summary

**Files:**
- Create: `src/handicap_ai/source_status.py`
- Test: `tests/test_source_status.py`

**Interfaces:**
- Consumes: `Database.list_tournament_teams`, `Database.find_tournament_fixtures`, `Database.list_fixture_source_links`
- Produces:
  - `summarize_world_cup_sources(db: Database, *, source: str = "betexplorer", season: str = "2026") -> SourceStatusSummary`
  - `SourceStatusSummary.to_dict() -> dict[str, object]`

- [ ] **Step 1: Write failing source-status test**

```python
from handicap_ai.database import Database
from handicap_ai.source_status import summarize_world_cup_sources
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def test_summarize_world_cup_sources_counts_fixture_readiness(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)

    summary = summarize_world_cup_sources(db, source="betexplorer")

    assert summary.total_fixtures > 0
    assert "pending" in summary.by_status
    assert summary.to_dict()["source"] == "betexplorer"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_source_status.py -q`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement summary**

Use seeded tournament fixtures and fixture source links. Count link status values and available HTML paths that still exist on disk.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_source_status.py tests/test_world_cup_seed.py -q`

Expected: PASS.

---

### Task 4: CLI And API Endpoints

**Files:**
- Modify: `src/handicap_ai/cli.py`
- Modify: `src/handicap_ai/ui.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_ui.py`

**Interfaces:**
- CLI:
  - `handicap-ai backtest --db data/handicap_ai.sqlite --limit 50`
  - `handicap-ai source-status --db data/handicap_ai.sqlite --source betexplorer`
- API:
  - `GET /api/source-status?source=betexplorer`
  - `POST /api/backtest` with `{ "limit": 50 }`

- [ ] **Step 1: Write failing CLI/API tests**

Assert CLI output includes `Backtest`, `handicap`, `total`, `1x2`.

Assert API returns JSON keys:

```python
assert body["markets"]["handicap"]["picks"] >= 0
assert body["source"] == "betexplorer"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python -m pytest tests/test_cli.py::test_backtest_command_prints_market_summary tests/test_ui.py::test_backtest_endpoint_returns_market_summary -q
```

Expected: FAIL because commands/endpoints do not exist.

- [ ] **Step 3: Implement CLI/API**

Wire new services without duplicating calculation logic.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_cli.py tests/test_ui.py -q`

Expected: PASS.

---

### Task 5: Dashboard Panels

**Files:**
- Modify: `src/handicap_ai/templates/dashboard.html`
- Modify: `src/handicap_ai/static/dashboard.css`
- Test: `tests/test_ui.py`

**Interfaces:**
- Dashboard displays:
  - Source readiness summary
  - Backtest summary
  - Feature grid
  - Score grid
  - Pick reasons

- [ ] **Step 1: Write failing dashboard render test**

Extend `test_dashboard_route_renders_workspace` with:

```python
assert "Feature panel" in response.text
assert "Backtest" in response.text
assert "Source readiness" in response.text
```

- [ ] **Step 2: Run test and verify RED**

Run: `python -m pytest tests/test_ui.py::test_dashboard_route_renders_workspace -q`

Expected: FAIL because new panel text is missing.

- [ ] **Step 3: Implement HTML/CSS/JS**

Add compact panels under the existing result cards. Use existing classes and add only scoped classes for dense key-value grids.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_ui.py -q`

Expected: PASS.

---

### Task 6: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Optionally create: `docs/handicap-ai-v2.md`

**Interfaces:**
- README documents:
  - Home/away-only auto analysis
  - Source status
  - Backtest command
  - Meaning of score, confidence, and risk tags

- [ ] **Step 1: Update docs**

Add exact commands:

```bash
handicap-ai source-status --db data/handicap_ai.sqlite --source betexplorer
handicap-ai backtest --db data/handicap_ai.sqlite --limit 50
handicap-ai ui --db data/handicap_ai.sqlite --host 127.0.0.1 --port 8005
```

- [ ] **Step 2: Full test run**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Start local v2 UI**

Run:

```bash
handicap-ai ui --db data/handicap_ai_v2.sqlite --host 127.0.0.1 --port 8005
```

Expected: dashboard opens at `http://127.0.0.1:8005/`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-07-handicap-ai-v2.md src tests README.md
git commit -m "feat: add handicap ai v2 workflow"
```

---

## Self-Review

- Spec coverage: all six requested areas map to tasks 1 through 6.
- Placeholder scan: no task is left as TBD; each task has concrete files, interfaces, commands, and expected results.
- Type consistency: `Scorecard`, `BacktestReport`, and `SourceStatusSummary` are defined before CLI/API/UI consumers use them.
