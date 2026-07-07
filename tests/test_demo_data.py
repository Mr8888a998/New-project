from pathlib import Path

from handicap_ai.database import Database
from handicap_ai.demo_data import prepare_demo_data


def test_prepare_demo_data_seeds_history_and_available_html(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")
    cache_html = tmp_path / "england-panama.html"
    cache_html.write_text(
        Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = prepare_demo_data(
        db,
        football_data_csv=Path("tests/fixtures/football_data_sample.csv"),
        history_folder=Path("tests/fixtures/history_folder"),
        cached_html_path=cache_html,
    )

    assert summary.world_cup_fixtures == 72
    assert summary.finished_matches >= 2
    assert summary.source_registered is True
    assert summary.available_html == 1
    assert summary.to_dict()["source"] == "betexplorer"


def test_prepare_demo_data_reports_missing_optional_inputs(tmp_path):
    db = Database(tmp_path / "handicap.sqlite")

    summary = prepare_demo_data(
        db,
        football_data_csv=tmp_path / "missing.csv",
        history_folder=tmp_path / "missing-folder",
        cached_html_path=tmp_path / "missing.html",
    )

    assert summary.world_cup_fixtures == 72
    assert summary.finished_matches == 0
    assert summary.source_registered is False
    assert any("football data CSV missing" in warning for warning in summary.warnings)
    assert any("cached HTML missing" in warning for warning in summary.warnings)
