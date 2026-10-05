"""Saved role settings are authoritative at creation, resume and dispatch."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from quest_runtime.orchestration import (
    DEFAULT_MODELS,
    SOLO_UNUSED_ROLES,
    effort_for_role,
    is_model_available_for_orchestrator,
    migrate_from_snapshot,
    validate_effort_config,
    write_default_from_allowlist,
    write_orchestration_json,
)

ROOT = Path(__file__).resolve().parents[2]


def test_shipped_defaults_round_trip_and_resume_ignores_current_allowlist(
    tmp_path, monkeypatch
):
    allowlist = json.loads((ROOT / ".ai/allowlist.json").read_text())
    path = tmp_path / "orchestration.json"
    write_default_from_allowlist(path, allowlist["models"], effort=allowlist["effort"])
    saved = json.loads(path.read_text())
    assert saved["effort"] == allowlist["effort"]
    assert "codex_reasoning_effort" not in saved
    allowlist["effort"]["builder"] = "low"
    (tmp_path / ".ai").mkdir()
    (tmp_path / ".ai/allowlist.json").write_text(json.dumps(allowlist))
    monkeypatch.chdir(tmp_path)
    before = path.read_bytes()
    assert not migrate_from_snapshot(tmp_path)
    assert path.read_bytes() == before
    assert effort_for_role(saved, "builder") == "medium"


@pytest.mark.parametrize("effort", [None, {}, {"bogus": "medium"}, {"builder": False}])
def test_invalid_or_missing_map_never_writes(tmp_path, effort):
    path = tmp_path / "orchestration.json"
    with pytest.raises(ValueError, match="effort"):
        write_default_from_allowlist(path, DEFAULT_MODELS, effort=effort)
    assert not path.exists()


def test_solo_can_omit_inactive_effort_and_models(tmp_path):
    models = {
        r: None if r in SOLO_UNUSED_ROLES else m for r, m in DEFAULT_MODELS.items()
    }
    efforts = {r: "medium" for r, m in models.items() if m}
    path = tmp_path / "orchestration.json"
    write_orchestration_json(
        path,
        models=models,
        effort=efforts,
        source="default",
        overridden_roles=[],
        quest_mode="solo",
    )
    saved = json.loads(path.read_text())
    validate_effort_config(saved, "solo")
    # Retaining an unused default pin is harmless; no role will be dispatched.
    saved["effort"]["arbiter"] = "medium"
    validate_effort_config(saved, "solo")
    (tmp_path / "state.json").write_text(json.dumps({"quest_mode": "solo"}))
    assert not migrate_from_snapshot(tmp_path)


def test_gemini_unpinned_is_valid_but_explicit_pin_rejects(tmp_path):
    models = {**DEFAULT_MODELS, "builder": "gemini-pro"}
    effort = {r: "medium" for r in models if r != "builder"}
    path = tmp_path / "orchestration.json"
    write_default_from_allowlist(path, models, effort=effort)
    saved = json.loads(path.read_text())
    assert effort_for_role(saved, "builder") is None
    saved["effort"]["builder"] = "medium"
    with pytest.raises(ValueError, match="Gemini role builder"):
        validate_effort_config(saved)


@pytest.mark.parametrize("scalar", ["medium", None])
def test_saved_scalar_rejected_even_alongside_valid_map(tmp_path, scalar):
    path = tmp_path / "orchestration.json"
    saved = {
        "models": DEFAULT_MODELS,
        "effort": dict.fromkeys(DEFAULT_MODELS, "medium"),
        "codex_reasoning_effort": scalar,
    }
    path.write_text(json.dumps(saved))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="start a new quest"):
        migrate_from_snapshot(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("level", ["low", "medium", "high", "xhigh", "max"])
def test_claude_accepts_background_runner_effort_syntax(level):
    assert (
        effort_for_role(
            {"models": {"builder": "claude"}, "effort": {"builder": level}}, "builder"
        )
        == level
    )


@pytest.mark.parametrize("orchestrator", ["claude", "codex"])
def test_claude_roles_require_transport_preflight_under_either_orchestrator(
    orchestrator,
):
    assert not is_model_available_for_orchestrator(
        "claude",
        orchestrator=orchestrator,
        codex_available=True,
        claude_available=False,
    )


def test_whitespace_model_rejects_before_effort_resolution():
    with pytest.raises(ValueError, match="invalid model"):
        effort_for_role(
            {"models": {"builder": "   "}, "effort": {"builder": "medium"}}, "builder"
        )


def test_state_validator_imports_its_installed_runtime_outside_workspace(tmp_path):
    quest = tmp_path / "quest"
    quest.mkdir()
    (quest / "state.json").write_text(
        json.dumps(
            {
                "phase": "plan",
                "quest_mode": "solo",
                "plan_iteration": 1,
                "fix_iteration": 0,
            }
        )
    )
    phase = quest / "phase_01_plan"
    phase.mkdir()
    (phase / "review_plan-reviewer-a.md").write_text("Revise the plan.")
    write_default_from_allowlist(
        quest / "orchestration.json",
        DEFAULT_MODELS,
        effort=dict.fromkeys(DEFAULT_MODELS, "medium"),
        quest_mode="solo",
    )
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/quest_validate-quest-state.sh"),
            str(quest),
            "plan",
        ],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("state", ["{", "null", '"solo"', "[]", "directory"])
def test_resume_rejects_unreadable_or_nonobject_state_without_writes(tmp_path, state):
    path = tmp_path / "orchestration.json"
    write_default_from_allowlist(
        path, DEFAULT_MODELS, effort=dict.fromkeys(DEFAULT_MODELS, "medium")
    )
    before = path.read_bytes()
    state_path = tmp_path / "state.json"
    if state == "directory":
        state_path.mkdir()
    else:
        state_path.write_text(state)
    with pytest.raises(ValueError, match="state.json.*(repair|Repair)"):
        migrate_from_snapshot(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("transport", ["bridge", "background-agent", "typo"])
def test_snapshot_restore_preserves_transport_or_rejects_invalid_policy(
    tmp_path, transport
):
    (tmp_path / "logs").mkdir()
    snapshot = {
        "models": DEFAULT_MODELS,
        "effort": dict.fromkeys(DEFAULT_MODELS, "medium"),
        "claude_role_transport": transport,
    }
    (tmp_path / "logs/allowlist_snapshot.json").write_text(json.dumps(snapshot))
    path = tmp_path / "orchestration.json"
    if transport == "typo":
        with pytest.raises(ValueError, match="claude_role_transport"):
            migrate_from_snapshot(tmp_path)
        assert not path.exists()
    else:
        assert migrate_from_snapshot(tmp_path)
        saved = json.loads(path.read_text())
        assert saved["claude_role_transport"] == transport
        assert saved["claude_transport_resolved"] is None


@pytest.mark.parametrize("case", ["missing", "empty", "valid", "gemini", "hook"])
def test_config_validator_checks_default_effort_without_ajv(tmp_path, case):
    allowlist = json.loads((ROOT / ".ai/allowlist.json").read_text())
    if case == "missing":
        allowlist.pop("effort")
    elif case == "empty":
        allowlist["effort"] = {}
    elif case == "gemini":
        allowlist["models"] = dict.fromkeys(DEFAULT_MODELS, "gemini-pro")
        allowlist["effort"] = {}
    (tmp_path / ".ai/schemas").mkdir(parents=True)
    (tmp_path / ".ai/roles").mkdir()
    (tmp_path / ".ai/allowlist.json").write_text(json.dumps(allowlist))
    shutil.copy(ROOT / ".ai/schemas/allowlist.schema.json", tmp_path / ".ai/schemas")
    shutil.copy(ROOT / ".ai/roles/quest_agent.md", tmp_path / ".ai/roles")
    shutil.copytree(ROOT / ".skills/quest/agents", tmp_path / ".skills/quest/agents")
    (tmp_path / ".gitignore").write_text(".quest/\n.worktrees/\n")
    bins = tmp_path / "bin"
    bins.mkdir()
    for name in (
        "basename",
        "dirname",
        "find",
        "git",
        "grep",
        "head",
        "python3",
        "sort",
        "tail",
    ):
        (bins / name).symlink_to(shutil.which(name))
    script = ROOT / "scripts/quest_validate-quest-config.sh"
    if case == "hook":
        hook = tmp_path / ".git/hooks/pre-commit"
        hook.parent.mkdir(parents=True)
        hook.symlink_to(script)
        script = hook
    result = subprocess.run(
        ["/bin/bash", str(script)],
        cwd=tmp_path,
        env={**os.environ, "PATH": str(bins)},
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert (result.returncode == 0) == (case in {"valid", "gemini", "hook"}), output
    assert "effort" in output


@pytest.mark.parametrize("missing", ["python3", "runtime"])
def test_state_validator_reports_missing_dependencies_without_traceback(
    tmp_path, missing
):
    quest = tmp_path / "quest"
    quest.mkdir()
    (quest / "state.json").write_text(
        json.dumps(
            {
                "phase": "plan",
                "quest_mode": "solo",
                "plan_iteration": 1,
                "fix_iteration": 0,
            }
        )
    )
    (quest / "phase_01_plan").mkdir()
    (quest / "phase_01_plan/review_plan-reviewer-a.md").write_text("Revise")
    write_default_from_allowlist(
        quest / "orchestration.json",
        DEFAULT_MODELS,
        effort=dict.fromkeys(DEFAULT_MODELS, "medium"),
        quest_mode="solo",
    )
    script = ROOT / "scripts/quest_validate-quest-state.sh"
    env = dict(os.environ)
    if missing == "python3":
        bins = tmp_path / "bin"
        bins.mkdir()
        for name in ("basename", "dirname", "git", "jq", "date", "mkdir"):
            (bins / name).symlink_to(shutil.which(name))
        env["PATH"] = str(bins)
    else:
        installed = tmp_path / "installed"
        installed.mkdir()
        shutil.copy(script, installed)
        script = installed / script.name
        (installed / "quest_runtime").mkdir()
        (installed / "quest_runtime/__init__.py").write_text("")
        (installed / "quest_runtime/orchestration.py").write_text("")
    result = subprocess.run(
        ["/bin/bash", str(script), str(quest), "plan"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Traceback" not in output, output
    assert (
        "python3 is required" if missing == "python3" else "reinstall"
    ) in output, output


def test_model_remap_requires_explicit_compatible_effort_before_writing(tmp_path):
    effort = dict.fromkeys(DEFAULT_MODELS, "medium")
    effort["builder"] = "ultra"
    path = tmp_path / "orchestration.json"
    with pytest.raises(ValueError, match="effort.builder for claude"):
        write_default_from_allowlist(
            path,
            DEFAULT_MODELS,
            effort=effort,
            orchestrator="claude",
            codex_available=False,
            claude_available=True,
            remap_unavailable=True,
        )
    assert not path.exists()
    assert effort["builder"] == "ultra"
    effort["builder"] = "high"
    write_default_from_allowlist(
        path,
        DEFAULT_MODELS,
        effort=effort,
        orchestrator="claude",
        codex_available=False,
        claude_available=True,
        remap_unavailable=True,
    )
    saved = json.loads(path.read_text())
    assert saved["models"]["builder"] == "claude"
    assert saved["effort"]["builder"] == "high"
