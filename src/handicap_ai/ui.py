from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from handicap_ai.candidate_search import FixtureCandidate, find_world_cup_candidates
from handicap_ai.database import Database
from handicap_ai.live_analysis import LiveAnalysisResult, analyze_saved_html
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


def create_app(db_path: Path) -> FastAPI:
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

    return app
