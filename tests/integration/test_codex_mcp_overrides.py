"""Validate runner overrides using the installed CLI parser, without inference."""

import json
import os
import shutil
import subprocess

import pytest

from quest_runtime.codex_runner import (
    Credentials,
    build_codex_command,
    disabled_self_servers,
)


@pytest.mark.parametrize("names", [("codex-cli",), ("odd.name", "codex-cli")])
def test_self_server_overrides_preserve_other_configuration(tmp_path, names):
    executable = shutil.which("codex")
    if executable is None:
        pytest.skip("Installed Codex CLI required for real override-parser validation")
    config = tmp_path / "config.toml"
    source = "".join(
        f"[mcp_servers.{json.dumps(name)}]\n" 'command="codex"\nargs=["mcp-server"]\n'
        for name in names
    ) + (
        '[mcp_servers.unrelated]\ncommand="unrelated-server"\nargs=["keep"]\n'
        "tool_timeout_sec=42\n[mcp_servers.unrelated.env]\n"
        'TOKEN="fixture-secret-must-not-enter-argv"\n'
        '[mcp_servers.already_disabled]\ncommand="other"\nenabled=false\n'
    )
    config.write_text(source)
    # Isolated config and cwd. mcp list parses configuration without launching
    # servers or inference; no account credentials are copied into this home.
    credentials = Credentials(
        "cached", "chatgpt", {"CODEX_HOME": str(tmp_path), "PATH": os.environ["PATH"]}
    )
    before = subprocess.run(
        [executable, "mcp", "list", "--json"],
        cwd=tmp_path,
        env=credentials.environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    disabled = disabled_self_servers(executable, tmp_path, credentials)
    assert set(disabled) == set(names)
    command = build_codex_command(
        executable,
        cwd=tmp_path,
        model=None,
        effort=None,
        sandbox="workspace-write",
        credentials=credentials,
        final_path=tmp_path / "unused-final",
        add_dirs=[],
        allow_non_git=True,
        disabled=disabled,
    )
    overrides = [
        value
        for flag, value in zip(command, command[1:])
        if flag == "-c" and value.startswith("mcp_servers")
    ]
    assert "fixture-secret-must-not-enter-argv" not in " ".join(command)
    parsed = subprocess.run(
        [
            executable,
            *[arg for value in overrides for arg in ("-c", value)],
            "mcp",
            "list",
            "--json",
        ],
        cwd=tmp_path,
        env=credentials.environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert parsed.returncode == 0, parsed.stderr
    expected = json.loads(before.stdout)
    for entry in expected:
        if entry["name"] in names:
            entry["enabled"] = False
    assert json.loads(parsed.stdout) == expected
    assert config.read_text() == source
