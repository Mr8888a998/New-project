from __future__ import annotations

from pathlib import Path

from rich.console import Console
import typer

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.features import build_match_features
from handicap_ai.ingest import ingest_bundles
from handicap_ai.labels import label_to_recommendation_bucket
from handicap_ai.recommendation import RecommendationEngine
from handicap_ai.report import render_text_report
from handicap_ai.resolver import MatchResolver
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total
from handicap_ai.similarity import SimilarityCandidate, SimilarityResult, find_similar_matches

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
    similar = _similar_matches(database, match_id, features)
    report = RecommendationEngine().recommend(features, similar=similar)
    console.print(render_text_report(match["home_team"], match["away_team"], report))


def _similar_matches(database: Database, match_id: int, features):
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


if __name__ == "__main__":
    app()
