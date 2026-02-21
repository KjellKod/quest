---
name: quest
description: Multi-agent quest orchestration. Plans, reviews, builds, and fixes features through coordinated agent handoffs. Use when the user invokes $quest or asks to run/resume Quest workflow.
---

## Local Repository Enforcement

When running in this repository:
- Follow the full Quest sequence and phase gates from `.skills/quest/delegation/workflow.md`.
- Before Build, only edit `.quest/**` artifacts; do not change project/source files.
- Runtime attribution in `context_health.log` must reflect actual backend/tool used (`claude` vs `codex`), never role labels.
- For PR/merge policy and design rubric, defer to `AGENTS.md` as the single authoritative source.

Read and follow the instructions in `.skills/quest/SKILL.md`.
