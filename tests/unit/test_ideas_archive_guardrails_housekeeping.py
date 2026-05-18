"""Contract tests for Slice G housekeeping (idea archival + Done Index row).

Plan reference: ``.quest/wrong-location-guardrails_2026-05-18__0003/phase_01_plan/plan.md``
§10 Slice G.

These tests assert:
(a) the three idea docs are now under ``ideas/archive/``;
(b) ``ideas/README.md`` contains a ``done`` row pointing at the quest
    journal path ``docs/quest-journal/wrong-location-guardrails_2026-05-18.md``.

The journal file itself is written at quest completion (after this builder
phase); the test asserts the link exists in the README, not the file on disk.
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_IDEAS_DIR = _REPO_ROOT / "ideas"
_ARCHIVE_DIR = _IDEAS_DIR / "archive"
_README = _IDEAS_DIR / "README.md"

_ARCHIVED_FILES = (
    "2026-05-17-wrong-location-guardrails.md",
    "2026-04-15-pretooluse-branch-dir-verification-hook.md",
    "2026-04-15-subagent-path-constraints-hardening.md",
)

_JOURNAL_REL_LINK = "docs/quest-journal/wrong-location-guardrails_2026-05-18.md"


def test_archived_idea_docs_exist_under_archive_dir() -> None:
    """(a): the three idea docs live under ideas/archive/ now."""

    for name in _ARCHIVED_FILES:
        path = _ARCHIVE_DIR / name
        assert path.exists(), f"expected archived idea doc at {path}"
        # They MUST NOT also remain at the active location.
        assert not (_IDEAS_DIR / name).exists(), (
            f"{name} must not remain at the active ideas/ root"
        )


def test_ideas_readme_has_done_row_pointing_at_quest_journal() -> None:
    """(b): ``ideas/README.md`` contains a ``done`` row for this quest with
    a link to the quest-journal entry."""

    text = _README.read_text(encoding="utf-8")
    # Locate the Done Index section.
    assert "### Done Index" in text, "expected '### Done Index' section in README"
    done_block = text.split("### Done Index", 1)[1]
    assert "wrong-location-guardrails" in done_block, (
        "Done Index must contain a row mentioning 'wrong-location-guardrails'"
    )
    # Link must point at the future quest-journal path (relative form).
    assert _JOURNAL_REL_LINK in done_block, (
        f"Done Index row must link at {_JOURNAL_REL_LINK}"
    )
    # Active "Execution Discipline and Observability" section must no longer
    # list the three rows.
    exec_section_marker = "### Execution Discipline and Observability"
    if exec_section_marker in text:
        # Slice between this header and the next ### header.
        after = text.split(exec_section_marker, 1)[1]
        next_h3 = after.find("\n### ")
        if next_h3 > 0:
            after = after[:next_h3]
        for name in _ARCHIVED_FILES:
            assert name not in after, (
                f"{name} must not remain in the active 'Execution Discipline "
                f"and Observability' section after archival"
            )
