# GPT-5.2 as Default Planner

## What
Make `gpt-5.2` (via Codex MCP) the default model for the planner agent, with Claude as fallback.

## Why
Currently Claude handles orchestration + planning + one review track. Moving planning to gpt-5.2 would:
- Diversify model perspective earlier in the pipeline (at planning, not just review)
- Match the existing pattern used for reviewers and arbiter
- Keep Claude focused on orchestration and its review track

## Approach
- Add `planner.tool` field to `.ai/allowlist.json` (default: `"codex"`)
- Adapt SKILL.md Step 3 to invoke `mcp__codex__codex` for the planner, same pattern as reviewer/arbiter Codex calls
- Point Codex at: role doc, quest brief, plan-maker skill, context digest
- Keep Claude subagent as fallback if Codex MCP fails
- Update `planner_agent.md` Tool field to reflect configurable default

## Considerations
- Planner needs codebase exploration (grep, file reads) — heavier Codex session than reviewer/arbiter
- Expect longer Codex calls for planning vs review
- Fallback to Claude must be seamless

## Status
idea
