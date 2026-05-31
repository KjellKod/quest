# Quest Journal: Configurable Quest ID Format

- Quest ID: `configurable-quest-id-format_2026-04-29__1328`
- Slug: configurable-quest-id-format
- Completed: 2026-04-29
- Mode: workflow
- Quality: Platinum
- Celebration: [`celebrations/configurable-quest-id-format_2026-04-29.md`](celebrations/configurable-quest-id-format_2026-04-29.md)
- Outcome: Implement issue #106: configurable Quest ID format. Goal: Add a config option that keeps the current slug-first quest ID format by default, and lets users opt into date-first quest IDs for chronolo...

## What Shipped

**Problem**: Quest currently documents and assumes a slug-first quest directory ID format: `<slug>_YYYY-MM-DD__HHMM`. Users who want `.quest/` directories to sort chronologically cannot opt into a date-first format.

**Impact**: Repositories can choose date-first IDs for new quests while existing...

## Files Changed

- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_01_plan/plan.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_01_plan/arbiter_verdict.md.next`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_01_plan/review_findings.json.next`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_02_implementation/pr_description.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_03_review/review_code-reviewer-a.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_03_review/review_code-reviewer-b.md`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_03_review/review_findings_code-reviewer-b.json`
- `.quest/configurable-quest-id-format_2026-04-29__1328/phase_03_review/review_fix_feedback_discussion.md`

## Iterations

- Plan iterations: 1
- Fix iterations: 1

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 

## Quest Brief

Implement issue #106: configurable Quest ID format.

Goal:
Add a config option that keeps the current slug-first quest ID format by default, and lets users opt into date-first quest IDs for chronological .quest/ sorting.

Reference:
- GitHub issue #106: https://github.com/KjellKod/quest/issues/106

Current format:
- slug-first: `<slug>_YYYY-MM-DD__HHMM`
- Example: `portable-pre-commit-review_2026-04-29__1430`

New optional format:
- date-first: `YYYY-MM-DD_HHMM__<slug>`
- Example: `2026-04-29_1430__portable-pre-commit-review`

Configuration:
- Add `quest_id_format` to `.ai/allowlist.json`.
- Valid values: `slug-first`, `date-first`.
- Missing value defaults to `slug-first`.
- Invalid value should be reported clearly by config validation.

Implementation guidance:
1. Do not migrate existing quest folders.
2. Do not change the default format.
3. Add a central helper for quest ID construction/parsing instead of scattering regex changes.
   Suggested location: `scripts/quest_runtime/quest_ids.py`.
4. The helper should expose behavior equivalent to:
   - `format_quest_id(slug, datetime, quest_id_format='slug-first')`
   - `parse_quest_id(value)`, accepting both slug-first and date-first IDs.
   - `is_quest_id(value)`, if useful for resume detection.
5. Resume detection must accept both formats regardless of the current configured format, because repos can contain mixed old and new quest IDs.
6. New quest creation should use the configured format.
7. Celebration/dashboard/display code should parse both formats, and should prefer explicit `state.json` fields like `slug` when available.
8. Update docs and examples only where they describe the quest ID format or resume pattern.
9. Keep the implementation narrow. Do not add a migration command in this PR.

Likely files to inspect:
- `.ai/allowlist.json`
- `.ai/schemas/allowlist.schema.json`
- `.skills/quest/SKILL.md`
- `.skills/quest/delegation/workflow.md`
- `scripts/quest_runtime/`
- `scripts/quest_celebrate/animations.py`
- `scripts/quest_celebrate/quest-celebrate.sh`
- `scripts/quest_dashboard/loaders.py`
- `tests/unit/`
- `tests/test-quest-runtime.sh`
- `tests/test-validate-quest-state.sh`
- `docs/guides/quest_setup.md`
- `docs/guides/quest_input_routing.md`
- `README.md`, only if it directly mentions the exact format

Acceptance criteria:
1. With no `quest_id_format` configured, new quests still use `<slug>_YYYY-MM-DD__HHMM`.
2. With `quest_id_format` set to `date-first`, new quests use `YYYY-MM-DD_HHMM__<slug>`.
3. Resume detection accepts both `<slug>_YYYY-MM-DD__HHMM` and `YYYY-MM-DD_HHMM__<slug>`.
4. Existing slug-first quest folders continue to work unchanged.
5. Invalid `quest_id_format` is caught by config validation with a clear error.
6. Celebration and dashboard code handle both formats without producing wrong quest names.
7. Tests cover formatting, parsing, default behavior, date-first behavior, invalid config, and mixed-format resume recognition.
8. Manifest validation passes.

Validation:
- Run focused unit tests for the new quest ID helper and touched consumers.
- Run `bash scripts/quest_validate-quest-config.sh`.
- Run `bash scripts/quest_validate-manifest.sh`.
- Run relevant runtime shell tests if quest startup/resume behavior changes.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/configurable-quest-id-format_2026-04-29.md`](celebrations/configurable-quest-id-format_2026-04-29.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/configurable-quest-id-format_2026-04-29.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    },
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
      "desc": "Tackled 4 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 5 reviews"
    },
    {
      "icon": "[SHIP]",
      "title": "Ship It",
      "desc": "PR #106 created"
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
      "label": "Fix iterations: 1"
    },
    {
      "icon": "📝",
      "label": "Review findings: 5"
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
  "files_changed": 12
}
```
<!-- celebration-data-end -->
