"""Unit tests for validation-step selection heuristics."""

from __future__ import annotations

from pathlib import Path

from quest_runtime.pr_review_cycle import select_validation_steps


def _finding(
    *,
    finding_id: str = "F-001",
    kind: str = "review_comment",
    path: str = "scripts/quest_runtime/pr_review_cycle.py",
    write_scope: list[str] | None = None,
    needs_test: bool = True,
    suggested_test: str | None = None,
    shared_boundary: bool = False,
) -> dict[str, object]:
    finding: dict[str, object] = {
        "finding_id": finding_id,
        "source": "reviewer",
        "kind": kind,
        "severity": "medium",
        "confidence": "medium",
        "path": path,
        "line": None,
        "summary": "summary",
        "why_it_matters": "matters",
        "evidence": ["evidence"],
        "action": "action",
        "needs_test": needs_test,
        "write_scope": write_scope or [path],
        "related_acceptance_criteria": [],
    }
    if suggested_test is not None:
        finding["suggested_test"] = suggested_test
    if shared_boundary:
        finding["shared_boundary"] = True
    return finding


def test_select_validation_steps_prioritizes_backlog_named_tests() -> None:
    inventory = {
        "format_command": "fmt",
        "lint_command": "lint",
        "typecheck_command": "typecheck",
        "pytest_command": "pytest",
        "test_paths": ["tests/unit/test_named.py", "tests/unit/test_other.py"],
    }
    finding = _finding(suggested_test="tests/unit/test_named.py")

    steps = select_validation_steps(finding, repo_inventory=inventory)
    level1_steps = [step for step in steps if step["level"] == 1]

    assert level1_steps
    assert level1_steps[0]["target"] == "tests/unit/test_named.py"
    assert level1_steps[0]["command"] == "pytest tests/unit/test_named.py"


def test_select_validation_steps_falls_back_to_nearest_tests_then_module_level() -> None:
    inventory = {
        "format_command": "fmt",
        "lint_command": "lint",
        "typecheck_command": "typecheck",
        "pytest_command": "pytest",
        "test_paths": [
            "tests/scripts/quest_runtime/test_pr_review_cycle.py",
            "tests/unit/test_misc.py",
        ],
        "module_tests_target": "tests/unit/",
    }

    nearest_steps = select_validation_steps(
        _finding(path="scripts/quest_runtime/pr_review_cycle.py", write_scope=[]),
        repo_inventory=inventory,
    )
    nearest_level1 = [step for step in nearest_steps if step["level"] == 1]
    assert nearest_level1[0]["target"] == "tests/scripts/quest_runtime/test_pr_review_cycle.py"

    module_steps = select_validation_steps(
        _finding(path="unmapped/module.py", write_scope=["unmapped/module.py"]),
        repo_inventory=inventory,
    )
    module_level1 = [step for step in module_steps if step["level"] == 1]
    assert module_level1[0]["target"] == "tests/unit/"


def test_select_validation_steps_escalates_to_level_2_only_for_shared_boundary_changes() -> None:
    inventory = {
        "format_command": "fmt",
        "lint_command": "lint",
        "typecheck_command": "typecheck",
        "pytest_command": "pytest",
        "test_paths": ["tests/unit/test_local.py"],
        "level2_command": "pytest tests/",
        "level2_target": "tests/",
    }

    local_steps = select_validation_steps(
        _finding(path="scripts/local_module.py", write_scope=["scripts/local_module.py"]),
        repo_inventory=inventory,
    )
    assert not [step for step in local_steps if step["level"] == 2]

    shared_steps = select_validation_steps(
        _finding(
            path="scripts/quest_runtime/pr_review_cycle.py",
            write_scope=["scripts/quest_runtime/pr_review_cycle.py"],
        ),
        repo_inventory=inventory,
    )
    level2 = [step for step in shared_steps if step["level"] == 2]
    assert level2
    assert level2[0]["target"] == "tests/"


def test_select_validation_steps_escalates_level_2_for_directory_scope_shared_boundary() -> None:
    inventory = {
        "format_command": "fmt",
        "lint_command": "lint",
        "typecheck_command": "typecheck",
        "pytest_command": "pytest",
        "test_paths": ["tests/unit/test_local.py"],
        "level2_command": "pytest tests/",
        "level2_target": "tests/",
    }

    directory_scope_steps = select_validation_steps(
        _finding(
            path="scripts/quest_runtime/pr_review_cycle.py",
            write_scope=["scripts/quest_runtime"],
        ),
        repo_inventory=inventory,
    )
    level2 = [step for step in directory_scope_steps if step["level"] == 2]
    assert level2
    assert level2[0]["target"] == "tests/"


def test_select_validation_steps_degrades_gracefully_when_scaffolding_missing() -> None:
    steps = select_validation_steps(
        _finding(path="scripts/example.py", write_scope=["scripts/example.py"]),
        repo_inventory=None,
    )
    level0_steps = [step for step in steps if step["level"] == 0]

    assert level0_steps
    assert all(step["command"] == "true" for step in level0_steps)
    assert all("passthrough" in step["reason"] for step in level0_steps)


def test_select_validation_steps_discovers_shell_tests_without_inventory(
    tmp_path: Path, monkeypatch
) -> None:
    test_path = tmp_path / "tests" / "scripts" / "test-quest-state.sh"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    steps = select_validation_steps(
        _finding(
            path="scripts/quest_validate-quest-state.sh",
            write_scope=["scripts/quest_validate-quest-state.sh"],
        ),
        repo_inventory=None,
    )

    level1_steps = [step for step in steps if step["level"] == 1]
    assert level1_steps
    assert level1_steps[0]["target"] == "tests/scripts/test-quest-state.sh"
    assert level1_steps[0]["command"] == "bash tests/scripts/test-quest-state.sh"
