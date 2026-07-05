# World Cup Candidate Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local 2026 World Cup candidate wizard so the user can enter home and away team names, confirm a seeded fixture, and then run the existing saved-HTML analysis workflow.

**Architecture:** Extend SQLite with tournament seed tables that sit beside the existing odds `matches` table. Add a deterministic `world_cup_seed` importer, a `candidate_search` service that resolves aliases and fixture candidates, then expose that service through CLI commands and FastAPI dashboard endpoints. The UI stays fixture/saved-HTML backed; no live BetExplorer/OddsPortal search is added in this phase.

**Tech Stack:** Python 3.11+, SQLite, Typer, FastAPI, Jinja2, pytest.

---

## Scope Check

This plan implements the confirmed design in `docs/superpowers/specs/2026-07-05-world-cup-candidate-wizard-design.md`.

It includes:

- 2026 World Cup team and group-stage fixture seed data.
- SQLite tables and methods for tournament teams, fixtures, source links, and aliases.
- Candidate search for exact names and known aliases.
- CLI commands for seeding and finding candidates.
- UI changes for home/away entry, candidate confirmation, and saved HTML analysis.

It does not include live source-page search, CAPTCHA handling, account login, paid data, automated betting, or downloading full third-party pages into git.

## File Structure

- `src/handicap_ai/database.py`: add tournament seed schema and CRUD helpers.
- `src/handicap_ai/world_cup_seed.py`: define 2026 World Cup groups, aliases, generated group fixtures, and import helper.
- `src/handicap_ai/candidate_search.py`: resolve team names, find seeded fixtures, attach saved HTML source-link status.
- `src/handicap_ai/cli.py`: add `seed-world-cup` and `find-candidates` commands.
- `src/handicap_ai/ui.py`: add candidate lookup and candidate-analysis endpoints.
- `src/handicap_ai/templates/dashboard.html`: make team fields editable, add candidate wizard panel, keep saved HTML analysis.
- `src/handicap_ai/static/dashboard.css`: style wizard states and candidate cards.
- `tests/test_tournament_database.py`: database tests for seed tables.
- `tests/test_world_cup_seed.py`: seed data and idempotent import tests.
- `tests/test_candidate_search.py`: service tests for aliases, candidate states, and source links.
- `tests/test_world_cup_cli.py`: CLI seed/find tests.
- `tests/test_ui.py`: extend existing UI tests for candidate wizard endpoints and page controls.

## Task 1: Add Tournament Seed Tables

**Files:**
- Modify: `src/handicap_ai/database.py`
- Create: `tests/test_tournament_database.py`

- [ ] **Step 1: Write failing database tests**

Create `tests/test_tournament_database.py`:

```python
from handicap_ai.database import Database


def test_database_upserts_tournament_teams_idempotently(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    db.upsert_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        team_name="England",
        country="England",
    )
    db.upsert_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        team_name="England",
        country="England",
    )

    rows = db.list_tournament_teams("fifa_world_cup", "2026")
    assert len(rows) == 1
    assert rows[0]["team_name"] == "England"
    assert rows[0]["group_name"] == "L"


def test_database_upserts_tournament_fixtures_and_source_links(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    fixture_id = db.upsert_tournament_fixture(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        home_team="England",
        away_team="Ghana",
        kickoff_time=None,
        status="scheduled",
    )
    second_id = db.upsert_tournament_fixture(
        tournament="fifa_world_cup",
        season="2026",
        group_name="L",
        home_team="England",
        away_team="Ghana",
        kickoff_time=None,
        status="scheduled",
    )
    db.upsert_fixture_source_link(
        fixture_id=fixture_id,
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url=None,
        status="available",
    )

    assert second_id == fixture_id
    fixtures = db.find_tournament_fixtures(
        tournament="fifa_world_cup",
        season="2026",
        home_team="England",
        away_team="Ghana",
    )
    assert len(fixtures) == 1
    assert fixtures[0]["fixture_id"] == fixture_id
    links = db.list_fixture_source_links(fixture_id)
    assert len(links) == 1
    assert links[0]["source"] == "betexplorer"
    assert links[0]["status"] == "available"


def test_database_stores_team_aliases(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    db.upsert_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        group_name="K",
        team_name="DR Congo",
        country="DR Congo",
    )
    db.upsert_tournament_team_alias(
        tournament="fifa_world_cup",
        season="2026",
        team_name="DR Congo",
        alias="Congo DR",
    )

    row = db.resolve_tournament_team(
        tournament="fifa_world_cup",
        season="2026",
        name="Congo DR",
    )

    assert row is not None
    assert row["team_name"] == "DR Congo"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_tournament_database.py -v
```

Expected: FAIL with missing `upsert_tournament_team`.

- [ ] **Step 3: Add tournament schema**

In `src/handicap_ai/database.py`, append these SQL statements to `SCHEMA` before the closing triple quote:

```sql
CREATE TABLE IF NOT EXISTS tournament_teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  group_name TEXT NOT NULL,
  team_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  country TEXT,
  UNIQUE(tournament, season, normalized_name)
);

CREATE INDEX IF NOT EXISTS idx_tournament_teams_group
ON tournament_teams(tournament, season, group_name, team_name);

CREATE TABLE IF NOT EXISTS tournament_team_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  team_name TEXT NOT NULL,
  normalized_team_name TEXT NOT NULL,
  alias TEXT NOT NULL,
  normalized_alias TEXT NOT NULL,
  UNIQUE(tournament, season, normalized_alias)
);

CREATE TABLE IF NOT EXISTS tournament_fixtures (
  fixture_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tournament TEXT NOT NULL,
  season TEXT NOT NULL,
  group_name TEXT NOT NULL,
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  home_normalized TEXT NOT NULL,
  away_normalized TEXT NOT NULL,
  kickoff_time TEXT,
  status TEXT NOT NULL,
  UNIQUE(tournament, season, home_normalized, away_normalized)
);

CREATE INDEX IF NOT EXISTS idx_tournament_fixtures_lookup
ON tournament_fixtures(tournament, season, home_normalized, away_normalized);

CREATE TABLE IF NOT EXISTS fixture_source_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fixture_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  html_path TEXT,
  url TEXT,
  status TEXT NOT NULL,
  UNIQUE(fixture_id, source),
  FOREIGN KEY(fixture_id) REFERENCES tournament_fixtures(fixture_id)
);
```

- [ ] **Step 4: Add database helper methods**

Add these methods to `Database` in `src/handicap_ai/database.py`:

```python
    def upsert_tournament_team(
        self,
        tournament: str,
        season: str,
        group_name: str,
        team_name: str,
        country: str | None,
    ) -> None:
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO tournament_teams (
                  tournament,
                  season,
                  group_name,
                  team_name,
                  normalized_name,
                  country
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tournament, season, normalized_name) DO UPDATE SET
                  group_name = excluded.group_name,
                  team_name = excluded.team_name,
                  country = excluded.country
                """,
                (
                    tournament,
                    season,
                    group_name,
                    team_name,
                    normalize_team_name(team_name),
                    country,
                ),
            )
            conn.commit()

    def list_tournament_teams(
        self,
        tournament: str,
        season: str,
    ) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT *
            FROM tournament_teams
            WHERE tournament = ? AND season = ?
            ORDER BY group_name ASC, team_name ASC
            """,
            (tournament, season),
        )

    def upsert_tournament_team_alias(
        self,
        tournament: str,
        season: str,
        team_name: str,
        alias: str,
    ) -> None:
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO tournament_team_aliases (
                  tournament,
                  season,
                  team_name,
                  normalized_team_name,
                  alias,
                  normalized_alias
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tournament, season, normalized_alias) DO UPDATE SET
                  team_name = excluded.team_name,
                  normalized_team_name = excluded.normalized_team_name,
                  alias = excluded.alias
                """,
                (
                    tournament,
                    season,
                    team_name,
                    normalize_team_name(team_name),
                    alias,
                    normalize_team_name(alias),
                ),
            )
            conn.commit()

    def resolve_tournament_team(
        self,
        tournament: str,
        season: str,
        name: str,
    ) -> sqlite3.Row | None:
        normalized = normalize_team_name(name)
        rows = self.execute(
            """
            SELECT *
            FROM tournament_teams
            WHERE tournament = ? AND season = ? AND normalized_name = ?
            """,
            (tournament, season, normalized),
        )
        if rows:
            return rows[0]
        alias_rows = self.execute(
            """
            SELECT tt.*
            FROM tournament_team_aliases aliases
            JOIN tournament_teams tt
              ON tt.tournament = aliases.tournament
             AND tt.season = aliases.season
             AND tt.normalized_name = aliases.normalized_team_name
            WHERE aliases.tournament = ?
              AND aliases.season = ?
              AND aliases.normalized_alias = ?
            """,
            (tournament, season, normalized),
        )
        return alias_rows[0] if alias_rows else None

    def upsert_tournament_fixture(
        self,
        tournament: str,
        season: str,
        group_name: str,
        home_team: str,
        away_team: str,
        kickoff_time: str | None,
        status: str,
    ) -> int:
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO tournament_fixtures (
                  tournament,
                  season,
                  group_name,
                  home_team,
                  away_team,
                  home_normalized,
                  away_normalized,
                  kickoff_time,
                  status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tournament, season, home_normalized, away_normalized)
                DO UPDATE SET
                  group_name = excluded.group_name,
                  home_team = excluded.home_team,
                  away_team = excluded.away_team,
                  kickoff_time = excluded.kickoff_time,
                  status = excluded.status
                """,
                (
                    tournament,
                    season,
                    group_name,
                    home_team,
                    away_team,
                    normalize_team_name(home_team),
                    normalize_team_name(away_team),
                    kickoff_time,
                    status,
                ),
            )
            row = conn.execute(
                """
                SELECT fixture_id
                FROM tournament_fixtures
                WHERE tournament = ?
                  AND season = ?
                  AND home_normalized = ?
                  AND away_normalized = ?
                """,
                (
                    tournament,
                    season,
                    normalize_team_name(home_team),
                    normalize_team_name(away_team),
                ),
            ).fetchone()
            conn.commit()
            return int(row["fixture_id"])

    def find_tournament_fixtures(
        self,
        tournament: str,
        season: str,
        home_team: str,
        away_team: str,
    ) -> list[sqlite3.Row]:
        home = normalize_team_name(home_team)
        away = normalize_team_name(away_team)
        return self.execute(
            """
            SELECT *
            FROM tournament_fixtures
            WHERE tournament = ?
              AND season = ?
              AND (
                (home_normalized = ? AND away_normalized = ?)
                OR (home_normalized = ? AND away_normalized = ?)
              )
            ORDER BY group_name ASC, fixture_id ASC
            """,
            (tournament, season, home, away, away, home),
        )

    def upsert_fixture_source_link(
        self,
        fixture_id: int,
        source: str,
        html_path: str | None,
        url: str | None,
        status: str,
    ) -> None:
        with closing(self.connect()) as conn:
            conn.execute(
                """
                INSERT INTO fixture_source_links (
                  fixture_id,
                  source,
                  html_path,
                  url,
                  status
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(fixture_id, source) DO UPDATE SET
                  html_path = excluded.html_path,
                  url = excluded.url,
                  status = excluded.status
                """,
                (fixture_id, source, html_path, url, status),
            )
            conn.commit()

    def list_fixture_source_links(self, fixture_id: int) -> list[sqlite3.Row]:
        return self.execute(
            """
            SELECT *
            FROM fixture_source_links
            WHERE fixture_id = ?
            ORDER BY source ASC
            """,
            (fixture_id,),
        )
```

- [ ] **Step 5: Run tournament database tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_tournament_database.py -v
```

Expected: PASS.

- [ ] **Step 6: Run existing database tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_database.py tests/test_scrape_database.py tests/test_tournament_database.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/handicap_ai/database.py tests/test_tournament_database.py
git commit -m "feat: add tournament seed tables"
```

## Task 2: Add 2026 World Cup Seed Import

**Files:**
- Create: `src/handicap_ai/world_cup_seed.py`
- Create: `tests/test_world_cup_seed.py`

- [ ] **Step 1: Write failing seed tests**

Create `tests/test_world_cup_seed.py`:

```python
from handicap_ai.database import Database
from handicap_ai.world_cup_seed import (
    FIFA_WORLD_CUP,
    import_world_cup_2026_seed,
)


def test_world_cup_seed_imports_48_teams(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_world_cup_2026_seed(db)

    assert summary.teams_imported == 48
    assert len(db.list_tournament_teams(FIFA_WORLD_CUP, "2026")) == 48


def test_world_cup_seed_imports_group_k_and_l_teams(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    import_world_cup_2026_seed(db)
    rows = db.list_tournament_teams(FIFA_WORLD_CUP, "2026")
    group_k = {row["team_name"] for row in rows if row["group_name"] == "K"}
    group_l = {row["team_name"] for row in rows if row["group_name"] == "L"}

    assert group_k == {"Colombia", "Portugal", "DR Congo", "Uzbekistan"}
    assert group_l == {"England", "Croatia", "Ghana", "Panama"}


def test_world_cup_seed_import_is_idempotent(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    import_world_cup_2026_seed(db)
    import_world_cup_2026_seed(db)

    assert len(db.list_tournament_teams(FIFA_WORLD_CUP, "2026")) == 48


def test_world_cup_seed_imports_group_stage_fixtures(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    summary = import_world_cup_2026_seed(db)

    assert summary.fixtures_imported == 72
    england_ghana = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        "2026",
        "England",
        "Ghana",
    )
    portugal_uzbekistan = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        "2026",
        "Portugal",
        "Uzbekistan",
    )
    assert len(england_ghana) == 1
    assert england_ghana[0]["group_name"] == "L"
    assert len(portugal_uzbekistan) == 1
    assert portugal_uzbekistan[0]["group_name"] == "K"


def test_world_cup_seed_imports_aliases(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    import_world_cup_2026_seed(db)

    assert db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "Congo DR")["team_name"] == "DR Congo"
    assert db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "USA")["team_name"] == "United States"
    assert db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "Korea Republic")["team_name"] == "South Korea"
    assert db.resolve_tournament_team(FIFA_WORLD_CUP, "2026", "Czechia")["team_name"] == "Czech Republic"
```

- [ ] **Step 2: Run seed tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_world_cup_seed.py -v
```

Expected: FAIL with missing `handicap_ai.world_cup_seed`.

- [ ] **Step 3: Implement world cup seed module**

Create `src/handicap_ai/world_cup_seed.py`:

```python
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from handicap_ai.database import Database


FIFA_WORLD_CUP = "fifa_world_cup"
SEASON_2026 = "2026"


@dataclass(frozen=True)
class SeedTeam:
    group_name: str
    team_name: str
    country: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeedFixture:
    group_name: str
    home_team: str
    away_team: str
    kickoff_time: str | None = None
    status: str = "scheduled"


@dataclass(frozen=True)
class WorldCupSeedSummary:
    teams_imported: int
    fixtures_imported: int
    aliases_imported: int


WORLD_CUP_2026_GROUPS: tuple[SeedTeam, ...] = (
    SeedTeam("A", "Mexico", "Mexico"),
    SeedTeam("A", "South Africa", "South Africa"),
    SeedTeam("A", "South Korea", "South Korea", ("Korea Republic", "Korea Rep")),
    SeedTeam("A", "Czech Republic", "Czech Republic", ("Czechia",)),
    SeedTeam("B", "Canada", "Canada"),
    SeedTeam("B", "Bosnia and Herzegovina", "Bosnia and Herzegovina"),
    SeedTeam("B", "Qatar", "Qatar"),
    SeedTeam("B", "Switzerland", "Switzerland"),
    SeedTeam("C", "Brazil", "Brazil"),
    SeedTeam("C", "Morocco", "Morocco"),
    SeedTeam("C", "Haiti", "Haiti"),
    SeedTeam("C", "Scotland", "Scotland"),
    SeedTeam("D", "United States", "United States", ("USA", "USMNT")),
    SeedTeam("D", "Paraguay", "Paraguay"),
    SeedTeam("D", "Australia", "Australia"),
    SeedTeam("D", "Turkey", "Turkey"),
    SeedTeam("E", "Germany", "Germany"),
    SeedTeam("E", "Curacao", "Curacao"),
    SeedTeam("E", "Ivory Coast", "Ivory Coast", ("Cote d'Ivoire", "Cote d Ivoire")),
    SeedTeam("E", "Ecuador", "Ecuador"),
    SeedTeam("F", "Netherlands", "Netherlands"),
    SeedTeam("F", "Japan", "Japan"),
    SeedTeam("F", "Sweden", "Sweden"),
    SeedTeam("F", "Tunisia", "Tunisia"),
    SeedTeam("G", "Belgium", "Belgium"),
    SeedTeam("G", "Egypt", "Egypt"),
    SeedTeam("G", "Iran", "Iran"),
    SeedTeam("G", "New Zealand", "New Zealand"),
    SeedTeam("H", "Spain", "Spain"),
    SeedTeam("H", "Cape Verde", "Cape Verde"),
    SeedTeam("H", "Saudi Arabia", "Saudi Arabia"),
    SeedTeam("H", "Uruguay", "Uruguay"),
    SeedTeam("I", "France", "France"),
    SeedTeam("I", "Senegal", "Senegal"),
    SeedTeam("I", "Iraq", "Iraq"),
    SeedTeam("I", "Norway", "Norway"),
    SeedTeam("J", "Argentina", "Argentina"),
    SeedTeam("J", "Algeria", "Algeria"),
    SeedTeam("J", "Austria", "Austria"),
    SeedTeam("J", "Jordan", "Jordan"),
    SeedTeam("K", "Colombia", "Colombia"),
    SeedTeam("K", "Portugal", "Portugal"),
    SeedTeam("K", "DR Congo", "DR Congo", ("Congo DR", "Democratic Republic of the Congo")),
    SeedTeam("K", "Uzbekistan", "Uzbekistan"),
    SeedTeam("L", "England", "England"),
    SeedTeam("L", "Croatia", "Croatia"),
    SeedTeam("L", "Ghana", "Ghana"),
    SeedTeam("L", "Panama", "Panama"),
)


def world_cup_2026_fixtures() -> tuple[SeedFixture, ...]:
    fixtures: list[SeedFixture] = []
    groups: dict[str, list[str]] = {}
    for team in WORLD_CUP_2026_GROUPS:
        groups.setdefault(team.group_name, []).append(team.team_name)
    for group_name, teams in groups.items():
        for home_index, home_team in enumerate(teams):
            for away_team in teams[home_index + 1 :]:
                fixtures.append(SeedFixture(group_name, home_team, away_team))
    return tuple(fixtures)


def import_world_cup_2026_seed(db: Database) -> WorldCupSeedSummary:
    for team in WORLD_CUP_2026_GROUPS:
        db.upsert_tournament_team(
            tournament=FIFA_WORLD_CUP,
            season=SEASON_2026,
            group_name=team.group_name,
            team_name=team.team_name,
            country=team.country,
        )
        for alias in team.aliases:
            db.upsert_tournament_team_alias(
                tournament=FIFA_WORLD_CUP,
                season=SEASON_2026,
                team_name=team.team_name,
                alias=alias,
            )

    fixtures = world_cup_2026_fixtures()
    for fixture in fixtures:
        db.upsert_tournament_fixture(
            tournament=FIFA_WORLD_CUP,
            season=SEASON_2026,
            group_name=fixture.group_name,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            kickoff_time=fixture.kickoff_time,
            status=fixture.status,
        )

    return WorldCupSeedSummary(
        teams_imported=len(WORLD_CUP_2026_GROUPS),
        fixtures_imported=len(fixtures),
        aliases_imported=sum(len(team.aliases) for team in WORLD_CUP_2026_GROUPS),
    )
```

- [ ] **Step 4: Run seed tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_world_cup_seed.py -v
```

Expected: PASS.

- [ ] **Step 5: Run relevant tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_tournament_database.py tests/test_world_cup_seed.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/world_cup_seed.py tests/test_world_cup_seed.py
git commit -m "feat: seed 2026 world cup teams"
```

## Task 3: Add Candidate Search Service

**Files:**
- Create: `src/handicap_ai/candidate_search.py`
- Create: `tests/test_candidate_search.py`

- [ ] **Step 1: Write failing candidate search tests**

Create `tests/test_candidate_search.py`:

```python
from handicap_ai.candidate_search import CandidateStatus, find_world_cup_candidates
from handicap_ai.database import Database
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


def seeded_db(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    import_world_cup_2026_seed(db)
    return db


def test_candidate_search_finds_group_l_fixture(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="England", away_team="Ghana")

    assert result.status is CandidateStatus.NEEDS_HTML
    assert result.candidates[0].home_team == "England"
    assert result.candidates[0].away_team == "Ghana"
    assert result.candidates[0].group_name == "L"


def test_candidate_search_resolves_aliases(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="Portugal", away_team="Congo DR")

    assert result.status is CandidateStatus.NEEDS_HTML
    assert result.candidates[0].home_team == "Portugal"
    assert result.candidates[0].away_team == "DR Congo"
    assert result.candidates[0].group_name == "K"


def test_candidate_search_reports_invalid_team(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="Atlantis", away_team="Ghana")

    assert result.status is CandidateStatus.INVALID_TEAM
    assert result.candidates == ()
    assert "Unknown team: Atlantis" in result.warnings


def test_candidate_search_reports_not_in_group_stage(tmp_path):
    db = seeded_db(tmp_path)

    result = find_world_cup_candidates(db, home_team="England", away_team="Portugal")

    assert result.status is CandidateStatus.NOT_IN_GROUP_STAGE
    assert result.candidates == ()
    assert "Both teams are seeded, but no group-stage fixture was found" in result.warnings


def test_candidate_search_marks_ready_when_source_link_exists(tmp_path):
    db = seeded_db(tmp_path)
    fixture = db.find_tournament_fixtures(
        "fifa_world_cup",
        "2026",
        "England",
        "Panama",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url=None,
        status="available",
    )

    result = find_world_cup_candidates(db, home_team="England", away_team="Panama")

    assert result.status is CandidateStatus.READY
    assert result.candidates[0].sources["betexplorer"].html_path == "tests/fixtures/betexplorer_match.html"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_candidate_search.py -v
```

Expected: FAIL with missing `handicap_ai.candidate_search`.

- [ ] **Step 3: Implement candidate service**

Create `src/handicap_ai/candidate_search.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from handicap_ai.database import Database
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, SEASON_2026


class CandidateStatus(str, Enum):
    READY = "ready"
    NEEDS_HTML = "needs_html"
    INVALID_TEAM = "invalid_team"
    NOT_IN_GROUP_STAGE = "not_in_group_stage"


@dataclass(frozen=True)
class SourceLinkCandidate:
    source: str
    status: str
    html_path: str | None
    url: str | None


@dataclass(frozen=True)
class FixtureCandidate:
    fixture_id: int
    group_name: str
    home_team: str
    away_team: str
    kickoff_time: str | None
    status: str
    sources: dict[str, SourceLinkCandidate]


@dataclass(frozen=True)
class CandidateSearchResult:
    status: CandidateStatus
    candidates: tuple[FixtureCandidate, ...]
    warnings: tuple[str, ...]


def find_world_cup_candidates(
    db: Database,
    home_team: str,
    away_team: str,
    season: str = SEASON_2026,
) -> CandidateSearchResult:
    home = db.resolve_tournament_team(FIFA_WORLD_CUP, season, home_team)
    away = db.resolve_tournament_team(FIFA_WORLD_CUP, season, away_team)
    warnings: list[str] = []
    if home is None:
        warnings.append(f"Unknown team: {home_team}")
    if away is None:
        warnings.append(f"Unknown team: {away_team}")
    if warnings:
        return CandidateSearchResult(CandidateStatus.INVALID_TEAM, (), tuple(warnings))

    fixtures = db.find_tournament_fixtures(
        tournament=FIFA_WORLD_CUP,
        season=season,
        home_team=home["team_name"],
        away_team=away["team_name"],
    )
    if not fixtures:
        return CandidateSearchResult(
            CandidateStatus.NOT_IN_GROUP_STAGE,
            (),
            ("Both teams are seeded, but no group-stage fixture was found",),
        )

    candidates = tuple(_fixture_candidate(db, row) for row in fixtures)
    if any(
        link.status == "available" and link.html_path
        for candidate in candidates
        for link in candidate.sources.values()
    ):
        status = CandidateStatus.READY
    else:
        status = CandidateStatus.NEEDS_HTML
    return CandidateSearchResult(status, candidates, ())


def _fixture_candidate(db: Database, row) -> FixtureCandidate:
    links = {
        link["source"]: SourceLinkCandidate(
            source=link["source"],
            status=link["status"],
            html_path=link["html_path"],
            url=link["url"],
        )
        for link in db.list_fixture_source_links(int(row["fixture_id"]))
    }
    return FixtureCandidate(
        fixture_id=int(row["fixture_id"]),
        group_name=row["group_name"],
        home_team=row["home_team"],
        away_team=row["away_team"],
        kickoff_time=row["kickoff_time"],
        status=row["status"],
        sources=links,
    )
```

- [ ] **Step 4: Run candidate tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_candidate_search.py -v
```

Expected: PASS.

- [ ] **Step 5: Run seed and candidate tests together**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_world_cup_seed.py tests/test_candidate_search.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/handicap_ai/candidate_search.py tests/test_candidate_search.py
git commit -m "feat: find world cup fixture candidates"
```

## Task 4: Add World Cup CLI Commands

**Files:**
- Modify: `src/handicap_ai/cli.py`
- Create: `tests/test_world_cup_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_world_cup_cli.py`:

```python
from typer.testing import CliRunner

from handicap_ai.cli import app


def test_seed_world_cup_command_imports_seed(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    result = CliRunner().invoke(
        app,
        [
            "seed-world-cup",
            "--db",
            str(db_path),
            "--season",
            "2026",
        ],
    )

    assert result.exit_code == 0
    assert "World Cup teams: 48" in result.output
    assert "World Cup fixtures: 72" in result.output


def test_find_candidates_command_prints_fixture(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])

    result = runner.invoke(
        app,
        [
            "find-candidates",
            "--db",
            str(db_path),
            "--home",
            "England",
            "--away",
            "Ghana",
        ],
    )

    assert result.exit_code == 0
    assert "Status: needs_html" in result.output
    assert "Group L: England vs Ghana" in result.output


def test_find_candidates_command_prints_invalid_team(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    runner = CliRunner()
    runner.invoke(app, ["seed-world-cup", "--db", str(db_path), "--season", "2026"])

    result = runner.invoke(
        app,
        [
            "find-candidates",
            "--db",
            str(db_path),
            "--home",
            "Atlantis",
            "--away",
            "Ghana",
        ],
    )

    assert result.exit_code == 0
    assert "Status: invalid_team" in result.output
    assert "Unknown team: Atlantis" in result.output
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_world_cup_cli.py -v
```

Expected: FAIL because commands do not exist.

- [ ] **Step 3: Add imports**

Modify imports in `src/handicap_ai/cli.py`:

```python
from handicap_ai.candidate_search import find_world_cup_candidates
from handicap_ai.world_cup_seed import import_world_cup_2026_seed
```

- [ ] **Step 4: Add commands**

Add these commands before helper functions in `src/handicap_ai/cli.py`:

```python
@app.command("seed-world-cup")
def seed_world_cup(
    season: str = typer.Option("2026", "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    if season != "2026":
        raise typer.BadParameter("only 2026 is supported in this seed")
    database = Database(db)
    database.migrate()
    summary = import_world_cup_2026_seed(database)
    console.print(f"World Cup teams: {summary.teams_imported}")
    console.print(f"World Cup fixtures: {summary.fixtures_imported}")
    console.print(f"World Cup aliases: {summary.aliases_imported}")


@app.command("find-candidates")
def find_candidates(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    result = find_world_cup_candidates(database, home_team=home, away_team=away)
    console.print(f"Status: {result.status.value}")
    for warning in result.warnings:
        console.print(f"Warning: {warning}")
    for candidate in result.candidates:
        console.print(
            f"Group {candidate.group_name}: {candidate.home_team} vs {candidate.away_team}"
        )
        if candidate.sources:
            for source, link in candidate.sources.items():
                console.print(f"- {source}: {link.status} {link.html_path or ''}".rstrip())
        else:
            console.print("- saved HTML required")
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_world_cup_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Run broader CLI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_cli.py tests/test_scrape_cli.py tests/test_ui_cli.py tests/test_world_cup_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/handicap_ai/cli.py tests/test_world_cup_cli.py
git commit -m "feat: add world cup cli commands"
```

## Task 5: Add Candidate API Endpoints

**Files:**
- Modify: `src/handicap_ai/ui.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Write failing UI API tests**

Append to `tests/test_ui.py`:

```python
def test_candidate_endpoint_returns_group_fixture(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/world-cup-candidates",
        json={"home_team": "England", "away_team": "Ghana"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_html"
    assert body["candidates"][0]["group_name"] == "L"
    assert body["candidates"][0]["home_team"] == "England"
    assert body["candidates"][0]["away_team"] == "Ghana"


def test_candidate_endpoint_reports_unknown_team(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/world-cup-candidates",
        json={"home_team": "Atlantis", "away_team": "Ghana"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid_team"
    assert body["candidates"] == []
    assert "Unknown team: Atlantis" in body["warnings"]


def test_candidate_analysis_endpoint_accepts_saved_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/analyze-candidate",
        json={
            "source": "betexplorer",
            "html_path": "tests/fixtures/betexplorer_match.html",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["match"] == "England vs Panama"
    assert body["coverage"] == "complete"
```

- [ ] **Step 2: Run UI tests to verify they fail**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py -v
```

Expected: FAIL with 404 for `/api/world-cup-candidates` and `/api/analyze-candidate`.

- [ ] **Step 3: Add imports and request models**

Modify `src/handicap_ai/ui.py` imports:

```python
from handicap_ai.candidate_search import find_world_cup_candidates
from handicap_ai.world_cup_seed import import_world_cup_2026_seed
```

Add request models next to `SavedHtmlAnalysisRequest`:

```python
class CandidateSearchRequest(BaseModel):
    home_team: str
    away_team: str


class CandidateAnalysisRequest(BaseModel):
    source: str
    html_path: str
```

- [ ] **Step 4: Add response helpers**

Add helper functions below request models in `src/handicap_ai/ui.py`:

```python
def _report_payload(result):
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


def _candidate_payload(candidate):
    return {
        "fixture_id": candidate.fixture_id,
        "group_name": candidate.group_name,
        "home_team": candidate.home_team,
        "away_team": candidate.away_team,
        "kickoff_time": candidate.kickoff_time,
        "status": candidate.status,
        "sources": {
            source: {
                "source": link.source,
                "status": link.status,
                "html_path": link.html_path,
                "url": link.url,
            }
            for source, link in candidate.sources.items()
        },
    }
```

- [ ] **Step 5: Seed database in `create_app`**

Inside `create_app`, after `database.migrate()`, add:

```python
    import_world_cup_2026_seed(database)
```

- [ ] **Step 6: Refactor existing saved HTML endpoint to use helper**

Replace the current return body in `analyze_saved_html_endpoint` with:

```python
        return _report_payload(result)
```

- [ ] **Step 7: Add candidate endpoints**

Inside `create_app`, add:

```python
    @app.post("/api/world-cup-candidates")
    def world_cup_candidates_endpoint(payload: CandidateSearchRequest):
        result = find_world_cup_candidates(
            database,
            home_team=payload.home_team,
            away_team=payload.away_team,
        )
        return {
            "status": result.status.value,
            "warnings": list(result.warnings),
            "candidates": [_candidate_payload(candidate) for candidate in result.candidates],
        }

    @app.post("/api/analyze-candidate")
    def analyze_candidate_endpoint(payload: CandidateAnalysisRequest):
        result = analyze_saved_html(
            db=database,
            source=payload.source,
            html_path=Path(payload.html_path),
        )
        return _report_payload(result)
```

- [ ] **Step 8: Run UI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py -v
```

Expected: PASS.

- [ ] **Step 9: Run service and UI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_candidate_search.py tests/test_ui.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/handicap_ai/ui.py tests/test_ui.py
git commit -m "feat: add world cup candidate api"
```

## Task 6: Update Dashboard Candidate Wizard UI

**Files:**
- Modify: `src/handicap_ai/templates/dashboard.html`
- Modify: `src/handicap_ai/static/dashboard.css`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Write failing dashboard render test**

Modify `test_dashboard_route_renders_workspace` in `tests/test_ui.py` so it asserts the new controls:

```python
def test_dashboard_route_renders_workspace(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Handicap AI Analyst Workspace" in response.text
    assert "Home team" in response.text
    assert "Away team" in response.text
    assert "Find candidates" in response.text
    assert "Candidate confirmation" in response.text
    assert "BetExplorer" in response.text
    assert "OddsPortal" in response.text
```

- [ ] **Step 2: Run UI test to verify it fails**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py::test_dashboard_route_renders_workspace -v
```

Expected: FAIL because `Find candidates` and `Candidate confirmation` are not rendered.

- [ ] **Step 3: Update dashboard HTML form**

In `src/handicap_ai/templates/dashboard.html`:

1. Make `#home-team` and `#away-team` editable with default values `England` and `Ghana`.
2. Add a secondary button:

```html
<button id="find-candidates-button" type="button">Find candidates</button>
```

3. Add a candidate panel in the main dashboard area:

```html
<article class="panel candidate-panel">
  <div class="panel-heading">
    <span class="label">Candidate confirmation</span>
    <strong id="candidate-status">Not checked</strong>
  </div>
  <div id="candidate-list" class="candidate-list">
    <p>Enter teams and find candidates.</p>
  </div>
</article>
```

4. Keep the saved HTML path input and the existing `Analyze saved HTML` button.

- [ ] **Step 4: Replace dashboard JavaScript with candidate flow**

Update the script in `dashboard.html` so it includes these functions and listeners:

```html
<script>
  const form = document.querySelector("#analysis-form");
  const message = document.querySelector("#form-message");
  const findCandidatesButton = document.querySelector("#find-candidates-button");

  function setText(id, value) {
    document.querySelector(id).textContent = value;
  }

  function splitMatch(match) {
    const parts = match.split(" vs ");
    return {
      home: parts[0] || "",
      away: parts[1] || "",
    };
  }

  function renderCandidates(body) {
    setText("#candidate-status", body.status);
    const list = document.querySelector("#candidate-list");
    list.replaceChildren();
    if (body.warnings.length) {
      for (const warning of body.warnings) {
        const item = document.createElement("p");
        item.textContent = warning;
        list.appendChild(item);
      }
    }
    if (!body.candidates.length) {
      if (!body.warnings.length) {
        const item = document.createElement("p");
        item.textContent = "No candidates found.";
        list.appendChild(item);
      }
      return;
    }
    for (const candidate of body.candidates) {
      const article = document.createElement("article");
      article.className = "candidate-card";
      const sourceNames = Object.keys(candidate.sources);
      const title = document.createElement("strong");
      title.textContent = `Group ${candidate.group_name}: ${candidate.home_team} vs ${candidate.away_team}`;
      const detail = document.createElement("span");
      detail.textContent = sourceNames.length ? sourceNames.join(", ") : "Saved HTML required";
      article.append(title, detail);
      list.appendChild(article);
    }
  }

  async function findCandidates() {
    message.textContent = "Finding candidates";
    const homeTeam = document.querySelector("#home-team").value;
    const awayTeam = document.querySelector("#away-team").value;
    const response = await fetch("/api/world-cup-candidates", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({home_team: homeTeam, away_team: awayTeam})
    });
    const body = await response.json();
    renderCandidates(body);
    message.textContent = "Candidates ready";
  }

  findCandidatesButton.addEventListener("click", async () => {
    try {
      await findCandidates();
    } catch (error) {
      message.textContent = error.message;
      setText("#candidate-status", "Error");
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    message.textContent = "Analyzing";
    setText("#source-status", data.get("source"));

    try {
      const response = await fetch("/api/analyze-candidate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          source: data.get("source"),
          html_path: data.get("html_path"),
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const body = await response.json();
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
      message.textContent = "Analysis ready";
    } catch (error) {
      message.textContent = error.message;
      setText("#source-status", "Error");
    }
  });
</script>
```

- [ ] **Step 5: Add CSS for candidate controls**

Append to `src/handicap_ai/static/dashboard.css`:

```css
.candidate-list {
  display: grid;
  gap: 10px;
}

.candidate-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 6px;
  padding: 12px;
}

.candidate-card span {
  color: var(--muted);
}

#find-candidates-button {
  background: #334155;
}

#find-candidates-button:hover,
#find-candidates-button:focus-visible {
  background: #1f2937;
}
```

- [ ] **Step 6: Run UI render test**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py::test_dashboard_route_renders_workspace -v
```

Expected: PASS.

- [ ] **Step 7: Run UI tests**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_ui.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/handicap_ai/templates/dashboard.html src/handicap_ai/static/dashboard.css tests/test_ui.py
git commit -m "feat: add candidate wizard dashboard"
```

## Task 7: Documentation and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add this section after "Import Historical Data":

````markdown
## Seed World Cup Candidates

```bash
handicap-ai seed-world-cup --db data/handicap_ai.sqlite --season 2026
handicap-ai find-candidates --db data/handicap_ai.sqlite --home England --away Ghana
```

The World Cup candidate workflow lets you enter home and away team names,
confirm a seeded group-stage fixture, then analyze a saved odds HTML file.
````

Update the "Run Local UI" section to say:

```markdown
Open `http://127.0.0.1:8000`, enter home and away team names, click
`Find candidates`, then analyze a saved HTML file for the confirmed fixture.
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run CLI smoke**

Run:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli seed-world-cup --db data/world-cup-smoke.sqlite --season 2026
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli find-candidates --db data/world-cup-smoke.sqlite --home England --away Ghana
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli scrape-match --db data/world-cup-smoke.sqlite --source betexplorer --html tests/fixtures/betexplorer_match.html
```

Expected output includes:

```text
World Cup teams: 48
World Cup fixtures: 72
Status: needs_html
Group L: England vs Ghana
Scraped England vs Panama from betexplorer
Handicap pick:
Total pick:
1X2 pick:
```

- [ ] **Step 4: Run UI smoke**

Start:

```bash
C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m handicap_ai.cli ui --db data/world-cup-smoke.sqlite --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001`.

Expected:

- dashboard loads
- `Home team` and `Away team` are editable
- `Find candidates` shows Group L for England vs Ghana
- saved HTML analysis still returns all three picks

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document world cup candidate workflow"
```

## Final Verification

- [ ] `git status --short --ignored` shows no untracked source files except ignored caches/data.
- [ ] `C:\Users\30613\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q` passes.
- [ ] CLI smoke prints seed, candidate, and saved HTML analysis output.
- [ ] Browser smoke confirms the candidate wizard works.
- [ ] No live-source scraping limitations are hidden; final response states that this phase remains saved-HTML backed.
