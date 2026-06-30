---
title: Implementation Plans Index
purpose: Navigation hub for active implementation plans (Layer 3).
audience: Contributors and AI agents building features.
scope: Index of active plans under docs/implementation/.
status: active
owner: maintainers
---

# Implementation Plans

Active, changing plans for in-flight work. Completed plans move to
`docs/implementation/history/` (see `DOCUMENTATION_STRUCTURE.md`). Earlier-stage
proposals live in `ideas/` until they are implementation-ready.

| Plan | Status | Summary |
|------|--------|---------|
| [claude-bg-run-script.md](claude-bg-run-script.md) | implemented (#136) | Step 1: a quest-agnostic standalone `claude --bg` runner (`scripts/claude_bg_run.py` + `tests/unit/test_claude_bg_run.py`, 20 tests green + real-CLI end-to-end incl. needs_human → resume-by-name). Dispatch → confirm → wait-on-files → collect → pid-signal teardown. |
| [claude-bg-transport-migration.md](claude-bg-transport-migration.md) | active — spec | Step 2 rationale + transport contract: migrate Codex-led Claude role execution from the `claude --print` bridge (API-metered after June 15, 2026) to the background-agent transport behind a config switch; bridge kept as an explicit/CI path, not deleted. |
| [claude-bg-transport-step2-wiring.md](claude-bg-transport-step2-wiring.md) | active — in progress | Step 2 execution plan: `claude_role_transport` config (`auto` default), preflight bg probe with user decision on failure, `build_bg_cmd` wiring under `quest_claude_runner.py`, transport callout in summary/celebration, ideas archival, human runbook, self-archival AC. |
