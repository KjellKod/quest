# Ideas

Future work items not yet ready for a full quest. When an idea is ready, run `/quest` to turn it into a quest run.

## Index

| Status | Idea | Elevator pitch |
|--------|------|---------------|
| | [user-feedback](user-feedback.md) | Real-world user feedback on Quest UX: cost transparency, smart pausing, status clarity, plan navigation. |
| in-progress | [quest-architecture-evolution](quest-architecture-evolution.md) | 5-phase roadmap to close the gap between Quest's philosophy and implementation. Phase 2 done, 2b in progress. |
| in-progress | [quest-context-optimization](quest-context-optimization.md) | Close remaining context leaks: handoff.json pattern, background agents, /clear suggestion. |
| | [quest-step-numbering-cleanup](quest-step-numbering-cleanup.md) | Fix step numbering overlap between SKILL.md and workflow.md after the delegation refactor. |
| | [quest-council-mode](quest-council-mode.md) | `/quest council` — two competing plans, independent reviews, council arbiter comparison report, human picks winner + optional golden nuggets. |
| dropped | ~~quest-council_v1~~ | Superseded by quest-council-mode. |
| dropped | ~~quest-council_v1_alternative~~ | Superseded by quest-council-mode. |
| | [gpt52-default-planner](gpt52-default-planner.md) | Make GPT the default planner to diversify model perspective earlier in the pipeline. |
| | [codex-quest-skill](codex-quest-skill.md) | GPT-only quest runner via Codex CLI — run quests without Claude Code. |
| | [parallel-reviewer-orchestration](parallel-reviewer-orchestration.md) | Ensure Claude and Codex reviewers run in parallel during review phases. |
| | [github-ci-pr-validation](github-ci-pr-validation.md) | CI workflow to validate quest plan structure on pull requests. |
| | [quest-abandon-flow](quest-abandon-flow.md) | `/quest abandon <id>` command — formal abandon with journal entry, state update, and archive cleanup. |
| | [quest-readme-auto-update](quest-readme-auto-update.md) | Auto-update `.quest/README.md` index when a quest completes. |
| | [memory_bank_model](memory_bank_model.md) | Curated repo docs as the AI's authoritative mental model instead of scanning files. |
| | [quest-completion-gate](quest-completion-gate.md) | When is a quest really done? Weigh trade-offs: close at review approval, close at PR merge, or soft close with hardening breadcrumbs. |
| done | ~~quest-intake-gate~~ | Delegation-based intake gate with question-first routing for vague input. See [journal](../docs/quest-journal/quest-delegation-gate_2026-02-06.md). |
| done | ~~handoff-fix-plan~~ | Standardize `---HANDOFF---` contracts across all role files. See [journal](../docs/quest-journal/handoff-contract-fix_2026-02-09.md). |
| done | ~~quest-philosophy-small-core~~ | Thin orchestrator philosophy, handoff contracts, delegation workflow. See [journal](../docs/quest-journal/thin-orchestrator_2026-02-09.md). |
| done | ~~dashboard-visual-polish~~ | Ambient glows, Chart.js charts, gradient enhancements. See [journal](../docs/quest-journal/dashboard-visual-polish_2026-02-12.md). |
| done | ~~dashboard-layout-redesign~~ | Executive "Quest Intelligence" design — hero branding, KPI cards, side-by-side charts, unified portfolio. See [journal](../docs/quest-journal/dashboard-layout-redesign_2026-02-13.md). |
| dropped | ~~default-quest-planner~~ | Brainstorm about configurable planner models. Superseded by gpt52-default-planner idea. |
| dropped | ~~fixer~~ | One-line question about fixer routing. Never developed. |
| dropped | ~~update_details~~ | UX brainstorm about update check UI. Never developed. |

**Legend:** blank = not started, in-progress = active idea being implemented, done = implemented (file removed), dropped = discarded (file removed)

## Format

Each idea is a brief markdown file with:

```markdown
# Idea Title

## What
Brief description.

## Why
Why this would be useful.

## Approach
Rough implementation ideas (optional).

## Status
idea | in-progress | implemented | rejected
```

## When to Graduate to a Quest

Run `/quest "your idea description"` to turn an idea into a quest run under `.quest/`.
