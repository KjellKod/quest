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
