---
name: quest
description: Multi-agent quest orchestration. Plans, reviews, builds, and fixes features through coordinated agent handoffs. Use when the user invokes $quest or asks to run/resume Quest workflow.
---

## Codex Runtime Policy

When this Quest is Codex-led and a role is assigned to the Codex runtime, dispatch it through local Codex subagents (`multi_agent_v1.spawn_agent` or the repo-supported equivalent) and inherit the active Codex model by default. Do not set a Codex model name unless the user explicitly requested one or the repo has a tested reason.

Do not use `mcp__codex*`, `codex_codex`, `codex mcp-server`, or Codex CLI model aliases for Codex-led Codex roles. For Codex-led Claude roles, use `scripts/quest_claude_runner.py` when the bridge is available.

Read and follow the instructions in `.skills/quest/SKILL.md`.
