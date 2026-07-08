from __future__ import annotations

from dataclasses import dataclass

from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationReport


@dataclass(frozen=True)
class MarketScore:
    market: str
    pick: str
    confidence: str
    hit_rate: float
    sample_size: int
    score: int
    reason: str

    def to_model_score(self) -> dict[str, object]:
        return {
            "pick": self.pick,
            "score": self.score,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Scorecard:
    handicap: MarketScore
    total: MarketScore
    one_x_two: MarketScore
    overall_score: int
    feature_payload: dict[str, object]

    def market_scores(self) -> dict[str, dict[str, object]]:
        return {
            "handicap": self.handicap.to_model_score(),
            "total": self.total.to_model_score(),
            "1x2": self.one_x_two.to_model_score(),
        }


def build_scorecard(features: MatchFeatures, report: RecommendationReport) -> Scorecard:
    handicap = _market_score(report.handicap, report.risk_tags, features.data_quality_score)
    total = _market_score(report.total, report.risk_tags, features.data_quality_score)
    one_x_two = _market_score(
        report.one_x_two,
        report.risk_tags,
        features.data_quality_score,
    )
    active_scores = [
        score.score
        for score in (handicap, total, one_x_two)
        if score.pick != Pick.NO_BET.value
    ]
    overall_score = round(sum(active_scores) / len(active_scores)) if active_scores else 0
    return Scorecard(
        handicap=handicap,
        total=total,
        one_x_two=one_x_two,
        overall_score=overall_score,
        feature_payload=feature_payload(features),
    )


def feature_payload(features: MatchFeatures) -> dict[str, object]:
    return {
        "handicap": {
            "open": features.open_handicap,
            "close": features.close_handicap,
            "delta": features.handicap_delta,
            "home_water_delta": features.home_water_delta,
            "away_water_delta": features.away_water_delta,
            "pattern": _pattern(features, 0),
            "line_depth_score": features.line_depth_score,
        },
        "total": {
            "open": features.open_total,
            "close": features.close_total,
            "delta": features.total_delta,
            "over_water_delta": features.over_water_delta,
            "under_water_delta": features.under_water_delta,
            "pattern": _pattern(features, 1),
        },
        "one_x_two": {
            "home": features.closing_home_win_price,
            "draw": features.closing_draw_price,
            "away": features.closing_away_win_price,
            "market_disagreement_score": features.market_disagreement_score,
        },
        "data_quality": features.data_quality_score,
    }


def _market_score(
    recommendation: MarketRecommendation,
    risk_tags: tuple[str, ...],
    data_quality_score: float,
) -> MarketScore:
    confidence_base = {"high": 38, "medium": 28, "low": 16}.get(
        recommendation.confidence,
        12,
    )
    hit_rate_component = round(max(recommendation.hit_rate, 0.0) * 35)
    sample_component = min(recommendation.sample_size, 20)
    data_quality_component = round(max(min(data_quality_score, 1.0), 0.0) * 15)
    risk_penalty = 4 * len(risk_tags)
    no_bet_penalty = 35 if recommendation.pick is Pick.NO_BET else 0
    raw_score = (
        confidence_base
        + hit_rate_component
        + sample_component
        + data_quality_component
        - risk_penalty
        - no_bet_penalty
    )
    return MarketScore(
        market=recommendation.market,
        pick=recommendation.pick.value,
        confidence=recommendation.confidence,
        hit_rate=recommendation.hit_rate,
        sample_size=recommendation.sample_size,
        score=_clamp_score(raw_score),
        reason=recommendation.reason,
    )


def _pattern(features: MatchFeatures, index: int) -> str | None:
    try:
        return features.movement_patterns[index]
    except IndexError:
        return None


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))
