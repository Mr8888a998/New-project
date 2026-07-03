import sqlite3

from handicap_ai.features import build_match_features, classify_movement


def test_classify_movement_patterns():
    assert (
        classify_movement(
            open_line=-1.75, close_line=-2.25, open_price=1.95, close_price=1.88
        )
        == "line_up_price_down"
    )
    assert (
        classify_movement(
            open_line=3.0, close_line=3.25, open_price=1.90, close_price=1.90
        )
        == "line_up_price_stable"
    )
    assert (
        classify_movement(
            open_line=-1.75, close_line=-1.75, open_price=1.90, close_price=1.87
        )
        == "line_stable_price_down"
    )
    assert (
        classify_movement(
            open_line=-1.75, close_line=-1.75, open_price=1.90, close_price=1.93
        )
        == "line_stable_price_up"
    )
    assert (
        classify_movement(
            open_line=-2.25, close_line=-1.75, open_price=1.90, close_price=None
        )
        == "line_down_price_missing"
    )
    assert (
        classify_movement(
            open_line=-1.75, close_line=-1.75, open_price=None, close_price=1.90
        )
        == "line_stable_price_missing"
    )


def test_build_match_features_from_opening_and_closing_rows():
    features = build_match_features(
        asian_rows=[
            {
                "is_opening": 1,
                "is_closing": 0,
                "line": -1.75,
                "home_price": 1.95,
                "away_price": 1.90,
            },
            {
                "is_opening": 0,
                "is_closing": 1,
                "line": -2.25,
                "home_price": 1.88,
                "away_price": 2.02,
            },
        ],
        total_rows=[
            {
                "is_opening": 1,
                "is_closing": 0,
                "total": 3.0,
                "over_price": 1.90,
                "under_price": 1.96,
            },
            {
                "is_opening": 0,
                "is_closing": 1,
                "total": 3.25,
                "over_price": 1.90,
                "under_price": 1.96,
            },
        ],
        one_x_two_rows=[
            {
                "is_opening": 0,
                "is_closing": 1,
                "home_win_price": 1.30,
                "draw_price": 5.00,
                "away_win_price": 9.00,
            }
        ],
    )

    assert features.open_handicap == -1.75
    assert features.close_handicap == -2.25
    assert features.handicap_delta == -0.5
    assert features.total_delta == 0.25
    assert features.home_water_delta == -0.07
    assert features.away_water_delta == 0.12
    assert features.closing_home_win_price == 1.30
    assert "line_up_price_down" in features.movement_patterns
    assert features.data_quality_score >= 0.7


def test_build_match_features_prefers_same_b365_opening_closing_pair():
    features = build_match_features(
        asian_rows=[
            {
                "source": "fixture",
                "bookmaker": "Other",
                "is_opening": 1,
                "is_closing": 0,
                "line": -0.75,
                "home_price": 1.80,
                "away_price": 2.05,
            },
            {
                "source": "fixture",
                "bookmaker": "B365",
                "is_opening": 1,
                "is_closing": 0,
                "line": -1.75,
                "home_price": 1.95,
                "away_price": 1.90,
            },
            {
                "source": "fixture",
                "bookmaker": "Other",
                "is_opening": 0,
                "is_closing": 1,
                "line": -1.00,
                "home_price": 1.85,
                "away_price": 2.00,
            },
            {
                "source": "fixture",
                "bookmaker": "B365",
                "is_opening": 0,
                "is_closing": 1,
                "line": -2.25,
                "home_price": 1.88,
                "away_price": 2.02,
            },
        ],
        total_rows=[],
        one_x_two_rows=[],
    )

    assert features.open_handicap == -1.75
    assert features.close_handicap == -2.25
    assert features.handicap_delta == -0.5
    assert features.home_water_delta == -0.07


def test_build_match_features_pairs_same_bookmaker_only_with_same_source():
    features = build_match_features(
        asian_rows=[
            {
                "source": "feed-a",
                "bookmaker": "B365",
                "is_opening": 1,
                "is_closing": 0,
                "line": -1.75,
                "home_price": 1.95,
                "away_price": 1.90,
            },
            {
                "source": "feed-b",
                "bookmaker": "B365",
                "is_opening": 0,
                "is_closing": 1,
                "line": -2.25,
                "home_price": 1.88,
                "away_price": 2.02,
            },
            {
                "source": "feed-a",
                "bookmaker": "B365",
                "is_opening": 0,
                "is_closing": 1,
                "line": -2.00,
                "home_price": 1.91,
                "away_price": 1.99,
            },
        ],
        total_rows=[],
        one_x_two_rows=[],
    )

    assert features.open_handicap == -1.75
    assert features.close_handicap == -2.00
    assert features.handicap_delta == -0.25
    assert features.home_water_delta == -0.04


def test_build_match_features_uses_sqlite_rows_and_last_row_fallback():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE asian_lines (
          is_opening INTEGER,
          is_closing INTEGER,
          line REAL,
          home_price REAL,
          away_price REAL
        );
        CREATE TABLE total_lines (
          is_opening INTEGER,
          is_closing INTEGER,
          total REAL,
          over_price REAL,
          under_price REAL
        );
        INSERT INTO asian_lines VALUES (1, 0, 0.25, 1.84, 2.04);
        INSERT INTO asian_lines VALUES (0, 0, 0.0, 1.91, 1.98);
        INSERT INTO total_lines VALUES (1, 0, 2.25, 1.95, 1.86);
        INSERT INTO total_lines VALUES (0, 0, 2.0, 2.01, 1.80);
        """
    )

    features = build_match_features(
        asian_rows=list(connection.execute("SELECT * FROM asian_lines")),
        total_rows=list(connection.execute("SELECT * FROM total_lines")),
        one_x_two_rows=[],
    )

    assert features.open_handicap == 0.25
    assert features.close_handicap == 0.0
    assert features.handicap_delta == -0.25
    assert features.open_total == 2.25
    assert features.close_total == 2.0
    assert features.total_delta == -0.25
    assert features.closing_home_win_price is None


def test_build_match_features_caps_quality_for_closing_only_line_data():
    features = build_match_features(
        asian_rows=[
            {
                "is_opening": 0,
                "is_closing": 1,
                "line": -2.25,
                "home_price": 1.88,
                "away_price": 2.02,
            }
        ],
        total_rows=[
            {
                "is_opening": 0,
                "is_closing": 1,
                "total": 3.25,
                "over_price": 1.90,
                "under_price": 1.96,
            }
        ],
        one_x_two_rows=[
            {
                "is_opening": 0,
                "is_closing": 1,
                "home_win_price": 1.30,
                "draw_price": 5.00,
                "away_win_price": 9.00,
            }
        ],
    )

    assert features.data_quality_score < 0.5


def test_market_disagreement_uses_away_favorite_probability_for_positive_handicap():
    agreement_features = build_match_features(
        asian_rows=[
            {
                "is_opening": 1,
                "is_closing": 0,
                "line": 1.25,
                "home_price": 1.95,
                "away_price": 1.90,
            },
            {
                "is_opening": 0,
                "is_closing": 1,
                "line": 1.50,
                "home_price": 1.92,
                "away_price": 1.94,
            },
        ],
        total_rows=[],
        one_x_two_rows=[
            {
                "is_opening": 0,
                "is_closing": 1,
                "home_win_price": 8.00,
                "draw_price": 4.50,
                "away_win_price": 1.40,
            }
        ],
    )
    disagreement_features = build_match_features(
        asian_rows=[
            {
                "is_opening": 1,
                "is_closing": 0,
                "line": 2.00,
                "home_price": 1.95,
                "away_price": 1.90,
            },
            {
                "is_opening": 0,
                "is_closing": 1,
                "line": 2.25,
                "home_price": 1.92,
                "away_price": 1.94,
            },
        ],
        total_rows=[],
        one_x_two_rows=[
            {
                "is_opening": 0,
                "is_closing": 1,
                "home_win_price": 4.00,
                "draw_price": 3.50,
                "away_win_price": 2.20,
            }
        ],
    )

    assert agreement_features.market_disagreement_score < 0.5
    assert disagreement_features.market_disagreement_score > 0.5


def test_build_match_features_is_deterministic_for_empty_rows():
    features = build_match_features(
        asian_rows=[],
        total_rows=[],
        one_x_two_rows=[],
    )

    assert features.open_handicap is None
    assert features.close_handicap is None
    assert features.handicap_delta is None
    assert features.movement_patterns == ("line_missing", "line_missing")
    assert features.line_depth_score == 0.0
    assert features.market_disagreement_score == 0.5
    assert features.data_quality_score == 0.0
