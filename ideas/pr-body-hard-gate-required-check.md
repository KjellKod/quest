# PR Description Hard Gate (Required Check + Branch Protection)

## Objective
Turn PR description structure from "best practice" into an enforceable merge gate.

## Enforced Structure
Require these headings in the human-authored PR section:
- `## Summary`
- `## Changes`
- `## Validation`
- `## Notes`

## How to Enforce
1. Add a workflow job (example name: `pr-body-gate`) triggered on PR events:
   - `opened`, `edited`, `synchronize`, `ready_for_review`, `reopened`
2. Parse PR body and validate required headings in the human-authored section.
3. Preserve bot-managed sections/anchors unchanged; do not require those sections to match the human heading schema.
4. Fail the job when required headings are missing.
5. Mark this check as required in branch protection/rulesets for `main`.

## Why This Should Be Core Quest Behavior
- Prevents format drift when users bypass skills and edit PR bodies manually.
- Keeps reviewer context consistent and scannable.
- Makes PR quality behavior enforceable, not instruction-only.

## Rollout Pattern
- Phase 1: enable workflow in warn-only mode.
- Phase 2: enforce as required status check.
- Phase 3: add regression fixtures for mixed human + bot-managed PR bodies.

## Downstream Implementation Note
This gate has already been trialed in a downstream repository and is compatible with preserving bot-managed PR sections.

## Status
proposed
