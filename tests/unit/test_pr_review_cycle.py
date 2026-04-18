"""Unit tests for PR review-cycle intake, batching, and stop classification."""

from __future__ import annotations

import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from quest_runtime.pr_review_cycle import (
    build_fix_batches,
    classify_pr_loop_stop,
    normalize_pr_review_intake,
)
from quest_runtime.review_intelligence import validate_findings


def _validation_step(target: str, *, level: int = 1) -> list[dict[str, object]]:
    return [
        {
            "level": level,
            "target": target,
            "command": f"python3 -m pytest {target}",
            "reason": "test",
        }
    ]


def _backlog_item(
    finding_id: str,
    *,
    decision: str = "fix_now",
    severity: str = "medium",
    confidence: str = "medium",
    path: str = "module/a.py",
    write_scope: list[str] | None = None,
    validation_steps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "source": "reviewer",
        "kind": "review_comment",
        "severity": severity,
        "confidence": confidence,
        "path": path,
        "line": None,
        "summary": "summary",
        "why_it_matters": "matters",
        "evidence": ["evidence"],
        "action": "action",
        "needs_test": False,
        "write_scope": write_scope or [],
        "related_acceptance_criteria": [],
        "decision": decision,
        "decision_confidence": "medium",
        "reason": "reason",
        "needs_validation": [],
        "owner": "builder",
        "batch": "batch",
        "validation_steps": validation_steps or _validation_step("tests/unit/test_default.py"),
    }


def test_normalize_pr_review_intake_merges_ci_inline_general_into_canonical_findings() -> None:
    intake = {
        "ci_checks": [
            {
                "job": "unit",
                "state": "failing",
                "failed_path": "scripts/quest_runtime/pr_review_cycle.py",
                "kind_hint": "test_failure",
            },
            {
                "job": "lint",
                "state": "green",
                "failed_path": None,
            },
        ],
        "inline_comments": [
            {
                "commenter": "alice",
                "body": "This is blocking because it breaks id generation.",
                "path": "scripts/quest_runtime/pr_review_cycle.py",
                "line": 42,
            }
        ],
        "general_comments": [
            {"commenter": "bob", "body": "Please tighten this flow before merge."}
        ],
        "existing_findings": [
            {
                "finding_id": "existing-001",
                "source": "historical",
                "kind": "review_comment",
                "severity": "low",
                "confidence": "low",
                "path": "docs/notes.md",
                "line": None,
                "summary": "Existing note",
                "why_it_matters": "Track deferred concern.",
                "evidence": ["prior evidence"],
                "action": "Keep in backlog.",
                "needs_test": False,
                "write_scope": ["docs/notes.md"],
                "related_acceptance_criteria": [],
            }
        ],
    }

    findings = normalize_pr_review_intake(intake)
    assert len(findings) == 4
    assert validate_findings(findings) == []

    finding_ids = {finding["finding_id"] for finding in findings}
    assert "pr-ci-001" in finding_ids
    assert "pr-inline-001" in finding_ids
    assert "pr-general-001" in finding_ids
    assert "existing-001" in finding_ids

    inline = next(finding for finding in findings if finding["finding_id"] == "pr-inline-001")
    ci = next(finding for finding in findings if finding["finding_id"] == "pr-ci-001")

    assert inline["severity"] == "high"
    assert inline["needs_test"] is True
    assert ci["evidence"] == ["ci:unit state=failing"]
    assert ci["needs_test"] is True


def test_build_fix_batches_groups_by_write_scope_and_validation_scope() -> None:
    items = [
        _backlog_item(
            "F-002",
            decision="fix_now",
            path="module/a.py",
            write_scope=[],
            validation_steps=_validation_step("tests/unit/test_a.py"),
        ),
        _backlog_item(
            "F-001",
            decision="verify_first",
            path="module/a.py",
            write_scope=[],
            validation_steps=_validation_step("tests/unit/test_a.py"),
        ),
        _backlog_item(
            "F-003",
            decision="fix_now",
            path="module/a.py",
            write_scope=[],
            validation_steps=_validation_step("tests/integration/test_a.py"),
        ),
        _backlog_item("F-004", decision="defer", path="module/a.py", write_scope=[]),
    ]

    batches = build_fix_batches(items)
    assert len(batches) == 2

    first = batches[0]
    second = batches[1]
    assert first["batch_key"] == "module/a.py"
    assert [item["finding_id"] for item in first["items"]] == ["F-001", "F-002"]
    assert [item["finding_id"] for item in second["items"]] == ["F-003"]


def test_build_fix_batches_detects_exact_path_overlap() -> None:
    items = [
        _backlog_item(
            "F-001",
            write_scope=["scripts/quest_runtime/pr_review_cycle.py"],
            validation_steps=_validation_step("tests/unit/test_one.py"),
        ),
        _backlog_item(
            "F-002",
            write_scope=["scripts/quest_runtime/pr_review_cycle.py"],
            validation_steps=_validation_step("tests/unit/test_one.py"),
        ),
    ]

    batches = build_fix_batches(items)
    assert len(batches) == 2
    assert [batch["batch_id"] for batch in batches] == [
        "scripts/quest_runtime/pr_review_cycle.py-1",
        "scripts/quest_runtime/pr_review_cycle.py-2",
    ]


def test_build_fix_batches_detects_parent_child_prefix_overlap() -> None:
    items = [
        _backlog_item(
            "F-001",
            write_scope=["scripts/quest_runtime"],
            validation_steps=_validation_step("tests/unit/test_one.py"),
        ),
        _backlog_item(
            "F-002",
            write_scope=["scripts/quest_runtime/pr_review_cycle.py"],
            validation_steps=_validation_step("tests/unit/test_one.py"),
        ),
    ]

    batches = build_fix_batches(items)
    assert len(batches) == 2


def test_build_fix_batches_normalizes_trailing_slash_for_overlap() -> None:
    items = [
        _backlog_item(
            "F-001",
            write_scope=["scripts/quest_runtime/"],
            validation_steps=_validation_step("tests/unit/test_one.py"),
        ),
        _backlog_item(
            "F-002",
            write_scope=["scripts/quest_runtime/pr_review_cycle.py"],
            validation_steps=_validation_step("tests/unit/test_one.py"),
        ),
    ]

    batches = build_fix_batches(items)
    assert len(batches) == 2


def test_build_fix_batches_is_deterministic_for_shuffled_input() -> None:
    items = [
        _backlog_item(
            "F-003",
            path="module/a.py",
            write_scope=[],
            validation_steps=_validation_step("tests/unit/test_a.py"),
        ),
        _backlog_item(
            "F-001",
            path="module/a.py",
            write_scope=[],
            validation_steps=_validation_step("tests/unit/test_a.py"),
        ),
        _backlog_item(
            "F-002",
            path="module/a.py",
            write_scope=[],
            validation_steps=_validation_step("tests/unit/test_b.py"),
        ),
    ]
    baseline = build_fix_batches(items)

    shuffled = items[:]
    random.Random(7).shuffle(shuffled)
    rerun = build_fix_batches(shuffled)

    assert baseline == rerun


@pytest.mark.parametrize(
    ("ci_state", "actionable_count", "iteration"),
    [
        (ci_state, actionable_count, iteration)
        for ci_state in ("green", "failing", "pending", "unknown")
        for actionable_count in (0, 2)
        for iteration in (2, 3, 4)
    ],
)
def test_classify_pr_loop_stop_matrix(
    ci_state: str, actionable_count: int, iteration: int
) -> None:
    cap = 3
    result = classify_pr_loop_stop(
        ci_state=ci_state,
        actionable_count=actionable_count,
        iteration=iteration,
        cap=cap,
    )

    if ci_state == "green" and actionable_count == 0 and iteration <= cap:
        assert result["stop"] is True
        assert result["outcome"] == "success"
        assert result["retag_required"] is False
        return

    if iteration < cap:
        assert result["stop"] is False
        assert result["outcome"] == "continue"
        assert result["retag_required"] is False
    else:
        assert result["stop"] is True
        assert result["outcome"] == "cap_enforced"
        assert result["retag_required"] is (actionable_count > 0)


def test_cli_normalize_pr_intake_round_trip(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "quest_review_intelligence.py"
    input_path = tmp_path / "intake.json"
    output_path = tmp_path / "findings.json"

    intake = {
        "ci_checks": [
            {
                "job": "unit",
                "state": "failing",
                "failed_path": "scripts/example.py",
                "kind_hint": "test_failure",
            }
        ],
        "inline_comments": [],
        "general_comments": [],
        "existing_findings": [],
    }
    input_path.write_text(json.dumps(intake), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "normalize-pr-intake",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    findings = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(findings, list)
    assert validate_findings(findings) == []


def test_cli_build_fix_batches_round_trip(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "quest_review_intelligence.py"
    backlog_path = tmp_path / "review_backlog.json"
    output_path = tmp_path / "batches.json"

    backlog_payload = {
        "items": [
            _backlog_item(
                "F-001",
                decision="fix_now",
                write_scope=["scripts/a.py"],
                validation_steps=_validation_step("tests/unit/test_a.py"),
            ),
            _backlog_item(
                "F-002",
                decision="defer",
                write_scope=["scripts/b.py"],
                validation_steps=_validation_step("tests/unit/test_b.py"),
            ),
        ]
    }
    backlog_path.write_text(json.dumps(backlog_payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "build-fix-batches",
            "--backlog",
            str(backlog_path),
            "--output",
            str(output_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    batches = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(batches, list)
    assert len(batches) == 1
    assert batches[0]["batch_key"] == "scripts/a.py"


def test_cli_classify_pr_stop_round_trip(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "quest_review_intelligence.py"
    quest_id = "sample-quest_2026-04-17__2101"
    backlog_dir = tmp_path / ".quest" / quest_id / "phase_03_review"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    backlog_path = backlog_dir / "review_backlog.json"
    retag_output = tmp_path / "retagged_backlog.json"

    backlog_payload = {
        "version": 1,
        "generated_at": "2026-01-01T00:00:00Z",
        "at_loop_cap": False,
        "allowed_decisions": [
            "fix_now",
            "verify_first",
            "defer",
            "drop",
            "needs_human_decision",
        ],
        "counts": {
            "fix_now": 1,
            "verify_first": 0,
            "defer": 0,
            "drop": 0,
            "needs_human_decision": 0,
        },
        "items": [
            _backlog_item(
                "F-001",
                decision="fix_now",
                severity="medium",
                confidence="medium",
                write_scope=["scripts/a.py"],
            ),
        ],
    }
    backlog_path.write_text(json.dumps(backlog_payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "classify-pr-stop",
            "--ci-state",
            "failing",
            "--actionable",
            "1",
            "--iteration",
            "3",
            "--cap",
            "3",
            "--backlog",
            str(backlog_path),
            "--retag-output",
            str(retag_output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["stop"] is True
    assert payload["outcome"] == "cap_enforced"
    assert payload["retag_required"] is True
    assert "deferred_count" in payload
    assert payload["deferred_count"] == 1

    retagged = json.loads(backlog_path.read_text(encoding="utf-8"))
    assert retagged["at_loop_cap"] is True
    assert retagged["counts"]["fix_now"] == 0
    assert retagged["counts"]["defer"] == 1
    assert retag_output.exists()

    deferred_path = tmp_path / ".quest" / "backlog" / "deferred_findings.jsonl"
    assert deferred_path.exists()
    first_record = json.loads(deferred_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_record["deferred_by_quest"] == quest_id
