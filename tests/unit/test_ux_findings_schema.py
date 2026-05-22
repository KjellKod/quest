"""Verify ux-review's example JSON validates against the canonical findings schema."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _extract_example_finding() -> dict:
    skill_text = (_repo_root() / ".skills" / "ux-review" / "SKILL.md").read_text(encoding="utf-8")
    # Find the first ```json block that looks like a canonical finding.
    matches = re.findall(r"```json\n(\{.*?\})\n```", skill_text, re.DOTALL)
    for block in matches:
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            # The example may contain `<placeholder>` literals; substitute and retry.
            sanitized = re.sub(r"<[^>]+>", "placeholder", block)
            obj = json.loads(sanitized)
        if isinstance(obj, dict) and "finding_id" in obj:
            return obj
    raise AssertionError("Could not find a canonical-finding JSON block in ux-review/SKILL.md")


def test_ux_example_finding_validates_against_canonical_schema() -> None:
    sys.path.insert(0, str(_repo_root() / "scripts"))
    from quest_runtime.review_intelligence import validate_finding  # noqa: E402

    finding = _extract_example_finding()
    # Coerce any placeholder strings into valid example values.
    for field in ("evidence", "write_scope", "related_acceptance_criteria"):
        value = finding.get(field)
        if isinstance(value, str):
            finding[field] = [value]
        elif value is None:
            finding[field] = []
    if finding.get("line") in (None, 0):
        finding["line"] = 1
    if not isinstance(finding.get("needs_test"), bool):
        finding["needs_test"] = False
    if finding.get("severity") not in ("critical", "high", "medium", "low", "info"):
        finding["severity"] = "high"
    if finding.get("confidence") not in ("high", "medium", "low"):
        finding["confidence"] = "high"

    errors = validate_finding(finding)
    assert errors == [], f"ux-review example finding does not validate: {errors}"
