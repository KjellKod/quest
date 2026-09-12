"""Installer boundary regressions, without fetching or running live models."""

import json
import hashlib
import os
from pathlib import Path
import subprocess
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
InstalledCandidate = tuple[Path, dict[str, str], list[str]]


def test_installer_does_not_write_global_codex_permissions(tmp_path: Path) -> None:
    source = (
        (ROOT / "scripts/quest_installer.sh")
        .read_text()
        .split("# Store original args for re-exec after self-update")[0]
    )
    # Exercise the old mutation entrypoint when present, new setup otherwise.
    script = tmp_path / "installer-functions.sh"
    script.write_text(
        source
        + "\nif declare -F ensure_codex_permission >/dev/null; then ensure_codex_permission; else offer_codex_setup; fi\n"
    )
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not (home / ".claude/settings.json").exists()


def test_shipped_opencode_retains_native_tasks_without_dead_server() -> None:
    config = json.loads((ROOT / ".opencode/opencode.json").read_text())
    assert "codex" not in config.get("mcp", {})
    assert config["agent"]["quest"]["permission"]["task"]["builder"] == "allow"


def test_manifest_installs_codex_runner_and_module() -> None:
    entries = (ROOT / ".quest-manifest").read_text().splitlines()
    assert "scripts/quest_codex_runner.py" in entries
    assert "scripts/quest_runtime/codex_runner.py" in entries


@pytest.fixture
def installed_candidate(tmp_path: Path) -> InstalledCandidate:
    """Run the real installer, replacing only remote git/curl boundaries."""
    snapshot = tmp_path / "candidate snapshot"
    snapshot.mkdir()
    entries = (ROOT / ".quest-manifest").read_text().splitlines()
    for entry in entries:
        source = ROOT / entry
        if entry and not entry.startswith(("#", "[")) and source.is_file():
            dest = snapshot / entry
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    shutil.copy2(ROOT / ".quest-manifest", snapshot / ".quest-manifest")
    revision = "a" * 40
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real_git = shutil.which("git")
    git = bin_dir / "git"
    git.write_text(
        "#!/usr/bin/env python3\nimport os,sys\n"
        "if sys.argv[1] == 'ls-remote':\n"
        f" print('{revision}\\trefs/heads/quest/codex-cli-dispatch')\n"
        f"else: os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n"
    )
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys\n"
        "args=sys.argv[1:]\nurl=next(a for a in args if a.startswith('https://'))\n"
        f"prefix='https://raw.githubusercontent.com/KjellKod/quest/{revision}/'\n"
        "assert url.startswith(prefix), url\n"
        f"path=pathlib.Path({str(snapshot)!r}) / url[len(prefix):]\n"
        "if not path.is_file(): sys.exit(22)\n"
        "if '-o' in args: pathlib.Path(args[args.index('-o')+1]).write_bytes(path.read_bytes())\n"
        "else: sys.stdout.buffer.write(path.read_bytes())\n"
    )
    for tool in (git, curl):
        tool.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    consumer = tmp_path / "installed consumer"
    consumer.mkdir()
    subprocess.run([real_git, "init", "-q", str(consumer)], check=True)
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "PYTHONPATH": "",
    }
    command = [
        "bash",
        str(ROOT / "scripts/quest_installer.sh"),
        "--force",
        "--skip-self-update",
        "--branch",
        "quest/codex-cli-dispatch",
    ]
    result = subprocess.run(
        command, cwd=consumer, env=env, text=True, capture_output=True, timeout=180
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (consumer / ".quest-version").read_text().strip() == revision
    return consumer, env, command


def test_actual_installer_distributes_importable_runner_outside_consumer(
    installed_candidate: InstalledCandidate, tmp_path: Path
) -> None:
    consumer, env, _ = installed_candidate
    target = tmp_path / "separate target"
    target.mkdir()
    runner = consumer / "scripts/quest_codex_runner.py"
    result = subprocess.run(
        ["python3", str(runner), "--help"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "probe" in result.stdout
    result = subprocess.run(
        [
            "python3",
            "-c",
            "import sys; sys.path.insert(0,sys.argv[1]); import quest_runtime.codex_runner as m; print(m.__file__)",
            str(consumer / "scripts"),
        ],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert str(consumer / "scripts/quest_runtime/codex_runner.py") in result.stdout

    executable = Path(env["PATH"].split(os.pathsep)[0]) / "codex"
    executable.write_text("""#!/usr/bin/env python3
import json, pathlib, sys
a = sys.argv[1:]
if a == ["exec", "--help"]:
    print("--json --cd --sandbox --model --config --add-dir --output-last-message --skip-git-repo-check")
elif a == ["login", "status"]:
    print("Logged in using ChatGPT")
elif a == ["mcp", "list", "--json"]:
    print("[]")
else:
    assert sys.stdin.read() == "installed boundary task"
    cwd = pathlib.Path(a[a.index("--cd")+1])
    (cwd / "receipt.json").write_text(json.dumps(a))
    pathlib.Path(a[a.index("-o")+1]).write_text("done\\n")
    print(json.dumps({"type":"thread.started", "thread_id":"installed-fixture"}))
    print(json.dumps({"type":"turn.completed", "usage":{"input_tokens":1,"output_tokens":1}}))
""")
    executable.chmod(0o755)
    artifacts = tmp_path / "external artifacts"
    artifacts.mkdir()
    command = [
        "python3",
        str(runner),
        "task",
        "--cwd",
        str(target),
        "--output-dir",
        str(artifacts),
        "--auth",
        "cached",
        "--model",
        "fixture-model",
        "--effort",
        "high",
        "--sandbox",
        "workspace-write",
    ]
    blocked = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        input="installed boundary task",
        text=True,
        capture_output=True,
    )
    assert blocked.returncode != 0
    assert not (target / "receipt.json").exists()
    result = subprocess.run(
        [*command, "--allow-non-git"],
        cwd=tmp_path,
        env=env,
        input="installed boundary task",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    args = json.loads((target / "receipt.json").read_text())
    assert args[args.index("--cd") + 1] == str(target)
    assert str(artifacts) in args
    assert "--skip-git-repo-check" in args
    assert not (consumer / "receipt.json").exists()


def test_actual_installer_upgrade_preserves_custom_opencode_and_global_config(
    installed_candidate: InstalledCandidate,
) -> None:
    consumer, env, command = installed_candidate
    path = consumer / ".opencode/opencode.json"
    config = json.loads(path.read_text())
    config["mcp"] = {
        "codex": {"command": ["npx", "-y", "codex", "mcp-server"]},
        "unrelated": {"command": ["sentinel"]},
    }
    path.write_text(json.dumps(config))
    before = path.read_bytes()
    global_config = Path(env["HOME"]) / ".claude.json"
    global_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "codex-cli": {"command": "codex", "args": ["mcp-server"]},
                    "custom": {"command": "sentinel"},
                }
            }
        )
    )
    global_before = global_config.read_bytes()
    result = subprocess.run(
        command, cwd=consumer, env=env, text=True, capture_output=True, timeout=180
    )
    assert result.returncode == 0, result.stderr
    assert path.read_bytes() == before
    assert global_config.read_bytes() == global_before
    assert "remove only mcp.codex" in result.stdout
    assert "claude mcp remove --scope user codex-cli" in result.stdout

    # Simulate a pristine legacy-managed default, then exercise real checksum upgrade.
    legacy = json.dumps(
        {"mcp": {"codex": {"command": ["npx", "-y", "codex", "mcp-server"]}}}
    ).encode()
    path.write_bytes(legacy)
    checksums = consumer / ".quest-checksums"
    lines = checksums.read_text().splitlines()
    lines = [line for line in lines if not line.endswith("  .opencode/opencode.json")]
    lines.append(hashlib.sha256(legacy).hexdigest() + "  .opencode/opencode.json")
    checksums.write_text("\n".join(lines) + "\n")
    result = subprocess.run(
        command, cwd=consumer, env=env, text=True, capture_output=True, timeout=180
    )
    assert result.returncode == 0, result.stderr
    assert "codex" not in json.loads(path.read_text()).get("mcp", {})
    assert (
        json.loads(path.read_text())["agent"]["quest"]["permission"]["task"]["builder"]
        == "allow"
    )
    assert global_config.read_bytes() == global_before


@pytest.mark.parametrize("config", ["{", '{"codex_auth_mode":"typo"}'])
def test_invalid_auth_configuration_returns_parseable_unavailable(tmp_path, config):
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(config)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/quest_preflight.sh"), "--orchestrator", "claude"],
        cwd=tmp_path,
        env={**os.environ, "QUEST_ALLOWLIST_FILE": str(allowlist)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["available"] is False
    assert payload["checks"]["codex_auth_reason"] == "invalid_configuration"
    assert "allowlist" in " ".join(payload["warning"]).lower()


def test_optional_legacy_scan_without_python_does_not_abort(tmp_path):
    source = (
        (ROOT / "scripts/quest_installer.sh")
        .read_text()
        .split("# Store original args for re-exec after self-update")[0]
    )
    script = tmp_path / "installer-functions.sh"
    script.write_text(
        source
        + "\nSCAN_PATH=$PATH\nPATH=/nonexistent\nreport_legacy_codex_config\nPATH=$SCAN_PATH\necho SCAN_COMPLETED\n"
    )
    result = subprocess.run(
        ["bash", str(script)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "SCAN_COMPLETED" in result.stdout


def test_unrelated_opencode_mcp_does_not_trigger_codex_migration_warning(tmp_path):
    config = tmp_path / ".opencode/opencode.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"mcp": {"other": {"command": ["other", "mcp-server"]}}})
    )
    source = (
        (ROOT / "scripts/quest_installer.sh")
        .read_text()
        .split("# Store original args for re-exec after self-update")[0]
    )
    script = tmp_path / "installer-functions.sh"
    script.write_text(source + "\nreport_legacy_codex_config\n")
    result = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "manually remove only mcp.codex" not in result.stdout


def test_runner_probe_crash_has_sanitized_actionable_diagnostic(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/quest_preflight.sh", scripts / "quest_preflight.sh")
    (scripts / "quest_codex_runner.py").write_text(
        "import sys\nsys.stderr.write('private-credential-do-not-log')\nsys.exit(3)\n"
    )
    result = subprocess.run(
        ["bash", str(scripts / "quest_preflight.sh"), "--orchestrator", "claude"],
        cwd=tmp_path,
        env={**os.environ, "QUEST_ALLOWLIST_FILE": str(tmp_path / "absent")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["available"] is False
    assert payload["checks"]["codex_auth_reason"] == "probe_failed"
    assert "exit 3" in " ".join(payload["warning"])
    assert "private-credential" not in result.stdout + result.stderr
