from __future__ import annotations

from pathlib import Path

from rich.console import Console
import typer

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.features import build_match_features
from handicap_ai.ingest import ingest_bundles
from handicap_ai.recommendation import RecommendationEngine
from handicap_ai.report import render_text_report
from handicap_ai.resolver import MatchResolver

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """Local football handicap analysis tool."""


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
