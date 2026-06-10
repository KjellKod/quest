---
name: quest
description: Multi-agent quest orchestration. Plans, reviews, builds, and fixes features through coordinated agent handoffs. Use when the user invokes $quest or asks to run/resume Quest workflow.
---

## Codex Runtime Policy

Codex-led Codex roles use local Codex subagents and never use Codex MCP. The canonical dispatch matrix (runtime + entrypoint per orchestrator) is `.skills/quest/delegation/workflow.md` (Runtime And Entrypoint Selection); this wrapper intentionally does not restate it.

Read and follow the instructions in `.skills/quest/SKILL.md`.
