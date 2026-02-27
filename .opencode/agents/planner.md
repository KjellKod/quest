---
name: planner
description: Creates detailed implementation plans for Quest features
tools:
  read: true
  write: true
  edit: true
  glob: true
  grep: true
  bash: true
---
# Planner Agent

Read and follow the role definition in `.ai/roles/planner.md`.

## Output Format
Write your plan to:
- `.quest/<quest_id>/phase_01_plan/plan.md` - Detailed implementation plan
- `.quest/<quest_id>/phase_01_plan/handoff.json` - Structured handoff data
