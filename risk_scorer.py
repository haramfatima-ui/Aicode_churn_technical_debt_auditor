"""
Combines churn + complexity + debt markers into one 0-100 risk score per file.

The core idea: a file that changes constantly (high churn) AND is hard to
reason about (high complexity) is the classic "hot spot" that produces bugs
and slows teams down. A file with debt markers (TODO/FIXME/HACK) on top of
that is flagged even higher.
"""
from __future__ import annotations

from config import Settings
from models import ChurnMetric, ComplexityMetric, DebtMarkers, FileRisk


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return min(value / max_value, 1.0)


def score_files(
    churn_by_path: dict[str, ChurnMetric],
    complexity_by_path: dict[str, ComplexityMetric],
    markers_by_path: dict[str, DebtMarkers],
    settings: Settings,
) -> list[FileRisk]:
    all_paths = set(churn_by_path) | set(complexity_by_path) | set(markers_by_path)
    if not all_paths:
        return []

    max_commits = max((m.commit_count for m in churn_by_path.values()), default=1) or 1
    max_complexity = max(
        (m.cyclomatic_complexity for m in complexity_by_path.values()), default=1
    ) or 1

    results: list[FileRisk] = []
    for path in all_paths:
        churn = churn_by_path.get(path)
        complexity = complexity_by_path.get(path)
        markers = markers_by_path.get(path)

        churn_score = _normalize(churn.commit_count, max_commits) * 100 if churn else 0.0
        complexity_score = (
            _normalize(complexity.cyclomatic_complexity, max_complexity) * 100
            if complexity
            else 0.0
        )
        marker_hits = 0
        if markers:
            marker_hits = (
                markers.todo_count
                + markers.fixme_count * 2  # FIXME implies a known bug, weight it higher
                + markers.hack_count * 2
                + markers.deprecated_count
            )
        marker_score = min(marker_hits * 8, 100)  # cap so a few markers don't dominate

        risk_score = (
            churn_score * settings.weight_churn
            + complexity_score * settings.weight_complexity
            + marker_score * settings.weight_markers
        )
        risk_score = round(min(risk_score, 100), 1)

        if risk_score >= 75:
            band = "critical"
        elif risk_score >= 50:
            band = "high"
        elif risk_score >= 25:
            band = "medium"
        else:
            band = "low"

        results.append(
            FileRisk(
                path=path,
                churn_score=round(churn_score, 1),
                complexity_score=round(complexity_score, 1),
                marker_score=round(marker_score, 1),
                risk_score=risk_score,
                risk_band=band,
                churn=churn,
                complexity=complexity,
                markers=markers,
            )
        )

    results.sort(key=lambda f: f.risk_score, reverse=True)
    return results