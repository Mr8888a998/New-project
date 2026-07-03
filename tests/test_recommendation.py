from dataclasses import fields

from handicap_ai.features import MatchFeatures
from handicap_ai.models import Pick
from handicap_ai.recommendation import MarketRecommendation, RecommendationEngine
from handicap_ai.similarity import SimilarityResult


def _features(
    *,
    close_handicap=-2.25,
    total_delta=0.25,
    closing_home_win_price=1.30,
    movement_patterns=("line_up_price_down", "line_up_price_stable"),
    line_depth_score=None,
    market_disagreement_score=0.2,
    data_quality_score=1.0,
):
    if line_depth_score is None:
        line_depth_score = abs(close_handicap or 0.0)

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
        movement_patterns=movement_patterns,
        line_depth_score=line_depth_score,
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
    assert report.handicap.market == "handicap"
    assert report.total.market == "total"
    assert report.one_x_two.market == "1x2"
    assert report.handicap.reason
    assert report.total.reason
    assert report.one_x_two.reason
    assert "line_too_deep" in report.risk_tags


def test_market_recommendation_fields_match_spec():
    assert [field.name for field in fields(MarketRecommendation)] == [
        "market",
        "pick",
        "confidence",
        "sample_size",
        "hit_rate",
        "reason",
    ]


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
    assert report.handicap.confidence == "low"
    assert report.handicap.hit_rate == 0.0
    assert report.handicap.reason
    assert report.total.pick == Pick.NO_BET
    assert report.total.confidence == "low"
    assert report.total.hit_rate == 0.0
    assert report.total.reason
    assert report.one_x_two.pick == Pick.NO_BET
    assert report.one_x_two.confidence == "low"
    assert report.one_x_two.hit_rate == 0.0
    assert "data quality" in report.one_x_two.reason
    assert "low_data_quality" in report.risk_tags


def test_empty_similar_list_returns_no_bet_for_sample_driven_markets():
    report = RecommendationEngine().recommend(
        _features(closing_home_win_price=1.90),
        [],
    )

    assert report.handicap.pick == Pick.NO_BET
    assert report.total.pick == Pick.NO_BET
    assert report.one_x_two.pick == Pick.NO_BET
    assert report.total.sample_size == 0
    assert report.total.hit_rate == 0.0
    assert "no bet" in report.total.reason


def test_low_data_quality_gates_one_x_two_strong_home_price():
    similar = [
        SimilarityResult(match_id=index, distance=index / 10, labels={"1x2": "home_win"})
        for index in range(1, 6)
    ]

    report = RecommendationEngine().recommend(
        _features(data_quality_score=0.49, closing_home_win_price=1.30),
        similar,
    )

    assert report.one_x_two.pick == Pick.NO_BET
    assert report.one_x_two.confidence == "low"
    assert report.one_x_two.hit_rate == 0.0
    assert "data quality" in report.one_x_two.reason


def test_one_x_two_no_bet_uses_low_confidence_and_zero_hit_rate():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"1x2": "draw"}),
        SimilarityResult(match_id=4, distance=0.4, labels={"1x2": "draw"}),
        SimilarityResult(match_id=5, distance=0.5, labels={"1x2": "away_win"}),
    ]

    report = RecommendationEngine().recommend(
        _features(close_handicap=-0.5, closing_home_win_price=2.10),
        similar,
    )

    assert report.one_x_two.pick == Pick.NO_BET
    assert report.one_x_two.confidence == "low"
    assert report.one_x_two.hit_rate == 0.0
    assert report.one_x_two.reason


def test_one_x_two_tied_best_rate_returns_no_bet():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=4, distance=0.4, labels={"1x2": "draw"}),
        SimilarityResult(match_id=5, distance=0.5, labels={"1x2": "draw"}),
        SimilarityResult(match_id=6, distance=0.6, labels={"1x2": "draw"}),
    ]

    report = RecommendationEngine().recommend(
        _features(close_handicap=-0.5, closing_home_win_price=2.10),
        similar,
    )

    assert report.one_x_two.pick == Pick.NO_BET
    assert "no bet" in report.one_x_two.reason


def test_one_x_two_strong_home_price_uses_confidence_floor_and_reason():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"1x2": "home_win"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"1x2": "draw"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"1x2": "draw"}),
        SimilarityResult(match_id=4, distance=0.4, labels={"1x2": "away_win"}),
        SimilarityResult(match_id=5, distance=0.5, labels={"1x2": "away_win"}),
    ]

    report = RecommendationEngine().recommend(
        _features(close_handicap=-1.0, closing_home_win_price=1.50),
        similar,
    )

    assert report.one_x_two.pick == Pick.HOME
    assert report.one_x_two.hit_rate == 0.2
    assert report.one_x_two.confidence == "medium"
    assert "price" in report.one_x_two.reason


def test_positive_handicap_with_away_cover_support_recommends_away():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"handicap": "away_cover"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"handicap": "away_cover"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"handicap": "away_cover"}),
        SimilarityResult(match_id=4, distance=0.4, labels={"handicap": "home_cover"}),
        SimilarityResult(match_id=5, distance=0.5, labels={}),
    ]

    report = RecommendationEngine().recommend(
        _features(close_handicap=0.75, closing_home_win_price=2.60),
        similar,
    )

    assert report.handicap.pick == Pick.AWAY
    assert report.handicap.hit_rate == 0.6
    assert "sample_size=5" in report.handicap.reason


def test_total_without_line_delta_can_follow_under_support():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"total": "under"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"total": "under"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"total": "under"}),
        SimilarityResult(match_id=4, distance=0.4, labels={"total": "over"}),
        SimilarityResult(match_id=5, distance=0.5, labels={}),
    ]

    report = RecommendationEngine().recommend(
        _features(total_delta=None, closing_home_win_price=2.10),
        similar,
    )

    assert report.total.pick == Pick.UNDER
    assert report.total.hit_rate == 0.6
    assert "sample_size=5" in report.total.reason

    empty_report = RecommendationEngine().recommend(
        _features(total_delta=None, closing_home_win_price=2.10),
        [],
    )

    assert empty_report.total.pick == Pick.NO_BET
    assert empty_report.total.hit_rate == 0.0
    assert "no bet" in empty_report.total.reason


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


def test_total_only_line_up_pattern_does_not_emit_favorite_heat():
    similar = [
        SimilarityResult(match_id=index, distance=index / 10, labels={})
        for index in range(1, 6)
    ]

    report = RecommendationEngine().recommend(
        _features(
            close_handicap=1.0,
            closing_home_win_price=2.00,
            movement_patterns=("line_stable_price_down", "line_up_price_stable"),
        ),
        similar,
    )

    assert "favorite_heat" not in report.risk_tags


def test_reasons_include_sample_count_or_no_bet_rationale():
    similar = [
        SimilarityResult(match_id=1, distance=0.1, labels={"handicap": "away_cover"}),
        SimilarityResult(match_id=2, distance=0.2, labels={"handicap": "away_cover"}),
        SimilarityResult(match_id=3, distance=0.3, labels={"handicap": "home_cover"}),
    ]

    report = RecommendationEngine().recommend(_features(), similar)
    empty_report = RecommendationEngine().recommend(
        _features(closing_home_win_price=2.10),
        [],
    )

    assert "sample_size=3" in report.handicap.reason
    assert "hit_rate=0.6667" in report.handicap.reason
    assert "no bet" in empty_report.handicap.reason


def test_risk_tag_thresholds_follow_spec():
    similar = [
        SimilarityResult(match_id=index, distance=index / 10, labels={})
        for index in range(1, 6)
    ]

    report = RecommendationEngine().recommend(
        _features(
            close_handicap=2.0,
            closing_home_win_price=1.30,
            movement_patterns=("line_stable_price_down",),
            market_disagreement_score=0.69,
            data_quality_score=0.69,
        ),
        similar,
    )

    assert "line_too_deep" in report.risk_tags
    assert "low_data_quality" in report.risk_tags
    assert "favorite_heat" not in report.risk_tags
    assert "market_disagreement" not in report.risk_tags
    assert "small_sample" not in report.risk_tags

    report = RecommendationEngine().recommend(
        _features(
            close_handicap=1.75,
            closing_home_win_price=2.00,
            movement_patterns=("line_up_price_stable",),
            line_depth_score=2.25,
            market_disagreement_score=0.7,
            data_quality_score=0.7,
        ),
        similar,
    )

    assert "line_too_deep" not in report.risk_tags
    assert "favorite_heat" in report.risk_tags
    assert "market_disagreement" in report.risk_tags
    assert "low_data_quality" not in report.risk_tags
