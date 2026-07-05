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
| _(none currently active)_ | | |

Recently completed and archived to [`history/`](history/): the three
claude-bg-transport specs (Step-1 runner, migration rationale, Step-2 wiring)
— implemented and hardened via PR #136/#137/#141/#142. Their empirical
findings live on in `scripts/claude_bg_run.py`'s module docstring and the
transport test suites; the archived specs remain the record of *why* the
design is shaped the way it is.
