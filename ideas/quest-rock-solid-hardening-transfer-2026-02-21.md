# Quest Rock-Solid Hardening Transfer (2026-02-21)

## Context
This note consolidates operational lessons from a full Quest run in a downstream repo so Quest can be hardened upstream.

## 1) Sequence Discipline Must Be Enforced
- Required order: routing -> plan -> dual plan review -> arbiter -> walkthrough -> explicit approval -> build -> dual code review -> fixes.
- If implementation starts early, stop immediately, disclose, and resume at the required gate.
- Pre-build writes limited to `.quest/**` only.

## 2) Runtime Attribution Must Reflect Actual Backend
- Do not infer runtime from role labels (e.g. `slot_a_claude`).
- Log runtime from invocation backend only:
  - Claude `Task(...)` -> `runtime=claude`
  - Codex agent tools / `mcp__codex__codex` -> `runtime=codex`
- Compliance summaries must use logged runtime values, not role names.

## 3) PR Description Quality Must Be Standardized
- Human-authored PR top section should use:
  - `## Summary`
  - `## Changes`
  - `## Validation`
  - `## Notes`
- Keep it concise and reviewer-first.

## 4) Ellipsis Add-On Handling
- If `<!-- ELLIPSIS_HIDDEN -->` exists, preserve everything from first marker to end exactly when editing PR bodies.
- Update only the human section above the marker.

## 5) Make PR Structure a True Hard Gate
- Add CI workflow check (`pr-body-gate`) validating required PR headings.
- If Ellipsis marker exists, validate only human section above first marker.
- Enforce via branch protection required status checks.

## 6) Merge Policy Gate (Mandatory)
Before merge:
1. PR is on a feature branch and opened as draft.
2. PR is made ready and required checks pass.
3. An explicit PR review comment is posted.
4. Merge decision is made after filtering low-value NITs.

## 7) Review Rubric for Merge Decisions
Use this order:
- Readability first
- KISS
- YAGNI
- SRP
- DRY
- Prefer simple robust over complex elegance
- High test quality without falling into mocking-hell

## 8) CI Reliability Lesson
- `actions/setup-node` with `cache: npm` fails without lockfile.
- Either add lockfile intentionally or remove cache setting to avoid false CI failures.

## 9) Suggested Quest-Core Actions
- Add explicit runtime attribution rules and checks in workflow docs + tests.
- Add PR body gating workflow template to Quest defaults.
- Add PR update helper that preserves Ellipsis block by marker.
- Add mandatory “posted review comment before merge” gate in Quest PR flow.
- Add regression fixtures for:
  - codex-only runtime reporting
  - Ellipsis-preserving PR edits
  - PR body gate heading checks
