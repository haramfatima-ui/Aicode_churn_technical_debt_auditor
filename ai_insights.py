"""
Turns the raw metrics for the top-risk files into a short, readable narrative.

Tries providers in order: Groq (free, fast) -> Anthropic (Claude) -> local
rule-based fallback. The app stays fully useful even with zero API keys
configured, since the local fallback never fails and never needs a network
call.
"""
from __future__ import annotations

import httpx

from models import FileRisk

MAX_FILES_IN_PROMPT = 12


def _build_prompt(repo_path: str, top_files: list[FileRisk]) -> str:
    """Formats risk metrics into a clean prompt string."""
    lines = [
        f"You are auditing the git repository at '{repo_path}' for code health.",
        "Below are the highest-risk files ranked by churn, complexity, and debt markers:",
        "",
    ]
    for f in top_files:
        churn_desc = f"{f.churn.commit_count} commits, {f.churn.authors} authors" if f.churn else "no churn"
        complexity_desc = f"complexity {f.complexity.cyclomatic_complexity}, {f.complexity.loc} LOC" if f.complexity else "no complexity data"
        marker_desc = f"{f.markers.todo_count} TODOs, {f.markers.fixme_count} FIXMEs" if f.markers else "no markers"
        lines.append(f"- {f.path} | risk {f.risk_score}/100 ({f.risk_band}) | {churn_desc} | {complexity_desc} | {marker_desc}")

    lines += [
        "",
        "Write a concise, actionable 3-bullet summary for an engineering manager covering:",
        "1. Top high-risk technical debt hot spots.",
        "2. Churn risks or visible patterns.",
        "3. Clear refactoring priorities.",
        "Be specific and reference actual file paths.",
    ]
    return "\n".join(lines)


def _try_groq(groq_key: str, prompt: str) -> tuple[str | None, str | None]:
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 600,
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
        if response.status_code == 200:
            text = response.json()["choices"][0]["message"]["content"].strip()
            return text, None
        return None, f"Groq API Error ({response.status_code}): {response.text[:300]}"
    except Exception as e:  # noqa: BLE001 - never crash the scan over an optional summary
        return None, f"Groq Connection Error: {str(e)}"


def _try_anthropic(anthropic_key: str, prompt: str) -> tuple[str | None, str | None]:
    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
        if response.status_code == 200:
            text = response.json()["content"][0]["text"].strip()
            return text, None
        return None, f"Anthropic API Error ({response.status_code}): {response.text[:300]}"
    except Exception as e:  # noqa: BLE001
        return None, f"Anthropic Connection Error: {str(e)}"


def _local_fallback(repo_path: str, top_files: list[FileRisk]) -> str:
    if not top_files:
        return (
            f"Scan of '{repo_path}' complete - no elevated-risk files were found.\n\n"
            "- Every scanned file came back with a risk score of 0, meaning low churn, "
            "low complexity, and no TODO/FIXME/HACK markers were detected.\n"
            "- No refactoring priorities to flag right now - the codebase looks healthy."
        )

    highest_file = top_files[0]
    return (
        f"Smart Local Summary for '{repo_path}':\n\n"
        f"- Highest technical debt: top volatile file is {highest_file.path} "
        f"with a risk score of {highest_file.risk_score}/100 ({highest_file.risk_band}).\n"
        f"- Code churn & complexity: high activity and markers detected across "
        f"top {len(top_files)} files.\n"
        f"- Refactoring priority: start with {highest_file.path} to reduce volatility."
    )


def generate_ai_summary(
    ranked_files: list[FileRisk],
    repo_path: str,
    groq_key: str | None = None,
    anthropic_key: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Generates an AI technical-debt summary using Groq, Anthropic, or a local
    rule-based fallback (in that priority order, based on which keys exist).
    Returns (summary_text, error_message) - error_message is only a soft
    warning when a fallback was used, never a hard failure.
    """
    top_files = [f for f in ranked_files if f.risk_score > 0][:MAX_FILES_IN_PROMPT]
    if not top_files:
        return _local_fallback(repo_path, top_files), None

    prompt = _build_prompt(repo_path, top_files)

    if groq_key:
        text, error = _try_groq(groq_key, prompt)
        if text:
            return text, None
        # fall through to next provider, but remember why Groq failed
        fallback_note = error
    else:
        fallback_note = None

    if anthropic_key and anthropic_key.startswith("sk-ant-"):
        text, error = _try_anthropic(anthropic_key, prompt)
        if text:
            return text, None
        fallback_note = error or fallback_note

    summary = _local_fallback(repo_path, top_files)
    if fallback_note:
        return summary, f"Live AI provider unavailable, showing local summary. ({fallback_note})"
    return summary, None