---
title: UX Stress Test (pointer)
purpose: Locate the canonical UX stress-test rubric, which is bundled as a skill resource so it travels with quest installations.
audience: Contributors and AI agents browsing the docs/guides/ tree.
scope: Pointer page only — content lives in the skill.
status: active
owner: maintainers
---

# UX Stress Test

The canonical stress-test rubric is bundled with the `ux-context` skill so it travels with quest installations. Read it here:

- **Stress-test rubric:** [`.skills/ux-context/resources/ux-stress-test.md`](../../.skills/ux-context/resources/ux-stress-test.md)
- **Companion guidebook:** [`.skills/ux-context/resources/ux-guidebook.md`](../../.skills/ux-context/resources/ux-guidebook.md)

## What's in it

- **The 12-question rubric** — signifier, feedback, mental model, consistency, error prevention, reversibility, recognition, Fitts, defaults, honesty, density-vs-chrome, scan test. Run before commit.
- **The 15-point red-flags diagnostic** — telltale signs of UI built without UX care. Use to triage a clunky project.
- **The 20-point mobile-feel checklist** — viewport, safe areas, touch targets, thumb zone, virtual keyboard handling.
- **The 15-point Mac-native feel checklist** — menu bar, shortcuts, traffic lights, sidebars, materials, accent color, context menus.

## How to invoke it

- Manually: open the rubric file and walk the checklists.
- With a skill: `/ux-review <path|url|image>` runs the rubric against a target and produces a structured P0–P3 critique with principle citations. See `.skills/ux-review/SKILL.md`.
- In a quest: when the router classifies a quest as `ui_work: true`, the plan-reviewer and code-reviewer agents auto-invoke `ux-review` and emit findings into the canonical review backlog.

See `.skills/SKILLS.md` for the full skill index.
