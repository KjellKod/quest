---
title: Autonomous PR Shepherd (Headless) Staged Design
purpose: Define a guarded path to headless PR lifecycle automation built on existing pr-shepherd capabilities.
audience:
  - quest-developers
  - quest-users
scope: Long-horizon automation for PR shepherding with strict safety boundaries.
status: idea
owner: kjell
---

## Problem
The evaluation shows high operational load in PR lifecycle work (20 PR-management sessions and 18 PR-shepherding sessions). Repetition is high-value automation territory, but current friction patterns (wrong branch/path, validation drift) can be amplified if autonomous loops are enabled too early.

## Proposal
Build headless PR shepherding on top of the existing `.skills/pr-shepherd/SKILL.md`, using the evaluation's headless invocation pattern (`claude -p ... --allowedTools ... --output-format json`) for scheduled/non-interactive execution. Hard constraint from the evaluation should be preserved: autonomous shepherd prepares for merge but never merges.

Prerequisite gate: Tier 1 and Tier 2 guardrails from this batch should land first.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
Inside this repo, existing `pr-shepherd` process and quality gates provide a stable baseline for incremental headless support (`--headless` mode, safe retry limits, no-merge policy).

### Outside-in use (Quest invoked from another repo)
Outside-in usage varies by branch conventions, test commands, and CI systems. Headless mode needs per-repo configuration (for example `.quest/shepherd.config.yaml`) to avoid hardcoded assumptions.

### Conflicts and Required Adaptations
Direct overlap exists with `.skills/pr-shepherd/SKILL.md`. This idea should extend that skill, not create a second shepherd implementation. Keep ownership unified and safety constraints explicit.

## Actionable Steps
1. Audit current `.skills/pr-shepherd/SKILL.md` flow and identify extension points for non-interactive operation.
2. Add a `--headless` execution mode with deterministic retries and polling limits.
3. Define `.quest/shepherd.config.yaml` schema for repo-specific branch/test/CI behavior.
4. Enforce hard constraints: never merge, branch verification before edits, stop on permissions/protection failures.
5. Roll out in stages after Tier 1-2 guardrails are proven.

## Cross-References
- `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md`
- `ideas/2026-04-15-pretooluse-branch-dir-verification-hook.md`
- `ideas/2026-04-15-claude-insights-priorities.md`

## Risks / Non-Goals
- Non-goal: autonomous merge rights.
- Risk: automation loops can repeat bad assumptions quickly without context guardrails.
- Risk: cross-repo CI variability can break headless flows unless config is explicit and validated.

## Success Signal
A headless shepherd can process PR updates, CI failures, and review replies end-to-end without manual babysitting while respecting the never-merge boundary.
