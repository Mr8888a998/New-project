from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.history_import import import_history_folder
from handicap_ai.ingest import ingest_bundles
from handicap_ai.source_status import summarize_world_cup_sources
from handicap_ai.world_cup_seed import (
    FIFA_WORLD_CUP,
    SEASON_2026,
    import_world_cup_2026_seed,
)


DEFAULT_FOOTBALL_DATA_CSV = Path("tests/fixtures/football_data_sample.csv")
DEFAULT_HISTORY_FOLDER = Path("tests/fixtures/history_folder")
DEFAULT_CACHED_HTML_CANDIDATES = (
    Path(
        "data/cache/auto-analyze-main/betexplorer/"
        "fixture-69-ce4a10cac34e081eeb0db4d10c8a672d17f70151be05efaf67675a87005cb6a8.html"
    ),
    Path("tests/fixtures/betexplorer_match.html"),
)


@dataclass(frozen=True)
class DemoDataSummary:
    source: str
    world_cup_teams: int
    world_cup_fixtures: int
    finished_matches: int
    football_data_matches: int
    history_files: int
    history_matches: int
    source_registered: bool
    available_html: int
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "world_cup_teams": self.world_cup_teams,
            "world_cup_fixtures": self.world_cup_fixtures,
            "finished_matches": self.finished_matches,
            "football_data_matches": self.football_data_matches,
            "history_files": self.history_files,
            "history_matches": self.history_matches,
            "source_registered": self.source_registered,
            "available_html": self.available_html,
            "warnings": list(self.warnings),
        }


def prepare_demo_data(
    db: Database,
    *,
    source: str = "betexplorer",
    football_data_csv: Path = DEFAULT_FOOTBALL_DATA_CSV,
    history_folder: Path = DEFAULT_HISTORY_FOLDER,
    cached_html_path: Path | None = None,
) -> DemoDataSummary:
    db.migrate()
    import_world_cup_2026_seed(db, overwrite_existing=False)
    warnings: list[str] = []
    football_data_matches = 0
    history_files = 0
    history_matches = 0

    if football_data_csv.is_file():
        bundles = FootballDataCsvAdapter(football_data_csv, season=SEASON_2026).load()
        football_data_matches = ingest_bundles(db, bundles)
    else:
        warnings.append(f"football data CSV missing: {football_data_csv}")

    if history_folder.is_dir():
        history_summary = import_history_folder(db, history_folder, season=SEASON_2026)
        history_files = history_summary.files_imported
        history_matches = history_summary.matches_imported
        warnings.extend(history_summary.errors)
    else:
        warnings.append(f"history folder missing: {history_folder}")

    html_path = cached_html_path or _default_cached_html_path()
    source_registered = False
    if html_path is not None and html_path.is_file():
        source_registered = _register_demo_html(db, source=source, html_path=html_path)
    else:
        warnings.append(f"cached HTML missing: {html_path or 'no default found'}")

    source_summary = summarize_world_cup_sources(db, source=source)
    return DemoDataSummary(
        source=source_summary.source,
        world_cup_teams=_count_world_cup_teams(db),
        world_cup_fixtures=_count_world_cup_fixtures(db),
        finished_matches=len(db.all_finished_matches()),
        football_data_matches=football_data_matches,
        history_files=history_files,
        history_matches=history_matches,
        source_registered=source_registered,
        available_html=source_summary.available_html,
        warnings=tuple(warnings),
    )


def _default_cached_html_path() -> Path | None:
    return next(
        (path for path in DEFAULT_CACHED_HTML_CANDIDATES if path.is_file()),
        None,
    )


def _count_world_cup_teams(db: Database) -> int:
    rows = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM tournament_teams
        WHERE tournament = ? AND season = ?
        """,
        (FIFA_WORLD_CUP, SEASON_2026),
    )
    return int(rows[0]["count"])


def _count_world_cup_fixtures(db: Database) -> int:
    rows = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM tournament_fixtures
        WHERE tournament = ? AND season = ?
        """,
        (FIFA_WORLD_CUP, SEASON_2026),
    )
    return int(rows[0]["count"])


def _register_demo_html(db: Database, *, source: str, html_path: Path) -> bool:
    fixture_rows = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        SEASON_2026,
        "England",
        "Panama",
    )
    if not fixture_rows:
        return False
    fixture = fixture_rows[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source=source,
        html_path=str(html_path),
        url="https://www.betexplorer.com/england-panama",
        status="available",
    )
    return True
