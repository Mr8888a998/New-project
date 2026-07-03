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

    assert text.splitlines() == [
        "Match: England vs Panama",
        "",
        "Handicap pick: away",
        "Total pick: under",
        "1X2 pick: home",
        "",
        "Confidence",
        "- handicap: medium (12 samples, hit rate 58.00%)",
        "- total: medium (12 samples, hit rate 58.00%)",
        "- 1x2: high (12 samples, hit rate 75.00%)",
        "",
        "Data quality: 0.85",
        "",
        "Reasons",
        "- handicap: Comparable samples favor the underdog side.",
        "- total: Total moved up without strong over support.",
        "- 1x2: 1X2 still favors home win.",
        "",
        "Risk tags",
        "- line_too_deep",
        "- favorite_heat",
    ]


def test_render_text_report_outputs_no_bet_and_none_when_no_risk_tags():
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

    assert "Handicap pick: no bet" in text
    assert "Total pick: no bet" in text
    assert "1X2 pick: no bet" in text
    assert "- handicap: low (0 samples, hit rate 0.00%)" in text
    assert "Data quality: 0.25" in text
    assert text.splitlines()[-2:] == [
        "Risk tags",
        "- none",
    ]
