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
| [claude-bg-run-script.md](claude-bg-run-script.md) | PoC landed — for review | Step 1: a quest-agnostic standalone `claude --bg` runner (`scripts/claude_bg_run.py` + `tests/unit/test_claude_bg_run.py`, 12 tests green + real-CLI smoke). Dispatch → confirm → wait-on-files → collect → teardown, with a headless-PTY noise firewall. |
| [claude-bg-transport-migration.md](claude-bg-transport-migration.md) | draft — for review | Step 2 (later): migrate Codex-led Claude role execution from the `claude --print` bridge (API-metered after June 15, 2026) to the background-agent transport behind a config switch; bridge demoted to fallback/CI path, not deleted. |
