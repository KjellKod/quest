"""Contract tests for the workflow.md postflight wire-in.

Plan reference: ``.quest/wrong-location-guardrails_2026-05-18__0003/phase_01_plan/plan.md``
§7.3.

The tests are filename-driven and operate on the canonical
``.skills/quest/delegation/workflow.md`` so they catch any future edit that
drifts the wire-in placement or shifts the cross-reference numbering that
other parts of the doc rely on.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".skills" / "quest" / "delegation" / "workflow.md"

_POSTFLIGHT_LITERAL = "quest_artifact_postflight.py"
_EXPECTED_HELPER = "expected_artifacts_for_role"
_HANDOFF_HEADING = "### Handoff File Polling"
_FALLBACK_LADDER_HEADING = "Three-tier fallback ladder for missing/unparsable handoff.json"
_PREINVOCATION_BULLET = "**Artifact preparation (before every role invocation):**"
_ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _line_index_of(needle: str, text: str) -> int:
    """Return the 0-indexed line number of the first line containing ``needle``.

    Raises AssertionError when the substring is not found.
    """

    for i, line in enumerate(text.splitlines()):
        if needle in line:
            return i
    raise AssertionError(f"substring not found: {needle!r}")


def _next_h3_after(start_line: int, text: str) -> int:
    """Return the line index of the next ``### `` heading after ``start_line``."""

    lines = text.splitlines()
    for i in range(start_line + 1, len(lines)):
        if lines[i].startswith("### "):
            return i
    return len(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_workflow_references_postflight_script(workflow_text: str) -> None:
    """#1: postflight script literal appears at least once in workflow.md."""

    assert workflow_text.count(_POSTFLIGHT_LITERAL) >= 1


def test_workflow_references_expected_artifacts_helper(workflow_text: str) -> None:
    """#2: ``expected_artifacts_for_role`` appears within 200 lines of the
    postflight script reference."""

    lines = workflow_text.splitlines()
    pf_line = _line_index_of(_POSTFLIGHT_LITERAL, workflow_text)

    proximity_window = range(max(0, pf_line - 200), min(len(lines), pf_line + 201))
    helper_present = any(_EXPECTED_HELPER in lines[i] for i in proximity_window)
    assert helper_present, (
        f"expected literal '{_EXPECTED_HELPER}' within 200 lines of "
        f"postflight reference at line {pf_line + 1}"
    )


def test_workflow_postflight_block_is_in_handoff_polling_section(
    workflow_text: str,
) -> None:
    """#3: postflight literal sits between the Handoff File Polling heading
    and the next ``### `` heading."""

    handoff_idx = _line_index_of(_HANDOFF_HEADING, workflow_text)
    next_h3_idx = _next_h3_after(handoff_idx, workflow_text)
    pf_idx = _line_index_of(_POSTFLIGHT_LITERAL, workflow_text)
    assert handoff_idx < pf_idx < next_h3_idx, (
        f"postflight reference at line {pf_idx + 1} must sit between "
        f"Handoff File Polling heading (line {handoff_idx + 1}) and next "
        f"H3 heading (line {next_h3_idx + 1})"
    )


def test_workflow_failure_handling_uses_accepted_with_warnings(
    workflow_text: str,
) -> None:
    """#4: ``accepted_with_warnings`` appears between the Handoff File Polling
    heading and the next H3 heading."""

    handoff_idx = _line_index_of(_HANDOFF_HEADING, workflow_text)
    next_h3_idx = _next_h3_after(handoff_idx, workflow_text)
    lines = workflow_text.splitlines()
    present = any(
        _ACCEPTED_WITH_WARNINGS in lines[i] for i in range(handoff_idx, next_h3_idx)
    )
    assert present, (
        "'accepted_with_warnings' must appear inside the Handoff File "
        "Polling section"
    )


def test_workflow_no_pre_invocation_postflight_reference(workflow_text: str) -> None:
    """#5: postflight literal does NOT appear in the pre-invocation
    ``Artifact preparation`` bullet block (which ends at the next blank line
    after the bullet)."""

    pre_idx = _line_index_of(_PREINVOCATION_BULLET, workflow_text)
    lines = workflow_text.splitlines()
    # Walk forward until we hit a top-level blank-separated bullet boundary.
    # A reasonable boundary is the first line that begins with "6. " (next
    # numbered item) or the next non-indented heading-like line.
    end_idx = len(lines)
    for i in range(pre_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("6.") or (
            lines[i].startswith("**") and "Artifact" not in stripped
        ):
            end_idx = i
            break
    for i in range(pre_idx, end_idx):
        assert _POSTFLIGHT_LITERAL not in lines[i], (
            f"postflight literal must not appear inside the pre-invocation "
            f"Artifact preparation bullet (line {i + 1}: {lines[i]!r})"
        )


def test_workflow_postflight_is_at_end_of_handoff_polling_section(
    workflow_text: str,
) -> None:
    """#6: postflight literal must NOT appear BEFORE the three-tier fallback
    ladder heading within the Handoff File Polling section. Combined with #3
    this pins the postflight literal to the end of the section."""

    handoff_idx = _line_index_of(_HANDOFF_HEADING, workflow_text)
    fallback_idx = _line_index_of(_FALLBACK_LADDER_HEADING, workflow_text)
    pf_idx = _line_index_of(_POSTFLIGHT_LITERAL, workflow_text)
    assert handoff_idx < fallback_idx, (
        "Three-tier fallback ladder heading must come AFTER the Handoff "
        "File Polling heading"
    )
    assert pf_idx > fallback_idx, (
        f"postflight literal at line {pf_idx + 1} must appear AFTER the "
        f"three-tier fallback ladder heading at line {fallback_idx + 1}"
    )


def test_workflow_cross_references_unchanged(workflow_text: str) -> None:
    """#7: Pin cross-reference counts for ``Handoff File Polling §5`` and
    ``Handoff File Polling** §6`` to catch any future placement edit that
    silently shifts the section numbering."""

    s5_count = workflow_text.count("Handoff File Polling §5")
    s6_count = workflow_text.count("Handoff File Polling** §6")
    assert s5_count == 6, (
        f"expected exactly 6 occurrences of 'Handoff File Polling §5'; "
        f"got {s5_count}. A new placement edit may have shifted section "
        f"numbering and silently broken cross-references."
    )
    assert s6_count == 4, (
        f"expected exactly 4 occurrences of 'Handoff File Polling** §6'; "
        f"got {s6_count}. A new placement edit may have shifted section "
        f"numbering and silently broken cross-references."
    )
