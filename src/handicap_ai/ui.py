from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from handicap_ai.auto_analysis import (
    AutoAnalyzeResult,
    DiscoveryRunner,
    FetchRunner,
    auto_analyze_candidate,
)
from handicap_ai.candidate_search import FixtureCandidate, find_world_cup_candidates
from handicap_ai.database import Database
from handicap_ai.live_analysis import LiveAnalysisResult, analyze_saved_html
from handicap_ai.source_discovery import (
    SourceLinkResult,
    discover_fixture_source,
    discover_fixture_source_from_listing,
    register_fixture_source_url,
)
from handicap_ai.source_fetch import FetchHttpResponse, fetch_fixture_source_html
from handicap_ai.world_cup_seed import import_world_cup_2026_seed


PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


class SavedHtmlAnalysisRequest(BaseModel):
    source: str
    html_path: str


class CandidateSearchRequest(BaseModel):
    home_team: str
    away_team: str


class CandidateAnalysisRequest(BaseModel):
    source: str
    html_path: str


class SourceUrlRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
    url: str


class SourceDiscoveryRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
    listing_html: str | None = None
    base_url: str | None = None


class SourceFetchRequest(BaseModel):
    home_team: str
    away_team: str
    source: str
    response_html: str | None = None


class AutoAnalyzeRequest(BaseModel):
    home_team: str
    away_team: str
    source: str


def _report_payload(result: LiveAnalysisResult) -> dict[str, object]:
    return {
        "match": f"{result.match['home_team']} vs {result.match['away_team']}",
        "coverage": "complete" if result.coverage.is_complete else "incomplete",
        "missing_markets": list(result.coverage.missing_markets),
        "risk_tags": list(result.report.risk_tags),
        "picks": {
            "handicap": result.report.handicap.pick.value,
            "total": result.report.total.pick.value,
            "1x2": result.report.one_x_two.pick.value,
        },
        "confidence": {
            "handicap": result.report.handicap.confidence,
            "total": result.report.total.confidence,
            "1x2": result.report.one_x_two.confidence,
        },
        "data_quality": result.report.data_quality_score,
    }


def _candidate_payload(candidate: FixtureCandidate) -> dict[str, object]:
    return {
        "fixture_id": candidate.fixture_id,
        "group_name": candidate.group_name,
        "home_team": candidate.home_team,
        "away_team": candidate.away_team,
        "kickoff_time": candidate.kickoff_time,
        "status": candidate.status,
        "sources": {
            source: {
                "source": link.source,
                "status": link.status,
                "html_path": link.html_path,
                "url": link.url,
            }
            for source, link in candidate.sources.items()
        },
    }


def _source_link_payload(result: SourceLinkResult) -> dict[str, object]:
    return {
        "fixture_id": result.fixture_id,
        "source": result.source,
        "status": result.status.value,
        "url": result.url,
        "html_path": result.html_path,
        "warnings": list(result.warnings),
    }


def _auto_analyze_payload(result: AutoAnalyzeResult) -> dict[str, object]:
    return {
        "status": result.status.value,
        "stage": result.stage,
        "warnings": list(result.warnings),
        "candidate": (
            _candidate_payload(result.candidate)
            if result.candidate is not None
            else None
        ),
        "source_link": (
            _source_link_payload(result.source_link)
            if result.source_link is not None
            else None
        ),
        "analysis": (
            _report_payload(result.analysis) if result.analysis is not None else None
        ),
    }


def create_app(
    db_path: Path,
    cache_dir: Path = Path("data/cache"),
    auto_discovery_runner: DiscoveryRunner | None = None,
    auto_fetch_runner: FetchRunner | None = None,
) -> FastAPI:
    app = FastAPI(title="Handicap AI")
    database = Database(db_path)
    database.migrate()
    import_world_cup_2026_seed(database, overwrite_existing=False)
    static_dir = PACKAGE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "dashboard.html",
            {
                "title": "Handicap AI Analyst Workspace",
            },
        )

    @app.post("/api/analyze-saved-html")
    def analyze_saved_html_endpoint(payload: SavedHtmlAnalysisRequest):
        result = analyze_saved_html(
            db=database,
            source=payload.source,
            html_path=Path(payload.html_path),
        )
        return _report_payload(result)

    @app.post("/api/world-cup-candidates")
    def world_cup_candidates_endpoint(payload: CandidateSearchRequest):
        result = find_world_cup_candidates(
            database,
            home_team=payload.home_team,
            away_team=payload.away_team,
        )
        return {
            "status": result.status.value,
            "warnings": list(result.warnings),
            "candidates": [
                _candidate_payload(candidate) for candidate in result.candidates
            ],
        }

    @app.post("/api/analyze-candidate")
    def analyze_candidate_endpoint(payload: CandidateAnalysisRequest):
        result = analyze_saved_html(
            db=database,
            source=payload.source,
            html_path=Path(payload.html_path),
        )
        return _report_payload(result)

    @app.post("/api/register-source-url")
    def register_source_url_endpoint(payload: SourceUrlRequest):
        try:
            result = register_fixture_source_url(
                database,
                home_team=payload.home_team,
                away_team=payload.away_team,
                source=payload.source,
                url=payload.url,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _source_link_payload(result)

    @app.post("/api/discover-sources")
    def discover_sources_endpoint(payload: SourceDiscoveryRequest):
        try:
            if payload.listing_html is not None:
                if not payload.base_url:
                    raise HTTPException(
                        status_code=400,
                        detail="base_url is required when listing_html is provided",
                    )
                result = discover_fixture_source_from_listing(
                    database,
                    home_team=payload.home_team,
                    away_team=payload.away_team,
                    source=payload.source,
                    listing_html=payload.listing_html,
                    base_url=payload.base_url,
                )
            else:
                result = discover_fixture_source(
                    database,
                    home_team=payload.home_team,
                    away_team=payload.away_team,
                    source=payload.source,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _source_link_payload(result)

    @app.post("/api/fetch-source-html")
    def fetch_source_html_endpoint(payload: SourceFetchRequest):
        try:
            if payload.response_html is not None:
                def http_get(url: str) -> FetchHttpResponse:
                    return FetchHttpResponse(
                        url=url,
                        status_code=200,
                        text=payload.response_html or "",
                    )

                result = fetch_fixture_source_html(
                    database,
                    home_team=payload.home_team,
                    away_team=payload.away_team,
                    source=payload.source,
                    cache_dir=cache_dir,
                    http_get=http_get,
                )
            else:
                result = fetch_fixture_source_html(
                    database,
                    home_team=payload.home_team,
                    away_team=payload.away_team,
                    source=payload.source,
                    cache_dir=cache_dir,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _source_link_payload(result)

    @app.post("/api/auto-analyze-candidate")
    def auto_analyze_candidate_endpoint(payload: AutoAnalyzeRequest):
        try:
            result = auto_analyze_candidate(
                database,
                home_team=payload.home_team,
                away_team=payload.away_team,
                source=payload.source,
                cache_dir=cache_dir,
                discovery_runner=auto_discovery_runner,
                fetch_runner=auto_fetch_runner,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _auto_analyze_payload(result)

    return app
