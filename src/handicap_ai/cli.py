from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from rich.console import Console
import typer
import uvicorn

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.backtest import run_backtest
from handicap_ai.cache_scan import scan_cache_html
from handicap_ai.candidate_search import find_world_cup_candidates
from handicap_ai.database import Database
from handicap_ai.features import build_match_features
from handicap_ai.history_import import import_history_folder
from handicap_ai.ingest import ingest_bundles
from handicap_ai.labels import label_to_recommendation_bucket
from handicap_ai.live_analysis import analyze_saved_html
from handicap_ai.manual_html import save_manual_fixture_html
from handicap_ai.demo_data import prepare_demo_data
from handicap_ai.recommendation import RecommendationEngine
from handicap_ai.report import render_text_report
from handicap_ai.resolver import MatchResolver
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total
from handicap_ai.similarity import SimilarityCandidate, SimilarityResult, find_similar_matches
from handicap_ai.source_checks import build_source_checks
from handicap_ai.source_matrix import build_source_matrix
from handicap_ai.source_status import summarize_world_cup_sources
from handicap_ai.source_discovery import (
    SourceLinkResult,
    discover_fixture_source,
    discover_fixture_source_from_listing,
    register_fixture_source_url,
)
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
from handicap_ai.ui import create_app
from handicap_ai.world_cup_seed import import_world_cup_2026_seed

app = typer.Typer(no_args_is_help=True)
console = Console()
T = TypeVar("T")


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
                details = [f"- {source}: {link.status}"]
                if link.html_path:
                    details.append(f"html={link.html_path}")
                if link.url:
                    details.append(f"url={link.url}")
                console.print(" ".join(details))
        else:
            console.print("- saved HTML required")


@app.command("register-source-url")
def register_source_url(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    url: str = typer.Option(..., "--url"),
    season: str = typer.Option("2026", "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    result = _run_source_action(
        lambda: register_fixture_source_url(
            database,
            home,
            away,
            source,
            url,
            season=season,
        )
    )
    _print_source_result(result)


@app.command("discover-sources")
def discover_sources(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    listing_html: Path | None = typer.Option(None, "--listing-html"),
    base_url: str | None = typer.Option(None, "--base-url"),
    season: str = typer.Option("2026", "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    if listing_html is None:
        result = _run_source_action(
            lambda: discover_fixture_source(
                database,
                home,
                away,
                source,
                season=season,
            )
        )
    else:
        if base_url is None:
            raise typer.BadParameter(
                "--base-url is required with --listing-html",
                param_hint="--base-url",
            )
        listing_text = _read_text_option(listing_html, "listing HTML")
        result = _run_source_action(
            lambda: discover_fixture_source_from_listing(
                database,
                home,
                away,
                source,
                listing_text,
                base_url,
                season=season,
            )
        )
    _print_source_result(result)


@app.command("fetch-source-html")
def fetch_source_html(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    cache_dir: Path = typer.Option(Path("data/cache"), "--cache-dir"),
    response_html: Path | None = typer.Option(None, "--response-html"),
    season: str = typer.Option("2026", "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    if response_html is None:
        result = _run_source_action(
            lambda: fetch_fixture_source_html(
                database,
                home,
                away,
                source,
                cache_dir,
                season=season,
            )
        )
    else:
        html = _read_text_option(response_html, "response HTML")

        def http_get(url: str) -> FetchHttpResponse:
            return FetchHttpResponse(url=url, status_code=200, text=html)

        result = _run_source_action(
            lambda: fetch_fixture_source_html(
                database,
                home,
                away,
                source,
                cache_dir,
                http_get=http_get,
                season=season,
            )
        )
    _print_source_result(result)


@app.command("save-manual-html")
def save_manual_html(
    home: str = typer.Option(..., "--home"),
    away: str = typer.Option(..., "--away"),
    source: str = typer.Option(..., "--source"),
    html: Path = typer.Option(..., "--html"),
    cache_dir: Path = typer.Option(Path("data/cache"), "--cache-dir"),
    season: str = typer.Option("2026", "--season"),
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
) -> None:
    database = Database(db)
    database.migrate()
    import_world_cup_2026_seed(database, overwrite_existing=False)
    html_text = _read_text_option(html, "manual HTML")
    result = _run_source_action(
        lambda: save_manual_fixture_html(
            database,
            home_team=home,
            away_team=away,
            source=source,
            html=html_text,
            cache_dir=cache_dir,
            season=season,
        )
    )
    details = [f"Manual HTML: status={result.status.value}"]
    if result.html_path:
        details.append(f"html={result.html_path}")
    console.print(" ".join(details), soft_wrap=True)
    for warning in result.warnings:
        console.print(f"Warning: {warning}")


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


@app.command("backtest")
def backtest(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    limit: int | None = typer.Option(None, "--limit"),
    prior_only: bool = typer.Option(True, "--prior-only/--all-history"),
) -> None:
    database = Database(db)
    database.migrate()
    report = run_backtest(database, limit=limit, prior_only=prior_only)
    console.print(f"Backtest matches: {report.total_matches}")
    for market, summary in report.markets.items():
        console.print(
            f"{market}: picks={summary.picks} hits={summary.hits} "
            f"misses={summary.misses} no_bets={summary.no_bets} "
            f"pushes={summary.pushes} hit_rate={summary.hit_rate:.2%}"
        )


@app.command("source-status")
def source_status(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    source: str = typer.Option("betexplorer", "--source"),
) -> None:
    database = Database(db)
    database.migrate()
    import_world_cup_2026_seed(database, overwrite_existing=False)
    try:
        summary = summarize_world_cup_sources(database, source=source)
    except ValueError as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc
    console.print(
        f"Source status: {summary.source} "
        f"fixtures={summary.total_fixtures} available_html={summary.available_html}"
    )
    for status, count in summary.by_status.items():
        console.print(f"{status}: {count}")


@app.command("source-matrix")
def source_matrix(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    season: str = typer.Option("2026", "--season"),
) -> None:
    database = Database(db)
    database.migrate()
    import_world_cup_2026_seed(database, overwrite_existing=False)
    matrix = build_source_matrix(database, season=season)
    console.print(
        f"Source matrix: fixtures={matrix.total_fixtures} "
        f"cells={matrix.total_source_cells}"
    )
    for source, summary in matrix.sources.items():
        counts = " ".join(
            f"{status}={count}" for status, count in summary.by_status.items()
        )
        console.print(
            f"{source}: cached={summary.available_html} "
            f"urls={summary.registered_urls} {counts}"
        )


@app.command("source-checks")
def source_checks(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    season: str = typer.Option("2026", "--season"),
    action: str | None = typer.Option(None, "--action"),
    limit: int | None = typer.Option(20, "--limit"),
) -> None:
    database = Database(db)
    database.migrate()
    import_world_cup_2026_seed(database, overwrite_existing=False)
    report = build_source_checks(
        database,
        season=season,
        action=action,
        limit=limit,
    )
    counts = " ".join(
        f"{name}={count}" for name, count in report.by_action.items()
    )
    console.print(
        f"Source checks: fixtures={report.total_fixtures} "
        f"checks={report.total_checks}"
    )
    console.print(counts)
    for check in report.checks:
        console.print(
            f"{check.source} {check.action} "
            f"{check.home_team} vs {check.away_team}: {check.reason}"
        )


@app.command("cache-scan")
def cache_scan(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    cache_dir: Path = typer.Option(Path("data/cache"), "--cache-dir"),
    limit: int | None = typer.Option(20, "--limit"),
) -> None:
    database = Database(db)
    database.migrate()
    report = scan_cache_html(database, cache_dir=cache_dir, limit=limit)
    console.print(
        "Cache scan: "
        f"files={report.total_files} "
        f"parseable={report.parseable_files} "
        f"invalid={report.invalid_files} "
        f"orphan={report.orphan_files} "
        f"missing_links={report.missing_linked_files}"
    )
    for file in report.files:
        console.print(f"{file.source} {file.status} {file.path}: {file.reason}")
    for link in report.missing_links[: limit or len(report.missing_links)]:
        console.print(
            f"{link.source} missing_link "
            f"{link.home_team or '-'} vs {link.away_team or '-'}: {link.html_path}"
        )


@app.command("prepare-demo-data")
def prepare_demo_data_command(
    db: Path = typer.Option(Path("data/handicap_ai.sqlite"), "--db"),
    source: str = typer.Option("betexplorer", "--source"),
    football_data_csv: Path = typer.Option(
        Path("tests/fixtures/football_data_sample.csv"),
        "--football-data-csv",
    ),
    history_folder: Path = typer.Option(
        Path("tests/fixtures/history_folder"),
        "--history-folder",
    ),
    cached_html: Path | None = typer.Option(None, "--cached-html"),
) -> None:
    database = Database(db)
    summary = prepare_demo_data(
        database,
        source=source,
        football_data_csv=football_data_csv,
        history_folder=history_folder,
        cached_html_path=cached_html,
    )
    console.print(
        f"Prepared demo data: fixtures={summary.world_cup_fixtures} "
        f"finished_matches={summary.finished_matches} "
        f"available_html={summary.available_html}"
    )
    for warning in summary.warnings:
        console.print(f"Warning: {warning}")


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
    console.print(
        render_text_report(
            result.match["home_team"],
            result.match["away_team"],
            result.report,
        )
    )


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


def _read_text_option(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        console.print(f"Error: cannot read {label}: {path}")
        raise typer.Exit(1) from exc


def _run_source_action(action: Callable[[], T]) -> T:
    try:
        return action()
    except ValueError as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1) from exc


def _print_source_result(result: SourceLinkResult) -> None:
    details = [f"{result.source}: {result.status.value}"]
    if result.html_path:
        details.append(f"html={result.html_path}")
    if result.url:
        details.append(f"url={result.url}")
    console.print(" ".join(details), soft_wrap=True)
    for warning in result.warnings:
        console.print(f"Warning: {warning}")


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
