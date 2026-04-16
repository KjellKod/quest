# Quest Journal: pr-inline-commenting-playbook

- Quest ID: `pr-inline-commenting-playbook_2026-03-05__0250`
- Completed: 2026-03-05
- Outcome: Added a practical inline comment playbook to PR shepherd guidance so review replies are kind, precise, and actionable.

## What Shipped

- Added an `Inline Commenting Playbook` section to `.skills/pr-shepherd/SKILL.md`.
- Included comment formula, tone rules, inline scope rules, optional severity labels, signature requirement, and a ready-to-use template.
- Preserved existing PR shepherd workflow and command usage.

## Files Changed

- `.skills/pr-shepherd/SKILL.md`

## Iterations

- Plan iterations: 1
- Fix iterations: 0

## Quest Brief

> # PR Inline Commenting Playbook (Kind + Useful + Slightly Funny)
>
> ## Goal
>
> Make review comments feel like coaching, not scolding.
> Each inline comment should help the author improve the code quickly, with clear next action.
>
> ## Comment Formula
>
> Use this structure for each inline comment:
>
> 1. Start with a small positive anchor.
> 2. Name the issue precisely (what and why).
> 3. Suggest a concrete fix (or two).
> 4. Keep tone warm; add light humor only when it does not hide the problem.
>
> Example shape:
>
> `Nice cleanup here. One tiny gremlin: <specific issue>. Could we <specific fix>?`
>
> ## Tone Rules
>
> - Be kind, not vague.
> - Be direct, not sharp.
> - Humor is optional and brief (one phrase, not a routine).
> - Prefer "could we" / "suggest" over commands.
> - Avoid sarcasm and avoid piling multiple unrelated nits into one comment.
>
> ## Inline Scope Rules
>
> - One comment = one issue.
> - Place comment exactly on the relevant line.
> - For larger concerns, use top-level PR comment with short bullets.
> - If blocking, say why it is blocking in one sentence.
>
> ## Severity Labels (optional but helpful)
>
> - `blocker`: correctness, security, broken behavior
> - `important`: maintainability/readability risk
> - `nit`: style or polish
>
> ## Signature Requirement
>
> Every posted review comment should end with a signature line:
>
> `- Reviewed by <model>, in collaboration with <github username>`
>
> Example:
>
> `- Reviewed by gpt-5.3-codex, in collaboration with KjellKod`
>
> ## Ready-to-Use Comment Template
>
> `Nice improvement here. One small gremlin: <issue>. This can cause <impact>. Suggestion: <specific change>.`
>
> `- Reviewed by <model>, in collaboration with <github username>`

### Archived Brief

`/quest let's implement ideas/pr-inline-commenting-playbook.md`

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/pr-inline-commenting-playbook_2026-03-05.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "unknown",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    }
  ],
  "achievements": [
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 4 reviews"
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
      "label": "Review findings: 4"
    }
  ],
  "quality": {
    "tier": "Diamond",
    "grade": "D"
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 8
}
```
<!-- celebration-data-end -->
