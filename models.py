"""
Pydantic schemas used across the analyzer, API, and dashboard.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChurnMetric(BaseModel):
    path: str
    commit_count: int = 0
    authors: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    last_modified_days_ago: int | None = None


class ComplexityMetric(BaseModel):
    path: str
    cyclomatic_complexity: float = 0.0
    maintainability_index: float | None = None  # 0-100, higher = healthier
    loc: int = 0
    functions_analyzed: int = 0


class DebtMarkers(BaseModel):
    path: str
    todo_count: int = 0
    fixme_count: int = 0
    hack_count: int = 0
    deprecated_count: int = 0
    long_lines: int = 0


class FileRisk(BaseModel):
    path: str
    churn_score: float = 0.0
    complexity_score: float = 0.0
    marker_score: float = 0.0
    risk_score: float = Field(default=0.0, description="0-100 weighted composite risk score")
    risk_band: str = "low"  # low | medium | high | critical
    churn: ChurnMetric | None = None
    complexity: ComplexityMetric | None = None
    markers: DebtMarkers | None = None


class AnalysisReport(BaseModel):
    repo_path: str
    generated_at: str
    total_files_scanned: int
    files: list[FileRisk]
    ai_summary: str | None = None
    ai_summary_error: str | None = None


class AnalyzeRequest(BaseModel):
    repo_path: str
    lookback_commits: int | None = None
    include_ai_summary: bool = True