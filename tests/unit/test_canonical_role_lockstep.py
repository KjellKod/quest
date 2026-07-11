"""Drift guard: every surface that enumerates orchestration role slots must agree
with ``CANONICAL_ROLES`` in ``scripts/quest_runtime/orchestration.py``.

The canonical role set is duplicated across many literals (allowlist data, the
allowlist JSON schema, the state validator, the artifact registries, and the
operator docs). Hand-verifying that duplicated list on every role change is
leaky -- a real example: adding ``review-arbiter`` updated 7 surfaces but missed
the schema enum, which only surfaced as a CI failure. These tests treat
``CANONICAL_ROLES`` as the single source of truth and fail *by name* the moment
any surface drifts, so a missing/stale role is caught in the required ``test``
check instead of at runtime or by luck in CI.

Scope: orchestration role *slots* (planner, plan-reviewer-a/b, arbiter, builder,
code-reviewer-a/b, review-arbiter, fixer). The separate agent-contract-file
dimension (role *types*) is guarded by
``test_runtime_agent_role_files_reference_canonical.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from quest_runtime.artifacts import (
    ROLE_ARTIFACTS,
    ROLE_PHASE_ALIASES,
    SOLO_DISABLED_AGENTS,
)
from quest_runtime.orchestration import (
    CANONICAL_ROLES,
    DEFAULT_MODELS,
    SOLO_UNUSED_ROLES,
)

CANONICAL = set(CANONICAL_ROLES)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _diff_message(surface: str, found: set[str]) -> str:
    missing = CANONICAL - found
    extra = found - CANONICAL
    return f"{surface} drifted from CANONICAL_ROLES -- missing: {sorted(missing)}; extra: {sorted(extra)}"


# --- Machine-readable surfaces: exact set-equality (catches missing AND stale) ---


def test_default_models_keys_match_canonical() -> None:
    found = set(DEFAULT_MODELS.keys())
    assert found == CANONICAL, _diff_message("orchestration.DEFAULT_MODELS", found)


def test_role_artifacts_keys_match_canonical() -> None:
    found = set(ROLE_ARTIFACTS.keys())
    assert found == CANONICAL, _diff_message("artifacts.ROLE_ARTIFACTS", found)


def test_role_phase_aliases_keys_match_canonical() -> None:
    found = set(ROLE_PHASE_ALIASES.keys())
    assert found == CANONICAL, _diff_message("artifacts.ROLE_PHASE_ALIASES", found)


def test_allowlist_models_keys_match_canonical() -> None:
    allowlist = json.loads(
        (_repo_root() / ".ai" / "allowlist.json").read_text(encoding="utf-8")
    )
    found = set(allowlist.get("models", {}).keys())
    assert found == CANONICAL, _diff_message(".ai/allowlist.json models", found)


def test_allowlist_schema_models_enum_matches_canonical() -> None:
    schema = json.loads(
        (_repo_root() / ".ai" / "schemas" / "allowlist.schema.json").read_text(
            encoding="utf-8"
        )
    )
    enum = schema["properties"]["models"]["propertyNames"]["enum"]
    found = set(enum)
    assert found == CANONICAL, _diff_message(
        ".ai/schemas/allowlist.schema.json models enum", found
    )


def test_validate_quest_state_required_roles_match_canonical() -> None:
    text = (_repo_root() / "scripts" / "quest_validate-quest-state.sh").read_text(
        encoding="utf-8"
    )
    # Collect quoted tokens from both `required_roles=(...)` and `required_roles+=(...)` lines.
    found: set[str] = set()
    for line in text.splitlines():
        if re.match(r"\s*(local\s+)?required_roles(\+)?=\(", line):
            found.update(re.findall(r'"([^"]+)"', line))
    assert found == CANONICAL, _diff_message(
        "quest_validate-quest-state.sh required_roles (base + workflow)", found
    )


# --- Subset surfaces: intentionally partial, so assert no stale/typo'd entries ---


def test_solo_unused_roles_subset_of_canonical() -> None:
    extra = set(SOLO_UNUSED_ROLES) - CANONICAL
    assert (
        not extra
    ), f"orchestration.SOLO_UNUSED_ROLES has non-canonical roles: {sorted(extra)}"


def test_solo_disabled_agents_subset_of_canonical() -> None:
    extra = set(SOLO_DISABLED_AGENTS) - CANONICAL
    assert (
        not extra
    ), f"artifacts.SOLO_DISABLED_AGENTS has non-canonical roles: {sorted(extra)}"


# --- Prose surfaces: presence-only (catches "new role never documented") ---


def test_skill_md_documents_every_role() -> None:
    text = (_repo_root() / ".skills" / "quest" / "SKILL.md").read_text(encoding="utf-8")
    missing = sorted(role for role in CANONICAL_ROLES if role not in text)
    assert not missing, f".skills/quest/SKILL.md does not mention role(s): {missing}"


def test_workflow_md_documents_every_role() -> None:
    text = (
        _repo_root() / ".skills" / "quest" / "delegation" / "workflow.md"
    ).read_text(encoding="utf-8")
    missing = sorted(role for role in CANONICAL_ROLES if role not in text)
    assert (
        not missing
    ), f".skills/quest/delegation/workflow.md does not mention role(s): {missing}"
