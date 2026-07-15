"""Source-only tests for active Quest documentation contracts."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


# Completed transport specs live in docs/implementation/history/ — history is
# a preserved record, deliberately NOT enforced by these accuracy contracts.
ACTIVE_DOCS = (
    "README.md",
    "scripts/README.md",
    "docs/guides/quest_setup.md",
    "docs/guides/quest_presentation.md",
    ".skills/quest/delegation/workflow.md",
)


def test_active_docs_do_not_claim_unprobed_claude_management_commands() -> None:
    forbidden = (
        "On 2.1.191, `claude logs <id>`",
        "On 2.1.191, `claude stop <id>`",
        "`claude stop <id>` (if alive)",
        "capture `claude logs <id>`",
        "issuing `claude stop <id>`",
    )

    for doc in ACTIVE_DOCS:
        text = _read(doc)
        for phrase in forbidden:
            assert phrase not in text, f"{doc} contains stale command claim: {phrase}"


def test_user_facing_docs_explain_transport_pair_and_runner() -> None:
    combined = "\n".join(
        _read(path)
        for path in (
            "README.md",
            "scripts/README.md",
            "docs/guides/quest_setup.md",
        )
    )

    assert "scripts/claude_bg_run.py" in combined
    assert "background-agent" in combined
    assert "bridge" in combined
    assert "subscription" in combined
    assert "API-metered" in combined


def test_docs_pin_cross_vendor_resume_from_state_json() -> None:
    readme = _read("README.md")
    setup = _read("docs/guides/quest_setup.md")
    combined = f"{readme}\n{setup}"

    assert "$quest <quest-id>" in combined
    assert "/quest <quest-id>" in combined
    assert ".quest/<id>/state.json" in combined
    assert "Cross-vendor resume" in readme


def test_docs_state_artifact_driven_orchestration_principle() -> None:
    readme = _read("README.md")
    workflow = _read(".skills/quest/delegation/workflow.md")

    assert "artifact-driven" in readme
    assert "not chat-history driven" in readme
    assert "state.json" in workflow
    assert "handoff.json" in workflow


def test_setup_guide_documents_current_model_and_transport_contracts() -> None:
    setup = _read("docs/guides/quest_setup.md")

    required_terms = (
        "models.<role>",
        ".ai/allowlist.json",
        ".quest/<id>/orchestration.json",
        "claude_role_transport",
        "auto",
        "background-agent",
        "bridge",
        "scripts/quest_preflight.sh --orchestrator claude",
        "scripts/quest_preflight.sh --orchestrator codex",
    )
    for term in required_terms:
        assert term in setup, f"setup guide is missing current contract term: {term}"

    model_config_row = next(
        line for line in setup.splitlines() if line.startswith("| `models.<role>` |")
    )
    for role in (
        "planner",
        "plan-reviewer-a",
        "plan-reviewer-b",
        "arbiter",
        "builder",
        "code-reviewer-a",
        "code-reviewer-b",
        "review-arbiter",
        "fixer",
    ):
        assert f"`{role}`" in model_config_row

    transport_config_row = next(
        line
        for line in setup.splitlines()
        if line.startswith("| `claude_role_transport` |")
    )
    for policy in ("`auto`", "`background-agent`", "`bridge`"):
        assert policy in transport_config_row

    stale_instructions = (
        "arbiter.tool",
        '"arbiter": {"tool": "codex"}',
        "The plan and code reviewers will also fall back to Claude if Codex is unavailable.",
        "The system falls back to Claude if Codex fails",
    )
    for instruction in stale_instructions:
        assert (
            instruction not in setup
        ), f"setup guide contains obsolete runtime guidance: {instruction}"


def test_docs_contract_scope_excludes_history_and_journal_archives() -> None:
    assert (_repo_root() / "docs" / "quest-journal").exists()
    assert all(not path.startswith("docs/quest-journal/") for path in ACTIVE_DOCS)
    assert all(
        not path.startswith("docs/implementation/history/") for path in ACTIVE_DOCS
    )
