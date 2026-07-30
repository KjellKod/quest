# Bug Report: Sharpen Revisions Cannot Return Presentation to Planning

**Date:** 2026-07-28  
**Status:** reference  
**Severity:** High — an approved Quest cannot continue after Sharpen finds plan revisions  
**Discovered during:** `filter-semantics-fix_2026-07-28__2103` in the `candid_talent_edge` consumer repository

## Summary

The canonical Quest workflow requires a Quest in `presenting` to return to
`plan` when the Sharpen interview produces revisions. The state validator does
not allow `presenting -> plan`, so the documented recovery path stops with an
invalid-transition error.

This is a closed-set mismatch between the workflow and its enforcement:

- `.skills/quest/delegation/workflow.md:675` routes Sharpen revisions to Change
  Handling.
- `.skills/quest/delegation/workflow.md:758` requires state to become
  `phase: plan`, `status: in_progress`.
- `scripts/quest_validate-quest-state.sh:244-256` omits
  `presenting->plan` from the allowed transition table.

The installed consumer files and the Quest source files were byte-identical when
the defect was reproduced.

## Reproduction

1. Run a workflow-mode Quest through plan approval.
2. Transition `plan_reviewed -> presenting`.
3. Select Sharpen during the mandatory plan presentation.
4. Resolve the interview with `Next: re-plan with these revisions: ...`.
5. Write the required `phase_01_plan/user_feedback.md`.
6. Run:

   ```bash
   python3 scripts/quest_state.py \
     --quest-dir .quest/<id> \
     --transition plan \
     --status in_progress \
     --expect-phase presenting
   ```

Actual result:

```text
Transition to plan rejected by validator.
[FAIL] Invalid transition: presenting -> plan (not in allowed transition table)

AGENT: Validation failed. Do NOT proceed with this phase transition.
Do NOT modify state.json to work around this failure.
Report this validation failure to the user and STOP.
```

The Quest remains in `presenting` even though the current plan is superseded by
accepted user feedback.

## Expected Behavior

`presenting -> plan` is valid only for the documented change-handling path and
only when non-empty `phase_01_plan/user_feedback.md` exists. The next planner
iteration then consumes that feedback and repeats plan review, arbitration, and
presentation before Build.

The transition must not allow a user or agent to bypass presentation approval
and enter Build.

## Likely Root Cause

The presentation state and mandatory Build gate were added to the validator, but
the reverse transition required by walkthrough/Sharpen change handling was not
added to the same closed transition set. The prose workflow and state machine
therefore evolved independently.

## Recommended Fix

Keep the change narrow:

1. Add `presenting->plan` to `validate_transition()`.
2. Add a `presenting->plan` artifact check requiring a non-empty
   `phase_01_plan/user_feedback.md`.
3. Preserve all existing forward gates:
   `plan -> plan_reviewed -> presenting -> presentation_complete -> building`.
4. Add an executable regression test proving:
   - the transition fails before feedback exists;
   - it passes with non-empty feedback;
   - it does not mutate state when validation fails;
   - `presenting -> building` remains invalid.
5. Add a workflow/validator contract test so every transition prescribed by
   `.skills/quest/delegation/workflow.md` is represented in the validator.

## Acceptance Criteria

- A Sharpen outcome with revisions can atomically transition
  `presenting -> plan`.
- Missing or empty `user_feedback.md` blocks that transition.
- The planner receives the recorded feedback on the next iteration.
- The revised plan still requires dual review, arbitration, presentation, and
  explicit Build approval.
- Existing invalid transitions remain invalid.
- Installed consumer behavior is corrected by the normal Quest distribution
  path rather than by a permanent consumer-repository patch.

## Workaround Used During Discovery

No direct `state.json` edit is acceptable. A consumer may temporarily align its
validator with the source-level fix, perform the validated transition, and then
remove that local recovery patch. The durable fix belongs in the Quest source
repository and should ship through its installer/update path.
