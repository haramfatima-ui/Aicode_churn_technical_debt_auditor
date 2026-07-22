# 🔍 AI Code Churn & Technical Debt Auditor

Find the files quietly costing your team the most time.

A lightweight, self-hosted dashboard that scans any local git repository and turns three usually-separate signals — **git churn**, **code complexity**, and **debt markers** (TODO/FIXME/HACK) — into a single, ranked **Risk Score** per file. No cloud upload, no mandatory API key, no enterprise pricing tier.

---

## The Problem

Most teams *feel* like they know which files are risky, but can rarely prove it. Code review is subjective, static-analysis tools usually measure complexity in isolation, and churn (how often a file changes and how many hands touch it) is almost never combined with that signal — even though the two together are what actually predicts bugs and slow-downs.

This project closes that gap with one composite, explainable score.

---

## Features

- **Composite Risk Score (0–100)** — weighted blend of churn, complexity, and debt markers, banded into Low / Medium / High / Critical
- **Interactive dashboard** — sortable table, live search, risk-level filter, and a bar chart of the top 10 riskiest files
- **Click-to-inspect modal** — full metric breakdown per file (commits, authors, cyclomatic complexity, maintainability index, TODO/FIXME/HACK counts, and more)
- **AI-generated summary** — a plain-English, engineering-manager-friendly narrative highlighting hot spots and refactor priorities
- **Three-tier AI fallback** — Groq (free tier) → Anthropic (Claude) → fully offline, zero-dependency local summary. The app is always useful, even with no API keys configured.
- **One-click export** — download the full report as JSON or a polished PDF
- **Zero cloud dependency** — everything runs locally against your own git repo

---

## Tech Stack

| Layer            | Technology                                   |
|-------------------|-----------------------------------------------|
| Backend            | Python, FastAPI, Pydantic / Pydantic-Settings |
| Git analysis        | `git log --numstat` parsing                   |
| Complexity analysis | [Radon](https://radon.readthedocs.io/) (cyclomatic complexity + maintainability index) |
| AI summaries        | Groq (Llama 3.3) / Anthropic (Claude) via `httpx`, with a local rule-based fallback |
| Frontend            | Vanilla JS, Chart.js, HTML/CSS (no framework, no build step) |
| Export              | html2canvas + jsPDF (PDF), native Blob download (JSON) |

---

## Project Structure

```
.
├── main.py                  # FastAPI app & API routes
├── config.py                # Environment-based settings
├── models.py                 # Pydantic schemas
├── git_analyzer.py          # Git churn analysis
├── complexity_analyzer.py    # Complexity + debt marker scanning
├── risk_scorer.py            # Composite risk scoring
├── ai_insights.py            # AI summary generation (Groq / Anthropic / local)
├── index.html                # Dashboard shell
├── static/
│   ├── style.css             # Design system
│   └── dashboard.js          # Dashboard behavior (fetch, render, filters, export)
├── .env.example
└── requirement.text          # Python dependencies
```

---

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirement.text
```

### 2. Configure environment (optional)

Copy the example env file and fill in what you need — every value is optional:

```bash
cp .env.example .env
```

```env
# Optional: free AI summaries via Groq (https://console.groq.com)
GROQ_API_KEY=

# Optional: AI summaries via Anthropic instead
ANTHROPIC_API_KEY=

# Default repo path shown in the UI
DEFAULT_REPO_PATH=.

# How many commits of history to scan for churn
CHURN_LOOKBACK_COMMITS=1000

# Max files to run complexity analysis on per scan
MAX_FILES_PER_SCAN=2000
```

No keys configured? The app still works end-to-end — AI summaries fall back to a local, offline narrative generator.

### 3. Run the server

```bash
uvicorn main:app --reload
```

### 4. Open the dashboard

Visit **http://localhost:8000**, enter the path to any local git repository, and click **Run Analysis**.

---

## API Endpoints

| Method | Endpoint         | Description                              |
|--------|------------------|-------------------------------------------|
| GET    | `/`              | Serves the dashboard                      |
| POST   | `/api/analyze`   | Runs a full scan and returns the report    |
| GET    | `/api/report`    | Returns the most recent report generated   |

---

## Who It's For

- **Engineering managers** running quarterly code-health checks
- **Tech leads** who need a defensible, data-backed case for refactor time
- **Consultants / contractors** auditing an unfamiliar codebase before taking it on
- **Any developer** who's inherited a repo and doesn't know where to start

---
