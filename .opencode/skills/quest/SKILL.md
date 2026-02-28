---
name: quest
description: Multi-agent quest orchestration for OpenCode. Delegates to shared workflow.
---

# Quest (OpenCode)

You are running Quest from the OpenCode runtime.

## Setup
1. Read `.ai/allowlist.json` for permissions and model routing (use the `opencode` key under `model_routing`)
2. Read `.skills/quest/delegation/workflow.md` for the full orchestration procedure

## Runtime Notes
- You are the OpenCode orchestrator. Use `task` tool to invoke subagents defined in `.opencode/agents/`
- After each `task` call, verify the expected artifact file exists on disk. If missing, extract content from the response and write it yourself.
- Log runtime as `opencode` in context_health.log
- Review artifacts use `reviewer_a` / `reviewer_b` naming (not claude/codex)
- For dual-model review, use split agents: `plan-reviewer-a` / `plan-reviewer-b` and `code-reviewer-a` / `code-reviewer-b` (different models for independent perspectives)

## Proceed
Follow the procedure in `.skills/quest/delegation/workflow.md` starting from Step 0.
