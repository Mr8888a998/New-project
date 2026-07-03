from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles
from handicap_ai.resolver import MatchResolver


def test_resolver_finds_match_from_home_and_away_only(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    ingest_bundles(
        db,
        FootballDataCsvAdapter(
            Path("tests/fixtures/football_data_sample.csv"),
            season="2026",
        ).load(),
    )

    match = MatchResolver(db).resolve("england", "panama")

    assert match["home_team"] == "England"
    assert match["away_team"] == "Panama"


def test_resolver_fuzzy_matches_normalized_home_and_away(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    ingest_bundles(
        db,
        FootballDataCsvAdapter(
            Path("tests/fixtures/football_data_sample.csv"),
            season="2026",
        ).load(),
    )

    match = MatchResolver(db).resolve("Englnd", "Panma")

    assert match["home_team"] == "England"
    assert match["away_team"] == "Panama"


def test_resolver_raises_clear_error_when_no_match(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    try:
        MatchResolver(db).resolve("Brazil", "Japan")
    except LookupError as exc:
        assert "No match found for Brazil vs Japan" in str(exc)
    else:
        raise AssertionError("expected LookupError")
