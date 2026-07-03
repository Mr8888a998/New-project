from __future__ import annotations

from handicap_ai.recommendation import MarketRecommendation, RecommendationReport


def render_text_report(home: str, away: str, report: RecommendationReport) -> str:
    recommendations = (report.handicap, report.total, report.one_x_two)
    risk_tags = report.risk_tags or ("none",)

    lines = [
        f"Match: {home} vs {away}",
        "",
        f"Handicap pick: {report.handicap.pick.value}",
        f"Total pick: {report.total.pick.value}",
        f"1X2 pick: {report.one_x_two.pick.value}",
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


def _confidence_line(recommendation: MarketRecommendation) -> str:
    return (
        f"- {recommendation.market}: {recommendation.confidence} "
        f"(sample_size={recommendation.sample_size}, "
        f"hit_rate={recommendation.hit_rate:.2f})"
    )
