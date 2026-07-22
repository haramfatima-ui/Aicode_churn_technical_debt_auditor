"""
Analyzes git history to compute "churn" per file: how often it changes,
how many people touch it, and how recently it was modified. Files with
high churn are more likely to accumulate risk, especially when combined
with high complexity.
"""
from __future__ import annotations

import subprocess
from collections import defaultdict
from datetime import datetime, timezone

from models import ChurnMetric


class GitAnalyzerError(RuntimeError):
    """Raised when the target path isn't a usable git repository."""


def _run_git(repo_path: str, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return result.stdout
    except FileNotFoundError as exc:
        raise GitAnalyzerError("git is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GitAnalyzerError(f"git command failed: {exc.stderr.strip() or exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitAnalyzerError("git command timed out") from exc


def verify_git_repo(repo_path: str) -> None:
    _run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])


def compute_churn(repo_path: str, lookback_commits: int = 1000) -> dict[str, ChurnMetric]:
    """
    Returns a dict of {file_path: ChurnMetric} built from `git log --numstat`.
    Uses a bounded lookback so huge repos stay responsive.
    """
    verify_git_repo(repo_path)

    log_output = _run_git(
        repo_path,
        [
            "log",
            f"-n{lookback_commits}",
            "--no-merges",
            "--pretty=format:__COMMIT__%H|%an|%at",
            "--numstat",
        ],
    )

    commit_count: dict[str, int] = defaultdict(int)
    authors: dict[str, set[str]] = defaultdict(set)
    lines_added: dict[str, int] = defaultdict(int)
    lines_removed: dict[str, int] = defaultdict(int)
    last_seen_ts: dict[str, int] = {}

    current_author = ""
    current_ts = 0

    for line in log_output.splitlines():
        if line.startswith("__COMMIT__"):
            _, meta = line.split("__COMMIT__", 1)
            _sha, author, ts = meta.split("|")
            current_author = author
            current_ts = int(ts)
            continue
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_str, removed_str, path = parts
        
        if " => " in path:
            path = path.split(" => ")[-1].strip("{}")

        added = int(added_str) if added_str.isdigit() else 0
        removed = int(removed_str) if removed_str.isdigit() else 0

        commit_count[path] += 1
        authors[path].add(current_author)
        lines_added[path] += added
        lines_removed[path] += removed
        last_seen_ts[path] = max(last_seen_ts.get(path, 0), current_ts)

    now = datetime.now(timezone.utc).timestamp()
    metrics: dict[str, ChurnMetric] = {}
    for path in commit_count:
        days_ago = int((now - last_seen_ts[path]) / 86400) if path in last_seen_ts else None
        metrics[path] = ChurnMetric(
            path=path,
            commit_count=commit_count[path],
            authors=len(authors[path]),
            lines_added=lines_added[path],
            lines_removed=lines_removed[path],
            last_modified_days_ago=days_ago,
        )
    return metrics