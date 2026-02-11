# Quest: Multi-Agent Orchestration for Claude Code

A presentation on coordinated AI agents with human oversight.

---

## TL;DR

**Quest** is a multi-agent workflow where specialized AI agents (planner, reviewers, builder) work in **isolated contexts** with **human approval gates**. Two different models (Claude + GPT) review independently, an arbiter filters nitpicks, and you approve before anything gets built. All artifacts are saved for audit.

**One sentence:** *"Structured AI teamwork with checks and balances."*

```
┌─────────────── PLAN PHASE ───────────────┐    ┌─────────── BUILD PHASE ───────────┐
│                                          │    │                       Arbiter     │
│  You → Planner → Reviewers → Arbiter  ───┼────→  Builder → Reviewers ──│──────────│──→ Done
│            ▲      (Claude)      │        │    │              (Claude)  │          │
│            │      (Codex)       │        │    │              (Codex)   │          │   
│            └───── iterate ──────┘        │    │                 │      │          │
│                                          │    │                 ▼      │          │
│                                          │    │              Fixer ────┘          │
│                                          │    │           (if issues)             │
└──────────────────────────────────────────┘    └───────────────────────────────────┘
                                   ▲
                                GATE: human approval
```

---

## How It Works
This is the default setup, without any code changes, just asking Claude, it'll spin up more reviewers, or do dual-implementations etc. It's easy to change the default. 

The point is: we don't trust the individual contributor, we trust the process of checks and balances.

```
                        YOU
                         │
                         ▼
                   ┌───────────┐
                   │   /quest  │
                   │  "add X"  │
                   └─────┬─────┘
                         │
                         ▼
                   ┌─────────┐
                   │ Planner │
                   │ (Claude)│
                   └────┬────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    ┌──────────┐                 ┌──────────┐
    │ Reviewer │                 │ Reviewer │
    │ (Claude) │                 │ (Codex)  │
    └────┬─────┘                 └────┬─────┘
         └──────────────┬─────────────┘
                        ▼
                   ┌─────────┐
                   │ Arbiter │──▶ iterate? ──┐ ──▶ [Back to Planner]
                   │ (Claude)│               │
                   └────┬────┘               │
                        │ approve            │
                        ▼                    │
                   ┌────┴────┐               │
                   │  GATE   │◀── You        │
                   └────┬────┘    approve    │
                        │                    │
                   ┌────┴────┐               │
                   │ Planner │◀──────────────┘
                   └────┬────┘
                        ▼
                   ┌─────────┐
                   │ Builder │
                   │ (Claude)│
                   └────┬────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
    ┌──────────┐                 ┌──────────┐
    │ Code     │                 │ Code     │
    │ Reviewer │                 │ Reviewer │
    │ (Claude) │                 │ (Codex)  │
    └────┬─────┘                 └────┬─────┘
         └──────────────┬─────────────┘
                        │
                        ▼
                   ┌─────────┐
                   │ Arbiter │
                   │ (Claude)│               
                   └────┬────┘               
                        │
                        │
              issues? ──┴── clean?
                 │            │
                 ▼            ▼
            ┌─────────┐  ┌──────────┐
            │  Fixer  │  │ PR Draft │
            │ (Claude)│  │(refs plan)│
            └────┬────┘  └────┬─────┘
                 │            │
                 │            ▼
                 │       ┌─────────┐
                 │       │   You   │
                 │       │ review  │
                 │       └────┬────┘
                 │            │
                 │            ▼
                 │       ┌────────┐
                 │       │  DONE  │
                 │       └────────┘
                 │
                 └───▶ Code Review (loop) ──▶ [Back Arbiter]
```

### Key Points

1. **Clean context** — each agent starts fresh (no drift)
2. **Dual-model review** — Claude + Codex review plans AND code (different blind spots)
3. **Arbiter** — filters nitpicks, decides "good enough"
4. **Human gates** — you approve before building
5. **Artifacts saved** — full audit trail in `.quest/`

---

## The Problem

### AI agents are powerful but risky

- Single-agent conversations drift, lose context, make unreviewed decisions
- Long conversations accumulate errors and hallucinations
- No separation of concerns: planning, reviewing, and implementing blur together
- Human approval gates are ad-hoc or missing entirely

### We need structure

- **Specialized roles** — planner, reviewer, builder, each with clear responsibilities
- **Clean context** — each role starts fresh, no inherited confusion
- **Human gates** — explicit approval points before risky actions
- **Audit trail** — all decisions and artifacts are preserved

---

## High-Level Idea

### Multi-agent orchestration with handoffs

```
Human
  ↓
Quest Agent (orchestrator)
  ↓
┌─────────────────────────────────────────────────┐
│  Plan Phase                                      │
│  ┌──────────┐    ┌──────────┐   ┌──────────┐   │
│  │ Planner  │ →  │ Reviewer │ → │ Arbiter  │   │
│  │ (Claude) │    │ (Claude) │   │ (Codex)  │   │
│  └──────────┘    │ (Codex)  │   └────┬─────┘   │
│                  └──────────┘        │         │
│                              approve/iterate    │
└─────────────────────────────────────────────────┘
  ↓ (human gate)
┌─────────────────────────────────────────────────┐
│  Build Phase                                     │
│  ┌──────────┐    ┌──────────┐   ┌──────────┐   │
│  │ Builder  │ →  │ Reviewer │ → │ Fixer    │   │
│  │ (Claude) │    │ (Claude) │   │ (Claude) │   │
│  └──────────┘    │ (Codex)  │   └──────────┘   │
│                  └──────────┘                   │
└─────────────────────────────────────────────────┘
  ↓
Human reviews final result
```

### Key principles

1. **Each agent has clean context** — starts fresh with only the artifacts it needs
2. **Dual-model review** — Claude AND Codex review independently (different blind spots)
3. **Arbiter prevents spin** — synthesizes feedback, enforces KISS/YAGNI, decides "good enough"
4. **Human is the gatekeeper** — explicit approval before implementation, commits, pushes

---

## Solution 1: Bash Orchestrator (Discarded)

### What we built

A 1,048-line bash script (`scripts/quest`) that:
- Parsed natural language intent via `claude -p`
- Spawned agents via `claude -p` and `codex exec`
- Extracted JSON handoffs with sed/grep
- Managed state via file existence

### Why it failed

| Problem | Impact |
|---------|--------|
| FIFO pipe race conditions | Random hangs, lost output |
| Heredoc escaping | Prompts corrupted by special characters |
| JSON extraction from free text | 3 fallback methods, still fragile |
| Codex CLI flag changes | Broke on CLI updates |
| Stdout contamination | Agent output mixed with orchestrator logs |

**14 of 18 commits were fixes for bash-level problems.**

The architecture was sound. The implementation medium was wrong.

---

## Solution 2: Claude Code Native (Current)

### The insight

Claude Code already has:
- **Task tool** — spawns subagents with clean context
- **MCP integration** — calls external models (Codex/GPT 5.2)
- **Hook system** — intercepts tool calls for permission enforcement
- **Skill system** — packages procedures as `/commands`

**Don't fight the platform. Use it.**

### How it works

```
/quest "add a loading skeleton"
        ↓
   Claude reads .skills/quest/SKILL.md
        ↓
   Claude becomes the Quest Agent
        ↓
   Follows numbered procedure:
   1. Create quest folder + brief
   2. Spawn planner (Task tool → clean context)
   3. Spawn reviewers (Task + MCP → clean context)
   4. Spawn arbiter (MCP → clean context)
   5. Check verdict, loop or proceed
   6. Gate: ask human before building
   7. Spawn builder, reviewer, fixer as needed
   8. Present results to human
```

---

## Solution 2: Details

### Clean Context Isolation

Each agent invocation starts fresh:

**Claude agents** (planner, builder, fixer):
```
Task tool with subagent_type: general-purpose
  → New conversation
  → Prompt includes: BOOTSTRAP.md + AGENTS.md + role instructions + artifacts
  → No history from orchestrator conversation
```

**Codex agents** (plan reviewers, code reviewers):
```
mcp__codex__codex(prompt: "...")
  → New Codex session
  → Prompt assembled by orchestrator
  → Completely separate model (GPT 5.2)
```

### Parallel Review Execution

During review phases, the orchestrator dispatches **both reviewers in a single message** to achieve parallel execution:

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
│   (Claude subagent)     │   EXECUTION   │   (Codex MCP server)    │
│                         │       │       │                         │
│  → plan-reviewer or     │       │       │  → GPT-5.2 reviews      │
│    code-reviewer agent  │       │       │    same artifacts       │
└───────────┬─────────────┘       │       └───────────┬─────────────┘
            │                     │                   │
            ▼                     │                   ▼
   review_claude.md               │          review_codex.md
                                  │
              └───────────────────┼───────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │   Runtime collects BOTH   │
                    │   results, then continues │
                    └─────────────┴─────────────┘
                                  │
                                  ▼
                          Arbiter synthesizes
```

**Key points:**
- Both tools appear in the **same Claude response message**
- Claude's API executes multiple tool calls from one message **concurrently**
- The runtime waits for both to complete before returning to the model
- Each reviewer writes to a separate file (idempotent, no conflicts)

**Why this works:**
- Task tool calls spawn subagents
- MCP tool calls invoke external servers
- Both are `tool_use` blocks at the API level — no serialization between them

### Human as Gatekeeper

The allowlist (`.ai/allowlist.json`) controls gates:

```json
{
  "auto_approve_phases": {
    "plan_creation": true,      // Auto-proceed
    "plan_review": true,        // Auto-proceed
    "implementation": false,    // STOP: Ask human
    "fix_loop": false           // STOP: Ask human
  },
  "gates": {
    "require_approval_before_commit": true,
    "require_approval_before_push": true,
    "max_plan_iterations": 4,
    "max_fix_iterations": 3
  }
}
```

**The human decides:**
- When to proceed from planning to building
- When to approve fixes
- When to commit and push

### Where You Spend Your Time

The human workflow is front-loaded and back-loaded. Planning is where you invest attention: reviewing the plan, reading the arbiter's reasoning, sometimes disagreeing. The middle (build, review, fix loops) runs largely on its own. Then after completion, you harden. The quest delivered an MVP that fulfills the plan — but seeing the feature built reveals implications that planning couldn't. Manual validation at this stage is where real understanding happens: you see how the plan was realized, spot hardening opportunities, and often kick off small adjustments or a v2 quest.

Not all code is equal. Critical paths, security boundaries, and architectural decisions warrant manual review even after agents approve. The system handles volume; you handle judgment. This works when you and Quest drive with intention: good test coverage and quality as a first-class constraint, not an afterthought.

### Permission Enforcement

Hook script enforces per-role permissions:

```bash
# .claude/hooks/enforce-allowlist.sh
# Called on every Write/Edit/Bash tool use

# Planner can only write to:
"file_write": [".quest/**", "docs/implementation/**"]

# Builder can write to source + tests:
"file_write": [".quest/**", "src/**", "tests/**"]

# Reviewers can only write to .quest/:
"file_write": [".quest/**"]
```

Exit codes:
- `0` = allow
- `2` = block (message shown to user)

### Arbiter Prevents Spin

The Arbiter is the gatekeeper for plan quality:

- Receives both Claude and Codex reviews
- Filters nitpicks using KISS/YAGNI/SRP principles
- Max 5 meaningful issues per iteration
- **Bias toward action**: when in doubt, approve

```
Iteration 1: "3 issues found, iterate"
Iteration 2: "1 issue found, iterate"
Iteration 3: "Remaining feedback is cosmetic, APPROVE"
```

### State Persistence

Quest state survives conversation restarts:

```json
// .quest/<id>/state.json
{
  "quest_id": "feature-x_2026-02-02__1430",
  "phase": "plan",
  "plan_iteration": 2,
  "last_role": "arbiter_agent",
  "last_verdict": "iterate"
}
```

Resume with: `/quest feature-x_2026-02-02__1430`

### Audit Trail

All artifacts preserved in `.quest/<id>/`:

```
phase_01_plan/
  plan.md              # The implementation plan
  review_claude.md     # Claude's plan review
  review_codex.md      # Codex's plan review
  arbiter_verdict.md   # Arbiter's decision
phase_02_implementation/
  pr_description.md    # PR description
phase_03_review/
  review_claude.md     # Claude's code review
  review_codex.md      # Codex's code review
logs/
  allowlist_snapshot.json  # Permissions at quest start
```

---

## Portability: Reuse in Another Repo

### Files to copy

```
.ai/                              # Source of truth (AI-agnostic)
  allowlist.json                  # Edit for your repo's paths
  roles/*.md                      # Agent role definitions
  schemas/                        # Handoff contract
  templates/                      # Document templates

.claude/                          # Claude Code integration
  skills/quest/SKILL.md           # Thin wrapper → .skills/
  agents/*.md                     # Thin wrappers → .ai/roles/
  hooks/enforce-allowlist.sh      # Permission enforcement

.skills/quest/SKILL.md            # The actual skill procedure
```

### Setup steps

1. **Copy folders**: `.ai/`, `.claude/`, `.skills/quest/`

2. **Edit allowlist** for your project:
   ```json
   "builder_agent": {
     "file_write": [".quest/**", "your-src/**", "your-tests/**"],
     "bash": ["your-test-command", "your-build-command"]
   }
   ```

3. **Add to .gitignore**:
   ```
   .quest/
   ```

4. **Optional: Configure Codex MCP** (if using GPT 5.2):
   ```bash
   claude mcp add codex -- npx -y @anthropic/codex-mcp-server
   ```

5. **Test**:
   ```
   /quest "add a simple feature"
   ```

### Why it's portable

| Component | Location | Why |
|-----------|----------|-----|
| Role definitions | `.ai/roles/` | AI-agnostic, works with any tool |
| Permissions | `.ai/allowlist.json` | Plain JSON, human-editable |
| Skill procedure | `.skills/quest/` | AI-agnostic, could work with other orchestrators |
| Claude Code config | `.claude/` | Thin wrappers that delegate to `.ai/` and `.skills/` |

**The source of truth is always in AI-agnostic locations.** Claude Code integration is just a thin layer on top.

---

## Performance Considerations

### Codex MCP Latency

Codex MCP calls are slower than Claude Task calls because Codex must:
1. Read multiple files (instructions, context, plan)
2. Analyze content
3. Write output file

**Direct Claude call:** "list files" → instant
**Codex review call:** read 5 files + analyze + write → 30-60 seconds

### Tuning Options

Edit `.skills/quest/SKILL.md` to customize Codex prompts:
- **Line ~103** — Plan Reviewer (Codex) prompt
- **Line ~177** — Code Reviewer (Codex) prompt

**Speed vs thoroughness tradeoff:**

| Approach | Speed | Thoroughness |
|----------|-------|--------------|
| Full context (default) | Slower | More thorough |
| Minimal prompt | Faster | Bullet points only |
| Skip Codex review | Fastest | Claude-only perspective |

**Example minimal prompt:**
```
"Review .quest/<id>/plan.md
 List issues (max 5 bullets).
 Write to review_codex.md"
```

---

## Summary

| Aspect | How Quest Handles It |
|--------|---------------------|
| Context pollution | Task tool + MCP = clean context per agent |
| Review quality | Dual-model review (Claude + Codex) |
| Nitpick spin | Arbiter filters with KISS/YAGNI/SRP |
| Human oversight | Gates at implementation, commit, push |
| Permission enforcement | PreToolUse hook checks allowlist |
| State persistence | state.json survives restarts |
| Audit trail | All artifacts in .quest/ folder |
| Portability | Source of truth in .ai/ and .skills/ |
| Customization | Edit prompts in .skills/quest/SKILL.md |

**The result**: Structured, auditable, human-gated AI workflows that leverage Claude Code's native capabilities instead of fighting them.
