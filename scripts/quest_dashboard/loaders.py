"""Data loaders for the Quest Dashboard.

This module extracts quest data from:
- docs/quest-journal/*.md (completed and abandoned quests)
- .quest/*/state.json and quest_brief.md (active quests)
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from .models import ActiveQuest, DashboardData, JournalEntry

UTC = timezone.utc

# Phase ordering for active quest sorting (from PR #22)
_PHASE_ORDER = {
    "complete": 0,
    "done": 0,
    "reviewing": 1,
    "code_review": 1,
    "fixing": 2,
    "building": 3,
    "implementing": 3,
    "presenting": 4,
    "plan": 5,
    "pending": 5,
}


def load_dashboard_data(
    repo_root: Path, github_url: str | None = None
) -> DashboardData:
    """Load all quest data and build the complete dashboard model.

    Args:
        repo_root: Repository root directory
        github_url: GitHub repo URL (auto-detected if None)

    Returns:
        DashboardData with finished, active, and abandoned quests
    """
    journal_dir = repo_root / "docs" / "quest-journal"
    quest_dir = repo_root / ".quest"

    warnings: list[str] = []

    # Load journal entries
    journal_entries, journal_warnings = load_journal_entries(journal_dir, repo_root)
    warnings.extend(journal_warnings)

    # Load active quests
    active_quests, active_warnings = load_active_quests(quest_dir)
    warnings.extend(active_warnings)

    # Deduplicate: exclude active quests that already have journal entries
    # (Arbiter guidance: prevents a quest appearing in both Finished and In Progress)
    journal_quest_ids = {e.quest_id for e in journal_entries}
    active_quests = [q for q in active_quests if q.quest_id not in journal_quest_ids]

    # Split journal entries into finished and abandoned
    finished = [e for e in journal_entries if e.status == "Completed"]
    abandoned = [e for e in journal_entries if e.status == "Abandoned"]

    # Sort finished and abandoned by completed_date descending, then quest_id
    finished.sort(key=lambda e: (e.completed_date, e.quest_id), reverse=True)
    abandoned.sort(key=lambda e: (e.completed_date, e.quest_id), reverse=True)

    # Detect GitHub URL if not provided
    if github_url is None:
        github_url = detect_github_url(repo_root)
    github_url = github_url or ""

    return DashboardData(
        finished_quests=finished,
        active_quests=active_quests,
        abandoned_quests=abandoned,
        warnings=warnings,
        github_repo_url=github_url,
    )


def load_journal_entries(
    journal_dir: Path, repo_root: Path
) -> tuple[list[JournalEntry], list[str]]:
    """Load all journal entries from docs/quest-journal/*.md.

    Args:
        journal_dir: Path to docs/quest-journal directory
        repo_root: Repository root (for git log PR extraction)

    Returns:
        Tuple of (journal entries, warnings)
    """
    entries: list[JournalEntry] = []
    warnings: list[str] = []

    if not journal_dir.exists():
        warnings.append(f"Journal directory not found: {journal_dir}")
        return entries, warnings

    for path in sorted(journal_dir.glob("*.md")):
        # BUILDER GUIDANCE NOTE #1: Skip README.md
        if path.name == "README.md":
            continue

        try:
            entry = _parse_journal_entry(path, repo_root)
            entries.append(entry)
        except Exception as e:
            warnings.append(f"Failed to parse journal {path.name}: {e}")

    return entries, warnings


def _parse_journal_entry(journal_path: Path, repo_root: Path) -> JournalEntry:
    """Parse a single journal markdown file into a JournalEntry.

    Args:
        journal_path: Path to the journal markdown file
        repo_root: Repository root (for git log PR extraction)

    Returns:
        JournalEntry with extracted metadata
    """
    content = journal_path.read_text(encoding="utf-8")

    # Extract quest_id (strip surrounding backticks per Arbiter guidance)
    quest_id = _extract_metadata(content, "quest id") or _humanize_filename(
        journal_path.stem
    )
    quest_id = quest_id.strip("`")

    # Extract slug (fallback to quest_id)
    slug = _extract_metadata(content, "slug") or quest_id

    # Extract title
    title = _extract_title(content) or _humanize_filename(journal_path.stem)

    # Extract status and normalize
    raw_status = _extract_metadata(content, "status") or "Completed"
    status = _normalize_status(raw_status)

    # Extract completed date
    completed_date = _extract_date(content, journal_path)

    # Extract elevator pitch from Summary section
    elevator_pitch = _extract_summary_pitch(content) or _extract_first_paragraph(
        content
    )

    # Extract PR number
    pr_number = extract_pr_number(content, journal_path, repo_root)

    # BUILDER GUIDANCE NOTE #2: Handle both bold and list-item iteration formats
    plan_iterations = _extract_iterations(content, "plan")
    fix_iterations = _extract_iterations(content, "fix")

    # Compute relative journal path
    journal_rel_path = journal_path.relative_to(repo_root)

    return JournalEntry(
        quest_id=quest_id,
        slug=slug,
        title=title,
        elevator_pitch=elevator_pitch,
        status=status,
        completed_date=completed_date,
        journal_path=journal_rel_path,
        pr_number=pr_number,
        plan_iterations=plan_iterations,
        fix_iterations=fix_iterations,
    )


def _extract_metadata(content: str, key: str) -> str | None:
    """Extract metadata value from bold or plain markdown patterns.

    Matches both:
    - **Key:** value  (colon is INSIDE the bold markers)
    - **Key**: value  (colon is OUTSIDE - less common)

    Args:
        content: Markdown content
        key: Metadata key (case-insensitive)

    Returns:
        Extracted value or None
    """
    # Primary pattern: **Key:** value (colon inside the **)
    pattern = rf"\*\*{re.escape(key)}:\s*\*\*\s*(.+?)(?:\n|$)"
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback pattern: **Key**: value (colon outside the **)
    pattern = rf"\*\*{re.escape(key)}\*\*\s*:\s*(.+?)(?:\n|$)"
    match = re.search(pattern, content, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_title(content: str) -> str | None:
    """Extract title from journal heading.

    Tries in order:
    1. # Quest Journal: <title>
    2. First # heading
    """
    # Try "# Quest Journal: <title>"
    match = re.search(r"^#\s+Quest Journal:\s*(.+?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Fallback to first heading
    match = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return None


def _normalize_status(raw_status: str) -> str:
    """Normalize status string to 'Completed' or 'Abandoned'.

    BUILDER GUIDANCE NOTE #3: Use prefix matching, not exact equality.

    Args:
        raw_status: Raw status value from journal

    Returns:
        'Completed' or 'Abandoned'
    """
    val = raw_status.strip().lower()

    # Check for abandoned prefix (handles "Abandoned (plan approved, never built)")
    if val.startswith("abandon"):
        return "Abandoned"

    # Check for completed/finished prefixes (handles "Complete", "Completed", "Finished")
    if val.startswith("complet") or val.startswith("finish"):
        return "Completed"

    # Default to Completed for journals
    return "Completed"


def _extract_date(content: str, journal_path: Path) -> date:
    """Extract completion date from metadata or filename.

    Tries in order:
    1. **Completed:** <date>
    2. **Date:** <date>
    3. Date in filename (YYYY-MM-DD pattern)
    4. Fallback to today
    """
    # Try metadata fields
    for key in ["completed", "date"]:
        date_str = _extract_metadata(content, key)
        if date_str:
            parsed = _parse_date_string(date_str)
            if parsed:
                return parsed

    # Try filename date pattern (YYYY-MM-DD)
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", journal_path.name)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Fallback to today
    return date.today()


def _parse_date_string(date_str: str) -> date | None:
    """Parse a date string in various formats.

    Supports:
    - YYYY-MM-DD
    - Month DD, YYYY (e.g. "February 10, 2026")
    """
    # Try ISO format
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Try "Month DD, YYYY" or "DD Month YYYY"
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    for month_name, month_num in months.items():
        # "Month DD, YYYY"
        pattern = rf"{month_name}\s+(\d{{1,2}}),?\s+(\d{{4}})"
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            try:
                return date(int(match.group(2)), month_num, int(match.group(1)))
            except ValueError:
                pass

    return None


def _extract_summary_pitch(content: str) -> str | None:
    """Extract elevator pitch from ## Summary section.

    Returns the first paragraph under the ## Summary heading.
    """
    # Find ## Summary section
    match = re.search(
        r"^##\s+Summary\s*$(.+?)(?=^##|\Z)", content, re.MULTILINE | re.DOTALL
    )
    if not match:
        return None

    section = match.group(1).strip()
    return _extract_first_paragraph(section)


def _extract_first_paragraph(content: str) -> str:
    """Extract the first non-empty paragraph from content.

    Skips headings, metadata lines (**Key:** value), and empty lines.
    Preserves paragraphs that start with bold text that is not a metadata key.
    """
    lines = content.split("\n")
    paragraph_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and headings
        if not stripped or stripped.startswith("#"):
            if paragraph_lines:
                break
            continue

        # Skip metadata lines: **Key:** value (key followed by colon inside or outside bold)
        if re.match(r"\*\*[^*]+:\s*\*\*", stripped) or re.match(
            r"\*\*[^*]+\*\*\s*:", stripped
        ):
            if paragraph_lines:
                break
            continue

        paragraph_lines.append(stripped)

    return " ".join(paragraph_lines) if paragraph_lines else ""


def extract_pr_number(content: str, journal_path: Path, repo_root: Path) -> int | None:
    """Extract PR number from journal metadata or git log.

    Tries in order:
    1. **PR:** #123
    2. **PR:** https://github.com/owner/repo/pull/123
    3. Git log merge commit message for this journal file

    Args:
        content: Journal markdown content
        journal_path: Path to journal file
        repo_root: Repository root

    Returns:
        PR number or None
    """
    # Try metadata field
    pr_str = _extract_metadata(content, "pr")
    if pr_str:
        # Try #123 pattern
        match = re.search(r"#(\d+)", pr_str)
        if match:
            return int(match.group(1))

        # Try URL pattern
        match = re.search(r"/pull/(\d+)", pr_str)
        if match:
            return int(match.group(1))

    # Try git log as fallback
    try:
        rel_path = journal_path.relative_to(repo_root)
        result = subprocess.run(
            ["git", "log", "--merges", "--format=%s", "--", str(rel_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Match "Merge pull request #123" pattern specifically
            match = re.search(r"Merge pull request #(\d+)", result.stdout)
            if match:
                return int(match.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    return None


def _extract_iterations(content: str, iteration_type: str) -> int | None:
    """Extract iteration count from journal metadata.

    BUILDER GUIDANCE NOTE #2: Handles both bold and list-item formats:
    - **Plan iterations:** 1
    - - Plan iterations: 1

    Args:
        content: Journal markdown content
        iteration_type: "plan" or "fix"

    Returns:
        Iteration count or None
    """
    # Pattern matches both bold and list-item formats
    # Bold format: **Plan iterations:** 1 (colon is INSIDE the **)
    # List format: - Plan iterations: 1 (no **)
    pattern = rf"(?:\*\*)?{re.escape(iteration_type)}\s+iterations:\s*(?:\*\*)?\s*(\d+)"
    match = re.search(pattern, content, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _humanize_filename(stem: str) -> str:
    """Convert filename stem to human-readable title.

    Example: "quest-journal-example" -> "Quest Journal Example"
    """
    return stem.replace("-", " ").replace("_", " ").title()


def load_active_quests(quest_dir: Path) -> tuple[list[ActiveQuest], list[str]]:
    """Load all active quests from .quest/*/state.json.

    Skips archived quests (directories containing 'archive' in path).

    Args:
        quest_dir: Path to .quest directory

    Returns:
        Tuple of (active quests sorted by phase and date, warnings)
    """
    quests: list[ActiveQuest] = []
    warnings: list[str] = []

    if not quest_dir.exists():
        warnings.append(f"Quest directory not found: {quest_dir}")
        return quests, warnings

    for state_path in quest_dir.rglob("state.json"):
        # Skip archived quests -- check path parts to avoid false positives
        # on quest slugs that happen to contain "archive"
        if "archive" in state_path.relative_to(quest_dir).parts:
            continue

        try:
            quest, quest_warnings = _parse_active_quest(state_path)
            quests.append(quest)
            warnings.extend(quest_warnings)
        except Exception as e:
            warnings.append(f"Failed to parse quest state {state_path}: {e}")

    # Sort by phase order (building before plan), then by updated_at descending
    quests.sort(
        key=lambda q: (
            _PHASE_ORDER.get(q.phase.lower().replace(" ", "_"), 999),
            -q.updated_at.timestamp(),
        )
    )

    return quests, warnings


def _parse_active_quest(state_path: Path) -> tuple[ActiveQuest, list[str]]:
    """Parse a single quest state.json and quest_brief.md into an ActiveQuest.

    Args:
        state_path: Path to state.json file

    Returns:
        Tuple of (ActiveQuest with extracted data, list of warnings)
    """
    quest_dir = state_path.parent
    warnings: list[str] = []

    # Load state.json
    state_data = json.loads(state_path.read_text(encoding="utf-8"))

    quest_id = state_data.get("quest_id", quest_dir.name)
    slug = state_data.get("slug", quest_id)
    raw_status = state_data.get("status", "in_progress")
    raw_phase = state_data.get("phase", "plan")
    updated_at_str = state_data.get("updated_at")
    plan_iteration = state_data.get("plan_iteration")
    fix_iteration = state_data.get("fix_iteration")

    # Normalize status and phase for display
    status = _normalize_display_label(raw_status)
    phase = _normalize_display_label(raw_phase)

    # Parse updated_at
    if updated_at_str:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
    else:
        updated_at = datetime.now(tz=UTC)

    # Load quest_brief.md
    brief_path = quest_dir / "quest_brief.md"
    if brief_path.exists():
        brief_content = brief_path.read_text(encoding="utf-8")
        title = _extract_brief_title(brief_content) or slug
        elevator_pitch = _extract_brief_pitch(brief_content) or ""
    else:
        msg = f"Missing quest_brief.md for quest {quest_id} ({quest_dir.name})"
        warnings.append(msg)
        title = slug
        elevator_pitch = ""

    return (
        ActiveQuest(
            quest_id=quest_id,
            slug=slug,
            title=title,
            elevator_pitch=elevator_pitch,
            status=status,
            phase=phase,
            updated_at=updated_at,
            plan_iterations=plan_iteration,
            fix_iterations=fix_iteration,
        ),
        warnings,
    )


def _normalize_display_label(raw_value: str) -> str:
    """Normalize a status or phase value for display.

    Examples:
    - "in_progress" -> "In Progress"
    - "code_review" -> "Code Review"
    """
    return raw_value.replace("_", " ").title()


def _extract_brief_title(content: str) -> str | None:
    """Extract title from quest_brief.md heading.

    Tries:
    1. # Quest Brief: <title>
    2. First # heading
    """
    # Try "# Quest Brief: <title>"
    match = re.search(r"^#\s+Quest Brief:\s*(.+?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Fallback to first heading
    match = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return None


def _extract_brief_pitch(content: str) -> str | None:
    """Extract elevator pitch from quest_brief.md.

    Tries in order:
    1. First paragraph under "## User Input (Original Prompt)" section
    2. First paragraph under "## Requirements" section
    3. First paragraph of entire brief
    """
    # Try Original Prompt section
    match = re.search(
        r"^##\s+User Input \(Original Prompt\)\s*$(.+?)(?=^##|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if match:
        section = match.group(1).strip()
        pitch = _extract_first_paragraph(section)
        if pitch:
            return pitch

    # Try Requirements section
    match = re.search(
        r"^##\s+Requirements\s*$(.+?)(?=^##|\Z)", content, re.MULTILINE | re.DOTALL
    )
    if match:
        section = match.group(1).strip()
        pitch = _extract_first_paragraph(section)
        if pitch:
            return pitch

    # Fallback to first paragraph of entire brief
    return _extract_first_paragraph(content)


def detect_github_url(repo_root: Path) -> str:
    """Auto-detect GitHub repository URL from git remote.

    Args:
        repo_root: Repository root directory

    Returns:
        GitHub HTTPS URL or empty string if detection fails
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip()

            # Convert SSH URL to HTTPS
            if remote_url.startswith("git@github.com:"):
                remote_url = remote_url.replace(
                    "git@github.com:", "https://github.com/"
                )

            # Remove .git suffix
            if remote_url.endswith(".git"):
                remote_url = remote_url[:-4]

            # Validate it's a GitHub URL
            if "github.com" in remote_url:
                return remote_url

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""
