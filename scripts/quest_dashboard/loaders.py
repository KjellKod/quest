from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from .models import ActiveQuestRecord, CompletedQuestRecord, DashboardData, UTC


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class DashboardDataError(RuntimeError):
    """Raised when dashboard input data is invalid or unreadable."""


def load_dashboard_data(repo_root: Path) -> DashboardData:
    repo_root = repo_root.resolve()
    warnings: list[str] = []
    active_quests = load_active_quests(repo_root=repo_root, warnings=warnings)
    completed_quests = load_completed_quests(repo_root=repo_root)
    return DashboardData(
        active_quests=active_quests,
        completed_quests=completed_quests,
        warnings=warnings,
    )


def load_active_quests(repo_root: Path, warnings: list[str] | None = None) -> list[ActiveQuestRecord]:
    warnings = warnings if warnings is not None else []
    quest_root = repo_root / ".quest"
    if not quest_root.exists():
        return []

    active_quests: list[ActiveQuestRecord] = []
    state_files = sorted(quest_root.glob("*/state.json"))

    for state_path in state_files:
        if _is_archived_state(state_path=state_path, quest_root=quest_root):
            continue

        state = _read_state_json(state_path)
        quest_id = _as_text(state.get("quest_id")) or state_path.parent.name
        slug = _as_text(state.get("slug")) or quest_id
        status = _display_label(state.get("status"), default="Unknown")
        phase = _display_label(state.get("phase"), default="Unknown")
        updated_at = _parse_updated_at(value=state.get("updated_at"), state_path=state_path)

        brief_path = state_path.parent / "quest_brief.md"
        brief_text: str | None = None
        if brief_path.exists():
            brief_text = _read_text_file(brief_path)
        else:
            warning_path = _repo_relative_path(path=brief_path, repo_root=repo_root)
            warnings.append(
                f"Missing quest brief for '{quest_id}' at {warning_path}. "
                "Using slug/quest_id fallback values."
            )

        name = _extract_active_name(brief_text=brief_text, slug=slug, quest_id=quest_id)
        elevator_pitch = _extract_active_pitch(brief_text=brief_text)
        if not elevator_pitch:
            elevator_pitch = "Quest brief unavailable."

        active_quests.append(
            ActiveQuestRecord(
                quest_id=quest_id,
                slug=slug,
                name=name,
                status=status,
                phase=phase,
                updated_at=updated_at,
                elevator_pitch=elevator_pitch,
                state_path=state_path,
                brief_path=brief_path if brief_text is not None else None,
            )
        )

    active_quests.sort(key=lambda record: (-record.updated_at.timestamp(), record.quest_id))
    return active_quests


def load_completed_quests(repo_root: Path) -> list[CompletedQuestRecord]:
    journal_root = repo_root / "docs" / "quest-journal"
    if not journal_root.exists():
        return []

    completed_quests: list[CompletedQuestRecord] = []
    for journal_path in sorted(journal_root.glob("*.md")):
        text = _read_text_file(journal_path)

        quest_id = _extract_quest_id(text) or _quest_id_from_filename(journal_path.name)
        status = _extract_status(text) or "Completed"
        updated_on = _extract_completed_date(text, journal_path.name) or date(1970, 1, 1)
        name = _extract_completed_name(text=text, filename=journal_path.name)
        elevator_pitch = _extract_completed_pitch(text=text) or "No summary provided."

        completed_quests.append(
            CompletedQuestRecord(
                quest_id=quest_id,
                name=name,
                status=status,
                updated_on=updated_on,
                elevator_pitch=elevator_pitch,
                journal_path=Path("docs") / "quest-journal" / journal_path.name,
                source_path=journal_path,
            )
        )

    completed_quests.sort(key=lambda record: (-record.updated_on.toordinal(), record.quest_id))
    return completed_quests


def _is_archived_state(state_path: Path, quest_root: Path) -> bool:
    try:
        relative = state_path.relative_to(quest_root)
    except ValueError:
        return False
    return "archive" in relative.parts


def _read_state_json(state_path: Path) -> dict[str, object]:
    raw_text = _read_text_file(state_path)
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise DashboardDataError(
            f"Malformed JSON in {state_path}. "
            f"Fix state.json formatting near line {exc.lineno}, column {exc.colno}."
        ) from None

    if not isinstance(payload, dict):
        raise DashboardDataError(
            f"Invalid state format in {state_path}. Expected a top-level JSON object."
        )
    return payload


def _repo_relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or "read error"
        raise DashboardDataError(f"Unable to read {path}: {reason}.") from None


def _parse_updated_at(value: object, state_path: Path) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=UTC)

    raw_value = _as_text(value)
    if not raw_value:
        return datetime(1970, 1, 1, tzinfo=UTC)

    normalized = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise DashboardDataError(
            f"Invalid updated_at timestamp in {state_path}. "
            "Expected ISO-8601 format like 2026-02-10T19:12:00Z."
        ) from None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _display_label(value: object, default: str) -> str:
    text = _as_text(value)
    if not text:
        return default

    normalized = text.replace("_", " ").replace("-", " ").strip()
    words = normalized.split()
    if not words:
        return default
    return " ".join(word.capitalize() if word.islower() else word for word in words)


def _extract_active_name(brief_text: str | None, slug: str, quest_id: str) -> str:
    if brief_text:
        match = re.search(r"(?im)^#\s*Quest Brief:\s*(.+?)\s*$", brief_text)
        if match:
            return _clean_inline_text(match.group(1))
    return slug or quest_id


def _extract_active_pitch(brief_text: str | None) -> str | None:
    if not brief_text:
        return None

    original_prompt_lines = _section_lines(brief_text, "Original Prompt")
    original_prompt = _first_paragraph(original_prompt_lines)
    if original_prompt:
        return original_prompt

    requirements_lines = _section_lines(brief_text, "Requirements")
    requirements_pitch = _first_bullet_or_paragraph(requirements_lines)
    if requirements_pitch:
        return requirements_pitch

    return _first_paragraph(brief_text.splitlines())


def _extract_completed_name(text: str, filename: str) -> str:
    prefixed_heading = re.search(r"(?im)^#\s*Quest Journal:\s*(.+?)\s*$", text)
    if prefixed_heading:
        return _clean_inline_text(prefixed_heading.group(1))

    generic_h1 = re.search(r"(?im)^#\s+(.+?)\s*$", text)
    if generic_h1:
        return _clean_inline_text(generic_h1.group(1))

    return _humanize_filename(filename)


def _extract_completed_pitch(text: str) -> str | None:
    summary_lines = _section_lines(text, "Summary")
    summary = _first_paragraph(summary_lines)
    if summary:
        return summary
    return _first_paragraph(text.splitlines())


def _extract_quest_id(text: str) -> str | None:
    for pattern in (
        r"(?im)^\*\*Quest ID:\*\*\s*(.+?)\s*$",
        r"(?im)^\*\*Quest ID\*\*:\s*(.+?)\s*$",
    ):
        match = re.search(pattern, text)
        if match:
            quest_id = match.group(1).strip()
            quest_id = re.sub(r"^\[(.*?)\]\((.*?)\)$", r"\1", quest_id)
            quest_id = quest_id.replace("**", "").replace("*", "").strip("`").strip()
            if quest_id:
                return quest_id
    return None


def _extract_status(text: str) -> str | None:
    for pattern in (
        r"(?im)^\*\*Status:\*\*\s*(.+?)\s*$",
        r"(?im)^\*\*Status\*\*:\s*(.+?)\s*$",
    ):
        match = re.search(pattern, text)
        if match:
            status = _clean_inline_text(match.group(1))
            if status:
                return status
    return None


def _extract_completed_date(text: str, filename: str) -> date | None:
    for label in ("Completed", "Date"):
        parsed = _extract_metadata_date(text=text, label=label)
        if parsed is not None:
            return parsed

    from_filename = DATE_RE.search(filename)
    if from_filename:
        try:
            return date.fromisoformat(from_filename.group(1))
        except ValueError:
            return None
    return None


def _extract_metadata_date(text: str, label: str) -> date | None:
    patterns = (
        rf"(?im)^\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$",
        rf"(?im)^\*\*{re.escape(label)}\*\*:\s*(.+?)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        date_match = DATE_RE.search(match.group(1))
        if not date_match:
            continue
        try:
            return date.fromisoformat(date_match.group(1))
        except ValueError:
            return None
    return None


def _quest_id_from_filename(filename: str) -> str:
    stem = filename[:-3] if filename.endswith(".md") else filename
    return stem


def _humanize_filename(filename: str) -> str:
    stem = filename[:-3] if filename.endswith(".md") else filename
    stem = re.sub(r"_\d{4}-\d{2}-\d{2}$", "", stem)
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else "Untitled Quest"


def _section_lines(text: str, heading_name: str) -> list[str]:
    lines = text.splitlines()
    start_index: int | None = None
    start_level = 0

    target = heading_name.strip().lower()
    for index, line in enumerate(lines):
        heading_match = HEADING_RE.match(line.strip())
        if not heading_match:
            continue
        level = len(heading_match.group(1))
        title = heading_match.group(2).strip().lower()
        if title == target:
            start_index = index + 1
            start_level = level
            break

    if start_index is None:
        return []

    result: list[str] = []
    for line in lines[start_index:]:
        heading_match = HEADING_RE.match(line.strip())
        if heading_match and len(heading_match.group(1)) <= start_level:
            break
        result.append(line)
    return result


def _first_bullet_or_paragraph(lines: list[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            candidate = _clean_inline_text(stripped[2:])
            if candidate:
                return candidate
    return _first_paragraph(lines)


def _first_paragraph(lines: list[str]) -> str | None:
    paragraph_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph_lines:
                break
            continue

        if stripped.startswith("#"):
            if paragraph_lines:
                break
            continue

        if stripped.startswith("|"):
            if paragraph_lines:
                break
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            candidate = _clean_inline_text(stripped[2:])
            if candidate:
                return candidate
            continue

        paragraph_lines.append(stripped)

    if not paragraph_lines:
        return None

    paragraph = " ".join(paragraph_lines)
    cleaned = _clean_inline_text(paragraph)
    return cleaned or None


def _clean_inline_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = cleaned.replace("*", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
