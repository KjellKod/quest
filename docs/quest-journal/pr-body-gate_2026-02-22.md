# PR Body Gate

**Date:** 2026-02-22
**Origin:** `ideas/pr-body-hard-gate-required-check.md`
**Status:** Shipped (Phase 1)

## What shipped
Added `.github/workflows/pr-body-gate.yml` — a GitHub Actions workflow that validates PR bodies contain four required headings:
- `## Summary`
- `## Changes`
- `## Validation`
- `## Notes`

Triggers on PR `opened`, `edited`, `synchronize`, `ready_for_review`, `reopened`. Uses `actions/github-script@v7` with inline validation logic. No external dependencies.

Ported from downstream repo (`internal-slack-automation-platform`) and simplified by removing bot-specific section splitting.

## What's left
- Enable `pr-body-gate` as a required status check in branch protection/rulesets for `main`.
- Add regression fixtures for edge cases (empty body, partial headings, mixed human + bot sections).

## Files changed
- `.github/workflows/pr-body-gate.yml` (new)
