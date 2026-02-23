# Quest Policy Canonicalization and Enforcement Roadmap

## Context
Two risks were identified:
1. Policy duplication across multiple instruction files creates drift risk.
2. Many protections are instruction-only, not enforced by checks/tests/workflows.

This note translates those risks into concrete implementation guidance.

## Scope Clarification
This is the consolidation doc for policy hardening. It supersedes scattered one-off notes about PR wording and mixed gate proposals.
Supporting incident note (deleted, fix shipped in `workflow.md` on this branch):
- ~~`ideas/runtime-attribution-accuracy-for-context-health.md`~~

## Problem 1: Policy Duplication (Drift Risk)

### Where duplication currently happens
- `AGENTS.md`
- `.agents/skills/quest/SKILL.md`
- `.skills/quest/delegation/workflow.md`
- `.skills/pr-assistant/SKILL.md`
- `.codex/AGENTS.md`

These files all contain behavior rules. Some are source-of-truth, some are mirrors, but that boundary is not always explicit.

### Proposed canonical ownership map
- Quest gate sequence and phase behavior:
  - Canonical file: `.skills/quest/delegation/workflow.md`
- Merge rubric and engineering principles:
  - Canonical file: `AGENTS.md`
- PR body structure and PR operation behavior:
  - Canonical file: `.skills/pr-assistant/SKILL.md`
- Repo-local guardrails for this repository:
  - Canonical file: `.agents/skills/quest/SKILL.md`
- Codex entrypoint behavior:
  - Canonical file: `.codex/AGENTS.md` should mostly point to canonicals above, not restate rules.

### Normalization rule
- Each rule family should be defined in exactly one canonical file.
- Other files should reference canonicals with short pointers, not duplicate normative text.

### Practical mechanism
- Add an explicit `Canonical Source` line in each rule section.
- Add a lightweight lint script to fail if restricted rule phrases are duplicated outside canonical files.
- Keep mirrors brief and pointer-based.

## Problem 2: Instruction-Only Hardening (Needs Enforcement)

### Current state
- Strong wording exists, but violations are still possible when tools/agents drift or skip steps.

### Enforcement plan (in priority order)
1. Quest phase gate validator:
- Block build-phase source edits before walkthrough + explicit approval markers exist.
- Validate pre-build file changes are limited to `.quest/**` plus approved planning files.

2. Runtime attribution validator:
- Parse `.quest/<id>/logs/context_health.log`.
- Require `runtime` field on every line.
- Allow role/runtime mismatch (for fallback), but fail if runtime is missing or inferred.

3. PR body structure gate:
- Required headings in human-authored section: `## Summary`, `## Changes`, `## Validation`, `## Notes`.
- Enforce as required status check in branch protection.

4. PR review-comment merge gate:
- Require at least one explicit review-readiness comment before merge.
- Enforce via workflow + branch protection check.

5. Quest completion gate:
- Fail completion if handoff contracts, phase-state transitions, or gate evidence are incomplete.
- Reuse/extend existing validation scripts (`validate-quest-state`, `validate-handoff-contracts`, `validate-manifest`).

## Test Strategy
- Add unit tests for each new validator with positive and negative fixtures.
- Add integration fixture for a synthetic quest run:
  - valid run (passes all checks)
  - early-build edit run (fails phase gate)
  - missing runtime field run (fails attribution gate)
  - missing PR sections run (fails PR gate)

## Rollout Plan
1. Phase A: Warn-only mode in CI for new checks (no merge blocking).
2. Phase B: Flip phase gate + runtime gate to blocking.
3. Phase C: Flip PR body + review-comment gates to blocking.
4. Phase D: Remove duplicated rule text and keep pointer-only mirrors.

## Non-Goals
- No changes to product/runtime behavior in this plan.
- No broad refactor of Quest architecture in one pass.

## Success Criteria
- Clear one-to-one mapping of rule families to canonical files.
- Fewer policy edits per change (lower maintenance overhead).
- CI-enforced compliance for gate order, runtime attribution, and PR quality rules.
- Lower chance of "instructions said X but run did Y" failures.

## Progress (2026-02-22)
- Problem 1 (duplication): canonical pointers in `.codex/AGENTS.md` and `.agents/` done. Lint script and `Canonical Source` annotations not started.
- Problem 2 item 3 (PR body gate): shipped. See `docs/quest-journal/pr-body-gate_2026-02-22.md`.
- Problem 2 items 1, 2, 4, 5: not started.
- Rollout Phase A partially started (PR body gate runs warn-only, not yet required).

## Status
in-progress
