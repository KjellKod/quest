# Quest Journal: Installer Branch Conflict

- Quest ID: `2026-05-01_1836__installer-branch-conflict`
- Completed: 2026-05-02
- Mode: solo
- Quality: Diamond
- Outcome: Fixed issue #110 so repeated same-day installer upgrades no longer fail when the default `quest-update-YYYYMMDD` branch already exists locally.

## What Shipped

**Problem**: During an upgrade from `main` or `master`, `scripts/quest_installer.sh` prompts to create a Quest update branch and always uses `quest-update-$(date +%Y%m%d)`. A second upgrade on the same day fails with `fatal: a branch named 'quest-update-YYYYMMDD' already exists`.

**Impact**: Users can accept the installer branch prompt repeatedly on the same day without deleting or reusing existing local update branches.

## Files Changed

- `.ai/allowlist.json`
- `scripts/quest_installer.sh`
- `tests/test-quest-runtime.sh`
- `docs/quest-journal/README.md`
- `docs/quest-journal/installer-branch-conflict_2026-05-02.md`
- `.quest/2026-05-01_1836__installer-branch-conflict/phase_01_plan/plan.md`
- `.quest/2026-05-01_1836__installer-branch-conflict/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/2026-05-01_1836__installer-branch-conflict/phase_02_implementation/pr_description.md`
- `.quest/2026-05-01_1836__installer-branch-conflict/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/2026-05-01_1836__installer-branch-conflict/phase_03_review/review_code-reviewer-a.md`
- `.quest/2026-05-01_1836__installer-branch-conflict/phase_03_review/review_findings_code-reviewer-a.json`

## Iterations

- Plan iterations: 2
- Fix iterations: 0

## Agents

- **The Planner** (planner): Codex
- **The A Plan Critic** (plan-reviewer-a): Codex
- **The Implementer** (builder): Codex
- **The A Code Critic** (code-reviewer-a): Codex

## Quest Brief

`$quest https://github.com/KjellKod/quest/issues/110 fix this.`

Issue: https://github.com/KjellKod/quest/issues/110

Title: quest installer fails if you upgrade twice the same day ... and old branch still exists locally

Body excerpt:

```text
Quest Installer (latest release: 1.4.2)
[INFO] Using upstream branch: quest/configurable-quest-id-format
...
[INFO] Updating Quest from 1c7d6954 to 376f0791
Create a new branch for Quest changes? [Y/n] y
fatal: a branch named 'quest-update-20260501' already exists
```

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/installer-branch-conflict_2026-05-02.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "solo",
  "agents": [
    {
      "name": "planner",
      "model": "Codex",
      "role": "The Planner"
    },
    {
      "name": "plan-reviewer-a",
      "model": "Codex",
      "role": "The A Plan Critic"
    },
    {
      "name": "builder",
      "model": "Codex",
      "role": "The Implementer"
    },
    {
      "name": "code-reviewer-a",
      "model": "Codex",
      "role": "The A Code Critic"
    }
  ],
  "achievements": [
    {
      "icon": "[FIX]",
      "title": "Same-Day Upgrade Unblocked",
      "desc": "Repeated installer upgrades no longer fail on an existing update branch"
    },
    {
      "icon": "[REF]",
      "title": "Local-Ref Precision",
      "desc": "Branch collision checks target local refs/heads only"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Refined validation before build"
    },
    {
      "icon": "[REVIEW]",
      "title": "Zero-Finding Finish",
      "desc": "Final code review found no issues"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 2"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 0"
    },
    {
      "icon": "🧪",
      "label": "Runtime tests: 42 passed, 0 failed"
    },
    {
      "icon": "📝",
      "label": "Final review findings: 0"
    }
  ],
  "quality": {
    "tier": "Diamond",
    "grade": "A+"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 0,
    "summaries": []
  },
  "test_count": 42,
  "tests_added": 4,
  "files_changed": 5
}
```
<!-- celebration-data-end -->
