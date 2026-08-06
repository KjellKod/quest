"""Tests for scripts/quest_state.py parked-bg-session persistence flags.

The needs_human relay requires a supported state-helper path for
`parked_bg_session` (workflow.md forbids hand-editing state.json), so the
set/clear flags are contract, not convenience.
"""

from __future__ import annotations

import json
import hashlib
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import quest_state
from quest_runtime import state as state_runtime

REPO_ROOT = Path(__file__).resolve().parents[2]
QUEST_STATE = REPO_ROOT / "scripts" / "quest_state.py"

PARKED = {
    "agent": "planner",
    "phase": "plan",
    "iteration": 1,
    "session_id": "11111111-1111-1111-1111-111111111111",
    "short_id": "abc12345",
}


def _make_quest_dir(tmp_path: Path) -> Path:
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    (quest_dir / "state.json").write_text(
        json.dumps({"phase": "plan", "status": "in_progress"}),
        encoding="utf-8",
    )
    return quest_dir


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(QUEST_STATE), *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def test_parked_bg_session_is_persisted(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run("--quest-dir", str(quest_dir), "--parked-bg-session", json.dumps(PARKED))

    assert cp.returncode == 0, cp.stderr
    state = json.loads((quest_dir / "state.json").read_text(encoding="utf-8"))
    assert state["parked_bg_session"] == PARKED
    assert state["phase"] == "plan"  # untouched


def test_clear_parked_bg_session_removes_field(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    _run("--quest-dir", str(quest_dir), "--parked-bg-session", json.dumps(PARKED))

    cp = _run("--quest-dir", str(quest_dir), "--clear-parked-bg-session")

    assert cp.returncode == 0, cp.stderr
    state = json.loads((quest_dir / "state.json").read_text(encoding="utf-8"))
    assert "parked_bg_session" not in state


def test_parked_bg_session_rejects_missing_session_id(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run(
        "--quest-dir", str(quest_dir), "--parked-bg-session", '{"agent": "planner"}'
    )

    assert cp.returncode == 1
    assert "session_id" in cp.stderr
    state = json.loads((quest_dir / "state.json").read_text(encoding="utf-8"))
    assert "parked_bg_session" not in state


def test_parked_bg_session_rejects_empty_string(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run("--quest-dir", str(quest_dir), "--parked-bg-session", "")

    assert cp.returncode == 1
    assert "valid JSON" in cp.stderr
    state = json.loads((quest_dir / "state.json").read_text(encoding="utf-8"))
    assert "parked_bg_session" not in state


def test_parked_bg_session_rejects_invalid_json(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run("--quest-dir", str(quest_dir), "--parked-bg-session", "not-json")

    assert cp.returncode == 1
    assert "valid JSON" in cp.stderr


def test_set_and_clear_flags_are_mutually_exclusive(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run(
        "--quest-dir",
        str(quest_dir),
        "--parked-bg-session",
        json.dumps(PARKED),
        "--clear-parked-bg-session",
    )

    assert cp.returncode == 2  # argparse usage error


def test_empty_expect_phase_fails_closed_instead_of_bypassing_lock(tmp_path):
    # A shell caller expanding an unset variable (--expect-phase "$PHASE")
    # passes "" — truthiness checks would silently skip BOTH lock checks and
    # proceed unlocked. The helper must reject it before touching state.
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run(
        "--quest-dir",
        str(quest_dir),
        "--transition",
        "build",
        "--expect-phase",
        "",
    )

    assert cp.returncode == 1
    assert "non-empty" in cp.stderr
    state = json.loads((quest_dir / "state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "plan"  # unmodified


def test_transition_requires_expected_phase_and_preserves_state(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    before = state_path.read_bytes()

    cp = _run("--quest-dir", str(quest_dir), "--transition", "plan")

    assert cp.returncode == 1
    assert "--transition requires --expect-phase" in cp.stderr
    assert state_path.read_bytes() == before


@pytest.mark.parametrize("payload", ["[]", '"state"', "1", "true", "null"])
def test_load_state_rejects_non_object_top_level(tmp_path, payload):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text(payload, encoding="utf-8")

    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.load_state(quest_dir)

    assert str(exc_info.value) == f"state_error[shape]: {state_path.resolve()}"


def test_load_state_classifies_invalid_json_as_decode(tmp_path):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.load_state(quest_dir)

    assert str(exc_info.value) == f"state_error[decode]: {state_path.resolve()}"


@pytest.mark.parametrize(
    "parse_error", [ValueError("too large"), RecursionError("deep")]
)
def test_load_state_classifies_parser_limit_failures_as_decode(
    tmp_path, monkeypatch, parse_error
):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    def fail_parse(_serialized):
        raise parse_error

    monkeypatch.setattr(state_runtime.json, "loads", fail_parse)
    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.load_state(quest_dir)

    assert str(exc_info.value) == f"state_error[decode]: {state_path.resolve()}"
    assert str(parse_error) not in str(exc_info.value)


def test_load_state_classifies_invalid_utf8_as_decode(tmp_path):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_bytes(b"\xff")

    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.load_state(quest_dir)

    assert str(exc_info.value) == f"state_error[decode]: {state_path.resolve()}"


def test_load_state_classifies_read_io_without_platform_text(tmp_path, monkeypatch):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text("{}", encoding="utf-8")

    def fail_read(*args, **kwargs):
        raise OSError("platform-specific-secret")

    monkeypatch.setattr(state_runtime.Path, "read_text", fail_read)
    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.load_state(quest_dir)

    assert str(exc_info.value) == f"state_error[read]: {state_path.resolve()}"
    assert "platform-specific-secret" not in str(exc_info.value)


def test_update_state_expected_phase_mismatch_preserves_exact_bytes(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    before = state_path.read_bytes()

    with pytest.raises(state_runtime.PhaseMismatchError) as exc_info:
        state_runtime.update_state(
            quest_dir,
            expected_phase="review",
            phase="building",
        )

    assert exc_info.value.expected == "review"
    assert exc_info.value.actual == "plan"
    assert state_path.read_bytes() == before
    assert (quest_dir / "state.json.lock").exists()


def test_update_state_atomically_replaces_and_keeps_lock_file(tmp_path, monkeypatch):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    real_replace = state_runtime.os.replace
    replacements = []

    def record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(state_runtime.os, "replace", record_replace)
    updated = state_runtime.update_state(
        quest_dir,
        expected_phase="plan",
        status="building",
    )

    assert updated["status"] == "building"
    assert len(replacements) == 1
    assert replacements[0][1] == state_path
    assert replacements[0][0].parent == quest_dir
    assert (quest_dir / "state.json.lock").exists()
    assert not replacements[0][0].exists()


@pytest.mark.parametrize(
    "phase", ["plan", "plan_reviewed", "presenting", "presentation_complete"]
)
def test_record_user_replan_feedback_owns_current_request(tmp_path, monkeypatch, phase):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "phase": phase,
                "status": "complete",
                "plan_iteration": 4,
                "last_verdict": "approve",
            }
        ),
        encoding="utf-8",
    )
    feedback_path = tmp_path / "prepared-feedback.md"
    feedback_path.write_text(
        "Please revise the cache invalidation plan.\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )

    state = state_runtime.record_user_replan_feedback(
        quest_dir,
        source="sharpen",
        feedback_file=feedback_path,
        expected_phase=phase,
    )

    request = state["user_replan"]
    assert request["generation"] == 1
    assert request["source_plan_iteration"] == 4
    assert request["requested_plan_iteration"] == 5
    assert request["source_phase"] == phase
    assert request["lifecycle"] == "recorded"
    assert (
        request["feedback_sha256"]
        == hashlib.sha256(feedback_path.read_bytes()).hexdigest()
    )
    assert state["last_verdict"] is None
    assert state["approval_invalidated"] is True
    canonical = quest_dir / "phase_01_plan" / "user_feedback.md"
    assert canonical.read_text(encoding="utf-8") == feedback_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("source_phase", "forward_phase"),
    [
        ("plan", "plan_reviewed"),
        ("plan_reviewed", "presenting"),
        ("presenting", "presentation_complete"),
        ("presentation_complete", "building"),
    ],
)
def test_recorded_replan_blocks_forward_phase_drift_and_remains_consumable(
    tmp_path,
    monkeypatch,
    source_phase,
    forward_phase,
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "phase": source_phase,
                "status": "complete",
                "plan_iteration": 2,
                "last_verdict": "approve",
            }
        ),
        encoding="utf-8",
    )
    feedback = tmp_path / "feedback.md"
    feedback.write_text("Revise the plan before advancing.\n", encoding="utf-8")
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )
    state_runtime.record_user_replan_feedback(
        quest_dir,
        source="resume_instruction",
        feedback_file=feedback,
        expected_phase=source_phase,
    )
    before = state_path.read_bytes()

    with pytest.raises(state_runtime.ReplanError, match="pending_replan_unconsumed"):
        state_runtime.transition_state(
            quest_dir,
            target_phase=forward_phase,
            expected_phase=source_phase,
            status="in_progress",
        )

    assert state_path.read_bytes() == before
    replanning = state_runtime.transition_state(
        quest_dir,
        target_phase="plan",
        expected_phase=source_phase,
        status="in_progress",
    )
    assert replanning["phase"] == "plan"
    assert replanning["user_replan"]["source_phase"] == source_phase
    assert replanning["user_replan"]["lifecycle"] == "planning"


def test_record_feedback_verifies_a_real_legacy_snapshot_before_replacement(
    tmp_path,
):
    from quest_runtime.plan_iterations import snapshot_plan_iteration

    quest_dir = tmp_path / "quest"
    plan_dir = quest_dir / "phase_01_plan"
    plan_dir.mkdir(parents=True)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "phase": "presenting",
                "status": "in_progress",
                "quest_mode": "solo",
                "plan_iteration": 1,
                "last_verdict": "approve",
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "plan.md").write_text("# Legacy plan\n", encoding="utf-8")
    (plan_dir / "review_plan-reviewer-a.md").write_text("Approved\n", encoding="utf-8")
    for name, next_role in (
        ("handoff.json", "plan_review"),
        ("handoff_plan-reviewer-a.json", "builder"),
    ):
        (plan_dir / name).write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": ["plan.md"],
                    "next": next_role,
                    "summary": "legacy handoff",
                }
            ),
            encoding="utf-8",
        )
    snapshot_plan_iteration(quest_dir, 1)
    prepared = tmp_path / "prepared.md"
    prepared.write_text("Revise the plan.\n", encoding="utf-8")

    state_runtime.record_user_replan_feedback(
        quest_dir,
        source="walkthrough",
        feedback_file=prepared,
        expected_phase="presenting",
    )

    assert (plan_dir / "user_feedback.md").read_bytes() == prepared.read_bytes()


def test_same_phase_feedback_supersession_increments_generation_and_keeps_invalidated(
    tmp_path, monkeypatch
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "phase": "presenting",
                "status": "complete",
                "plan_iteration": 2,
                "last_verdict": "approve",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("First request\n", encoding="utf-8")
    second.write_text("Second request\n", encoding="utf-8")

    state_runtime.record_user_replan_feedback(
        quest_dir,
        source="walkthrough",
        feedback_file=first,
        expected_phase="presenting",
    )
    result = state_runtime.record_user_replan_feedback(
        quest_dir,
        source="sharpen",
        feedback_file=second,
        expected_phase="presenting",
    )

    assert result["user_replan"]["generation"] == 2
    assert result["user_replan_generation"] == 2
    assert result["approval_invalidated"] is True
    assert result["last_verdict"] is None
    assert (quest_dir / "phase_01_plan" / "user_feedback.md").read_bytes() == (
        second.read_bytes()
    )


def test_cross_phase_feedback_supersession_rejects_without_replacing_feedback(
    tmp_path, monkeypatch
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps({"phase": "presenting", "status": "complete", "plan_iteration": 2}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("First request\n", encoding="utf-8")
    second.write_text("Second request\n", encoding="utf-8")
    state_runtime.record_user_replan_feedback(
        quest_dir,
        source="walkthrough",
        feedback_file=first,
        expected_phase="presenting",
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["phase"] = "presentation_complete"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before_state = state_path.read_bytes()
    canonical = quest_dir / "phase_01_plan" / "user_feedback.md"
    before_feedback = canonical.read_bytes()

    with pytest.raises(state_runtime.ReplanError, match="supersession_cross_phase"):
        state_runtime.record_user_replan_feedback(
            quest_dir,
            source="resume_instruction",
            feedback_file=second,
            expected_phase="presentation_complete",
        )

    assert state_path.read_bytes() == before_state
    assert canonical.read_bytes() == before_feedback


def test_pending_replan_rejects_approval_revival_or_cancellation(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "phase": "plan",
                "status": "replan_requested",
                "approval_invalidated": True,
                "last_verdict": None,
                "user_replan": {"generation": 1, "lifecycle": "recorded"},
            }
        ),
        encoding="utf-8",
    )
    before = state_path.read_bytes()

    with pytest.raises(state_runtime.ReplanError, match="approval_revival_forbidden"):
        state_runtime.update_state(
            quest_dir,
            approval_invalidated=False,
            last_verdict="approve",
        )
    assert state_path.read_bytes() == before

    with pytest.raises(
        state_runtime.ReplanError, match="replan_cancellation_forbidden"
    ):
        state_runtime.update_state(quest_dir, user_replan={})
    assert state_path.read_bytes() == before


@pytest.mark.parametrize("boundary", ["canonical", "history", "final_state"])
def test_partial_feedback_recording_durably_blocks_build(
    tmp_path,
    monkeypatch,
    boundary,
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "phase": "presentation_complete",
                "status": "complete",
                "plan_iteration": 2,
                "last_verdict": "approve",
                "approval_invalidated": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )
    feedback = tmp_path / "feedback.md"
    feedback.write_text("Change the plan before Build.\n", encoding="utf-8")

    if boundary == "canonical":

        def fail_canonical(*_args, **_kwargs):
            raise state_runtime.StateError("write", state_path)

        monkeypatch.setattr(state_runtime, "_atomic_write_bytes", fail_canonical)
    elif boundary == "history":

        def fail_history(*_args, **_kwargs):
            raise state_runtime.StateError("write", state_path)

        monkeypatch.setattr(state_runtime, "_append_replan_history", fail_history)
    else:
        real_write_state = state_runtime._atomic_write_state
        calls = 0

        def fail_final(path, state):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise state_runtime.StateError("write", path)
            real_write_state(path, state)

        monkeypatch.setattr(state_runtime, "_atomic_write_state", fail_final)

    with pytest.raises(state_runtime.StateError):
        state_runtime.record_user_replan_feedback(
            quest_dir,
            source="build_gate",
            feedback_file=feedback,
            expected_phase="presentation_complete",
        )

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["approval_invalidated"] is True
    assert persisted["last_verdict"] is None
    assert persisted["user_replan"]["lifecycle"] == "recording"
    before_transition = state_path.read_bytes()
    with pytest.raises(state_runtime.ReplanError, match="pending_replan_unconsumed"):
        state_runtime.transition_state(
            quest_dir,
            target_phase="building",
            expected_phase="presentation_complete",
            status="in_progress",
        )
    assert state_path.read_bytes() == before_transition
    validation = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts" / "quest_validate-quest-state.sh"),
            str(quest_dir),
            "building",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert validation.returncode != 0


@pytest.mark.parametrize("feedback", [b"", b"  \n\t"])
def test_record_user_replan_feedback_rejects_empty_without_state_change(
    tmp_path, monkeypatch, feedback
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    before = state_path.read_bytes()
    feedback_path = tmp_path / "prepared-feedback.md"
    feedback_path.write_bytes(feedback)
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )

    with pytest.raises(state_runtime.ReplanError, match="feedback_empty"):
        state_runtime.record_user_replan_feedback(
            quest_dir,
            source="walkthrough",
            feedback_file=feedback_path,
            expected_phase="plan",
        )

    assert state_path.read_bytes() == before
    assert not (quest_dir / "phase_01_plan" / "user_feedback.md").exists()


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("plan_iteration", "iteration_invalid"),
        ("user_replan_generation", "generation_invalid"),
    ],
)
def test_record_user_replan_feedback_rejects_boolean_identity_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    error: str,
) -> None:
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update({"plan_iteration": 1, "user_replan_generation": 0})
    state[field] = True
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()
    feedback = tmp_path / "feedback.md"
    feedback.write_text("Revise plan.\n", encoding="utf-8")
    monkeypatch.setattr(
        state_runtime, "verify_plan_iteration_snapshot", lambda *_: None
    )

    with pytest.raises(state_runtime.ReplanError, match=error):
        state_runtime.record_user_replan_feedback(
            quest_dir,
            source="walkthrough",
            feedback_file=feedback,
            expected_phase="plan",
        )

    assert state_path.read_bytes() == before


def test_human_replan_transition_rejects_stale_feedback_without_state_change(
    tmp_path,
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    feedback_path = quest_dir / "phase_01_plan" / "user_feedback.md"
    feedback_path.parent.mkdir(parents=True)
    feedback_path.write_text("old request\n", encoding="utf-8")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "plan_iteration": 2,
            "user_replan_generation": 1,
            "approval_invalidated": True,
            "user_replan": {
                "generation": 1,
                "source_phase": "plan",
                "source_plan_iteration": 2,
                "requested_plan_iteration": 3,
                "source": "walkthrough",
                "feedback_sha256": hashlib.sha256(b"current request\n").hexdigest(),
                "lifecycle": "recorded",
            },
        }
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()

    with pytest.raises(state_runtime.ReplanError, match="feedback_stale"):
        state_runtime.transition_state(
            quest_dir,
            target_phase="plan",
            expected_phase="plan",
            status="in_progress",
        )

    assert state_path.read_bytes() == before


@pytest.mark.parametrize(
    "case",
    [
        "null_generation",
        "bool_generation",
        "missing_source",
        "invalid_source",
        "approval_revived",
        "bool_iteration",
        "missing_request",
        "erased_feedback",
        "empty_feedback",
        "replayed_request",
        "stale_digest",
    ],
)
def test_malformed_pending_replan_matrix_preserves_state_bytes(
    tmp_path: Path,
    case: str,
) -> None:
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    feedback_path = quest_dir / "phase_01_plan" / "user_feedback.md"
    feedback_path.parent.mkdir(parents=True)
    feedback = b"Current helper-owned request\n"
    feedback_path.write_bytes(feedback)
    state = {
        "phase": "presenting",
        "status": "replan_requested",
        "plan_iteration": 2,
        "user_replan_generation": 1,
        "approval_invalidated": True,
        "user_replan": {
            "generation": 1,
            "source": "walkthrough",
            "source_phase": "presenting",
            "source_plan_iteration": 2,
            "requested_plan_iteration": 3,
            "feedback_sha256": hashlib.sha256(feedback).hexdigest(),
            "lifecycle": "recorded",
        },
    }

    if case == "null_generation":
        state["user_replan_generation"] = None
        state["user_replan"]["generation"] = None
    elif case == "bool_generation":
        state["user_replan_generation"] = True
        state["user_replan"]["generation"] = True
    elif case == "missing_source":
        state["user_replan"].pop("source")
    elif case == "invalid_source":
        state["user_replan"]["source"] = "manual"
    elif case == "approval_revived":
        state["approval_invalidated"] = False
    elif case == "bool_iteration":
        state["plan_iteration"] = True
        state["user_replan"]["source_plan_iteration"] = True
        state["user_replan"]["requested_plan_iteration"] = 2
    elif case == "missing_request":
        state.pop("user_replan")
    elif case == "erased_feedback":
        feedback_path.unlink()
    elif case == "empty_feedback":
        feedback_path.write_text("  \n", encoding="utf-8")
    elif case == "replayed_request":
        state["user_replan"]["lifecycle"] = "planning"
    elif case == "stale_digest":
        state["user_replan"]["feedback_sha256"] = "0" * 64

    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()

    with pytest.raises(state_runtime.ReplanError):
        state_runtime.transition_state(
            quest_dir,
            target_phase="plan",
            expected_phase="presenting",
            status="in_progress",
        )

    assert state_path.read_bytes() == before


@pytest.mark.parametrize("target_phase", ["plan", "building"])
def test_raw_phase_change_cannot_bypass_transition_validation(tmp_path, target_phase):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["phase"] = "presenting"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()

    with pytest.raises(state_runtime.ReplanError, match="unvalidated_phase_change"):
        state_runtime.update_state(quest_dir, phase=target_phase)

    assert state_path.read_bytes() == before


def test_replan_lifecycle_advances_only_through_review_and_presentation(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "phase": "plan",
            "plan_iteration": 3,
            "approval_invalidated": True,
            "user_replan_generation": 2,
            "user_replan": {
                "generation": 2,
                "source_phase": "presenting",
                "source_plan_iteration": 2,
                "requested_plan_iteration": 3,
                "source": "sharpen",
                "feedback_sha256": "digest",
                "lifecycle": "planning",
            },
        }
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")

    reviewed = state_runtime.transition_state(
        quest_dir,
        target_phase="plan_reviewed",
        expected_phase="plan",
        status="complete",
    )
    assert reviewed["user_replan"]["lifecycle"] == "reviewed"
    state_runtime.transition_state(
        quest_dir,
        target_phase="presenting",
        expected_phase="plan_reviewed",
        status="in_progress",
    )
    approved = state_runtime.transition_state(
        quest_dir,
        target_phase="presentation_complete",
        expected_phase="presenting",
        status="complete",
    )
    assert approved["user_replan"]["lifecycle"] == "presentation_approved"
    assert approved["approval_invalidated"] is False


def test_transition_rejects_clear_parked_session_combination(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["parked_bg_session"] = PARKED
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()

    result = _run(
        "--quest-dir",
        str(quest_dir),
        "--transition",
        "plan",
        "--expect-phase",
        "plan",
        "--clear-parked-bg-session",
    )

    assert result.returncode == 1
    assert "cannot be combined" in result.stderr
    assert state_path.read_bytes() == before


@pytest.mark.parametrize(
    "extra_args",
    [
        ["--status", "ignored"],
        ["--clear-parked-bg-session"],
    ],
)
def test_record_feedback_rejects_unrelated_mutation_flags(
    tmp_path, monkeypatch, capsys, extra_args
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    feedback = tmp_path / "feedback.md"
    feedback.write_text("Revise the plan.\n", encoding="utf-8")
    before = state_path.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_state.py",
            "--quest-dir",
            str(quest_dir),
            "--record-user-replan-feedback",
            "--source",
            "walkthrough",
            "--feedback-file",
            str(feedback),
            "--expect-phase",
            "plan",
            *extra_args,
        ],
    )
    monkeypatch.setattr(
        quest_state,
        "record_user_replan_feedback",
        lambda *_args, **_kwargs: pytest.fail("recording must not start"),
    )

    assert quest_state.main() == 1
    assert "cannot be combined" in capsys.readouterr().err
    assert state_path.read_bytes() == before


def test_update_state_clears_parked_session_in_single_replacement(
    tmp_path, monkeypatch
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["parked_bg_session"] = PARKED
    state_path.write_text(json.dumps(state), encoding="utf-8")
    real_replace = state_runtime.os.replace
    replacements = []

    def record_replace(source, destination):
        replacements.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(state_runtime.os, "replace", record_replace)
    updated = state_runtime.update_state(
        quest_dir,
        expected_phase="plan",
        clear_parked_bg_session=True,
        status="building",
    )

    assert "parked_bg_session" not in updated
    assert len(replacements) == 1
    assert "expected_phase" not in updated
    assert "clear_parked_bg_session" not in updated


def test_clear_absent_parked_session_still_updates_once(tmp_path, monkeypatch):
    quest_dir = _make_quest_dir(tmp_path)
    real_replace = state_runtime.os.replace
    replacements = []

    def record_replace(source, destination):
        replacements.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(state_runtime.os, "replace", record_replace)
    updated = state_runtime.update_state(quest_dir, clear_parked_bg_session=True)

    assert "parked_bg_session" not in updated
    assert "updated_at" in updated
    assert len(replacements) == 1


def test_update_state_holds_lock_through_atomic_replace(tmp_path, monkeypatch):
    quest_dir = _make_quest_dir(tmp_path)
    events = []
    real_flock = state_runtime.fcntl.flock
    real_replace = state_runtime.os.replace

    def record_flock(file_descriptor, operation):
        events.append("lock" if operation == state_runtime.fcntl.LOCK_EX else "unlock")
        real_flock(file_descriptor, operation)

    def record_replace(source, destination):
        events.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(state_runtime.fcntl, "flock", record_flock)
    monkeypatch.setattr(state_runtime.os, "replace", record_replace)

    state_runtime.update_state(quest_dir, status="building")

    assert events == ["lock", "replace", "unlock"]


def test_update_state_does_not_report_failure_when_explicit_unlock_fails(
    tmp_path, monkeypatch
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    real_flock = state_runtime.fcntl.flock

    def fail_explicit_unlock(file_descriptor, operation):
        if operation == state_runtime.fcntl.LOCK_UN:
            raise OSError("platform unlock detail")
        real_flock(file_descriptor, operation)

    monkeypatch.setattr(state_runtime.fcntl, "flock", fail_explicit_unlock)

    updated = state_runtime.update_state(quest_dir, status="building")

    assert updated["status"] == "building"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["phase"] == "plan"
    assert persisted["status"] == "building"


def test_update_state_classifies_lock_failure(tmp_path, monkeypatch):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"

    def fail_lock(*args, **kwargs):
        raise OSError("platform lock detail")

    monkeypatch.setattr(state_runtime.fcntl, "flock", fail_lock)
    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.update_state(quest_dir, status="building")

    assert str(exc_info.value) == f"state_error[lock]: {state_path.resolve()}"
    assert "platform lock detail" not in str(exc_info.value)


def test_update_state_classifies_write_failure_and_cleans_temp(tmp_path, monkeypatch):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    before = state_path.read_bytes()

    def fail_replace(*args, **kwargs):
        raise OSError("platform write detail")

    monkeypatch.setattr(state_runtime.os, "replace", fail_replace)
    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.update_state(quest_dir, status="building")

    assert str(exc_info.value) == f"state_error[write]: {state_path.resolve()}"
    assert state_path.read_bytes() == before
    assert not list(quest_dir.glob(".state.json.*.tmp"))


def test_atomic_replace_preserves_existing_state_file_mode(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.chmod(0o640)

    state_runtime.update_state(quest_dir, status="building")

    assert stat.S_IMODE(state_path.stat().st_mode) == 0o640


def test_cli_invalid_state_has_readable_error_without_traceback(tmp_path):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text("[]", encoding="utf-8")

    cp = _run("--quest-dir", str(quest_dir), "--phase", "building")

    assert cp.returncode == 1
    assert f"state_error[shape]: {state_path.resolve()}" in cp.stderr
    assert "Traceback" not in cp.stderr


def test_record_feedback_maps_missing_snapshot_without_traceback(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["plan_iteration"] = 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("Revise the plan.\n", encoding="utf-8")
    before = state_path.read_bytes()

    cp = _run(
        "--quest-dir",
        str(quest_dir),
        "--record-user-replan-feedback",
        "--source",
        "walkthrough",
        "--feedback-file",
        str(feedback),
        "--expect-phase",
        "plan",
    )

    assert cp.returncode == 1
    assert "replan_error[snapshot_invalid]" in cp.stderr
    assert "Traceback" not in cp.stderr
    assert state_path.read_bytes() == before


def test_validator_rejection_does_not_read_state(tmp_path, monkeypatch, capsys):
    quest_dir = _make_quest_dir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_state.py",
            "--quest-dir",
            str(quest_dir),
            "--transition",
            "building",
            "--expect-phase",
            "plan",
        ],
    )
    monkeypatch.setattr(
        quest_state,
        "run_validator",
        lambda *_args: (1, "validator detail\n"),
    )

    def reject_state_read(*_args, **_kwargs):
        raise AssertionError("validator rejection must not load state")

    monkeypatch.setattr(quest_state, "load_state", reject_state_read, raising=False)

    assert quest_state.main() == 1
    captured = capsys.readouterr()
    assert captured.err == (
        "Transition to building rejected by validator.\nvalidator detail\n\n"
    )
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("failure_boundary", "category", "platform_text"),
    [
        ("lock", "lock", "platform lock detail"),
        ("write", "write", "platform write detail"),
    ],
)
def test_cli_translates_state_mutation_failures(
    tmp_path,
    monkeypatch,
    capsys,
    failure_boundary,
    category,
    platform_text,
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["quest_state.py", "--quest-dir", str(quest_dir), "--status", "building"],
    )

    def fail(*_args, **_kwargs):
        raise OSError(platform_text)

    if failure_boundary == "lock":
        monkeypatch.setattr(state_runtime.fcntl, "flock", fail)
    else:
        monkeypatch.setattr(state_runtime.os, "replace", fail)

    assert quest_state.main() == 1
    captured = capsys.readouterr()
    assert captured.err == (f"Error: state_error[{category}]: {state_path.resolve()}\n")
    assert platform_text not in captured.err
    assert "Traceback" not in captured.err


def test_cli_expected_phase_mismatch_is_distinct_and_does_not_mutate(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    (quest_dir / "orchestration.json").write_text(
        json.dumps(
            {
                "version": 1,
                "source": "default",
                "models": {
                    role: "test-model"
                    for role in (
                        "planner",
                        "plan-reviewer-a",
                        "plan-reviewer-b",
                        "arbiter",
                        "builder",
                        "code-reviewer-a",
                        "code-reviewer-b",
                        "review-arbiter",
                        "fixer",
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    plan_dir = quest_dir / "phase_01_plan"
    plan_dir.mkdir()
    (plan_dir / "arbiter_verdict.md").write_text("approved", encoding="utf-8")
    state_path = quest_dir / "state.json"
    before = state_path.read_bytes()

    cp = _run(
        "--quest-dir",
        str(quest_dir),
        "--transition",
        "plan",
        "--expect-phase",
        "review",
    )

    assert cp.returncode == 1
    assert "Expected phase 'review' but state.json has 'plan'" in cp.stderr
    assert "state_error" not in cp.stderr
    assert state_path.read_bytes() == before
