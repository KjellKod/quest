# Quest Journal: Per-Quest Orchestration Override

- Quest ID: `orchestration-override_2026-05-18__0540`
- Slug: orchestration-override
- Completed: 2026-05-18
- Mode: solo
- Quality: Platinum
- Celebration: [`celebrations/orchestration-override_2026-05-18.md`](celebrations/orchestration-override_2026-05-18.md)
- Outcome: Added `.quest/<id>/orchestration.json` as the per-quest source of truth for role model assignments, plus a startup chooser that lets users keep defaults or override models for the current quest only.

## What Shipped

1. New per-quest config file `.quest/<id>/orchestration.json` written at quest startup. This file is the single source of truth for `models.<role>` during the quest.
2. A startup "chooser" sub-step in `.skills/quest/SKILL.md` Step 3 (Quest Folder Creation) that surfaces on every fresh quest and lets users keep defaults or override role models for that quest only.

## Files Changed

- `.quest/orchestration-override_2026-05-18__0540/phase_01_plan/plan.md`
- `.quest/orchestration-override_2026-05-18__0540/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/orchestration-override_2026-05-18__0540/phase_02_implementation/pr_description.md`
- `.quest/orchestration-override_2026-05-18__0540/phase_02_implementation/builder_feedback_discussion.md`
- `.skills/quest/SKILL.md`
- `.skills/quest/delegation/workflow.md`
- `scripts/quest_validate-quest-state.sh`
- `scripts/quest_runtime/__init__.py`
- `scripts/quest_runtime/orchestration.py`
- `tests/test-validate-quest-state.sh`
- `tests/test-quest-orchestration.sh`
- `AGENTS.md`
- `ideas/2026-05-18-per-quest-orchestration-override.md`
- `.quest-manifest`
- `.quest/orchestration-override_2026-05-18__0540/phase_03_review/review_code-reviewer-a.md`
- `.quest/orchestration-override_2026-05-18__0540/phase_03_review/review_findings_code-reviewer-a.json`

## Iterations

- Plan iterations: 1
- Fix iterations: 0

## Agents

- **The Implementer** (builder):

## Quest Brief

Implement per-quest orchestration override.

Reference: `ideas/2026-05-18-per-quest-orchestration-override.md` (committed on this branch, `orchestration-override`).

### PRE-DECISIONS (do not re-litigate in planning)

- **Option B**: keep `.quest/<id>/logs/allowlist_snapshot.json` as the read-only historical record. Add `.quest/<id>/orchestration.json` as the active config the orchestrator reads.
- **Drop the "silent if defaults are clean"** option from the idea doc — the chooser surfaces on every fresh quest start.
- **Migration**: on `/quest <id>` resume, if `orchestration.json` is missing, copy `allowlist_snapshot.json` → `orchestration.json` with `source: "default"` and continue. Never re-prompt on resume.

### DELIVERABLES

1. **Storage**
   - Add `.quest/<id>/orchestration.json` writer to Quest Folder Creation (SKILL.md Step 3).
   - Schema: `{ version: 1, models: {planner, plan-reviewer-a, plan-reviewer-b, arbiter, builder, code-reviewer-a, code-reviewer-b, fixer}, source: "default"|"overridden", overridden_roles: [], preflight_validated_at: <ISO8601> }`.
   - Roles unused in the active mode (e.g., `plan-reviewer-b` in solo) may be omitted or set to `null` — be explicit in the schema.

2. **Startup chooser**
   - New SKILL.md sub-step after route selection and before Quest Folder Creation completes.
   - Displays the active `models` block from `.ai/allowlist.json`.
   - Omits/marks roles unused in the chosen mode.
   - Prompts `Customize for this quest only? [y/N]` — default N is a single Enter.
   - On N: write `orchestration.json` with `source: "default"` and the unmodified block.
   - On Y: collect overrides (decide chooser UX in planning — single-line shorthand vs. per-role prompt), validate each override against the preflight cache at `.quest/cache/claude_bridge_codex.json`, reject unavailable models with the preflight reason. Write `orchestration.json` with `source: "overridden"` and `overridden_roles` populated.

3. **Source-of-truth swap**
   - Update each of the 6 dispatch sites in `.skills/quest/delegation/workflow.md` (planner ~L315, plan-reviewers ~L349, arbiter ~L478, builder ~L712, code-reviewers ~L781, fixer ~L980) to read `models.<role>` from `.quest/<id>/orchestration.json`, not the repo allowlist.
   - Contract test: a grep-based check that no `models.<role>` read in `workflow.md` references `.ai/allowlist.json`.

4. **Validate-quest-state additions**
   - `scripts/quest_validate-quest-state.sh` asserts `orchestration.json` exists at every phase transition.
   - Rejects if any required role for the active mode has an unset or invalid model.

5. **Resume**
   - SKILL.md Step 1 (resume path) detects `orchestration.json` and skips the chooser.
   - Implements the migration line above for pre-existing quest folders.

6. **Tests**
   - Chooser writes correct artifact for default and override paths.
   - Override validation rejects unavailable models with the preflight reason.
   - Resume does not re-prompt; missing `orchestration.json` on resume triggers migration.
   - `workflow.md` text reads only from `orchestration.json` for `models.*`.
   - `validate-quest-state` rejects missing or malformed `orchestration.json`.

7. **Docs**
   - Update `SKILL.md`, `AGENTS.md` as needed, and the chooser help text.
   - Add a one-paragraph note to the idea doc marking it implemented (or move to history per repo convention).

### OUT OF SCOPE

- Per-user persistent preferences across quests.
- Preset templates (`--orchestration claude-only`, etc.).
- Splitting `models` into a dedicated schema file.
- Changes to `role_permissions`, `gates`, or `quest_completion` sections of the allowlist.
- Codex-led orchestrator chooser UX (note as follow-up, do not block on it).

### KILL CRITERIA

- Chooser raises false-positive validation errors for valid model names.
- `workflow.md` dispatch still reads `.ai/allowlist.json` for any role's model.
- Resume re-prompts the chooser.
- A new quest started without override picks a different model for any role than the repo allowlist would have.

### CONSTRAINTS

- Run end-to-end without asking the user. Full permissions granted.
- Use this branch (`orchestration-override`). Produce a PR ready for review when complete.
- The branch already has the idea doc committed; build on top of it.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/orchestration-override_2026-05-18.md`](celebrations/orchestration-override_2026-05-18.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/orchestration-override_2026-05-18.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "solo",
  "agents": [
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 7 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 2 reviews"
    },
    {
      "icon": "[SOLO]",
      "title": "Solo Adventurer",
      "desc": "Completed quest with a single companion"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 1"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 0"
    },
    {
      "icon": "📝",
      "label": "Review findings: 2"
    }
  ],
  "quality": {
    "tier": "Platinum",
    "grade": "P"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 0,
    "summaries": []
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 16
}
```
<!-- celebration-data-end -->
