"""Regressions for defects found reviewing the per-role effort change.

Each test pins a case where effort was silently wrong rather than loudly
wrong, which is the failure mode that makes an effort setting untrustworthy.
"""

import json

import pytest

from quest_runtime import claude_runner
from quest_runtime.orchestration import (
    CANONICAL_ROLES,
    effort_for_role,
    migrate_from_snapshot,
    write_orchestration_json,
)


def _snapshot(tmp_path, **extra):
    quest = tmp_path / "qid"
    (quest / "logs").mkdir(parents=True)
    (quest / "logs" / "allowlist_snapshot.json").write_text(
        json.dumps({"models": {r: "gpt-6-astra" for r in CANONICAL_ROLES}, **extra})
    )
    return quest


def test_snapshot_migration_keeps_legacy_scalar(tmp_path):
    # Filling DEFAULT_EFFORT here would override the scalar the quest was
    # started with, re-tiering work already in flight.
    quest = _snapshot(tmp_path, codex_reasoning_effort="high")
    migrate_from_snapshot(quest)
    saved = json.loads((quest / "orchestration.json").read_text())
    assert "effort" not in saved
    assert effort_for_role(saved, "builder") == "high"


def test_snapshot_migration_without_any_effort_stays_unpinned(tmp_path):
    quest = _snapshot(tmp_path)
    migrate_from_snapshot(quest)
    saved = json.loads((quest / "orchestration.json").read_text())
    assert "effort" not in saved
    assert effort_for_role(saved, "builder") is None


def test_legacy_scalar_is_codex_scoped():
    # The key is named codex_*; before the map existed the Claude runner never
    # read it, so Claude roles must stay unpinned.
    saved = {
        "models": {"builder": "gpt-6-astra", "arbiter": "claude-opus-5-5"},
        "codex_reasoning_effort": "high",
    }
    assert effort_for_role(saved, "builder") == "high"
    assert effort_for_role(saved, "arbiter") is None


def test_legacy_codex_only_ultra_does_not_break_claude_roles():
    # `ultra` is valid for Codex. Leaking it onto a Claude role would turn a
    # previously-working legacy quest into a hard dispatch failure.
    saved = {
        "models": {"arbiter": "claude-opus-5-5"},
        "codex_reasoning_effort": "ultra",
    }
    level = effort_for_role(saved, "arbiter")
    assert level is None
    assert claude_runner.normalize_claude_cli_effort(level) is None


@pytest.mark.parametrize("bad", [{"builder": 5}, {"builder": ""}, [], "high"])
def test_malformed_effort_map_is_loud(bad):
    # A malformed map is a config error. Falling back to the legacy scalar
    # would hide it behind a plausible-looking level.
    with pytest.raises(ValueError):
        effort_for_role({"effort": bad, "codex_reasoning_effort": "high"}, "builder")


def test_unknown_role_key_is_rejected():
    with pytest.raises(ValueError, match="unknown role"):
        effort_for_role({"effort": {"buidler": "high"}}, "builder")


def test_new_quest_writer_still_persists_a_full_map(tmp_path):
    # The migration fix must not stop new quests from getting defaults.
    from quest_runtime.orchestration import write_default_from_allowlist

    path = tmp_path / "orchestration.json"
    write_default_from_allowlist(
        path, {r: "gpt-6-astra" for r in CANONICAL_ROLES}, effort=None
    )
    saved = json.loads(path.read_text())
    assert set(saved["effort"]) == set(CANONICAL_ROLES)


def test_write_orchestration_json_omits_effort_when_unset(tmp_path):
    path = tmp_path / "orchestration.json"
    write_orchestration_json(
        path,
        models={r: "gpt-6-astra" for r in CANONICAL_ROLES},
        source="default",
        overridden_roles=[],
    )
    assert "effort" not in json.loads(path.read_text())


def test_permission_retry_preserves_effort(tmp_path, monkeypatch):
    # A retry that silently drops to the default effort makes the pinned value
    # a lie on exactly the runs that were already going badly. Drives the real
    # Tier B permission retry and inspects both dispatched argvs.
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("prompt", encoding="utf-8")
    (tmp_path / "state.json").write_text(
        json.dumps({"phase": "plan", "plan_iteration": 1}), encoding="utf-8"
    )
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "artifact.md"

    class FakeProcess:
        returncode = 1

        def __init__(self, stderr="", on_communicate=None):
            self._stderr = stderr
            self._on_communicate = on_communicate

        def communicate(self, timeout=None):
            if self._on_communicate:
                self._on_communicate()
            return "", self._stderr

        def poll(self):
            return self.returncode

        def terminate(self):
            return None

        def kill(self):
            return None

    argvs: list[list[str]] = []

    def succeed():
        artifact.write_text("ok", encoding="utf-8")
        handoff_file.write_text(
            '{"status":"complete","artifacts":["artifact.md"],'
            '"next":null,"summary":"ok"}',
            encoding="utf-8",
        )

    def fake_popen(cmd, *args, **kwargs):
        argvs.append(list(cmd))
        if len(argvs) == 1:
            return FakeProcess(stderr="Error: Permission denied writing artifact")
        return FakeProcess(on_communicate=succeed)

    monkeypatch.setattr(claude_runner.subprocess, "Popen", fake_popen)

    claude_runner.run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "bridge.py",
        model="claude-opus-5-5",
        effort="high",
        timeout=1.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.01,
    )

    assert len(argvs) == 2, "expected an initial dispatch plus one Tier B retry"
    for attempt, argv in enumerate(argvs, start=1):
        assert "--effort" in argv, f"attempt {attempt} dropped --effort"
        assert argv[argv.index("--effort") + 1] == "high"


def test_generator_replaces_quoted_effort_key():
    from quest_sync_model_defaults import _with_effort

    out = _with_effort(
        '---\nname: x\nmodel: inherit\n"effort": low\n---\nbody\n', "high"
    )
    assert '"effort"' not in out
    assert "effort: high" in out
