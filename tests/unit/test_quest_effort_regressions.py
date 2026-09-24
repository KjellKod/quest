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


@pytest.mark.parametrize("existing", [False, True])
def test_snapshot_migration_keeps_legacy_scalar(tmp_path, existing):
    # Filling DEFAULT_EFFORT here would override the scalar the quest was
    # started with, re-tiering work already in flight.
    quest = _snapshot(tmp_path, codex_reasoning_effort="high")
    if existing:
        (quest / "orchestration.json").write_text(
            (quest / "logs/allowlist_snapshot.json").read_text()
        )
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


@pytest.mark.parametrize("preparation_failure", [False, True])
def test_permission_retry_preserves_effort(tmp_path, monkeypatch, preparation_failure):
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
        if len(argvs) == 1 and not preparation_failure:
            return FakeProcess(stderr="Error: Permission denied writing artifact")
        return FakeProcess(on_communicate=succeed)

    if preparation_failure:

        def deny_preparation(*args, **kwargs):
            raise PermissionError("Permission denied writing artifact")

        monkeypatch.setattr(claude_runner, "prepare_artifact_files", deny_preparation)
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

    assert len(argvs) == (1 if preparation_failure else 2)
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


@pytest.mark.parametrize("effort", [{}, {"arbiter": "low"}])
@pytest.mark.parametrize("existing", [False, True])
def test_migration_preserves_partial_effort(tmp_path, effort, existing):
    quest = _snapshot(tmp_path, effort=effort, codex_reasoning_effort="high")
    if existing:
        (quest / "orchestration.json").write_text(
            (quest / "logs/allowlist_snapshot.json").read_text()
        )
    migrate_from_snapshot(quest)
    saved = json.loads((quest / "orchestration.json").read_text())
    assert saved["effort"] == effort
    assert effort_for_role(saved, "builder") == "high"


@pytest.mark.parametrize("existing", [False, True])
def test_migration_rejects_null_effort(tmp_path, existing):
    quest = _snapshot(tmp_path, effort=None)
    if existing:
        (quest / "orchestration.json").write_text(
            (quest / "logs/allowlist_snapshot.json").read_text()
        )
    with pytest.raises(ValueError, match="effort"):
        migrate_from_snapshot(quest)


def test_null_effort_is_not_absent():
    with pytest.raises(ValueError, match="effort"):
        effort_for_role({"effort": None}, "builder")


@pytest.mark.parametrize("contents", ["{", "[]", "null"])
def test_claude_loader_rejects_corrupt_saved_config(tmp_path, contents):
    from quest_claude_runner import _resolve_effort

    (tmp_path / "orchestration.json").write_text(contents)
    with pytest.raises(ValueError):
        _resolve_effort(str(tmp_path), "arbiter", None)


def test_existing_solo_migration_preserves_null_unused_models(tmp_path):
    from quest_runtime.orchestration import SOLO_UNUSED_ROLES

    models = {
        r: None if r in SOLO_UNUSED_ROLES else "gpt-6-astra" for r in CANONICAL_ROLES
    }
    quest = _snapshot(tmp_path, models=models, effort={"builder": "high"})
    (quest / "orchestration.json").write_text(
        (quest / "logs/allowlist_snapshot.json").read_text()
    )
    (quest / "state.json").write_text('{"quest_mode":"solo"}')
    migrate_from_snapshot(quest)
    saved = json.loads((quest / "orchestration.json").read_text())
    assert saved["models"] == models
    assert saved["effort"] == {"builder": "high"}


@pytest.mark.parametrize("model", [None, "", " ", "opencode/claude-opus-5-5"])
def test_legacy_scalar_does_not_leak_to_missing_or_claude_models(model):
    assert (
        effort_for_role(
            {"models": {"arbiter": model}, "codex_reasoning_effort": "ultra"}, "arbiter"
        )
        is None
    )


@pytest.mark.parametrize("prefix", ["\t", "  ", ""])
def test_generator_strips_indented_quoted_key(prefix):
    from quest_sync_model_defaults import _with_effort

    out = _with_effort(
        "---\nmodel: inherit\n" + prefix + '"effort": low\n---\nbody\n', "high"
    )
    assert '"effort"' not in out
    assert out.count("effort:") == 1


def test_generator_crlf_file_read_and_invalid_opening(tmp_path):
    from quest_sync_model_defaults import _with_effort

    path = tmp_path / "agent.md"
    path.write_bytes(b'---\r\nmodel: inherit\r\n"effort": low\r\n---\r\nbody\r\n')
    assert "effort: high" in _with_effort(path.read_text(), "high")
    with pytest.raises(ValueError):
        _with_effort(path.read_bytes().decode(), "high")
    with pytest.raises(ValueError):
        _with_effort('name: x\n---\n"effort": low\n---\n', "high")


def test_invalid_claude_effort_does_not_truncate_artifacts(tmp_path):
    artifact = tmp_path / "plan.md"
    artifact.write_text("preserve")
    (tmp_path / "state.json").write_text('{"phase":"plan","plan_iteration":1}')
    result = claude_runner.run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=tmp_path / "prompt",
        handoff_file=tmp_path / "handoff",
        bridge_script=tmp_path / "bridge",
        model="claude",
        effort="ultra",
        timeout=1,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
    )
    # Validating early must not cost the JSON envelope: orchestrators parse
    # this result, and a traceback reaches them as an unreadable failure.
    assert result.result_kind == "invocation_error"
    assert "ultra" in result.stderr
    assert artifact.read_text() == "preserve"


@pytest.mark.parametrize(
    "level,frontmatter,accepted",
    [
        ("high", "effort: high", True),
        ("high", "effort: medium", False),
        ("ultra", "effort: ultra", False),
        # An unpinned role must NOT block: the generated frontmatter always
        # names a level, so blocking here would wall off every legacy quest.
        (None, "effort: medium", True),
        (None, "name: arbiter", True),
        # A valid nested subagent key must not be mistaken for ambiguity.
        ("high", "effort: high\nhooks:\n  PreToolUse:\n    - matcher: Bash", True),
        ("high", 'effort: high\n"effort": low', False),
        ("high", "effort: high\n\teffort: low", False),
    ],
)
def test_native_claude_effort_guard(level, frontmatter, accepted):
    from quest_runtime.orchestration import validate_native_claude_effort

    saved = {
        "models": {"arbiter": "opencode/claude-opus-5-5"},
        "codex_reasoning_effort": "ultra",
    }
    if level is not None:
        saved["effort"] = {"arbiter": level}
    text = "---\n" + frontmatter + "\n---\nbody"
    if accepted:
        validate_native_claude_effort(saved, "arbiter", text)
    else:
        with pytest.raises(ValueError):
            validate_native_claude_effort(saved, "arbiter", text)


def test_claude_loader_rejects_unreadable_saved_config(tmp_path):
    from quest_claude_runner import _resolve_effort

    (tmp_path / "orchestration.json").mkdir()
    with pytest.raises(ValueError, match="Cannot read"):
        _resolve_effort(str(tmp_path), "arbiter", None)


@pytest.mark.parametrize("field", ["description: |", "description: >-", "metadata:"])
def test_generator_preserves_nested_effort_content(field):
    from quest_sync_model_defaults import _with_effort

    nested = field + "\n  effort: low\n  other: text"
    text = "---\nmodel: inherit\n" + nested + "\neffort: low\n---\nbody\n"
    result = _with_effort(text, "medium")
    assert nested in result
    assert "\neffort: medium\n" in result


@pytest.mark.parametrize("models", [123, "invalid", ["arbiter"], []])
def test_claude_loader_rejects_non_object_models(tmp_path, models):
    from quest_claude_runner import _resolve_effort

    (tmp_path / "orchestration.json").write_text(
        json.dumps({"models": models, "codex_reasoning_effort": "medium"})
    )
    with pytest.raises(ValueError, match="models"):
        _resolve_effort(str(tmp_path), "arbiter", None)


@pytest.mark.parametrize("model", [123, ["gpt-6-astra"], True, " "])
def test_migration_rejects_invalid_active_model_without_writing(tmp_path, model):
    models = {r: "gpt-6-astra" for r in CANONICAL_ROLES}
    models["builder"] = model
    quest = _snapshot(tmp_path, models=models)
    path = quest / "orchestration.json"
    path.write_text((quest / "logs/allowlist_snapshot.json").read_text())
    before = path.read_bytes()
    with pytest.raises(ValueError, match="model"):
        migrate_from_snapshot(quest)
    assert path.read_bytes() == before
