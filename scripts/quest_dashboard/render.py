from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from .models import ActiveQuestRecord, CompletedQuestRecord, DashboardData, UTC


def render_dashboard(data: DashboardData, output_path: Path, repo_root: Path, github_base_url: str = "") -> str:
    generated_label = _format_generated_at(data.generated_at)
    blocked_count = sum(1 for q in data.active_quests if "block" in q.status.lower())

    active_cards = "\n".join(_render_active_card(record) for record in data.active_quests)
    completed_cards = "\n".join(
        _render_completed_card(record, output_path=output_path, repo_root=repo_root, github_base_url=github_base_url)
        for record in data.completed_quests
    )

    if not active_cards:
        active_cards = _render_empty_state("No active quests found.")
    if not completed_cards:
        completed_cards = _render_empty_state("No completed quests found.")

    warning_banner = ""
    if data.warnings:
        warning_items = "".join(f"<li>{escape(warning)}</li>" for warning in data.warnings)
        warning_banner = (
            '<aside class="warning-panel">'
            "<h2>Build Warnings</h2>"
            "<ul>"
            f"{warning_items}"
            "</ul>"
            "</aside>"
        )

    chart_svg = _render_activity_chart(data)
    chart_section = ""
    if chart_svg:
        chart_section = f"""
    <section class="panel chart-panel">
      <div class="section-header">
        <h2>Quest Activity</h2>
        <small>Started vs completed by week</small>
      </div>
      {chart_svg}
    </section>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quest Dashboard</title>
  <style>
    :root {{
      /* ── Palette: derived from the hero's slate tones ── */
      --slate-950: #0c1220;
      --slate-900: #0f172a;
      --slate-800: #1e293b;
      --slate-700: #334155;
      --slate-600: #475569;
      --slate-500: #64748b;
      --slate-400: #94a3b8;
      --slate-300: #cbd5e1;
      --slate-200: #e2e8f0;
      --slate-100: #f1f5f9;
      --slate-50:  #f8fafc;

      --ink: var(--slate-900);
      --ink-secondary: var(--slate-600);
      --muted: var(--slate-400);
      --surface: #ffffff;
      --bg: var(--slate-50);
      --stroke: var(--slate-200);

      /* Accent: the compass needle — gold, used only where it matters */
      --accent: #b4975a;
      --accent-muted: rgba(180, 151, 90, .10);

      /* Status: quiet indicators, same slate family */
      --status-active: #94783a;
      --status-complete: #5a8a74;
      --status-abandoned: #8b6f6f;
      --status-blocked: #8b5a5a;

      /* Phase: all within the slate range, barely distinguishable */
      --phase-plan: var(--slate-500);
      --phase-build: var(--slate-500);
      --phase-review: var(--slate-500);
      --phase-present: var(--slate-500);
      --phase-fix: var(--slate-500);
      --phase-complete: var(--status-complete);

      --shadow-sm: 0 1px 3px rgba(15,23,42,.04);
      --shadow-md: 0 4px 12px rgba(15,23,42,.06);
      --shadow-lg: 0 16px 40px rgba(15,23,42,.10);

      /* Hero: a single confident direction — deep night, one warm glow
         on the horizon. The journey from unknown to clarity. */
      --hero-gradient:
        radial-gradient(ellipse 60% 60% at 85% 85%, rgba(180,151,90,.06) 0%, transparent 70%),
        linear-gradient(155deg, var(--slate-950) 0%, #101828 55%, #162033 100%);

      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      --font-display: "Avenir Next", "Segoe UI", var(--font);
      --font-mono: "SF Mono", Menlo, monospace;
      --radius: 10px;
      --radius-lg: 14px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: var(--font);
      color: var(--ink);
      background: var(--bg);
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }}

    .page {{
      max-width: 1060px;
      margin: 0 auto;
      padding: 28px 24px 60px;
    }}

    /* ── Hero ──────────────────────────────────────── */

    .hero {{
      background: var(--hero-gradient);
      border-radius: var(--radius-lg);
      color: var(--slate-100);
      padding: 36px 32px 30px;
      box-shadow: var(--shadow-lg);
      position: relative;
      overflow: hidden;
    }}

    /* No ::before — one gradient, one intent, no competing light sources */

    .hero h1 {{
      margin: 0;
      font-family: var(--font-display);
      font-size: clamp(1.65rem, 3vw, 2.3rem);
      font-weight: 700;
      letter-spacing: -.015em;
      position: relative;
    }}

    .hero .subtitle {{
      margin: 8px 0 0;
      color: var(--slate-400);
      font-size: .88rem;
      max-width: 52ch;
      position: relative;
    }}

    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-top: 24px;
      position: relative;
    }}

    .kpi {{
      background: rgba(255,255,255,.05);
      border: 1px solid rgba(255,255,255,.06);
      border-radius: 8px;
      padding: 14px 14px 12px;
    }}

    .kpi .label {{
      font-size: .68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--slate-500);
    }}

    .kpi .value {{
      margin-top: 4px;
      font-size: clamp(1.3rem, 2.2vw, 1.7rem);
      font-family: var(--font-display);
      font-weight: 700;
      color: var(--slate-200);
    }}

    .kpi.kpi-active .value {{ color: var(--accent); }}
    .kpi.kpi-complete .value, .kpi.kpi-blocked .value {{ color: var(--slate-300); }}

    /* ── Panels ───────────────────────────────────── */

    .panel {{
      background: var(--surface);
      border: 1px solid var(--stroke);
      border-radius: var(--radius-lg);
      padding: 22px 24px;
      margin-top: 16px;
      box-shadow: var(--shadow-sm);
    }}

    .section {{
      margin-top: 24px;
    }}

    .section-header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }}

    .section h2, .panel h2 {{
      margin: 0;
      font-family: var(--font-display);
      font-size: 1.05rem;
      font-weight: 600;
      letter-spacing: -.01em;
      color: var(--slate-800);
    }}

    .section small, .panel small {{
      color: var(--muted);
      font-size: .8rem;
    }}

    /* ── Warning Panel ────────────────────────────── */

    .warning-panel {{
      margin-top: 14px;
      background: rgba(180,151,90,.06);
      border: 1px solid rgba(180,151,90,.18);
      border-radius: var(--radius);
      padding: 14px 18px;
      color: var(--slate-700);
    }}

    .warning-panel h2 {{
      margin: 0 0 6px;
      font-size: .85rem;
      color: var(--status-active);
    }}

    .warning-panel ul {{
      margin: 0;
      padding-left: 18px;
      font-size: .85rem;
      color: var(--slate-600);
    }}

    /* ── Card Grid ────────────────────────────────── */

    .card-grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    }}

    .quest-card {{
      background: var(--surface);
      border: 1px solid var(--stroke);
      border-radius: var(--radius);
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 190px;
      transition: box-shadow .2s ease, transform .2s ease;
    }}

    .quest-card:hover {{
      box-shadow: var(--shadow-md);
      transform: translateY(-1px);
    }}

    .quest-card header {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }}

    .quest-card h3 {{
      margin: 0;
      font-family: var(--font-display);
      font-size: .98rem;
      font-weight: 600;
      line-height: 1.32;
      color: var(--ink);
    }}

    .meta {{
      margin: 0;
      color: var(--muted);
      font-size: .78rem;
    }}

    /* ── Status & Phase indicators ────────────────── */

    .badge-row {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: .72rem;
      font-weight: 600;
      letter-spacing: .02em;
      text-transform: uppercase;
      padding: 3px 0;
      color: var(--slate-500);
      border: none;
      background: none;
      border-radius: 999px;
    }}

    .badge::before {{
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    .badge--active::before   {{ background: var(--accent); }}
    .badge--completed::before {{ background: var(--status-complete); }}
    .badge--abandoned::before {{ background: var(--status-abandoned); }}

    .badge--active   {{ color: var(--status-active); }}
    .badge--completed {{ color: var(--status-complete); }}
    .badge--abandoned {{ color: var(--status-abandoned); }}

    .phase-label {{
      font-size: .72rem;
      font-weight: 500;
      letter-spacing: .02em;
      text-transform: uppercase;
      color: var(--slate-400);
      padding-left: 6px;
      border-left: 1.5px solid var(--slate-200);
    }}

    /* Phase labels stay in the slate family — no color noise */
    .phase-label.phase-complete {{ color: var(--status-complete); }}

    /* ── Pitch & Links ────────────────────────────── */

    .pitch {{
      margin: 0;
      color: var(--ink-secondary);
      font-size: .88rem;
      line-height: 1.52;
      flex: 1;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}

    .journal-link {{
      margin-top: auto;
      width: fit-content;
      text-decoration: none;
      color: var(--slate-400);
      font-weight: 500;
      font-size: .8rem;
      letter-spacing: .02em;
      padding: 4px 0 2px;
      border-bottom: 1px solid transparent;
      transition: color .2s ease, border-color .2s ease;
    }}

    .journal-link:hover,
    .journal-link:focus-visible {{
      color: var(--accent);
      border-bottom-color: rgba(180,151,90,.4);
    }}

    .empty-state {{
      padding: 32px 20px;
      border-radius: var(--radius);
      border: 1.5px dashed var(--slate-200);
      background: var(--slate-100);
      color: var(--slate-400);
      font-style: italic;
      font-size: .9rem;
      text-align: center;
    }}

    /* ── Chart ────────────────────────────────────── */

    .chart-panel {{
      padding-bottom: 18px;
    }}

    .chart-panel svg {{
      display: block;
      width: 100%;
      max-width: 640px;
      height: auto;
    }}

    /* ── Footer ───────────────────────────────────── */

    .footer {{
      margin-top: 32px;
      text-align: center;
      color: var(--slate-400);
      font-size: .75rem;
      letter-spacing: .01em;
    }}

    /* ── Responsive ───────────────────────────────── */

    @media (max-width: 780px) {{
      .page {{ padding: 16px 14px 36px; }}
      .hero {{ padding: 24px 20px 22px; border-radius: var(--radius); }}
      .kpis {{ grid-template-columns: repeat(2, 1fr); }}
      .panel {{ padding: 16px; }}
      .section {{ margin-top: 18px; }}
      .card-grid {{ grid-template-columns: 1fr; }}
      .quest-card {{ min-height: 0; }}
    }}

    @media (max-width: 480px) {{
      .kpis {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero" aria-labelledby="dashboard-title">
      <h1 id="dashboard-title">Quest Dashboard</h1>
      <p class="subtitle">Executive summary of active and completed quests generated from repository artifacts.</p>
      <div class="kpis" role="list" aria-label="Dashboard metrics">
        <article class="kpi kpi-active" role="listitem">
          <div class="label">Active</div>
          <div class="value">{len(data.active_quests)}</div>
        </article>
        <article class="kpi kpi-complete" role="listitem">
          <div class="label">Completed</div>
          <div class="value">{len(data.completed_quests)}</div>
        </article>
        <article class="kpi kpi-blocked" role="listitem">
          <div class="label">Blocked</div>
          <div class="value">{blocked_count}</div>
        </article>
        <article class="kpi" role="listitem">
          <div class="label">Generated</div>
          <div class="value">{escape(generated_label)}</div>
        </article>
      </div>
    </section>

    {warning_banner}
    {chart_section}

    <section class="section" aria-labelledby="active-quests-heading">
      <div class="section-header">
        <h2 id="active-quests-heading">Active Quests</h2>
        <small>Sorted by last updated</small>
      </div>
      <div class="card-grid">
        {active_cards}
      </div>
    </section>

    <section class="section" aria-labelledby="completed-quests-heading">
      <div class="section-header">
        <h2 id="completed-quests-heading">Completed Quests</h2>
        <small>Includes completed and abandoned</small>
      </div>
      <div class="card-grid">
        {completed_cards}
      </div>
    </section>

    <footer class="footer">
      Generated {escape(generated_label)}
    </footer>
  </main>
</body>
</html>
"""


def _render_empty_state(message: str) -> str:
    return f'<article class="empty-state">{escape(message)}</article>'


def _render_active_card(record: ActiveQuestRecord) -> str:
    status_class = _status_badge_class(record.status)
    phase_class = _phase_css_class(record.phase)
    updated_label = _format_timestamp(record.updated_at)

    return (
        '<article class="quest-card active-card">'
        "<header>"
        "<div>"
        f"<h3>{escape(record.name)}</h3>"
        f'<p class="meta">Last Updated: {escape(updated_label)}</p>'
        "</div>"
        "</header>"
        '<div class="badge-row">'
        f'<span class="badge {status_class}">{escape(record.status)}</span>'
        f'<span class="phase-label {phase_class}">Phase: {escape(record.phase)}</span>'
        "</div>"
        f'<p class="pitch">{escape(record.elevator_pitch)}</p>'
        "</article>"
    )


def _render_completed_card(record: CompletedQuestRecord, output_path: Path, repo_root: Path, github_base_url: str = "") -> str:
    status_class = _status_badge_class(record.status)
    card_class = "abandoned-card" if "abandon" in record.status.lower() else "completed-card"
    if github_base_url:
        journal_posix = record.journal_path.as_posix()
        link = f"{github_base_url.rstrip('/')}/blob/main/{journal_posix}"
    else:
        link = _relative_link(output_path=output_path, repo_root=repo_root, target=record.journal_path)
    updated_label = record.updated_on.isoformat()

    return (
        f'<article class="quest-card {card_class}">'
        "<header>"
        "<div>"
        f"<h3>{escape(record.name)}</h3>"
        f'<p class="meta">Last Updated: {escape(updated_label)}</p>'
        "</div>"
        "</header>"
        '<div class="badge-row">'
        f'<span class="badge {status_class}">{escape(record.status)}</span>'
        "</div>"
        f'<p class="pitch">{escape(record.elevator_pitch)}</p>'
        f'<a class="journal-link" href="{escape(link)}">Open Journal &#8594;</a>'
        "</article>"
    )


# ── Badge helpers ─────────────────────────────────────


def _status_badge_class(status: str) -> str:
    s = status.strip().lower()
    if "abandon" in s:
        return "badge--abandoned"
    if "complete" in s or "done" in s:
        return "badge--completed"
    return "badge--active"


def _phase_css_class(phase: str) -> str:
    p = phase.strip().lower()
    if "plan" in p and "present" not in p:
        return "phase-plan"
    if "build" in p:
        return "phase-build"
    if "review" in p:
        return "phase-review"
    if "present" in p:
        return "phase-present"
    if "fix" in p:
        return "phase-fix"
    if "complete" in p or "done" in p:
        return "phase-complete"
    return ""


# ── Chart rendering ───────────────────────────────────


def _parse_date_from_quest_id(quest_id: str) -> date | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})__\d{4}", quest_id)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def _iso_week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _render_activity_chart(data: DashboardData) -> str:
    started_dates: list[date] = []
    completed_dates: list[date] = []

    for q in data.active_quests:
        d = _parse_date_from_quest_id(q.quest_id)
        if d:
            started_dates.append(d)

    for q in data.completed_quests:
        d = _parse_date_from_quest_id(q.quest_id)
        if d:
            started_dates.append(d)
        if q.updated_on and q.updated_on.year > 1970:
            completed_dates.append(q.updated_on)

    if not started_dates and not completed_dates:
        return ""

    started_by_week: dict[date, int] = defaultdict(int)
    completed_by_week: dict[date, int] = defaultdict(int)

    for d in started_dates:
        started_by_week[_iso_week_monday(d)] += 1
    for d in completed_dates:
        completed_by_week[_iso_week_monday(d)] += 1

    all_weeks = sorted(set(started_by_week.keys()) | set(completed_by_week.keys()))
    if not all_weeks:
        return ""

    filled_weeks: list[date] = []
    current = all_weeks[0]
    end = all_weeks[-1]
    while current <= end:
        filled_weeks.append(current)
        current += timedelta(weeks=1)

    n = len(filled_weeks)
    if n == 0:
        return ""

    max_val = max(
        max((started_by_week.get(w, 0) for w in filled_weeks), default=0),
        max((completed_by_week.get(w, 0) for w in filled_weeks), default=0),
    )
    if max_val == 0:
        return ""

    # Chart dimensions
    svg_w = 600
    svg_h = 170
    pad_l, pad_r, pad_t, pad_b = 28, 16, 20, 42
    chart_w = svg_w - pad_l - pad_r
    chart_h = svg_h - pad_t - pad_b
    group_w = chart_w / n
    bar_w = max(group_w * 0.32, 6)
    gap = max(group_w * 0.06, 2)
    base_y = pad_t + chart_h

    # Colors — one family: gold at two intensities, slate for structure
    c_started = "#b4975a"          # full accent gold
    c_started_ink = "#7d6a3e"
    c_completed = "#94a3b8"        # slate — the journey complete, faded
    c_completed_ink = "#64748b"
    c_grid = "#e2e8f0"
    c_axis = "#cbd5e1"
    c_label = "#94a3b8"

    parts: list[str] = [
        f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg"'
        f' style="font-family:inherit;" role="img" aria-label="Quest activity chart">'
    ]

    # Gridlines
    for i in range(5):
        y = pad_t + chart_h * i / 4
        parts.append(f'<line x1="{pad_l}" y1="{y:.0f}" x2="{svg_w - pad_r}" y2="{y:.0f}" stroke="{c_grid}" stroke-width=".5"/>')

    parts.append(f'<line x1="{pad_l}" y1="{base_y}" x2="{svg_w - pad_r}" y2="{base_y}" stroke="{c_axis}" stroke-width="1"/>')

    for i, week in enumerate(filled_weeks):
        cx = pad_l + group_w * i + group_w / 2
        s_val = started_by_week.get(week, 0)
        c_val = completed_by_week.get(week, 0)

        if s_val > 0:
            h = (s_val / max_val) * chart_h
            x = cx - bar_w - gap / 2
            y = base_y - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2.5" fill="{c_started}" opacity=".78"/>')
            parts.append(f'<text x="{x + bar_w/2:.1f}" y="{y - 4:.1f}" text-anchor="middle" fill="{c_started_ink}" font-size="9.5" font-weight="600">{s_val}</text>')

        if c_val > 0:
            h = (c_val / max_val) * chart_h
            x = cx + gap / 2
            y = base_y - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="2.5" fill="{c_completed}" opacity=".78"/>')
            parts.append(f'<text x="{x + bar_w/2:.1f}" y="{y - 4:.1f}" text-anchor="middle" fill="{c_completed_ink}" font-size="9.5" font-weight="600">{c_val}</text>')

        iso_week = week.isocalendar()[1]
        parts.append(f'<text x="{cx:.1f}" y="{base_y + 15:.0f}" text-anchor="middle" fill="{c_label}" font-size="9.5">W{iso_week:02d}</text>')

    # Legend
    ly = svg_h - 8
    parts.append(f'<rect x="{pad_l}" y="{ly - 8}" width="9" height="9" rx="2" fill="{c_started}" opacity=".78"/>')
    parts.append(f'<text x="{pad_l + 13}" y="{ly}" fill="{c_label}" font-size="9.5">Started</text>')
    parts.append(f'<rect x="{pad_l + 68}" y="{ly - 8}" width="9" height="9" rx="2" fill="{c_completed}" opacity=".78"/>')
    parts.append(f'<text x="{pad_l + 81}" y="{ly}" fill="{c_label}" font-size="9.5">Completed</text>')

    parts.append("</svg>")
    return "\n    ".join(parts)


# ── Utilities ─────────────────────────────────────────


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _format_generated_at(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _relative_link(output_path: Path, repo_root: Path, target: Path) -> str:
    output_parent = output_path.resolve().parent
    target_path = (repo_root / target).resolve()
    try:
        relative = os.path.relpath(target_path, output_parent)
    except ValueError:
        relative = target_path.as_posix()
    return relative.replace(os.sep, "/")
