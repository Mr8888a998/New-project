from pathlib import Path

import pytest

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


def test_football_data_adapter_prefers_closing_alias_columns(tmp_path):
    csv_path = tmp_path / "aliases.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,AHh,AHCh,"
                "B365AHH,B365AHA,B365CAHH,B365CAHA,"
                "BbAv>2.5,BbAv<2.5,Avg>2.5,Avg<2.5,"
                "B365H,B365D,B365A,B365CH,B365CD,B365CA",
                "INT,2026-01-03,France,Japan,1,1,-1.75,-2.25,"
                "1.95,1.90,1.77,2.10,"
                "2.05,1.80,1.91,1.99,"
                "1.30,5.00,9.00,1.25,5.30,10.00",
            ]
        ),
        encoding="utf-8",
    )

    bundle = FootballDataCsvAdapter(csv_path, season="2026").load()[0]

    assert bundle.asian_handicaps[0].line == -2.25
    assert bundle.asian_handicaps[0].home_price == 1.77
    assert bundle.asian_handicaps[0].away_price == 2.10
    assert bundle.totals[0].over_price == 1.91
    assert bundle.totals[0].under_price == 1.99
    assert bundle.one_x_two[0].home_win_price == 1.25
    assert bundle.one_x_two[0].draw_price == 5.30
    assert bundle.one_x_two[0].away_win_price == 10.00


def test_football_data_adapter_rejects_blank_home_team(tmp_path):
    csv_path = tmp_path / "blank_home.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG",
                "INT,01/01/26, ,Panama,2,0",
            ]
        ),
        encoding="utf-8",
    )

    adapter = FootballDataCsvAdapter(csv_path, season="2026")

    with pytest.raises(ValueError, match=r"row 2.*HomeTeam"):
        adapter.load()


def test_football_data_adapter_rejects_unparseable_date(tmp_path):
    csv_path = tmp_path / "bad_date.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG",
                "INT,not-a-date,England,Panama,2,0",
            ]
        ),
        encoding="utf-8",
    )

    adapter = FootballDataCsvAdapter(csv_path, season="2026")

    with pytest.raises(ValueError, match=r"row 2.*Date.*not-a-date"):
        adapter.load()


def test_football_data_adapter_rejects_missing_required_header(tmp_path):
    csv_path = tmp_path / "missing_date_header.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Div,HomeTeam,AwayTeam,FTHG,FTAG",
                "INT,England,Panama,2,0",
            ]
        ),
        encoding="utf-8",
    )

    adapter = FootballDataCsvAdapter(csv_path, season="2026")

    with pytest.raises(ValueError, match=r"missing required header.*Date"):
        adapter.load()
