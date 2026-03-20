# Quest Orchestration

A quest is a structured workflow for completing a non-trivial task using coordinated AI agents with human approval gates.

## Quick Reference

- **Allowlist:** `.ai/allowlist.json` (edit to control permissions)
- **Run state:** `.quest/<quest_id>/` (ephemeral, gitignored)
- **Skill:** `.skills/quest/SKILL.md`

## Usage

Use the `/quest` command in Claude Code:

```
# New quest — describe what you want
/quest "Add a loading skeleton to the candidate list"

# Point to a spec, PRD, or RFC
/quest "implement docs/specs/feature-x.md"

# Continue an existing quest (auto-detects next phase)
/quest feature-x_2026-02-02__1831

# Continue with instruction
/quest feature-x_2026-02-02__1831 "now review the code"

# Utility
/quest status
/quest allowlist
```

The Quest Agent interprets your intent, matches brief references, and routes to the right phase. If unclear, it asks you — reply in plain English.

**Input quality matters.** Your quest input is the spec. A rough idea works (Quest asks clarifying questions), but providing intent, constraints, and acceptance criteria upfront produces tighter plans with fewer iterations. See the README for examples at each level.

## Roles

| Role | File | Tool | Purpose |
|------|------|------|---------|
| Quest Agent | (Claude Code itself) | Claude Opus (`opus`) | Orchestration, gating |
| Planner | `.skills/quest/agents/planner.md` | Claude runtime (`Task(...)` natively, bridge in Codex-led runs) | Write and refine plan artifacts |
| Plan Reviewer (Claude) | `.skills/quest/agents/plan-reviewer.md` | Claude runtime (`Task(...)` natively, bridge in Codex-led runs) | Review plans (read-only) |
| Plan Reviewer (Codex) | `.skills/quest/agents/plan-reviewer.md` | Codex (`gpt-5.4`) | Review plans (read-only) |
| Arbiter | `.skills/quest/agents/arbiter.md` | Claude runtime (`Task(...)` natively, bridge in Codex-led runs) | Synthesize reviews, approve or iterate |
| Builder | `.skills/quest/agents/builder.md` | Codex (`gpt-5.4`) by default; Claude runtime fallback | Implement changes |
| Code Reviewer (Claude) | `.skills/quest/agents/code-reviewer.md` | Claude runtime (`Task(...)` natively, bridge in Codex-led runs) | Review code (read-only) |
| Code Reviewer (Codex) | `.skills/quest/agents/code-reviewer.md` | Codex (`gpt-5.4`) | Review code (read-only) |
| Fixer | `.skills/quest/agents/fixer.md` | Codex (`gpt-5.4`) by default; Claude runtime fallback | Fix review issues |

## Plan Phase Flow

```
Planner -> [Review Claude + Review Codex] -> Arbiter -> approve? -> Builder
                                                  \-> iterate? -> Planner (loop)
```

The Arbiter is the gatekeeper. It enforces KISS, YAGNI, SRP. It prevents nitpick spin. The Planner only sees the Arbiter's synthesized feedback, not raw reviews.

Max iterations controlled by `gates.max_plan_iterations` in allowlist.

## Full Flow

```
Intake -> Plan -> [Dual Review + Arbiter Loop] -> [Gate] -> Implement -> Code Review -> [Fix Loop] -> [Gate] -> Done
```

Codex runtime policy for Quest:
- Codex roles run non-interactive (`no questions`, `no needs_human`).
- If a Codex role cannot comply, Quest retries once with explicit-assumption guidance, then falls back to the equivalent Claude role.
- Human Q&A is used only when the Claude path returns `needs_human`.

Codex-led Quest note:
- In a Codex-orchestrated session, Claude-designated roles run through the supported local bridge runtime, using `scripts/quest_claude_runner.py` as the orchestration entrypoint and `scripts/claude_cli_bridge.py` as the transport layer.
- Native Claude-led Quest behavior is unchanged: Claude-designated roles still use native `Task(...)` execution when the orchestrator supports it.
- The preferred helpers for Codex-led Claude slots are `scripts/quest_claude_probe.py` for bridge preflight and `scripts/quest_claude_runner.py` for real role execution; the runner uses `bypassPermissions`, adds explicit repo/quest access via `--add-dir`, polls `handoff.json`, and updates `context_health.log`.
- The workflow now probes bridge availability once per session, routes Claude-designated slots by selected model/runtime, and logs bridge-invoked Claude roles as `runtime=claude`.
- Bridge failures are explicit: timeout retries once, CLI/auth failures block immediately, and malformed output/missing handoff retries once before text fallback or blocking.

## Artifact Preparation and Runtime Fallbacks

### Workspace-Local Quest Paths

All Quest-owned artifacts default to `<repo>/.quest/<quest_id>/...`. This keeps artifacts within the workspace root for all runtimes, avoiding sandbox write-boundary issues.

Use `default_quest_dir(workspace_root, quest_id)` from `quest_runtime.artifacts` to resolve the canonical path.

### Artifact Preparation Invariant

Before each role invocation, the orchestrator prepares that role's expected artifact files:
1. Resolve paths via `expected_artifacts_for_role(quest_dir, phase, agent)`
2. Create directories and truncate files via `prepare_artifact_files(paths)`
3. Instruct the agent to overwrite the prepared files directly (no shell redirection or heredocs)

This is runtime-neutral — the same preparation runs whether the orchestrator is Claude or Codex.

### Fallback Ladder

When a role invocation fails (missing/unparsable handoff), Quest uses a three-tier retry strategy:

- **Tier A — Normal run:** Configured runtime/model, normal permissions, with artifact preparation.
- **Tier B — Permission/transport retry (same runtime, same model):** Triggered only for `write_boundary` or `permission` failures. Codex: escalate from `workspace-write` to `danger-full-access` only when the user has explicitly approved that broader access or an equivalent persisted approval exists. Claude bridge: add out-of-workspace dirs via `--add-dir`. Native Claude: widen tool permissions.
- **Tier C — Cross-runtime fallback:** Triggered when Tier B is exhausted or the failure is non-write-boundary (timeout, model failure, invocation error). Codex slots fall back to Claude; Claude bridge slots fall back to Codex.

`danger-full-access` is never set automatically. Escalation is explicit and exceptional.

### Failure Classification

`classify_failure_kind` in `quest_runtime.claude_runner` routes failures:
- `timeout` — process timed out
- `invocation` — CLI/auth/environment error
- `write_boundary` — artifacts missing/empty AND paths are out-of-workspace
- `permission` — stderr contains permission-denied signals
- `model` — reasoning/compliance failure (default)

## Allowlist

The Creator controls quest permissions via `.ai/allowlist.json`:
- `auto_approve_phases` — which phases need human approval
- `models` — default role model map (`planner`, `plan-reviewer-a`, `plan-reviewer-b`, `builder`, `code-reviewer-a`, `code-reviewer-b`, `arbiter`, `fixer`)
- `review_mode` — `auto` (default), `fast`, or `full` for Codex reviews
- `fast_review_thresholds` — file/LOC thresholds for auto fast mode

- `role_permissions` — per-role file and bash access
- `gates` — commit/push/delete always require approval by default

Edit the file directly. Changes take effect on next quest run.

## Setup

See `docs/guides/quest_setup.md` for setup instructions when porting to a new repository.
