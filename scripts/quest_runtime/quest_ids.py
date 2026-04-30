"""Quest ID formatting and parsing helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SLUG_FIRST = "slug-first"
DATE_FIRST = "date-first"
DEFAULT_QUEST_ID_FORMAT = SLUG_FIRST
VALID_QUEST_ID_FORMATS = (SLUG_FIRST, DATE_FIRST)

_SLUG_PATTERN = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_SLUG_FIRST_RE = re.compile(
    rf"^(?P<slug>{_SLUG_PATTERN})_(?P<date>\d{{4}}-\d{{2}}-\d{{2}})__(?P<time>\d{{4}})$"
)
_DATE_FIRST_RE = re.compile(
    rf"^(?P<date>\d{{4}}-\d{{2}}-\d{{2}})_(?P<time>\d{{4}})__(?P<slug>{_SLUG_PATTERN})$"
)


@dataclass(frozen=True)
class ParsedQuestId:
    """Structured fields extracted from a supported Quest ID."""

    slug: str
    date: str
    time: str
    quest_id_format: str


def normalize_quest_id_format(value: str | None) -> str:
    """Return a known quest ID format or raise for invalid config values."""
    if value is None:
        return DEFAULT_QUEST_ID_FORMAT
    if value in VALID_QUEST_ID_FORMATS:
        return value
    allowed = ", ".join(VALID_QUEST_ID_FORMATS)
    raise ValueError(f"Invalid quest_id_format: {value!r}. Expected one of: {allowed}.")


def format_quest_id(
    slug: str,
    when: datetime,
    quest_id_format: str = DEFAULT_QUEST_ID_FORMAT,
) -> str:
    """Format a quest ID using the selected supported format."""
    normalized = normalize_quest_id_format(quest_id_format)
    if not re.fullmatch(_SLUG_PATTERN, slug):
        raise ValueError("Invalid slug. Expected lowercase letters, numbers, and hyphens.")

    date_part = when.strftime("%Y-%m-%d")
    time_part = when.strftime("%H%M")
    if normalized == DATE_FIRST:
        return f"{date_part}_{time_part}__{slug}"
    return f"{slug}_{date_part}__{time_part}"


def parse_quest_id(value: str) -> ParsedQuestId | None:
    """Parse either supported Quest ID format, returning None for non-matches."""
    slug_first = _SLUG_FIRST_RE.fullmatch(value)
    if slug_first:
        return ParsedQuestId(
            slug=slug_first.group("slug"),
            date=slug_first.group("date"),
            time=slug_first.group("time"),
            quest_id_format=SLUG_FIRST,
        )

    date_first = _DATE_FIRST_RE.fullmatch(value)
    if date_first:
        return ParsedQuestId(
            slug=date_first.group("slug"),
            date=date_first.group("date"),
            time=date_first.group("time"),
            quest_id_format=DATE_FIRST,
        )

    return None


def is_quest_id(value: str) -> bool:
    """Return whether the value is a supported Quest ID."""
    return parse_quest_id(value) is not None


def load_quest_id_format(allowlist_path: Path) -> str:
    """Load quest_id_format from allowlist JSON, defaulting when missing."""
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_QUEST_ID_FORMAT
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {allowlist_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid allowlist.json: expected object at {allowlist_path}.")

    value = data.get("quest_id_format")
    if value is not None and not isinstance(value, str):
        allowed = ", ".join(VALID_QUEST_ID_FORMATS)
        raise ValueError(f"Invalid quest_id_format: {value!r}. Expected one of: {allowed}.")
    return normalize_quest_id_format(value)
