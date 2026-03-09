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
| Planner | `.skills/quest/agents/planner.md` | Claude Opus (`opus`) | Write and refine plan artifacts |
| Plan Reviewer (Claude) | `.skills/quest/agents/plan-reviewer.md` | Claude Opus (`opus`) | Review plans (read-only) |
| Plan Reviewer (Codex) | `.skills/quest/agents/plan-reviewer.md` | Codex (`gpt-5.3-codex`) | Review plans (read-only) |
| Arbiter | `.skills/quest/agents/arbiter.md` | Claude Opus (`opus`) | Synthesize reviews, approve or iterate |
| Builder | `.skills/quest/agents/builder.md` | Codex (`gpt-5.3-codex`) by default; Claude fallback | Implement changes |
| Code Reviewer (Claude) | `.skills/quest/agents/code-reviewer.md` | Claude Opus (`opus`) | Review code (read-only) |
| Code Reviewer (Codex) | `.skills/quest/agents/code-reviewer.md` | Codex (`gpt-5.3-codex`) | Review code (read-only) |
| Fixer | `.skills/quest/agents/fixer.md` | Codex (`gpt-5.3-codex`) by default; Claude fallback | Fix review issues |

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

## Allowlist

The Creator controls quest permissions via `.ai/allowlist.json`:
- `auto_approve_phases` — which phases need human approval
- `arbiter.tool` — Arbiter model (`claude` by default)
- `model_overrides` — default role model map (`planner`, `plan-reviewer-a`, `plan-reviewer-b`, `builder`, `code-reviewer-a`, `code-reviewer-b`, `arbiter`, `fixer`)
- `review_mode` — `auto` (default), `fast`, or `full` for Codex reviews
- `fast_review_thresholds` — file/LOC thresholds for auto fast mode

- `role_permissions` — per-role file and bash access
- `gates` — commit/push/delete always require approval by default

Edit the file directly. Changes take effect on next quest run.

## Setup

See `docs/guides/quest_setup.md` for setup instructions when porting to a new repository.
