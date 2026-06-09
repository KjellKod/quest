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
| [claude-bg-transport-migration.md](claude-bg-transport-migration.md) | draft — for review | Migrate Codex-led Claude role execution from the `claude --print` bridge (API-metered after June 15, 2026) to the official background-agent transport (`claude --bg` + supervisor, subscription pool); bridge demoted to fallback/CI path, not deleted. |
