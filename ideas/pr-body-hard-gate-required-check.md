# PR Description Hard Gate (Required Check + Branch Protection)

## Objective
Turn PR description structure from “best practice” into an enforceable merge gate.

## Enforced Structure
Require these headings in the human-authored PR section:
- `## Summary`
- `## Changes`
- `## Validation`
- `## Notes`

## How to Enforce
1. Add a workflow job (example name: `pr-body-gate`) triggered on PR events:
   - `opened`, `edited`, `synchronize`, `ready_for_review`, `reopened`
2. Parse PR body and validate required headings.
3. If Ellipsis marker exists (`<!-- ELLIPSIS_HIDDEN -->`), validate only content above the first marker.
4. Fail the job when headings are missing.
5. Mark this check as required in branch protection/rulesets for `main`.

## Why This Should Be Core Quest Behavior
- Prevents format drift when users bypass skills and edit PR bodies manually.
- Keeps human-readable reviewer context consistent across PRs.
- Coexists safely with Ellipsis/bot sections by validating only the human section.

## Rollout Pattern
- Phase 1: enable workflow and observe failures for a week.
- Phase 2: enable required check in branch protection.
- Phase 3: add regression fixture for PR body with Ellipsis marker to ensure parser behavior stays stable.

## Downstream Implementation Status
Implemented in downstream repo via:
- `.github/workflows/pr-body-gate.yml`
with explicit human-section validation and Ellipsis-aware parsing.
