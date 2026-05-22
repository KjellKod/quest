---
title: UX Guidebook (pointer)
purpose: Locate the canonical UX guidebook, which is bundled as a skill resource so it travels with quest installations.
audience: Contributors and AI agents browsing the docs/guides/ tree.
scope: Pointer page only — content lives in the skill.
status: active
owner: maintainers
---

# UX Guidebook

The canonical UX guidebook is bundled with the `ux-context` skill so it travels with quest installations. Read it here:

- **Guidebook:** [`.skills/ux-context/resources/ux-guidebook.md`](../../.skills/ux-context/resources/ux-guidebook.md)
- **Stress-test rubric:** [`.skills/ux-context/resources/ux-stress-test.md`](../../.skills/ux-context/resources/ux-stress-test.md)

## How it's used

- **Auto-attached** by quest orchestration to planner / builder / fixer agents when the router classifies a quest as `ui_work: true`. The principles primer is loaded as context; the agents shape their output against the canon.
- **Invocable** as `/ux-review` (or `$ux-review`) for direct critique of a file, directory, URL, screenshot, or git diff. The reviewer skill walks the 12-question stress test, the 15-point red-flag diagnostic, the 20-point mobile-feel checklist, and the 15-point Mac-native checklist, then emits structured findings with P0–P3 severity and principle citations.
- **In the quest pipeline**, plan-reviewer and code-reviewer agents automatically invoke `ux-review` when `ui_work: true`, and the resulting findings flow into the canonical review backlog alongside other findings.

## Why this lives in the skill, not in `docs/guides/`

When quest is installed into another repo, the `.skills/` tree is copied; `docs/guides/` is not. Keeping the guidebook inside the `ux-context` skill makes the standard portable — every quest installation carries the same UX canon without a separate sync step.

See `.skills/SKILLS.md` for the full skill index and `.skills/BOOTSTRAP.md` for how skills are discovered and loaded.
