---
title: PR Create Checklist via Existing PR Assistant
purpose: Improve PR accuracy by extending the existing pr-assistant skill with a verification checklist mode.
audience:
  - quest-developers
  - quest-users
scope: PR creation workflow quality and validation discipline.
status: proposed
owner: kjell
---

> Superseded by `ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`.
> Keep this file as historical source material; do not implement directly.

## Problem
The evaluation documents repeated PR quality drift: wrong script names (`npm run server` vs `npm run dev:server`), incorrect file/test paths, and manual steps presented as automated validation. Given high PR volume (20 PR-management + 18 PR-shepherding sessions), these small errors compound into repeated review friction.

## Proposal
Use the evaluation's 7-step PR creation checklist, but apply it by extending existing `.skills/pr-assistant/SKILL.md` instead of creating a duplicate `/pr-create` skill:

1. Run `pwd` and `git branch --show-current`
2. Run `git status` (all staged)
3. Run relevant test/lint commands
4. `gh pr create`
5. Verify PR description paths/script names/test commands against code
6. Run each command listed in PR testing section
7. Report PR URL

Quest-specific adaptation: integrate this into current `pr-assistant` flow as "verification checklist mode" and align output with AGENTS readability-first review expectations.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
This is a direct enhancement to an existing skill and avoids workflow fragmentation. It also complements `AGENTS.md` PR review gate language (readability-first, KISS/YAGNI/SRP/DRY).

### Outside-in use (Quest invoked from another repo)
Quest typically runs outside-in; a single canonical `pr-assistant` with checklist mode travels better than introducing repo-specific duplicate commands. Checklist items remain valid across repos with only command substitutions.

### Conflicts and Required Adaptations
There is direct overlap with `.skills/pr-assistant/SKILL.md`. Resolution is additive extension (new checklist section or linked checklist doc), not new slash-command registration.

## Actionable Steps
1. Add a "Verification Checklist" subsection to `.skills/pr-assistant/SKILL.md`.
2. Require branch/path confirmation and staged-file checks before PR creation.
3. Add a dry-run subflow that executes each command listed in the PR `## Validation` section.
4. Fail PR generation when listed commands do not run or do not match repository scripts/paths.
5. Keep ownership in `pr-assistant`; do not introduce a parallel `/pr-create` skill.

## Cross-References
- `ideas/2026-04-15-claude-rule-never-dismiss-acceptance-criteria.md`
- `ideas/2026-04-15-precommit-status-diffstat-discipline.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`

## Risks / Non-Goals
- Non-goal: replacing `pr-shepherd`; this is pre-submission quality control.
- Risk: extra checks can slow very small PRs; use a compact checklist for low-diff changes.
- Risk: duplicate checklist logic in multiple skills can drift; keep one canonical source in `pr-assistant`.

## Success Signal
PR descriptions consistently reference valid script names and paths, and commands in `## Validation` are executable and verified before PR submission.
