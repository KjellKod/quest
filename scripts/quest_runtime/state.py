"""Helpers for reading and atomically updating Quest state.json."""

from __future__ import annotations

import fcntl
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
