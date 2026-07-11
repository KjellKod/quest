"""Static guardrails for Codex-led Quest role dispatch instructions."""

from __future__ import annotations

import json
import re
from pathlib import Path


FORBIDDEN_CODEX_MCP_TERMS = (
    "codex mcp",
    "mcp__codex",
    "codex_codex",
    "codex mcp-server",
)

CODEX_FACING_PATHS = (
    ".skills/quest/delegation/workflow.md",
    ".skills/gpt/SKILL.md",
    ".skills/SKILLS.md",
    ".agents/skills/quest/SKILL.md",
    ".codex/AGENTS.md",
    ".opencode/agents/quest.md",
)

# Markers that a paragraph positively routes Codex roles/models somewhere.
# Used by the unscoped-routing check: such a paragraph that also names an MCP
# term must be explicitly scoped to Claude-led sessions or phrased as a
# prohibition — otherwise it silently re-opens the Codex-led MCP path even
# without any "Codex-led" wording (e.g. "Codex-backed model names use the
# codex_codex MCP tool").
CODEX_ROLE_ROUTING_MARKERS = (
    "codex-backed",
    "codex backed",
    "codex role",
    "codex roles",
    "codex runtime",
    "role to codex",
    "roles to codex",
    "assigned to codex",
)

CLAUDE_LED_SCOPE_MARKERS = (
    "claude-led",
    "claude led",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _role_docs() -> tuple[Path, ...]:
    root = _repo_root()
    return tuple(
        path.relative_to(root)
        for path in sorted((root / ".skills" / "quest" / "agents").glob("*.md"))
    )


def _opencode_agent_docs() -> tuple[Path, ...]:
    root = _repo_root()
    return tuple(
        path.relative_to(root)
        for path in sorted((root / ".opencode" / "agents").glob("*.md"))
    )


def _read(relative_path: str | Path) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def _paragraphs(content: str) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", content)
        if paragraph.strip()
    ]


def _has_forbidden_term(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in FORBIDDEN_CODEX_MCP_TERMS)


def _looks_like_codex_led_codex_context(text: str) -> bool:
    lowered = text.lower()
    codex_led = any(
        marker in lowered
        for marker in (
            "codex-led",
            "codex led",
            "already codex",
            "from codex",
        )
    )
    codex_role = any(
        marker in lowered
        for marker in (
            "codex-led + codex",
            "codex led + codex",
            "codex-led/codex",
            "codex led/codex",
            "codex role",
            "codex roles",
            "codex runtime role",
            "codex runtime",
            "assigned to codex",
        )
    )
    return codex_led and codex_role


def _allows_or_prohibits_mcp(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "do not use",
            "do not probe",
            "do not call",
            "do not probe, call",
            "not use",
            "never use",
            "only for claude-led",
            "only from claude-led",
            "for claude-led",
            "claude-led entrypoint only",
            "only the cross-runtime path when the orchestrator is claude-led",
            "orchestration violation",
            "not this entrypoint",
            "instead of the mcp",
        )
    )


def _assert_no_positive_codex_led_mcp_dispatch(relative_path: str | Path) -> None:
    content = _read(relative_path)
    for paragraph in _paragraphs(content):
        if not _has_forbidden_term(paragraph):
            continue
        if not _looks_like_codex_led_codex_context(paragraph):
            continue
        assert _allows_or_prohibits_mcp(paragraph), (
            f"{relative_path} appears to allow Codex-led Codex-role MCP dispatch:\n"
            f"{paragraph}"
        )


def _assert_text_allows_no_positive_codex_led_mcp_dispatch(text: str) -> None:
    for paragraph in _paragraphs(text):
        if not _has_forbidden_term(paragraph):
            continue
        if not _looks_like_codex_led_codex_context(paragraph):
            continue
        assert _allows_or_prohibits_mcp(paragraph), paragraph


def _routes_codex_roles(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in CODEX_ROLE_ROUTING_MARKERS)


def _is_claude_led_scoped_or_prohibited(text: str) -> bool:
    lowered = text.lower()
    if any(marker in lowered for marker in CLAUDE_LED_SCOPE_MARKERS):
        return True
    return _allows_or_prohibits_mcp(text)


def _assert_codex_role_mcp_routing_is_scoped(text: str, *, source: str) -> None:
    for paragraph in _paragraphs(text):
        if not _has_forbidden_term(paragraph):
            continue
        if not _routes_codex_roles(paragraph):
            continue
        assert _is_claude_led_scoped_or_prohibited(paragraph), (
            f"{source} routes Codex roles to an MCP entrypoint without "
            f"scoping it to Claude-led sessions:\n{paragraph}"
        )


def _tool_line(content: str, heading: str | None = None) -> str:
    if heading is None:
        match = re.search(r"^- \*\*Tool:\*\* .*$", content, re.M)
        if match is not None:
            return match.group(0)
        section_match = re.search(r"^## Tool\s*\n(?P<tool>[^\n]+)", content, re.M)
        assert section_match is not None
        return section_match.group("tool")

    section = content.split(heading, 1)
    assert len(section) == 2, f"missing heading: {heading}"
    match = re.search(r"^- \*\*Tool:\*\* .*$", section[1], re.M)
    assert match is not None, f"missing Tool line after {heading}"
    return match.group(0)


def test_dispatch_matrix_documents_runtime_entrypoint_split() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")

    assert "Quest dispatch separates **runtime** from **entrypoint**" in workflow
    assert "`models.*` stores model IDs, not runtime names" in workflow
    assert (
        "`runtime_for_model()` in `scripts/quest_runtime/orchestration.py`" in workflow
    )


def test_claude_led_unavailable_preflight_requires_human_routing_decision() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")
    clause = workflow.split("**Claude-led sessions:**", 1)[1].split(
        "**Codex-led sessions:**", 1
    )[0]

    assert "pause" in clause.lower()
    assert "fix" in clause.lower() and "rerun preflight" in clause.lower()
    assert "continue Claude-only" in clause
    assert "cancel" in clause.lower()
    assert "still assigns an active role to Codex" in clause
    assert "do not prompt again" in clause
    assert "using Claude runtime fallback for all roles" not in clause
    assert "| Codex-led | Codex | local Codex subagent" in workflow
    assert "| Codex-led | Claude | `python3 scripts/quest_claude_runner.py`" in workflow
    assert "| Claude-led | Codex | Codex MCP" in workflow
    assert "| Claude-led | Claude | native `Task(...)`" in workflow
    assert (
        "entrypoint violation, not a model-selection or model/account failure"
        in workflow
    )


def test_workflow_documents_bg_transport_model_and_resume_contracts() -> None:
    workflow = _read(".skills/quest/delegation/workflow.md")

    assert "--model <models.<role> from .quest/<id>/orchestration.json>" in workflow
    assert "must not be sent to the CLI as `--model claude`" in workflow
    assert "python3 scripts/claude_bg_run.py --sweep quest-bg-probe-" in workflow
    assert (
        "python3 scripts/quest_claude_probe.py --model claude --transport background-agent"
        in workflow
    )
    assert "--resume <session_id> --answer-file <answer_file>" in workflow
    # The resume example must be runnable as written: the runner requires the
    # full role-argument set, and a fresh re-dispatch must never silently kill
    # a parked session.
    assert (
        "python3 scripts/quest_claude_runner.py --quest-dir .quest/<id> --phase <phase> "
        "--agent <role> --iter <n> --prompt-file" in workflow
    )
    assert (
        "Parked-session guard (before ANY fresh retry/re-dispatch of a role)"
        in workflow
    )
    assert "Persist the parked session id in `.quest/<id>/state.json`" in workflow
    assert '"parked_bg_session"' in workflow
    # The state helper must be the documented persistence path (never a
    # hand-edit of state.json), and clearing must be documented too.
    assert (
        "scripts/quest_state.py --quest-dir .quest/<id> --parked-bg-session" in workflow
    )
    assert "--clear-parked-bg-session" in workflow
    assert "Cap repeated questions" in workflow  # anchor, not exact prose
    assert (
        "For abandon/manual cleanup, run `python3 scripts/claude_bg_run.py --sweep quest-<id>-`"
        in workflow
    )
    assert "**`rate_limited`:** Do NOT blind retry" in workflow
    assert "Surface `reset_at` when present" in workflow
    assert "**`startup_dialog`:** Do NOT retry" in workflow
    assert "trust/bypass" in workflow  # anchor, not exact prose
    assert "**`model_rejected`:** Do NOT retry" in workflow
    assert "`rejected_model`" in workflow  # anchor, not exact prose
    # The human must be told WHERE to change the model, a leaked session must
    # never ride silently on success, and a cold restart must re-present a
    # parked role's pending questions before any other routing.
    assert "`models.<role>` in `.quest/<id>/orchestration.json`" in workflow
    assert "**`teardown_failed` (any status, including success):**" in workflow
    assert "Parked-session check (cold restart)" in workflow


def test_gpt_skill_excludes_codex_led_quest_dispatch() -> None:
    skill = _read(".skills/gpt/SKILL.md")

    assert "Not for Codex-Led Quest Role Dispatch" in skill
    assert "If you are already Codex" in skill
    assert "use local Codex subagents" in skill
    assert "inherit the active Codex model" in skill
    assert (
        "Codex MCP is only the cross-runtime path when the orchestrator is Claude-led"
        in skill
    )


def test_skills_index_scopes_gpt_to_claude_led_dispatch() -> None:
    index = _read(".skills/SKILLS.md")

    assert "a Claude-led Quest workflow routes a role to Codex" in index
    assert "or Quest routes a role to Codex" not in index
    assert "**Not for:** Codex-led Quest role dispatch" in index
    assert "use local Codex subagents" in index
    assert "Codex MCP is only for Claude-led dispatch to Codex" in index


def test_codex_wrapper_and_entrypoint_point_at_canonical_matrix() -> None:
    """Wrappers (.agents, .codex) stay thin: a one-line rule plus a pointer to
    the canonical dispatch matrix. They must not restate the matrix — the
    canonical content lives in .skills/quest/delegation/workflow.md only."""
    for relative_path in (
        ".agents/skills/quest/SKILL.md",
        ".codex/AGENTS.md",
    ):
        content = _read(relative_path)
        assert "local Codex subagents" in content
        assert "never use Codex MCP" in content
        assert ".skills/quest/delegation/workflow.md" in content
        assert (
            "single source of truth" in content
            or "intentionally does not restate" in content
        )
        # Restated matrix details belong only in the canonical doc.
        assert "multi_agent_v1.spawn_agent" not in content
        assert "inherit the active Codex model" not in content

    wrapper = _read(".agents/skills/quest/SKILL.md")
    assert "Read and follow the instructions in `.skills/quest/SKILL.md`." in wrapper


def test_role_docs_point_at_canonical_dispatch_matrix() -> None:
    """Role docs reference the canonical matrix instead of restating it — one
    source of truth in .skills/quest/delegation/workflow.md."""
    for relative_path in _role_docs():
        if relative_path.name == "README.md":
            continue
        content = _read(relative_path)
        assert ".skills/quest/delegation/workflow.md" in content, relative_path
        assert "canonical dispatch matrix" in content, relative_path
        # The matrix prose must not be duplicated into role docs.
        assert "multi_agent_v1.spawn_agent" not in content, relative_path


def test_needs_human_policy_is_runtime_based_not_slot_based() -> None:
    """Slots are runtime-configurable, so the non-interactive contract must key
    on the selected runtime — slot-label wording lets a Codex-assigned slot A
    return `needs_human` in violation of the Codex non-interactive policy."""
    reviewer_docs = (
        ".skills/quest/agents/plan-reviewer.md",
        ".skills/quest/agents/code-reviewer.md",
    )
    for relative_path in reviewer_docs:
        content = _read(relative_path)
        assert "For Reviewer B, `STATUS: needs_human` is non-compliant" not in content
        assert "For Reviewer A, `STATUS: needs_human` remains valid" not in content
        assert "### Non-Interactive Rule (Runtime-Based)" in content
        assert "not the slot label" in content
        assert "only valid when your slot's selected runtime is Claude" in content

    arbiter_docs = {
        ".skills/quest/agents/arbiter.md": "models.arbiter",
        ".skills/quest/agents/review-arbiter.md": "models.review-arbiter",
    }
    for relative_path, model_key in arbiter_docs.items():
        content = _read(relative_path)
        assert "only valid when this role's selected runtime" in content
        assert model_key in content


def test_configurable_reviewer_and_arbiter_tool_lines_use_runtime_matrix() -> None:
    expected = {
        ".skills/quest/agents/plan-reviewer.md": (
            ("### Plan Reviewer A", "models.plan-reviewer-a"),
            ("### Plan Reviewer B", "models.plan-reviewer-b"),
        ),
        ".skills/quest/agents/code-reviewer.md": (
            ("### Code Reviewer A", "models.code-reviewer-a"),
            ("### Code Reviewer B", "models.code-reviewer-b"),
        ),
    }

    for relative_path, slot_expectations in expected.items():
        content = _read(relative_path)
        for heading, model_key in slot_expectations:
            tool_line = _tool_line(content, heading)
            assert model_key in tool_line
            assert ".quest/<id>/orchestration.json" in tool_line
            assert ".skills/quest/delegation/workflow.md" in tool_line
            assert "canonical dispatch matrix" in tool_line

    arbiter_tool_line = _tool_line(_read(".skills/quest/agents/arbiter.md"))
    assert "models.arbiter" in arbiter_tool_line
    assert ".quest/<id>/orchestration.json" in arbiter_tool_line
    assert ".skills/quest/delegation/workflow.md" in arbiter_tool_line
    assert "canonical dispatch matrix" in arbiter_tool_line


def test_positive_codex_mcp_dispatch_examples_are_rejected() -> None:
    positive_regressions = (
        "Codex-led Quest Codex runtime roles use Codex MCP.",
        "When this Quest is Codex-led and a role is assigned to Codex, dispatch it through Codex MCP.",
        "Codex-led + Codex -> use mcp__codex-cli__codex.",
    )

    for text in positive_regressions:
        try:
            _assert_text_allows_no_positive_codex_led_mcp_dispatch(text)
        except AssertionError:
            continue
        raise AssertionError(f"positive Codex MCP dispatch was allowed: {text}")


def test_negative_prohibitions_and_claude_led_mcp_docs_are_allowed() -> None:
    allowed_examples = (
        "Codex-led Quest Codex runtime roles do not use Codex MCP.",
        "Codex-led + Codex -> never use mcp__codex-cli__codex.",
        "Claude-led + Codex runtime uses Codex MCP.",
    )

    for text in allowed_examples:
        _assert_text_allows_no_positive_codex_led_mcp_dispatch(text)


def test_codex_facing_docs_do_not_allow_positive_codex_led_mcp_dispatch() -> None:
    for relative_path in (*CODEX_FACING_PATHS, *_role_docs(), *_opencode_agent_docs()):
        _assert_no_positive_codex_led_mcp_dispatch(relative_path)


def test_codex_role_mcp_routing_requires_claude_led_scope() -> None:
    for relative_path in (*CODEX_FACING_PATHS, *_role_docs(), *_opencode_agent_docs()):
        _assert_codex_role_mcp_routing_is_scoped(
            _read(relative_path), source=str(relative_path)
        )


def test_unscoped_codex_role_mcp_routing_examples_are_rejected() -> None:
    rejected_examples = (
        "Codex-backed model names use the `codex_codex` MCP tool.",
        "Codex roles dispatch through mcp__codex-cli__codex.",
        "If a role is assigned to Codex, call codex mcp-server.",
    )

    for text in rejected_examples:
        try:
            _assert_codex_role_mcp_routing_is_scoped(text, source="example")
        except AssertionError:
            continue
        raise AssertionError(f"unscoped Codex role MCP routing was allowed: {text}")


def test_scoped_or_prohibited_codex_role_mcp_routing_examples_are_allowed() -> None:
    allowed_examples = (
        "In Claude-led sessions, Codex-backed model names use the codex_codex MCP tool.",
        "Do not use codex_codex for Codex-led Codex roles.",
        "Codex MCP is only for Claude-led dispatch of Codex roles.",
    )

    for text in allowed_examples:
        _assert_codex_role_mcp_routing_is_scoped(text, source="example")


def test_opencode_agent_descriptions_do_not_advertise_mcp_dispatch() -> None:
    """Agent descriptions in opencode.json are an orchestrator-visible routing
    surface. "Codex via MCP"-style wording there steers Codex roles back toward
    MCP even when the agent is wired as a local subagent, and the adjacency-based
    forbidden terms (e.g. "codex mcp") do not catch it — so descriptions must
    not mention MCP at all. The `mcp` server registration block is exempt: it
    exists for the Claude-led cross-runtime path, not role routing."""
    config = json.loads(_read(".opencode/opencode.json"))

    agents = config.get("agent", {})
    assert agents, ".opencode/opencode.json defines no agents"
    for agent_name, agent in agents.items():
        description = str(agent.get("description", ""))
        assert "mcp" not in description.lower(), (
            f".opencode/opencode.json agent '{agent_name}' description "
            f"advertises an MCP transport: {description}"
        )


def test_opencode_quest_doc_scopes_codex_mcp_to_claude_led_sessions() -> None:
    content = _read(".opencode/agents/quest.md")

    assert (
        "canonical dispatch matrix in `.skills/quest/delegation/workflow.md`" in content
    )
    assert "local `task` subagent" in content
    assert "orchestration violation" in content
    assert "Codex-backed model names use the `codex_codex` MCP tool" not in content


def test_codex_facing_docs_do_not_dispatch_codex_roles_with_cli_model_aliases() -> None:
    quest_surfaces = (
        ".skills/quest/delegation/workflow.md",
        ".agents/skills/quest/SKILL.md",
        ".codex/AGENTS.md",
        *_role_docs(),
    )

    positive_alias_patterns = (
        re.compile(r"codex(?:-led)?[^.\n]{0,120}codex[^.\n]{0,120}codex exec -m", re.I),
        re.compile(
            r"codex(?:-led)?[^.\n]{0,120}codex[^.\n]{0,120}model:\s*[\"']gpt-", re.I
        ),
        re.compile(r"codex(?:-led)?[^.\n]{0,120}codex[^.\n]{0,120}use\s+gpt-\d", re.I),
    )

    for relative_path in quest_surfaces:
        content = _read(relative_path)
        for pattern in positive_alias_patterns:
            assert not pattern.search(content), (
                f"{relative_path} appears to dispatch Codex-led Codex roles with "
                "a Codex CLI/model alias"
            )
