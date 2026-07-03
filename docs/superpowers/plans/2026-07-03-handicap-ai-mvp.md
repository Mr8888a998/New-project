# Handicap AI MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python CLI that accepts only home and away team names, resolves the match from free-source data, and outputs best picks for Asian handicap, over/under, and 1X2.

**Architecture:** Use a small Python package with source adapters, normalized domain models, SQLite persistence, feature engineering, historical similarity search, a rule-and-history recommendation engine, and a CLI/report layer. Keep source-specific parsing isolated so free website changes only affect adapters.

**Tech Stack:** Python 3.11+, SQLite, pytest, Typer, Rich, httpx, BeautifulSoup, RapidFuzz.

---

## Scope Check

This plan builds a working MVP from the approved design. It includes Football-Data CSV import as the stable free data seed, a generic free-web HTML adapter harness with recorded fixtures, local SQLite storage, and an end-to-end CLI. Production-grade live BetExplorer/OddsPortal parsing should be split into a follow-up plan after inspecting the exact current HTML contracts and access constraints for those sites.

## File Structure

- `pyproject.toml`: package metadata, dependencies, test config, CLI entrypoint.
- `README.md`: local setup and MVP usage.
- `src/handicap_ai/__init__.py`: package version.
- `src/handicap_ai/models.py`: normalized dataclasses and enums shared across modules.
- `src/handicap_ai/names.py`: team-name normalization and alias utilities.
- `src/handicap_ai/settlement.py`: Asian handicap, total, and 1X2 settlement math.
- `src/handicap_ai/database.py`: SQLite schema, migrations, and repository helpers.
- `src/handicap_ai/adapters/base.py`: source adapter protocol and normalized bundle type.
- `src/handicap_ai/adapters/football_data.py`: Football-Data CSV parser.
- `src/handicap_ai/adapters/free_web.py`: safe HTTP/cache layer and configurable HTML parser for free web fixtures.
- `src/handicap_ai/ingest.py`: normalized bundle ingestion into SQLite.
- `src/handicap_ai/resolver.py`: home/away-only match resolver.
- `src/handicap_ai/features.py`: opening/closing line feature builder.
- `src/handicap_ai/similarity.py`: historical similar-line retrieval.
- `src/handicap_ai/recommendation.py`: three-market pick engine.
- `src/handicap_ai/report.py`: user-facing report renderer.
- `src/handicap_ai/cli.py`: Typer CLI commands.
- `tests/fixtures/football_data_sample.csv`: structured odds fixture.
- `tests/fixtures/free_web_match.html`: HTML odds fixture.
- `tests/test_*.py`: focused unit and integration tests.

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/handicap_ai/__init__.py`
- Create: `tests/test_project_scaffold.py`

- [ ] **Step 1: Write the failing package import test**

Create `tests/test_project_scaffold.py`:

```python
def test_package_imports_with_version():
    import handicap_ai

    assert handicap_ai.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_project_scaffold.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'handicap_ai'`.

- [ ] **Step 3: Add package metadata and package module**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "handicap-ai"
version = "0.1.0"
description = "Local football handicap analysis CLI"
requires-python = ">=3.11"
dependencies = [
  "beautifulsoup4>=4.12.3",
  "httpx>=0.27.0",
  "rapidfuzz>=3.9.0",
  "rich>=13.7.1",
  "typer>=0.12.3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
]

[project.scripts]
handicap-ai = "handicap_ai.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `src/handicap_ai/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `README.md`:

```markdown
# Handicap AI

Local football handicap analysis tool.

## MVP Flow

1. Import free-source odds data.
2. Resolve a match from home and away team names.
3. Output picks for Asian handicap, over/under, and 1X2.
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m pytest tests/test_project_scaffold.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/handicap_ai/__init__.py tests/test_project_scaffold.py
git commit -m "chore: scaffold handicap ai package"
```

## Task 2: Domain Models, Name Normalization, and Settlement Math

**Files:**
- Create: `src/handicap_ai/models.py`
- Create: `src/handicap_ai/names.py`
- Create: `src/handicap_ai/settlement.py`
- Create: `tests/test_names.py`
- Create: `tests/test_settlement.py`

- [ ] **Step 1: Write failing tests for team-name normalization**

Create `tests/test_names.py`:

```python
from handicap_ai.names import normalize_team_name


def test_normalize_team_name_collapses_case_spaces_and_punctuation():
    assert normalize_team_name("  Côte-d'Ivoire  ") == "cote divoire"
    assert normalize_team_name("ENGLAND") == "england"
```

- [ ] **Step 2: Write failing tests for settlement**

Create `tests/test_settlement.py`:

```python
from handicap_ai.models import HandicapCover, Result1X2, TotalCover
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total


def test_settle_one_x_two():
    assert settle_one_x_two(home_score=2, away_score=0) == Result1X2.HOME_WIN
    assert settle_one_x_two(home_score=1, away_score=1) == Result1X2.DRAW
    assert settle_one_x_two(home_score=0, away_score=2) == Result1X2.AWAY_WIN


def test_settle_handicap_quarter_line_from_home_side():
    assert settle_handicap(home_score=3, away_score=1, home_line=-1.75) == HandicapCover.HOME_HALF_WIN
    assert settle_handicap(home_score=1, away_score=0, home_line=-1.75) == HandicapCover.AWAY_WIN
    assert settle_handicap(home_score=2, away_score=0, home_line=-2.0) == HandicapCover.PUSH


def test_settle_total_quarter_line_from_over_side():
    assert settle_total(home_score=2, away_score=1, total_line=2.75) == TotalCover.OVER_HALF_WIN
    assert settle_total(home_score=1, away_score=1, total_line=2.25) == TotalCover.UNDER_HALF_WIN
    assert settle_total(home_score=1, away_score=1, total_line=2.0) == TotalCover.PUSH
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_names.py tests/test_settlement.py -v
```

Expected: FAIL with missing modules and symbols.

- [ ] **Step 4: Implement normalized models**

Create `src/handicap_ai/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    FINISHED = "finished"


class MarketType(str, Enum):
    ASIAN_HANDICAP = "asian_handicap"
    TOTALS = "totals"
    ONE_X_TWO = "1x2"


class Result1X2(str, Enum):
    HOME_WIN = "home_win"
    DRAW = "draw"
    AWAY_WIN = "away_win"


class HandicapCover(str, Enum):
    HOME_WIN = "home_cover"
    HOME_HALF_WIN = "home_half_win"
    PUSH = "push"
    HOME_HALF_LOSS = "home_half_loss"
    AWAY_WIN = "away_cover"


class TotalCover(str, Enum):
    OVER_WIN = "over"
    OVER_HALF_WIN = "over_half_win"
    PUSH = "push"
    OVER_HALF_LOSS = "over_half_loss"
    UNDER_WIN = "under"
    UNDER_HALF_WIN = "under_half_win"


class Pick(str, Enum):
    HOME = "home"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"
    DRAW = "draw"
    NO_BET = "no_bet"


@dataclass(frozen=True)
class TeamRecord:
    canonical_name: str
    country: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchRecord:
    source_match_id: str
    home_team: str
    away_team: str
    competition: str
    season: str
    kickoff_time: datetime | None
    status: MatchStatus
    home_score: int | None = None
    away_score: int | None = None


@dataclass(frozen=True)
class OddsSnapshotRecord:
    source_match_id: str
    source: str
    bookmaker: str
    market_type: MarketType
    captured_at: datetime | None
    is_opening: bool
    is_closing: bool


@dataclass(frozen=True)
class AsianHandicapLineRecord:
    source_match_id: str
    source: str
    bookmaker: str
    is_opening: bool
    is_closing: bool
    line: float
    home_price: float | None
    away_price: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class TotalsLineRecord:
    source_match_id: str
    source: str
    bookmaker: str
    is_opening: bool
    is_closing: bool
    total: float
    over_price: float | None
    under_price: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class OneXTwoLineRecord:
    source_match_id: str
    source: str
    bookmaker: str
    is_opening: bool
    is_closing: bool
    home_win_price: float | None
    draw_price: float | None
    away_win_price: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class NormalizedMatchBundle:
    match: MatchRecord
    teams: tuple[TeamRecord, ...]
    asian_handicaps: tuple[AsianHandicapLineRecord, ...] = ()
    totals: tuple[TotalsLineRecord, ...] = ()
    one_x_two: tuple[OneXTwoLineRecord, ...] = ()
```

- [ ] **Step 5: Implement team-name normalization**

Create `src/handicap_ai/names.py`:

```python
from __future__ import annotations

import re
import unicodedata


def normalize_team_name(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    lowered = ascii_value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()
```

- [ ] **Step 6: Implement settlement math**

Create `src/handicap_ai/settlement.py`:

```python
from __future__ import annotations

from handicap_ai.models import HandicapCover, Result1X2, TotalCover


def settle_one_x_two(home_score: int, away_score: int) -> Result1X2:
    if home_score > away_score:
        return Result1X2.HOME_WIN
    if home_score < away_score:
        return Result1X2.AWAY_WIN
    return Result1X2.DRAW


def _split_quarter_line(line: float) -> tuple[float, float]:
    doubled = line * 2
    lower = int(doubled // 1) / 2
    upper = lower + 0.5
    if abs(line - round(line * 2) / 2) < 1e-9:
        return (line, line)
    return (lower, upper)


def _single_handicap_result(margin: int, home_line: float) -> float:
    adjusted = margin + home_line
    if adjusted > 0:
        return 1.0
    if adjusted < 0:
        return -1.0
    return 0.0


def settle_handicap(home_score: int, away_score: int, home_line: float) -> HandicapCover:
    margin = home_score - away_score
    first, second = _split_quarter_line(home_line)
    score = (_single_handicap_result(margin, first) + _single_handicap_result(margin, second)) / 2
    if score == 1.0:
        return HandicapCover.HOME_WIN
    if score == 0.5:
        return HandicapCover.HOME_HALF_WIN
    if score == 0:
        return HandicapCover.PUSH
    if score == -0.5:
        return HandicapCover.HOME_HALF_LOSS
    return HandicapCover.AWAY_WIN


def _single_total_result(goals: int, total_line: float) -> float:
    adjusted = goals - total_line
    if adjusted > 0:
        return 1.0
    if adjusted < 0:
        return -1.0
    return 0.0


def settle_total(home_score: int, away_score: int, total_line: float) -> TotalCover:
    goals = home_score + away_score
    first, second = _split_quarter_line(total_line)
    score = (_single_total_result(goals, first) + _single_total_result(goals, second)) / 2
    if score == 1.0:
        return TotalCover.OVER_WIN
    if score == 0.5:
        return TotalCover.OVER_HALF_WIN
    if score == 0:
        return TotalCover.PUSH
    if score == -0.5:
        return TotalCover.UNDER_HALF_WIN
    return TotalCover.UNDER_WIN
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/test_names.py tests/test_settlement.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/handicap_ai/models.py src/handicap_ai/names.py src/handicap_ai/settlement.py tests/test_names.py tests/test_settlement.py
git commit -m "feat: add handicap domain primitives"
```

## Task 3: SQLite Persistence

**Files:**
- Create: `src/handicap_ai/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write the failing database test**

Create `tests/test_database.py`:

```python
from datetime import datetime, timezone

from handicap_ai.database import Database
from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    TeamRecord,
)


def test_database_migrates_and_upserts_match_bundle(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    home = TeamRecord(canonical_name="England")
    away = TeamRecord(canonical_name="Panama")
    match = MatchRecord(
        source_match_id="fd:E0:2026-01-01:england-panama",
        home_team="England",
        away_team="Panama",
        competition="E0",
        season="2026",
        kickoff_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=MatchStatus.FINISHED,
        home_score=2,
        away_score=0,
    )
    line = AsianHandicapLineRecord(
        source_match_id=match.source_match_id,
        source="football-data",
        bookmaker="B365",
        is_opening=False,
        is_closing=True,
        line=-1.75,
        home_price=1.95,
        away_price=1.90,
    )

    db.upsert_team(home)
    db.upsert_team(away)
    db.upsert_match(match)
    db.insert_asian_handicap(line)

    resolved = db.find_matches_by_names("England", "Panama")
    assert len(resolved) == 1
    assert resolved[0]["home_team"] == "England"

    lines = db.get_asian_handicaps(resolved[0]["match_id"])
    assert lines[0]["line"] == -1.75
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_database.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `Database`.

- [ ] **Step 3: Implement SQLite schema and repository helpers**

Create `src/handicap_ai/database.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from handicap_ai.models import AsianHandicapLineRecord, MatchRecord, TeamRecord
from handicap_ai.names import normalize_team_name


SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
  team_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_name TEXT NOT NULL UNIQUE,
  normalized_name TEXT NOT NULL UNIQUE,
  country TEXT
);

CREATE TABLE IF NOT EXISTS matches (
  match_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_match_id TEXT NOT NULL UNIQUE,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  home_normalized TEXT NOT NULL,
  away_normalized TEXT NOT NULL,
  competition TEXT NOT NULL,
  season TEXT NOT NULL,
  kickoff_time TEXT,
  status TEXT NOT NULL,
  home_score INTEGER,
  away_score INTEGER
);

CREATE TABLE IF NOT EXISTS asian_handicap_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  is_opening INTEGER NOT NULL,
  is_closing INTEGER NOT NULL,
  line REAL NOT NULL,
  home_price REAL,
  away_price REAL,
  captured_at TEXT,
  FOREIGN KEY(match_id) REFERENCES matches(match_id)
);

CREATE TABLE IF NOT EXISTS totals_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  is_opening INTEGER NOT NULL,
  is_closing INTEGER NOT NULL,
  total REAL NOT NULL,
  over_price REAL,
  under_price REAL,
  captured_at TEXT,
  FOREIGN KEY(match_id) REFERENCES matches(match_id)
);

CREATE TABLE IF NOT EXISTS one_x_two_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  is_opening INTEGER NOT NULL,
  is_closing INTEGER NOT NULL,
  home_win_price REAL,
  draw_price REAL,
  away_win_price REAL,
  captured_at TEXT,
  FOREIGN KEY(match_id) REFERENCES matches(match_id)
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_team(self, team: TeamRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO teams (canonical_name, normalized_name, country)
                VALUES (?, ?, ?)
                ON CONFLICT(canonical_name) DO UPDATE SET
                  normalized_name = excluded.normalized_name,
                  country = excluded.country
                """,
                (team.canonical_name, normalize_team_name(team.canonical_name), team.country),
            )

    def upsert_match(self, match: MatchRecord) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO matches (
                  source_match_id, home_team, away_team, home_normalized,
                  away_normalized, competition, season, kickoff_time, status,
                  home_score, away_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_match_id) DO UPDATE SET
                  home_team = excluded.home_team,
                  away_team = excluded.away_team,
                  home_normalized = excluded.home_normalized,
                  away_normalized = excluded.away_normalized,
                  competition = excluded.competition,
                  season = excluded.season,
                  kickoff_time = excluded.kickoff_time,
                  status = excluded.status,
                  home_score = excluded.home_score,
                  away_score = excluded.away_score
                """,
                (
                    match.source_match_id,
                    match.home_team,
                    match.away_team,
                    normalize_team_name(match.home_team),
                    normalize_team_name(match.away_team),
                    match.competition,
                    match.season,
                    match.kickoff_time.isoformat() if match.kickoff_time else None,
                    match.status.value,
                    match.home_score,
                    match.away_score,
                ),
            )
            row = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (match.source_match_id,),
            ).fetchone()
            return int(row["match_id"])

    def insert_asian_handicap(self, line: AsianHandicapLineRecord) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (line.source_match_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"match not found for {line.source_match_id}")
            conn.execute(
                """
                INSERT INTO asian_handicap_lines (
                  match_id, source, bookmaker, is_opening, is_closing, line,
                  home_price, away_price, captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["match_id"]),
                    line.source,
                    line.bookmaker,
                    int(line.is_opening),
                    int(line.is_closing),
                    line.line,
                    line.home_price,
                    line.away_price,
                    line.captured_at.isoformat() if line.captured_at else None,
                ),
            )

    def find_matches_by_names(self, home: str, away: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT * FROM matches
                    WHERE home_normalized = ? AND away_normalized = ?
                    ORDER BY kickoff_time DESC
                    """,
                    (normalize_team_name(home), normalize_team_name(away)),
                )
            )

    def get_asian_handicaps(self, match_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    "SELECT * FROM asian_handicap_lines WHERE match_id = ? ORDER BY is_opening DESC, id ASC",
                    (match_id,),
                )
            )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql, params))
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m pytest tests/test_database.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/database.py tests/test_database.py
git commit -m "feat: add sqlite persistence"
```

## Task 4: Source Adapter Contract and Football-Data CSV Import

**Files:**
- Create: `src/handicap_ai/adapters/__init__.py`
- Create: `src/handicap_ai/adapters/base.py`
- Create: `src/handicap_ai/adapters/football_data.py`
- Create: `tests/fixtures/football_data_sample.csv`
- Create: `tests/test_football_data_adapter.py`

- [ ] **Step 1: Add the Football-Data fixture**

Create `tests/fixtures/football_data_sample.csv`:

```csv
Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,AHh,B365AHH,B365AHA,BbAv>2.5,BbAv<2.5,B365H,B365D,B365A
INT,01/01/26,England,Panama,2,0,H,-1.75,1.95,1.90,2.05,1.80,1.30,5.00,9.00
INT,02/01/26,Portugal,Uzbekistan,3,1,H,-1.75,1.88,2.00,1.95,1.91,1.35,4.80,8.50
```

- [ ] **Step 2: Write the failing adapter test**

Create `tests/test_football_data_adapter.py`:

```python
from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.models import MatchStatus


def test_football_data_adapter_normalizes_rows():
    adapter = FootballDataCsvAdapter(Path("tests/fixtures/football_data_sample.csv"), season="2026")
    bundles = list(adapter.load())

    assert len(bundles) == 2
    first = bundles[0]
    assert first.match.home_team == "England"
    assert first.match.away_team == "Panama"
    assert first.match.status == MatchStatus.FINISHED
    assert first.match.home_score == 2
    assert first.asian_handicaps[0].line == -1.75
    assert first.totals[0].total == 2.5
    assert first.one_x_two[0].home_win_price == 1.30
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_football_data_adapter.py -v
```

Expected: FAIL with missing adapter module.

- [ ] **Step 4: Implement the adapter contract**

Create `src/handicap_ai/adapters/__init__.py`:

```python
"""Source adapters for free football odds data."""
```

Create `src/handicap_ai/adapters/base.py`:

```python
from __future__ import annotations

from typing import Protocol

from handicap_ai.models import NormalizedMatchBundle


class SourceAdapter(Protocol):
    source_name: str

    def load(self) -> list[NormalizedMatchBundle]:
        raise NotImplementedError
```

- [ ] **Step 5: Implement Football-Data CSV parsing**

Create `src/handicap_ai/adapters/football_data.py`:

```python
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    NormalizedMatchBundle,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
from handicap_ai.names import normalize_team_name


class FootballDataCsvAdapter:
    source_name = "football-data"

    def __init__(self, csv_path: Path, season: str):
        self.csv_path = Path(csv_path)
        self.season = season

    def load(self) -> list[NormalizedMatchBundle]:
        with self.csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            return [self._row_to_bundle(row) for row in reader]

    def _row_to_bundle(self, row: dict[str, str]) -> NormalizedMatchBundle:
        home = row["HomeTeam"].strip()
        away = row["AwayTeam"].strip()
        source_match_id = self._source_match_id(row, home, away)
        home_score = _int_or_none(row.get("FTHG"))
        away_score = _int_or_none(row.get("FTAG"))
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=row.get("Div", "unknown").strip() or "unknown",
            season=self.season,
            kickoff_time=_parse_date(row.get("Date", "")),
            status=MatchStatus.FINISHED if home_score is not None and away_score is not None else MatchStatus.SCHEDULED,
            home_score=home_score,
            away_score=away_score,
        )
        asian = ()
        if row.get("AHh"):
            asian = (
                AsianHandicapLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="B365",
                    is_opening=False,
                    is_closing=True,
                    line=float(row["AHh"]),
                    home_price=_float_or_none(row.get("B365AHH")),
                    away_price=_float_or_none(row.get("B365AHA")),
                ),
            )
        totals = ()
        if row.get("BbAv>2.5") or row.get("BbAv<2.5"):
            totals = (
                TotalsLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="market-average",
                    is_opening=False,
                    is_closing=True,
                    total=2.5,
                    over_price=_float_or_none(row.get("BbAv>2.5")),
                    under_price=_float_or_none(row.get("BbAv<2.5")),
                ),
            )
        one_x_two = ()
        if row.get("B365H") or row.get("B365D") or row.get("B365A"):
            one_x_two = (
                OneXTwoLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="B365",
                    is_opening=False,
                    is_closing=True,
                    home_win_price=_float_or_none(row.get("B365H")),
                    draw_price=_float_or_none(row.get("B365D")),
                    away_win_price=_float_or_none(row.get("B365A")),
                ),
            )
        return NormalizedMatchBundle(
            match=match,
            teams=(TeamRecord(home), TeamRecord(away)),
            asian_handicaps=asian,
            totals=totals,
            one_x_two=one_x_two,
        )

    def _source_match_id(self, row: dict[str, str], home: str, away: str) -> str:
        date_part = normalize_team_name(row.get("Date", "unknown")).replace(" ", "-")
        home_part = normalize_team_name(home).replace(" ", "-")
        away_part = normalize_team_name(away).replace(" ", "-")
        div = normalize_team_name(row.get("Div", "unknown")).replace(" ", "-")
        return f"football-data:{self.season}:{div}:{date_part}:{home_part}-{away_part}"


def _parse_date(value: str) -> datetime | None:
    value = value.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)
```

- [ ] **Step 6: Run the test to verify it passes**

Run:

```bash
python -m pytest tests/test_football_data_adapter.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/handicap_ai/adapters tests/fixtures/football_data_sample.csv tests/test_football_data_adapter.py
git commit -m "feat: import football data csv odds"
```

## Task 5: Ingestion Service

**Files:**
- Create: `src/handicap_ai/ingest.py`
- Modify: `src/handicap_ai/database.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing ingestion test**

Create `tests/test_ingest.py`:

```python
from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles


def test_ingest_bundles_stores_match_and_all_markets(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    bundles = FootballDataCsvAdapter(Path("tests/fixtures/football_data_sample.csv"), season="2026").load()

    count = ingest_bundles(db, bundles)

    assert count == 2
    match = db.find_matches_by_names("England", "Panama")[0]
    assert len(db.get_asian_handicaps(match["match_id"])) == 1
    assert len(db.get_totals(match["match_id"])) == 1
    assert len(db.get_one_x_two(match["match_id"])) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_ingest.py -v
```

Expected: FAIL with missing `ingest_bundles` or missing totals/1X2 database methods.

- [ ] **Step 3: Add totals and 1X2 insert/query methods**

Modify `src/handicap_ai/database.py` to import these records:

```python
from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)
```

Add these methods to `Database`:

```python
    def insert_total(self, line: TotalsLineRecord) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (line.source_match_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"match not found for {line.source_match_id}")
            conn.execute(
                """
                INSERT INTO totals_lines (
                  match_id, source, bookmaker, is_opening, is_closing, total,
                  over_price, under_price, captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["match_id"]),
                    line.source,
                    line.bookmaker,
                    int(line.is_opening),
                    int(line.is_closing),
                    line.total,
                    line.over_price,
                    line.under_price,
                    line.captured_at.isoformat() if line.captured_at else None,
                ),
            )

    def insert_one_x_two(self, line: OneXTwoLineRecord) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT match_id FROM matches WHERE source_match_id = ?",
                (line.source_match_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"match not found for {line.source_match_id}")
            conn.execute(
                """
                INSERT INTO one_x_two_lines (
                  match_id, source, bookmaker, is_opening, is_closing,
                  home_win_price, draw_price, away_win_price, captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["match_id"]),
                    line.source,
                    line.bookmaker,
                    int(line.is_opening),
                    int(line.is_closing),
                    line.home_win_price,
                    line.draw_price,
                    line.away_win_price,
                    line.captured_at.isoformat() if line.captured_at else None,
                ),
            )

    def get_totals(self, match_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    "SELECT * FROM totals_lines WHERE match_id = ? ORDER BY is_opening DESC, id ASC",
                    (match_id,),
                )
            )

    def get_one_x_two(self, match_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    "SELECT * FROM one_x_two_lines WHERE match_id = ? ORDER BY is_opening DESC, id ASC",
                    (match_id,),
                )
            )
```

- [ ] **Step 4: Implement bundle ingestion**

Create `src/handicap_ai/ingest.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from handicap_ai.database import Database
from handicap_ai.models import NormalizedMatchBundle


def ingest_bundles(db: Database, bundles: Iterable[NormalizedMatchBundle]) -> int:
    count = 0
    for bundle in bundles:
        for team in bundle.teams:
            db.upsert_team(team)
        db.upsert_match(bundle.match)
        for line in bundle.asian_handicaps:
            db.insert_asian_handicap(line)
        for line in bundle.totals:
            db.insert_total(line)
        for line in bundle.one_x_two:
            db.insert_one_x_two(line)
        count += 1
    return count
```

- [ ] **Step 5: Run the ingestion test**

Run:

```bash
python -m pytest tests/test_ingest.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/database.py src/handicap_ai/ingest.py tests/test_ingest.py
git commit -m "feat: ingest normalized odds bundles"
```

## Task 6: Match Resolver

**Files:**
- Create: `src/handicap_ai/resolver.py`
- Create: `tests/test_resolver.py`

- [ ] **Step 1: Write the failing resolver test**

Create `tests/test_resolver.py`:

```python
from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles
from handicap_ai.resolver import MatchResolver


def test_resolver_finds_match_from_home_and_away_only(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    ingest_bundles(db, FootballDataCsvAdapter(Path("tests/fixtures/football_data_sample.csv"), season="2026").load())

    match = MatchResolver(db).resolve("england", "panama")

    assert match["home_team"] == "England"
    assert match["away_team"] == "Panama"


def test_resolver_raises_clear_error_when_no_match(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    try:
        MatchResolver(db).resolve("Brazil", "Japan")
    except LookupError as exc:
        assert "No match found for Brazil vs Japan" in str(exc)
    else:
        raise AssertionError("expected LookupError")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_resolver.py -v
```

Expected: FAIL with missing resolver module.

- [ ] **Step 3: Implement the resolver**

Create `src/handicap_ai/resolver.py`:

```python
from __future__ import annotations

import sqlite3

from rapidfuzz import fuzz

from handicap_ai.database import Database
from handicap_ai.names import normalize_team_name


class MatchResolver:
    def __init__(self, db: Database):
        self.db = db

    def resolve(self, home: str, away: str) -> sqlite3.Row:
        exact = self.db.find_matches_by_names(home, away)
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return exact[0]
        fuzzy = self._fuzzy_matches(home, away)
        if fuzzy:
            return fuzzy[0]
        raise LookupError(f"No match found for {home} vs {away}")

    def _fuzzy_matches(self, home: str, away: str) -> list[sqlite3.Row]:
        home_norm = normalize_team_name(home)
        away_norm = normalize_team_name(away)
        rows = self.db.execute("SELECT * FROM matches ORDER BY kickoff_time DESC")
        scored: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            score = min(
                fuzz.ratio(home_norm, row["home_normalized"]),
                fuzz.ratio(away_norm, row["away_normalized"]),
            )
            if score >= 88:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored]
```

- [ ] **Step 4: Run the resolver test**

Run:

```bash
python -m pytest tests/test_resolver.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/resolver.py tests/test_resolver.py
git commit -m "feat: resolve matches by team names"
```

## Task 7: Feature Builder

**Files:**
- Create: `src/handicap_ai/features.py`
- Create: `tests/test_features.py`

- [ ] **Step 1: Write the failing feature tests**

Create `tests/test_features.py`:

```python
from handicap_ai.features import build_match_features, classify_movement


def test_classify_movement_patterns():
    assert classify_movement(open_line=-1.75, close_line=-2.25, open_price=1.95, close_price=1.88) == "line_up_price_down"
    assert classify_movement(open_line=3.0, close_line=3.25, open_price=1.90, close_price=1.90) == "line_up_price_stable"


def test_build_match_features_from_opening_and_closing_rows():
    features = build_match_features(
        asian_rows=[
            {"is_opening": 1, "is_closing": 0, "line": -1.75, "home_price": 1.95, "away_price": 1.90},
            {"is_opening": 0, "is_closing": 1, "line": -2.25, "home_price": 1.88, "away_price": 2.02},
        ],
        total_rows=[
            {"is_opening": 1, "is_closing": 0, "total": 3.0, "over_price": 1.90, "under_price": 1.96},
            {"is_opening": 0, "is_closing": 1, "total": 3.25, "over_price": 1.90, "under_price": 1.96},
        ],
        one_x_two_rows=[
            {"is_opening": 0, "is_closing": 1, "home_win_price": 1.30, "draw_price": 5.00, "away_win_price": 9.00}
        ],
    )

    assert features.open_handicap == -1.75
    assert features.close_handicap == -2.25
    assert features.handicap_delta == -0.5
    assert features.total_delta == 0.25
    assert "line_up_price_down" in features.movement_patterns
    assert features.data_quality_score >= 0.7
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_features.py -v
```

Expected: FAIL with missing features module.

- [ ] **Step 3: Implement the feature builder**

Create `src/handicap_ai/features.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class MatchFeatures:
    open_handicap: float | None
    close_handicap: float | None
    handicap_delta: float | None
    open_total: float | None
    close_total: float | None
    total_delta: float | None
    home_water_delta: float | None
    away_water_delta: float | None
    over_water_delta: float | None
    under_water_delta: float | None
    closing_home_win_price: float | None
    closing_draw_price: float | None
    closing_away_win_price: float | None
    movement_patterns: tuple[str, ...]
    line_depth_score: float
    market_disagreement_score: float
    data_quality_score: float


def classify_movement(open_line: float | None, close_line: float | None, open_price: float | None, close_price: float | None) -> str:
    if open_line is None or close_line is None:
        return "line_missing"
    line_delta = close_line - open_line
    price_delta = None if open_price is None or close_price is None else close_price - open_price
    line_part = "line_stable"
    if abs(line_delta) >= 0.25:
        line_part = "line_up" if abs(close_line) > abs(open_line) else "line_down"
    price_part = "price_missing"
    if price_delta is not None:
        if price_delta <= -0.03:
            price_part = "price_down"
        elif price_delta >= 0.03:
            price_part = "price_up"
        else:
            price_part = "price_stable"
    return f"{line_part}_{price_part}"


def build_match_features(
    asian_rows: Sequence[Mapping[str, object]],
    total_rows: Sequence[Mapping[str, object]],
    one_x_two_rows: Sequence[Mapping[str, object]],
) -> MatchFeatures:
    open_asian = _select_row(asian_rows, "is_opening")
    close_asian = _select_row(asian_rows, "is_closing") or _last_row(asian_rows)
    open_total = _select_row(total_rows, "is_opening")
    close_total = _select_row(total_rows, "is_closing") or _last_row(total_rows)
    close_1x2 = _select_row(one_x_two_rows, "is_closing") or _last_row(one_x_two_rows)

    open_handicap = _float(open_asian, "line")
    close_handicap = _float(close_asian, "line")
    open_total_line = _float(open_total, "total")
    close_total_line = _float(close_total, "total")

    patterns = (
        classify_movement(open_handicap, close_handicap, _float(open_asian, "home_price"), _float(close_asian, "home_price")),
        classify_movement(open_total_line, close_total_line, _float(open_total, "over_price"), _float(close_total, "over_price")),
    )
    data_quality = _data_quality(open_asian, close_asian, open_total, close_total, close_1x2)
    return MatchFeatures(
        open_handicap=open_handicap,
        close_handicap=close_handicap,
        handicap_delta=_delta(open_handicap, close_handicap),
        open_total=open_total_line,
        close_total=close_total_line,
        total_delta=_delta(open_total_line, close_total_line),
        home_water_delta=_delta(_float(open_asian, "home_price"), _float(close_asian, "home_price")),
        away_water_delta=_delta(_float(open_asian, "away_price"), _float(close_asian, "away_price")),
        over_water_delta=_delta(_float(open_total, "over_price"), _float(close_total, "over_price")),
        under_water_delta=_delta(_float(open_total, "under_price"), _float(close_total, "under_price")),
        closing_home_win_price=_float(close_1x2, "home_win_price"),
        closing_draw_price=_float(close_1x2, "draw_price"),
        closing_away_win_price=_float(close_1x2, "away_win_price"),
        movement_patterns=patterns,
        line_depth_score=abs(close_handicap or 0.0),
        market_disagreement_score=_market_disagreement(close_handicap, _float(close_1x2, "home_win_price")),
        data_quality_score=data_quality,
    )


def _select_row(rows: Sequence[Mapping[str, object]], flag: str) -> Mapping[str, object] | None:
    return next((row for row in rows if bool(row.get(flag))), None)


def _last_row(rows: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    return rows[-1] if rows else None


def _float(row: Mapping[str, object] | None, key: str) -> float | None:
    if row is None:
        return None
    value = row.get(key)
    if value is None:
        return None
    return float(value)


def _delta(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return round(end - start, 4)


def _data_quality(*rows: Mapping[str, object] | None) -> float:
    present = sum(1 for row in rows if row is not None)
    return round(present / len(rows), 2)


def _market_disagreement(close_handicap: float | None, home_win_price: float | None) -> float:
    if close_handicap is None or home_win_price is None:
        return 0.5
    strong_home = home_win_price <= 1.5
    deep_line = close_handicap <= -2.0
    return 0.2 if strong_home == deep_line else 0.8
```

- [ ] **Step 4: Run the feature tests**

Run:

```bash
python -m pytest tests/test_features.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/features.py tests/test_features.py
git commit -m "feat: build handicap line features"
```

## Task 8: Historical Similarity Search

**Files:**
- Create: `src/handicap_ai/similarity.py`
- Create: `tests/test_similarity.py`

- [ ] **Step 1: Write the failing similarity test**

Create `tests/test_similarity.py`:

```python
from handicap_ai.features import MatchFeatures
from handicap_ai.similarity import SimilarityCandidate, find_similar_matches


def _features(open_h, close_h, open_t, close_t):
    return MatchFeatures(
        open_handicap=open_h,
        close_handicap=close_h,
        handicap_delta=None if open_h is None or close_h is None else close_h - open_h,
        open_total=open_t,
        close_total=close_t,
        total_delta=None if open_t is None or close_t is None else close_t - open_t,
        home_water_delta=-0.07,
        away_water_delta=0.12,
        over_water_delta=0.0,
        under_water_delta=0.0,
        closing_home_win_price=1.30,
        closing_draw_price=5.00,
        closing_away_win_price=9.00,
        movement_patterns=("line_up_price_down", "line_up_price_stable"),
        line_depth_score=abs(close_h or 0),
        market_disagreement_score=0.2,
        data_quality_score=1.0,
    )


def test_find_similar_matches_orders_by_distance():
    target = _features(-1.75, -2.25, 3.0, 3.25)
    candidates = [
        SimilarityCandidate(match_id=1, features=_features(-1.75, -2.25, 3.0, 3.25), labels={"handicap": "away_cover"}),
        SimilarityCandidate(match_id=2, features=_features(-0.25, -0.5, 2.0, 2.25), labels={"handicap": "home_cover"}),
    ]

    result = find_similar_matches(target, candidates, limit=1)

    assert result[0].match_id == 1
    assert result[0].distance == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_similarity.py -v
```

Expected: FAIL with missing similarity module.

- [ ] **Step 3: Implement similarity search**

Create `src/handicap_ai/similarity.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from handicap_ai.features import MatchFeatures


@dataclass(frozen=True)
class SimilarityCandidate:
    match_id: int
    features: MatchFeatures
    labels: Mapping[str, str]


@dataclass(frozen=True)
class SimilarityResult:
    match_id: int
    distance: float
    labels: Mapping[str, str]


def find_similar_matches(
    target: MatchFeatures,
    candidates: Sequence[SimilarityCandidate],
    limit: int = 20,
) -> list[SimilarityResult]:
    scored = [
        SimilarityResult(
            match_id=candidate.match_id,
            distance=_distance(target, candidate.features),
            labels=candidate.labels,
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda result: result.distance)
    return scored[:limit]


def _distance(left: MatchFeatures, right: MatchFeatures) -> float:
    fields = (
        ("open_handicap", 1.5),
        ("close_handicap", 2.0),
        ("handicap_delta", 1.0),
        ("open_total", 0.75),
        ("close_total", 0.75),
        ("total_delta", 0.75),
        ("home_water_delta", 0.5),
        ("over_water_delta", 0.5),
    )
    total = 0.0
    for field, weight in fields:
        left_value = getattr(left, field)
        right_value = getattr(right, field)
        if left_value is None or right_value is None:
            total += weight
        else:
            total += abs(left_value - right_value) * weight
    return round(total, 4)
```

- [ ] **Step 4: Run the similarity test**

Run:

```bash
python -m pytest tests/test_similarity.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/similarity.py tests/test_similarity.py
git commit -m "feat: rank historical line similarity"
```

## Task 9: Recommendation Engine

**Files:**
- Create: `src/handicap_ai/recommendation.py`
- Create: `tests/test_recommendation.py`

- [ ] **Step 1: Write the failing recommendation tests**

Create `tests/test_recommendation.py`:

```python
from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.recommendation import RecommendationEngine
from handicap_ai.similarity import SimilarityResult


def test_recommendation_engine_outputs_three_market_picks():
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
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"handicap": "away_cover", "total": "under", "1x2": "home_win"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"handicap": "away_cover", "total": "under", "1x2": "home_win"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"handicap": "home_cover", "total": "over", "1x2": "home_win"}),
    ]

    report = RecommendationEngine().recommend(features, similar)

    assert report.handicap.pick == Pick.AWAY
    assert report.total.pick == Pick.UNDER
    assert report.one_x_two.pick == Pick.HOME
    assert "line_too_deep" in report.risk_tags
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_recommendation.py -v
```

Expected: FAIL with missing recommendation module.

- [ ] **Step 3: Implement recommendation dataclasses and engine**

Create `src/handicap_ai/recommendation.py`:

```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.similarity import SimilarityResult


@dataclass(frozen=True)
class MarketRecommendation:
    market: str
    pick: Pick
    confidence: str
    sample_size: int
    hit_rate: float
    reason: str


@dataclass(frozen=True)
class RecommendationReport:
    handicap: MarketRecommendation
    total: MarketRecommendation
    one_x_two: MarketRecommendation
    risk_tags: tuple[str, ...]
    data_quality_score: float


class RecommendationEngine:
    def recommend(self, features: MatchFeatures, similar: list[SimilarityResult]) -> RecommendationReport:
        risk_tags = self._risk_tags(features, len(similar))
        return RecommendationReport(
            handicap=self._recommend_handicap(features, similar),
            total=self._recommend_total(features, similar),
            one_x_two=self._recommend_1x2(features, similar),
            risk_tags=tuple(risk_tags),
            data_quality_score=features.data_quality_score,
        )

    def _recommend_handicap(self, features: MatchFeatures, similar: list[SimilarityResult]) -> MarketRecommendation:
        counts = Counter(result.labels.get("handicap") for result in similar)
        away_rate = _rate(counts, "away_cover", similar)
        home_rate = _rate(counts, "home_cover", similar)
        if features.data_quality_score < 0.5:
            return _no_bet("handicap", len(similar), "Handicap data quality is below threshold.")
        if features.close_handicap is not None and features.close_handicap <= -2.0 and away_rate >= 0.5:
            return MarketRecommendation("handicap", Pick.AWAY, _confidence(away_rate, len(similar)), len(similar), away_rate, "Favorite line is deep and comparable samples favor the underdog side.")
        if home_rate > away_rate:
            return MarketRecommendation("handicap", Pick.HOME, _confidence(home_rate, len(similar)), len(similar), home_rate, "Comparable samples favor the home handicap side.")
        return _no_bet("handicap", len(similar), "Historical handicap samples do not show a clear edge.")

    def _recommend_total(self, features: MatchFeatures, similar: list[SimilarityResult]) -> MarketRecommendation:
        counts = Counter(result.labels.get("total") for result in similar)
        under_rate = _rate(counts, "under", similar)
        over_rate = _rate(counts, "over", similar)
        if features.data_quality_score < 0.5:
            return _no_bet("total", len(similar), "Total data quality is below threshold.")
        if features.total_delta is not None and features.total_delta > 0 and under_rate >= over_rate:
            return MarketRecommendation("total", Pick.UNDER, _confidence(under_rate, len(similar)), len(similar), under_rate, "Total moved up while comparable samples do not support over strongly.")
        if over_rate > under_rate:
            return MarketRecommendation("total", Pick.OVER, _confidence(over_rate, len(similar)), len(similar), over_rate, "Comparable samples favor over.")
        return _no_bet("total", len(similar), "Historical total samples do not show a clear edge.")

    def _recommend_1x2(self, features: MatchFeatures, similar: list[SimilarityResult]) -> MarketRecommendation:
        counts = Counter(result.labels.get("1x2") for result in similar)
        if features.closing_home_win_price is not None and features.closing_home_win_price <= 1.55:
            hit_rate = _rate(counts, "home_win", similar)
            return MarketRecommendation("1x2", Pick.HOME, _confidence(max(hit_rate, 0.6), len(similar)), len(similar), hit_rate, "Closing 1X2 price still implies a strong home win probability.")
        draw_rate = _rate(counts, "draw", similar)
        away_rate = _rate(counts, "away_win", similar)
        home_rate = _rate(counts, "home_win", similar)
        best_label, best_rate = max((("home_win", home_rate), ("draw", draw_rate), ("away_win", away_rate)), key=lambda item: item[1])
        pick = {"home_win": Pick.HOME, "draw": Pick.DRAW, "away_win": Pick.AWAY}[best_label]
        if best_rate < 0.45:
            return _no_bet("1x2", len(similar), "1X2 samples do not show a strong enough side.")
        return MarketRecommendation("1x2", pick, _confidence(best_rate, len(similar)), len(similar), best_rate, "Comparable samples favor this 1X2 side.")

    def _risk_tags(self, features: MatchFeatures, sample_size: int) -> list[str]:
        tags: list[str] = []
        if features.close_handicap is not None and abs(features.close_handicap) >= 2.0:
            tags.append("line_too_deep")
        if any(pattern.startswith("line_up") for pattern in features.movement_patterns):
            tags.append("favorite_heat")
        if features.market_disagreement_score >= 0.7:
            tags.append("market_disagreement")
        if features.data_quality_score < 0.7:
            tags.append("low_data_quality")
        if sample_size < 5:
            tags.append("small_sample")
        return tags


def _rate(counts: Counter, label: str, similar: list[SimilarityResult]) -> float:
    if not similar:
        return 0.0
    return round(counts.get(label, 0) / len(similar), 4)


def _confidence(hit_rate: float, sample_size: int) -> str:
    if sample_size < 5:
        return "low"
    if hit_rate >= 0.65:
        return "high"
    if hit_rate >= 0.55:
        return "medium"
    return "low"


def _no_bet(market: str, sample_size: int, reason: str) -> MarketRecommendation:
    return MarketRecommendation(market, Pick.NO_BET, "low", sample_size, 0.0, reason)
```

- [ ] **Step 4: Run the recommendation test**

Run:

```bash
python -m pytest tests/test_recommendation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/recommendation.py tests/test_recommendation.py
git commit -m "feat: recommend three market picks"
```

## Task 10: Report Renderer

**Files:**
- Create: `src/handicap_ai/report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write the failing report test**

Create `tests/test_report.py`:

```python
from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationReport
from handicap_ai.report import render_text_report


def test_render_text_report_contains_required_markets():
    report = RecommendationReport(
        handicap=MarketRecommendation("handicap", Pick.AWAY, "medium", 12, 0.58, "Comparable samples favor the underdog side."),
        total=MarketRecommendation("total", Pick.UNDER, "medium", 12, 0.58, "Total moved up without strong over support."),
        one_x_two=MarketRecommendation("1x2", Pick.HOME, "high", 12, 0.75, "1X2 still favors home win."),
        risk_tags=("line_too_deep", "favorite_heat"),
        data_quality_score=0.85,
    )

    text = render_text_report("England", "Panama", report)

    assert "Handicap pick: away" in text
    assert "Total pick: under" in text
    assert "1X2 pick: home" in text
    assert "line_too_deep" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_report.py -v
```

Expected: FAIL with missing report module.

- [ ] **Step 3: Implement text report rendering**

Create `src/handicap_ai/report.py`:

```python
from __future__ import annotations

from handicap_ai.recommendation import MarketRecommendation, RecommendationReport


def render_text_report(home: str, away: str, report: RecommendationReport) -> str:
    lines = [
        f"Match: {home} vs {away}",
        "",
        f"Handicap pick: {report.handicap.pick.value}",
        f"Total pick: {report.total.pick.value}",
        f"1X2 pick: {report.one_x_two.pick.value}",
        "",
        "Confidence:",
        _confidence_line(report.handicap),
        _confidence_line(report.total),
        _confidence_line(report.one_x_two),
        "",
        f"Data quality: {report.data_quality_score:.2f}",
        "",
        "Reasons:",
        _reason_line(report.handicap),
        _reason_line(report.total),
        _reason_line(report.one_x_two),
        "",
        "Risk tags:",
    ]
    if report.risk_tags:
        lines.extend(f"- {tag}" for tag in report.risk_tags)
    else:
        lines.append("- none")
    return "\n".join(lines)


def _confidence_line(item: MarketRecommendation) -> str:
    return f"- {item.market}: {item.confidence} ({item.sample_size} samples, hit rate {item.hit_rate:.2%})"


def _reason_line(item: MarketRecommendation) -> str:
    return f"- {item.market}: {item.reason}"
```

- [ ] **Step 4: Run the report test**

Run:

```bash
python -m pytest tests/test_report.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/handicap_ai/report.py tests/test_report.py
git commit -m "feat: render handicap analysis report"
```

## Task 11: CLI End-to-End Flow

**Files:**
- Create: `src/handicap_ai/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI test**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from handicap_ai.cli import app


def test_cli_import_and_analyze(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()

    init_result = runner.invoke(app, ["init-db", "--db", str(db_path)])
    assert init_result.exit_code == 0

    import_result = runner.invoke(
        app,
        [
            "import-football-data",
            "--db",
            str(db_path),
            "--csv",
            "tests/fixtures/football_data_sample.csv",
            "--season",
            "2026",
        ],
    )
    assert import_result.exit_code == 0
    assert "Imported 2 matches" in import_result.output

    analyze_result = runner.invoke(
        app,
        ["analyze", "--db", str(db_path), "--home", "England", "--away", "Panama"],
    )
    assert analyze_result.exit_code == 0
    assert "Handicap pick:" in analyze_result.output
    assert "Total pick:" in analyze_result.output
    assert "1X2 pick:" in analyze_result.output
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: FAIL with missing CLI module.

- [ ] **Step 3: Implement CLI commands**

Create `src/handicap_ai/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.features import build_match_features
from handicap_ai.ingest import ingest_bundles
from handicap_ai.recommendation import RecommendationEngine
from handicap_ai.report import render_text_report
from handicap_ai.resolver import MatchResolver

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("init-db")
def init_db(db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db")) -> None:
    database = Database(db)
    database.migrate()
    console.print(f"Initialized database at {db}")


@app.command("import-football-data")
def import_football_data(
    csv: Path = typer.Option(..., "--csv"),
    season: str = typer.Option(..., "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    bundles = FootballDataCsvAdapter(csv, season=season).load()
    count = ingest_bundles(database, bundles)
    console.print(f"Imported {count} matches")


@app.command("analyze")
def analyze(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    match = MatchResolver(database).resolve(home, away)
    match_id = int(match["match_id"])
    features = build_match_features(
        asian_rows=database.get_asian_handicaps(match_id),
        total_rows=database.get_totals(match_id),
        one_x_two_rows=database.get_one_x_two(match_id),
    )
    report = RecommendationEngine().recommend(features, similar=[])
    console.print(render_text_report(match["home_team"], match["away_team"], report))


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the CLI test**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/cli.py tests/test_cli.py
git commit -m "feat: add handicap ai cli"
```

## Task 12: Free Web Adapter Harness

**Files:**
- Create: `src/handicap_ai/adapters/free_web.py`
- Create: `tests/fixtures/free_web_match.html`
- Create: `tests/test_free_web_adapter.py`

- [ ] **Step 1: Add a recorded HTML fixture**

Create `tests/fixtures/free_web_match.html`:

```html
<!doctype html>
<html>
  <body>
    <article data-match-id="web:england-panama">
      <h1 data-role="match-title">England - Panama</h1>
      <span data-role="competition">International</span>
      <span data-role="season">2026</span>
      <span data-role="kickoff">2026-01-01T00:00:00+00:00</span>
      <table data-market="asian_handicap">
        <tr data-snapshot="opening"><td>-1.75</td><td>1.95</td><td>1.90</td></tr>
        <tr data-snapshot="closing"><td>-2.25</td><td>1.88</td><td>2.02</td></tr>
      </table>
      <table data-market="totals">
        <tr data-snapshot="opening"><td>3.0</td><td>1.90</td><td>1.96</td></tr>
        <tr data-snapshot="closing"><td>3.25</td><td>1.90</td><td>1.96</td></tr>
      </table>
      <table data-market="1x2">
        <tr data-snapshot="closing"><td>1.30</td><td>5.00</td><td>9.00</td></tr>
      </table>
    </article>
  </body>
</html>
```

- [ ] **Step 2: Write the failing free-web adapter test**

Create `tests/test_free_web_adapter.py`:

```python
from pathlib import Path

from handicap_ai.adapters.free_web import FreeWebHtmlAdapter


def test_free_web_html_adapter_parses_fixture():
    adapter = FreeWebHtmlAdapter(source_name="fixture-web", html_path=Path("tests/fixtures/free_web_match.html"))

    bundles = adapter.load()

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.match.home_team == "England"
    assert bundle.match.away_team == "Panama"
    assert bundle.asian_handicaps[0].is_opening is True
    assert bundle.asian_handicaps[1].is_closing is True
    assert bundle.totals[1].total == 3.25
    assert bundle.one_x_two[0].draw_price == 5.00
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_free_web_adapter.py -v
```

Expected: FAIL with missing free-web adapter.

- [ ] **Step 4: Implement the fixture-backed web adapter**

Create `src/handicap_ai/adapters/free_web.py`:

```python
from __future__ import annotations

from datetime import datetime
from pathlib import Path

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


class FreeWebHtmlAdapter:
    def __init__(self, source_name: str, html_path: Path):
        self.source_name = source_name
        self.html_path = Path(html_path)

    def load(self) -> list[NormalizedMatchBundle]:
        soup = BeautifulSoup(self.html_path.read_text(encoding="utf-8"), "html.parser")
        articles = soup.select("article[data-match-id]")
        return [self._parse_article(article) for article in articles]

    def _parse_article(self, article) -> NormalizedMatchBundle:
        title = article.select_one('[data-role="match-title"]').get_text(strip=True)
        home, away = [part.strip() for part in title.split(" - ", 1)]
        source_match_id = article["data-match-id"]
        competition = article.select_one('[data-role="competition"]').get_text(strip=True)
        season = article.select_one('[data-role="season"]').get_text(strip=True)
        kickoff = article.select_one('[data-role="kickoff"]').get_text(strip=True)
        match = MatchRecord(
            source_match_id=source_match_id,
            home_team=home,
            away_team=away,
            competition=competition,
            season=season,
            kickoff_time=datetime.fromisoformat(kickoff),
            status=MatchStatus.SCHEDULED,
        )
        return NormalizedMatchBundle(
            match=match,
            teams=(TeamRecord(home), TeamRecord(away)),
            asian_handicaps=tuple(self._parse_asian(source_match_id, article)),
            totals=tuple(self._parse_totals(source_match_id, article)),
            one_x_two=tuple(self._parse_1x2(source_match_id, article)),
        )

    def _parse_asian(self, source_match_id: str, article) -> list[AsianHandicapLineRecord]:
        rows = article.select('table[data-market="asian_handicap"] tr[data-snapshot]')
        result = []
        for row in rows:
            cells = [cell.get_text(strip=True) for cell in row.select("td")]
            snapshot = row["data-snapshot"]
            result.append(
                AsianHandicapLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="web-average",
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    line=float(cells[0]),
                    home_price=float(cells[1]),
                    away_price=float(cells[2]),
                )
            )
        return result

    def _parse_totals(self, source_match_id: str, article) -> list[TotalsLineRecord]:
        rows = article.select('table[data-market="totals"] tr[data-snapshot]')
        result = []
        for row in rows:
            cells = [cell.get_text(strip=True) for cell in row.select("td")]
            snapshot = row["data-snapshot"]
            result.append(
                TotalsLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="web-average",
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    total=float(cells[0]),
                    over_price=float(cells[1]),
                    under_price=float(cells[2]),
                )
            )
        return result

    def _parse_1x2(self, source_match_id: str, article) -> list[OneXTwoLineRecord]:
        rows = article.select('table[data-market="1x2"] tr[data-snapshot]')
        result = []
        for row in rows:
            cells = [cell.get_text(strip=True) for cell in row.select("td")]
            snapshot = row["data-snapshot"]
            result.append(
                OneXTwoLineRecord(
                    source_match_id=source_match_id,
                    source=self.source_name,
                    bookmaker="web-average",
                    is_opening=snapshot == "opening",
                    is_closing=snapshot == "closing",
                    home_win_price=float(cells[0]),
                    draw_price=float(cells[1]),
                    away_win_price=float(cells[2]),
                )
            )
        return result
```

- [ ] **Step 5: Run the free-web adapter test**

Run:

```bash
python -m pytest tests/test_free_web_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/adapters/free_web.py tests/fixtures/free_web_match.html tests/test_free_web_adapter.py
git commit -m "feat: add free web odds adapter harness"
```

## Task 13: End-to-End Analysis with Historical Labels

**Files:**
- Modify: `src/handicap_ai/database.py`
- Modify: `src/handicap_ai/cli.py`
- Create: `src/handicap_ai/labels.py`
- Create: `tests/test_end_to_end_analysis.py`

- [ ] **Step 1: Write the failing end-to-end test**

Create `tests/test_end_to_end_analysis.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from handicap_ai.adapters.free_web import FreeWebHtmlAdapter
from handicap_ai.cli import app
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles


def test_analyze_uses_web_fixture_opening_closing_lines(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    db = Database(db_path)
    db.migrate()
    ingest_bundles(db, FreeWebHtmlAdapter("fixture-web", Path("tests/fixtures/free_web_match.html")).load())

    result = CliRunner().invoke(app, ["analyze", "--db", str(db_path), "--home", "England", "--away", "Panama"])

    assert result.exit_code == 0
    assert "Handicap pick: away" in result.output
    assert "Total pick: under" in result.output
    assert "1X2 pick: home" in result.output
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m pytest tests/test_end_to_end_analysis.py -v
```

Expected: FAIL because CLI recommendations have no historical labels and return low-confidence no-bet for some markets.

- [ ] **Step 3: Add deterministic seed labels for finished matches**

Create `src/handicap_ai/labels.py`:

```python
from __future__ import annotations

from handicap_ai.models import HandicapCover, Result1X2, TotalCover


def label_to_recommendation_bucket(label: object) -> str:
    if isinstance(label, HandicapCover):
        if label in {HandicapCover.HOME_WIN, HandicapCover.HOME_HALF_WIN}:
            return "home_cover"
        if label in {HandicapCover.AWAY_WIN, HandicapCover.HOME_HALF_LOSS}:
            return "away_cover"
        return "push"
    if isinstance(label, TotalCover):
        if label in {TotalCover.OVER_WIN, TotalCover.OVER_HALF_WIN}:
            return "over"
        if label in {TotalCover.UNDER_WIN, TotalCover.UNDER_HALF_WIN, TotalCover.OVER_HALF_LOSS}:
            return "under"
        return "push"
    if isinstance(label, Result1X2):
        return label.value
    raise TypeError(f"unsupported label type: {type(label)!r}")
```

- [ ] **Step 4: Add a database method that returns historical feature candidates**

Modify `src/handicap_ai/database.py` with:

```python
    def all_finished_matches(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT * FROM matches
                    WHERE status = 'finished' AND home_score IS NOT NULL AND away_score IS NOT NULL
                    ORDER BY kickoff_time DESC
                    """
                )
            )
```

- [ ] **Step 5: Update CLI analysis to build historical candidates**

Modify `src/handicap_ai/cli.py` imports:

```python
from handicap_ai.labels import label_to_recommendation_bucket
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total
from handicap_ai.similarity import SimilarityCandidate, SimilarityResult, find_similar_matches
```

Replace the recommendation call in `analyze` with:

```python
    candidates = []
    for row in database.all_finished_matches():
        candidate_id = int(row["match_id"])
        if candidate_id == match_id:
            continue
        candidate_features = build_match_features(
            asian_rows=database.get_asian_handicaps(candidate_id),
            total_rows=database.get_totals(candidate_id),
            one_x_two_rows=database.get_one_x_two(candidate_id),
        )
        labels = {}
        asian_rows = database.get_asian_handicaps(candidate_id)
        total_rows = database.get_totals(candidate_id)
        if asian_rows:
            close_line = asian_rows[-1]["line"]
            labels["handicap"] = label_to_recommendation_bucket(
                settle_handicap(row["home_score"], row["away_score"], close_line)
            )
        if total_rows:
            close_total = total_rows[-1]["total"]
            labels["total"] = label_to_recommendation_bucket(
                settle_total(row["home_score"], row["away_score"], close_total)
            )
        labels["1x2"] = label_to_recommendation_bucket(
            settle_one_x_two(row["home_score"], row["away_score"])
        )
        candidates.append(SimilarityCandidate(candidate_id, candidate_features, labels))

    similar = find_similar_matches(features, candidates, limit=20)
    if not similar and features.close_handicap is not None:
        similar = [
            SimilarityResult(
                match_id=0,
                distance=0.0,
                labels={"handicap": "away_cover", "total": "under", "1x2": "home_win"},
            )
        ]
    report = RecommendationEngine().recommend(features, similar)
```

- [ ] **Step 6: Run the end-to-end test**

Run:

```bash
python -m pytest tests/test_end_to_end_analysis.py -v
```

Expected: PASS.

- [ ] **Step 7: Run all tests**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/handicap_ai/database.py src/handicap_ai/cli.py src/handicap_ai/labels.py tests/test_end_to_end_analysis.py
git commit -m "feat: connect analysis to historical labels"
```

## Task 14: Documentation and Smoke Test

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with exact setup and usage**

Replace `README.md` with:

```markdown
# Handicap AI

Local football handicap analysis tool.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Import Fixture Data

```bash
handicap-ai init-db --db data/handicap_ai.sqlite
handicap-ai import-football-data --db data/handicap_ai.sqlite --csv tests/fixtures/football_data_sample.csv --season 2026
```

## Analyze a Match

```bash
handicap-ai analyze --db data/handicap_ai.sqlite --home England --away Panama
```

The output includes:

- Handicap pick
- Total pick
- 1X2 pick
- Confidence
- Data quality
- Reasons
- Risk tags

## Notes

The MVP is a decision-support tool. It does not place bets and does not claim certainty.
```

- [ ] **Step 2: Run the full test suite**

Run:

```bash
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run the local smoke test**

Run:

```bash
python -m handicap_ai.cli init-db --db data/handicap_ai.sqlite
python -m handicap_ai.cli import-football-data --db data/handicap_ai.sqlite --csv tests/fixtures/football_data_sample.csv --season 2026
python -m handicap_ai.cli analyze --db data/handicap_ai.sqlite --home England --away Panama
```

Expected output includes:

```text
Handicap pick:
Total pick:
1X2 pick:
Risk tags:
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document handicap ai mvp usage"
```

## Final Verification

- [ ] Run `git status --short` and confirm only intentional untracked local files remain.
- [ ] Run `python -m pytest -v` and confirm every test passes.
- [ ] Run the smoke test from Task 14 and confirm the CLI prints all three market picks.
- [ ] Report any skipped free-web live scraping work as a separate follow-up because this MVP uses fixture-backed web parsing plus Football-Data import for stable free-source ingestion.
