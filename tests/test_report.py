from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationReport
from handicap_ai.report import render_text_report


def test_render_text_report_contains_required_markets():
    report = RecommendationReport(
        handicap=MarketRecommendation(
            "handicap",
            Pick.AWAY,
            "medium",
            12,
            0.58,
            "Comparable samples favor the underdog side.",
        ),
        total=MarketRecommendation(
            "total",
            Pick.UNDER,
            "medium",
            12,
            0.58,
            "Total moved up without strong over support.",
        ),
        one_x_two=MarketRecommendation(
            "1x2",
            Pick.HOME,
            "high",
            12,
            0.75,
            "1X2 still favors home win.",
        ),
        risk_tags=("line_too_deep", "favorite_heat"),
        data_quality_score=0.85,
    )

    text = render_text_report("England", "Panama", report)

    assert "Handicap pick: away" in text
    assert "Total pick: under" in text
    assert "1X2 pick: home" in text
    assert "line_too_deep" in text


def test_render_text_report_outputs_none_when_no_risk_tags():
    report = RecommendationReport(
        handicap=MarketRecommendation(
            "handicap",
            Pick.NO_BET,
            "low",
            0,
            0.0,
            "No comparable samples.",
        ),
        total=MarketRecommendation(
            "total",
            Pick.NO_BET,
            "low",
            0,
            0.0,
            "No comparable samples.",
        ),
        one_x_two=MarketRecommendation(
            "1x2",
            Pick.NO_BET,
            "low",
            0,
            0.0,
            "No comparable samples.",
        ),
        risk_tags=(),
        data_quality_score=0.25,
    )

    text = render_text_report("England", "Panama", report)

    assert "Risk tags" in text
    assert "- none" in text
