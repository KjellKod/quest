# Parallel Reviewer Orchestration

## What
Document and ensure that the Quest orchestrator runs Claude and Codex reviewers **in parallel** during plan review and code review phases.

## Why
- **Performance**: Two reviews running concurrently halves review phase latency
- **Independence**: Each reviewer operates without knowledge of the other's findings
- **Current uncertainty**: Need to verify that "same message, two tool calls" actually achieves parallel execution in practice

## Investigation Findings

### How Claude Code Tool Dispatch Works

When Claude makes **multiple tool calls in the same response message**, they are **executed in parallel by the runtime**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      QUEST ORCHESTRATOR                             │
│                 (Main Claude executing /quest skill)                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Review Phase
                                  │
                    ┌─────────────┴─────────────┐
                    │   SINGLE MESSAGE with     │
                    │   TWO TOOL CALLS          │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   │                   ▼
┌─────────────────────────┐       │       ┌─────────────────────────┐
│   Tool Call 1:          │       │       │   Tool Call 2:          │
│   Task tool             │  PARALLEL     │   mcp__codex__codex     │
│   (plan-reviewer or     │   EXECUTION   │                         │
│   code-reviewer agent)  │       │       │                         │
│                         │       │       │                         │
│  → Spawns Claude        │       │       │  → Calls Codex MCP      │
│    subagent             │       │       │    server               │
└───────────┬─────────────┘       │       └───────────┬─────────────┘
            │                     │                   │
            ▼                     │                   ▼
   review_claude.md               │          review_codex.md
                                  │
              └───────────────────┼───────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │   Runtime collects BOTH   │
                    │   results before          │
                    │   returning to model      │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                          Arbiter phase
```

### Key Facts

1. **Parallel execution is API behavior, not guidance**
   - Claude's API supports multiple `tool_use` blocks in a single response
   - The runtime executes all tool calls from the same message concurrently
   - Results are collected and returned together

2. **Task tool and MCP tool are equivalent at dispatch level**
   - Both are `tool_use` blocks to the Claude API
   - No serialization between them when issued together
   - The difference is in implementation, not execution timing

3. **`run_in_background` has known issues**
   - GitHub Issue #20679: Sessions can hang after background agents complete
   - Notification system is decoupled from TaskOutput
   - **Recommended workaround**: Multiple Task calls in same message WITHOUT the flag

4. **Current skill design is correct**
   - `.skills/quest/SKILL.md` lines 101-144 specify "SAME message, two tool calls"
   - This achieves parallel execution IF the orchestrator follows the instruction

### Potential Issue

The skill **instructs** the orchestrator to use parallel calls, but:
- The orchestrator (main Claude) must actually emit both tool calls in one message
- If Claude generates separate messages, execution becomes sequential
- No enforcement mechanism ensures parallel dispatch

## Approach

### Option A: Trust Current Design (Minimal Change)
The skill already says "same message, two tool calls" - trust that Claude follows this.

**Add to documentation:**
- Explain the parallel execution model in README and guide
- Add the orchestration diagram
- Note that parallelism depends on orchestrator behavior

### Option B: Wrap MCP in Task Agent
Create a thin Task agent that wraps the Codex MCP call:

```
Task(subagent_type="codex-reviewer-wrapper")
  → Agent reads role instructions
  → Agent calls mcp__codex__codex
  → Agent writes review file
```

**Pros:**
- Both reviewers are Task calls - easier to reason about
- Could use `run_in_background: true` on both (if bug is fixed)
- Unified error handling

**Cons:**
- Extra layer of indirection
- Additional latency (agent startup overhead)
- `run_in_background` bug makes this risky today

### Option C: Explicit Parallel Instruction
Add explicit instruction to skill procedure:

```markdown
**CRITICAL: Issue BOTH tool calls in your NEXT response.**
Do NOT make sequential responses. Both tools MUST appear in a single message block.
```

**Pros:**
- Reinforces expected behavior
- No code changes needed

**Cons:**
- Still relies on model compliance

## Acceptance Criteria

1. Documentation updated with orchestration diagram (README.md, quest_presentation.md)
2. Skill procedure has clear "same message" instruction (already present, verify)
3. (Optional) Add observability: log timestamps in review files to verify parallelism

## Open Questions

1. Can we add a hook or validation to detect sequential dispatch?
2. Should we wait for `run_in_background` bug fix before using Task wrappers?
3. Do we need explicit instrumentation to measure actual parallel execution?

## References

- Claude API: Tool use overview - https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- GitHub Issue #20679: Background agents session hang
- `.skills/quest/SKILL.md` lines 101-144 (plan review), 296-349 (code review)

## Status
idea
