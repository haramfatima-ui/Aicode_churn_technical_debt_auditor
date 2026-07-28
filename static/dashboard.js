const state = { report: null };
const $ = (id) => document.getElementById(id);

const BAND_LABEL = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
const BAND_COLOR = { critical: "#ff453a", high: "#ff9f0a", medium: "#ffd60a", low: "#32d74b" };

function fmt(value, fallback = "—") {
  return value === null || value === undefined ? fallback : value;
}

function setStatus(text, mode) {
  const line = $("status-line");
  line.textContent = text;
  line.classList.toggle("error", mode === "error");
  line.classList.toggle("busy", mode === "busy");
}

function setExportButtonsEnabled(enabled) {
  $("export-json-btn").disabled = !enabled;
  $("export-pdf-btn").disabled = !enabled;
}

async function runAnalysis(e) {
  e.preventDefault();
  const btn = $("analyze-btn");
  btn.disabled = true;
  setStatus("Scanning repository… this can take a moment on large repos.", "busy");

  const payload = {
    repo_path: $("repo_path").value.trim(),
    lookback_commits: parseInt($("lookback").value, 10) || undefined,
    include_ai_summary: $("include_ai_summary").checked,
  };

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    const report = await res.json();
    state.report = report;
    renderReport(report);
    setExportButtonsEnabled(true);
    setStatus(
      `Scanned ${report.total_files_scanned} files at ${new Date(report.generated_at).toLocaleString()}.`
    );
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
  }
}

function renderReport(report) {
  $("results").classList.remove("hidden");
  renderSummaryCards(report);
  renderChart(report);
  renderAiSummary(report);
  renderTable(report.files);
}

function renderSummaryCards(report) {
  const files = report.files;
  const critical = files.filter((f) => f.risk_band === "critical").length;
  const high = files.filter((f) => f.risk_band === "high").length;
  const avgRisk = files.length
    ? (files.reduce((s, f) => s + f.risk_score, 0) / files.length).toFixed(1)
    : "0";

  const cards = [
    { label: "Files scanned", value: report.total_files_scanned, cls: "" },
    { label: "Critical risk files", value: critical, cls: "stat-card--critical" },
    { label: "High risk files", value: high, cls: "stat-card--high" },
    { label: "Average risk score", value: avgRisk, cls: "" },
  ];

  $("summary-cards").innerHTML = cards
    .map(
      (c) => `
      <div class="stat-card ${c.cls}">
        <div class="stat-card__value">${c.value}</div>
        <div class="stat-card__label">${c.label}</div>
      </div>`
    )
    .join("");
}

let chartInstance = null;
function renderChart(report) {
  const top = [...report.files].sort((a, b) => b.risk_score - a.risk_score).slice(0, 10);
  const ctx = $("risk-chart").getContext("2d");
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: top.map((f) => f.path),
      datasets: [
        {
          label: "Risk score",
          data: top.map((f) => f.risk_score),
          backgroundColor: top.map((f) => BAND_COLOR[f.risk_band]),
          borderRadius: 4,
          barThickness: 16,
        },
      ],
    },
    options: {
      responsive: true,
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, max: 100, ticks: { color: "#86868b" }, grid: { color: "#1f1f21" } },
        y: { ticks: { color: "#86868b", font: { family: "IBM Plex Mono", size: 11 } }, grid: { display: false } },
      },
    },
  });
}

function renderAiSummary(report) {
  const box = $("ai-summary-box");
  const text = $("ai-summary-text");
  if (report.ai_summary) {
    box.classList.remove("hidden");
    text.textContent = report.ai_summary;
  } else if (report.ai_summary_error) {
    box.classList.remove("hidden");
    text.textContent = `⚠ ${report.ai_summary_error}`;
  } else {
    box.classList.add("hidden");
  }
}

function renderTable(files) {
  const tbody = $("files-tbody");
  tbody.innerHTML = files
    .map(
      (f, idx) => `
      <tr data-idx="${idx}" class="file-row" data-band="${f.risk_band}" data-path="${f.path.toLowerCase()}">
        <td class="col-file">${f.path}</td>
        <td><span class="badge badge--${f.risk_band}">${f.risk_score}</span></td>
        <td>${f.churn_score}</td>
        <td>${f.complexity_score}</td>
        <td>${f.marker_score}</td>
        <td>${fmt(f.churn?.commit_count)}</td>
        <td>${fmt(f.churn?.authors)}</td>
        <td>${fmt(f.complexity?.loc)}</td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll(".file-row").forEach((row) => {
    row.addEventListener("click", () => openModal(files[parseInt(row.dataset.idx, 10)]));
  });

  applyFilters();
}

function applyFilters() {
  const search = $("search-input").value.trim().toLowerCase();
  const riskFilter = $("risk-filter").value;
  let visibleCount = 0;

  document.querySelectorAll("#files-tbody .file-row").forEach((row) => {
    const matchesSearch = !search || row.dataset.path.includes(search);
    const matchesRisk = riskFilter === "all" || row.dataset.band === riskFilter;
    const visible = matchesSearch && matchesRisk;
    row.style.display = visible ? "" : "none";
    if (visible) visibleCount += 1;
  });

  $("no-results").classList.toggle("hidden", visibleCount !== 0);
}

function openModal(f) {
  $("modal-filename").textContent = f.path;
  $("modal-band").textContent = BAND_LABEL[f.risk_band];
  $("modal-band").className = `badge badge--${f.risk_band}`;

  $("modal-content").innerHTML = `
    <h3>Composite score</h3>
    <div class="metric-row"><span>Risk score</span><span>${f.risk_score} / 100</span></div>
    <div class="metric-row"><span>Churn contribution</span><span>${f.churn_score}</span></div>
    <div class="metric-row"><span>Complexity contribution</span><span>${f.complexity_score}</span></div>
    <div class="metric-row"><span>Marker contribution</span><span>${f.marker_score}</span></div>

    <h3>Git churn</h3>
    <div class="metric-row"><span>Commits</span><span>${fmt(f.churn?.commit_count)}</span></div>
    <div class="metric-row"><span>Authors</span><span>${fmt(f.churn?.authors)}</span></div>
    <div class="metric-row"><span>Lines added</span><span>${fmt(f.churn?.lines_added)}</span></div>
    <div class="metric-row"><span>Lines removed</span><span>${fmt(f.churn?.lines_removed)}</span></div>
    <div class="metric-row"><span>Last modified</span><span>${fmt(f.churn?.last_modified_days_ago)} day(s) ago</span></div>

    <h3>Complexity</h3>
    <div class="metric-row"><span>Cyclomatic complexity</span><span>${fmt(f.complexity?.cyclomatic_complexity)}</span></div>
    <div class="metric-row"><span>Maintainability index</span><span>${fmt(f.complexity?.maintainability_index)}</span></div>
    <div class="metric-row"><span>Lines of code</span><span>${fmt(f.complexity?.loc)}</span></div>
    <div class="metric-row"><span>Functions analyzed</span><span>${fmt(f.complexity?.functions_analyzed)}</span></div>

    <h3>Debt markers</h3>
    <div class="metric-row"><span>TODO</span><span>${fmt(f.markers?.todo_count)}</span></div>
    <div class="metric-row"><span>FIXME</span><span>${fmt(f.markers?.fixme_count)}</span></div>
    <div class="metric-row"><span>HACK</span><span>${fmt(f.markers?.hack_count)}</span></div>
    <div class="metric-row"><span>DEPRECATED</span><span>${fmt(f.markers?.deprecated_count)}</span></div>
    <div class="metric-row"><span>Long lines (&gt;120 chars)</span><span>${fmt(f.markers?.long_lines)}</span></div>
  `;

  $("inspector-modal").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  $("inspector-modal").classList.add("hidden");
  document.body.style.overflow = "";
}

function exportJSON() {
  if (!state.report) return;
  const blob = new Blob([JSON.stringify(state.report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `debt-report-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function exportPDF() {
  if (!state.report) return;
  const btn = $("export-pdf-btn");
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Generating…";

  try {
    const target = $("report-content");

    // Solution 1: Updated html2canvas config with clone handling for canvas elements
    const canvas = await html2canvas(target, {
      backgroundColor: "#000000",
      scale: 2,
      useCORS: true,
      logging: false,
      onclone: (clonedDoc) => {
        // Ensure chart canvas maintains valid display properties in the rendered clone
        const clonedCanvases = clonedDoc.querySelectorAll("canvas");
        clonedCanvases.forEach((c) => {
          c.style.display = "block";
        });
      },
    });

    const imgData = canvas.toDataURL("image/png");
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF("p", "pt", "a4");
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const imgWidth = pageWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;

    let heightLeft = imgHeight;
    let position = 0;

    pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
    heightLeft -= pageHeight;

    while (heightLeft > 0) {
      position = heightLeft - imgHeight;
      pdf.addPage();
      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
    }

    pdf.save(`debt-report-${Date.now()}.pdf`);
  } catch (err) {
    setStatus(`PDF export failed: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("analyze-form").addEventListener("submit", runAnalysis);
  $("search-input").addEventListener("input", applyFilters);
  $("risk-filter").addEventListener("change", applyFilters);

  document.querySelectorAll("[data-close-modal]").forEach((elm) =>
    elm.addEventListener("click", closeModal)
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  $("export-json-btn").addEventListener("click", exportJSON);
  $("export-pdf-btn").addEventListener("click", exportPDF);
});