from pathlib import Path
import tomllib

from fastapi.testclient import TestClient

from handicap_ai.ui import create_app


def test_dashboard_route_renders_workspace(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Handicap AI Analyst Workspace" in response.text
    assert "Home team" in response.text
    assert "Away team" in response.text
    assert "BetExplorer" in response.text
    assert "OddsPortal" in response.text


def test_saved_html_analysis_endpoint_returns_recommendations(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/analyze-saved-html",
        json={
            "source": "betexplorer",
            "html_path": "tests/fixtures/betexplorer_match.html",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["match"] == "England vs Panama"
    assert body["coverage"] == "complete"
    assert body["picks"]["handicap"] in {"home", "away", "no_bet"}
    assert body["picks"]["total"] in {"over", "under", "no_bet"}
    assert body["picks"]["1x2"] in {"home", "draw", "away", "no_bet"}


def test_candidate_endpoint_returns_group_fixture(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/world-cup-candidates",
        json={"home_team": "England", "away_team": "Ghana"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_html"
    assert body["candidates"][0]["group_name"] == "L"
    assert body["candidates"][0]["home_team"] == "England"
    assert body["candidates"][0]["away_team"] == "Ghana"


def test_candidate_endpoint_reports_unknown_team(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/world-cup-candidates",
        json={"home_team": "Atlantis", "away_team": "Ghana"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid_team"
    assert body["candidates"] == []
    assert "Unknown team: Atlantis" in body["warnings"]


def test_candidate_analysis_endpoint_accepts_saved_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/analyze-candidate",
        json={
            "source": "betexplorer",
            "html_path": "tests/fixtures/betexplorer_match.html",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["match"] == "England vs Panama"
    assert body["coverage"] == "complete"


def test_dashboard_static_asset_is_served(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/static/dashboard.css")

    assert response.status_code == 200
    assert "control-panel" in response.text


def test_dashboard_assets_are_declared_as_package_data():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["handicap_ai"]

    assert "templates/*.html" in package_data
    assert "static/*.css" in package_data
