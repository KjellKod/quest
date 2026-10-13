"""Effort-format upgrades refuse before changing the consuming repository."""

from __future__ import annotations

import errno
import pty
import select
import time
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40


def valid_allowlist(builder_effort: str = "medium") -> dict[str, object]:
    config = json.loads((ROOT / ".ai/allowlist.json").read_text())
    config["effort"]["builder"] = builder_effort
    return config


def run_install(
    tmp_path: Path,
    target: Path,
    *,
    framework_files: dict[str, str] | None = None,
    copy_manifest: bool = False,
    validator_available: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Exercise run_install, replacing network reads and optional global setup."""
    source = tmp_path / "upstream"
    source.mkdir()
    files = {"payload.txt": "new runtime payload\n", **(framework_files or {})}
    (source / ".quest-manifest").write_text(
        "[copy-as-is]\n"
        + (".quest-manifest\n" if copy_manifest else "")
        + "\n".join(files)
        + "\n[user-customized]\n.ai/allowlist.json\n"
    )
    for name, content in files.items():
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    (source / ".ai").mkdir()
    (source / ".ai/allowlist.json").write_text(json.dumps(valid_allowlist()))
    validator = source / "scripts/quest_runtime/orchestration.py"
    validator.parent.mkdir(parents=True, exist_ok=True)
    if validator_available:
        shutil.copy2(ROOT / "scripts/quest_runtime/orchestration.py", validator)
    functions = tmp_path / "installer-functions.sh"
    functions.write_text(
        (ROOT / "scripts/quest_installer.sh")
        .read_text()
        .split("# Store original args for re-exec after self-update")[0]
    )
    script = tmp_path / "run.sh"
    script.write_text(
        'source "$INSTALLER_FUNCTIONS"\n'
        "fetch_latest_release() { LATEST_RELEASE=fixture; }\n"
        'fetch_upstream_version() { UPSTREAM_SHA="$FIXTURE_SHA"; }\n'
        'fetch_file() { cat "$FIXTURE_UPSTREAM/$1"; }\n'
        'fetch_file_to_temp() { cp "$FIXTURE_UPSTREAM/$1" "$2"; }\n'
        "offer_codex_setup() { :; }\n"
        "parse_args --force --branch acceptance-fixture\n"
        "run_install\n"
    )
    return subprocess.run(
        ["bash", str(script)],
        cwd=target,
        env={
            **os.environ,
            "INSTALLER_FUNCTIONS": str(functions),
            "FIXTURE_UPSTREAM": str(source),
            "FIXTURE_SHA": REVISION,
        },
        text=True,
        capture_output=True,
        timeout=30,
    )


def snapshot_tree(root: Path) -> dict[str, bytes | str | None]:
    """Include empty directories and link targets without following symlinks."""
    snapshot: dict[str, bytes | str | None] = {}
    for path in root.rglob("*"):
        key = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[key] = os.readlink(path)
        else:
            snapshot[key] = None if path.is_dir() else path.read_bytes()
    return snapshot


@pytest.mark.parametrize(
    "allowlist",
    [
        {},
        {"effort": None},
        {"effort": "medium"},
        {"effort": {}},
        valid_allowlist("unsupported"),
        {**valid_allowlist(), "models": []},
    ],
)
def test_old_effort_format_refuses_before_any_repository_write(
    tmp_path: Path, allowlist: dict[str, object]
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text(json.dumps(allowlist))
    (target / ".quest-version").write_text("old-version\n")
    old_checksum = hashlib.sha256(b"old runtime payload\n").hexdigest()
    (target / ".quest-checksums").write_text(f"{old_checksum}  payload.txt\n")
    (target / "payload.txt").write_text("old runtime payload\n")
    before = snapshot_tree(target)

    result = run_install(tmp_path, target)

    assert result.returncode != 0, result.stdout + result.stderr
    after = snapshot_tree(target)
    assert after == before
    assert "Installation Complete" not in result.stdout
    assert ".ai/allowlist.json" in result.stdout
    assert (
        f"https://raw.githubusercontent.com/KjellKod/quest/{REVISION}/.ai/allowlist.json"
        in result.stdout
    )
    assert "effort" in result.stdout
    assert "This installer pass stopped before changing project files." in result.stdout
    assert "No installation files were changed" not in result.stdout


@pytest.mark.parametrize("existing", [False, True])
def test_fresh_or_current_effort_format_installs(
    tmp_path: Path, existing: bool
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    if existing:
        (target / ".ai").mkdir()
        (target / ".ai/allowlist.json").write_text(json.dumps(valid_allowlist("low")))

    result = run_install(tmp_path, target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "payload.txt").read_text() == "new runtime payload\n"
    assert (target / ".quest-version").read_text().strip() == REVISION
    saved = json.loads((target / ".ai/allowlist.json").read_text())
    assert saved["effort"]["builder"] == ("low" if existing else "medium")


@pytest.mark.parametrize(
    "case",
    [
        "changed_custom",
        "unknown_checksum",
        "pristine",
        "symlink_pristine",
        "already_current",
        "unchanged_custom",
    ],
)
def test_framework_upgrade_never_leaves_changed_custom_dispatch_behind(
    tmp_path: Path, case: str
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text(json.dumps(valid_allowlist()))
    (target / ".quest-version").write_text("old-version\n")
    path = (
        ".claude/agents/arbiter.md"
        if case == "unchanged_custom"
        else ".skills/quest/delegation/workflow.md"
    )
    old = "Native role instructions\n"
    upstream = old if case == "unchanged_custom" else "Background role instructions\n"
    local = old + "Local customization\n"
    if case == "pristine":
        local = old
    elif case == "already_current":
        local = upstream
    destination = target / path
    destination.parent.mkdir(parents=True)
    external = tmp_path / "external-workflow.md"
    if case == "symlink_pristine":
        external.write_text(old)
        destination.symlink_to(external)
    else:
        destination.write_text(local)
    checksum = hashlib.sha256(old.encode()).hexdigest()
    (target / ".quest-checksums").write_text(
        "" if case == "unknown_checksum" else f"{checksum}  {path}\n"
    )
    before = snapshot_tree(target)

    result = run_install(tmp_path, target, framework_files={path: upstream})

    if case in {"changed_custom", "unknown_checksum", "symlink_pristine"}:
        assert result.returncode != 0, result.stdout + result.stderr
        after = snapshot_tree(target)
        assert after == before
        if case == "symlink_pristine":
            assert external.read_text() == old
            assert destination.is_symlink()
        assert path in result.stdout
        assert (
            f"https://raw.githubusercontent.com/KjellKod/quest/{REVISION}/{path}"
            in result.stdout
        )
        assert "Installation Complete" not in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert destination.read_text() == (
            local if case == "unchanged_custom" else upstream
        )
        assert (target / ".quest-version").read_text().strip() == REVISION


def test_modified_manifest_is_backed_up_and_replaced_during_upgrade(
    tmp_path: Path,
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text(json.dumps(valid_allowlist()))
    old_manifest = "[copy-as-is]\nold-runtime.txt\n"
    custom_manifest = old_manifest + "# local bookkeeping customization\n"
    (target / ".quest-manifest").write_text(custom_manifest)
    checksum = hashlib.sha256(old_manifest.encode()).hexdigest()
    (target / ".quest-checksums").write_text(f"{checksum}  .quest-manifest\n")

    result = run_install(tmp_path, target, copy_manifest=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        target / ".quest-manifest.quest_local_backup"
    ).read_text() == custom_manifest
    assert (target / ".quest-manifest").read_bytes() == (
        tmp_path / "upstream/.quest-manifest"
    ).read_bytes()
    assert (target / "payload.txt").read_text() == "new runtime payload\n"
    assert (target / ".quest-version").read_text().strip() == REVISION


def test_gemini_only_allowlist_needs_no_effort_pins(tmp_path: Path) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    config = valid_allowlist()
    config["models"] = dict.fromkeys(config["models"], "gemini-pro")
    config["effort"] = {}
    allowlist = target / ".ai/allowlist.json"
    allowlist.write_text(json.dumps(config))
    before = allowlist.read_bytes()

    result = run_install(tmp_path, target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert allowlist.read_bytes() == before


def test_unavailable_upstream_validator_refuses_before_writes(tmp_path: Path) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text(json.dumps(valid_allowlist("low")))
    before = snapshot_tree(target)

    result = run_install(tmp_path, target, validator_available=False)

    assert result.returncode != 0, result.stdout + result.stderr
    assert snapshot_tree(target) == before
    assert "validator" in result.stdout.lower()


# Byte-for-byte git export of 319494ec43e53906836e8054aebedabeca1f8314.
LEGACY_INSTALLER = ROOT / "tests/fixtures/installers/quest_installer_319494ec.sh"
LEGACY_SHA256 = "7ae4063fc7257f2da53d29ef06e9d1d470f6cd9b752e8ee2cfb7f6b92e42f28e"
BRANCH = "feat/quest-effort-dispatch"
EFFORT_PROMPT = "Add these effort defaults to .ai/allowlist.json and continue?"


@pytest.fixture
def upgrade_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Full real distribution; only remote executable boundaries are replaced."""
    upstream = tmp_path / "upstream snapshot"
    upstream.mkdir()
    for entry in (ROOT / ".quest-manifest").read_text().splitlines():
        source = ROOT / entry
        if entry and not entry.startswith(("#", "[")) and source.is_file():
            destination = upstream / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    shutil.copy2(
        ROOT / "scripts/quest_installer.sh", upstream / "scripts/quest_installer.sh"
    )
    tools = tmp_path / "bin"
    tools.mkdir()
    real_git = shutil.which("git")
    (tools / "git").write_text(
        "#!/usr/bin/env python3\nimport os,sys\n"
        "if sys.argv[1] == 'ls-remote':\n"
        f" assert sys.argv[-1] in ('refs/heads/{BRANCH}', 'https://github.com/KjellKod/quest.git'), sys.argv\n"
        f" print('{REVISION}\\t' + ('refs/tags/fixture' if '--tags' in sys.argv else 'refs/heads/{BRANCH}'))\n"
        f"else: os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n"
    )
    (tools / "curl").write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys\n"
        "args=sys.argv[1:]\nurl=next(a for a in args if a.startswith('https://'))\n"
        f"prefix='https://raw.githubusercontent.com/KjellKod/quest/{REVISION}/'\n"
        "assert url.startswith(prefix), url\n"
        f"path=pathlib.Path({str(upstream)!r}) / url[len(prefix):]\n"
        "if not path.is_file(): sys.exit(22)\n"
        "if '-o' in args: pathlib.Path(args[args.index('-o')+1]).write_bytes(path.read_bytes())\n"
        "else: sys.stdout.buffer.write(path.read_bytes())\n"
    )
    # Prevent optional global CLI installation; this executable is never invoked.
    (tools / "codex").write_text("#!/bin/sh\nexit 99\n")
    for tool in tools.iterdir():
        tool.chmod(0o755)
    home = tmp_path / "isolated home"
    home.mkdir()
    target = tmp_path / "old consumer"
    (target / ".ai").mkdir(parents=True)
    config = valid_allowlist()
    del config["effort"]
    config["description"] = "Sanitized customized legacy configuration"
    config["codex_reasoning_effort"] = "high"
    config["models"]["builder"] = "claude-opus-5"
    config["models"]["fixer"] = "gemini-pro"
    (target / ".ai/allowlist.json").write_text(json.dumps(config, indent=4) + "\n")
    (target / ".ai/allowlist.json").chmod(0o640)
    (target / ".quest-version").write_text("319494ec43e53906836e8054aebedabeca1f8314\n")
    (target / ".gitignore").write_text(".quest/\n.worktrees/\n")
    (target / ".quest/existing").mkdir(parents=True)
    (target / ".quest/existing/orchestration.json").write_text('{"legacy": true}\n')
    env = {"HOME": str(home), "PATH": f"{tools}:{os.environ['PATH']}", "PYTHONPATH": ""}
    return target, upstream, env


def run_interactive_installer(
    command: list[str],
    target: Path,
    env: dict[str, str],
    answer: str = "y\n",
    before_answer=None,
) -> subprocess.CompletedProcess[str]:
    """Respond to named prompts through a real PTY, with a bounded deadline."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        command, cwd=target, env=env, stdin=slave, stdout=slave, stderr=slave
    )
    os.close(slave)
    output = ""
    answered = set()
    responses = {
        "Would you like to view .ai/quest.md now?": "n\n",
        "Register Codex MCP server?": "n\n",
        "Update installer now?": "y\n",
        EFFORT_PROMPT: answer,
        "Create a new branch for Quest changes?": "n\n",
    }
    deadline = time.monotonic() + 120
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output += chunk.decode(errors="replace")
                for prompt, response in responses.items():
                    if prompt in output and prompt not in answered:
                        if prompt == EFFORT_PROMPT and before_answer:
                            before_answer()
                        os.write(master, response.encode())
                        answered.add(prompt)
            elif proc.poll() is not None:
                break
        else:
            raise AssertionError(f"Installer timed out:\n{output[-6000:]}")
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(master)
    return subprocess.CompletedProcess(command, proc.returncode, output, "")


@pytest.mark.parametrize("with_git", [False, True])
def test_legacy_installer_self_updates_and_upgrades_effort(upgrade_fixture, with_git):
    target, upstream, env = upgrade_fixture
    assert hashlib.sha256(LEGACY_INSTALLER.read_bytes()).hexdigest() == LEGACY_SHA256
    if with_git:
        subprocess.run(["git", "init", "-q", str(target)], check=True)
    script = target / "scripts/quest_installer.sh"
    script.parent.mkdir()
    shutil.copy2(LEGACY_INSTALLER, script)
    (target / ".quest-checksums").write_text(
        f"{LEGACY_SHA256}  scripts/quest_installer.sh\n"
    )
    original = (target / ".ai/allowlist.json").read_bytes()
    saved_quests = snapshot_tree(target / ".quest")

    result = run_interactive_installer(
        ["bash", str(script), "--branch", BRANCH], target, env
    )

    assert result.returncode == 0, result.stdout
    assert "Re-running updated installer" in result.stdout
    assert EFFORT_PROMPT in result.stdout
    assert script.read_bytes() == (upstream / "scripts/quest_installer.sh").read_bytes()
    updated = json.loads((target / ".ai/allowlist.json").read_text())
    effort = updated.pop("effort")
    assert updated == json.loads(original)
    assert "fixer" not in effort  # Existing Gemini assignment survives.
    expected = json.loads((upstream / ".ai/allowlist.json").read_text())["effort"]
    assert effort == {
        role: value for role, value in expected.items() if role != "fixer"
    }
    backups = list((target / ".ai").glob("allowlist.json.quest_local_backup*"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert (target / ".ai/allowlist.json").stat().st_mode & 0o777 == 0o640
    assert snapshot_tree(target / ".quest") == saved_quests
    validated = subprocess.run(
        ["bash", "scripts/quest_validate-quest-config.sh"],
        cwd=target,
        env=env,
        text=True,
        capture_output=True,
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    writer = subprocess.run(
        [
            "python3",
            "-c",
            "import json,sys; from pathlib import Path; sys.path.insert(0,str(Path('scripts').resolve())); from quest_runtime.orchestration import write_default_from_allowlist; c=json.loads(Path('.ai/allowlist.json').read_text()); write_default_from_allowlist(Path('.quest/new/orchestration.json'),c['models'],effort=c['effort'])",
        ],
        cwd=target,
        env=env,
        text=True,
        capture_output=True,
    )
    assert writer.returncode == 0, writer.stderr
    assert (
        json.loads((target / ".quest/new/orchestration.json").read_text())["effort"]
        == effort
    )
    assert (target / ".quest-version").read_text().strip() == REVISION


def candidate_command() -> list[str]:
    return [
        "bash",
        str(ROOT / "scripts/quest_installer.sh"),
        "--skip-self-update",
        "--branch",
        BRANCH,
    ]


@pytest.mark.parametrize("mode", ["decline", "eof", "noninteractive", "force", "check"])
def test_effort_upgrade_requires_explicit_consent(upgrade_fixture, mode):
    target, _, env = upgrade_fixture
    before = snapshot_tree(target)
    command = candidate_command()
    if mode in ("decline", "eof"):
        result = run_interactive_installer(
            command, target, env, "n\n" if mode == "decline" else "\x04"
        )
    elif mode == "force":
        result = run_interactive_installer(command + ["--force"], target, env)
    else:
        result = subprocess.run(
            command + (["--check"] if mode == "check" else []),
            cwd=target,
            env=env,
            input="y\n",
            text=True,
            capture_output=True,
            timeout=90,
        )
    assert (result.returncode == 0) == (mode == "check"), result.stdout + result.stderr
    assert snapshot_tree(target) == before
    assert '"effort": {' in result.stdout
    if mode not in ("decline", "eof"):
        assert EFFORT_PROMPT not in result.stdout


@pytest.mark.parametrize(
    "failure",
    [
        "validator_fetch",
        "defaults_fetch",
        "incompatible_default",
        "framework",
        "symlink",
        "directory",
        "concurrent_edit",
        "backup",
    ],
)
def test_effort_upgrade_failure_leaves_configuration_untouched(
    upgrade_fixture, failure
):
    target, upstream, env = upgrade_fixture
    allowlist = target / ".ai/allowlist.json"
    callback = None
    external = None
    if failure in ("validator_fetch", "defaults_fetch"):
        (
            upstream
            / (
                "scripts/quest_runtime/orchestration.py"
                if failure == "validator_fetch"
                else ".ai/allowlist.json"
            )
        ).unlink()
    elif failure == "incompatible_default":
        path = upstream / ".ai/allowlist.json"
        config = json.loads(path.read_text())
        config["effort"][
            "builder"
        ] = "ultra"  # Valid Codex default, incompatible customized Claude role.
        path.write_text(json.dumps(config))
    elif failure == "framework":
        (target / ".ai/quest.md").write_text("locally modified old framework\n")
        (target / ".quest-checksums").write_text("b" * 64 + "  .ai/quest.md\n")
    elif failure == "symlink":
        external = target.parent / "external-allowlist.json"
        allowlist.rename(external)
        allowlist.symlink_to(external)
    elif failure == "directory":
        allowlist.unlink()
        allowlist.mkdir()
    elif failure == "concurrent_edit":

        def edit_config():
            config = json.loads(allowlist.read_text())
            config["description"] = "Concurrent edit must survive"
            allowlist.write_text(json.dumps(config))

        callback = edit_config
    elif failure == "backup":
        # Fail precisely the backup creation at the filesystem boundary.
        injection = target.parent / "fault injection"
        injection.mkdir()
        (injection / "sitecustomize.py").write_text(
            "import tempfile\noriginal = tempfile.mkstemp\n"
            "def fail_backup(*args, **kwargs):\n"
            " if '.quest_local_backup.' in kwargs.get('prefix', ''): raise OSError('injected backup failure')\n"
            " return original(*args, **kwargs)\n"
            "tempfile.mkstemp = fail_backup\n"
        )
        env["PYTHONPATH"] = str(injection)
    before = snapshot_tree(target)
    external_bytes = external.read_bytes() if external else None

    result = run_interactive_installer(
        candidate_command(), target, env, before_answer=callback
    )

    assert result.returncode != 0, result.stdout
    if failure == "concurrent_edit":
        changed = json.loads(before[".ai/allowlist.json"])
        changed["description"] = "Concurrent edit must survive"
        before[".ai/allowlist.json"] = json.dumps(changed).encode()
    assert snapshot_tree(target) == before
    if external:
        assert external.read_bytes() == external_bytes
    if failure in ("concurrent_edit", "backup"):
        assert EFFORT_PROMPT in result.stdout
    else:
        assert EFFORT_PROMPT not in result.stdout
    assert "start a new quest" not in result.stdout
    if failure == "incompatible_default":
        assert (
            "Selected upstream effort defaults are incompatible with project models"
            in result.stdout
        )
        assert "effort.builder" in result.stdout
    if failure == "backup":
        assert "Could not apply the approved effort addition" in result.stdout
        assert "Framework installation has not started" in result.stdout


@pytest.mark.parametrize(
    "version", [REVISION, "213cd960e691045d45be08a198eebe1472fa534b"]
)
def test_downloaded_installer_upgrades_current_or_intermediate_version_and_is_idempotent(
    upgrade_fixture, version
):
    target, _, env = upgrade_fixture
    (target / ".quest-version").write_text(version + "\n")
    result = run_interactive_installer(candidate_command(), target, env)
    assert result.returncode == 0, result.stdout
    assert EFFORT_PROMPT in result.stdout
    allowlist = target / ".ai/allowlist.json"
    config = json.loads(allowlist.read_text())
    config["effort"]["builder"] = "low"
    allowlist.write_text(json.dumps(config))
    before = snapshot_tree(target)
    repeat = run_interactive_installer(candidate_command(), target, env)
    assert repeat.returncode == 0, repeat.stdout
    assert EFFORT_PROMPT not in repeat.stdout
    assert snapshot_tree(target) == before
    assert len(list((target / ".ai").glob("allowlist.json.quest_local_backup.*"))) == 1


@pytest.mark.parametrize("model", [None, 7])
def test_missing_effort_with_non_string_model_has_actionable_error(
    upgrade_fixture, model
):
    target, _, env = upgrade_fixture
    path = target / ".ai/allowlist.json"
    config = json.loads(path.read_text())
    config["models"]["arbiter"] = model
    path.write_text(json.dumps(config))
    before = snapshot_tree(target)
    result = run_interactive_installer(candidate_command(), target, env)
    assert result.returncode != 0
    assert snapshot_tree(target) == before
    assert "models.arbiter must be a model name string" in result.stdout
    assert "Traceback" not in result.stdout


def test_invalid_upstream_defaults_do_not_blame_project_configuration(upgrade_fixture):
    target, upstream, env = upgrade_fixture
    path = upstream / ".ai/allowlist.json"
    config = json.loads(path.read_text())
    config["effort"]["builder"] = "unsupported"
    path.write_text(json.dumps(config))
    before = snapshot_tree(target)
    result = run_interactive_installer(candidate_command(), target, env)
    assert result.returncode != 0
    assert snapshot_tree(target) == before
    assert "Selected upstream defaults are unusable" in result.stdout
    assert "effort.builder" in result.stdout
    assert "Review .ai/allowlist.json" not in result.stdout
    assert "allowlist.json has invalid role effort" not in result.stdout


def test_changed_custom_framework_refuses_before_installer_self_update(upgrade_fixture):
    target, _, env = upgrade_fixture
    script = target / "scripts/quest_installer.sh"
    script.parent.mkdir()
    script.write_bytes((ROOT / "scripts/quest_installer.sh").read_bytes() + b"\n")
    (target / ".ai/quest.md").write_text("customized framework instructions\n")
    (target / ".quest-checksums").write_text("b" * 64 + "  .ai/quest.md\n")
    before = snapshot_tree(target)
    result = run_interactive_installer(
        ["bash", str(script), "--branch", BRANCH], target, env
    )
    assert result.returncode != 0
    assert snapshot_tree(target) == before
    assert "Update installer now?" not in result.stdout


def test_failed_final_effort_validation_reports_partial_install_and_preserves_stamp(
    upgrade_fixture,
):
    target, _, env = upgrade_fixture
    # Simulate an external config edit at the remote-download boundary, after approval.
    curl = Path(env["PATH"].split(os.pathsep)[0]) / "curl"
    with curl.open("a") as output:
        output.write(
            "\nif url.endswith('/.claude/settings.json'):\n"
            " import json\n"
            " config_path=pathlib.Path('.ai/allowlist.json')\n"
            " config=json.loads(config_path.read_text())\n"
            " config['effort']={}\n"
            " config_path.write_text(json.dumps(config))\n"
        )
    old_stamp = (target / ".quest-version").read_bytes()
    result = run_interactive_installer(candidate_command(), target, env)
    assert result.returncode != 0
    assert (target / "scripts/quest_runtime/orchestration.py").is_file()
    assert (target / ".quest-version").read_bytes() == old_stamp
    assert not (target / ".quest-checksums").exists()
    assert "Framework files were written" in result.stdout
    assert "version stamp was not recorded" in result.stdout


@pytest.mark.parametrize("model", ["", " gpt-6-astra", "opencode/"])
def test_malformed_local_model_is_not_reported_as_upstream_incompatibility(
    upgrade_fixture, model
):
    target, _, env = upgrade_fixture
    path = target / ".ai/allowlist.json"
    config = json.loads(path.read_text())
    config["models"]["arbiter"] = model
    path.write_text(json.dumps(config))
    before = snapshot_tree(target)
    result = run_interactive_installer(candidate_command(), target, env)
    assert result.returncode != 0
    assert snapshot_tree(target) == before
    assert "Project allowlist effort check failed" in result.stdout
    assert "Selected upstream effort defaults are incompatible" not in result.stdout
    assert "Traceback" not in result.stdout
