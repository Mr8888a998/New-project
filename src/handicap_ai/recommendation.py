from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

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
    def recommend(
        self,
        features: MatchFeatures,
        similar: Sequence[SimilarityResult],
    ) -> RecommendationReport:
        similar_matches = tuple(similar)
        sample_size = len(similar_matches)

        return RecommendationReport(
            handicap=_recommend_handicap(features, similar_matches, sample_size),
            total=_recommend_total(features, similar_matches, sample_size),
            one_x_two=_recommend_one_x_two(features, similar_matches, sample_size),
            risk_tags=_risk_tags(features, sample_size),
            data_quality_score=features.data_quality_score,
        )


def _recommend_handicap(
    features: MatchFeatures,
    similar: Sequence[SimilarityResult],
    sample_size: int,
) -> MarketRecommendation:
    if sample_size == 0:
        return _no_bet("handicap", sample_size, "no similar matches available")

    if features.data_quality_score < 0.5:
        return _no_bet("handicap", sample_size, "data quality below handicap cutoff")

    home_hits = _label_hits(similar, "handicap", {"home_cover", "home_half_win"})
    away_hits = _label_hits(similar, "handicap", {"away_cover", "home_half_loss"})
    home_rate = _label_rate(similar, "handicap", {"home_cover", "home_half_win"})
    away_rate = _label_rate(similar, "handicap", {"away_cover", "home_half_loss"})

    if away_hits > 0 and away_rate > home_rate:
        reason = "similar matches favor away cover"
        if (
            features.close_handicap is not None
            and features.close_handicap <= -2.0
            and away_rate >= 0.5
        ):
            reason = "deep home favorite with similar away-cover support"
        return _market_recommendation(
            "handicap",
            Pick.AWAY,
            away_rate,
            sample_size,
            reason,
        )

    if home_hits > 0 and home_rate > away_rate:
        return _market_recommendation(
            "handicap",
            Pick.HOME,
            home_rate,
            sample_size,
            "similar matches favor home cover",
        )

    return _no_bet("handicap", sample_size, "no clear handicap edge")


def _recommend_total(
    features: MatchFeatures,
    similar: Sequence[SimilarityResult],
    sample_size: int,
) -> MarketRecommendation:
    if sample_size == 0:
        return _no_bet("total", sample_size, "no similar matches available")

    if features.data_quality_score < 0.5:
        return _no_bet("total", sample_size, "data quality below total cutoff")

    over_hits = _label_hits(similar, "total", {"over", "over_half_win"})
    under_hits = _label_hits(similar, "total", {"under", "under_half_win"})
    over_rate = _label_rate(similar, "total", {"over", "over_half_win"})
    under_rate = _label_rate(similar, "total", {"under", "under_half_win"})

    if (
        features.total_delta is not None
        and features.total_delta > 0
        and under_rate >= over_rate
        and under_hits > 0
    ):
        return _market_recommendation(
            "total",
            Pick.UNDER,
            under_rate,
            sample_size,
            "total moved up while similar matches lean under",
        )

    if over_hits > 0 and over_rate > under_rate:
        return _market_recommendation(
            "total",
            Pick.OVER,
            over_rate,
            sample_size,
            "similar matches favor over",
        )

    if under_hits > 0 and under_rate > over_rate:
        return _market_recommendation(
            "total",
            Pick.UNDER,
            under_rate,
            sample_size,
            "similar matches favor under",
        )

    return _no_bet("total", sample_size, "no clear total edge")


def _recommend_one_x_two(
    features: MatchFeatures,
    similar: Sequence[SimilarityResult],
    sample_size: int,
) -> MarketRecommendation:
    if sample_size == 0:
        return _no_bet("1x2", sample_size, "no similar matches available")

    if features.data_quality_score < 0.5:
        return _no_bet("1x2", sample_size, "data quality below 1x2 cutoff")

    hits = {
        Pick.HOME: _label_hits(similar, "1x2", {"home_win"}),
        Pick.DRAW: _label_hits(similar, "1x2", {"draw"}),
        Pick.AWAY: _label_hits(similar, "1x2", {"away_win"}),
    }
    rates = {
        Pick.HOME: _label_rate(similar, "1x2", {"home_win"}),
        Pick.DRAW: _label_rate(similar, "1x2", {"draw"}),
        Pick.AWAY: _label_rate(similar, "1x2", {"away_win"}),
    }

    if (
        features.closing_home_win_price is not None
        and features.closing_home_win_price <= 1.55
    ):
        hit_rate = rates[Pick.HOME]
        return _market_recommendation(
            "1x2",
            Pick.HOME,
            hit_rate,
            sample_size,
            "short home win price indicates strong favorite",
            confidence_rate=max(hit_rate, 0.6),
        )

    best_pick, best_rate = max(rates.items(), key=lambda item: item[1])
    if hits[best_pick] > 0 and best_rate >= 0.45 and _is_unique_best(best_pick, rates):
        return _market_recommendation(
            "1x2",
            best_pick,
            best_rate,
            sample_size,
            "similar matches support the 1x2 outcome",
        )

    return _no_bet("1x2", sample_size, "no 1x2 outcome reaches support cutoff")


def _label_rate(
    similar: Sequence[SimilarityResult],
    market: str,
    winning_labels: set[str],
) -> float:
    if not similar:
        return 0.0

    hits = _label_hits(similar, market, winning_labels)
    return round(hits / len(similar), 4)


def _label_hits(
    similar: Sequence[SimilarityResult],
    market: str,
    winning_labels: set[str],
) -> int:
    return sum(
        1
        for result in similar
        if _label_value(result.labels.get(market)) in winning_labels
    )


def _is_unique_best(best_pick: Pick, rates: dict[Pick, float]) -> bool:
    best_rate = rates[best_pick]
    return all(
        best_rate > rate for pick, rate in rates.items() if pick is not best_pick
    )


def _label_value(label: object | None) -> str | None:
    if isinstance(label, Enum):
        return str(label.value)
    if label is None:
        return None
    return str(label)


def _market_recommendation(
    market: str,
    pick: Pick,
    hit_rate: float,
    sample_size: int,
    reason: str,
    confidence_rate: float | None = None,
) -> MarketRecommendation:
    detailed_reason = f"{reason}; {_sample_summary(sample_size, hit_rate)}"
    return MarketRecommendation(
        market=market,
        pick=pick,
        confidence=_confidence(
            hit_rate if confidence_rate is None else confidence_rate, sample_size
        ),
        sample_size=sample_size,
        hit_rate=hit_rate,
        reason=detailed_reason,
    )


def _no_bet(market: str, sample_size: int, reason: str) -> MarketRecommendation:
    detailed_reason = f"no bet: {reason}; {_sample_summary(sample_size, 0.0)}"
    return MarketRecommendation(
        market=market,
        pick=Pick.NO_BET,
        confidence="low",
        sample_size=sample_size,
        hit_rate=0.0,
        reason=detailed_reason,
    )


def _sample_summary(sample_size: int, hit_rate: float) -> str:
    sample_word = "sample" if sample_size == 1 else "samples"
    return f"based on {sample_size} {sample_word} at {hit_rate:.2%}"


def _confidence(hit_rate: float, sample_size: int) -> str:
    if sample_size < 5:
        return "low"
    if hit_rate >= 0.65:
        return "high"
    if hit_rate >= 0.55:
        return "medium"
    return "low"


def _risk_tags(features: MatchFeatures, sample_size: int) -> tuple[str, ...]:
    tags: list[str] = []

    if features.close_handicap is not None and abs(features.close_handicap) >= 2.0:
        tags.append("line_too_deep")
    handicap_pattern = features.movement_patterns[0] if features.movement_patterns else ""
    if handicap_pattern.startswith("line_up"):
        tags.append("favorite_heat")
    if features.market_disagreement_score >= 0.7:
        tags.append("market_disagreement")
    if features.data_quality_score < 0.7:
        tags.append("low_data_quality")
    if sample_size < 5:
        tags.append("small_sample")

    return tuple(tags)
