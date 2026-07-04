from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from handicap_ai.database import Database
from handicap_ai.live_analysis import analyze_saved_html


PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


class SavedHtmlAnalysisRequest(BaseModel):
    source: str
    html_path: str


def create_app(db_path: Path) -> FastAPI:
    app = FastAPI(title="Handicap AI")
    database = Database(db_path)
    database.migrate()
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

    return app
