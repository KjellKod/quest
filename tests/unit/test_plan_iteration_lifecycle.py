"""Regression tests for immutable Quest plan-iteration lifecycles."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import quest_runtime.plan_iterations as plan_iterations_module
from quest_runtime.artifacts import prepare_artifact_files
from quest_runtime.plan_iterations import (
    PlanIterationError,
    cleanup_current_plan_iteration,
    publish_refinement,
    snapshot_plan_iteration,
    verify_plan_iteration_snapshot,
    verify_refinement,
)
from quest_runtime.state import update_state

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_state(
    quest_dir: Path,
    *,
    iteration: int = 1,
    mode: str = "workflow",
) -> None:
    _write_json(
        quest_dir / "state.json",
        {
            "phase": "plan",
            "status": "in_progress",
            "quest_mode": mode,
            "plan_iteration": iteration,
        },
    )


def _handoff(next_role: str, iteration: int = 1) -> dict[str, object]:
    return {
        "status": "complete",
        "artifacts": ["artifact.md"],
        "next": next_role,
        "summary": "fixture producer output",
        "plan_iteration": iteration,
        "user_replan_generation": None,
    }


def _write_completed_iteration(
    quest_dir: Path,
    *,
    iteration: int = 1,
    mode: str = "workflow",
    decision: str = "builder",
) -> Path:
    """Write real producer outputs without consulting production inventory."""

    _write_state(quest_dir, iteration=iteration, mode=mode)
    plan_dir = quest_dir / "phase_01_plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan.md").write_text("# Current plan\n", encoding="utf-8")
    _write_json(plan_dir / "handoff.json", _handoff("plan_review", iteration))
    (plan_dir / "review_plan-reviewer-a.md").write_text(
        "# Reviewer A\nApproved\n", encoding="utf-8"
    )

    reviewer_next = "planner" if decision == "planner" else "arbiter"
    _write_json(
        plan_dir / "handoff_plan-reviewer-a.json",
        _handoff(reviewer_next, iteration),
    )
    if mode == "solo":
        return plan_dir

    (plan_dir / "review_plan-reviewer-b.md").write_text(
        "# Reviewer B\nApproved\n", encoding="utf-8"
    )
    _write_json(
        plan_dir / "handoff_plan-reviewer-b.json",
        _handoff("arbiter", iteration),
    )
    (plan_dir / "arbiter_verdict.md").write_text(
        "VERDICT: APPROVE\n" if decision == "builder" else "VERDICT: ITERATE\n",
        encoding="utf-8",
    )
    _write_json(
        plan_dir / "handoff_arbiter.json",
        _handoff(decision, iteration),
    )
    if decision == "builder":
        _write_json(plan_dir / "review_findings.json", [])
        _write_json(
            plan_dir / "review_backlog.json",
            {"version": 1, "phase": "plan", "items": []},
        )
    else:
        verdict = (plan_dir / "arbiter_verdict.md").read_bytes()
        _write_json(
            plan_dir / "refinement_binding.json",
            {
                "source_plan_iteration": iteration,
                "requested_plan_iteration": iteration + 1,
                "verdict_sha256": _sha256(verdict),
                "arbiter_handoff_sha256": _sha256(
                    (plan_dir / "handoff_arbiter.json").read_bytes()
                ),
                "next": "planner",
            },
        )
    return plan_dir


def _valid_finding() -> dict[str, object]:
    return {
        "finding_id": "PLAN-1",
        "source": "arbiter",
        "kind": "plan",
        "severity": "medium",
        "confidence": "high",
        "path": "phase_01_plan/plan.md",
        "line": 1,
        "summary": "Clarify one lifecycle edge.",
        "why_it_matters": "The next Planner must receive exact feedback.",
        "evidence": ["Reviewer A and Reviewer B agree."],
        "action": "Revise the named plan section.",
        "needs_test": True,
        "write_scope": ["phase_01_plan/plan.md"],
        "related_acceptance_criteria": ["AC-15"],
    }


def _tree_signature(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        str(path.relative_to(root)): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_workflow_planner_snapshot_matches_real_producer_inventory(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="planner")
    _write_json(plan_dir / "review_findings.json.next", [_valid_finding()])

    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)

    archived = {
        path.name for path in snapshot_dir.iterdir() if path.name != "snapshot.sha256"
    }
    assert archived == {
        "snapshot.json",
        "plan.md",
        "handoff_planner.json",
        "review_plan-reviewer-a.md",
        "handoff_plan-reviewer-a.json",
        "review_plan-reviewer-b.md",
        "handoff_plan-reviewer-b.json",
        "arbiter_verdict.md",
        "handoff_arbiter.json",
        "refinement_binding.json",
    }
    assert not (snapshot_dir / "review_findings.json").exists()
    assert (plan_dir / "review_findings.json.next").exists()

    manifest = json.loads((snapshot_dir / "snapshot.json").read_text())
    assert manifest["mode"] == "workflow"
    assert manifest["decision"] == "planner"
    assert manifest["version"] == 1
    assert manifest["files"]["handoff_planner.json"]["source"] == "handoff.json"


@pytest.mark.parametrize("missing", ["review_findings.json", "review_backlog.json"])
def test_workflow_builder_snapshot_requires_each_published_review_artifact(
    tmp_path: Path,
    missing: str,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    (plan_dir / missing).unlink()

    with pytest.raises(PlanIterationError, match=missing):
        snapshot_plan_iteration(quest_dir, 1)

    assert not (quest_dir / "history" / "plan" / "iteration-0001").exists()


def test_solo_snapshot_never_requires_workflow_only_artifacts(tmp_path: Path) -> None:
    quest_dir = tmp_path / "quest"
    _write_completed_iteration(quest_dir, mode="solo", decision="builder")

    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)

    archived = {path.name for path in snapshot_dir.iterdir()}
    assert "review_plan-reviewer-b.md" not in archived
    assert "handoff_plan-reviewer-b.json" not in archived
    assert "arbiter_verdict.md" not in archived
    assert "handoff_arbiter.json" not in archived
    assert "review_findings.json" not in archived
    assert "review_backlog.json" not in archived
    assert "refinement_binding.json" not in archived


def test_repeat_snapshot_verifies_archive_without_rewriting_any_file(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)
    before = _tree_signature(snapshot_dir)

    # Canonical paths now belong to a later round and must not be compared to
    # the already-sealed audit snapshot.
    (plan_dir / "plan.md").write_text("# Revised plan\n", encoding="utf-8")
    assert snapshot_plan_iteration(quest_dir, 1) == snapshot_dir

    assert _tree_signature(snapshot_dir) == before


def test_corrupt_sealed_snapshot_fails_without_repairing_history(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_completed_iteration(quest_dir, decision="builder")
    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)
    archived_plan = snapshot_dir / "plan.md"
    archived_plan.write_bytes(b"CORRUPTED\n")
    corrupted = _tree_signature(snapshot_dir)

    with pytest.raises(PlanIterationError, match="mismatch"):
        snapshot_plan_iteration(quest_dir, 1)

    assert _tree_signature(snapshot_dir) == corrupted


def test_existing_legacy_manifest_is_verified_and_sealed_in_place(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_state(quest_dir, iteration=1)
    snapshot_dir = quest_dir / "history" / "plan" / "iteration-0001"
    snapshot_dir.mkdir(parents=True)
    archived_plan = snapshot_dir / "plan.md"
    archived_plan.write_bytes(b"# Legacy plan\n")
    legacy_manifest = {
        "plan_iteration": 1,
        "quest_mode": "workflow",
        "decision": "planner",
        "reason": "automatic_refinement",
        "bootstrap_snapshot": True,
        "files": {"plan.md": _sha256(archived_plan.read_bytes())},
    }
    _write_json(snapshot_dir / "snapshot.json", legacy_manifest)
    before = {
        "plan.md": archived_plan.read_bytes(),
        "snapshot.json": (snapshot_dir / "snapshot.json").read_bytes(),
    }
    real_publish = plan_iterations_module._atomic_publish_bytes
    published: list[Path] = []

    def record_publish(path: Path, data: bytes) -> None:
        published.append(path)
        real_publish(path, data)

    monkeypatch.setattr(plan_iterations_module, "_atomic_publish_bytes", record_publish)

    # Deliberately omit the new producer inventory from canonical paths. A
    # byte-valid legacy archive is its own identity and is never recaptured.
    assert snapshot_plan_iteration(quest_dir, 1) == snapshot_dir

    assert archived_plan.read_bytes() == before["plan.md"]
    assert (snapshot_dir / "snapshot.json").read_bytes() == before["snapshot.json"]
    assert (snapshot_dir / "snapshot.sha256").read_text().strip() == _sha256(
        before["snapshot.json"]
    )
    assert published == [snapshot_dir / "snapshot.sha256"]


def test_invalid_legacy_manifest_iteration_is_not_sealed(tmp_path: Path) -> None:
    quest_dir = tmp_path / "quest"
    _write_state(quest_dir, iteration=1)
    snapshot_dir = quest_dir / "history" / "plan" / "iteration-0001"
    snapshot_dir.mkdir(parents=True)
    archived_plan = snapshot_dir / "plan.md"
    archived_plan.write_bytes(b"# Wrong iteration\n")
    _write_json(
        snapshot_dir / "snapshot.json",
        {
            "plan_iteration": 2,
            "files": {"plan.md": _sha256(archived_plan.read_bytes())},
        },
    )

    with pytest.raises(PlanIterationError, match="snapshot_iteration_mismatch"):
        verify_plan_iteration_snapshot(quest_dir, 1)

    assert not (snapshot_dir / "snapshot.sha256").exists()


@pytest.mark.parametrize("boundary", ["open", "fsync"])
def test_directory_fsync_failures_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    def fail(*_args, **_kwargs):
        raise OSError(f"{boundary} failed")

    monkeypatch.setattr(plan_iterations_module.os, boundary, fail)

    with pytest.raises(PlanIterationError, match="directory_fsync_failed"):
        plan_iterations_module._fsync_dir(tmp_path)


@pytest.mark.parametrize("mode", ["workflow", "solo"])
def test_legacy_canonical_iteration_without_typed_handoffs_bootstraps_snapshot(
    tmp_path: Path,
    mode: str,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, mode=mode, decision="builder")
    for handoff_path in plan_dir.glob("handoff*.json"):
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff.pop("plan_iteration")
        handoff.pop("user_replan_generation")
        _write_json(handoff_path, handoff)

    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)

    manifest = json.loads((snapshot_dir / "snapshot.json").read_text())
    assert manifest["bootstrap_snapshot"] is True
    assert (snapshot_dir / "plan.md").read_bytes() == (
        plan_dir / "plan.md"
    ).read_bytes()
    assert (snapshot_dir / "handoff_planner.json").exists()
    if mode == "solo":
        assert not (snapshot_dir / "handoff_arbiter.json").exists()
    else:
        assert (snapshot_dir / "handoff_arbiter.json").exists()


def test_untyped_handoffs_cannot_bootstrap_after_plan_history_exists(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_completed_iteration(quest_dir, iteration=1, decision="builder")
    first_snapshot = snapshot_plan_iteration(quest_dir, 1)
    first_plan = (first_snapshot / "plan.md").read_bytes()

    plan_dir = _write_completed_iteration(quest_dir, iteration=2, decision="builder")
    (plan_dir / "plan.md").write_text(
        "# Current iteration two plan\n", encoding="utf-8"
    )
    for handoff_path in plan_dir.glob("handoff*.json"):
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff.pop("plan_iteration")
        handoff.pop("user_replan_generation")
        _write_json(handoff_path, handoff)

    with pytest.raises(PlanIterationError, match="handoff_iteration_mismatch"):
        snapshot_plan_iteration(quest_dir, 2)

    assert (first_snapshot / "plan.md").read_bytes() == first_plan
    assert not (quest_dir / "history" / "plan" / "iteration-0002").exists()


@pytest.mark.parametrize("sealed", [True, False])
def test_manifest_metadata_shape_uses_stable_plan_iteration_error(
    tmp_path: Path,
    sealed: bool,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_completed_iteration(quest_dir, decision="builder")
    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)
    manifest_path = snapshot_dir / "snapshot.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["plan.md"] = 7
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    seal_path = snapshot_dir / "snapshot.sha256"
    if sealed:
        seal_path.write_text(f"{_sha256(manifest_bytes)}\n", encoding="ascii")
    else:
        seal_path.unlink()

    with pytest.raises(PlanIterationError, match="snapshot_manifest_invalid"):
        verify_plan_iteration_snapshot(quest_dir, 1)


def test_legacy_reseal_wraps_corrupt_manifest_and_missing_file_errors(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_state(quest_dir)
    snapshot_dir = quest_dir / "history" / "plan" / "iteration-0001"
    snapshot_dir.mkdir(parents=True)
    manifest_path = snapshot_dir / "snapshot.json"
    manifest_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(PlanIterationError, match="snapshot_manifest_invalid"):
        verify_plan_iteration_snapshot(quest_dir, 1)

    _write_json(
        manifest_path,
        {
            "plan_iteration": 1,
            "files": {"missing.md": _sha256(b"missing")},
        },
    )
    with pytest.raises(PlanIterationError, match="snapshot_file_missing:missing.md"):
        verify_plan_iteration_snapshot(quest_dir, 1)


def test_snapshot_holds_state_lock_through_source_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    target_source = (plan_dir / "plan.md").resolve()
    original_read_bytes = Path.read_bytes
    started = threading.Event()
    mutation_complete = threading.Event()
    worker: threading.Thread | None = None

    def mutate_state() -> None:
        started.set()
        update_state(quest_dir, plan_iteration=2)
        mutation_complete.set()

    def read_bytes(path: Path) -> bytes:
        nonlocal worker
        if path.resolve() == target_source and worker is None:
            worker = threading.Thread(target=mutate_state)
            worker.start()
            assert started.wait(1)
            assert not mutation_complete.wait(
                0.1
            ), "state mutation interleaved with snapshot source capture"
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    snapshot_plan_iteration(quest_dir, 1)
    assert worker is not None
    worker.join(timeout=2)
    assert mutation_complete.is_set()


def test_snapshot_rejects_refinement_binding_for_another_iteration(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="planner")
    binding_path = plan_dir / "refinement_binding.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["source_plan_iteration"] = 0
    _write_json(binding_path, binding)

    with pytest.raises(PlanIterationError, match="refinement_iteration_mismatch"):
        snapshot_plan_iteration(quest_dir, 1)

    assert not (quest_dir / "history" / "plan" / "iteration-0001").exists()


def test_first_capture_failure_leaves_no_partial_snapshot(tmp_path: Path) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    (plan_dir / "review_plan-reviewer-b.md").unlink()

    with pytest.raises(PlanIterationError, match="review_plan-reviewer-b.md"):
        snapshot_plan_iteration(quest_dir, 1)

    history_root = quest_dir / "history" / "plan"
    assert not (history_root / "iteration-0001").exists()
    assert list(history_root.glob(".iteration-0001.*")) == []


def test_cleanup_rejects_wrong_or_corrupt_snapshot_before_deleting_artifacts(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)
    scratch = plan_dir / "review_findings.json.next"
    scratch.write_text("scratch\n", encoding="utf-8")
    before = _tree_signature(plan_dir)

    with pytest.raises(PlanIterationError, match="iteration_mismatch"):
        cleanup_current_plan_iteration(quest_dir, 2)
    assert _tree_signature(plan_dir) == before

    (snapshot_dir / "plan.md").write_text("corrupt\n", encoding="utf-8")
    with pytest.raises(PlanIterationError, match="mismatch"):
        cleanup_current_plan_iteration(quest_dir, 1)
    assert _tree_signature(plan_dir) == before


def test_cleanup_removes_only_handoffs_and_transient_scratch(tmp_path: Path) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    snapshot_plan_iteration(quest_dir, 1)
    (plan_dir / "arbiter_verdict.md.next").write_text(
        "scratch verdict\n", encoding="utf-8"
    )
    (plan_dir / "review_findings.json.next").write_text(
        "scratch findings\n", encoding="utf-8"
    )

    cleanup_current_plan_iteration(quest_dir, 1)

    assert list(plan_dir.glob("handoff*.json")) == []
    assert list(plan_dir.glob("*.next")) == []
    assert (plan_dir / "plan.md").read_text() == "# Current plan\n"
    assert (plan_dir / "arbiter_verdict.md").exists()
    assert (plan_dir / "review_findings.json").exists()
    assert (plan_dir / "review_backlog.json").exists()


def test_cleanup_holds_state_lock_through_verification_and_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_completed_iteration(quest_dir, decision="builder")
    snapshot_plan_iteration(quest_dir, 1)
    original_verify = plan_iterations_module.verify_plan_iteration_snapshot
    started = threading.Event()
    mutation_complete = threading.Event()
    worker: threading.Thread | None = None

    def mutate_state() -> None:
        started.set()
        update_state(quest_dir, plan_iteration=2)
        mutation_complete.set()

    def verify(root: str | Path, iteration: int) -> None:
        nonlocal worker
        worker = threading.Thread(target=mutate_state)
        worker.start()
        assert started.wait(1)
        assert not mutation_complete.wait(
            0.1
        ), "state mutation interleaved with cleanup verification"
        original_verify(root, iteration)

    monkeypatch.setattr(
        plan_iterations_module, "verify_plan_iteration_snapshot", verify
    )
    cleanup_current_plan_iteration(quest_dir, 1)
    assert worker is not None
    worker.join(timeout=2)
    assert mutation_complete.is_set()


def test_publish_refinement_validates_findings_before_mutating_verdict(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    verdict_next = plan_dir / "arbiter_verdict.md.next"
    verdict_next.write_bytes(b"EXACT NEW VERDICT\n")
    _write_json(plan_dir / "review_findings.json.next", [{"finding_id": "broken"}])
    arbiter_handoff = _handoff("planner", 1)
    _write_json(plan_dir / "handoff_arbiter.json", arbiter_handoff)
    canonical_before = (plan_dir / "arbiter_verdict.md").read_bytes()

    with pytest.raises(PlanIterationError, match="findings"):
        publish_refinement(quest_dir, 1)

    assert (plan_dir / "arbiter_verdict.md").read_bytes() == canonical_before
    assert verdict_next.read_bytes() == b"EXACT NEW VERDICT\n"
    assert not (plan_dir / "refinement_binding.json").exists()


def test_publish_refinement_binds_exact_verdict_and_handoff_identity(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    verdict_next = plan_dir / "arbiter_verdict.md.next"
    findings_next = plan_dir / "review_findings.json.next"
    verdict_next.write_bytes(b"EXACT ITERATE VERDICT\n")
    _write_json(findings_next, [_valid_finding()])
    _write_json(plan_dir / "handoff_arbiter.json", _handoff("planner", 1))
    handoff_bytes = (plan_dir / "handoff_arbiter.json").read_bytes()

    binding_path = publish_refinement(quest_dir, 1)
    binding = json.loads(binding_path.read_text())

    assert (plan_dir / "arbiter_verdict.md").read_bytes() == b"EXACT ITERATE VERDICT\n"
    assert findings_next.exists(), "cleanup-current owns transient deletion"
    assert binding == {
        "source_plan_iteration": 1,
        "requested_plan_iteration": 2,
        "verdict_sha256": _sha256(b"EXACT ITERATE VERDICT\n"),
        "arbiter_handoff_sha256": _sha256(handoff_bytes),
        "next": "planner",
    }


def test_publish_refinement_rejects_stale_generation_without_mutation_then_retries(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["user_replan_generation"] = 7
    state["user_replan"] = {"generation": 7, "lifecycle": "planning"}
    _write_json(state_path, state)
    exact_verdict = b"EXACT CURRENT GENERATION VERDICT\n"
    verdict_next = plan_dir / "arbiter_verdict.md.next"
    verdict_next.write_bytes(exact_verdict)
    _write_json(plan_dir / "review_findings.json.next", [_valid_finding()])
    _write_json(plan_dir / "handoff_arbiter.json", _handoff("planner", 1))
    canonical = plan_dir / "arbiter_verdict.md"
    canonical_before = canonical.read_bytes()

    with pytest.raises(PlanIterationError, match="handoff_generation_mismatch"):
        publish_refinement(quest_dir, 1)

    assert canonical.read_bytes() == canonical_before
    assert verdict_next.read_bytes() == exact_verdict
    assert not (plan_dir / "refinement_binding.json").exists()

    current_handoff = _handoff("planner", 1)
    current_handoff["user_replan_generation"] = 7
    _write_json(plan_dir / "handoff_arbiter.json", current_handoff)
    binding = publish_refinement(quest_dir, 1)

    assert canonical.read_bytes() == exact_verdict
    assert json.loads(binding.read_text(encoding="utf-8"))["verdict_sha256"] == _sha256(
        exact_verdict
    )


def test_publish_refinement_holds_state_lock_through_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    verdict_next = (plan_dir / "arbiter_verdict.md.next").resolve()
    verdict_next.write_bytes(b"LOCKED VERDICT\n")
    _write_json(plan_dir / "review_findings.json.next", [_valid_finding()])
    _write_json(plan_dir / "handoff_arbiter.json", _handoff("planner", 1))
    original_read = plan_iterations_module._read_refinement_bytes
    started = threading.Event()
    mutation_complete = threading.Event()
    worker: threading.Thread | None = None

    def mutate_state() -> None:
        started.set()
        update_state(quest_dir, plan_iteration=2)
        mutation_complete.set()

    def read_bytes(path: Path) -> bytes:
        nonlocal worker
        if path.resolve() == verdict_next and worker is None:
            worker = threading.Thread(target=mutate_state)
            worker.start()
            assert started.wait(1)
            assert not mutation_complete.wait(
                0.1
            ), "state mutation interleaved with refinement publication"
        return original_read(path)

    monkeypatch.setattr(plan_iterations_module, "_read_refinement_bytes", read_bytes)
    publish_refinement(quest_dir, 1)
    assert worker is not None
    worker.join(timeout=2)
    assert mutation_complete.is_set()


def test_publish_refinement_failure_keeps_retryable_exact_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    verdict_next = plan_dir / "arbiter_verdict.md.next"
    exact_verdict = b"EXACT RETRYABLE VERDICT\n"
    verdict_next.write_bytes(exact_verdict)
    _write_json(plan_dir / "review_findings.json.next", [_valid_finding()])
    _write_json(plan_dir / "handoff_arbiter.json", _handoff("planner", 1))
    original_replace = plan_iterations_module.os.replace

    def fail_binding_replace(source: object, target: object) -> None:
        if Path(target).name == "refinement_binding.json":
            raise OSError("injected binding publication failure")
        original_replace(source, target)

    monkeypatch.setattr(plan_iterations_module.os, "replace", fail_binding_replace)
    with pytest.raises(OSError, match="injected binding"):
        publish_refinement(quest_dir, 1)

    assert verdict_next.read_bytes() == exact_verdict
    monkeypatch.setattr(plan_iterations_module.os, "replace", original_replace)
    binding_path = publish_refinement(quest_dir, 1)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    assert (plan_dir / "arbiter_verdict.md").read_bytes() == exact_verdict
    assert binding["verdict_sha256"] == _sha256(exact_verdict)
    binding_before = binding_path.read_bytes()
    assert publish_refinement(quest_dir, 1) == binding_path
    assert binding_path.read_bytes() == binding_before


@pytest.mark.parametrize(
    "missing",
    ["arbiter_verdict.md.next", "review_findings.json.next"],
)
def test_publish_refinement_missing_scratch_uses_stable_error(
    tmp_path: Path,
    missing: str,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    (plan_dir / "arbiter_verdict.md.next").write_text("ITERATE\n", encoding="utf-8")
    _write_json(plan_dir / "review_findings.json.next", [_valid_finding()])
    _write_json(plan_dir / "handoff_arbiter.json", _handoff("planner", 1))
    (plan_dir / missing).unlink()

    with pytest.raises(PlanIterationError, match="refinement_output_missing"):
        publish_refinement(quest_dir, 1)


def test_verify_refinement_rejects_wrong_iteration_and_changed_verdict(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="planner")
    snapshot_plan_iteration(quest_dir, 1)
    update_state(quest_dir, plan_iteration=2)

    binding = verify_refinement(quest_dir, 2)
    assert binding["source_plan_iteration"] == 1

    (plan_dir / "arbiter_verdict.md").write_bytes(b"RECREATED VERDICT\n")
    with pytest.raises(PlanIterationError, match="verdict_mismatch"):
        verify_refinement(quest_dir, 2)
    with pytest.raises(PlanIterationError, match="iteration_mismatch"):
        verify_refinement(quest_dir, 3)


def test_verify_refinement_missing_canonical_verdict_uses_stable_error(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="planner")
    snapshot_plan_iteration(quest_dir, 1)
    update_state(quest_dir, plan_iteration=2)
    (plan_dir / "arbiter_verdict.md").unlink()

    with pytest.raises(
        PlanIterationError,
        match="refinement_output_missing:arbiter_verdict.md",
    ):
        verify_refinement(quest_dir, 2)


def test_verify_refinement_solo_does_not_require_workflow_binding(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    _write_completed_iteration(quest_dir, mode="solo", decision="builder")
    snapshot_plan_iteration(quest_dir, 1)
    cleanup_current_plan_iteration(quest_dir, 1)
    update_state(quest_dir, plan_iteration=2)

    result = verify_refinement(quest_dir, 2)

    assert result == {
        "mode": "solo",
        "source_plan_iteration": 1,
        "requested_plan_iteration": 2,
    }


def test_plan_iteration_cli_wraps_malformed_state_as_stable_error(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    (quest_dir / "state.json").write_text("{broken", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "quest_plan_iteration.py"),
            "cleanup-current",
            "--quest-dir",
            str(quest_dir),
            "--iteration",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("plan_iteration_error: state_error[decode]")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("iteration", ["0", "-1"])
def test_plan_iteration_cli_rejects_non_positive_iterations(
    tmp_path: Path, iteration: str
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "quest_plan_iteration.py"),
            "snapshot",
            "--quest-dir",
            str(tmp_path / "quest"),
            "--iteration",
            iteration,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "positive integer" in result.stderr


def test_real_workflow_iterate_round_completes_in_pinned_order(
    tmp_path: Path,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    exact_verdict = b"ITERATE USING THESE FINDINGS\n"
    (plan_dir / "arbiter_verdict.md.next").write_bytes(exact_verdict)
    _write_json(plan_dir / "review_findings.json.next", [_valid_finding()])
    _write_json(plan_dir / "handoff_arbiter.json", _handoff("planner", 1))
    (plan_dir / "review_findings.json").unlink()
    (plan_dir / "review_backlog.json").unlink()

    # 1. Publish producer scratch, including exact verdict binding.
    publish_refinement(quest_dir, 1)
    assert (plan_dir / "review_findings.json.next").exists()
    # 2. Snapshot decision: planner without canonical findings or backlog.
    snapshot_dir = snapshot_plan_iteration(quest_dir, 1)
    assert not (snapshot_dir / "review_findings.json").exists()
    assert not (snapshot_dir / "review_backlog.json").exists()
    # 3. Cleanup owns scratch and current handoff deletion.
    cleanup_current_plan_iteration(quest_dir, 1)
    assert not (plan_dir / "review_findings.json.next").exists()
    # 4. Planner startup advances exactly once.
    update_state(quest_dir, plan_iteration=2)
    # 5. Preparation verifies immediate predecessor before truncation.
    prepare_artifact_files(
        [plan_dir / "plan.md", plan_dir / "handoff.json"],
        quest_dir=quest_dir,
        role="planner",
    )
    # 6. Binding still proves the exact predecessor verdict.
    binding = verify_refinement(quest_dir, 2)
    assert binding["verdict_sha256"] == _sha256(exact_verdict)
    # 7. The next Planner can echo typed continuity from the verified binding.
    _write_json(
        plan_dir / "handoff.json",
        {
            **_handoff("plan_review", 2),
            "refinement_source_plan_iteration": binding["source_plan_iteration"],
            "refinement_verdict_sha256": binding["verdict_sha256"],
        },
    )
    planner_handoff = json.loads((plan_dir / "handoff.json").read_text())
    assert planner_handoff["refinement_source_plan_iteration"] == 1
    assert planner_handoff["refinement_verdict_sha256"] == _sha256(exact_verdict)


@pytest.mark.parametrize(
    ("lifecycle", "expected_reason"),
    [("planning", "human_replan"), ("presentation_approved", "completed")],
)
def test_snapshot_reason_reflects_only_an_active_human_replan(
    tmp_path: Path,
    lifecycle: str,
    expected_reason: str,
) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["user_replan_generation"] = 1
    state["user_replan"] = {"generation": 1, "lifecycle": lifecycle}
    _write_json(state_path, state)
    for handoff_path in plan_dir.glob("handoff*.json"):
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff["user_replan_generation"] = 1
        _write_json(handoff_path, handoff)

    snapshot = snapshot_plan_iteration(quest_dir, 1)
    manifest = json.loads((snapshot / "snapshot.json").read_text(encoding="utf-8"))

    assert manifest["reason"] == expected_reason


def test_verify_existing_snapshot_api_uses_archive_only(tmp_path: Path) -> None:
    quest_dir = tmp_path / "quest"
    plan_dir = _write_completed_iteration(quest_dir, decision="builder")
    snapshot_plan_iteration(quest_dir, 1)
    (plan_dir / "plan.md").unlink()

    verify_plan_iteration_snapshot(quest_dir, 1)
