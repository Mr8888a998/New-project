from datetime import datetime, timezone

from handicap_ai.backtest import run_backtest
from handicap_ai.database import Database
from handicap_ai.models import (
    AsianHandicapLineRecord,
    MatchRecord,
    MatchStatus,
    OneXTwoLineRecord,
    TotalsLineRecord,
)


def _insert_finished_match(
    db: Database,
    *,
    source_match_id: str,
    kickoff: datetime,
    home_score: int,
    away_score: int,
    close_handicap: float,
    close_total: float,
) -> None:
    db.upsert_match(
        MatchRecord(
            source_match_id=source_match_id,
            home_team=f"Home {source_match_id}",
            away_team=f"Away {source_match_id}",
            competition="World Cup",
            season="2026",
            kickoff_time=kickoff,
            status=MatchStatus.FINISHED,
            home_score=home_score,
            away_score=away_score,
        )
    )
    db.insert_asian_handicap(
        AsianHandicapLineRecord(
            source_match_id=source_match_id,
            source="football-data",
            bookmaker="B365",
            is_opening=True,
            is_closing=False,
            line=close_handicap + 0.25,
            home_price=1.95,
            away_price=1.90,
        )
    )
    db.insert_asian_handicap(
        AsianHandicapLineRecord(
            source_match_id=source_match_id,
            source="football-data",
            bookmaker="B365",
            is_opening=False,
            is_closing=True,
            line=close_handicap,
            home_price=1.88,
            away_price=2.02,
        )
    )
    db.insert_total(
        TotalsLineRecord(
            source_match_id=source_match_id,
            source="football-data",
            bookmaker="B365",
            is_opening=True,
            is_closing=False,
            total=close_total - 0.25,
            over_price=1.91,
            under_price=1.95,
        )
    )
    db.insert_total(
        TotalsLineRecord(
            source_match_id=source_match_id,
            source="football-data",
            bookmaker="B365",
            is_opening=False,
            is_closing=True,
            total=close_total,
            over_price=1.93,
            under_price=1.93,
        )
    )
    db.insert_one_x_two(
        OneXTwoLineRecord(
            source_match_id=source_match_id,
            source="football-data",
            bookmaker="B365",
            is_opening=False,
            is_closing=True,
            home_win_price=1.45,
            draw_price=4.80,
            away_win_price=8.50,
        )
    )


def test_run_backtest_summarizes_three_markets(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    for index, score in enumerate(((2, 0), (3, 1), (1, 0)), start=1):
        _insert_finished_match(
            db,
            source_match_id=f"m{index}",
            kickoff=datetime(2026, 6, index, tzinfo=timezone.utc),
            home_score=score[0],
            away_score=score[1],
            close_handicap=-1.25,
            close_total=2.5,
        )

    report = run_backtest(db, prior_only=False)

    assert report.total_matches == 3
    assert set(report.markets) == {"handicap", "total", "1x2"}
    assert report.markets["handicap"].picks > 0
    assert report.markets["total"].picks > 0
    assert report.markets["1x2"].hit_rate >= 0.0
    assert report.to_dict()["markets"]["handicap"]["picks"] > 0


def test_run_backtest_can_limit_finished_matches(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    for index in range(1, 4):
        _insert_finished_match(
            db,
            source_match_id=f"limited-{index}",
            kickoff=datetime(2026, 7, index, tzinfo=timezone.utc),
            home_score=2,
            away_score=0,
            close_handicap=-1.25,
            close_total=2.5,
        )

    report = run_backtest(db, limit=2, prior_only=False)

    assert report.total_matches == 2
