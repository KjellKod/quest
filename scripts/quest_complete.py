#!/usr/bin/env python3
"""Automate quest completion: journal entry creation, README update, and archival.

Usage:
    python3 scripts/quest_complete.py --quest-dir .quest/<id>

This script is called by the orchestrator during Step 7 of the quest workflow.
It reads quest artifacts, generates a journal entry with embedded celebration_data,
updates the journal README index, and moves the quest to the archive.

The celebration animation itself is NOT handled here — it runs via the /celebrate
skill or the Python celebrate.py script before this script is called.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add scripts/ to path so we can import quest_celebrate
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quest_celebrate.quest_data import (
    QuestData,
    friendly_model_name,
    load_quest_data,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _build_celebration_json(data: QuestData) -> dict:
    """Build the celebration_data JSON block from QuestData."""
    return {
        "quest_mode": data.quest_mode or "unknown",
        "agents": [
            {"name": a.name, "model": a.model, "role": a.role_title}
            for a in data.agents
        ],
        "achievements": [
            {"icon": a.icon, "title": a.title, "desc": a.description}
            for a in data.achievements
        ],
        "metrics": [
            {"icon": "📊", "label": f"Plan iterations: {data.plan_iterations}"},
            {"icon": "🔧", "label": f"Fix iterations: {data.fix_iterations}"},
            {"icon": "📝", "label": f"Review findings: {data.review_count}"},
        ],
        "quality": {
            "tier": data.quality_tier,
            "grade": data.quality_tier[0] if data.quality_tier else "?",
        },
        "test_count": data.test_count,
        "tests_added": data.tests_added,
        "files_changed": len(data.files_changed),
    }


def _generate_journal_entry(data: QuestData, completion_date: date) -> str:
    """Generate a markdown journal entry from quest data."""
    lines = []

    # Title
    title = data.name or data.slug or data.quest_id
    lines.append(f"# Quest Journal: {title}")
    lines.append("")

    # Metadata
    lines.append(f"- Quest ID: `{data.quest_id}`")
    lines.append(f"- Completed: {completion_date.isoformat()}")
    if data.quest_mode:
        lines.append(f"- Mode: {data.quest_mode}")
    if data.quality_tier:
        lines.append(f"- Quality: {data.quality_tier}")
    lines.append(f"- Outcome: {data.brief_summary or data.plan_summary or 'Completed successfully.'}")
    lines.append("")

    # What shipped
    if data.plan_summary:
        lines.append("## What Shipped")
        lines.append("")
        lines.append(data.plan_summary)
        lines.append("")

    # Files changed
    if data.files_changed:
        lines.append("## Files Changed")
        lines.append("")
        for f in data.files_changed:
            lines.append(f"- `{f}`")
        lines.append("")

    # Iterations
    lines.append("## Iterations")
    lines.append("")
    lines.append(f"- Plan iterations: {data.plan_iterations}")
    lines.append(f"- Fix iterations: {data.fix_iterations}")
    lines.append("")

    # Agents
    if data.agents:
        lines.append("## Agents")
        lines.append("")
        for agent in data.agents:
            model_label = friendly_model_name(agent.model)
            lines.append(f"- **{agent.role_title}** ({agent.name}): {model_label}")
        lines.append("")

    # Brief as origin quote
    if data.brief_summary:
        lines.append("## This is where it all began...")
        lines.append("")
        lines.append(f"> {data.brief_summary}")
        lines.append("")

    # Celebration data JSON block
    celebration = _build_celebration_json(data)
    lines.append("## Celebration Data")
    lines.append("")
    lines.append("<!-- celebration-data-start -->")
    lines.append("```json")
    lines.append(json.dumps(celebration, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("<!-- celebration-data-end -->")
    lines.append("")

    return "\n".join(lines)


def _update_readme_index(journal_dir: Path, slug: str, completion_date: date, outcome: str) -> None:
    """Insert a row at the top of the journal README index table."""
    readme = journal_dir / "README.md"
    if not readme.exists():
        return

    content = readme.read_text()
    # Find the header row separator and insert after it
    # Format: | Date | Quest | Outcome |
    #         |------|-------|---------|
    #         | new row here |
    pattern = r"(\| Date \| Quest \| Outcome \|\n\|[-\s|]+\|\n)"
    new_row = f"| {completion_date.isoformat()} | [{slug}]({slug}_{completion_date.isoformat()}.md) | {outcome} |\n"

    if re.search(pattern, content):
        content = re.sub(pattern, lambda m: m.group(1) + new_row, content, count=1)
    else:
        # Fallback: append to end
        content += f"\n{new_row}"

    readme.write_text(content)


def _archive_quest(quest_dir: Path) -> Path:
    """Move quest directory to archive. Returns archive path."""
    archive_root = quest_dir.parent / "archive"
    archive_root.mkdir(exist_ok=True)
    dest = archive_root / quest_dir.name
    if dest.exists():
        raise FileExistsError(f"Archive already exists: {dest}. Remove it manually to re-archive.")
    shutil.move(str(quest_dir), str(dest))
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete a quest: journal + archive")
    parser.add_argument("--quest-dir", required=True, help="Path to quest directory")
    parser.add_argument("--skip-archive", action="store_true", help="Skip archival step")
    parser.add_argument("--skip-journal", action="store_true", help="Skip journal creation")
    parser.add_argument("--date", default=None, help="Override completion date (YYYY-MM-DD)")
    args = parser.parse_args()

    quest_dir = Path(args.quest_dir)
    if not quest_dir.exists():
        print(f"Error: quest directory not found: {quest_dir}", file=sys.stderr)
        return 1

    state_file = quest_dir / "state.json"
    if not state_file.exists():
        print(f"Error: no state.json in {quest_dir}", file=sys.stderr)
        return 1

    state = json.loads(state_file.read_text())
    if state.get("status") != "complete":
        print(f"Error: quest status is '{state.get('status')}', not 'complete'. "
              "Transition to complete or abandoned first.", file=sys.stderr)
        return 1

    # Load quest data
    data = load_quest_data(quest_dir)
    completion_date = date.fromisoformat(args.date) if args.date else _today()

    # Determine slug and outcome
    slug = data.slug or state.get("slug", quest_dir.name.split("_")[0])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        print(f"Error: invalid slug '{slug}'. Must match [a-z0-9][a-z0-9-]*", file=sys.stderr)
        return 1
    outcome = data.brief_summary or data.plan_summary or "Completed."
    # Sanitize outcome for README markdown table: collapse newlines, escape pipes
    outcome = re.sub(r"\s*\n\s*", " ", outcome).replace("|", "\\|")
    if len(outcome) > 120:
        outcome = outcome[:117] + "..."

    journal_path = None
    if not args.skip_journal:
        # Find journal directory (walk up to repo root)
        repo_root = quest_dir.resolve()
        found = False
        for _ in range(5):
            if (repo_root / "docs" / "quest-journal").exists():
                found = True
                break
            parent = repo_root.parent
            if parent == repo_root:
                break
            repo_root = parent
        if not found:
            print(f"Error: could not find docs/quest-journal/ above {quest_dir}", file=sys.stderr)
            return 1
        journal_dir = repo_root / "docs" / "quest-journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = journal_dir / f"{slug}_{completion_date.isoformat()}.md"

        if journal_file.exists():
            print(f"Journal entry already exists: {journal_file}")
        else:
            entry = _generate_journal_entry(data, completion_date)
            journal_file.write_text(entry)
            print(f"Journal entry created: {journal_file}")

            # Update README index
            _update_readme_index(journal_dir, slug, completion_date, outcome)
            print(f"README index updated")
        journal_path = str(journal_file)

    if not args.skip_archive:
        archive_path = _archive_quest(quest_dir)
        print(f"Quest archived: {archive_path}")

    print(json.dumps({
        "slug": slug,
        "journal": journal_path,
        "archived": not args.skip_archive,
        "quality_tier": data.quality_tier,
    }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
