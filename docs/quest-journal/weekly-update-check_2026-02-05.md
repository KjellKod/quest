# Quest Journal: Weekly Update Check

**Quest ID:** `weekly-update-check_2026-02-04__2349`
**Completed:** 2026-02-05
**Plan Iterations:** 2
**Fix Iterations:** 0

## Summary

Implemented automatic weekly update checking for Quest. After a quest completes, the system checks if updates are available (respecting a configurable interval) and prompts the user to update if a newer version exists upstream.

## Files Changed

| File | Change |
|------|--------|
| `.skills/quest/SKILL.md` | Added Step 7.5: Update check logic with SHA comparison via `git ls-remote` |
| `.ai/allowlist.json` | Added `update_check` config section (`enabled`, `interval_days`) |
| `.gitignore` | Added `.quest-last-check` |
| `ideas/weekly-update-check.md` | Status updated from `idea` to `implemented` |

## Acceptance Criteria Met

- [x] AC1: Update check runs after quest completion (Step 7)
- [x] AC2: Respects `update_check.enabled` setting (default: true)
- [x] AC3: Respects `update_check.interval_days` setting (default: 7)
- [x] AC4: Prompts user interactively when update available
- [x] AC5: Runs installer if user accepts
- [x] AC6: Network errors handled gracefully (silent skip)
- [x] AC7: `.quest-last-check` added to `.gitignore`
- [x] AC8: Idea file status updated to `implemented`

## This is where it all began...

> **From `ideas/weekly-update-check.md`:**
>
> Quest automatically checks for updates once per week (or configurable interval) when a `/quest` command completes. If an update is available, it notifies the user and offers to run the installer.
>
> **Why:**
> - Users stay current with bug fixes and improvements without manual checking
> - Non-intrusive: only triggers after quest completion, not during
> - Opt-in update: user decides whether to apply
> - "Set it and forget it" experience for adopters

## Artifacts

- Plan: `.quest/weekly-update-check_2026-02-04__2349/phase_01_plan/plan.md`
- Reviews: `.quest/weekly-update-check_2026-02-04__2349/phase_01_plan/review_claude.md`
- Code Review: `.quest/weekly-update-check_2026-02-04__2349/phase_03_review/review_claude.md`
