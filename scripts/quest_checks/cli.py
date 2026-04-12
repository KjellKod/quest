"""Run the standard Quest validation and test commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

COMMANDS: list[tuple[str, list[str]]] = [
    ("validate quest config", ["bash", "scripts/quest_validate-quest-config.sh"]),
    ("validate manifest", ["bash", "scripts/quest_validate-manifest.sh"]),
    ("python tests", [sys.executable, "-m", "pytest"]),
    ("quest preflight shell tests", ["bash", "tests/test-quest-preflight.sh"]),
    ("quest runtime shell tests", ["bash", "tests/test-quest-runtime.sh"]),
    (
        "handoff contract shell tests",
        ["bash", "tests/test-validate-handoff-contracts.sh"],
    ),
    ("quest state shell tests", ["bash", "tests/test-validate-quest-state.sh"]),
]


def main() -> int:
    for label, command in COMMANDS:
        print(f"==> {label}: {' '.join(command)}")
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0
