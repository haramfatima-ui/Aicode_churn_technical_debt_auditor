"""
Analyzes source files for complexity and explicit debt markers.

- Python files get real cyclomatic complexity + maintainability index via `radon`.
- All text files (any language) get scanned for TODO/FIXME/HACK/deprecated
  markers and overly long lines, which are cheap, language-agnostic debt signals.
"""
from __future__ import annotations

import os
import re

from radon.complexity import cc_visit
from radon.metrics import mi_visit

from models import ComplexityMetric, DebtMarkers


IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", ".nuxt", "target", ".mypy_cache", ".pytest_cache", "coverage",
}


IGNORED_EXTENSIONS = {".pyc", ".pyo", ".pyd"}


SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".rs", ".c",
    ".cpp", ".h", ".hpp", ".cs", ".php", ".swift", ".kt", ".scala", ".vue",
}

MARKER_PATTERN = re.compile(
    r"\b(TODO|FIXME|HACK|XXX|DEPRECATED)\b", re.IGNORECASE
)
LONG_LINE_THRESHOLD = 120


def discover_source_files(repo_path: str, max_files: int) -> list[str]:
    found: list[str] = []
    for root, dirs, files in os.walk(repo_path):
        # Skip ignored directories and hidden folders
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in files:
            _, ext = os.path.splitext(name)
            # Skip ignored binary/compiled extensions
            if ext.lower() in IGNORED_EXTENSIONS:
                continue
                
            if ext.lower() in SOURCE_EXTENSIONS:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, repo_path)
                
                # Double-check that relative path doesn't contain hidden/cache dirs
                parts = rel.split(os.sep)
                if any(p in IGNORED_DIRS or p.startswith(".") for p in parts[:-1]):
                    continue

                found.append(rel)
                if len(found) >= max_files:
                    return found
    return found


def analyze_python_complexity(repo_path: str, rel_path: str) -> ComplexityMetric:
    full_path = os.path.join(repo_path, rel_path)
    try:
        with open(full_path, encoding="utf-8", errors="ignore") as fh:
            source = fh.read()
    except OSError:
        return ComplexityMetric(path=rel_path)

    loc = source.count("\n") + 1
    try:
        blocks = cc_visit(source)
        avg_cc = sum(b.complexity for b in blocks) / len(blocks) if blocks else 0.0
    except SyntaxError:
        avg_cc = 0.0
        blocks = []

    try:
        mi = mi_visit(source, multi=True)
    except SyntaxError:
        mi = None

    return ComplexityMetric(
        path=rel_path,
        cyclomatic_complexity=round(avg_cc, 2),
        maintainability_index=round(mi, 2) if mi is not None else None,
        loc=loc,
        functions_analyzed=len(blocks),
    )


def analyze_generic_complexity(repo_path: str, rel_path: str) -> ComplexityMetric:
    """
    Lightweight, language-agnostic proxy for complexity when radon can't help:
    longer files with deeper nesting tend to be riskier. Not a substitute for
    a real static analyzer, but useful signal at zero dependency cost.
    """
    full_path = os.path.join(repo_path, rel_path)
    try:
        with open(full_path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError:
        return ComplexityMetric(path=rel_path)

    loc = len(lines)
    max_indent = 0
    for line in lines:
        stripped = line.lstrip(" \t")
        indent = len(line) - len(stripped)
        max_indent = max(max_indent, indent)

   
    proxy_score = round((max_indent / 4) + (loc / 50), 2)

    return ComplexityMetric(
        path=rel_path,
        cyclomatic_complexity=proxy_score,
        maintainability_index=None,
        loc=loc,
        functions_analyzed=0,
    )


def analyze_complexity(repo_path: str, rel_path: str) -> ComplexityMetric:
    if rel_path.endswith(".py"):
        return analyze_python_complexity(repo_path, rel_path)
    return analyze_generic_complexity(repo_path, rel_path)


def analyze_markers(repo_path: str, rel_path: str) -> DebtMarkers:
    full_path = os.path.join(repo_path, rel_path)
    counts = {"TODO": 0, "FIXME": 0, "HACK": 0, "DEPRECATED": 0}
    long_lines = 0

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if len(line) > LONG_LINE_THRESHOLD:
                    long_lines += 1
                for match in MARKER_PATTERN.findall(line):
                    key = match.upper()
                    if key == "XXX":
                        key = "HACK"
                    if key in counts:
                        counts[key] += 1
    except OSError:
        pass

    return DebtMarkers(
        path=rel_path,
        todo_count=counts["TODO"],
        fixme_count=counts["FIXME"],
        hack_count=counts["HACK"],
        deprecated_count=counts["DEPRECATED"],
        long_lines=long_lines,
    )