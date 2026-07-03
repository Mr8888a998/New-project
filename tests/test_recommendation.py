from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.recommendation import RecommendationEngine
from handicap_ai.similarity import SimilarityResult


def _features(
    *,
    close_handicap=-2.25,
    total_delta=0.25,
    closing_home_win_price=1.30,
    market_disagreement_score=0.2,
    data_quality_score=1.0,
):
    return MatchFeatures(
        open_handicap=-1.75,
        close_handicap=close_handicap,
        handicap_delta=None if close_handicap is None else close_handicap + 1.75,
        open_total=3.0,
        close_total=3.25,
        total_delta=total_delta,
        home_water_delta=-0.07,
        away_water_delta=0.12,
        over_water_delta=0.0,
        under_water_delta=0.0,
        closing_home_win_price=closing_home_win_price,
        closing_draw_price=5.00,
        closing_away_win_price=9.00,
        movement_patterns=("line_up_price_down", "line_up_price_stable"),
        line_depth_score=abs(close_handicap or 0.0),
        market_disagreement_score=market_disagreement_score,
        data_quality_score=data_quality_score,
    )


def test_recommendation_engine_outputs_three_market_picks():
    features = MatchFeatures(
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
    similar = [
        SimilarityResult(
            match_id=1,
            distance=0.1,
            labels={"handicap": "away_cover", "total": "under", "1x2": "home_win"},
        ),
        SimilarityResult(
            match_id=2,
            distance=0.2,
            labels={"handicap": "away_cover", "total": "under", "1x2": "home_win"},
        ),
        SimilarityResult(
            match_id=3,
            distance=0.3,
            labels={"handicap": "home_cover", "total": "over", "1x2": "home_win"},
        ),
    ]

    report = RecommendationEngine().recommend(features, similar)

    assert report.handicap.pick == Pick.AWAY
    assert report.total.pick == Pick.UNDER
    assert report.one_x_two.pick == Pick.HOME
    assert "line_too_deep" in report.risk_tags


def test_low_data_quality_suppresses_handicap_and_total_picks():
    similar = [
        SimilarityResult(
            match_id=1,
            distance=0.1,
            labels={"handicap": "home_cover", "total": "over", "1x2": "away_win"},
        ),
        SimilarityResult(
            match_id=2,
            distance=0.2,
            labels={"handicap": "home_cover", "total": "over", "1x2": "away_win"},
        ),
    ]

    report = RecommendationEngine().recommend(
        _features(data_quality_score=0.49, closing_home_win_price=1.90),
        similar,
    )

    assert report.handicap.pick == Pick.NO_BET
    assert report.total.pick == Pick.NO_BET
    assert "low_data_quality" in report.risk_tags


def test_one_x_two_uses_similar_draw_rate_when_home_price_is_not_short():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"1x2": "draw"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"1x2": "draw"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"1x2": "draw"}),
        SimilarityResult(match_id=4, distance=0.4, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=5, distance=0.5, labels={"1x2": "away_win"}),
    ]

    report = RecommendationEngine().recommend(
        _features(close_handicap=-0.5, closing_home_win_price=2.10),
        similar,
    )

    assert report.one_x_two.pick == Pick.DRAW
    assert report.one_x_two.hit_rate == 0.6
    assert report.one_x_two.confidence == "medium"
