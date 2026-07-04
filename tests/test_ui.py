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
