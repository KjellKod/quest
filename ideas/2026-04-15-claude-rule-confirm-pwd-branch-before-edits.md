---
title: CLAUDE Rule - Confirm PWD and Branch Before Edits
purpose: Add an execution-discipline rule that requires explicit workspace context checks before editing.
audience:
  - quest-developers
  - quest-users
scope: Policy-level pre-edit context verification.
status: proposed
owner: kjell
---

## Problem
The evaluation reports 55 wrong-approach events, with repeated branch/directory mistakes across multi-repo sessions and worktrees. The same pattern appears both in direct edits and in delegated work, so a policy-level check is needed in addition to hook-level visibility.

## Proposal
Adopt the evaluation rule text verbatim, with Quest compatibility notes:

> "When working across multiple repos or worktrees, always confirm the current working directory and active branch before making any edits. Run `git branch --show-current` and `pwd` before starting work."

Quest-specific adaptation: prefer `pwd` plus `git branch --show-current 2>/dev/null || echo 'no git'` so the rule remains usable when `vcs_available == false`.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
Inside the Quest repo this is trivial and complementary to hooks. It provides a human-readable policy reminder that matches daily branch-based development.

### Outside-in use (Quest invoked from another repo)
Outside-in execution can be non-git or detached from normal VCS assumptions. The rule still helps if phrased with graceful fallback to `pwd`-only behavior.

### Conflicts and Required Adaptations
This idea overlaps with policy-sprawl concerns in `ideas/2026-04-13-instruction-architecture.md`. The rule should land in the canonical execution-discipline section (or its pointer file), not as another untracked one-off line.

## Actionable Steps
1. Add an `Execution Discipline` subsection in `CLAUDE.md` (or canonical policy file) for pre-edit context checks.
2. Use command text that is safe in non-git contexts: `pwd && (git branch --show-current 2>/dev/null || echo 'no git')`.
3. Link this rule to the hook proposal to make policy + enforcement discoverable together.
4. In Quest prompts for builder/reviewer roles, include a short reminder that pre-edit context confirmation is mandatory.

## Cross-References
- `ideas/2026-04-15-pretooluse-branch-dir-verification-hook.md`
- `ideas/2026-04-13-instruction-architecture.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`

## Risks / Non-Goals
- Non-goal: policy text alone does not enforce behavior.
- Risk: duplicating the same rule in multiple files increases drift.
- Risk: strict wording without non-git fallback can produce false failures outside-in.

## Success Signal
Quest prompts and local workflow docs consistently include the pre-edit context command, and wrong-repo/branch incidents are materially reduced in follow-up evaluations.
