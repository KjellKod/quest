# Quest Journal: Portable Pre-Commit Review Skill

- Quest ID: `portable-pre-commit-review_2026-04-27__1211`
- Completed: 2026-04-27
- Mode: workflow
- Quality: Gold
- Outcome: Completed successfully.

## What Shipped

**Problem**: Quest installs review skills for plans and PRs, but installed repos do not have a portable way to review the local working-tree diff before a PR exists.

**Impact**: Developers in repos installed via `quest_installer` can invoke a local pre-commit review before committing or opening ...

## Files Changed

- `plan.md`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_01_plan/arbiter_verdict.md.next`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_01_plan/review_findings.json.next`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_02_implementation/pr_description.md`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_02_implementation/builder_feedback_discussion.md`
- `.skills/pre-commit-review/SKILL.md`
- `.skills/SKILLS.md`
- `.agents/skills/pre-commit-review/SKILL.md`
- `.claude/skills/pre-commit-review/SKILL.md`
- `.opencode/commands/pre-commit-review.md`
- `.quest-manifest`
- `tests/unit/test_codex_skill_wrappers.py`
- `tests/unit/test_pre_commit_review_install_surface.py`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_03_review/review_code-reviewer-a_iter1.md`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_03_review/review_findings_code-reviewer-a_iter1.json`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_03_review/review_code-reviewer-b_iter1.md`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_03_review/review_findings_code-reviewer-b_iter1.json`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_03_review/handoff_code-reviewer-b.json`
- `.quest/portable-pre-commit-review_2026-04-27__1211/phase_03_review/review_fix_feedback_discussion.md`

## Iterations

- Plan iterations: 2
- Fix iterations: 1

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 

## Quest Brief

```text
Implement the portable pre-commit review skill from ideas/2026-04-22-review-ergonomics-and-team-preference-memory.md.

Goal:
Add an installed Quest skill that reviews the local working-tree diff before a PR exists, so repos installed via quest_installer benefit directly.

Scope:
1. Add `.skills/pre-commit-review/SKILL.md`.
   - Review staged + unstaged `git diff` by default.
   - Reuse `.skills/code-reviewer/SKILL.md` severity model.
   - Reuse `.skills/review-anti-patterns.md`.
   - Output numbered findings in `[N]` current-review order.
   - Include a clear terminal decision flow: fix selected / fix all Must / skip / commit.
   - Never push.
   - Refuse with a clear message when no git repo is available or the working tree diff is empty.

2. Add installed wrapper / catalog entries.
   - Update `.skills/SKILLS.md`.
   - Add any relevant `.agents/skills/`, `.claude/skills/`, or `.opencode/commands/` wrapper if that is the established installed pattern.
   - Ensure every installed file is represented in `.quest-manifest`.

3. Runtime or helper scripts only if needed.
   - Prefer skill instructions first.
   - If adding a helper script, keep it installer-managed, narrowly scoped, and tested.

Installer portability:
- This must benefit repos installed via `quest_installer`, not only the Quest repo.
- Do not depend on files under `ideas/`, `docs/`, or `.github/` at runtime.
- For every changed/added installed file, verify it is listed in `.quest-manifest`.
- Do not modify `.ai/allowlist.json` unless strictly required; if required, keep the merge impact minimal and document it.

Constraints:
- Do not implement team-preference memory.
- Do not implement pr-shepherd rename.
- Do not implement fix-loop checkpoint commits.
- Do not add GitHub CI workflows.
- Preserve the existing review-decision taxonomy: `fix_now`, `verify_first`, `defer`, `drop`, `needs_human_decision`.

Validation:
- bash scripts/quest_validate-manifest.sh
- bash tests/test-quest-runtime.sh
- Add or update focused tests for manifest/catalog/wrapper behavior if new installed files are added.
- Manually verify the new skill text clearly handles: no git repo, empty diff, staged+unstaged diff, numbered findings, and no-push behavior.

PR title:
Add portable pre-commit review skill
```

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/portable-pre-commit-review_2026-04-27.md`

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
      "desc": "Tackled 8 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 7 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 2 times"
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
      "label": "Plan iterations: 2"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 1"
    },
    {
      "icon": "📝",
      "label": "Review findings: 7"
    }
  ],
  "quality": {
    "tier": "Gold",
    "grade": "G"
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
  "files_changed": 21
}
```
<!-- celebration-data-end -->
