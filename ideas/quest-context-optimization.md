# Idea: Quest Context Optimization

## Problem

The Quest orchestrator accumulates context despite the thin-orchestrator design (Phase 2). Three remaining leaks:

1. **TaskOutput transcripts** (~30-50k tokens/quest): Background agents return full transcripts (every tool call, intermediate step) via `TaskOutput`. The orchestrator only needs STATUS/NEXT/SUMMARY.
2. **MCP Codex responses** (~10-20k tokens/quest): Synchronous `mcp__codex__codex` calls return full response text into orchestrator context.
3. **Review file reads** (~5-10k tokens/quest): Orchestrator reads full review files to present summaries to the user.

By the end of a quest with 2 review rounds, the orchestrator has accumulated ~50-80k tokens of agent output that should never have entered its context.

## Proposed Improvements

### 1. handoff.json pattern (biggest win)

Every agent writes a small `handoff.json` alongside its artifacts:

```json
{
  "status": "complete",
  "artifacts": [".quest/<id>/phase_03_review/review_claude.md"],
  "next": "fixer",
  "summary": "Two must-fix issues found: HTML injection, dead code"
}
```

The orchestrator polls for this file instead of calling `TaskOutput`. Zero transcript content enters orchestrator context.

**Implementation:**
- Add handoff.json write instruction to every agent prompt template in workflow.md
- Orchestrator polls: `while not exists(handoff.json): sleep(5)`
- Read handoff.json (tiny), route based on `next` field
- Never call `TaskOutput` for quest agents

### 2. Background all agents

Currently MCP Codex calls are synchronous — their full response enters orchestrator context. Instead:
- Wrap Codex calls in background Task agents
- Task agent calls Codex, writes handoff.json, exits
- Orchestrator only reads handoff.json

This means ALL agents (Claude and Codex) follow the same pattern: background + handoff.json.

### 3. Don't read review content in orchestrator

Currently the orchestrator reads full review files to present summaries. Instead:
- Agent's `handoff.json` summary is sufficient for user-facing status
- User reads full reviews themselves if interested
- Orchestrator only reads handoff.json `next` field for routing

### 4. Post-quest /clear suggestion

Add to Step 7 (Complete) in workflow.md:

```
After showing summary, suggest:
"Quest complete. Consider /clear before your next quest to reset context."
```

### 5. Context budget awareness (future)

Track estimated token usage per phase. If >60% context used, proactively suggest `/compact` or session split.

## Impact Estimate

| Improvement | Tokens saved/quest | Effort |
|---|---|---|
| handoff.json instead of TaskOutput | ~30-50k | Small |
| Background all agents | ~10-20k | Small |
| Post-quest /clear suggestion | Full reset | Trivial |
| Don't read full reviews | ~5-10k | Small |
| Context budget tracking | Prevents overflow | Medium |

## Relationship to Architecture Evolution

This is the natural completion of Phase 2 (thin orchestrator). Phase 2 changed prompts to pass paths instead of content. This phase closes the remaining leaks where content still enters the orchestrator via tool results.

Could be implemented as "Phase 2b" in quest-architecture-evolution.md.
