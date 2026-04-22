#!/usr/bin/env python3
"""Backfill existing quest journal pages from archived quest artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from quest_celebrate.quest_data import extract_metadata_value, load_quest_data
    from quest_complete import (
        build_celebration_data_section,
        build_celebration_section,
        build_quest_brief_section,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from quest_celebrate.quest_data import extract_metadata_value, load_quest_data
    from quest_complete import (
        build_celebration_data_section,
        build_celebration_section,
        build_quest_brief_section,
    )


UTC = timezone.utc


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "docs" / "quest-journal").exists() and (candidate / ".quest").exists():
            return candidate
    raise FileNotFoundError(f"Could not find repo root above {start}")


def _extract_journal_quest_id(journal_path: Path) -> str | None:
    return extract_metadata_value(journal_path.read_text(encoding="utf-8"), "quest id")


def _extract_date_from_journal_filename(journal_path: Path) -> date | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", journal_path.name)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _extract_journal_completed_date(journal_path: Path) -> date | None:
    content = journal_path.read_text(encoding="utf-8")
    completed = extract_metadata_value(content, "completed") or extract_metadata_value(content, "date")
    if completed:
        try:
            return date.fromisoformat(completed[:10])
        except ValueError:
            return _extract_date_from_journal_filename(journal_path)

    return _extract_date_from_journal_filename(journal_path)


def _archive_completion_date(archive_dir: Path) -> date | None:
    data = load_quest_data(archive_dir)
    for value in (data.updated_at, data.created_at):
        if not value:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).date()
        except ValueError:
            continue
    return None


def _find_matching_journal(
    archive_dir: Path,
    journal_dir: Path,
    journal_by_quest_id: dict[str, Path],
    duplicate_quest_ids: set[str],
) -> tuple[Path | None, str | None]:
    data = load_quest_data(archive_dir)
    if not data.quest_id:
        return None, f"{archive_dir.name}: missing quest_id in archive data"

    if data.quest_id in duplicate_quest_ids:
        return None, f"{archive_dir.name}: duplicate Quest ID match in journal entries"

    if data.quest_id in journal_by_quest_id:
        return journal_by_quest_id[data.quest_id], None

    completion_date = _archive_completion_date(archive_dir)
    if completion_date is None:
        return None, f"{archive_dir.name}: missing or invalid completion date; cannot use slug/date fallback"

    completion_date_str = completion_date.isoformat()
    fallback_candidates = sorted(journal_dir.glob(f"{data.slug}_{completion_date_str}*.md"))
    if len(fallback_candidates) > 1:
        return None, (
            f"{archive_dir.name}: ambiguous slug/date fallback "
            f"({', '.join(path.name for path in fallback_candidates)})"
        )
    if len(fallback_candidates) == 1:
        return fallback_candidates[0], None

    return None, f"{archive_dir.name}: no matching journal entry found"


def _replace_or_insert_section(
    content: str,
    heading_patterns: tuple[str, ...],
    replacement: str,
    *,
    before_patterns: tuple[str, ...] = (),
) -> str:
    source = content
    replacement_text = replacement.rstrip()
    compiled = [
        re.compile(
            rf"(?ms)^##\s+(?:{pattern})\s*$.*?(?=^##\s+|\Z)",
            re.IGNORECASE,
        )
        for pattern in heading_patterns
    ]
    for pattern in compiled:
        if pattern.search(source):
            return pattern.sub(f"{replacement_text}\n\n", source, count=1)

    for before_pattern in before_patterns:
        match = re.search(
            rf"(?m)^##\s+(?:{before_pattern})\s*$",
            source,
            re.IGNORECASE,
        )
        if match:
            return f"{source[: match.start()]}{replacement_text}\n\n{source[match.start() :]}"

    if source and not source.endswith("\n"):
        source = f"{source}\n"
    return f"{source.rstrip()}\n\n{replacement_text}\n"


def _extract_section_block(content: str, heading_patterns: tuple[str, ...]) -> str | None:
    for heading_pattern in heading_patterns:
        match = re.search(
            rf"(?ms)^##\s+(?:{heading_pattern})\s*$.*?(?=^##\s+|\Z)",
            content,
            re.IGNORECASE,
        )
        if match:
            return match.group(0).rstrip()
    return None


def _section_body(section: str) -> str:
    lines = section.splitlines()
    if len(lines) <= 1:
        return ""
    return "\n".join(lines[1:]).strip()


def _normalize_section_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _preferred_brief_section(content: str, generated_section: str) -> str:
    existing_section = _extract_section_block(
        content,
        ("Quest Brief", r"This is where it all began[^\n]*"),
    )
    if not existing_section:
        return generated_section

    existing_body = _section_body(existing_section)
    generated_body = _section_body(generated_section)
    if not existing_body:
        return generated_section
    if not generated_body:
        return f"## Quest Brief\n\n{existing_body.strip()}\n"

    existing_normalized = _normalize_section_text(existing_body)
    generated_normalized = _normalize_section_text(generated_body)
    if len(existing_normalized) <= len(generated_normalized):
        return generated_section

    if generated_normalized and generated_normalized not in existing_normalized:
        return (
            f"## Quest Brief\n\n{existing_body.strip()}\n\n"
            f"### Archived Brief\n\n{generated_body.strip()}\n"
        )

    return f"## Quest Brief\n\n{existing_body.strip()}\n"


def _patch_journal_content(content: str, archive_dir: Path, repo_root: Path, journal_path: Path) -> str:
    data = load_quest_data(archive_dir)
    journal_rel_path = journal_path.relative_to(repo_root)
    patched_content = content

    quest_brief_section = build_quest_brief_section(data)
    if quest_brief_section:
        quest_brief_section = _preferred_brief_section(patched_content, quest_brief_section)
        patched_content = _replace_or_insert_section(
            patched_content,
            ("Quest Brief", r"This is where it all began[^\n]*"),
            quest_brief_section,
            before_patterns=("Celebration", "Celebration Data"),
        )

    celebration_section = build_celebration_section(journal_rel_path)
    if celebration_section:
        patched_content = _replace_or_insert_section(
            patched_content,
            ("Celebration",),
            celebration_section,
            before_patterns=("Celebration Data",),
        )

    patched_content = _replace_or_insert_section(
        patched_content,
        ("Celebration Data",),
        build_celebration_data_section(data),
    )

    return f"{patched_content.rstrip()}\n"


def backfill_journal_entries(
    repo_root: Path,
    quest_id: str | None = None,
    write: bool = True,
) -> dict[str, object]:
    """Patch existing journal pages from archive quests."""
    journal_dir = repo_root / "docs" / "quest-journal"
    archive_root = repo_root / ".quest" / "archive"
    if not archive_root.is_dir():
        return {
            "patched": [],
            "unchanged": [],
            "skipped": [],
        }

    journal_paths = [path for path in sorted(journal_dir.glob("*.md")) if path.name != "README.md"]
    journal_by_quest_id: dict[str, Path] = {}
    duplicate_quest_ids: set[str] = set()
    for journal_path in journal_paths:
        journal_quest_id = _extract_journal_quest_id(journal_path)
        if journal_quest_id:
            if journal_quest_id in journal_by_quest_id:
                duplicate_quest_ids.add(journal_quest_id)
                journal_by_quest_id.pop(journal_quest_id, None)
                continue
            journal_by_quest_id[journal_quest_id] = journal_path

    archive_dirs = sorted(path for path in archive_root.iterdir() if path.is_dir())
    if quest_id:
        archive_dirs = [path for path in archive_dirs if path.name == quest_id]

    patched: list[str] = []
    unchanged: list[str] = []
    skipped: list[str] = []

    for archive_dir in archive_dirs:
        journal_path, warning = _find_matching_journal(
            archive_dir,
            journal_dir,
            journal_by_quest_id,
            duplicate_quest_ids,
        )
        if warning:
            skipped.append(warning)
            continue

        if journal_path is None:
            skipped.append(f"{archive_dir.name}: matching journal path missing unexpectedly")
            continue
        existing = journal_path.read_text(encoding="utf-8")
        rendered = _patch_journal_content(existing, archive_dir, repo_root, journal_path)

        if existing == rendered:
            unchanged.append(journal_path.name)
            continue

        if write:
            journal_path.write_text(rendered, encoding="utf-8")
        patched.append(journal_path.name)

    return {
        "patched": patched,
        "unchanged": unchanged,
        "skipped": skipped,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill quest journal pages from archived quests")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    parser.add_argument("--quest-id", default=None, help="Only backfill one archived quest ID")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _find_repo_root(Path(args.repo_root))
    result = backfill_journal_entries(repo_root, quest_id=args.quest_id, write=not args.dry_run)

    print(f"Patched: {len(result['patched'])}")
    for path in result["patched"]:
        print(f"  patched: {path}")

    print(f"Unchanged: {len(result['unchanged'])}")
    for path in result["unchanged"]:
        print(f"  unchanged: {path}")

    print(f"Skipped: {len(result['skipped'])}")
    for warning in result["skipped"]:
        print(f"  skipped: {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
