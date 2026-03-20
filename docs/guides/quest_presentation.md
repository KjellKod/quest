# Quest: Multi-Agent Orchestration for Claude Code

A deep dive into how Quest coordinates AI agents with human oversight.

For the quick version, see the [README](../../README.md). For setup instructions, see the [Setup Guide](quest_setup.md).

---

## How It Works

This is the default setup. No code changes needed, just ask Claude. You can easily spin up more reviewers, do dual implementations, or change the defaults.

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

1. **Clean context**, each agent starts fresh (no drift)
2. **Dual-model review**, Claude + Codex review plans AND code (different blind spots)
3. **Arbiter**, filters nitpicks, decides "good enough"
4. **Human gates**, you approve before building
5. **Artifacts saved**, full audit trail in `.quest/`

---

## The Problem Quest Solves

Single-agent conversations drift, lose context, and make unreviewed decisions. Long conversations accumulate errors. Planning, reviewing, and implementing blur together. Human approval is ad-hoc or missing entirely.

Quest fixes this with **specialized roles** (planner, reviewer, builder), **clean context** (each role starts fresh), **human gates** (explicit approval before risky actions), and a **full audit trail**.

---

## Under the Hood

### How `/quest` Executes

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

### Clean Context Isolation

Each agent invocation starts fresh:

**Claude agents** (planner, builder, fixer): spawned via Task tool with `subagent_type: general-purpose`. New conversation, prompt includes BOOTSTRAP.md + AGENTS.md + role instructions + artifacts. No history from the orchestrator.

**Codex agents** (reviewers, arbiter): called via `mcp__codex-cli__codex`. Completely separate model (GPT 5.x), prompt assembled by orchestrator.

### Parallel Review Execution

During review phases, the orchestrator dispatches both reviewers in a **single message with two tool calls**. Claude's API executes multiple tool calls from one message concurrently. Each reviewer writes to a separate file (no conflicts), and the runtime waits for both to complete before the arbiter synthesizes.

In **solo mode**, only Reviewer A is dispatched. No Reviewer B, no arbiter. Reviewer A's verdict routes directly to the next phase.

### Human as Gatekeeper

The allowlist (`.ai/allowlist.json`) controls gates:

```json
{
  "auto_approve_phases": {
    "plan_creation": true,
    "plan_review": true,
    "implementation": false,
    "fix_loop": false
  },
  "gates": {
    "require_approval_before_commit": true,
    "require_approval_before_push": true,
    "max_plan_iterations": 4,
    "max_fix_iterations": 3
  }
}
```

You decide when to proceed from planning to building, when to approve fixes, and when to commit and push.

### Where You Spend Your Time

The human workflow is front-loaded and back-loaded. Planning is where you invest attention: reviewing the plan, reading the arbiter's reasoning, sometimes disagreeing. The middle (build, review, fix loops) runs largely on its own. Then after completion, you harden. The quest delivered an MVP that fulfills the plan, but seeing the feature built reveals implications that planning couldn't. Manual validation at this stage is where real understanding happens: you see how the plan was realized, spot hardening opportunities, and often kick off small adjustments or a v2 quest.

Not all code is equal. Critical paths, security boundaries, and architectural decisions warrant manual review even after agents approve. The system handles volume; you handle judgment. This works when you and Quest drive with intention: good test coverage and quality as a first-class constraint, not an afterthought.

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

Exit codes: `0` = allow, `2` = block (message shown to user).

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
  review_plan-reviewer-a.md  # Plan Reviewer A's review
  review_plan-reviewer-b.md  # Plan Reviewer B's review
  arbiter_verdict.md   # Arbiter's decision
phase_02_implementation/
  pr_description.md    # PR description
phase_03_review/
  review_code-reviewer-a.md  # Code Reviewer A's review
  review_code-reviewer-b.md  # Code Reviewer B's review
logs/
  allowlist_snapshot.json  # Permissions at quest start
```

---

## Performance Considerations

Codex MCP calls are slower than Claude Task calls because Codex must read multiple files, analyze content, and write output. A direct Claude call is near-instant; a Codex review call takes 30-60 seconds.

**Tuning options** (edit `.skills/quest/SKILL.md`):

| Approach | Speed | Thoroughness |
|----------|-------|--------------|
| Full context (default) | Slower | More thorough |
| Minimal prompt | Faster | Bullet points only |
| Skip Codex review | Fastest | Claude-only perspective |

---

## Historical Note: The Bash Orchestrator

Quest started as a 1,048-line bash script that parsed natural language via `claude -p`, spawned agents, and extracted JSON handoffs with sed/grep. It worked conceptually but failed practically: FIFO pipe race conditions, heredoc escaping corruption, fragile JSON extraction, and Codex CLI flag changes. 14 of 18 commits were fixes for bash-level problems.

The architecture was sound. The implementation medium was wrong. Claude Code's native Task tool, MCP integration, and skill system solved every problem the bash script fought.

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

---

## Quest Portfolio

### Live Dashboard

See all quest outcomes, status distribution, and drill into individual journal entries:

**[Quest Portfolio Dashboard](https://kjellkod.github.io/quest/)**

### Example Quests

Every completed quest produces a journal entry with a summary, artifacts, and lessons learned:

| Quest | What it did | Journal |
|-------|------------|---------|
| **Phase 4 Role Wiring** | Relocated six Quest role files from `.ai/roles/` to `.skills/quest/agents/`, updated runtime references, validators, metadata, and docs | [journal](https://github.com/KjellKod/quest/blob/main/docs/quest-journal/phase4-role-wiring_2026-02-18.md) |
| **State Validation Script** | Built `validate-quest-state.sh`, the first system-enforced correctness check for Quest phase transitions, with 28-test harness and 10 workflow gates | [journal](https://github.com/KjellKod/quest/blob/main/docs/quest-journal/state-validation-script_2026-02-15.md) |
| **Context Leak Closure** | Implemented `handoff.json` structured file pattern so every agent writes a tiny JSON file and the orchestrator reads routing decisions without processing full responses | [journal](https://github.com/KjellKod/quest/blob/main/docs/quest-journal/context-leak-closure_2026-02-15.md) |
| **Dashboard Layout Redesign** | Restructured dashboard to match executive "Quest Intelligence" design, hero branding, KPI cards, side-by-side charts, card content redesign | [journal](https://github.com/KjellKod/quest/blob/main/docs/quest-journal/dashboard-layout-redesign_2026-02-13.md) |
| **Thin Orchestrator** | Phase 2 of architecture evolution, orchestrator passes paths not content, context stays lean | [journal](https://github.com/KjellKod/quest/blob/main/docs/quest-journal/thin-orchestrator_2026-02-09.md) |
| **Harden URL Rendering** | Fixed XSS vulnerability in dashboard URL rendering, added `_sanitize_url()` with scheme/pattern validation, 7 new tests | [journal](https://github.com/KjellKod/quest/blob/main/docs/quest-journal/harden-url-rendering_2026-02-12.md) |

See the full [Quest Journal](https://github.com/KjellKod/quest/tree/main/docs/quest-journal) for all 21 quests, or browse them on the [dashboard](https://kjellkod.github.io/quest/).

### Architecture Evolution

Quest has evolved through deliberate phases, each driven by a quest:

1. **Phase 1**, Delegation gate and routing
2. **Phase 2**, Thin orchestrator, paths not content
3. **Phase 2b**, Context leak closure with handoff.json
4. **Phase 3**, State validation script with 28 tests
5. **Phase 4**, Role wiring consolidated under `.skills/quest/`
6. **Phase 5**, Infrastructure hooks, assessed and deliberately deferred

See [quest-platform-constellations.md](../architecture/quest-platform-constellations.md) for the current architecture direction.
