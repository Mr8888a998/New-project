from pathlib import Path
import tomllib

from fastapi.testclient import TestClient

from handicap_ai.database import Database
from handicap_ai.source_discovery import (
    SourceLinkResult,
    SourceLinkStatus,
    register_fixture_source_url,
)
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
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
    assert "Auto analyze" in response.text
    assert 'id="auto-analyze-button"' in response.text
    assert "/api/auto-analyze-candidate" in response.text
    assert "autoAnalyzeButton.disabled" in response.text
    assert "Candidate confirmation" in response.text
    assert "BetExplorer" in response.text
    assert "OddsPortal" in response.text
    assert "Discover sources" in response.text
    assert "Register source URL" in response.text
    assert "Fetch source HTML" in response.text
    assert "Source links" in response.text
    assert "Source readiness" in response.text
    assert "Feature panel" in response.text
    assert "Backtest" in response.text
    assert 'id="source-url"' in response.text
    assert "required" in response.text
    assert "checkValidity()" in response.text
    assert "reportValidity()" in response.text
    assert "setSourceBusy" in response.text
    assert "workspaceRequestId" in response.text
    assert "if (requestId !== workspaceRequestId)" in response.text
    assert response.text.count("const requestId = workspaceRequestId + 1;") >= 4
    assert "findCandidatesButton.disabled" in response.text
    assert "registerSourceUrlButton.disabled" in response.text
    assert "function clearAnalysis()" in response.text
    assert "function clearSourceResult()" in response.text
    assert "clearAnalysis();" in response.text
    assert "clearSourceResult();" in response.text
    assert "function renderMissingSourceResult" in response.text
    assert "candidates: []" in response.text
    assert "cache_dir" not in response.text


def test_dashboard_source_result_does_not_clear_existing_html_path(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'document.querySelector("#html-path").value = body.html_path || "";' not in (
        response.text
    )
    assert "if (body.html_path) {" in response.text
    assert 'document.querySelector("#html-path").value = body.html_path;' in (
        response.text
    )


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
    assert body["features"]["handicap"]["open"] == -1.75
    assert body["scores"]["total"]["pick"] in {"over", "under", "no_bet"}
    assert body["reasons"]["handicap"]


def test_source_status_endpoint_returns_world_cup_readiness(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.get("/api/source-status?source=betexplorer")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "betexplorer"
    assert body["total_fixtures"] == 72
    assert body["by_status"]["pending"] == 72


def test_backtest_endpoint_returns_market_summary(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post("/api/backtest", json={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert set(body["markets"]) == {"handicap", "total", "1x2"}
    assert body["markets"]["handicap"]["picks"] >= 0


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


def test_auto_analyze_candidate_endpoint_uses_cached_html(tmp_path):
    db_path = tmp_path / "handicap.sqlite"
    db = Database(db_path)
    db.migrate()
    import_world_cup_2026_seed(db)
    fixture = db.find_tournament_fixtures(
        FIFA_WORLD_CUP,
        "2026",
        "England",
        "Panama",
    )[0]
    db.upsert_fixture_source_link(
        fixture_id=int(fixture["fixture_id"]),
        source="betexplorer",
        html_path="tests/fixtures/betexplorer_match.html",
        url="https://www.betexplorer.com/england-panama",
        status="available",
    )
    app = create_app(db_path=db_path, cache_dir=tmp_path / "cache")
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "analysis_ready"
    assert body["stage"] == "analyzed"
    assert body["candidate"]["home_team"] == "England"
    assert body["candidate"]["away_team"] == "Panama"
    assert body["source_link"]["status"] == "available"
    assert body["analysis"]["match"] == "England vs Panama"
    assert body["analysis"]["picks"]["handicap"] in {"home", "away", "no_bet"}
    assert body["analysis"]["picks"]["total"] in {"over", "under", "no_bet"}
    assert body["analysis"]["picks"]["1x2"] in {"home", "draw", "away", "no_bet"}


def test_auto_analyze_candidate_endpoint_can_discover_and_fetch(tmp_path):
    html = Path("tests/fixtures/betexplorer_match.html").read_text(encoding="utf-8")

    def discovery_runner(db, home_team, away_team, source):
        return register_fixture_source_url(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            url="https://www.betexplorer.com/england-panama",
        )

    def fetch_runner(db, home_team, away_team, source, cache_dir):
        def http_get(url: str) -> FetchHttpResponse:
            return FetchHttpResponse(url=url, status_code=200, text=html)

        return fetch_fixture_source_html(
            db,
            home_team=home_team,
            away_team=away_team,
            source=source,
            cache_dir=cache_dir,
            http_get=http_get,
        )

    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
        auto_discovery_runner=discovery_runner,
        auto_fetch_runner=fetch_runner,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "analysis_ready"
    assert body["source_link"]["status"] == "available"
    assert Path(body["source_link"]["html_path"]).is_file()
    assert body["analysis"]["coverage"] == "complete"


def test_auto_analyze_candidate_endpoint_returns_manual_state(tmp_path):
    def discovery_runner(db, home_team, away_team, source):
        fixture = db.find_tournament_fixtures(
            FIFA_WORLD_CUP,
            "2026",
            "England",
            "Panama",
        )[0]
        return SourceLinkResult(
            status=SourceLinkStatus.MANUAL_REQUIRED,
            fixture_id=int(fixture["fixture_id"]),
            source=source,
            html_path=None,
            url=None,
            warnings=("No source URL found for England vs Panama",),
        )

    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
        auto_discovery_runner=discovery_runner,
    )
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_manual_source"
    assert body["stage"] == "manual_required"
    assert body["analysis"] is None
    assert "No source URL found for England vs Panama" in body["warnings"]


def test_auto_analyze_candidate_endpoint_rejects_unsupported_source(tmp_path):
    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)

    response = client.post(
        "/api/auto-analyze-candidate",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "unknown",
        },
    )

    assert response.status_code == 400
    assert "unsupported source" in response.json()["detail"]


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
            "url": "https://www.betexplorer.com/england-ghana",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "betexplorer"
    assert body["status"] == "pending"
    assert body["url"] == "https://www.betexplorer.com/england-ghana"
    assert body["html_path"] is None
    assert body["warnings"] == []


def test_register_source_url_endpoint_reports_unknown_team(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/register-source-url",
        json={
            "home_team": "Atlantis",
            "away_team": "Ghana",
            "source": "betexplorer",
            "url": "https://www.betexplorer.com/atlantis-ghana",
        },
    )

    assert response.status_code == 400
    assert "Unknown team" in response.json()["detail"]


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


def test_discover_sources_endpoint_reports_unsupported_source(tmp_path):
    app = create_app(db_path=tmp_path / "handicap.sqlite")
    client = TestClient(app)

    response = client.post(
        "/api/discover-sources",
        json={
            "home_team": "England",
            "away_team": "Ghana",
            "source": "unknown",
        },
    )

    assert response.status_code == 400
    assert "unsupported source" in response.json()["detail"]


def test_fetch_source_html_endpoint_uses_response_html(tmp_path):
    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)
    client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "url": "https://www.betexplorer.com/england-panama",
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
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert Path(body["html_path"]).is_file()


def test_fetch_source_html_endpoint_ignores_request_cache_dir(tmp_path):
    server_cache_dir = tmp_path / "cache"
    request_cache_dir = tmp_path / "outside"
    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=server_cache_dir,
    )
    client = TestClient(app)
    client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "url": "https://www.betexplorer.com/england-panama",
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
            "cache_dir": str(request_cache_dir),
        },
    )

    assert response.status_code == 200
    html_path = Path(response.json()["html_path"]).resolve()
    assert html_path.is_file()
    assert html_path.is_relative_to(server_cache_dir.resolve())
    assert not html_path.is_relative_to(request_cache_dir.resolve())


def test_fetch_source_html_endpoint_returns_failed_result_on_cache_write_error(
    tmp_path,
):
    cache_file = tmp_path / "cache-file"
    cache_file.write_text("not a directory", encoding="utf-8")
    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=cache_file,
    )
    client = TestClient(app)
    client.post(
        "/api/register-source-url",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "url": "https://www.betexplorer.com/england-panama",
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
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["html_path"] is None
    assert "cache write failed" in body["warnings"][0]


def test_fetch_source_html_endpoint_requires_registered_url(tmp_path):
    app = create_app(
        db_path=tmp_path / "handicap.sqlite",
        cache_dir=tmp_path / "cache",
    )
    client = TestClient(app)

    response = client.post(
        "/api/fetch-source-html",
        json={
            "home_team": "England",
            "away_team": "Panama",
            "source": "betexplorer",
            "response_html": "<html></html>",
        },
    )

    assert response.status_code == 400
    assert "no registered URL" in response.json()["detail"]
