"""Helpers for reading and atomically updating Quest state.json."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateError(Exception):
    """Stable state-boundary failure without platform-specific details."""

    def __init__(self, category: str, state_path: Path) -> None:
        self.category = category
        self.state_path = state_path.resolve()
        super().__init__(f"state_error[{category}]: {self.state_path}")


class PhaseMismatchError(Exception):
    """The locked state phase did not match the caller's expectation."""

    def __init__(self, expected: str, actual: object) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected phase '{expected}' but state.json has '{actual}'")


class ReplanError(Exception):
    """A stable human-replan contract failure."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(f"replan_error[{category}]")


REPLAN_PHASES = frozenset(
    {"plan", "plan_reviewed", "presenting", "presentation_complete"}
)
REPLAN_SOURCES = frozenset(
    {"walkthrough", "sharpen", "build_gate", "resume_instruction"}
)


def verify_plan_iteration_snapshot(quest_dir: str | Path, iteration: int) -> None:
    """Late import avoids a state and lifecycle module import cycle."""

    from .plan_iterations import verify_plan_iteration_snapshot as verify

    verify(quest_dir, iteration)


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _state_path(quest_dir: str | Path) -> Path:
    return (Path(quest_dir) / "state.json").resolve()


def load_state(quest_dir: str | Path) -> dict[str, Any]:
    """Load a Quest state object or raise a stable categorized error."""
    state_path = _state_path(quest_dir)
    try:
        serialized = state_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise StateError("decode", state_path) from exc
    except OSError as exc:
        raise StateError("read", state_path) from exc

    try:
        state = json.loads(serialized)
    except (ValueError, RecursionError) as exc:
        raise StateError("decode", state_path) from exc
    if not isinstance(state, dict):
        raise StateError("shape", state_path)
    # JSON state is an external deserialization boundary, so values are dynamic.
    return state


def _atomic_write_state(state_path: Path, state: dict[str, Any]) -> None:
    temp_path: Path | None = None
    try:
        state_mode = stat.S_IMODE(state_path.stat().st_mode)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=state_path.parent,
            prefix=f".{state_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(state, temp_file, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_path.chmod(state_mode)
        os.replace(temp_path, state_path)
        temp_path = None
    except (OSError, TypeError, ValueError) as exc:
        raise StateError("write", state_path) from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise StateError("write", _state_path(path.parents[1])) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _lock_file(state_path: Path):
    lock_path = state_path.with_name(f"{state_path.name}.lock")
    try:
        return lock_path.open("a", encoding="utf-8")
    except OSError as exc:
        raise StateError("lock", state_path) from exc


def _feedback_bytes(quest_dir: Path) -> bytes:
    feedback_path = quest_dir / "phase_01_plan" / "user_feedback.md"
    try:
        return feedback_path.read_bytes()
    except OSError as exc:
        raise ReplanError("feedback_missing") from exc


def _append_replan_history(root: Path, request: dict[str, Any]) -> None:
    history_path = root / "logs" / "user_replan_history.jsonl"
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as history:
            history.write(json.dumps(request, sort_keys=True) + "\n")
            history.flush()
            os.fsync(history.fileno())
    except OSError as exc:
        raise StateError("write", _state_path(root)) from exc


def _validate_pending_replan(
    quest_dir: Path, state: dict[str, Any], expected_phase: str
) -> dict[str, Any]:
    request = state.get("user_replan")
    if not isinstance(request, dict):
        raise ReplanError("feedback_missing")
    if request.get("lifecycle") != "recorded":
        raise ReplanError("request_replayed")
    iteration = state.get("plan_iteration")
    generation = state.get("user_replan_generation")
    request_generation = request.get("generation")
    source_iteration = request.get("source_plan_iteration")
    requested_iteration = request.get("requested_plan_iteration")

    def is_positive_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    if (
        not is_positive_int(iteration)
        or not is_positive_int(generation)
        or not is_positive_int(request_generation)
        or not is_positive_int(source_iteration)
        or not is_positive_int(requested_iteration)
        or request.get("source") not in REPLAN_SOURCES
        or state.get("approval_invalidated") is not True
    ):
        raise ReplanError("request_malformed")
    if (
        request_generation != generation
        or request.get("source_phase") != expected_phase
        or source_iteration != iteration
        or requested_iteration != iteration + 1
    ):
        raise ReplanError("request_stale")
    feedback = _feedback_bytes(quest_dir)
    if not feedback.strip():
        raise ReplanError("feedback_empty")
    if request.get("feedback_sha256") != hashlib.sha256(feedback).hexdigest():
        raise ReplanError("feedback_stale")
    return request


def validate_pending_replan(
    quest_dir: str | Path, expected_phase: str
) -> dict[str, Any]:
    """Read-only preflight for the shell validator.

    The locked transition repeats this check and remains authoritative.
    """

    root = Path(quest_dir).resolve()
    return _validate_pending_replan(root, load_state(root), expected_phase)


def record_user_replan_feedback(
    quest_dir: str | Path,
    *,
    source: str,
    feedback_file: str | Path,
    expected_phase: str,
) -> dict[str, Any]:
    """Record current feedback and invalidate approval under the state lock."""

    root = Path(quest_dir).resolve()
    state_path = _state_path(root)
    if source not in REPLAN_SOURCES:
        raise ReplanError("source_invalid")
    try:
        feedback = Path(feedback_file).read_bytes()
    except OSError as exc:
        raise ReplanError("feedback_missing") from exc
    if not feedback.strip():
        raise ReplanError("feedback_empty")

    with _lock_file(state_path) as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = load_state(root)
        phase = state.get("phase")
        if phase != expected_phase:
            raise PhaseMismatchError(expected_phase, phase)
        if phase not in REPLAN_PHASES:
            raise ReplanError("phase_forbidden")
        iteration = state.get("plan_iteration")
        if (
            not isinstance(iteration, int)
            or isinstance(iteration, bool)
            or iteration < 1
        ):
            raise ReplanError("iteration_invalid")
        from .plan_iterations import PlanIterationError

        try:
            verify_plan_iteration_snapshot(root, iteration)
        except PlanIterationError as exc:
            raise ReplanError("snapshot_invalid") from exc

        previous_generation = state.get("user_replan_generation", 0)
        if (
            not isinstance(previous_generation, int)
            or isinstance(previous_generation, bool)
            or previous_generation < 0
        ):
            raise ReplanError("generation_invalid")
        existing = state.get("user_replan")
        if isinstance(existing, dict) and existing.get("lifecycle") in {
            "recording",
            "recorded",
        }:
            if (
                existing.get("source_phase") != phase
                or existing.get("source_plan_iteration") != iteration
            ):
                raise ReplanError("supersession_cross_phase")

        generation = previous_generation + 1
        digest = hashlib.sha256(feedback).hexdigest()
        request = {
            "generation": generation,
            "source": source,
            "source_phase": phase,
            "source_plan_iteration": iteration,
            "requested_plan_iteration": iteration + 1,
            "feedback_sha256": digest,
            "lifecycle": "recorded",
            "recorded_at": utc_now_iso(),
        }
        recording_request = {**request, "lifecycle": "recording"}
        state["user_replan_generation"] = generation
        state["user_replan"] = recording_request
        state["approval_invalidated"] = True
        state["last_verdict"] = None
        state["status"] = "replan_requested"
        state["updated_at"] = utc_now_iso()
        _atomic_write_state(state_path, state)

        canonical = root / "phase_01_plan" / "user_feedback.md"
        _atomic_write_bytes(canonical, feedback)
        _append_replan_history(root, request)
        state["user_replan"] = request
        state["updated_at"] = utc_now_iso()
        _atomic_write_state(state_path, state)
        return state


def transition_state(
    quest_dir: str | Path,
    *,
    target_phase: str,
    expected_phase: str | None,
    **updates: Any,
) -> dict[str, Any]:
    """Publish a validated transition and consume current human replan intent."""

    root = Path(quest_dir).resolve()
    state_path = _state_path(root)
    with _lock_file(state_path) as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = load_state(root)
        actual_phase = state.get("phase")
        if expected_phase is not None and actual_phase != expected_phase:
            raise PhaseMismatchError(expected_phase, actual_phase)
        pending_replan = state.get("user_replan")
        if (
            target_phase != "plan"
            and isinstance(pending_replan, dict)
            and pending_replan.get("lifecycle") in {"recording", "recorded"}
        ):
            raise ReplanError("pending_replan_unconsumed")
        if target_phase == "plan" and actual_phase in REPLAN_PHASES:
            has_pending = (
                isinstance(state.get("user_replan"), dict)
                and state["user_replan"].get("lifecycle") == "recorded"
            )
            if actual_phase != "plan" or has_pending:
                request = _validate_pending_replan(root, state, str(actual_phase))
                request["lifecycle"] = "planning"
                request["consumed_at"] = utc_now_iso()
                state["user_replan"] = request
        if target_phase == "presentation_complete" and isinstance(
            state.get("user_replan"), dict
        ):
            request = state["user_replan"]
            if request.get("lifecycle") == "reviewed":
                request["lifecycle"] = "presentation_approved"
                request["approved_at"] = utc_now_iso()
                state["approval_invalidated"] = False
        if target_phase == "plan_reviewed" and isinstance(
            state.get("user_replan"), dict
        ):
            request = state["user_replan"]
            if request.get("lifecycle") == "planning":
                request["lifecycle"] = "reviewed"
                request["reviewed_at"] = utc_now_iso()
        state["phase"] = target_phase
        for key, value in updates.items():
            if value is not None:
                state[key] = value
        state["updated_at"] = utc_now_iso()
        _atomic_write_state(state_path, state)
        return state


def update_state(
    quest_dir: str | Path,
    *,
    expected_phase: str | None = None,
    clear_parked_bg_session: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    """Lock, reload, optionally compare, mutate, and atomically replace state."""
    state_path = _state_path(quest_dir)
    lock_path = state_path.with_name(f"{state_path.name}.lock")
    try:
        lock_file = lock_path.open("a", encoding="utf-8")
    except OSError as exc:
        raise StateError("lock", state_path) from exc

    with lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise StateError("lock", state_path) from exc

        try:
            state = load_state(state_path.parent)
            actual_phase = state.get("phase")
            if expected_phase is not None and actual_phase != expected_phase:
                raise PhaseMismatchError(expected_phase, actual_phase)

            requested_phase = updates.get("phase")
            if requested_phase is not None and requested_phase != actual_phase:
                raise ReplanError("unvalidated_phase_change")

            active_request = state.get("user_replan")
            if isinstance(active_request, dict) and active_request.get("lifecycle") in {
                "recording",
                "recorded",
                "planning",
                "reviewed",
            }:
                if updates.get("approval_invalidated") is False:
                    raise ReplanError("approval_revival_forbidden")
                if (
                    "user_replan" in updates
                    and updates["user_replan"] != active_request
                ):
                    raise ReplanError("replan_cancellation_forbidden")

            for key, value in updates.items():
                if value is not None:
                    state[key] = value
            if clear_parked_bg_session:
                state.pop("parked_bg_session", None)
            state["updated_at"] = utc_now_iso()
            _atomic_write_state(state_path, state)
            return state
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                # Closing the descriptor releases the lock. Do not turn an
                # already-committed replacement into a false failure report.
                pass
