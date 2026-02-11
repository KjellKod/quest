#!/usr/bin/env python3
"""Generate dashboard data for Quest history."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

STATUS_ORDER = ("in_progress", "blocked", "abandoned", "finished", "unknown")
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_HEADER_RE = re.compile(r"^\*\*(.+?)\*\*\s*:?[ \t]*(.+?)\s*$")
_TITLE_PREFIX = "Quest Journal:"


def _to_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _extract_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    match = _DATE_RE.search(value)
    if not match:
        return None
    return match.group(1)


def _slug_from_quest_id(quest_id: Optional[str]) -> Optional[str]:
    if not quest_id:
        return None
    match = re.match(r"^(?P<slug>.+)_\d{4}-\d{2}-\d{2}__\d{4}$", quest_id)
    if match:
        return match.group("slug")
    return quest_id


def _slug_from_stem(stem: str) -> str:
    match = re.match(r"^(?P<slug>.+)_\d{4}-\d{2}-\d{2}$", stem)
    if match:
        return match.group("slug")
    return stem


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _clean_meta_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1].strip()
    return value


def _date_from_timestamp(timestamp: Optional[str]) -> Optional[str]:
    if not timestamp:
        return None
    timestamp = timestamp.strip()
    if not timestamp:
        return None
    try:
        parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return _extract_date(timestamp)
    return parsed.date().isoformat()


def _status_from_value(value: Optional[str]) -> str:
    if not value:
        return "unknown"

    normalized = value.strip().lower()
    normalized = normalized.replace("`", "")
    normalized = normalized.replace("-", "_")
    normalized = normalized.replace(" ", "_")

    if normalized.startswith("completed") or normalized.startswith("complete"):
        return "finished"
    if normalized.startswith("finished"):
        return "finished"
    if normalized.startswith("in_progress"):
        return "in_progress"
    if normalized.startswith("blocked"):
        return "blocked"
    if normalized.startswith("abandoned"):
        return "abandoned"
    return "unknown"


def normalize_status(journal_record: Optional[Dict[str, Any]], state_record: Optional[Dict[str, Any]]) -> str:
    """Map state/journal status values into dashboard canonical statuses."""

    state_status = None
    state_phase = None
    journal_status = None
    completed_date = None

    if state_record:
        state_status = state_record.get("status_raw")
        state_phase = state_record.get("phase")
    if journal_record:
        journal_status = journal_record.get("status_raw")
        completed_date = journal_record.get("completed_date")

    for candidate in (state_status, state_phase, journal_status):
        mapped = _status_from_value(candidate)
        if mapped != "unknown":
            return mapped

    if completed_date:
        return "finished"
    return "unknown"


def parse_journal_entry(path: Path, repo_root: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title: Optional[str] = None
    meta: Dict[str, str] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and title is None:
            heading = stripped[2:].strip()
            if heading.lower().startswith(_TITLE_PREFIX.lower()):
                heading = heading[len(_TITLE_PREFIX) :].strip()
            title = heading
            continue

        header_match = _HEADER_RE.match(stripped)
        if not header_match:
            continue

        key = header_match.group(1).strip().lower().replace("_", " ").rstrip(":")
        value = _clean_meta_value(header_match.group(2))
        meta[key] = value

    summary = ""
    summary_index = None
    for idx, line in enumerate(lines):
        if re.match(r"^##\s+summary\b", line.strip(), flags=re.IGNORECASE):
            summary_index = idx + 1
            break

    if summary_index is not None:
        paragraph_lines: List[str] = []
        for line in lines[summary_index:]:
            stripped = line.strip()
            if not stripped and paragraph_lines:
                break
            if not stripped and not paragraph_lines:
                continue
            if stripped.startswith("## "):
                break
            paragraph_lines.append(stripped)
        summary = " ".join(paragraph_lines).strip()

    quest_id = _coalesce(meta.get("quest id"), meta.get("quest_id"))
    slug = _slug_from_quest_id(quest_id) or _slug_from_stem(path.stem)
    completed_date = _extract_date(_coalesce(meta.get("completed"), meta.get("date")))

    return {
        "quest_id": quest_id,
        "slug": slug,
        "title": title or slug,
        "elevator_pitch": summary,
        "completed_date": completed_date,
        "status_raw": meta.get("status"),
        "journal_path": _to_posix(path, repo_root),
    }


def _load_state_file(path: Path, repo_root: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    quest_id = payload.get("quest_id")

    return {
        "quest_id": quest_id,
        "slug": payload.get("slug") or _slug_from_quest_id(quest_id),
        "status_raw": _coalesce(payload.get("status"), payload.get("phase")),
        "phase": payload.get("phase"),
        "plan_iteration": payload.get("plan_iteration"),
        "fix_iteration": payload.get("fix_iteration"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "state_path": _to_posix(path, repo_root),
    }


def _state_index(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for record in records:
        quest_id = record.get("quest_id")
        slug = record.get("slug")
        if quest_id:
            by_key[f"id:{quest_id}"] = record
        if slug:
            by_key[f"slug:{slug}"] = record
    return by_key


def load_active_states(quest_dir: Path, repo_root: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(quest_dir.glob("*/state.json")):
        if "archive" in path.parts:
            continue
        records.append(_load_state_file(path, repo_root))
    return records


def load_archive_states(archive_dir: Path, repo_root: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(archive_dir.glob("*/state.json")):
        records.append(_load_state_file(path, repo_root))
    return records


def _merge_records(
    journal_records: List[Dict[str, Any]],
    active_states: List[Dict[str, Any]],
    archive_states: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # Dedup precedence: archive state overrides active state for duplicate keys.
    active_by_key = _state_index(active_states)
    archive_by_key = _state_index(archive_states)
    merged_by_key: Dict[str, Dict[str, Any]] = dict(active_by_key)
    merged_by_key.update(archive_by_key)

    merged_states = list({id(value): value for value in merged_by_key.values()}.values())
    state_by_id = {
        record["quest_id"]: record
        for record in merged_states
        if record.get("quest_id")
    }
    state_by_slug = {
        record["slug"]: record
        for record in merged_states
        if record.get("slug")
    }

    quests: List[Dict[str, Any]] = []
    seen_state_ids = set()

    for journal in journal_records:
        quest_id = journal.get("quest_id")
        slug = journal.get("slug")

        state = None
        if quest_id and quest_id in state_by_id:
            state = state_by_id[quest_id]
        elif slug and slug in state_by_slug:
            state = state_by_slug[slug]

        if state is not None:
            seen_state_ids.add(id(state))

        status = normalize_status(journal, state)
        fallback_state_date = _date_from_timestamp(
            _coalesce(
                state.get("updated_at") if state else None,
                state.get("created_at") if state else None,
            )
        )

        completed_date = journal.get("completed_date")
        if not completed_date and status == "finished":
            completed_date = fallback_state_date

        resolved_quest_id = _coalesce(state.get("quest_id") if state else None, quest_id)
        resolved_slug = _coalesce(
            state.get("slug") if state else None,
            slug,
            _slug_from_quest_id(resolved_quest_id),
        )

        quests.append(
            {
                "quest_id": resolved_quest_id,
                "slug": resolved_slug,
                "title": journal.get("title") or resolved_slug or resolved_quest_id,
                "elevator_pitch": journal.get("elevator_pitch") or "",
                "status": status,
                "completed_date": completed_date,
                "created_at": state.get("created_at") if state else None,
                "updated_at": state.get("updated_at") if state else None,
                "plan_iteration": state.get("plan_iteration") if state else None,
                "fix_iteration": state.get("fix_iteration") if state else None,
                "journal_path": journal.get("journal_path"),
                "state_path": state.get("state_path") if state else None,
            }
        )

    for state in merged_states:
        if id(state) in seen_state_ids:
            continue

        status = normalize_status(None, state)
        completed_date = None
        fallback_date = _date_from_timestamp(_coalesce(state.get("updated_at"), state.get("created_at")))
        if status == "finished":
            completed_date = fallback_date

        quests.append(
            {
                "quest_id": state.get("quest_id"),
                "slug": state.get("slug") or _slug_from_quest_id(state.get("quest_id")),
                "title": state.get("slug") or state.get("quest_id") or "Untitled quest",
                "elevator_pitch": "",
                "status": status,
                "completed_date": completed_date,
                "created_at": state.get("created_at"),
                "updated_at": state.get("updated_at"),
                "plan_iteration": state.get("plan_iteration"),
                "fix_iteration": state.get("fix_iteration"),
                "journal_path": None,
                "state_path": state.get("state_path"),
            }
        )

    quests.sort(
        key=lambda quest: (
            quest.get("quest_id") or "",
            quest.get("slug") or "",
            quest.get("journal_path") or "",
            quest.get("state_path") or "",
        )
    )
    return quests


def build_trend_points(quests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    points: Dict[str, Dict[str, int]] = {}

    for quest in quests:
        event_date = _coalesce(
            quest.get("completed_date"),
            _date_from_timestamp(quest.get("updated_at")),
            _date_from_timestamp(quest.get("created_at")),
        )
        if not event_date:
            continue

        period = event_date[:7]
        if not re.match(r"^\d{4}-\d{2}$", period):
            continue

        if period not in points:
            points[period] = {status: 0 for status in STATUS_ORDER}

        status = quest.get("status")
        if status not in STATUS_ORDER:
            status = "unknown"
        points[period][status] += 1

    trend_points = []
    for period in sorted(points):
        point: Dict[str, Any] = {"period": period}
        for status in STATUS_ORDER:
            point[status] = points[period][status]
        trend_points.append(point)
    return trend_points


def build_dashboard_data(
    journal_dir: Path,
    quest_dir: Path,
    archive_dir: Path,
    repo_root: Path,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    journal_records = []
    for path in sorted(journal_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        journal_records.append(parse_journal_entry(path, repo_root))

    active_states = load_active_states(quest_dir, repo_root)
    archive_states = load_archive_states(archive_dir, repo_root)

    quests = _merge_records(journal_records, active_states, archive_states)

    by_status = {status: 0 for status in STATUS_ORDER}
    for quest in quests:
        status = quest.get("status")
        if status not in STATUS_ORDER:
            status = "unknown"
        by_status[status] += 1

    if not generated_at:
        generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return {
        "generated_at": generated_at,
        "summary": {
            "total": len(quests),
            "by_status": by_status,
        },
        "trends": {
            "granularity": "month",
            "points": build_trend_points(quests),
        },
        "quests": quests,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Quest dashboard JSON data")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path (defaults to parent of this script)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (defaults to docs/dashboard/dashboard-data.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent.parent
    output_path = (
        Path(args.output).resolve()
        if args.output
        else repo_root / "docs" / "dashboard" / "dashboard-data.json"
    )

    dashboard_data = build_dashboard_data(
        journal_dir=repo_root / "docs" / "quest-journal",
        quest_dir=repo_root / ".quest",
        archive_dir=repo_root / ".quest" / "archive",
        repo_root=repo_root,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dashboard_data, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
