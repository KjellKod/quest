---
name: ux-review
description: Run the canonical UX stress-test rubric against a target (file, directory, URL, screenshot, or git diff) and produce a structured critique report with P0–P3 severity, principle citations from the bundled UX guidebook, and a bright-spots section. Used by reviewer agents in the quest pipeline when ui_work=true, and invocable directly with /ux-review or $ux-review.
user-invocable: true
---

At activation, announce the skill name and scope in one line. Example: `[ux-review] reviewing src/components/SettingsPanel.tsx against ux-guidebook`.

Read and follow the instructions in `.skills/ux-review/SKILL.md`.
