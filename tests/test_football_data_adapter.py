from pathlib import Path

from handicap_ai.adapters.football_data import FootballDataCsvAdapter
from handicap_ai.models import MatchStatus


def test_football_data_adapter_normalizes_rows():
    adapter = FootballDataCsvAdapter(
        Path("tests/fixtures/football_data_sample.csv"),
        season="2026",
    )
    bundles = list(adapter.load())

    assert len(bundles) == 2
    first = bundles[0]
    assert first.match.home_team == "England"
    assert first.match.away_team == "Panama"
    assert first.match.status == MatchStatus.FINISHED
    assert first.match.home_score == 2
    assert first.asian_handicaps[0].line == -1.75
    assert first.totals[0].total == 2.5
    assert first.one_x_two[0].home_win_price == 1.30
