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
