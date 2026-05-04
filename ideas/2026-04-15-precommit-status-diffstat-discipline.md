---
title: Pre-Commit Status and Diffstat Discipline
purpose: Reduce missed files and staging mistakes by requiring explicit pre-commit status and diffstat checks.
audience:
  - quest-developers
  - quest-users
scope: Commit-readiness checks and bounded hook options.
status: proposed
owner: kjell
---

> Superseded by `ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`.
> Keep this file as historical source material; do not implement directly.

## Problem
The evaluation repeatedly notes forgotten unstaged files (including `.skills` and config changes) discovered late in the commit/PR flow. This creates avoidable rework and undermines confidence that PRs represent the full intended change set.

## Proposal
Adopt the evaluation rule verbatim as commit discipline:

> "Before committing and pushing, run `git status` and `git diff --stat` to ensure ALL modified files are staged. Never assume only the files you edited are the ones that changed."

Quest-specific adaptation: keep hook enforcement bounded. The evaluation's broad `PostToolUse Bash` diff hook is informative but likely too noisy if triggered on every bash call.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
This complements existing workflow expectations and catches accidental file drift before commit, especially in Quest docs/skill changes.

### Outside-in use (Quest invoked from another repo)
When `vcs_available == false`, the rule should degrade to a no-op with explicit note, not a hard failure. In git-backed repos, it remains fully applicable.

### Conflicts and Required Adaptations
`.skills/git-commit-assistant/SKILL.md` currently validates manifest + staged diff style, but does not explicitly require `git status` and `git diff --stat` checks for full working-tree awareness. This idea should extend that skill rather than adding parallel commit rules.

## Actionable Steps
1. Add explicit `git status` + `git diff --stat` checks to `.skills/git-commit-assistant/SKILL.md`.
2. Add a pre-commit checklist item requiring "all expected files staged."
3. If adding hook support, scope it to commit-adjacent commands (or dedicated pre-commit event) rather than all bash invocations.
4. Add `vcs_available == false` fallback text so no-VCS workflows do not break.

## Cross-References
- `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md`
- `ideas/2026-04-15-pretooluse-branch-dir-verification-hook.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`

## Risks / Non-Goals
- Non-goal: forcing all workflows to use hooks.
- Risk: unbounded hooks produce alert fatigue and can be ignored.
- Risk: strict gating without no-VCS fallback can block outside-in scenarios unnecessarily.

## Success Signal
Commit workflows consistently show full-file awareness before push, and follow-up sessions no longer report missing staged files as recurring friction.
