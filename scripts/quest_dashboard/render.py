"""HTML rendering for the Quest Dashboard.

This module generates a self-contained HTML file with:
- Inline CSS (dark navy theme from PR #21)
- Three status sections: Finished, In Progress, Abandoned
- Quest cards with title, elevator pitch, journal links, and metadata
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime
from pathlib import Path

from .models import ActiveQuest, DashboardData, JournalEntry


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
    hero = _render_hero(data)
    finished_section = _render_finished_section(
        data.finished_quests, data.github_repo_url, output_path, repo_root
    )
    active_section = _render_active_section(data.active_quests)
    abandoned_section = _render_abandoned_section(
        data.abandoned_quests, data.github_repo_url, output_path, repo_root
    )
    warnings_html = _render_warnings(data.warnings)
    footer = _render_footer(data.generated_at)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quest Dashboard</title>
  <style>
{css}
  </style>
</head>
<body>
  <div class="container">
{hero}
{finished_section}
{active_section}
{abandoned_section}
{warnings_html}
{footer}
  </div>
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
      --line: rgba(148, 163, 184, 0.22);
      --text-0: #f8fafc;
      --text-1: #cbd5e1;
      --text-2: #94a3b8;
      --status-finished: #34d399;
      --status-in-progress: #60a5fa;
      --status-blocked: #f59e0b;
      --status-abandoned: #f87171;
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
      background: radial-gradient(ellipse at top, var(--bg-1), var(--bg-0));
      color: var(--text-0);
      line-height: 1.6;
      min-height: 100vh;
      padding: 2rem 1rem;
    }

    .container {
      max-width: 1400px;
      margin: 0 auto;
    }

    /* Hero section */
    .hero {
      background: var(--surface-0);
      backdrop-filter: blur(12px);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 3rem 2rem;
      margin-bottom: 3rem;
      box-shadow: var(--shadow-lg);
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
      margin-bottom: 2rem;
    }

    .kpi-row {
      display: flex;
      gap: 2rem;
      flex-wrap: wrap;
    }

    .kpi-item {
      display: flex;
      flex-direction: column;
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
      font-weight: 700;
      color: var(--text-0);
    }

    .kpi-value--finished {
      color: var(--status-finished);
    }

    .kpi-value--in-progress {
      color: var(--status-in-progress);
    }

    .kpi-value--abandoned {
      color: var(--status-abandoned);
    }

    /* Section headings */
    .section {
      margin-bottom: 3rem;
    }

    .section-header {
      margin-bottom: 1.5rem;
    }

    .section-title {
      font-size: 1.875rem;
      font-weight: 700;
      color: var(--text-0);
      margin-bottom: 0.25rem;
    }

    .section-subtitle {
      font-size: 1rem;
      color: var(--text-2);
    }

    /* Quest cards grid */
    .quest-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.5rem;
    }

    .quest-card {
      background: var(--surface-1);
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .quest-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-lg);
    }

    .quest-card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      margin-bottom: 1rem;
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

    .quest-pitch {
      font-size: 0.9375rem;
      color: var(--text-1);
      margin-bottom: 1rem;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .journal-link {
      color: var(--status-in-progress);
      text-decoration: none;
      font-weight: 500;
      margin-bottom: 1rem;
      display: inline-block;
    }

    .journal-link:hover {
      text-decoration: underline;
    }

    .quest-meta {
      border-top: 1px solid var(--line);
      padding-top: 0.75rem;
      margin-top: auto;
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      font-size: 0.8125rem;
      color: var(--text-2);
    }

    .meta-item {
      display: inline-block;
    }

    .meta-link {
      color: var(--text-2);
      text-decoration: none;
    }

    .meta-link:hover {
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

    /* Responsive */
    @media (max-width: 768px) {
      .hero h1 {
        font-size: 2rem;
      }

      .kpi-row {
        gap: 1.5rem;
      }

      .section-title {
        font-size: 1.5rem;
      }

      .quest-grid {
        grid-template-columns: 1fr;
      }
    }"""


def _render_hero(data: DashboardData) -> str:
    """Render the hero section with title and KPIs."""
    finished_count = len(data.finished_quests)
    active_count = len(data.active_quests)
    abandoned_count = len(data.abandoned_quests)

    return f"""    <div class="hero">
      <h1>Quest Dashboard</h1>
      <div class="hero-subtitle">Quest status and progress tracking</div>
      <div class="kpi-row">
        <div class="kpi-item">
          <div class="kpi-label">Finished</div>
          <div class="kpi-value kpi-value--finished">{finished_count}</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-label">In Progress</div>
          <div class="kpi-value kpi-value--in-progress">{active_count}</div>
        </div>
        <div class="kpi-item">
          <div class="kpi-label">Abandoned</div>
          <div class="kpi-value kpi-value--abandoned">{abandoned_count}</div>
        </div>
      </div>
    </div>"""


def _render_finished_section(
    quests: list[JournalEntry],
    github_url: str,
    output_path: Path,
    repo_root: Path,
) -> str:
    """Render the Finished quests section."""
    return _render_journal_section(
        title="Finished",
        subtitle=f"{len(quests)} completed quest{'s' if len(quests) != 1 else ''}",
        section_id="finished-quests",
        quests=quests,
        badge_class="finished",
        github_url=github_url,
        output_path=output_path,
        repo_root=repo_root,
    )


def _render_abandoned_section(
    quests: list[JournalEntry],
    github_url: str,
    output_path: Path,
    repo_root: Path,
) -> str:
    """Render the Abandoned quests section."""
    return _render_journal_section(
        title="Abandoned",
        subtitle=f"{len(quests)} abandoned quest{'s' if len(quests) != 1 else ''}",
        section_id="abandoned-quests",
        quests=quests,
        badge_class="abandoned",
        github_url=github_url,
        output_path=output_path,
        repo_root=repo_root,
    )


def _render_journal_section(
    title: str,
    subtitle: str,
    section_id: str,
    quests: list[JournalEntry],
    badge_class: str,
    github_url: str,
    output_path: Path,
    repo_root: Path,
) -> str:
    """Render a section for journal-based quests (finished or abandoned)."""
    if not quests:
        cards_html = '      <div class="empty-state">No quests in this category</div>'
    else:
        cards = [
            _render_journal_card(q, badge_class, github_url, output_path, repo_root)
            for q in quests
        ]
        cards_html = (
            f'      <div class="quest-grid">\n' + "\n".join(cards) + "\n      </div>"
        )

    return f"""    <section class="section" id="{section_id}">
      <div class="section-header">
        <h2 class="section-title">{title}</h2>
        <div class="section-subtitle">{subtitle}</div>
      </div>
{cards_html}
    </section>"""


def _render_journal_card(
    entry: JournalEntry,
    badge_class: str,
    github_url: str,
    output_path: Path,
    repo_root: Path,
) -> str:
    """Render a single quest card for a journal entry."""
    journal_link = _compute_journal_link(
        entry.journal_path, github_url, output_path, repo_root
    )

    # Format metadata items -- AC #6: show quest_id in muted metadata
    meta_items = [f'<span class="meta-item">{html.escape(entry.quest_id)}</span>']
    meta_items.append(
        f'<span class="meta-item">{entry.completed_date.strftime("%b %d, %Y")}</span>'
    )

    # Add iterations if available
    if entry.plan_iterations is not None or entry.fix_iterations is not None:
        plan = entry.plan_iterations or 0
        fix = entry.fix_iterations or 0
        meta_items.append(f'<span class="meta-item">plan {plan} / fix {fix}</span>')

    # Add PR link if available
    if entry.pr_number:
        pr_link = _compute_pr_link(entry.pr_number, github_url)
        meta_items.append(
            f'<a href="{pr_link}" class="meta-link">PR #{entry.pr_number}</a>'
        )

    meta_html = "\n        ".join(meta_items)

    return f"""        <article class="quest-card">
          <div class="quest-card-header">
            <h3 class="quest-card-title">{html.escape(entry.title)}</h3>
            <span class="badge badge--{badge_class}">{html.escape(entry.status)}</span>
          </div>
          <p class="quest-pitch">{html.escape(entry.elevator_pitch)}</p>
          <a href="{journal_link}" class="journal-link">View Journal &rarr;</a>
          <div class="quest-meta">
        {meta_html}
          </div>
        </article>"""


def _render_active_section(quests: list[ActiveQuest]) -> str:
    """Render the In Progress quests section."""
    if not quests:
        cards_html = '      <div class="empty-state">No quests in this category</div>'
    else:
        cards = [_render_active_card(q) for q in quests]
        cards_html = (
            f'      <div class="quest-grid">\n' + "\n".join(cards) + "\n      </div>"
        )

    return f"""    <section class="section" id="in-progress-quests">
      <div class="section-header">
        <h2 class="section-title">In Progress</h2>
        <div class="section-subtitle">{len(quests)} active quest{'s' if len(quests) != 1 else ''}</div>
      </div>
{cards_html}
    </section>"""


def _render_active_card(quest: ActiveQuest) -> str:
    """Render a single quest card for an active quest."""
    # Determine badge class from status
    status_lower = quest.status.lower().replace(" ", "-")
    if "block" in status_lower:
        badge_class = "blocked"
    else:
        badge_class = "in-progress"

    # Format metadata items -- AC #6: show quest_id in muted metadata
    meta_items = [f'<span class="meta-item">{html.escape(quest.quest_id)}</span>']
    meta_items.append(f'<span class="meta-item">{html.escape(quest.phase)}</span>')
    meta_items.append(
        f'<span class="meta-item">{quest.updated_at.strftime("%b %d, %Y")}</span>'
    )

    # Add iterations if available
    if quest.plan_iterations is not None or quest.fix_iterations is not None:
        plan = quest.plan_iterations or 0
        fix = quest.fix_iterations or 0
        meta_items.append(f'<span class="meta-item">plan {plan} / fix {fix}</span>')

    meta_html = "\n        ".join(meta_items)

    return f"""        <article class="quest-card">
          <div class="quest-card-header">
            <h3 class="quest-card-title">{html.escape(quest.title)}</h3>
            <span class="badge badge--{badge_class}">{html.escape(quest.status)}</span>
          </div>
          <p class="quest-pitch">{html.escape(quest.elevator_pitch)}</p>
          <div class="quest-meta">
        {meta_html}
          </div>
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


def _compute_journal_link(
    journal_path: Path, github_url: str, output_path: Path, repo_root: Path
) -> str:
    """Compute the link to a journal file.

    Prefers GitHub blob URL if github_url is available.
    Falls back to relative path from output location.

    Args:
        journal_path: Path to journal file (relative to repo root)
        github_url: GitHub repository URL or empty string
        output_path: Where the dashboard HTML will be written
        repo_root: Repository root

    Returns:
        URL or relative path to journal file
    """
    if github_url:
        # Use GitHub blob URL, validated and escaped
        sanitized = _sanitize_url(f"{github_url}/blob/main/{journal_path.as_posix()}")
        if sanitized:
            return sanitized
        # If sanitization fails, fall through to relative-path fallback

    # Fallback to relative path from output location to repo root
    try:
        output_dir = output_path.parent.resolve()
        repo_resolved = repo_root.resolve()
        rel_to_root = Path(os.path.relpath(repo_resolved, output_dir))
        rel_path = rel_to_root / journal_path
        return html.escape(rel_path.as_posix())
    except ValueError:
        # On Windows, relpath fails across drives; fall back to ../../
        rel_path = Path("../..") / journal_path
        return html.escape(rel_path.as_posix())


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


