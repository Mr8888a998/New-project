from pathlib import Path
import tomllib

from fastapi.testclient import TestClient

from handicap_ai.database import Database
from handicap_ai.ui import create_app
from handicap_ai.world_cup_seed import FIFA_WORLD_CUP, import_world_cup_2026_seed


def test_dashboard_route_renders_workspace(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Handicap AI Analyst Workspace" in response.text
    assert "Home team" in response.text
    assert "Away team" in response.text
    assert "Find candidates" in response.text
    assert "Candidate confirmation" in response.text
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


def test_create_app_preserves_enriched_seed_fixture_metadata(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    db = Database(db_path)
    db.migrate()
    import_world_cup_2026_seed(db)
    db.upsert_tournament_fixture(
        tournament=FIFA_WORLD_CUP,
        season="2026",
        group_name="L",
        home_team="England",
        away_team="Ghana",
        kickoff_time="2026-06-20T12:00:00Z",
        status="confirmed",
    )

    create_app(db_path=db_path)

    england_ghana = db.find_tournament_fixtures(
        tournament=FIFA_WORLD_CUP,
        season="2026",
        home_team="England",
        away_team="Ghana",
    )
    assert england_ghana[0]["kickoff_time"] == "2026-06-20T12:00:00Z"
    assert england_ghana[0]["status"] == "confirmed"


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


def test_register_source_url_endpoint_updates_candidate(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Ghana",
            "source": "betexplorer",
            "url": "https://example.test/england-ghana",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "betexplorer"
    assert body["status"] == "pending"
    assert body["url"] == "https://example.test/england-ghana"


def test_discover_sources_endpoint_uses_listing_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)
    html = Path("tests/fixtures/source_listing_betexplorer.html").read_text(
        encoding="utf-8"
    )

    response = client.post(
        "/api/discover-sources",
        json={
            "home_team": "England",
            "away_team": "Ghana",
            "source": "betexplorer",
            "listing_html": html,
            "base_url": "https://www.betexplorer.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert "england-ghana/KhgvzGjJ/" in body["url"]


def test_discover_sources_endpoint_requires_base_url_with_listing_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/discover-sources",
        json={
            "home_team": "England",
            "away_team": "Ghana",
            "source": "betexplorer",
            "listing_html": "<a href='/match/england-ghana'>England - Ghana</a>",
        },
    )

    assert response.status_code == 400
    assert "base_url" in response.json()["detail"]


def test_fetch_source_html_endpoint_uses_response_html(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)
    client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "url": "https://example.test/england-panama",
        },
    )
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    response = client.post(
        "/api/fetch-source-html",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "response_html": html,
            "cache_dir": str(tmp_path / "cache"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert Path(body["html_path"]).is_file()


def test_fetch_source_html_endpoint_requires_registered_url(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/fetch-source-html",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "response_html": "<html></html>",
            "cache_dir": str(tmp_path / "cache"),
        },
    )

    assert response.status_code == 400
    assert "no registered URL" in response.json()["detail"]
