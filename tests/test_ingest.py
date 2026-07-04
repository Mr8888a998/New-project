from dataclasses import replace
from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles


def test_ingest_bundles_stores_match_and_all_markets(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    bundles = FootballDataCsvAdapter(
        Path("tests/fixtures/football_data_sample.csv"),
        season="2026",
    ).load()

    count = ingest_bundles(db, bundles)

    assert count == 2
    match = db.find_matches_by_names("England", "Panama")[0]
    assert len(db.get_asian_handicaps(match["match_id"])) == 1
    assert len(db.get_totals(match["match_id"])) == 1
    assert len(db.get_one_x_two(match["match_id"])) == 1


def test_repeated_ingest_updates_prices_without_duplicate_market_rows(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    bundles = FootballDataCsvAdapter(
        Path("tests/fixtures/football_data_sample.csv"),
        season="2026",
    ).load()

    first, second = bundles
    updated_first = replace(
        first,
        asian_handicaps=(
            replace(first.asian_handicaps[0], home_price=2.01, away_price=1.82),
        ),
        totals=(
            replace(first.totals[0], over_price=2.11, under_price=1.72),
        ),
        one_x_two=(
            replace(
                first.one_x_two[0],
                home_win_price=1.44,
                draw_price=4.80,
                away_win_price=8.20,
            ),
        ),
    )

    ingest_bundles(db, bundles)
    count = ingest_bundles(db, [updated_first, second])

    assert count == 2
    match = db.find_matches_by_names("England", "Panama")[0]
    asian = db.get_asian_handicaps(match["match_id"])
    totals = db.get_totals(match["match_id"])
    one_x_two = db.get_one_x_two(match["match_id"])
    assert len(asian) == 1
    assert asian[0]["home_price"] == 2.01
    assert asian[0]["away_price"] == 1.82
    assert len(totals) == 1
    assert totals[0]["over_price"] == 2.11
    assert totals[0]["under_price"] == 1.72
    assert len(one_x_two) == 1
    assert one_x_two[0]["home_win_price"] == 1.44
    assert one_x_two[0]["draw_price"] == 4.80
    assert one_x_two[0]["away_win_price"] == 8.20
