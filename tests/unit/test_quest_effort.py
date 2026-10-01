"""Saved role settings are authoritative at creation, resume and dispatch."""

import json
import os
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
