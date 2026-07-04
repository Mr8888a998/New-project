from pathlib import Path

from handicap_ai.adapters.betexplorer import BetExplorerHtmlAdapter


def test_betexplorer_adapter_parses_all_markets():
    adapter = BetExplorerHtmlAdapter(Path("tests/fixtures/betexplorer_match.html"))

    bundle, coverage = adapter.load_one()

    assert bundle.match.source_match_id == "be:england-panama"
    assert bundle.match.home_team == "England"
    assert bundle.match.away_team == "Panama"
    assert len(bundle.one_x_two) == 2
    assert len(bundle.asian_handicaps) == 2
    assert len(bundle.totals) == 2
    assert bundle.asian_handicaps[-1].line == -2.25
    assert bundle.totals[-1].total == 3.25
    assert coverage.is_complete is True


def test_betexplorer_adapter_reports_missing_market():
    adapter = BetExplorerHtmlAdapter(
        Path("tests/fixtures/betexplorer_missing_market.html")
    )

    bundle, coverage = adapter.load_one()

    assert bundle.match.source_match_id == "be:england-panama-missing"
    assert coverage.is_complete is False
    assert coverage.missing_markets == ("totals",)
    assert "scrape_market_missing" in coverage.risk_tags
