"""Pytest wrapper that runs the shell-based hook test.

The hook itself is a `.sh` file (it is what runs as a PreToolUse hook in
production), so its native tests are written in shell at
`tests/unit/test_branch_dir_context_hook.sh`. Without this wrapper, pytest
(and therefore CI's `test` job) never executes the shell tests — they
would only run if someone manually invoked `bash tests/unit/...`.

This module subprocess-executes the shell suite and asserts on exit code,
so any failure inside the shell tests bubbles up as a normal pytest
failure with the runner output captured for inspection.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHELL_TESTS = _REPO_ROOT / "tests" / "unit" / "test_branch_dir_context_hook.sh"


@pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="bash interpreter not available; the hook is bash-targeted",
)
def test_branch_dir_context_hook_shell_suite_passes() -> None:
    assert _SHELL_TESTS.exists(), f"missing shell test file: {_SHELL_TESTS}"

    result = subprocess.run(
        ["bash", str(_SHELL_TESTS)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.fail(
            "branch-dir-context hook shell suite failed\n"
            f"exit code: {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
