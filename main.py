from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from ai_insights import generate_ai_summary
from complexity_analyzer import analyze_complexity, analyze_markers, discover_source_files
from config import get_settings
from git_analyzer import GitAnalyzerError, compute_churn
from models import AnalysisReport, AnalyzeRequest
from risk_scorer import score_files

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debt_auditor")

app = FastAPI(title="AI Code Churn & Technical Debt Auditor")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_last_report: AnalysisReport | None = None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serves the main dashboard instantly without any login requirements."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            content = f.read()

        settings = get_settings()
        default_path = settings.default_repo_path or "."

        content = content.replace("{{ default_repo_path }}", default_path)
        content = content.replace("{% if not has_ai_key %}", "")
        content = content.replace("{% endif %}", "")

        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Backend Loading Error</h1><p>{str(e)}</p>", status_code=500)


@app.post("/api/analyze", response_model=AnalysisReport)
def analyze(req: AnalyzeRequest) -> AnalysisReport:
    global _last_report
    settings = get_settings()
    lookback = req.lookback_commits or settings.churn_lookback_commits

    try:
        churn_by_path = compute_churn(req.repo_path, lookback)
    except GitAnalyzerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        source_files = discover_source_files(req.repo_path, settings.max_files_per_scan)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read repo path: {exc}") from exc

    complexity_by_path = {}
    markers_by_path = {}
    for rel_path in source_files:
        complexity_by_path[rel_path] = analyze_complexity(req.repo_path, rel_path)
        markers_by_path[rel_path] = analyze_markers(req.repo_path, rel_path)

    ranked = score_files(churn_by_path, complexity_by_path, markers_by_path, settings)

    ai_summary = None
    ai_summary_error = None
    if req.include_ai_summary:
        # Tries Groq first, then Anthropic, then a local zero-dependency
        # fallback - whichever key(s) are configured in .env.
        ai_summary, ai_summary_error = generate_ai_summary(
            ranked,
            req.repo_path,
            groq_key=settings.groq_api_key,
            anthropic_key=settings.anthropic_api_key,
        )

    report = AnalysisReport(
        repo_path=req.repo_path,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_files_scanned=len(source_files),
        files=ranked,
        ai_summary=ai_summary,
        ai_summary_error=ai_summary_error,
    )
    _last_report = report
    return report


@app.get("/api/report", response_model=AnalysisReport)
def get_last_report() -> AnalysisReport:
    if _last_report is None:
        raise HTTPException(status_code=404, detail="No report has been generated yet.")
    return _last_report
