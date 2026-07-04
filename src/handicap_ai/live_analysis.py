from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import TypeAlias

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter
from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter
from handicap_ai.database import Database
from handicap_ai.features import MatchFeatures, build_match_features
from handicap_ai.ingest import ingest_bundles
from handicap_ai.labels import label_to_recommendation_bucket
from handicap_ai.recommendation import RecommendationEngine, RecommendationReport
from handicap_ai.scraping.fetcher import load_saved_html
from handicap_ai.scraping.models import SourceCoverage
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total
from handicap_ai.similarity import (
    SimilarityCandidate,
    SimilarityResult,
    find_similar_matches,
)

HtmlAdapter: TypeAlias = type[BetExplorerHtmlAdapter] | type[OddsPortalHtmlAdapter]


@dataclass(frozen=True)
class LiveAnalysisResult:
    match: sqlite3.Row
    features: MatchFeatures
    coverage: SourceCoverage
    report: RecommendationReport


def analyze_saved_html(db: Database, source: str, html_path: Path) -> LiveAnalysisResult:
    adapter_class = _adapter_for_source(source)
    saved = load_saved_html(source, html_path)
    db.upsert_source_fetch(saved.record)

    bundle, coverage = adapter_class(html_path).parse_html(saved.html)
    ingest_bundles(db, (bundle,))

    match = _resolve_ingested_match(
        db,
        home_team=bundle.match.home_team,
        away_team=bundle.match.away_team,
        source_match_id=bundle.match.source_match_id,
    )
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


def _adapter_for_source(source: str) -> HtmlAdapter:
    adapters: dict[str, HtmlAdapter] = {
        BetExplorerHtmlAdapter.source_name: BetExplorerHtmlAdapter,
        OddsPortalHtmlAdapter.source_name: OddsPortalHtmlAdapter,
    }
    try:
        return adapters[source]
    except KeyError as exc:
        raise ValueError(f"unsupported source: {source}") from exc


def _resolve_ingested_match(
    db: Database,
    home_team: str,
    away_team: str,
    source_match_id: str,
) -> sqlite3.Row:
    matches = db.find_matches_by_names(home_team, away_team)
    source_matches = [
        match for match in matches if match["source_match_id"] == source_match_id
    ]
    if len(source_matches) == 1:
        return source_matches[0]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise LookupError(f"No match found for {home_team} vs {away_team}")
    raise LookupError(f"Multiple matches found for {home_team} vs {away_team}")


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


def _last_line_value(rows: list[sqlite3.Row], field: str) -> float | None:
    if not rows:
        return None
    closing_rows = [row for row in rows if bool(row["is_closing"])]
    row = closing_rows[-1] if closing_rows else rows[-1]
    value = row[field]
    return None if value is None else float(value)
