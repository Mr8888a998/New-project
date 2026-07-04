from datetime import datetime, timezone

import pytest

from handicap_ai.database import Database
from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    OneXTwoLineRecord,
    TeamRecord,
    TotalsLineRecord,
)


def _match_record(
    *,
    source_match_id: str = "fd:E0:2026-01-01:england-panama",
    status: MatchStatus = MatchStatus.FINISHED,
    home_score: int | None = 2,
    away_score: int | None = 0,
) -> MatchRecord:
    return MatchRecord(
        source_match_id=source_match_id,
        home_team="England",
        away_team="Panama",
        competition="E0",
        season="2026",
        kickoff_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=status,
        home_score=home_score,
        away_score=away_score,
    )


def _asian_line(
    *,
    source_match_id: str = "fd:E0:2026-01-01:england-panama",
    line: float = -1.75,
    home_price: float | None = 1.95,
    away_price: float | None = 1.90,
    is_opening: bool = False,
    is_closing: bool = True,
    captured_at: datetime | None = None,
) -> AsianHandicapLineRecord:
    return AsianHandicapLineRecord(
        source_match_id=source_match_id,
        source="football-data",
        bookmaker="B365",
        is_opening=is_opening,
        is_closing=is_closing,
        line=line,
        home_price=home_price,
        away_price=away_price,
        captured_at=captured_at,
    )


def _total_line(
    *,
    source_match_id: str = "fd:E0:2026-01-01:england-panama",
    total: float = 2.5,
    over_price: float | None = 2.05,
    under_price: float | None = 1.80,
    is_opening: bool = False,
    is_closing: bool = True,
    captured_at: datetime | None = None,
) -> TotalsLineRecord:
    return TotalsLineRecord(
        source_match_id=source_match_id,
        source="football-data",
        bookmaker="market-average",
        is_opening=is_opening,
        is_closing=is_closing,
        total=total,
        over_price=over_price,
        under_price=under_price,
        captured_at=captured_at,
    )


def _one_x_two_line(
    *,
    source_match_id: str = "fd:E0:2026-01-01:england-panama",
    home_win_price: float | None = 1.30,
    draw_price: float | None = 5.00,
    away_win_price: float | None = 9.00,
    is_opening: bool = False,
    is_closing: bool = True,
    captured_at: datetime | None = None,
) -> OneXTwoLineRecord:
    return OneXTwoLineRecord(
        source_match_id=source_match_id,
        source="football-data",
        bookmaker="B365",
        is_opening=is_opening,
        is_closing=is_closing,
        home_win_price=home_win_price,
        draw_price=draw_price,
        away_win_price=away_win_price,
        captured_at=captured_at,
    )


def test_database_migrates_and_upserts_match_bundle(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    home = TeamRecord(canonical_name="England")
    away = TeamRecord(canonical_name="Panama")
    match = _match_record()
    line = _asian_line(source_match_id=match.source_match_id)

    db.upsert_team(home)
    db.upsert_team(away)
    db.upsert_match(match)
    db.insert_asian_handicap(line)

    resolved = db.find_matches_by_names("England", "Panama")
    assert len(resolved) == 1
    assert resolved[0]["home_team"] == "England"

    lines = db.get_asian_handicaps(resolved[0]["match_id"])
    assert lines[0]["line"] == -1.75


def test_upsert_team_uses_normalized_name_as_identity(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    db.upsert_team(TeamRecord(canonical_name="England", country="UK"))
    db.upsert_team(TeamRecord(canonical_name="ENGLAND"))

    rows = db.execute(
        "SELECT canonical_name, normalized_name, country FROM teams WHERE normalized_name = ?",
        ("england",),
    )
    assert len(rows) == 1
    assert rows[0]["canonical_name"] == "ENGLAND"
    assert rows[0]["country"] == "UK"


def test_insert_asian_handicap_is_idempotent_and_updates_prices(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    match = _match_record()
    match_id = db.upsert_match(match)

    db.insert_asian_handicap(_asian_line(source_match_id=match.source_match_id))
    db.insert_asian_handicap(
        _asian_line(
            source_match_id=match.source_match_id,
            home_price=2.01,
            away_price=1.80,
        )
    )

    lines = db.get_asian_handicaps(match_id)
    assert len(lines) == 1
    assert lines[0]["home_price"] == 2.01
    assert lines[0]["away_price"] == 1.80


def test_insert_asian_handicap_raises_when_match_missing(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    with pytest.raises(ValueError, match="source_match_id"):
        db.insert_asian_handicap(_asian_line(source_match_id="missing-match"))


def test_insert_total_is_idempotent_and_updates_prices(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    match = _match_record()
    match_id = db.upsert_match(match)

    db.insert_total(_total_line(source_match_id=match.source_match_id))
    db.insert_total(
        _total_line(
            source_match_id=match.source_match_id,
            over_price=2.11,
            under_price=1.72,
        )
    )

    lines = db.get_totals(match_id)
    assert len(lines) == 1
    assert lines[0]["over_price"] == 2.11
    assert lines[0]["under_price"] == 1.72


def test_insert_total_raises_when_match_missing(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    with pytest.raises(ValueError, match="source_match_id"):
        db.insert_total(_total_line(source_match_id="missing-match"))


def test_insert_one_x_two_is_idempotent_and_updates_prices(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    match = _match_record()
    match_id = db.upsert_match(match)

    db.insert_one_x_two(_one_x_two_line(source_match_id=match.source_match_id))
    db.insert_one_x_two(
        _one_x_two_line(
            source_match_id=match.source_match_id,
            home_win_price=1.44,
            draw_price=4.80,
            away_win_price=8.20,
        )
    )

    lines = db.get_one_x_two(match_id)
    assert len(lines) == 1
    assert lines[0]["home_win_price"] == 1.44
    assert lines[0]["draw_price"] == 4.80
    assert lines[0]["away_win_price"] == 8.20


def test_insert_one_x_two_raises_when_match_missing(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    with pytest.raises(ValueError, match="source_match_id"):
        db.insert_one_x_two(_one_x_two_line(source_match_id="missing-match"))


def test_upsert_match_updates_existing_status_and_score(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    source_match_id = "fd:E0:2026-01-01:england-panama"

    db.upsert_match(
        _match_record(
            source_match_id=source_match_id,
            status=MatchStatus.SCHEDULED,
            home_score=None,
            away_score=None,
        )
    )
    db.upsert_match(
        _match_record(
            source_match_id=source_match_id,
            status=MatchStatus.FINISHED,
            home_score=3,
            away_score=1,
        )
    )

    rows = db.find_matches_by_names("England", "Panama")
    assert len(rows) == 1
    assert rows[0]["status"] == MatchStatus.FINISHED.value
    assert rows[0]["home_score"] == 3
    assert rows[0]["away_score"] == 1


def test_get_asian_handicaps_orders_opening_first_then_captured_at(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    match = _match_record()
    match_id = db.upsert_match(match)

    db.insert_asian_handicap(
        _asian_line(
            source_match_id=match.source_match_id,
            line=-2.25,
            is_opening=False,
            is_closing=True,
            captured_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
        )
    )
    db.insert_asian_handicap(
        _asian_line(
            source_match_id=match.source_match_id,
            line=-1.75,
            is_opening=True,
            is_closing=False,
            captured_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        )
    )
    db.insert_asian_handicap(
        _asian_line(
            source_match_id=match.source_match_id,
            line=-2.0,
            is_opening=False,
            is_closing=True,
            captured_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        )
    )

    lines = db.get_asian_handicaps(match_id)
    assert [line["line"] for line in lines] == [-1.75, -2.0, -2.25]
