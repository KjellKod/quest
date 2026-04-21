"""Unit tests for canonical review-intelligence helpers."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from quest_runtime.pr_review_cycle import (
    normalize_pr_review_intake,
    retag_backlog_at_cap,
)
from quest_runtime.review_intelligence import (
    append_deferred_findings,
    build_review_backlog,
    merge_and_dedupe,
    scan_deferred_backlog,
    select_decision,
    synthesize_findings_from_review_markdown,
    synthesize_plan_review_findings,
    validate_findings,
)


def _finding(
    *,
    finding_id: str = "F-001",
    source: str = "code-reviewer-a",
    kind: str = "correctness",
    severity: str = "medium",
    confidence: str = "medium",
    path: str = "scripts/example.py",
    line: int | None = 10,
    summary: str = "Potential issue in edge-case handling.",
    why_it_matters: str = "Could break behavior for uncommon inputs.",
    evidence: list[str] | None = None,
    action: str = "Add guard and tests for this edge case.",
    needs_test: bool = True,
    write_scope: list[str] | None = None,
    related_acceptance_criteria: list[str] | None = None,
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "source": source,
        "kind": kind,
        "severity": severity,
        "confidence": confidence,
        "path": path,
        "line": line,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "evidence": evidence or ["Reproducible with malformed payload."],
        "action": action,
        "needs_test": needs_test,
        "write_scope": write_scope or [path],
        "related_acceptance_criteria": related_acceptance_criteria or ["AC-1"],
    }


def test_validate_findings_accepts_valid_record() -> None:
    errors = validate_findings([_finding()])
    assert errors == []


def test_validate_findings_rejects_missing_required_field() -> None:
    invalid = _finding()
    invalid.pop("summary")
    errors = validate_findings([invalid])
    assert any("missing required field 'summary'" in error for error in errors)


def test_validate_findings_rejects_wrong_types() -> None:
    invalid = _finding(needs_test=True, line=10)
    invalid["line"] = "10"
    invalid["needs_test"] = "yes"
    invalid["evidence"] = "single string"
    errors = validate_findings([invalid])
    assert any("field 'line' must be null or an integer >= 1" in error for error in errors)
    assert any("field 'needs_test' must be a boolean" in error for error in errors)
    assert any("field 'evidence' must be a list[str]" in error for error in errors)


def test_select_decision_fix_now_for_high_severity_strong_evidence() -> None:
    finding = _finding(severity="high", confidence="high", evidence=["a", "b"])
    decision = select_decision(finding, at_loop_cap=False)
    assert decision["decision"] == "fix_now"


def test_select_decision_verify_first_for_uncertain_evidence() -> None:
    finding = _finding(severity="high", confidence="low", evidence=["single"])
    decision = select_decision(finding, at_loop_cap=False)
    assert decision["decision"] == "verify_first"


def test_select_decision_defer_at_loop_cap() -> None:
    finding = _finding(severity="medium", confidence="medium")
    decision = select_decision(finding, at_loop_cap=True)
    assert decision["decision"] == "defer"


def test_select_decision_needs_human_decision_at_loop_cap_for_high_risk() -> None:
    finding = _finding(severity="critical", confidence="high")
    decision = select_decision(finding, at_loop_cap=True)
    assert decision["decision"] == "needs_human_decision"


def test_select_decision_at_loop_cap_includes_accepted_debt_reason() -> None:
    finding = _finding(severity="low", confidence="medium")
    decision = select_decision(finding, at_loop_cap=True)
    assert decision["decision"] == "defer"
    assert "accepted debt" in decision["reason"].lower()


def test_merge_and_dedupe_collapses_cross_source_duplicates() -> None:
    finding_a = _finding(
        finding_id="F-1A",
        source="code-reviewer-a",
        severity="medium",
        confidence="medium",
        evidence=["evidence-a"],
    )
    finding_b = _finding(
        finding_id="F-1B",
        source="code-reviewer-b",
        severity="high",
        confidence="high",
        evidence=["evidence-b"],
    )
    merged = merge_and_dedupe([[finding_a], [finding_b]])
    assert len(merged) == 1
    only = merged[0]
    assert only["severity"] == "high"
    assert only["confidence"] == "high"
    assert only["source_lineage"] == ["code-reviewer-a", "code-reviewer-b"]
    assert set(only["evidence"]) == {"evidence-a", "evidence-b"}


def test_merge_and_dedupe_uses_strongest_severity() -> None:
    weaker = _finding(finding_id="F-weak", severity="low", confidence="medium")
    stronger = _finding(finding_id="F-strong", severity="critical", confidence="high")
    merged = merge_and_dedupe([[weaker], [stronger]])
    assert len(merged) == 1
    assert merged[0]["severity"] == "critical"
    assert merged[0]["confidence"] == "high"


def test_build_review_backlog_merges_dedupes_and_decides() -> None:
    findings = [
        _finding(finding_id="F-1", severity="high", confidence="high", evidence=["one", "two"]),
        _finding(
            finding_id="F-2",
            source="code-reviewer-b",
            severity="medium",
            confidence="medium",
            evidence=["two", "three"],
        ),
    ]
    backlog = build_review_backlog(findings, at_loop_cap=False)
    assert backlog["version"] == 1
    assert len(backlog["items"]) == 1
    assert backlog["items"][0]["decision"] == "fix_now"
    assert backlog["counts"]["fix_now"] == 1


def test_append_deferred_findings_writes_one_json_object_per_line(tmp_path: Path) -> None:
    backlog_path = tmp_path / "deferred_findings.jsonl"
    finding = _finding()
    count = append_deferred_findings(
        backlog_path,
        [finding],
        {
            "deferred_by_quest": "quest-1",
            "deferred_at": "2026-04-16T00:00:00Z",
            "defer_reason": "loop cap reached",
            "proposed_followup": "Create a focused follow-up quest.",
        },
    )
    lines = backlog_path.read_text(encoding="utf-8").splitlines()
    assert count == 1
    assert len(lines) == 1
    assert isinstance(json.loads(lines[0]), dict)


def test_append_deferred_findings_includes_lineage_fields(tmp_path: Path) -> None:
    backlog_path = tmp_path / "deferred_findings.jsonl"
    append_deferred_findings(
        backlog_path,
        [_finding()],
        {
            "deferred_by_quest": "quest-2",
            "deferred_at": "2026-04-16T01:00:00Z",
            "defer_reason": "accepted debt",
            "proposed_followup": "Schedule debt cleanup.",
        },
    )
    record = json.loads(backlog_path.read_text(encoding="utf-8").strip())
    assert record["deferred_by_quest"] == "quest-2"
    assert record["deferred_at"] == "2026-04-16T01:00:00Z"
    assert record["defer_reason"] == "accepted debt"
    assert record["proposed_followup"] == "Schedule debt cleanup."


def test_append_deferred_findings_bootstraps_missing_file(tmp_path: Path) -> None:
    nested = tmp_path / "backlog" / "deferred_findings.jsonl"
    assert not nested.exists()
    append_deferred_findings(
        nested,
        [_finding()],
        {
            "deferred_by_quest": "quest-bootstrap",
            "deferred_at": "2026-04-16T02:00:00Z",
            "defer_reason": "manual defer",
            "proposed_followup": "Re-check after refactor.",
        },
    )
    assert nested.exists()


def test_scan_deferred_backlog_matches_exact_write_scope_path(tmp_path: Path) -> None:
    backlog = tmp_path / "deferred_findings.jsonl"
    entry = _finding(write_scope=["scripts/quest_runtime/artifacts.py"])
    append_deferred_findings(
        backlog,
        [entry],
        {
            "deferred_by_quest": "quest-scan",
            "deferred_at": "2026-04-16T03:00:00Z",
            "defer_reason": "pending priority",
            "proposed_followup": "Pull into next quest.",
        },
    )
    matches = scan_deferred_backlog(
        backlog, {"scripts/quest_runtime/artifacts.py", "tests/unit/test_artifacts.py"}
    )
    assert len(matches) == 1


def test_scan_deferred_backlog_does_not_match_partial_paths(tmp_path: Path) -> None:
    backlog = tmp_path / "deferred_findings.jsonl"
    entry = _finding(write_scope=["scripts/quest_runtime/artifacts.py"])
    append_deferred_findings(
        backlog,
        [entry],
        {
            "deferred_by_quest": "quest-scan-partial",
            "deferred_at": "2026-04-16T04:00:00Z",
            "defer_reason": "pending priority",
            "proposed_followup": "Pull into next quest.",
        },
    )
    matches = scan_deferred_backlog(backlog, {"scripts/quest_runtime"})
    assert matches == []


def test_synthesize_findings_from_review_markdown_parses_path_and_skips_short_bullets() -> None:
    markdown = """
- scripts/quest_runtime/review_intelligence.py:387 High severity parser bug.
- v1.2 causes edge behavior with no slash path.
- short
"""
    findings = synthesize_findings_from_review_markdown(
        markdown,
        source="plan-reviewer-a",
        default_path="phase_01_plan/plan.md",
    )

    assert len(findings) == 2
    first = findings[0]
    second = findings[1]

    assert first["path"] == "scripts/quest_runtime/review_intelligence.py"
    assert first["line"] == 387
    assert first["severity"] == "high"

    # v1.2 should not be mistaken for a filesystem path.
    assert second["path"] == "phase_01_plan/plan.md"
    assert second["line"] is None
    assert validate_findings(findings) == []


def test_synthesize_plan_review_findings_merges_duplicates_across_reviewers() -> None:
    review_a = "- scripts/quest_validate-quest-state.sh:345 High severity backlog routing mismatch."
    review_b = "- scripts/quest_validate-quest-state.sh:345 high severity backlog routing mismatch."
    merged = synthesize_plan_review_findings(review_a, review_b)
    assert len(merged) == 1
    assert merged[0]["source_lineage"] == ["plan-reviewer-a", "plan-reviewer-b"]
    assert validate_findings(merged) == []


def test_normalized_intake_findings_flow_through_existing_backlog_policy() -> None:
    intake = {
        "ci_checks": [
            {
                "job": "unit-tests",
                "state": "failing",
                "failed_path": "scripts/example.py",
                "kind_hint": "test_failure",
            }
        ],
        "inline_comments": [
            {
                "commenter": "reviewer",
                "body": "Looks blocking due to error handling.",
                "path": "scripts/example.py",
                "line": 14,
            }
        ],
        "general_comments": [],
        "existing_findings": [],
    }

    findings = normalize_pr_review_intake(intake)
    assert validate_findings(findings) == []

    backlog = build_review_backlog(findings, at_loop_cap=False)
    assert backlog["version"] == 1
    assert backlog["counts"]["fix_now"] >= 1
    assert all(
        item["decision"]
        in {"fix_now", "verify_first", "defer", "drop", "needs_human_decision"}
        for item in backlog["items"]
    )


def test_retag_backlog_at_cap_uses_select_decision_loop_cap_semantics() -> None:
    finding = _finding(severity="medium", confidence="medium")
    backlog = build_review_backlog([finding], at_loop_cap=False)
    assert backlog["items"][0]["decision"] == "verify_first"

    expected = select_decision(finding, at_loop_cap=True)
    retagged = retag_backlog_at_cap(backlog)
    item = retagged["items"][0]

    assert retagged["at_loop_cap"] is True
    assert item["decision"] == expected["decision"]
    assert item["decision_confidence"] == expected["decision_confidence"]
    assert item["reason"] == expected["reason"]
    assert item["needs_validation"] == expected["needs_validation"]
    assert item["owner"] == expected["owner"]
    assert item["batch"] == expected["batch"]


def test_scan_backlog_cli_accepts_empty_paths(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "deferred_findings.jsonl"
    script = Path(__file__).resolve().parents[2] / "scripts" / "quest_review_intelligence.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "scan-backlog",
            "--jsonl",
            str(jsonl_path),
            "--paths",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["count"] == 0
