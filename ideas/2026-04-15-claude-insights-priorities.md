---
title: Claude Insights Priorities (2026-04-15)
purpose: Canonical priority index translating evaluation suggestions into Quest-specific, sanity-checked proposals and explicit skips.
audience:
  - quest-developers
  - quest-users
scope: Prioritization and coverage map for Claude insights follow-up ideas.
status: proposed
owner: kjell
---

## Context
The source evaluation spans 1,542 messages across 97 sessions (2026-03-16 to 2026-04-15). Top friction counts are `Wrong Approach (55)`, `Buggy Code (25)`, `Misunderstood Request (21)`, and `Excessive Changes (12)`. The dominant pattern is workspace/branch/path targeting error, so ranking prioritizes controls that reduce wrong-location edits and validation drift before adding heavier automation.

## Problem
The raw evaluation contains many strong suggestions, but without a canonical priority index the recommendations can be implemented out of order, duplicated across policy surfaces, or applied without outside-in compatibility safeguards. That risks solving lower-impact problems first while the primary friction pattern (wrong branch/directory/path) remains unresolved.

## Proposal
Create a single user-authoritative index that preserves tier order, maps each suggestion to a destination proposal, and records required Quest-specific adaptations (non-git fallback, additive hooks, no duplicate skills, existing workflow hardening). This document is the coordination layer for the other eight idea files.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
Inside-repo work benefits from explicit sequencing and ownership boundaries so implementation quests can execute in a stable order and avoid policy drift.

### Outside-in use (Quest invoked from another repo)
Outside-in use needs explicit compatibility annotations (especially `vcs_available == false` handling and repo-specific PR/CI variability), which this index centralizes.

### Conflicts and Required Adaptations
Without this index, overlapping governance docs can diverge. This file resolves overlap by pointing each evaluation item to one destination file (or explicit skip reason), then cross-linking canonicals.

## Canonical Priority Ranking (User-Authoritative)
This ordering is the **historical evaluation order** copied from the original quest brief. It is preserved for provenance, not as current actionable guidance — several items have since been retired or shipped. **Current status tags are inline below; do not action a `RETIRED`/`SUPERSEDED`/`DONE` item.**

### Tier 1 — Do this week (highest ROI)
1. ~~**PreToolUse hook for branch/directory verification**~~ — **RETIRED (won't-do, PR #116).** Hook stdout on exit 0 is debug-log-only (invisible) and never fires under Codex/MCP; statusline covers the intent. See [`archive/2026-04-15-pretooluse-branch-dir-verification-hook.md`](archive/2026-04-15-pretooluse-branch-dir-verification-hook.md).
2. ~~**CLAUDE.md rule: confirm `pwd` + `git branch --show-current` before edits**~~ — **RETIRED (won't-do).** Soft prose, no enforcement; superseded by statusline. See [`archive/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md`](archive/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md).
3. **CLAUDE.md rule: never dismiss acceptance criteria** — Zero-effort addition that prevents a recurring, specific failure mode (the `--help timeout` episode, pytest-as-manual-validation, etc.).

### Tier 2 — Do this month (compound returns)
4. **Custom `/pr-create` skill with verification checklist** — 20 PR-management + 18 PR-shepherding sessions; small per-PR wins compound fast. Encodes "verify script names, run documented commands, stage all files."
5. **CLAUDE.md rule: pre-commit `git status` + `git diff --stat`** — Fixes the "forgot to stage `.skills` changes" pattern. Cheap.
6. ~~**CLAUDE.md rule: sub-agent path constraints**~~ — **SUPERSEDED.** `quest_validate-quest-state.sh` already blocks transitions on missing/misplaced canonical artifacts (both runtimes); residual failure-diagnostics belong to `handoff-validation-and-failure-ux`. See [`archive/2026-04-15-subagent-path-constraints-hardening.md`](archive/2026-04-15-subagent-path-constraints-hardening.md).

### Tier 3 — Higher-leverage but more investment
7. **CLAUDE.md rule: cap tool-failure investigation at 2 attempts** — Targets rabbit-holing (#2 friction). Harder to enforce via text rules alone; interrupting early may still work better in practice.
8. **Autonomous PR Shepherd (headless mode)** — Big payoff, but only worth building after Tiers 1–2 harden conventions. Running an autonomous agent on current friction patterns would amplify failures, not reduce them.

### Skip or defer
- **Parallel multi-repo quest orchestration** — Ambitious, but single-repo friction isn't solved yet. Premature.
- **TDD bug-fix agent** — Nice framing, but bug-fix sessions aren't the top pain point; wrong-branch edits are.

## File Pointers
- `ideas/archive/2026-04-15-pretooluse-branch-dir-verification-hook.md` — **WON'T-DO** (built + closed in PR #116; hook stdout is invisible, Codex-blind). Hook-level context visibility before write/edit.
- `ideas/archive/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md` — **WON'T-DO** (retired with the hook). Policy-level pre-edit context confirmation.
- `ideas/2026-04-15-claude-rule-never-dismiss-acceptance-criteria.md` — Completion gate for explicit ACs.
- `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md` — PR checklist via existing `pr-assistant`.
- `ideas/2026-04-15-precommit-status-diffstat-discipline.md` — Staging/diffstat discipline before commit.
- `ideas/archive/2026-04-15-subagent-path-constraints-hardening.md` — **SUPERSEDED** (transition validator already gates misplaced artifacts). Postflight path-compliance hardening for sub-agents.
- `ideas/2026-04-15-tool-failure-two-attempt-cap.md` — Two-attempt investigation cap.
- `ideas/2026-04-15-autonomous-pr-shepherd-headless.md` — Staged headless PR shepherd concept.

## Skip Bucket
- **Parallel multi-repo quest orchestration** — deferred; core single-repo execution discipline issues are still unresolved.
- **TDD bug-fix agent** — deferred; not aligned to top friction source from this evaluation.
- **Batch security scans (evaluation headless example)** — useful pattern, but orthogonal to current Quest workflow priorities; better handled as a standalone scripted workflow, not a Quest idea in this batch.

## Sanity-Check Modifications to Raw Suggestions
- **Hook snippet adaptation:** merge additively into `.claude/settings.json`; do not overwrite existing `SessionStart` and `PostToolUse Write|Edit` audit hooks.
- **`git branch --show-current` adaptation:** degrade safely when `vcs_available == false` by using fallback command behavior.
- **`/pr-create` adaptation:** routed to extending `.skills/pr-assistant/SKILL.md`, not creating a duplicate skill surface.
- **Sub-agent path constraints adaptation:** framed as hardening of existing controls in `.skills/quest/delegation/workflow.md` (`expected_artifacts_for_role`, `prepare_artifact_files`).
- **PostToolUse Bash diff hook adaptation:** flagged as too noisy if global; recommend bounded commit-adjacent usage only.

## Coverage Map
| Evaluation suggestion | Destination |
|---|---|
| CLAUDE.md add: confirm directory+branch before edits | `ideas/archive/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md` (won't-do) |
| Hook: `PreToolUse` branch/dir echo | `ideas/archive/2026-04-15-pretooluse-branch-dir-verification-hook.md` (won't-do) |
| CLAUDE.md add: never dismiss acceptance criteria | `ideas/2026-04-15-claude-rule-never-dismiss-acceptance-criteria.md` |
| CLAUDE.md add: PR descriptions must match real scripts/paths/tests | `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md` |
| Custom skill suggestion: `/pr-create` checklist | `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md` (extension of existing `pr-assistant`) |
| CLAUDE.md add: pre-commit `git status` + `git diff --stat` | `ideas/2026-04-15-precommit-status-diffstat-discipline.md` |
| Hook: `PostToolUse Bash` unstaged-diff print | `ideas/2026-04-15-precommit-status-diffstat-discipline.md` (bounded/noise-controlled adaptation) |
| CLAUDE.md add: explicit sub-agent path constraints and validation | `ideas/archive/2026-04-15-subagent-path-constraints-hardening.md` (superseded) |
| New usage pattern: sub-agent path constraints in delegation | `ideas/archive/2026-04-15-subagent-path-constraints-hardening.md` (superseded) |
| CLAUDE.md add: cap tool investigation at 2 attempts | `ideas/2026-04-15-tool-failure-two-attempt-cap.md` |
| Headless mode: autonomous PR shepherd | `ideas/2026-04-15-autonomous-pr-shepherd-headless.md` |
| Headless mode: batch security scans | Skip bucket (defer to standalone script path) |
| Horizon: parallel multi-repo orchestration | Skip bucket |
| Horizon: test-driven bug-fix iteration agent | Skip bucket |

## Actionable Steps
1. Keep this file updated as the single source for rank order and skip/defer decisions.
2. Require implementation quests to reference this index when selecting next policy/hardening work.
3. For each implemented item, append an execution/journal pointer and mark status progression in both this file and `ideas/README.md`.
4. Reject new overlapping proposals unless they map cleanly into this index or replace an existing entry with rationale.

## Cross-References
- `ideas/2026-04-13-instruction-architecture.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`
- `ideas/handoff-validation-and-failure-ux.md`

## Risks / Non-Goals
- Non-goal: implementing policy/hook/skill changes in this documentation quest.
- Risk: if canonical ownership is not enforced, these ideas can reintroduce policy duplication.
- Risk: Tier 3 automation before Tier 1/2 hardening can amplify existing failure modes.

## Success Signal
All evaluation suggestions map to either a concrete proposal file or an explicit skip/defer rationale, and teams can execute the ranked list without ambiguity about dual-mode behavior.
