from handicap_ai.features import MatchFeatures
from handicap_ai.similarity import SimilarityCandidate, find_similar_matches


def _features(open_h, close_h, open_t, close_t):
    return MatchFeatures(
        open_handicap=open_h,
        close_handicap=close_h,
        handicap_delta=None if open_h is None or close_h is None else close_h - open_h,
        open_total=open_t,
        close_total=close_t,
        total_delta=None if open_t is None or close_t is None else close_t - open_t,
        home_water_delta=-0.07,
        away_water_delta=0.12,
        over_water_delta=0.0,
        under_water_delta=0.0,
        closing_home_win_price=1.30,
        closing_draw_price=5.00,
        closing_away_win_price=9.00,
        movement_patterns=("line_up_price_down", "line_up_price_stable"),
        line_depth_score=abs(close_h or 0),
        market_disagreement_score=0.2,
        data_quality_score=1.0,
    )


def test_find_similar_matches_orders_by_distance():
    target = _features(-1.75, -2.25, 3.0, 3.25)
    candidates = [
        SimilarityCandidate(
            match_id=1,
            features=_features(-1.75, -2.25, 3.0, 3.25),
            labels={"handicap": "away_cover"},
        ),
        SimilarityCandidate(
            match_id=2,
            features=_features(-0.25, -0.5, 2.0, 2.25),
            labels={"handicap": "home_cover"},
        ),
    ]

    result = find_similar_matches(target, candidates, limit=1)

    assert result[0].match_id == 1
    assert result[0].distance == 0


def test_find_similar_matches_penalizes_missing_values_and_limits_results():
    target = _features(-1.75, -2.25, 3.0, 3.25)
    candidates = [
        SimilarityCandidate(
            match_id=1,
            features=_features(None, -2.25, 3.0, 3.25),
            labels={"handicap": "partial"},
        ),
        SimilarityCandidate(
            match_id=2,
            features=_features(-1.75, -2.25, 3.0, 3.25),
            labels={"handicap": "exact"},
        ),
    ]

    result = find_similar_matches(target, candidates, limit=1)

    assert len(result) == 1
    assert result[0].match_id == 2
