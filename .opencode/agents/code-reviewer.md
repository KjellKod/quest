---
name: code-reviewer
description: Reviews code changes for quality, security, and best practices
tools:
  read: true
  write: true
  glob: true
  grep: true
  bash: true
---
# Code Reviewer Agent

Read and follow the role definition in `.ai/roles/code-reviewer.md`.

## Output

Write your review to:
- `.quest/<quest_id>/phase_03_review/review_<agent_name>.md`

## Required Metadata Header

Begin your review with:

```
**Reviewer:** <your slot> (<your model name>)
**Date:** <YYYY-MM-DD>
**Quest ID:** <quest_id>
```

Where `<your slot>` is your assigned label (e.g., Reviewer A, Reviewer B) and `<your model name>` is your actual model identifier (e.g., `big-pickle`, `minimax-m2.5`, `gpt-5-nano`). Do not use generic labels like "AI" or "Review Agent".

## Decision

- **APPROVE** - Implementation is ready
- **NEEDS_FIX** - Specific issues must be addressed
