from datetime import datetime, timezone
from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.database import Database
from handicap_ai.ingest import ingest_bundles
from handicap_ai.models import MatchRecord, MatchStatus
from handicap_ai.resolver import MatchResolver


def _insert_match(
    db: Database,
    *,
    source_match_id: str,
    home_team: str = "England",
    away_team: str = "Panama",
    competition: str,
    kickoff_time: datetime,
) -> None:
    db.upsert_match(
        MatchRecord(
            source_match_id=source_match_id,
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            season="2026",
            kickoff_time=kickoff_time,
            status=MatchStatus.SCHEDULED,
        )
    )


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


def test_resolver_raises_when_exact_match_is_ambiguous(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    _insert_match(
        db,
        source_match_id="fd:wc:2026-06-18:england-panama",
        competition="World Cup",
        kickoff_time=datetime(2026, 6, 18, 20, tzinfo=timezone.utc),
    )
    _insert_match(
        db,
        source_match_id="fd:friendly:2026-03-21:england-panama",
        competition="Friendly",
        kickoff_time=datetime(2026, 3, 21, 19, tzinfo=timezone.utc),
    )

    try:
        MatchResolver(db).resolve("England", "Panama")
    except LookupError as exc:
        message = str(exc)
        assert "Multiple matches found for England vs Panama" in message
        assert "World Cup" in message
        assert "2026-06-18T20:00:00+00:00" in message
        assert "Friendly" in message
        assert "2026-03-21T19:00:00+00:00" in message
    else:
        raise AssertionError("expected LookupError")


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


def test_resolver_raises_when_fuzzy_match_is_ambiguous(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    _insert_match(
        db,
        source_match_id="fd:wc:2026-06-18:england-panama",
        home_team="England",
        away_team="Panama",
        competition="World Cup",
        kickoff_time=datetime(2026, 6, 18, 20, tzinfo=timezone.utc),
    )
    _insert_match(
        db,
        source_match_id="fd:friendly:2026-03-21:englond-panima",
        home_team="Englond",
        away_team="Panima",
        competition="Friendly",
        kickoff_time=datetime(2026, 3, 21, 19, tzinfo=timezone.utc),
    )

    try:
        MatchResolver(db).resolve("Englnd", "Panma")
    except LookupError as exc:
        message = str(exc)
        assert "Multiple fuzzy matches found for Englnd vs Panma" in message
        assert "World Cup" in message
        assert "2026-06-18T20:00:00+00:00" in message
        assert "Friendly" in message
        assert "2026-03-21T19:00:00+00:00" in message
    else:
        raise AssertionError("expected LookupError")


def test_resolver_raises_clear_error_when_no_match(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    try:
        MatchResolver(db).resolve("Brazil", "Japan")
    except LookupError as exc:
        assert "No match found for Brazil vs Japan" in str(exc)
    else:
        raise AssertionError("expected LookupError")
