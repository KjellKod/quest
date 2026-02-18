# Idea: Quest Abandon Flow

## Problem

There is no way to formally abandon a quest. When a quest is interrupted or superseded, cleanup is manual: write a journal entry, update the index, archive the directory. The state schema doesn't even have `abandoned` as a valid value.

## Current State

- `state.json` status values: `pending | in_progress | complete | blocked` — no `abandoned`
- `workflow.md` has Step 7 (Complete) but no abandon step
- `/quest status` shows stale quests as "In Progress" indefinitely
- Manual cleanup required: edit journal, update index, move to archive

## Proposed: `/quest abandon <id>`

### User Experience

```
/quest abandon dashboard-final-implementation_2026-02-12__0913
# or just:
/quest abandon   (if only one active quest, auto-select)
```

Prompts for a reason, then handles all cleanup automatically.

### Steps (Step 8: Abandon)

1. **Validate:** Confirm quest exists and is not already complete/abandoned
2. **Prompt for reason:** Ask user why (e.g., "superseded by X", "no longer needed", "blocked indefinitely")
3. **Update state.json:** `phase: "abandoned"`, `status: "abandoned"`
4. **Create journal entry:** `docs/quest-journal/<slug>_<date>.md` with `**Status:** Abandoned (<reason>)`
   - Include what was planned/built so far
   - Include the reason
   - If superseded, link to successor quest
5. **Update journal index:** Append row to `docs/quest-journal/README.md` with **Abandoned** prefix
6. **Archive:** Move `.quest/<id>/` to `.quest/archive/<id>/`
7. **Show summary:** Quest ID, reason, journal location, archive location

### State Schema Change

Add `abandoned` to valid values:
```json
{
  "phase": "plan | plan_reviewed | presenting | presentation_complete | building | reviewing | fixing | complete | abandoned",
  "status": "pending | in_progress | complete | blocked | abandoned"
}
```

### Router Change

Add intent detection in `router.md`:
```
| "abandon", "cancel", "shelve", "drop" | has active quest | → Abandon Phase |
```

### Workflow Change

Add Step 8 to `workflow.md` with the steps above.

### Edge Cases

- Quest with uncommitted code changes: warn user, suggest stashing or committing first
- Quest mid-fix-loop: note which fix iteration it was on
- Multiple active quests: list them and ask which to abandon (or accept ID as argument)
- Already archived quest: error with "quest already archived"

## Scope

Small — one workflow step, router update, state schema update. No new agents needed.

---

# Approved Plan (Iteration 2)

## Revision Notes

Iteration 2 -- Addresses all 4 issues from arbiter verdict:

1. **AC3 Router Intent Detection (BLOCKING)**: Chose Option A. Added keyword detection to `router.md` that recognizes abandon/cancel/shelve/drop intent and delegates to SKILL.md Step 1 for quest resolution, then to workflow Step 8. Phase 3 updated throughout for consistency.
2. **abandoned->abandoned test case**: Added `test_invalid_abandoned_to_abandoned()` to Phase 4 test list.
3. **Manual validation for resume-from-abandoned (AC6)**: Added dedicated manual test scenario to the Validation Plan.
4. **Manual validation for edge cases (AC7)**: Added two manual test scenarios (uncommitted changes warning, already-archived error) to the Validation Plan.

## Overview

**Problem**: There is no formal way to abandon a quest. When a quest is interrupted or superseded, cleanup requires manual edits to state.json, journal entries, the journal index, and directory archiving. The state schema does not include `abandoned` as a valid value, so stale quests show as "In Progress" indefinitely.

**Impact**: Maintainers and AI agents can cleanly terminate quests with full traceability -- reason recorded, journal updated, directory archived.

**Scope**:
- IN: State schema update, workflow Step 8, router intent detection, validation script update, dashboard compatibility check
- OUT: No new agents, no UI changes, no changes to the questioner or builder flows

## Acceptance Criteria

1. `abandoned` is a valid value for both `phase` and `status` in `state.json`
2. Step 8 (Abandon) exists in `workflow.md` with all 7 cleanup substeps from the idea spec
3. Router detects abandon intent keywords ("abandon", "cancel", "shelve", "drop") and routes to the abandon phase
4. `validate-quest-state.sh` accepts `abandoned` as a valid target phase and validates transitions to it from any active phase (plan, plan_reviewed, presenting, presentation_complete, building, reviewing, fixing)
5. `validate-quest-state.sh --help` lists `abandoned` in the valid target phases
6. Step 0 (Resume Check) in `workflow.md` handles `phase: abandoned` by showing a summary ("Quest was abandoned") instead of attempting to resume
7. Edge cases are documented: uncommitted code changes warning, mid-fix-loop notation, multiple active quests selection, already-archived error
8. All existing tests in `tests/test-validate-quest-state.sh` continue to pass
9. New tests cover: valid transitions to `abandoned` from each active phase, rejection of transitions from `abandoned` to other phases (including `abandoned` itself), and the `abandoned` target in help output

## Implementation

### Phase 1: State Schema and Validation Script

**Files**:
- `scripts/validate-quest-state.sh` -- Modify -- Add `abandoned` as valid target phase and transition rules

**Key Changes**:

1. **Help text** (line ~69): Add `abandoned` to the valid target phases list.

2. **Transition table** (`validate_transition` function, line ~147): Add transitions from every active phase to `abandoned`:
   ```
   "plan->abandoned")          valid=true ;;
   "plan_reviewed->abandoned") valid=true ;;
   "presenting->abandoned")    valid=true ;;
   "presentation_complete->abandoned") valid=true ;;
   "building->abandoned")      valid=true ;;
   "reviewing->abandoned")     valid=true ;;
   "fixing->abandoned")        valid=true ;;
   ```

3. **Artifact validation** (`validate_artifacts` function, line ~173): Add a case for `*->abandoned` transitions. The only required artifact is `state.json` (already validated). No additional artifacts are needed -- the abandon flow creates its own journal entry.

4. **Reject transitions FROM abandoned**: The transition table already handles this implicitly (no `abandoned->*` entries), so `complete->plan` style rejections apply equally to `abandoned->plan`. Add an explicit test to confirm.

**Acceptance Criteria**: AC1, AC4, AC5

### Phase 2: Workflow Changes

**Files**:
- `.skills/quest/delegation/workflow.md` -- Modify -- Add Step 8 and update state schema, Step 0

**Key Changes**:

1. **State File Format section** (line ~762): Add `abandoned` to both `phase` and `status` enum values:
   ```
   "phase": "plan | plan_reviewed | presenting | presentation_complete | building | reviewing | fixing | complete | abandoned",
   "status": "pending | in_progress | complete | blocked | abandoned"
   ```

2. **Step 0: Resume Check** (line ~85): Add a case for `phase: abandoned`:
   ```
   - `phase: abandoned` -> show summary: "Quest was abandoned. Reason: <from state.json or journal>. Use /quest to start a new quest."
   ```

3. **Step 8: Abandon** -- New section after Step 7, before the Q&A Loop Pattern section (after line ~745). Contains the 7 substeps from the idea spec:
   - 8.1 **Validate**: Confirm quest exists, is not already complete or abandoned
   - 8.2 **Prompt for reason**: Ask user why (superseded, no longer needed, blocked indefinitely)
   - 8.3 **Update state.json**: Set `phase: "abandoned"`, `status: "abandoned"`, add `abandon_reason` field
   - 8.4 **Create journal entry**: Write to `docs/quest-journal/<slug>_<date>.md` with `**Status:** Abandoned (<reason>)`, include what was planned/built, include the reason, link successor quest if superseded
   - 8.5 **Update journal index**: Append row to `docs/quest-journal/README.md` with **Abandoned** prefix
   - 8.6 **Archive**: Move `.quest/<id>/` to `.quest/archive/<id>/`
   - 8.7 **Show summary**: Quest ID, reason, journal location, archive location

4. **Edge case handling** within Step 8:
   - Before archiving, check `git status` for uncommitted changes. If found, warn: "Warning: You have uncommitted changes. Consider committing or stashing before abandoning."
   - If `phase: fixing`, note the fix iteration in the journal entry: "Abandoned during fix iteration N"
   - If multiple active quests exist (multiple directories in `.quest/` excluding `archive/` and `audit.log`), list them and ask which to abandon, or accept the ID as argument
   - If quest is already in `.quest/archive/`, error with "Quest already archived"

5. **Utility Commands section** (line ~879): Add `/quest abandon <id>` command:
   ```
   **`/quest abandon <id>`** -- Abandon a quest with cleanup (state update, journal, archive)
   **`/quest abandon`** -- If only one active quest, auto-select it for abandonment
   ```

**Acceptance Criteria**: AC1, AC2, AC6, AC7

### Phase 3: Router Changes

**Files**:
- `.skills/quest/delegation/router.md` -- Modify -- Add abandon intent keyword detection
- `.skills/quest/SKILL.md` -- Modify -- Add abandon routing in Step 1

**Key Changes**:

1. **router.md**: Add an **Abandon Intent Detection** section before the substance evaluation dimensions. This section detects abandon-related keywords early:
   ```markdown
   ## Abandon Intent Detection

   Before evaluating substance dimensions, check if the user input contains
   abandon intent keywords: "abandon", "cancel", "shelve", "drop".

   If detected:
   - route: "abandon"
   - confidence: 1.0
   - reason: "User explicitly requested quest abandonment"
   - Skip substance evaluation entirely

   The abandon route is handled by SKILL.md Step 1, which resolves the
   target quest ID and delegates to workflow.md Step 8.
   ```

   This satisfies AC3: the router detects the keywords. The actual quest resolution (which quest to abandon, validation) is handled downstream where quest state is accessible.

2. **SKILL.md Step 1: Resume Check** (line ~22): Add abandon intent handling before the existing resume logic:
   ```
   If the router returned route = "abandon", or the user says `/quest abandon <id>` or `/quest abandon`:
   1. If <id> provided, verify `.quest/<id>/` exists
   2. If no <id>, scan `.quest/` for active quests (exclude `archive/`, `audit.log`)
      - If exactly one active quest: auto-select it
      - If multiple: list them and ask which to abandon
      - If none: error "No active quests to abandon"
   3. Delegate to `delegation/workflow.md` Step 8 (Abandon)
   ```

3. **SKILL.md Step 3: Route** (line ~38): Add abandon route handling:
   ```
   **If route = "abandon":**
   1. Handle as described in Step 1 abandon flow above
   ```

**Acceptance Criteria**: AC3

### Phase 4: Tests

**Files**:
- `tests/test-validate-quest-state.sh` -- Modify -- Add abandon-related test cases

**New Test Cases**:

```bash
test_valid_plan_to_abandoned()
  # state: phase=plan, target: abandoned -> should pass (exit 0)

test_valid_building_to_abandoned()
  # state: phase=building, target: abandoned -> should pass (exit 0)

test_valid_reviewing_to_abandoned()
  # state: phase=reviewing, target: abandoned -> should pass (exit 0)

test_valid_fixing_to_abandoned()
  # state: phase=fixing, target: abandoned -> should pass (exit 0)

test_valid_presenting_to_abandoned()
  # state: phase=presenting, target: abandoned -> should pass (exit 0)

test_valid_presentation_complete_to_abandoned()
  # state: phase=presentation_complete, target: abandoned -> should pass (exit 0)

test_valid_plan_reviewed_to_abandoned()
  # state: phase=plan_reviewed, target: abandoned -> should pass (exit 0)

test_invalid_abandoned_to_plan()
  # state: phase=abandoned, target: plan -> should fail (exit 1)
  # Verifies no transitions OUT of abandoned

test_invalid_abandoned_to_abandoned()
  # state: phase=abandoned, target: abandoned -> should fail (exit 1)
  # Verifies idempotent abandon is rejected (already abandoned)

test_invalid_complete_to_abandoned()
  # state: phase=complete, target: abandoned -> should fail (exit 1)
  # Cannot abandon an already-completed quest

test_help_lists_abandoned()
  # Run --help, verify "abandoned" appears in valid target phases
```

**Run command**: `bash tests/test-validate-quest-state.sh`

**Acceptance Criteria**: AC8, AC9

## Validation Plan

**Automated Test**: Validation script abandon transitions
- **File**: tests/test-validate-quest-state.sh
- **Tests**: test_valid_plan_to_abandoned, test_valid_building_to_abandoned, test_valid_reviewing_to_abandoned, test_valid_fixing_to_abandoned, test_valid_presenting_to_abandoned, test_valid_presentation_complete_to_abandoned, test_valid_plan_reviewed_to_abandoned, test_invalid_abandoned_to_plan, test_invalid_abandoned_to_abandoned, test_invalid_complete_to_abandoned, test_help_lists_abandoned
- **Run**: `bash tests/test-validate-quest-state.sh`
- **Covers**: All valid transitions to abandoned, rejection of transitions from abandoned (including self-transition), help text
- **Mocking**: None (uses temp directories with state.json fixtures)
- **Expected**: All tests pass, exit 0

**Automated Test**: Existing test regression check
- **File**: tests/test-validate-quest-state.sh
- **Run**: `bash tests/test-validate-quest-state.sh`
- **Covers**: All 27 existing tests continue to pass
- **Expected**: 0 failures

**MANUAL TEST**: End-to-end abandon flow
- **Why manual**: Requires interactive orchestrator with `/quest abandon` command
- **Preconditions**: An active quest exists in `.quest/`
- **Steps**:
  1. Run `/quest abandon` with an active quest
  2. Provide a reason when prompted
  3. Verify state.json shows `phase: abandoned`, `status: abandoned`
  4. Verify journal entry exists in `docs/quest-journal/` with abandoned status and reason
  5. Verify journal index row added to `docs/quest-journal/README.md`
  6. Verify quest directory moved to `.quest/archive/`
- **Expected**: All cleanup steps execute, summary displayed
- **Observability**: Check state.json, journal file, journal index, archive directory

**MANUAL TEST**: Resume-from-abandoned (AC6)
- **Why manual**: Requires interactive orchestrator with `/quest` resume behavior
- **Preconditions**: A quest with `phase: abandoned` in its state.json (create manually or use a previously abandoned quest before archiving)
- **Steps**:
  1. Ensure `.quest/<id>/state.json` has `"phase": "abandoned"`
  2. Run `/quest <id>` to attempt resuming the abandoned quest
  3. Observe the output
- **Expected**: Shows "Quest was abandoned. Reason: ..." summary message. Does NOT attempt to resume workflow from any phase. Suggests starting a new quest.
- **Observability**: Terminal output shows abandoned summary, no phase delegation occurs

**MANUAL TEST**: Abandon with uncommitted changes (AC7 edge case)
- **Why manual**: Requires git working tree with uncommitted changes and interactive orchestrator
- **Preconditions**: An active quest exists in `.quest/`, and the working tree has uncommitted changes (`git status` shows modified/untracked files)
- **Steps**:
  1. Make a local file change without committing
  2. Run `/quest abandon` targeting the active quest
  3. Observe the warning output before the abandon proceeds
- **Expected**: A warning message appears: "Warning: You have uncommitted changes. Consider committing or stashing before abandoning." The abandon flow continues after the warning (does not block).
- **Observability**: Terminal output contains the uncommitted changes warning

**MANUAL TEST**: Abandon already-archived quest (AC7 edge case)
- **Why manual**: Requires a quest that has already been archived
- **Preconditions**: A quest directory exists in `.quest/archive/<id>/` but not in `.quest/<id>/`
- **Steps**:
  1. Run `/quest abandon <id>` where `<id>` is the archived quest
  2. Observe the error output
- **Expected**: Error message: "Quest already archived" (or equivalent). The command exits without making changes.
- **Observability**: Terminal output shows the error, no state changes occur

## Integration Touchpoints

**Quest Dashboard** (`scripts/quest_dashboard/`): Already handles `abandoned` status in journal entries (see `models.py` `abandoned_quests` field). The dashboard loads journal entries and classifies them by status. Adding `abandoned` to state.json does not affect the dashboard -- it reads from journal files, not state.json directly. No changes needed.

**CI Workflow** (`.github/workflows/validate-quest-config.yml`): Runs `tests/test-validate-quest-state.sh`. New tests will be picked up automatically. No workflow changes needed.

**Validation Logging**: The validation script already logs transitions to `<quest-dir>/logs/validation.log`. Transitions to `abandoned` will be logged automatically. No changes needed.

## Risks

1. **Risk**: Transition table grows with 7 new entries, increasing maintenance surface
   - Impact: L | Likelihood: L | Mitigation: All transitions follow the same pattern (any-active->abandoned). A comment block groups them clearly.

2. **Risk**: Abandon during uncommitted changes could lose work
   - Impact: M | Likelihood: M | Mitigation: Step 8 checks `git status` and warns before proceeding. Does not force-clean.

3. **Risk**: State schema change could break external tooling reading state.json
   - Impact: L | Likelihood: L | Mitigation: `abandoned` is additive. Existing tooling that does not recognize it will simply ignore it or treat it as unknown, which is safe.

## Open Questions

- None. The idea spec is detailed and all edge cases are addressed.
