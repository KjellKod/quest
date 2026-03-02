# Idea: OpenCode Integration — Deferred Items

## Origin

Quest `opencode-integration_2026-02-28__1325` code review phase. Both reviewers approved with these non-blocking observations deferred to follow-up after first live test.

Source: `.quest/opencode-integration_2026-02-28__1325/phase_03_review/arbiter_verdict.md`

## Items

### 1. Fixer `scripts/**` permission alignment

The fixer agent in `.opencode/opencode.json` has `"scripts/**": "allow"` for edit permissions, but `.ai/allowlist.json` `fixer_agent` does not list `scripts/**` (only `builder_agent` does). Decide whether fixer should have this permission or remove it for consistency.

### 2. Bash `"*": "ask"` behavior for Codex subagents

Builder and fixer have `"bash": {"*": "ask", ...}` which could trigger interactive approval prompts for non-test bash commands. If Codex subagents hit this path, it may break the non-interactive contract. Evaluate during first live test — if it causes deadlocks, change to explicit deny-with-allows or widen the allow patterns.

### 3. Add `AGENTS.md` reference to fixer and arbiter prompts

Planner, plan-reviewer, builder, and code-reviewer prompts all reference `AGENTS.md` for coding conventions. Fixer and arbiter prompts do not. Add for consistency.

### 4. Missing edit permission patterns from allowlist

`.ai/allowlist.json` grants builder/fixer write access to `*.txt`, `LICENSE*`, and `.ai/**`. The OpenCode config omits these. Evaluate whether they're needed for real quests and add if so.

## Priority

Low. All items are non-blocking and should be validated against actual runtime behavior before fixing. Run a real quest through OpenCode first, then address whatever actually breaks.
