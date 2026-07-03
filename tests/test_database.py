from datetime import datetime, timezone

from handicap_ai.database import Database
from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    TeamRecord,
)


def test_database_migrates_and_upserts_match_bundle(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    home = TeamRecord(canonical_name="England")
    away = TeamRecord(canonical_name="Panama")
    match = MatchRecord(
        source_match_id="fd:E0:2026-01-01:england-panama",
        home_team="England",
        away_team="Panama",
        competition="E0",
        season="2026",
        kickoff_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=MatchStatus.FINISHED,
        home_score=2,
        away_score=0,
    )
    line = AsianHandicapLineRecord(
        source_match_id=match.source_match_id,
        source="football-data",
        bookmaker="B365",
        is_opening=False,
        is_closing=True,
        line=-1.75,
        home_price=1.95,
        away_price=1.90,
    )

    db.upsert_team(home)
    db.upsert_team(away)
    db.upsert_match(match)
    db.insert_asian_handicap(line)

    resolved = db.find_matches_by_names("England", "Panama")
    assert len(resolved) == 1
    assert resolved[0]["home_team"] == "England"

    lines = db.get_asian_handicaps(resolved[0]["match_id"])
    assert lines[0]["line"] == -1.75
