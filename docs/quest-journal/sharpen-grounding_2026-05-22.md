# Quest Journal: sharpen-grounding

- Quest ID: `sharpen-grounding_2026-05-21__0954`
- Slug: sharpen-grounding
- Completed: 2026-05-22
- Mode: workflow
- Quality: Gold
- Celebration: [`celebrations/sharpen-grounding_2026-05-22.md`](celebrations/sharpen-grounding_2026-05-22.md)
- Outcome: Improve the standalone sharpen skill so its questions are grounded in repo evidence when local implementation facts matter. Context: - The canonical skill is `.skills/sharpen/SKILL.md`. - `.agents/...

## What Shipped

Problem: `.skills/sharpen/SKILL.md` currently allows low-context questioning before validating local repo facts, which can produce weak or incorrect challenge questions.

Impact: Sharpen sessions will become evidence-grounded when implementation facts matter, while preserving the existing interac...

## Files Changed

- `.quest/sharpen-grounding_2026-05-21__0954/phase_01_plan/plan.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_01_plan/arbiter_verdict.md.next`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_01_plan/review_findings.json.next`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_02_implementation/pr_description.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_03_review/review_code-reviewer-a.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_03_review/review_code-reviewer-b.md`
- `.quest/sharpen-grounding_2026-05-21__0954/phase_03_review/review_findings_code-reviewer-b.json`

## Iterations

- Plan iterations: 2
- Fix iterations: 0

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 

## Quest Brief

Improve the standalone sharpen skill so its questions are grounded in repo evidence when local implementation facts matter.

Context:
- The canonical skill is `.skills/sharpen/SKILL.md`.
- `.agents/skills/sharpen/SKILL.md` and `.claude/skills/sharpen/SKILL.md` must remain thin wrappers delegating to the canonical skill.
- Quest already invokes sharpen from the plan presentation gate, so implement this as a portable sharpen skill improvement, not Quest-only orchestration.
- Preserve the interactive shape: one question at a time, recommended answer attached, hard cap at 12, progress footer, Resolved/Open/Next exit summary.

Required behavior:
1. Replace the current On entry step 3 with a grounded-before-asking rule.
2. If the artifact references repo/code/tests/scripts/workflows/tools/conventions, run a bounded grounding pass before Q1:
   - session-wide cap: at most 5 targeted reads and 3 targeted searches unless the user explicitly asks for deeper investigation
   - extract anchors from the artifact: paths, commands, scripts, tests, modules, acceptance criteria
   - verify the highest-impact anchors in the current checkout
   - skip questions answered by those facts and log them in Resolved
   - if no repo/local surface exists, use artifact-only grounding and do not pretend local evidence exists
   - if a search returns more than 50 hits, accept partial grounding and disclose the uncertainty in the question
3. Use per-question grounding. When local facts matter, include a short Grounded on: block before the question.
4. Revise Take a position so recommendations cite grounding facts when facts support the recommendation.
5. Add contradiction handling:
   - if grounding contradicts a plan claim and blocks the rest of the tree, make it Q1: The plan says X. I found Y in path:line. Which is correct?
   - if the contradiction is fully resolved by local evidence, log it under Resolved and ask the next high-impact unresolved question.
6. Add the smoke-runner before/after example to the skill, but keep it generic and portable.

Tests:
- Update `tests/unit/test_sharpen_install_surface.py` to assert the grounding contract.
- Replace the brittle assertion that the canonical skill cannot mention Quest with a portability assertion that forbids Quest-only dependencies such as `.quest/`, `quest_state.py`, `.skills/quest`, or planner/builder/reviewer role requirements.
- Preserve wrapper tests proving `.agents` and `.claude` sharpen files are thin delegates.
- Add tests that preserve the interview shape and prevent the skill from becoming a planner/code reviewer.

Validation:
- Run `python3 -m pytest tests/unit/test_sharpen_install_surface.py tests/unit/test_codex_skill_wrappers.py tests/unit/test_quest_manifest.py -q`
- Run `bash scripts/quest_validate-manifest.sh`

Use `quest:workflow`. Stop at the normal build approval gate before editing source files.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/sharpen-grounding_2026-05-22.md`](celebrations/sharpen-grounding_2026-05-22.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/sharpen-grounding_2026-05-22.md`

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
      "desc": "Tackled 5 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 4 reviews"
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
      "label": "Fix iterations: 0"
    },
    {
      "icon": "📝",
      "label": "Review findings: 4"
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
  "files_changed": 11
}
```
<!-- celebration-data-end -->
