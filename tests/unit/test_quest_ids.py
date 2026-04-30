"""Unit tests for Quest ID formatting and parsing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from quest_runtime.quest_ids import (
    DATE_FIRST,
    DEFAULT_QUEST_ID_FORMAT,
    SLUG_FIRST,
    format_quest_id,
    is_quest_id,
    load_quest_id_format,
    normalize_quest_id_format,
    parse_quest_id,
)


def test_format_quest_id_defaults_to_slug_first() -> None:
    when = datetime(2026, 4, 29, 14, 30)

    assert format_quest_id("portable-pre-commit-review", when) == (
        "portable-pre-commit-review_2026-04-29__1430"
    )


def test_format_quest_id_supports_date_first() -> None:
    when = datetime(2026, 4, 29, 14, 30)

    assert format_quest_id("portable-pre-commit-review", when, DATE_FIRST) == (
        "2026-04-29_1430__portable-pre-commit-review"
    )


def test_parse_quest_id_accepts_slug_first() -> None:
    parsed = parse_quest_id("portable-pre-commit-review_2026-04-29__1430")

    assert parsed is not None
    assert parsed.slug == "portable-pre-commit-review"
    assert parsed.date == "2026-04-29"
    assert parsed.time == "1430"
    assert parsed.quest_id_format == SLUG_FIRST


def test_parse_quest_id_accepts_date_first() -> None:
    parsed = parse_quest_id("2026-04-29_1430__portable-pre-commit-review")

    assert parsed is not None
    assert parsed.slug == "portable-pre-commit-review"
    assert parsed.date == "2026-04-29"
    assert parsed.time == "1430"
    assert parsed.quest_id_format == DATE_FIRST


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Portable_2026-04-29__1430",
        "portable_2026-04-29_1430",
        "2026-04-29__1430__portable",
        "2026-04-29_1430__portable_quest",
        "-portable_2026-04-29__1430",
    ],
)
def test_parse_quest_id_rejects_non_ids(value: str) -> None:
    assert parse_quest_id(value) is None


def test_is_quest_id_accepts_both_formats() -> None:
    assert is_quest_id("portable-pre-commit-review_2026-04-29__1430")
    assert is_quest_id("2026-04-29_1430__portable-pre-commit-review")
    assert not is_quest_id("portable-pre-commit-review")


def test_normalize_quest_id_format_defaults_when_missing() -> None:
    assert normalize_quest_id_format(None) == DEFAULT_QUEST_ID_FORMAT


def test_load_quest_id_format_defaults_when_file_missing(tmp_path: Path) -> None:
    assert load_quest_id_format(tmp_path / "missing.json") == SLUG_FIRST


def test_load_quest_id_format_defaults_when_key_missing(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(json.dumps({"version": 2}), encoding="utf-8")

    assert load_quest_id_format(allowlist) == SLUG_FIRST


def test_load_quest_id_format_reads_date_first(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(json.dumps({"quest_id_format": DATE_FIRST}), encoding="utf-8")

    assert load_quest_id_format(allowlist) == DATE_FIRST


def test_load_quest_id_format_rejects_invalid_value(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(json.dumps({"quest_id_format": "date_slug"}), encoding="utf-8")

    with pytest.raises(ValueError, match="quest_id_format.*slug-first.*date-first"):
        load_quest_id_format(allowlist)
