from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_quest_dashboard.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_script_generates_dashboard_html_from_fixture_repo(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "active-quest" / "state.json",
        {
            "quest_id": "active_quest_2026-02-10__1111",
            "slug": "active-quest",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "2026-02-10T18:00:00Z",
        },
    )

    _write(
        tmp_path / ".quest" / "active-quest" / "quest_brief.md",
        """# Quest Brief: Fixture Active Quest

## Original Prompt

Create an executive dashboard from quest records.
""",
    )

    _write(
        tmp_path / "docs" / "quest-journal" / "fixture-complete_2026-02-08.md",
        """# Quest Journal: Fixture Complete Quest

**Quest ID:** fixture_complete_2026-02-08__0912
**Completed:** 2026-02-08
**Status:** Completed

## Summary

Generated static dashboard output and validated deployment compatibility.
""",
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()

    html = output_path.read_text(encoding="utf-8")
    assert "<html" in html
    assert "Quest Dashboard" in html
    assert "Fixture Active Quest" in html
    assert "Fixture Complete Quest" in html
    assert "Open Journal" in html
    assert "Dashboard built:" in result.stdout
