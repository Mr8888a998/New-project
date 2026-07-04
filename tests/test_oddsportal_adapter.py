from pathlib import Path

from handicap_ai.adapters.oddsportal import OddsPortalHtmlAdapter


def test_oddsportal_adapter_parses_fixture():
    adapter = OddsPortalHtmlAdapter(Path("tests/fixtures/oddsportal_match.html"))

    bundle, coverage = adapter.load_one()

    assert bundle.match.source_match_id == "op:england-panama"
    assert bundle.match.home_team == "England"
    assert bundle.match.away_team == "Panama"
    assert bundle.one_x_two[-1].home_win_price == 1.30
    assert bundle.asian_handicaps[-1].line == -2.25
    assert bundle.totals[-1].under_price == 1.92
    assert coverage.is_complete is True
