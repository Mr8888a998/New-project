from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import sqlite3

from handicap_ai.database import Database
from handicap_ai.features import MatchFeatures, build_match_features
from handicap_ai.labels import label_to_recommendation_bucket
from handicap_ai.models import Pick
from handicap_ai.recommendation import RecommendationEngine, RecommendationReport
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total
from handicap_ai.similarity import (
    SimilarityCandidate,
    SimilarityResult,
    find_similar_matches,
)


@dataclass(frozen=True)
class MarketBacktestSummary:
    market: str
    picks: int
    hits: int
    misses: int
    no_bets: int
    pushes: int
    hit_rate: float

    def to_dict(self) -> dict[str, object]:
        return {
            "market": self.market,
            "picks": self.picks,
            "hits": self.hits,
            "misses": self.misses,
            "no_bets": self.no_bets,
            "pushes": self.pushes,
            "hit_rate": self.hit_rate,
        }


@dataclass(frozen=True)
class BacktestMatchResult:
    match_id: int
    home_team: str
    away_team: str
    picks: Mapping[str, str]
    labels: Mapping[str, str]
    hits: Mapping[str, bool | None]

    def to_dict(self) -> dict[str, object]:
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "picks": dict(self.picks),
            "labels": dict(self.labels),
            "hits": dict(self.hits),
        }


@dataclass(frozen=True)
class BacktestReport:
    total_matches: int
    evaluated_matches: int
    markets: Mapping[str, MarketBacktestSummary]
    matches: tuple[BacktestMatchResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_matches": self.total_matches,
            "evaluated_matches": self.evaluated_matches,
            "markets": {
                market: summary.to_dict()
                for market, summary in self.markets.items()
            },
            "matches": [match.to_dict() for match in self.matches],
        }


@dataclass
class _MarketAccumulator:
    market: str
    picks: int = 0
    hits: int = 0
    misses: int = 0
    no_bets: int = 0
    pushes: int = 0

    def observe(self, pick: Pick, label: str | None) -> bool | None:
        if pick is Pick.NO_BET:
            self.no_bets += 1
            return None
        if label is None:
            return None
        if label == "push":
            self.pushes += 1
            return None

        self.picks += 1
        is_hit = _is_hit(self.market, pick, label)
        if is_hit:
            self.hits += 1
        else:
            self.misses += 1
        return is_hit

    def summary(self) -> MarketBacktestSummary:
        hit_rate = round(self.hits / self.picks, 4) if self.picks else 0.0
        return MarketBacktestSummary(
            market=self.market,
            picks=self.picks,
            hits=self.hits,
            misses=self.misses,
            no_bets=self.no_bets,
            pushes=self.pushes,
            hit_rate=hit_rate,
        )


def run_backtest(
    db: Database,
    *,
    limit: int | None = None,
    prior_only: bool = True,
) -> BacktestReport:
    rows = _finished_rows(db)
    if limit is not None:
        rows = rows[-limit:]

    accumulators = {
        "handicap": _MarketAccumulator("handicap"),
        "total": _MarketAccumulator("total"),
        "1x2": _MarketAccumulator("1x2"),
    }
    match_results: list[BacktestMatchResult] = []

    for row in rows:
        match_id = int(row["match_id"])
        features = _features_for_match(db, match_id)
        similar = _similar_matches(db, row, rows, features, prior_only=prior_only)
        report = RecommendationEngine().recommend(features, similar=similar)
        labels = _settled_labels(db, row)
        picks = _picks(report)
        hits = {
            market: accumulators[market].observe(pick, labels.get(market))
            for market, pick in _pick_values(report).items()
        }
        match_results.append(
            BacktestMatchResult(
                match_id=match_id,
                home_team=str(row["home_team"]),
                away_team=str(row["away_team"]),
                picks=picks,
                labels=labels,
                hits=hits,
            )
        )

    return BacktestReport(
        total_matches=len(rows),
        evaluated_matches=len(match_results),
        markets={
            market: accumulator.summary()
            for market, accumulator in accumulators.items()
        },
        matches=tuple(match_results),
    )


def _finished_rows(db: Database) -> list[sqlite3.Row]:
    rows = list(db.all_finished_matches())
    rows.sort(key=lambda row: (str(row["kickoff_time"] or ""), int(row["match_id"])))
    return rows


def _similar_matches(
    db: Database,
    current: sqlite3.Row,
    rows: list[sqlite3.Row],
    features: MatchFeatures,
    *,
    prior_only: bool,
) -> list[SimilarityResult]:
    current_match_id = int(current["match_id"])
    candidates: list[SimilarityCandidate] = []
    for row in rows:
        candidate_id = int(row["match_id"])
        if candidate_id == current_match_id:
            continue
        if prior_only and not _is_prior(row, current):
            continue
        labels = _settled_labels(db, row)
        candidates.append(
            SimilarityCandidate(
                match_id=candidate_id,
                features=_features_for_match(db, candidate_id),
                labels=labels,
            )
        )
    return find_similar_matches(features, candidates, limit=20)


def _features_for_match(db: Database, match_id: int) -> MatchFeatures:
    return build_match_features(
        asian_rows=db.get_asian_handicaps(match_id),
        total_rows=db.get_totals(match_id),
        one_x_two_rows=db.get_one_x_two(match_id),
    )


def _settled_labels(db: Database, row: sqlite3.Row) -> dict[str, str]:
    labels: dict[str, str] = {
        "1x2": label_to_recommendation_bucket(
            settle_one_x_two(int(row["home_score"]), int(row["away_score"]))
        )
    }
    asian_rows = db.get_asian_handicaps(int(row["match_id"]))
    close_handicap = _last_line_value(asian_rows, "line")
    if close_handicap is not None:
        labels["handicap"] = label_to_recommendation_bucket(
            settle_handicap(
                int(row["home_score"]),
                int(row["away_score"]),
                close_handicap,
            )
        )

    total_rows = db.get_totals(int(row["match_id"]))
    close_total = _last_line_value(total_rows, "total")
    if close_total is not None:
        labels["total"] = label_to_recommendation_bucket(
            settle_total(int(row["home_score"]), int(row["away_score"]), close_total)
        )
    return labels


def _pick_values(report: RecommendationReport) -> dict[str, Pick]:
    return {
        "handicap": report.handicap.pick,
        "total": report.total.pick,
        "1x2": report.one_x_two.pick,
    }


def _picks(report: RecommendationReport) -> dict[str, str]:
    return {
        market: pick.value
        for market, pick in _pick_values(report).items()
    }


def _last_line_value(rows: list[sqlite3.Row], field: str) -> float | None:
    if not rows:
        return None
    closing_rows = [row for row in rows if bool(row["is_closing"])]
    row = closing_rows[-1] if closing_rows else rows[-1]
    value = row[field]
    return None if value is None else float(value)


def _is_prior(candidate: sqlite3.Row, current: sqlite3.Row) -> bool:
    candidate_time = _parse_time(candidate["kickoff_time"])
    current_time = _parse_time(current["kickoff_time"])
    if candidate_time is None or current_time is None:
        return False
    return candidate_time < current_time


def _parse_time(value: object | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _is_hit(market: str, pick: Pick, label: str) -> bool:
    winning_labels = {
        "handicap": {
            Pick.HOME: {"home_cover"},
            Pick.AWAY: {"away_cover"},
        },
        "total": {
            Pick.OVER: {"over"},
            Pick.UNDER: {"under"},
        },
        "1x2": {
            Pick.HOME: {"home_win"},
            Pick.DRAW: {"draw"},
            Pick.AWAY: {"away_win"},
        },
    }
    return label in winning_labels.get(market, {}).get(pick, set())
