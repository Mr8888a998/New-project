from datetime import datetime, timezone
from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.live_analysis import analyze_saved_html
from handicap_ai.models import MatchRecord, MatchStatus


def test_analyze_saved_html_ingests_source_and_returns_report(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    result = analyze_saved_html(
        db=db,
        source="betexplorer",
        html_path=Path("tests/fixtures/betexplorer_match.html"),
    )

    assert result.match["home_team"] == "England"
    assert result.match["away_team"] == "Panama"
    assert result.coverage.is_complete is True
    assert result.report.handicap.market == "handicap"
    assert result.report.total.market == "total"
    assert result.report.one_x_two.market == "1x2"
    assert db.list_source_fetches("betexplorer")


def test_analyze_saved_html_marks_incomplete_coverage(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()

    result = analyze_saved_html(
        db=db,
        source="betexplorer",
        html_path=Path("tests/fixtures/betexplorer_missing_market.html"),
    )

    assert result.coverage.is_complete is False
    assert result.coverage.missing_markets == ("totals",)


def test_analyze_saved_html_resolves_ingested_match_when_history_has_same_teams(
    tmp_path,
):
    db = Database(tmp_path / "handicap.sqlite")
    db.migrate()
    db.upsert_match(
        MatchRecord(
            source_match_id="historical-england-panama",
            home_team="England",
            away_team="Panama",
            competition="World Cup",
            season="2022",
            kickoff_time=datetime(2022, 6, 24, 18, tzinfo=timezone.utc),
            status=MatchStatus.FINISHED,
            home_score=2,
            away_score=0,
        )
    )

    result = analyze_saved_html(
        db=db,
        source="betexplorer",
        html_path=Path("tests/fixtures/betexplorer_match.html"),
    )

    assert result.match["source_match_id"] == "be:england-panama"
