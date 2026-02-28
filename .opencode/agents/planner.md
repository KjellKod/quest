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

## Output

Write your plan to:
- `.quest/<quest_id>/phase_01_plan/plan.md` - Detailed implementation plan
- `.quest/<quest_id>/phase_01_plan/handoff.json` - Structured handoff data

## Required Metadata Header

Begin your plan with:

```
**Planner:** <your model name>
**Date:** <YYYY-MM-DD>
**Quest ID:** <quest_id>
```

Use your actual model identifier (e.g., `big-pickle`, `minimax-m2.5`, `gpt-5-nano`). Do not use generic labels like "AI" or "Planner Agent".
