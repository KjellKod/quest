"""Tests for scripts/quest_state.py parked-bg-session persistence flags.

The needs_human relay requires a supported state-helper path for
`parked_bg_session` (workflow.md forbids hand-editing state.json), so the
set/clear flags are contract, not convenience.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
        "--quest-dir", str(quest_dir),
        "--parked-bg-session", json.dumps(PARKED),
        "--clear-parked-bg-session",
    )

    assert cp.returncode == 2  # argparse usage error


def test_empty_expect_phase_fails_closed_instead_of_bypassing_lock(tmp_path):
    # A shell caller expanding an unset variable (--expect-phase "$PHASE")
    # passes "" — truthiness checks would silently skip BOTH lock checks and
    # proceed unlocked. The helper must reject it before touching state.
    quest_dir = _make_quest_dir(tmp_path)

    cp = _run(
        "--quest-dir", str(quest_dir),
        "--transition", "build",
        "--expect-phase", "",
    )

    assert cp.returncode == 1
    assert "non-empty" in cp.stderr
    state = json.loads((quest_dir / "state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "plan"  # unmodified
