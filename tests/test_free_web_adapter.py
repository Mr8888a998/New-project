from pathlib import Path

from handicap_ai.adapters.free_web import FreeWebHtmlAdapter


def test_free_web_html_adapter_parses_fixture():
    adapter = FreeWebHtmlAdapter(
        source_name="fixture-web",
        html_path=Path("tests/fixtures/free_web_match.html"),
    )

    bundles = adapter.load()

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.match.home_team == "England"
    assert bundle.match.away_team == "Panama"
    assert bundle.asian_handicaps[0].is_opening is True
    assert bundle.asian_handicaps[1].is_closing is True
    assert bundle.totals[1].total == 3.25
    assert bundle.one_x_two[0].draw_price == 5.00
