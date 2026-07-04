from __future__ import annotations

from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationReport


def render_text_report(home: str, away: str, report: RecommendationReport) -> str:
    recommendations = (report.handicap, report.total, report.one_x_two)
    risk_tags = report.risk_tags or ("none",)

    lines = [
        f"Match: {home} vs {away}",
        "",
        f"Handicap pick: {_pick_label(report.handicap.pick)}",
        f"Total pick: {_pick_label(report.total.pick)}",
        f"1X2 pick: {_pick_label(report.one_x_two.pick)}",
        "",
        "Confidence",
        *[_confidence_line(recommendation) for recommendation in recommendations],
        "",
        f"Data quality: {report.data_quality_score:.2f}",
        "",
        "Reasons",
        *[
            f"- {recommendation.market}: {recommendation.reason}"
            for recommendation in recommendations
        ],
        "",
        "Risk tags",
        *[f"- {risk_tag}" for risk_tag in risk_tags],
    ]

    return "\n".join(lines)


def _pick_label(pick: Pick) -> str:
    if pick is Pick.NO_BET:
        return "no bet"
    return pick.value


def _confidence_line(recommendation: MarketRecommendation) -> str:
    sample_word = "sample" if recommendation.sample_size == 1 else "samples"
    return (
        f"- {recommendation.market}: {recommendation.confidence} "
        f"({recommendation.sample_size} {sample_word}, "
        f"hit rate {recommendation.hit_rate:.2%})"
    )
