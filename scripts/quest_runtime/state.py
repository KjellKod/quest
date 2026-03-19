"""Helpers for updating quest state.json consistently."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_state(quest_dir: str | Path) -> dict[str, Any]:
    state_path = Path(quest_dir) / "state.json"
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(quest_dir: str | Path, state: dict[str, Any]) -> Path:
    state_path = Path(quest_dir) / "state.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state_path


def update_state(quest_dir: str | Path, **updates: Any) -> dict[str, Any]:
    state = load_state(quest_dir)
    for key, value in updates.items():
        if value is not None:
            state[key] = value
    state["updated_at"] = utc_now_iso()
    write_state(quest_dir, state)
    return state
