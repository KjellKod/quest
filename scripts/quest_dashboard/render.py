"""HTML rendering for the Quest Dashboard.

This module generates a self-contained HTML file with:
- Inline CSS (dark navy theme matching PR #21 executive design)
- Ambient glow effects (2 orbs: sky-blue left, teal right)
- Interactive charts (doughnut + line chart) via inlined Chart.js
- 5 KPI cards (Total, Finished, In Progress, Blocked, Abandoned)
- Unified Quest Portfolio section with all quests sorted by date
- Quest cards with full pitch, labeled metadata, and status badges
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path
from typing import Union

from .models import ActiveQuest, DashboardData, JournalEntry

logger = logging.getLogger(__name__)

# Path to the vendored Chart.js file
_VENDOR_DIR = Path(__file__).parent / "vendor"
_CHARTJS_PATH = _VENDOR_DIR / "chart.min.js"

# Badge text mapping: internal status -> display badge text
_BADGE_TEXT = {
    "completed": "FINISHED",
    "abandoned": "ABANDONED",
    "in progress": "IN PROGRESS",
    "blocked": "BLOCKED",
}


def render_dashboard(data: DashboardData, output_path: Path, repo_root: Path) -> str:
    """Render the complete dashboard HTML.

    Args:
        data: Dashboard data with all quests
        output_path: Where the HTML will be written (for computing relative links)
        repo_root: Repository root (for computing relative links)

    Returns:
        Complete HTML document as string
    """
    css = _render_css()
    chart_js_lib, chart_js_loaded = _render_chart_js()
    glows = _render_glows()
    hero = _render_hero(data)
    kpi_row = _render_kpi_row(data)
    charts_section = _render_charts_section()
    portfolio_section = _render_portfolio_section(data, data.github_repo_url)
    warnings_html = _render_warnings(data.warnings)
    footer = _render_footer(data.generated_at)
    chart_config = _render_chart_config(data, chart_js_loaded)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quest Portfolio Dashboard</title>
  <style>
{css}
  </style>
{chart_js_lib}
</head>
<body>
{glows}
  <div class="container">
{hero}
{kpi_row}
{charts_section}
{portfolio_section}
{warnings_html}
{footer}
  </div>
{chart_config}
</body>
</html>
"""


def _render_css() -> str:
    """Generate the complete CSS stylesheet with dark navy theme."""
    return """    /* Design tokens from PR #21 */
    :root {
      --bg-0: #05070f;
      --bg-1: #0a0f1d;
      --surface-0: rgba(17, 24, 39, 0.78);
      --surface-1: rgba(15, 23, 42, 0.84);
      --surface-2: rgba(30, 41, 59, 0.75);
      --line: rgba(148, 163, 184, 0.22);
      --text-0: #f8fafc;
      --text-1: #cbd5e1;
      --text-2: #94a3b8;
      --status-finished: #34d399;
      --status-in-progress: #60a5fa;
      --status-blocked: #f59e0b;
      --status-abandoned: #f87171;
      --status-unknown: #a78bfa;
      --radius-lg: 22px;
      --radius-md: 16px;
      --shadow-lg: 0 25px 60px rgba(2, 6, 23, 0.45);
    }

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background:
        radial-gradient(1200px circle at 8% -5%, rgba(56, 189, 248, 0.18), transparent 42%),
        radial-gradient(1000px circle at 92% 12%, rgba(45, 212, 191, 0.12), transparent 38%),
        linear-gradient(155deg, var(--bg-0) 0%, var(--bg-1) 68%, #0f172a 100%);
      color: var(--text-0);
      line-height: 1.6;
      min-height: 100vh;
      padding: 2rem 1rem;
    }

    .container {
      position: relative;
      z-index: 1;
      max-width: 1400px;
      margin: 0 auto;
    }

    /* Page glow effects */
    .page-glow {
      position: fixed;
      border-radius: 50%;
      width: 480px;
      height: 480px;
      filter: blur(95px);
      opacity: 0.38;
      pointer-events: none;
      z-index: -1;
    }

    .page-glow-left {
      top: -220px;
      left: -160px;
      background: #0ea5e9;
    }

    .page-glow-right {
      top: 120px;
      right: -180px;
      background: #14b8a6;
    }

    /* Hero section */
    .hero {
      background: linear-gradient(140deg, rgba(15,23,42,0.9), rgba(30,41,59,0.74));
      backdrop-filter: blur(12px);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 3rem 2rem;
      margin-bottom: 2rem;
      box-shadow: var(--shadow-lg);
    }

    .eyebrow {
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.15em;
      color: #67e8f9;
      margin-bottom: 0.5rem;
    }

    .hero h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      color: var(--text-0);
    }

    .hero-subtitle {
      font-size: 1.125rem;
      color: var(--text-2);
      margin-bottom: 1.5rem;
    }

    .meta-row {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }

    .meta-label {
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-2);
      font-weight: 600;
    }

    .meta-value {
      font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      color: var(--text-1);
    }

    /* KPI cards */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 1rem;
      margin-bottom: 2rem;
    }

    .kpi-card {
      background: var(--surface-0);
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      padding: 1.25rem;
      text-align: center;
    }

    .kpi-label {
      font-size: 0.875rem;
      color: var(--text-2);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }

    .kpi-value {
      font-size: 2rem;
      font-weight: 800;
      color: var(--text-0);
    }

    .kpi-value--finished {
      color: var(--status-finished);
    }

    .kpi-value--in-progress {
      color: var(--status-in-progress);
    }

    .kpi-value--blocked {
      color: var(--status-blocked);
    }

    .kpi-value--abandoned {
      color: var(--status-abandoned);
    }

    /* Chart panels */
    .panel-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 1.5rem;
      margin-bottom: 2rem;
    }

    .panel {
      background: var(--surface-0);
      backdrop-filter: blur(12px);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      box-shadow: var(--shadow-lg);
      min-height: 340px;
    }

    .panel h2 {
      font-size: 1.18rem;
      font-weight: 700;
      color: var(--text-0);
      margin-bottom: 0.25rem;
    }

    .panel-subtitle {
      font-size: 0.88rem;
      color: var(--text-2);
      margin-bottom: 1rem;
    }

    .chart-wrap {
      height: 255px;
      position: relative;
    }

    /* Quest Portfolio section */
    .quests-section {
      background: var(--surface-0);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 2rem;
      margin-bottom: 2rem;
    }

    .quests-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 12px;
      margin-bottom: 1.5rem;
    }

    .quests-header h2 {
      font-size: 1.18rem;
      font-weight: 700;
      color: var(--text-0);
    }

    /* Quest cards grid */
    .quest-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.5rem;
    }

    .quest-card {
      background: var(--surface-2);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 1.5rem;
      min-height: 210px;
      display: grid;
      gap: 10px;
      transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }

    .quest-card:hover {
      transform: translateY(-3px);
      box-shadow: var(--shadow-lg);
      border-color: rgba(148,163,184, 0.5);
    }

    .quest-card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
    }

    .quest-card-title {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-0);
      flex: 1;
    }

    .badge {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }

    .badge--finished {
      background: rgba(52, 211, 153, 0.15);
      color: var(--status-finished);
      border: 1px solid rgba(52, 211, 153, 0.3);
    }

    .badge--in-progress {
      background: rgba(96, 165, 250, 0.15);
      color: var(--status-in-progress);
      border: 1px solid rgba(96, 165, 250, 0.3);
    }

    .badge--blocked {
      background: rgba(245, 158, 11, 0.15);
      color: var(--status-blocked);
      border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .badge--abandoned {
      background: rgba(248, 113, 113, 0.15);
      color: var(--status-abandoned);
      border: 1px solid rgba(248, 113, 113, 0.3);
    }

    .badge--unknown {
      background: rgba(167, 139, 250, 0.15);
      color: var(--status-unknown);
      border: 1px solid rgba(167, 139, 250, 0.3);
    }

    .quest-pitch {
      font-size: 0.92rem;
      color: var(--text-1);
      line-height: 1.58;
    }

    .quest-meta {
      border-top: 1px solid var(--line);
      padding-top: 0.75rem;
      margin-top: auto;
      display: grid;
      gap: 5px;
      font-size: 0.83rem;
      color: var(--text-2);
    }

    .quest-meta b {
      color: #e2e8f0;
      font-weight: 600;
    }

    .quest-meta a {
      color: var(--text-2);
      text-decoration: none;
    }

    .quest-meta a:hover {
      color: var(--status-in-progress);
      text-decoration: underline;
    }

    /* Empty state */
    .empty-state {
      text-align: center;
      padding: 3rem 1rem;
      color: var(--text-2);
      font-style: italic;
    }

    /* Warnings */
    .warnings {
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      border-radius: var(--radius-md);
      padding: 1rem 1.5rem;
      margin-bottom: 2rem;
    }

    .warnings-title {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--status-blocked);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
    }

    .warnings-list {
      list-style: none;
      font-size: 0.875rem;
      color: var(--text-1);
    }

    .warnings-list li {
      margin-bottom: 0.25rem;
    }

    /* Footer */
    .footer {
      text-align: center;
      padding: 2rem 1rem;
      color: var(--text-2);
      font-size: 0.875rem;
    }

    /* Responsive: 3 breakpoints */
    @media (max-width: 1120px) {
      .kpi-grid {
        grid-template-columns: repeat(3, 1fr);
      }

      .quest-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    @media (max-width: 780px) {
      body {
        padding: 1rem 0.5rem;
      }

      .hero {
        padding: 2rem 1.25rem;
      }

      .hero h1 {
        font-size: 2rem;
      }

      .kpi-grid {
        grid-template-columns: repeat(2, 1fr);
      }

      .panel-grid {
        grid-template-columns: 1fr;
      }

      .quest-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 460px) {
      .kpi-grid {
        grid-template-columns: 1fr;
      }

      .quests-header {
        flex-direction: column;
        align-items: flex-start;
      }
    }"""


def _render_hero(data: DashboardData) -> str:
    """Render the hero section with QUEST INTELLIGENCE branding."""
    timestamp = data.generated_at.strftime("%b %d, %Y, %I:%M %p UTC")

    return f"""    <div class="hero">
      <p class="eyebrow">QUEST INTELLIGENCE</p>
      <h1>Quest Portfolio Dashboard</h1>
      <div class="hero-subtitle">Board-level visibility into quest outcomes, execution momentum, and strategic throughput.</div>
      <div class="meta-row"><span class="meta-label">DATA GENERATED:</span> <span class="meta-value">{timestamp}</span></div>
    </div>"""


def _render_glows() -> str:
    """Emit fixed-position decorative glow divs.

    Two glow orbs: sky-blue left and teal right, providing ambient
    color effects behind the dashboard content.
    """
    return """  <div class="page-glow page-glow-left" aria-hidden="true"></div>
  <div class="page-glow page-glow-right" aria-hidden="true"></div>"""


def _render_chart_js() -> tuple[str, bool]:
    """Inline the vendored Chart.js library as a <script> block.

    Returns:
        A tuple of (script_tag, available) where script_tag is a ``<script>``
        tag containing the full Chart.js source (or empty string if the vendor
        file is missing), and available indicates whether Chart.js was loaded.
    """
    if not _CHARTJS_PATH.is_file():
        logger.warning(
            "Chart.js vendor file not found at %s; charts will be disabled",
            _CHARTJS_PATH,
        )
        return "", False

    chart_js_source = _CHARTJS_PATH.read_text(encoding="utf-8")
    return f"  <script>\n{chart_js_source}\n  </script>", True


def _render_kpi_row(data: DashboardData) -> str:
    """Render the 5 KPI cards row below the hero.

    Cards: Total Quests, Finished, In Progress, Blocked, Abandoned.
    Uses _classify_status() so counts agree with the doughnut chart.
    """
    blocked_count = 0
    in_progress_count = 0
    for q in data.active_quests:
        cls = _classify_status(q.status)
        if cls == "blocked":
            blocked_count += 1
        elif cls != "unknown":
            in_progress_count += 1
    finished_count = len(data.finished_quests)
    abandoned_count = len(data.abandoned_quests)
    total = finished_count + len(data.active_quests) + abandoned_count

    return f"""    <div class="kpi-grid">
      <article class="kpi-card">
        <p class="kpi-label">Total Quests</p>
        <p class="kpi-value">{total}</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">Finished</p>
        <p class="kpi-value kpi-value--finished">{finished_count}</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">In Progress</p>
        <p class="kpi-value kpi-value--in-progress">{in_progress_count}</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">Blocked</p>
        <p class="kpi-value kpi-value--blocked">{blocked_count}</p>
      </article>
      <article class="kpi-card">
        <p class="kpi-label">Abandoned</p>
        <p class="kpi-value kpi-value--abandoned">{abandoned_count}</p>
      </article>
    </div>"""


def _render_charts_section() -> str:
    """Emit the side-by-side chart panels (doughnut + line chart)."""
    return """    <div class="panel-grid">
      <div class="panel">
        <h2>Status Distribution</h2>
        <p class="panel-subtitle">Current normalized state across all quests</p>
        <div class="chart-wrap">
          <canvas id="chart-status-doughnut"></canvas>
          <noscript>Chart requires JavaScript</noscript>
        </div>
      </div>
      <div class="panel">
        <h2>Final Status Over Time</h2>
        <p class="panel-subtitle">Monthly trend using each quest's final/current status</p>
        <div class="chart-wrap">
          <canvas id="chart-time-progression"></canvas>
          <noscript>Chart requires JavaScript</noscript>
        </div>
      </div>
    </div>"""


def _compute_monthly_buckets(data: DashboardData) -> OrderedDict[str, dict[str, int]]:
    """Group all quests by month for the time-progression chart.

    Tracks all 5 statuses: finished, abandoned, in_progress, blocked, unknown.

    Returns:
        OrderedDict keyed by 'YYYY-MM' strings (sorted chronologically),
        each value is ``{"finished": int, "abandoned": int, "in_progress": int,
        "blocked": int, "unknown": int}``.
        Gaps between min and max months are filled with zeros.
    """
    empty_bucket = {
        "finished": 0,
        "abandoned": 0,
        "in_progress": 0,
        "blocked": 0,
        "unknown": 0,
    }
    raw: dict[str, dict[str, int]] = {}

    for quest in data.finished_quests:
        key = quest.completed_date.strftime("%Y-%m")
        raw.setdefault(key, dict(empty_bucket))
        raw[key]["finished"] += 1

    for quest in data.abandoned_quests:
        key = quest.completed_date.strftime("%Y-%m")
        raw.setdefault(key, dict(empty_bucket))
        raw[key]["abandoned"] += 1

    for quest in data.active_quests:
        key = quest.updated_at.strftime("%Y-%m")
        raw.setdefault(key, dict(empty_bucket))
        if "block" in quest.status.lower():
            raw[key]["blocked"] += 1
        elif _classify_status(quest.status) == "unknown":
            raw[key]["unknown"] += 1
        else:
            raw[key]["in_progress"] += 1

    if not raw:
        return OrderedDict()

    # Fill gaps between min and max months
    sorted_keys = sorted(raw.keys())
    min_year, min_month = (int(x) for x in sorted_keys[0].split("-"))
    max_year, max_month = (int(x) for x in sorted_keys[-1].split("-"))

    result: OrderedDict[str, dict[str, int]] = OrderedDict()
    year, month = min_year, min_month
    while (year, month) <= (max_year, max_month):
        key = f"{year:04d}-{month:02d}"
        result[key] = raw.get(key, dict(empty_bucket))
        month += 1
        if month > 12:
            month = 1
            year += 1

    return result


def _classify_status(status: str) -> str:
    """Classify a quest status string into a known category.

    Returns one of: 'finished', 'in_progress', 'blocked', 'abandoned', 'unknown'.
    """
    lower = status.lower()
    if lower in ("completed", "finished"):
        return "finished"
    if "block" in lower:
        return "blocked"
    if lower in ("abandoned",):
        return "abandoned"
    if lower in ("in progress", "in_progress"):
        return "in_progress"
    return "unknown"


def _render_chart_config(data: DashboardData, chart_js_available: bool) -> str:
    """Generate inline JavaScript that creates Chart.js instances.

    Args:
        data: Dashboard data with all quests.
        chart_js_available: Whether Chart.js was successfully loaded.

    Returns:
        A <script> tag with chart initialization code, or empty string
        if Chart.js vendor was not loaded.
    """
    if not chart_js_available:
        return ""

    finished_count = len(data.finished_quests)
    abandoned_count = len(data.abandoned_quests)
    blocked_count = 0
    in_progress_count = 0
    unknown_count = 0
    for q in data.active_quests:
        cls = _classify_status(q.status)
        if cls == "blocked":
            blocked_count += 1
        elif cls == "unknown":
            unknown_count += 1
        else:
            in_progress_count += 1

    # Compute monthly buckets for time-progression chart
    buckets = _compute_monthly_buckets(data)
    labels = list(buckets.keys())
    finished_series = [b["finished"] for b in buckets.values()]
    abandoned_series = [b["abandoned"] for b in buckets.values()]
    in_progress_series = [b["in_progress"] for b in buckets.values()]
    blocked_series = [b["blocked"] for b in buckets.values()]
    unknown_series = [b["unknown"] for b in buckets.values()]

    return f"""  <script>
document.addEventListener('DOMContentLoaded', function() {{
  // Doughnut chart: status distribution (all 5 statuses)
  var doughnutCtx = document.getElementById('chart-status-doughnut');
  if (doughnutCtx) {{
    new Chart(doughnutCtx, {{
      type: 'doughnut',
      data: {{
        labels: ['In Progress', 'Blocked', 'Abandoned', 'Finished', 'Unknown'],
        datasets: [{{
          data: [{in_progress_count}, {blocked_count}, {abandoned_count}, {finished_count}, {unknown_count}],
          backgroundColor: [
            getComputedStyle(document.documentElement).getPropertyValue('--status-in-progress').trim(),
            getComputedStyle(document.documentElement).getPropertyValue('--status-blocked').trim(),
            getComputedStyle(document.documentElement).getPropertyValue('--status-abandoned').trim(),
            getComputedStyle(document.documentElement).getPropertyValue('--status-finished').trim(),
            getComputedStyle(document.documentElement).getPropertyValue('--status-unknown').trim()
          ],
          borderWidth: 1,
          borderColor: 'rgba(15,23,42,0.85)',
          hoverOffset: 8
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{
            display: true,
            position: 'bottom',
            labels: {{ color: '#cbd5e1', boxWidth: 14, padding: 16 }}
          }}
        }},
        cutout: '65%'
      }}
    }});
  }}

  // Time-progression chart: line chart (all 5 statuses)
  var timeCtx = document.getElementById('chart-time-progression');
  if (timeCtx) {{
    new Chart(timeCtx, {{
      type: 'line',
      data: {{
        labels: {json.dumps(labels)},
        datasets: [
          {{
            label: 'Finished',
            data: {json.dumps(finished_series)},
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--status-finished').trim(),
            fill: false,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3
          }},
          {{
            label: 'In Progress',
            data: {json.dumps(in_progress_series)},
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--status-in-progress').trim(),
            fill: false,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3
          }},
          {{
            label: 'Blocked',
            data: {json.dumps(blocked_series)},
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--status-blocked').trim(),
            fill: false,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3
          }},
          {{
            label: 'Abandoned',
            data: {json.dumps(abandoned_series)},
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--status-abandoned').trim(),
            fill: false,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3
          }},
          {{
            label: 'Unknown',
            data: {json.dumps(unknown_series)},
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--status-unknown').trim(),
            fill: false,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
          x: {{
            ticks: {{ color: '#94a3b8' }},
            grid: {{ color: 'rgba(148, 163, 184, 0.1)' }}
          }},
          y: {{
            beginAtZero: true,
            ticks: {{ color: '#94a3b8', stepSize: 1 }},
            grid: {{ color: 'rgba(148, 163, 184, 0.1)' }}
          }}
        }},
        plugins: {{
          legend: {{
            labels: {{ color: '#cbd5e1', padding: 12, boxWidth: 12 }}
          }}
        }}
      }}
    }});
  }}
}});
  </script>"""


def _render_portfolio_section(
    data: DashboardData,
    github_url: str,
) -> str:
    """Render the unified Quest Portfolio section with all quests."""
    # Merge all quests into a single list with sort keys
    all_quests: list[tuple[date, Union[JournalEntry, ActiveQuest]]] = []

    for q in data.finished_quests:
        all_quests.append((q.completed_date, q))

    for q in data.abandoned_quests:
        all_quests.append((q.completed_date, q))

    for q in data.active_quests:
        all_quests.append((q.updated_at.date(), q))

    # Sort descending by date (most recent first)
    all_quests.sort(key=lambda x: x[0], reverse=True)

    total = len(all_quests)

    if not all_quests:
        cards_html = '      <div class="empty-state">No quests in this category</div>'
    else:
        cards = [
            _render_quest_card(quest, github_url)
            for _, quest in all_quests
        ]
        cards_html = (
            f'      <div class="quest-grid">\n' + "\n".join(cards) + "\n      </div>"
        )

    return f"""    <section class="quests-section" id="quest-portfolio">
      <div class="quests-header">
        <h2>Quest Portfolio</h2>
        <p class="panel-subtitle">{total} quests represented</p>
      </div>
{cards_html}
    </section>"""


def _render_quest_card(
    quest: Union[JournalEntry, ActiveQuest],
    github_url: str,
) -> str:
    """Render a single quest card for any quest type.

    Handles both JournalEntry (finished/abandoned) and ActiveQuest (in-progress/blocked).
    """
    # Determine badge class and text
    status_lower = quest.status.lower()
    badge_text = _BADGE_TEXT.get(status_lower, "UNKNOWN")

    if status_lower in ("completed", "finished"):
        badge_class = "finished"
    elif "block" in status_lower:
        badge_class = "blocked"
    elif status_lower == "abandoned":
        badge_class = "abandoned"
    elif status_lower in ("in progress", "in_progress"):
        badge_class = "in-progress"
    else:
        badge_class = "unknown"

    # Build metadata spans
    meta_items = [f'<span><b>Quest ID:</b> {html.escape(quest.quest_id)}</span>']

    if isinstance(quest, JournalEntry):
        meta_items.append(
            f'<span><b>Completion Date:</b> {quest.completed_date.strftime("%b %d, %Y")}</span>'
        )
    else:
        meta_items.append(
            f'<span><b>Updated:</b> {quest.updated_at.strftime("%b %d, %Y")}</span>'
        )

    # Add iterations if available
    if quest.plan_iterations is not None or quest.fix_iterations is not None:
        plan = quest.plan_iterations or 0
        fix = quest.fix_iterations or 0
        meta_items.append(f'<span><b>Iterations:</b> plan {plan} / fix {fix}</span>')

    # Add PR link if available (JournalEntry only)
    if isinstance(quest, JournalEntry) and quest.pr_number:
        pr_link = _compute_pr_link(quest.pr_number, github_url)
        meta_items.append(
            f'<span><b>PR:</b> <a href="{pr_link}">#{quest.pr_number}</a></span>'
        )

    meta_html = "\n            ".join(meta_items)

    return f"""        <article class="quest-card">
          <div class="quest-card-header">
            <h3 class="quest-card-title">{html.escape(quest.title)}</h3>
            <span class="badge badge--{badge_class}">{badge_text}</span>
          </div>
          <p class="quest-pitch">{html.escape(quest.elevator_pitch)}</p>
          <p class="quest-meta">
            {meta_html}
          </p>
        </article>"""


def _render_warnings(warnings: list[str]) -> str:
    """Render warnings section if there are any warnings."""
    if not warnings:
        return ""

    warnings_items = "\n".join(f"      <li>{html.escape(w)}</li>" for w in warnings)

    return f"""    <div class="warnings">
      <div class="warnings-title">Build Warnings</div>
      <ul class="warnings-list">
{warnings_items}
      </ul>
    </div>"""


def _render_footer(generated_at: datetime) -> str:
    """Render the footer with generation timestamp."""
    timestamp = generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""    <footer class="footer">
      Generated on {timestamp}
    </footer>"""


def _sanitize_url(url: str) -> str:
    """Validate and escape a URL for safe use in an HTML href attribute.

    Args:
        url: Raw URL string.

    Returns:
        Sanitized URL string safe for attribute interpolation, or "" if invalid.
    """
    url = url.strip()
    if not url:
        return ""

    # Reject non-HTTPS schemes (blocks javascript:, data:, vbscript:, http://, etc.)
    if not url.startswith("https://"):
        return ""

    # Validate GitHub URL pattern: https://github.com/<owner>/<repo> with optional path
    if not re.match(
        r"^https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(/.*)?$", url
    ):
        return ""

    # HTML attribute escaping
    return html.escape(url)


def _compute_pr_link(pr_number: int, github_url: str) -> str:
    """Compute the link to a pull request.

    Args:
        pr_number: PR number
        github_url: GitHub repository URL

    Returns:
        URL to PR (or # if github_url is empty)
    """
    if github_url:
        sanitized = _sanitize_url(f"{github_url}/pull/{pr_number}")
        if sanitized:
            return sanitized
    return "#"
