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


def test_human_replan_entry_points_share_one_documented_contract() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")
    exact_commands = (
        "python3 scripts/quest_plan_iteration.py snapshot --quest-dir .quest/<id> --iteration <N>",
        "python3 scripts/quest_state.py --quest-dir .quest/<id> --record-user-replan-feedback",
        "python3 scripts/quest_state.py --quest-dir .quest/<id> --transition plan --status in_progress --expect-phase <current>",
    )
    for command in exact_commands:
        assert command in workflow
    for source in ("walkthrough", "sharpen", "build_gate", "resume_instruction"):
        assert source in workflow

    assert "## Change Request (Iteration <N+1>)" in workflow
    assert "## Sharpen Outcome (Iteration <N+1>)" in workflow
    assert "### Resolved" in workflow
    assert "### Open" in workflow
    assert "### Next" in workflow
    assert "The human path deliberately does not call `cleanup-current`" in workflow
    assert "Current-generation identity checks prevent old handoffs" in workflow
    assert workflow.index(exact_commands[0]) < workflow.index(exact_commands[1])
    assert workflow.index(exact_commands[1]) < workflow.index(exact_commands[2])


def test_plan_role_dispatches_inject_resolved_current_identity() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")
    identity = (
        "Current plan identity: plan_iteration=<resolved integer>; "
        "user_replan_generation=<resolved integer|null>"
    )

    assert workflow.count(identity) >= 5
    assert (
        "Current plan identity: `plan_iteration=<resolved integer>; "
        "user_replan_generation=<resolved integer|null>`"
    ) in workflow
    assert "with actual JSON values, not expressions or example values" in workflow
    for role in ("planner.md", "plan-reviewer.md", "arbiter.md"):
        text = _read(f".skills/quest/agents/{role}")
        assert "state.json.plan_iteration" in text
        assert "state.json.user_replan.generation" in text
        assert "Do not copy the literal example values below" in text


def test_plan_roles_enforce_the_same_clear_value_scope_gate() -> None:
    role_paths = (
        ".skills/quest/agents/planner.md",
        ".skills/quest/agents/plan-reviewer.md",
        ".skills/quest/agents/arbiter.md",
    )
    required_phrases = (
        "## Scope and Value Gate",
        "KISS, YAGNI, SRP, and DRY",
        "clear, concrete value",
        "speculative future-proofing",
        "nice-to-haves",
        "leave it out",
    )

    for role_path in role_paths:
        role_text = _read(role_path)
        missing = [phrase for phrase in required_phrases if phrase not in role_text]
        assert not missing, f"{role_path} is missing scope gate language: {missing}"


def test_refinement_bug_report_separates_fact_from_unconfirmed_loss() -> None:
    report = _read(
        "ideas/2026-08-04-bug-reporting-automatic-plan-refinement-feedback-loss.md"
    )
    assert "## Confirmed Trigger" in report
    assert "## Unconfirmed Broader Loss" in report
    assert report.index("## Confirmed Trigger") < report.index(
        "## Unconfirmed Broader Loss"
    )


def test_approval_configurations_keep_presentation_mandatory() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")
    for setting in (
        "plan_creation",
        "plan_review",
        "plan_refinement",
        "implementation",
    ):
        assert f"auto_approve_phases.{setting}" in workflow
    assert "Interactive Plan Presentation (MANDATORY HUMAN GATE)" in workflow
    assert (
        'If false (default): You MUST ask the user "Plan approved. Proceed with implementation?"'
        in workflow
    )
    assert "If true: You may proceed without asking" in workflow


def test_solo_automatic_refinement_has_an_explicit_workflow_only_free_order() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")
    solo_start = workflow.index(
        "In solo mode, Reviewer A's typed `next: planner` decision"
    )
    solo_end = workflow.index("- **UI work:**", solo_start)
    solo_order = workflow[solo_start:solo_end]

    assert "snapshot --quest-dir .quest/<id> --iteration <N>" in solo_order
    assert "cleanup-current --quest-dir .quest/<id> --iteration <N>" in solo_order
    assert "Increment state once from `N` to `N+1`" in solo_order
    assert "Prepare Planner outputs" in solo_order
    assert "Dispatch Planner" in solo_order
    assert "skips `publish-refinement` and `verify-refinement`" in solo_order
    assert "never requires Arbiter artifacts" in solo_order


def test_artifact_preparation_docs_use_the_required_keyword_context() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")
    quest_docs = _read(".ai/quest.md")
    call = "prepare_artifact_files(paths, quest_dir=quest_dir, role=agent)"

    assert call in workflow
    assert call in quest_docs
    assert "prepare_artifact_files(paths)`" not in workflow
    assert "sealed immediate predecessor" in workflow
    assert "sealed immediate predecessor" in quest_docs
