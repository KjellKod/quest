"""Tests for scripts/quest_state.py parked-bg-session persistence flags.

The needs_human relay requires a supported state-helper path for
`parked_bg_session` (workflow.md forbids hand-editing state.json), so the
set/clear flags are contract, not convenience.
"""

from __future__ import annotations

import json
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


def test_load_state_classifies_invalid_utf8_as_decode(tmp_path):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_bytes(b'\xff')

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
        phase="building",
    )

    assert updated["phase"] == "building"
    assert len(replacements) == 1
    assert replacements[0][1] == state_path
    assert replacements[0][0].parent == quest_dir
    assert (quest_dir / "state.json.lock").exists()
    assert not replacements[0][0].exists()


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
        phase="building",
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
        events.append(
            "lock" if operation == state_runtime.fcntl.LOCK_EX else "unlock"
        )
        real_flock(file_descriptor, operation)

    def record_replace(source, destination):
        events.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(state_runtime.fcntl, "flock", record_flock)
    monkeypatch.setattr(state_runtime.os, "replace", record_replace)

    state_runtime.update_state(quest_dir, phase="building")

    assert events == ["lock", "replace", "unlock"]


def test_update_state_classifies_lock_failure(tmp_path, monkeypatch):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"

    def fail_lock(*args, **kwargs):
        raise OSError("platform lock detail")

    monkeypatch.setattr(state_runtime.fcntl, "flock", fail_lock)
    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.update_state(quest_dir, phase="building")

    assert str(exc_info.value) == f"state_error[lock]: {state_path.resolve()}"
    assert "platform lock detail" not in str(exc_info.value)


def test_update_state_classifies_write_failure_and_cleans_temp(
    tmp_path, monkeypatch
):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    before = state_path.read_bytes()

    def fail_replace(*args, **kwargs):
        raise OSError("platform write detail")

    monkeypatch.setattr(state_runtime.os, "replace", fail_replace)
    with pytest.raises(state_runtime.StateError) as exc_info:
        state_runtime.update_state(quest_dir, phase="building")

    assert str(exc_info.value) == f"state_error[write]: {state_path.resolve()}"
    assert state_path.read_bytes() == before
    assert not list(quest_dir.glob(".state.json.*.tmp"))


def test_atomic_replace_preserves_existing_state_file_mode(tmp_path):
    quest_dir = _make_quest_dir(tmp_path)
    state_path = quest_dir / "state.json"
    state_path.chmod(0o640)

    state_runtime.update_state(quest_dir, phase="building")

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


def test_validator_rejection_does_not_read_state(
    tmp_path, monkeypatch, capsys
):
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
        ["quest_state.py", "--quest-dir", str(quest_dir), "--phase", "building"],
    )

    def fail(*_args, **_kwargs):
        raise OSError(platform_text)

    if failure_boundary == "lock":
        monkeypatch.setattr(state_runtime.fcntl, "flock", fail)
    else:
        monkeypatch.setattr(state_runtime.os, "replace", fail)

    assert quest_state.main() == 1
    captured = capsys.readouterr()
    assert captured.err == (
        f"Error: state_error[{category}]: {state_path.resolve()}\n"
    )
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
