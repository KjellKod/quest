# Auto-Update .quest/README.md on Quest Completion

## What
When a quest completes (Step 7), automatically update `.quest/README.md` with the quest's results — purpose, status, key findings, and recommendation.

## Why
The `.quest/README.md` serves as a fast-scanning index of all quests. Today it must be updated manually (or by explicit request), which means it drifts out of date. Since the quest system already writes `state.json`, journal entries, and plan artifacts at completion, it has all the data needed to update the index automatically.

## Approach

### What to add to Step 7 (Complete)
After writing the journal entry (Step 7.2), add a step that updates `.quest/README.md`:

1. **If `.quest/README.md` does not exist**, create it with the standard template (dashboard table + "How to Read Quest Folders" section).
2. **If it exists**, parse the dashboard table and either:
   - **Update** the row for this quest (status → Complete, phase → Complete)
   - **Add** a new row if the quest isn't listed yet
3. **Update or add** the detail section for this quest under "Completed Quests" with:
   - Folder path
   - Journal link
   - Type (from quest brief or plan)
   - Purpose (1-2 sentences from quest brief)
   - Key findings (from journal or plan acceptance criteria)
   - Recommendation (implement/wait/done — inferred from quest type)
   - Deliverables list
4. **If the quest was previously listed under "Interrupted / In-Progress"**, move it to "Completed Quests".

### Data sources (all available at Step 7)
- `state.json` — quest ID, slug, phase, status
- `quest_brief.md` — purpose, requirements, type
- `phase_01_plan/plan.md` — acceptance criteria, key findings
- `docs/quest-journal/<slug>_<date>.md` — summary, files changed

### One-liner generation
The dashboard table includes a "One-liner" column. Generate this from:
- The journal summary (first sentence), or
- The quest brief's first requirement, or
- A fallback: "<type>: <slug humanized>"

### Edge cases
- **Interrupted quests**: Don't auto-add these to the README on creation. Only add them if the README is being regenerated or if a `/quest status` command is run.
- **Re-run quests**: If a quest is resumed and completed after being interrupted, move it from "Interrupted" to "Completed".
- **README conflicts**: The README is in `.quest/` (gitignored), so no merge conflicts. But if two quests complete in parallel, the last write wins. Acceptable for now.

## Acceptance Criteria
1. A quest that runs to completion (Step 7) produces an updated `.quest/README.md` without manual intervention.
2. The dashboard table row is added or updated with correct status, phase, date, type, and one-liner.
3. A detail section is added under "Completed Quests" with purpose, findings, recommendation, and deliverables.
4. If `.quest/README.md` doesn't exist, it is created from scratch with the standard template.
5. Existing content for other quests is preserved (no clobbering).
6. The update is performed by the orchestrator (workflow.md Step 7), not by a separate agent.

## Complexity
S-M — mostly string manipulation and file parsing within the existing Step 7 flow.

## Status
idea
