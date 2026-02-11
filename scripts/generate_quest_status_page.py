#!/usr/bin/env python3
"""Generate a static quest status dashboard page from .quest artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path
from typing import Any

NOT_AVAILABLE = "Not available"
DEFAULT_JOURNAL_DIR = "docs/quest-journal"
DEFAULT_REPO_URL = ""

# Pattern: quest IDs end with _YYYY-MM-DD__HHMM
_QUEST_ID_TIMESTAMP_RE = re.compile(r"_\d{4}-\d{2}-\d{2}__\d{4}$")


def _slug_from_quest_id(quest_id: str) -> str:
    """Extract the slug portion from a quest ID by stripping the timestamp suffix."""
    return _QUEST_ID_TIMESTAMP_RE.sub("", quest_id)


def find_journal_entry(quest_id: str, journal_dir: Path) -> Path | None:
    """Find the journal entry file for a quest by matching its slug prefix."""
    if not journal_dir.is_dir():
        return None
    slug = _slug_from_quest_id(quest_id)
    if not slug:
        return None
    for entry in journal_dir.iterdir():
        if entry.is_file() and entry.name.startswith(slug) and entry.suffix == ".md":
            return entry
    return None


def parse_journal_summary(path: Path) -> str:
    """Extract the ## Summary section from a quest journal entry."""
    if not path.is_file():
        return ""
    try:
        markdown = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""
    sections = _split_sections(markdown)
    return sections.get("summary", "").strip()


def discover_quest_dirs(quest_root: Path) -> list[Path]:
    """Return valid quest directories from active and archive roots."""
    roots = [quest_root]
    archive_root = quest_root / "archive"
    if archive_root.is_dir():
        roots.append(archive_root)

    discovered: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            if (entry / "state.json").is_file() and (entry / "quest_brief.md").is_file():
                discovered.append(entry)
    return discovered


def _default_state(path: Path) -> dict[str, Any]:
    return {
        "quest_id": path.parent.name,
        "phase": NOT_AVAILABLE,
        "status": "unknown",
        "plan_iteration": None,
        "fix_iteration": None,
        "last_role": NOT_AVAILABLE,
        "last_verdict": NOT_AVAILABLE,
        "created_at": "",
        "updated_at": "",
        "warnings": [],
    }


def load_state(path: Path) -> dict[str, Any]:
    """Load a quest state file with resilient defaults."""
    state = _default_state(path)

    if not path.is_file():
        state["warnings"].append(f"Missing state.json: {path}")
        return state

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        state["warnings"].append(f"Invalid state.json at {path}: {exc}")
        return state

    if not isinstance(raw, dict):
        state["warnings"].append(f"Invalid state.json structure at {path}: expected object")
        return state

    for key in (
        "quest_id",
        "phase",
        "status",
        "plan_iteration",
        "fix_iteration",
        "last_role",
        "last_verdict",
        "created_at",
        "updated_at",
    ):
        value = raw.get(key)
        if value is None:
            continue
        if key in ("plan_iteration", "fix_iteration"):
            state[key] = value
        else:
            state[key] = str(value).strip() or state[key]
    return state


def _first_heading_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            match = re.match(r"^Quest Brief:\s*(.+)$", title, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return title
    return ""


def _split_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in markdown.splitlines():
        section_match = re.match(r"^##\s+(.+?)\s*$", line)
        if section_match:
            current = section_match.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}


def _replace_code_fences(markdown: str) -> str:
    def repl(match: re.Match[str]) -> str:
        content = match.group(1) or ""
        return content.strip()

    return re.sub(r"```(?:[^\n]*\n)?(.*?)```", repl, markdown, flags=re.DOTALL)


def _paragraphs(markdown: str) -> list[str]:
    text = _replace_code_fences(markdown)
    blocks: list[str] = []
    chunk: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if chunk:
                blocks.append(" ".join(chunk).strip())
                chunk = []
            continue
        if line.startswith("#"):
            if chunk:
                blocks.append(" ".join(chunk).strip())
                chunk = []
            continue
        chunk.append(line)
    if chunk:
        blocks.append(" ".join(chunk).strip())
    return [block for block in blocks if block]


def _first_paragraph(markdown: str, skip_json_like: bool = True) -> str:
    for paragraph in _paragraphs(markdown):
        cleaned = paragraph.strip()
        if skip_json_like and (cleaned.startswith("{") or cleaned.startswith("[")):
            continue
        return cleaned
    return ""


def parse_quest_brief(path: Path) -> dict[str, str]:
    """Extract title, elevator pitch, and description from quest_brief.md."""
    default = {
        "title": path.parent.name,
        "elevator_pitch": NOT_AVAILABLE,
        "description": NOT_AVAILABLE,
        "original_request": NOT_AVAILABLE,
    }
    if not path.is_file():
        return default

    try:
        markdown = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return default

    title = _first_heading_title(markdown) or default["title"]
    sections = _split_sections(markdown)

    pitch_priorities = (
        "user input (original prompt)",
        "user input",
        "original prompt",
        "user request",
    )
    pitch = ""
    for heading in pitch_priorities:
        section = sections.get(heading, "")
        pitch = _first_paragraph(section)
        if pitch:
            break

    desc_priorities = ("goal", "objective", "problem", "context")
    description = ""
    for heading in desc_priorities:
        section = sections.get(heading, "")
        description = _first_paragraph(section)
        if description:
            break

    if not description:
        body_after_title = "\n".join(markdown.splitlines()[1:])
        description = _first_paragraph(body_after_title)

    return {
        "title": title or default["title"],
        "elevator_pitch": pitch or NOT_AVAILABLE,
        "description": description or NOT_AVAILABLE,
        "original_request": pitch or NOT_AVAILABLE,
    }


def sanitize_anchor(quest_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", quest_id).strip("-").lower()
    return f"quest-{safe or 'unknown'}"


def _safe_anchor(anchor: Any, quest_id: Any) -> str:
    raw = str(anchor).strip() if anchor is not None else ""
    if not raw:
        return sanitize_anchor(str(quest_id or "unknown"))

    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    if not safe:
        return sanitize_anchor(str(quest_id or "unknown"))
    if not safe.startswith("quest-"):
        safe = f"quest-{safe}"
    return safe


def load_quests(quest_root: Path, journal_dir: Path | None = None) -> list[dict[str, Any]]:
    quests: list[dict[str, Any]] = []
    used_anchors: set[str] = set()
    for quest_dir in discover_quest_dirs(quest_root):
        state = load_state(quest_dir / "state.json")
        brief = parse_quest_brief(quest_dir / "quest_brief.md")
        quest_id = str(state.get("quest_id") or quest_dir.name)
        status = str(state.get("status") or "unknown").strip().lower()

        # For finished quests, try to get the journal summary as the elevator pitch
        elevator_pitch = brief["elevator_pitch"]
        journal_filename = ""
        if journal_dir is not None:
            journal_path = find_journal_entry(quest_id, journal_dir)
            if journal_path is not None:
                journal_filename = journal_path.name
                if status == "complete":
                    journal_summary = parse_journal_summary(journal_path)
                    if journal_summary:
                        elevator_pitch = journal_summary

        base_anchor = sanitize_anchor(quest_id)
        anchor = base_anchor
        suffix = 2
        while anchor in used_anchors:
            anchor = f"{base_anchor}-{suffix}"
            suffix += 1
        used_anchors.add(anchor)
        quests.append(
            {
                "quest_id": quest_id,
                "phase": str(state.get("phase") or NOT_AVAILABLE),
                "status": str(state.get("status") or "unknown"),
                "plan_iteration": state.get("plan_iteration"),
                "fix_iteration": state.get("fix_iteration"),
                "last_role": str(state.get("last_role") or NOT_AVAILABLE),
                "last_verdict": str(state.get("last_verdict") or NOT_AVAILABLE),
                "created_at": str(state.get("created_at") or ""),
                "updated_at": str(state.get("updated_at") or ""),
                "title": brief["title"],
                "elevator_pitch": elevator_pitch,
                "description": brief["description"],
                "original_request": brief["original_request"],
                "anchor": anchor,
                "artifact_path": quest_dir.as_posix(),
                "journal_filename": journal_filename,
                "warnings": list(state.get("warnings", [])),
            }
        )
    return quests


_PHASE_ORDER = {
    "complete": 0, "done": 0,
    "reviewing": 1, "code_review": 1, "presentation_complete": 1,
    "fixing": 2,
    "building": 3, "implementing": 3,
    "presenting": 4,
    "plan": 5, "pending": 5,
}


def _phase_rank(quest: dict[str, Any]) -> int:
    phase = str(quest.get("phase") or "").strip().lower()
    return _PHASE_ORDER.get(phase, 6)


def _date_key(quest: dict[str, Any]) -> str:
    return str(quest.get("updated_at") or quest.get("created_at") or "")


def build_dashboard_model(quests: list[dict[str, Any]]) -> dict[str, Any]:
    ongoing: list[dict[str, Any]] = []
    finished: list[dict[str, Any]] = []
    blocked_count = 0
    warnings: list[str] = []

    for quest in quests:
        warnings.extend(quest.get("warnings", []))
        status = str(quest.get("status") or "").strip().lower()
        if status == "blocked":
            blocked_count += 1
        if status == "complete":
            finished.append(quest)
        else:
            ongoing.append(quest)

    # Sort by phase rank (building before plan), then most recent first within each phase
    ongoing_sorted = sorted(sorted(ongoing, key=_date_key, reverse=True), key=_phase_rank)
    finished_sorted = sorted(finished, key=_date_key, reverse=True)
    return {
        "ongoing": ongoing_sorted,
        "finished": finished_sorted,
        "counts": {
            "ongoing": len(ongoing_sorted),
            "finished": len(finished_sorted),
            "blocked": blocked_count,
        },
        "warnings": warnings,
    }


def _escape(value: Any) -> str:
    if value is None:
        return html.escape(NOT_AVAILABLE, quote=True)
    text = str(value).strip()
    if not text:
        text = NOT_AVAILABLE
    return html.escape(text, quote=True)


def _humanize_title(title: str, quest_id: str) -> str:
    """Return a human-readable title. If the title is just a slug, title-case it."""
    slug = _slug_from_quest_id(quest_id) or quest_id
    # If the title is a real human-written title (has spaces, mixed case), keep it
    if title and title != quest_id and title != slug and not title.startswith(".quest/"):
        return title
    # Otherwise humanize from the slug
    return slug.replace("-", " ").replace("_", " ").title()


def _format_date(iso_str: str) -> str:
    """Convert ISO timestamp to human-readable date like 'Feb 10, 2026'."""
    if not iso_str:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return parsed.strftime("%b %-d, %Y")
    except (ValueError, AttributeError):
        return iso_str


_PHASE_DISPLAY = {
    "plan": ("Plan", "phase-plan"),
    "pending": ("Plan", "phase-plan"),
    "building": ("Building", "phase-build"),
    "implementing": ("Building", "phase-build"),
    "reviewing": ("Under Review", "phase-review"),
    "code_review": ("Under Review", "phase-review"),
    "presentation_complete": ("Under Review", "phase-review"),
    "presenting": ("Under Review", "phase-review"),
    "fixing": ("Fixing", "phase-fix"),
    "complete": ("Complete", "phase-done"),
    "done": ("Complete", "phase-done"),
}


def _phase_label_and_class(phase: str) -> tuple[str, str]:
    """Return (display label, CSS class) for a phase."""
    p = phase.strip().lower().replace(" ", "_")
    return _PHASE_DISPLAY.get(p, (phase.replace("_", " ").title(), "phase-plan"))


def _render_timeline_svg(model: dict[str, Any]) -> str:
    """Render an inline SVG timeline chart showing quest activity by week."""
    all_quests = model["ongoing"] + model["finished"]
    if not all_quests:
        return ""

    # Collect weekly buckets: {iso_week: {"started": n, "completed": n}}
    weeks: dict[str, dict[str, int]] = {}
    for quest in all_quests:
        created = quest.get("created_at", "")
        updated = quest.get("updated_at", "")
        status = str(quest.get("status", "")).strip().lower()
        if created:
            try:
                d = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
                key = d.strftime("%Y-W%W")
                weeks.setdefault(key, {"started": 0, "completed": 0})
                weeks[key]["started"] += 1
            except ValueError:
                pass
        if status == "complete" and updated:
            try:
                d = dt.datetime.fromisoformat(updated.replace("Z", "+00:00"))
                key = d.strftime("%Y-W%W")
                weeks.setdefault(key, {"started": 0, "completed": 0})
                weeks[key]["completed"] += 1
            except ValueError:
                pass

    if not weeks:
        return ""

    sorted_weeks = sorted(weeks.keys())
    n = len(sorted_weeks)

    # Chart dimensions
    chart_w = 600
    chart_h = 160
    pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 40
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    max_val = max(max(w["started"], w["completed"]) for w in weeks.values())
    if max_val == 0:
        max_val = 1

    bar_group_w = plot_w / max(n, 1)
    bar_w = bar_group_w * 0.35

    bars = []
    labels = []
    for i, wk in enumerate(sorted_weeks):
        data = weeks[wk]
        x_center = pad_l + i * bar_group_w + bar_group_w / 2

        # Started bar (amber)
        sh = (data["started"] / max_val) * plot_h
        sy = pad_t + plot_h - sh
        sx = x_center - bar_w - 1
        bars.append(f'<rect x="{sx:.1f}" y="{sy:.1f}" width="{bar_w:.1f}" height="{sh:.1f}" rx="3" fill="#f59e0b" opacity="0.85"/>')
        if data["started"] > 0:
            bars.append(f'<text x="{sx + bar_w/2:.1f}" y="{sy - 4:.1f}" text-anchor="middle" fill="#92400e" font-size="11" font-weight="600">{data["started"]}</text>')

        # Completed bar (green)
        ch = (data["completed"] / max_val) * plot_h
        cy = pad_t + plot_h - ch
        cx = x_center + 1
        bars.append(f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{bar_w:.1f}" height="{ch:.1f}" rx="3" fill="#10b981" opacity="0.85"/>')
        if data["completed"] > 0:
            bars.append(f'<text x="{cx + bar_w/2:.1f}" y="{cy - 4:.1f}" text-anchor="middle" fill="#065f46" font-size="11" font-weight="600">{data["completed"]}</text>')

        # Week label
        short_label = wk.split("-")[1] if "-" in wk else wk
        labels.append(f'<text x="{x_center:.1f}" y="{pad_t + plot_h + 16:.1f}" text-anchor="middle" fill="#5c706e" font-size="11">{_escape(short_label)}</text>')

    # Y-axis line
    axis = f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" stroke="#d6ddd8" stroke-width="1"/>'
    baseline = f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" stroke="#d6ddd8" stroke-width="1"/>'

    # Legend
    legend_y = pad_t + plot_h + 32
    legend = (
        f'<rect x="{pad_l}" y="{legend_y}" width="10" height="10" rx="2" fill="#f59e0b"/>'
        f'<text x="{pad_l + 14}" y="{legend_y + 9}" fill="#5c706e" font-size="11">Started</text>'
        f'<rect x="{pad_l + 70}" y="{legend_y}" width="10" height="10" rx="2" fill="#10b981"/>'
        f'<text x="{pad_l + 84}" y="{legend_y + 9}" fill="#5c706e" font-size="11">Completed</text>'
    )

    total_h = chart_h + 20
    svg_body = "\n    ".join([axis, baseline] + bars + labels + [legend])
    return f'''<svg viewBox="0 0 {chart_w} {total_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{chart_w}px;height:auto;font-family:inherit;">
    {svg_body}
  </svg>'''


def render_html(model: dict[str, Any], generated_at: str, repo_url: str = "") -> str:
    journal_base = repo_url.rstrip("/") + "/blob/main/docs/quest-journal/" if repo_url else ""

    # --- Ongoing cards ---
    ongoing_cards = []
    for quest in model["ongoing"]:
        title = _humanize_title(quest["title"], quest["quest_id"])
        phase_label, phase_cls = _phase_label_and_class(quest["phase"])
        date_str = _format_date(quest["updated_at"])
        pitch = quest.get("elevator_pitch", "")
        pitch_display = pitch if pitch and pitch != NOT_AVAILABLE else quest.get("description", "")
        if pitch_display == NOT_AVAILABLE:
            pitch_display = ""

        ongoing_cards.append(
            f'''<article class="card ongoing-card">
              <div class="card-top">
                <h3>{_escape(title)}</h3>
                <span class="badge {phase_cls}">{_escape(phase_label)}</span>
              </div>
              {f'<p class="pitch">{_escape(pitch_display)}</p>' if pitch_display else ''}
              <div class="card-foot"><span class="id-chip">{_escape(quest["quest_id"])}</span><span class="meta">{_escape(date_str)}</span></div>
            </article>'''
        )
    ongoing_html = "\n".join(ongoing_cards) or '<article class="empty-state">No ongoing quests.</article>'

    # --- Finished cards + details ---
    finished_cards = []
    finished_details = []
    for quest in model["finished"]:
        anchor = _safe_anchor(quest.get("anchor"), quest.get("quest_id"))
        title = _humanize_title(quest["title"], quest["quest_id"])
        date_str = _format_date(quest["updated_at"])
        jf = quest.get("journal_filename", "")
        journal_link = ""
        if jf and journal_base:
            journal_link = f'<a class="journal-link" href="{_escape(journal_base + jf)}">Open Journal</a>'
        elif jf:
            journal_link = f'<a class="journal-link" href="#{_escape(anchor)}">View Details</a>'

        finished_cards.append(
            f'''<article class="card finished-card">
              <div class="card-top">
                <h3>{_escape(title)}</h3>
                <span class="badge phase-done">Complete</span>
              </div>
              <p class="pitch">{_escape(quest["elevator_pitch"])}</p>
              <div class="card-foot"><span class="id-chip">{_escape(quest["quest_id"])}</span><span class="meta">{_escape(date_str)}</span></div>
              {journal_link}
            </article>'''
        )
        finished_details.append(
            f'''<details id="{_escape(anchor)}" class="detail-card">
              <summary><strong>{_escape(title)}</strong></summary>
              <p class="detail-body">{_escape(quest["elevator_pitch"])}</p>
              <p class="detail-request"><strong>Original request:</strong> {_escape(quest["original_request"])}</p>
              <p class="meta"><code>{_escape(quest["quest_id"])}</code> &middot; Completed {_escape(date_str)}</p>
            </details>'''
        )
    finished_html = "\n".join(finished_cards) or '<article class="empty-state">No completed quests yet.</article>'
    details_html = "\n".join(finished_details) or "<p>No quest details available.</p>"

    # --- Timeline chart ---
    timeline_svg = _render_timeline_svg(model)
    timeline_section = ""
    if timeline_svg:
        timeline_section = f'''<section class="section" aria-labelledby="activity-heading">
      <div class="section-head"><h2 id="activity-heading">Quest Activity</h2><small>Quests started vs completed by week</small></div>
      {timeline_svg}
    </section>'''

    # --- Warnings ---
    warnings = model.get("warnings", [])
    warning_html = ""
    if warnings:
        warning_html = (
            '<div class="warning-panel"><h2>Warnings</h2><ul>'
            + "".join(f"<li>{_escape(warn)}</li>" for warn in warnings)
            + "</ul></div>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quest Status Dashboard</title>
  <style>
    :root {{
      --bg: #f4f4ef;
      --bg-accent: #ecf1ea;
      --ink: #121619;
      --muted: #4f5e59;
      --surface: rgba(255,255,255,0.86);
      --surface-solid: #ffffff;
      --stroke: rgba(18,22,25,0.08);
      --accent: #4338ca;
      --green: #0b8f53;
      --green-light: #ecfdf5;
      --green-border: #a7f3d0;
      --amber: #b45309;
      --amber-light: #fffbeb;
      --amber-border: #fde68a;
      --red: #dc2626;
      --red-light: #fef2f2;
      --red-border: #fecaca;
      --blue: #2563eb;
      --blue-light: #eff6ff;
      --blue-border: #bfdbfe;
      --purple: #7c3aed;
      --purple-light: #f5f3ff;
      --purple-border: #c4b5fd;
      --teal: #0891b2;
      --teal-light: #ecfeff;
      --teal-border: #a5f3fc;
      --shadow-sm: 0 1px 3px rgba(18,22,25,0.06);
      --shadow-md: 0 8px 24px rgba(18,22,25,0.09);
      --shadow-hero: 0 20px 60px rgba(18,22,25,0.16);
      --font: "Avenir Next","Segoe UI",system-ui,sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh;
      font-family: var(--font);
      color: var(--ink);
      background:
        radial-gradient(circle at 80% 10%, #fff6e0 0%, rgba(255,246,224,0) 40%),
        radial-gradient(circle at 8% 90%, #dceee8 0%, rgba(220,238,232,0) 42%),
        linear-gradient(180deg, var(--bg) 0%, var(--bg-accent) 100%);
      line-height: 1.5;
    }}
    .page {{ max-width: 1120px; margin: 0 auto; padding: 24px 20px 48px; }}

    /* ── Hero ── */
    .hero {{
      background:
        radial-gradient(circle at 10% -10%, #f6d49f 0%, rgba(246,212,159,0) 48%),
        radial-gradient(circle at 90% 0%, #91c9ff 0%, rgba(145,201,255,0) 50%),
        linear-gradient(160deg, #0e1a25 0%, #162838 40%, #243850 100%);
      border-radius: 20px; color: #f8fbff;
      padding: 28px; position: relative; overflow: hidden;
      box-shadow: var(--shadow-hero);
    }}
    .hero::after {{
      content: ""; position: absolute; width: 220px; height: 220px;
      border-radius: 999px; right: -40px; top: -60px;
      background: rgba(255,255,255,0.10); filter: blur(4px);
    }}
    .hero h1 {{
      margin: 0; font-size: clamp(1.7rem,3.2vw,2.6rem);
      font-weight: 700; letter-spacing: 0.01em; position: relative; z-index: 1;
    }}
    .hero .subtitle {{
      max-width: 60ch; margin: 6px 0 0; font-size: .95rem;
      color: rgba(248,251,255,0.85); position: relative; z-index: 1;
    }}
    .metrics {{
      margin-top: 18px; display: grid; gap: 12px;
      grid-template-columns: repeat(3, minmax(0,1fr));
      position: relative; z-index: 1;
    }}
    .metric {{
      background: rgba(255,255,255,0.13);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 14px; padding: 12px 14px;
      backdrop-filter: blur(2px);
    }}
    .metric .label {{
      font-size: .74rem; text-transform: uppercase;
      letter-spacing: .08em; color: rgba(248,251,255,0.72);
    }}
    .metric .value {{
      margin-top: 2px; font-size: clamp(1.5rem,2.6vw,2rem);
      font-weight: 700; color: #ffffff;
    }}

    /* ── Sections ── */
    .section {{ margin-top: 28px; }}
    .section-head {{
      display: flex; align-items: baseline;
      justify-content: space-between; gap: 12px;
      margin-bottom: 12px;
    }}
    .section-head h2 {{
      margin: 0; font-size: clamp(1.2rem,2.4vw,1.7rem);
      font-weight: 700; letter-spacing: 0.01em;
    }}
    .section-head small {{ color: var(--muted); font-size: .84rem; }}
    section.section {{
      background: var(--surface-solid);
      border: 1px solid var(--stroke);
      border-radius: 16px;
      padding: 20px; margin-top: 16px;
    }}

    /* ── Badges ── */
    .badge {{
      display: inline-flex; align-items: center;
      border-radius: 999px; padding: 4px 10px;
      font-size: .72rem; font-weight: 700;
      letter-spacing: .04em; text-transform: uppercase;
      white-space: nowrap; border: 1px solid transparent;
    }}
    .phase-plan {{ background: var(--blue-light); color: #1e40af; border-color: var(--blue-border); }}
    .phase-build {{ background: var(--amber-light); color: #92400e; border-color: var(--amber-border); }}
    .phase-review {{ background: var(--purple-light); color: #5b21b6; border-color: var(--purple-border); }}
    .phase-fix {{ background: var(--red-light); color: #991b1b; border-color: var(--red-border); }}
    .phase-done {{ background: var(--green-light); color: #065f46; border-color: var(--green-border); }}
    .phase-present {{ background: var(--teal-light); color: #155e75; border-color: var(--teal-border); }}

    /* ── Cards ── */
    .card-grid {{
      display: grid; gap: 14px;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--stroke);
      border-radius: 16px; padding: 16px;
      box-shadow: var(--shadow-sm);
      display: flex; flex-direction: column; gap: 10px;
      min-height: 200px;
      transition: box-shadow .15s, transform .15s;
    }}
    .card:hover {{ box-shadow: var(--shadow-md); transform: translateY(-1px); }}
    .ongoing-card {{ border-left: 4px solid var(--amber); }}
    .finished-card {{ border-left: 4px solid var(--green); }}
    .card-top {{
      display: flex; justify-content: space-between;
      align-items: flex-start; gap: 8px;
    }}
    .card-top h3 {{
      margin: 0; font-size: 1.08rem; font-weight: 600;
      line-height: 1.25; letter-spacing: 0.01em;
    }}
    .pitch {{
      margin: 0; color: #1e272b; font-size: .92rem;
      flex: 1;
      display: -webkit-box; -webkit-line-clamp: 3;
      -webkit-box-orient: vertical; overflow: hidden;
    }}
    .card-foot {{
      display: flex; align-items: center;
      justify-content: space-between; gap: 8px;
      margin-top: auto;
    }}
    .id-chip {{
      display: inline-block; font-size: .72rem;
      color: #2e3b37; background: rgba(17,26,37,0.07);
      border-radius: 999px; padding: 3px 10px;
      max-width: 60%; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap;
      font-family: "SF Mono","Fira Code",Menlo,monospace;
    }}
    .meta {{ color: var(--muted); font-size: .82rem; }}
    .journal-link {{
      display: inline-block; margin-top: auto; width: fit-content;
      text-decoration: none; color: #0f4aa3; font-weight: 700;
      font-size: .86rem; border-bottom: 1px solid rgba(15,74,163,0.25);
      padding-bottom: 1px;
    }}
    .journal-link:hover {{ color: #083776; border-color: rgba(8,55,118,0.5); }}
    .empty-state {{
      padding: 20px; border-radius: 16px;
      border: 1px dashed rgba(17,26,37,0.22);
      background: rgba(255,255,255,0.5);
      color: var(--muted); font-style: italic;
    }}

    /* ── Details ── */
    .detail-card {{
      border: 1px solid var(--stroke);
      border-radius: 12px; background: #fafbf9;
      padding: .8rem 1rem; margin-bottom: .6rem;
    }}
    .detail-card summary {{
      cursor: pointer; font-size: .95rem; padding: .2rem 0;
    }}
    .detail-card summary:hover {{ color: var(--accent); }}
    .detail-body {{ margin: .6rem 0 .4rem; font-size: .9rem; }}
    .detail-request {{ color: var(--muted); font-size: .85rem; margin: .4rem 0; }}
    .detail-card .meta {{ margin-top: .6rem; display: block; }}

    /* ── Warnings ── */
    .warning-panel {{
      margin-top: 16px; background: #fff8e6;
      border: 1px solid #f0d297; border-radius: 14px;
      padding: 14px 16px; color: #4f3a00;
    }}
    .warning-panel h2 {{ margin: 0 0 8px; font-size: .95rem; }}
    .warning-panel ul {{ margin: 0; padding-left: 20px; }}

    code {{
      font-family: "SF Mono","Fira Code",Menlo,monospace;
      background: rgba(17,26,37,0.06);
      border: 1px solid rgba(17,26,37,0.08);
      border-radius: 4px; padding: .1rem .3rem; font-size: .8em;
    }}
    a {{ color: var(--accent); }}

    @media (max-width: 780px) {{
      .page {{ padding: 14px 12px 30px; }}
      .hero {{ padding: 18px; border-radius: 16px; }}
      .metrics {{ grid-template-columns: 1fr; }}
      .card {{ min-height: 0; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero" aria-labelledby="dashboard-title">
      <h1 id="dashboard-title">Quest Status Dashboard</h1>
      <p class="subtitle">Executive overview of engineering quests &mdash; generated {_escape(generated_at)}</p>
      <div class="metrics" role="list" aria-label="Key metrics">
        <article class="metric" role="listitem">
          <div class="label">Ongoing</div>
          <div class="value">{_escape(model["counts"]["ongoing"])}</div>
        </article>
        <article class="metric" role="listitem">
          <div class="label">Completed</div>
          <div class="value">{_escape(model["counts"]["finished"])}</div>
        </article>
        <article class="metric" role="listitem">
          <div class="label">Blocked</div>
          <div class="value">{_escape(model["counts"]["blocked"])}</div>
        </article>
      </div>
    </section>

    {warning_html}
    {timeline_section}

    <div class="section" aria-labelledby="ongoing-heading">
      <div class="section-head">
        <h2 id="ongoing-heading">Ongoing</h2>
        <small>Sorted by progress</small>
      </div>
      <div class="card-grid">
        {ongoing_html}
      </div>
    </div>

    <div class="section" aria-labelledby="completed-heading">
      <div class="section-head">
        <h2 id="completed-heading">Completed</h2>
        <small>Most recent first</small>
      </div>
      <div class="card-grid">
        {finished_html}
      </div>
    </div>

    <section class="section" aria-labelledby="details-heading">
      <div class="section-head">
        <h2 id="details-heading">Details</h2>
        <small>Click to expand</small>
      </div>
      {details_html}
    </section>
  </main>
</body>
</html>
"""


def write_output(html_text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")


def generate_dashboard(
    quest_root: Path,
    output_path: Path,
    journal_dir: Path | None = None,
    repo_url: str = "",
) -> dict[str, Any]:
    quests = load_quests(quest_root, journal_dir=journal_dir)
    model = build_dashboard_model(quests)
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    html_text = render_html(model, generated_at, repo_url=repo_url)
    write_output(html_text, output_path)
    return model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate static quest status dashboard HTML.")
    parser.add_argument("--quest-root", default=".quest", help="Quest root directory (default: .quest)")
    parser.add_argument(
        "--output",
        default="docs/quest-status/index.html",
        help="Output HTML path (default: docs/quest-status/index.html)",
    )
    parser.add_argument(
        "--journal-dir",
        default=DEFAULT_JOURNAL_DIR,
        help=f"Quest journal directory (default: {DEFAULT_JOURNAL_DIR})",
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help="GitHub repo URL for journal links (e.g. https://github.com/org/repo)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    journal_dir = Path(args.journal_dir) if args.journal_dir else None
    model = generate_dashboard(
        Path(args.quest_root), Path(args.output),
        journal_dir=journal_dir, repo_url=args.repo_url or "",
    )
    print(f"Wrote {args.output} (ongoing={model['counts']['ongoing']}, finished={model['counts']['finished']}).")
    if model["warnings"]:
        print(f"Warnings: {len(model['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
