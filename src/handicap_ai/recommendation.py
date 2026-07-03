from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.similarity import SimilarityResult


@dataclass(frozen=True)
class MarketRecommendation:
    pick: Pick
    hit_rate: float
    sample_size: int
    confidence: str


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
    home_rate = _label_rate(similar, "handicap", {"home_cover", "home_half_win"})
    away_rate = _label_rate(similar, "handicap", {"away_cover", "home_half_loss"})

    if features.data_quality_score < 0.5:
        return _market_recommendation(
            Pick.NO_BET, max(home_rate, away_rate), sample_size
        )

    if (
        features.close_handicap is not None
        and features.close_handicap <= -2.0
        and away_rate >= 0.5
    ):
        return _market_recommendation(Pick.AWAY, away_rate, sample_size)

    if home_rate > away_rate:
        return _market_recommendation(Pick.HOME, home_rate, sample_size)

    return _market_recommendation(Pick.NO_BET, max(home_rate, away_rate), sample_size)


def _recommend_total(
    features: MatchFeatures,
    similar: Sequence[SimilarityResult],
    sample_size: int,
) -> MarketRecommendation:
    over_rate = _label_rate(similar, "total", {"over", "over_half_win"})
    under_rate = _label_rate(similar, "total", {"under", "under_half_win"})

    if features.data_quality_score < 0.5:
        return _market_recommendation(
            Pick.NO_BET, max(over_rate, under_rate), sample_size
        )

    if (
        features.total_delta is not None
        and features.total_delta > 0
        and under_rate >= over_rate
    ):
        return _market_recommendation(Pick.UNDER, under_rate, sample_size)

    if over_rate > under_rate:
        return _market_recommendation(Pick.OVER, over_rate, sample_size)

    return _market_recommendation(Pick.NO_BET, max(over_rate, under_rate), sample_size)


def _recommend_one_x_two(
    features: MatchFeatures,
    similar: Sequence[SimilarityResult],
    sample_size: int,
) -> MarketRecommendation:
    rates = {
        Pick.HOME: _label_rate(similar, "1x2", {"home_win"}),
        Pick.DRAW: _label_rate(similar, "1x2", {"draw"}),
        Pick.AWAY: _label_rate(similar, "1x2", {"away_win"}),
    }

    if (
        features.closing_home_win_price is not None
        and features.closing_home_win_price <= 1.55
    ):
        return _market_recommendation(Pick.HOME, rates[Pick.HOME], sample_size)

    best_pick, best_rate = max(rates.items(), key=lambda item: item[1])
    if best_rate >= 0.45:
        return _market_recommendation(best_pick, best_rate, sample_size)

    return _market_recommendation(Pick.NO_BET, best_rate, sample_size)


def _label_rate(
    similar: Sequence[SimilarityResult],
    market: str,
    winning_labels: set[str],
) -> float:
    if not similar:
        return 0.0

    hits = sum(
        1
        for result in similar
        if _label_value(result.labels.get(market)) in winning_labels
    )
    return round(hits / len(similar), 4)


def _label_value(label: object | None) -> str | None:
    if isinstance(label, Enum):
        return str(label.value)
    if label is None:
        return None
    return str(label)


def _market_recommendation(
    pick: Pick,
    hit_rate: float,
    sample_size: int,
) -> MarketRecommendation:
    return MarketRecommendation(
        pick=pick,
        hit_rate=hit_rate,
        sample_size=sample_size,
        confidence=_confidence(hit_rate, sample_size),
    )


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

    if (
        features.line_depth_score >= 2.0
        or features.close_handicap is not None
        and features.close_handicap <= -2.0
    ):
        tags.append("line_too_deep")
    if (
        features.closing_home_win_price is not None
        and features.closing_home_win_price <= 1.55
    ):
        tags.append("favorite_heat")
    if features.market_disagreement_score >= 0.5:
        tags.append("market_disagreement")
    if features.data_quality_score < 0.5:
        tags.append("low_data_quality")
    if sample_size < 5:
        tags.append("small_sample")

    return tuple(tags)
