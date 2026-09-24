"""Per-role reasoning effort across the four dispatch paths.

Effort reaches a role by a different mechanism per path: subagent frontmatter
(Claude-led -> Claude), `claude --effort` via the runner (Codex-led -> Claude),
and `model_reasoning_effort` (both Codex paths). These cover the shared
resolution rule and the two Claude-side plumbing points.
"""

import json

import pytest

from quest_runtime import claude_runner
from quest_runtime.orchestration import (
    CANONICAL_ROLES,
    DEFAULT_EFFORT,
    effort_for_role,
    validate_effort_map,
    write_orchestration_json,
)

BRIDGE_ARGS = {
    "cwd": ".",
    "bridge_script": "scripts/quest_claude_bridge.py",
    "prompt_file": "p.txt",
    "model": "claude-opus-5-5",
    "timeout": 60.0,
    "permission_mode": "bypassPermissions",
}


def test_bridge_cmd_passes_effort_flag():
    cmd = claude_runner.build_bridge_cmd(**BRIDGE_ARGS, effort="medium")
    assert cmd[cmd.index("--effort") + 1] == "medium"


def test_bg_cmd_passes_effort_flag():
    cmd = claude_runner.build_bg_cmd(
        cwd=".",
        bg_runner_script="scripts/quest_claude_bg_run.py",
        prompt_file="p.txt",
        name="quest-x-arbiter-i1",
        model="claude-opus-5-5",
        timeout=60.0,
        permission_mode="bypassPermissions",
        handoff_file="h.json",
        wait_for=[],
        effort="high",
    )
    assert cmd[cmd.index("--effort") + 1] == "high"


def test_effort_flag_omitted_when_unset():
    # No pinned effort must leave the CLI default untouched, not guess a level.
    assert "--effort" not in claude_runner.build_bridge_cmd(**BRIDGE_ARGS)


def test_claude_runtime_rejects_codex_only_ultra():
    # `ultra` is valid in the shared role map but unreachable on the Claude CLI,
    # so it must fail loudly rather than silently run at the default.
    with pytest.raises(ValueError, match="ultra"):
        claude_runner.build_bridge_cmd(**BRIDGE_ARGS, effort="ultra")


def test_effort_map_wins_over_legacy_scalar():
    saved = {"effort": {"arbiter": "high"}, "codex_reasoning_effort": "low"}
    assert effort_for_role(saved, "arbiter") == "high"


def test_legacy_quests_resolve_through_the_scalar():
    # A quest written before the per-role map keeps its saved effort, so resume
    # never silently re-tiers work that is already in flight. The scalar is
    # Codex-scoped, so resolving it needs the role's model — see
    # test_quest_effort_regressions for the full contract.
    legacy = {
        "models": {"builder": "gpt-6-astra"},
        "codex_reasoning_effort": "medium",
    }
    assert effort_for_role(legacy, "builder") == "medium"
    assert effort_for_role({}, "builder") is None


def test_invalid_level_is_rejected():
    with pytest.raises(ValueError, match="builder"):
        validate_effort_map({"builder": "turbo"})
    with pytest.raises(ValueError, match="unknown role"):
        validate_effort_map({"nobody": "high"})


def test_orchestration_json_persists_a_complete_effort_map(tmp_path):
    path = tmp_path / "orchestration.json"
    write_orchestration_json(
        path,
        models={role: "claude-opus-5-5" for role in CANONICAL_ROLES},
        source="default",
        overridden_roles=[],
        effort={"builder": "max"},
    )
    saved = json.loads(path.read_text())
    assert set(saved["effort"]) == set(CANONICAL_ROLES)
    assert saved["effort"]["builder"] == "max"
    # Roles the caller did not pin fall back to the shipped default.
    assert saved["effort"]["fixer"] == DEFAULT_EFFORT["fixer"]


def test_allowlist_and_generated_defaults_agree():
    # The generator is the only thing keeping four dispatch surfaces in sync;
    # drift here means a role silently runs at a different effort than declared.
    allowlist = json.loads(open(".ai/allowlist.json").read())
    assert allowlist["effort"] == DEFAULT_EFFORT
