---
title: Sub-Agent Path Constraints Hardening
purpose: Harden existing Quest path controls by validating sub-agent artifact paths after execution.
audience:
  - quest-developers
  - quest-users
scope: Delegation safety and output-path compliance.
status: proposed
owner: kjell
---

## Problem
The evaluation highlights repeated sub-agent path failures: wrong directories, nested quest folders, and wiped workspace artifacts across high-volume agent usage (268 Agent invocations). These incidents were costly because errors were discovered after work completed, not at post-run validation time.

## Proposal
Use the evaluation guidance as a hardening extension:

> "When spawning sub-agents or using quest workflows, explicitly pass the correct working directory and target file paths. Validate sub-agent output paths before accepting their work."

Quest-specific adaptation: this is not net-new architecture. `.skills/quest/delegation/workflow.md` already references `expected_artifacts_for_role(...)` and `prepare_artifact_files(...)`; the gap is stronger post-invocation validation against on-disk results.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
Inside this repo, hardening can reuse existing workflow contracts and add explicit verification before handoff acceptance. This lowers recovery effort when sub-agents misplace files.

### Outside-in use (Quest invoked from another repo)
Outside-in invocation still runs the same Quest delegation workflow. Path verification remains valid and should respect `vcs_available` mode differences (checks must be filesystem-based, not git-dependent).

### Conflicts and Required Adaptations
No structural conflict with current workflow. Required adaptation is additive: validate `handoff.json` artifact claims against actual filesystem paths and fail/flag mismatches before routing.

## Actionable Steps
1. Add a post-invocation validator (for example `scripts/quest_artifact_postflight.py`) that compares declared artifacts to on-disk files.
2. Validate each declared path is within expected role path boundaries.
3. Log mismatches to `.quest/<id>/logs/path_compliance.log` with phase, role, and offending path.
4. Mark runs with mismatches as recoverable failure requiring retry or fallback before accepting agent output.
5. Reference `expected_artifacts_for_role(...)` and `prepare_artifact_files(...)` directly in validator docs to avoid rule drift.

## Cross-References
- `ideas/2026-04-15-pretooluse-branch-dir-verification-hook.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`
- `ideas/handoff-validation-and-failure-ux.md`

## Risks / Non-Goals
- Non-goal: redesigning delegation architecture from scratch.
- Risk: overly strict checks can reject valid edge-case outputs if path normalization is wrong.
- Risk: adding validation without clear failure UX can increase confusion; tie into handoff diagnostics.

## Success Signal
Sub-agent runs that write outside expected paths are detected immediately, logged, and blocked from silent acceptance.
