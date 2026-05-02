"""Run validation commands available in installed Quest projects."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

COMMANDS: list[tuple[str, list[str]]] = [
    ("validate quest config", ["bash", "scripts/quest_validate-quest-config.sh"]),
    ("validate manifest", ["bash", "scripts/quest_validate-manifest.sh"]),
]


def main() -> int:
    for label, command in COMMANDS:
        print(f"==> {label}: {' '.join(command)}")
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
