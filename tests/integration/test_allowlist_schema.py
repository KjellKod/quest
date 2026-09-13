"""Exercise the same AJV boundary used by quest_validate-quest-config.sh."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

AJV = shutil.which("ajv")
pytestmark = pytest.mark.skipif(AJV is None, reason="AJV CLI is not installed")
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("mode", "expected_valid"),
    [
        ("cached", True),
        ("api-key", True),
        ("api", False),
        ("apiKey", False),
        (1, False),
    ],
)
def test_allowlist_schema_validates_codex_auth_mode(
    tmp_path: Path, mode: str | int, expected_valid: bool
) -> None:
    allowlist = json.loads((REPO_ROOT / ".ai/allowlist.json").read_text())
    allowlist["codex_auth_mode"] = mode
    candidate = tmp_path / "allowlist.json"
    candidate.write_text(json.dumps(allowlist))

    result = subprocess.run(
        [
            str(AJV),
            "validate",
            "-s",
            str(REPO_ROOT / ".ai/schemas/allowlist.schema.json"),
            "-d",
            str(candidate),
            "--spec=draft2020",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert (result.returncode == 0) == expected_valid, result.stdout + result.stderr
    if not expected_valid:
        assert "codex_auth_mode" in result.stderr
