from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationReport
from handicap_ai.scorecard import build_scorecard, feature_payload


def _features() -> MatchFeatures:
    return MatchFeatures(
        open_handicap=-1.75,
        close_handicap=-2.25,
        handicap_delta=-0.5,
        open_total=3.0,
        close_total=3.25,
        total_delta=0.25,
        home_water_delta=-0.07,
        away_water_delta=0.12,
        over_water_delta=0.0,
        under_water_delta=0.0,
        closing_home_win_price=1.30,
        closing_draw_price=5.00,
        closing_away_win_price=9.00,
        movement_patterns=("line_up_price_down", "line_up_price_stable"),
        line_depth_score=2.25,
        market_disagreement_score=0.2,
        data_quality_score=1.0,
    )


def test_build_scorecard_outputs_numeric_market_scores():
    report = RecommendationReport(
        handicap=MarketRecommendation(
            "handicap",
            Pick.AWAY,
            "medium",
            20,
            0.62,
            "similar away support",
        ),
        total=MarketRecommendation(
            "total",
            Pick.UNDER,
            "high",
            20,
            0.70,
            "similar under support",
        ),
        one_x_two=MarketRecommendation(
            "1x2",
            Pick.HOME,
            "medium",
            20,
            0.60,
            "short home price",
        ),
        risk_tags=("line_too_deep",),
        data_quality_score=1.0,
    )

    scorecard = build_scorecard(_features(), report)

    assert scorecard.handicap.pick == "away"
    assert scorecard.total.score > scorecard.handicap.score
    assert scorecard.one_x_two.market == "1x2"
    assert 0 <= scorecard.overall_score <= 100
    market_scores = scorecard.market_scores()
    assert set(market_scores) == {"handicap", "total", "1x2"}
    assert market_scores["handicap"] == {
        "pick": "away",
        "score": scorecard.handicap.score,
        "confidence": "medium",
        "reason": "similar away support",
    }


def test_feature_payload_exposes_line_and_water_movement():
    payload = feature_payload(_features())

    assert payload["handicap"]["open"] == -1.75
    assert payload["handicap"]["close"] == -2.25
    assert payload["handicap"]["home_water_delta"] == -0.07
    assert payload["total"]["delta"] == 0.25
    assert payload["one_x_two"]["home"] == 1.3
