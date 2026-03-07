# How Quest Routes Your Input

When you run `/quest`, the system evaluates your input before deciding what to do next. Depending on how much detail you provide and how complex the task is, Quest decides whether to ask questions, which workflow mode to use, or whether you need a quest pipeline at all.

This guide explains the routing logic, what the questioning phase looks like, how complexity routing works, and how you can override any recommendation.

## How Quest Routes Your Input

```
/quest "your input"
       │
       ├── Quest ID provided?  ──yes──>  Resume existing quest
       │
       └── New quest  ──>  Evaluate input substance
                                │
                                ├── Gaps detected (confidence < 0.70)
                                │       └── Ask questions first ──> Re-evaluate
                                │
                                └── Enough detail  ──>  Complexity × Risk routing
                                        │
                                        ├── trivial + low risk  ──>  Exit (no quest needed)
                                        ├── moderate complexity  ──>  Solo or full quest (depends on risk)
                                        └── substantial / high risk  ──>  Full quest (dual reviews)
```

### Path 1: Resume an Existing Quest

If your argument looks like a quest ID (e.g., `feature-x_2026-02-04__1430`), Quest picks up where you left off. It reads the saved state and jumps to the right phase — whether that's planning, building, reviewing, or showing a completed summary.

### Path 2: Detailed Input — Complexity Routing

When your input has enough substance, Quest runs it through the complexity × risk matrix to determine which route to recommend. Depending on the task, that might be a solo quest (single reviewer, lighter process), a full quest (dual reviews, arbiter), or an exit from the pipeline entirely for trivial tasks.

### Path 3: Thin Input — Questioning First, Then Routing

When your input has significant gaps, Quest enters a structured questioning phase to gather what it needs. Once questioning is complete, the enriched input goes through the same complexity × risk routing as Path 2.

When the router determines a task is trivial and low-risk, it recommends exiting the quest system entirely — no folder, no artifacts, no pipeline. You just do it directly. This isn't a quest mode; it's Quest recognizing the task doesn't need one.

## How Quest Evaluates Your Input

Quest assesses your input across seven dimensions:

| Dimension | What it looks for | Example (present) | Example (missing) |
|-----------|------------------|-------------------|-------------------|
| **Deliverable** | A concrete thing being built or changed | "Add email validation to the registration form" | "Make things better" |
| **Scope** | Which parts of the system are affected | "Changes to src/components/Form.tsx only" | No indication of where |
| **Success criteria** | How to know it's done | "Errors shown inline, password requires 8+ chars" | No definition of done |
| **Constraints** | Technical limits, dependencies, targets | "No new dependencies, must support IE11" | Nothing mentioned |
| **Input artifacts** | Referenced specs, docs, tickets, files | "See spec in docs/design/auth-flow.md" | No references |
| **Testing** | How it should be tested | "Unit tests for validation logic" | Not mentioned |
| **Deployment** | Rollout, migration, compatibility | "Needs database migration, feature flag" | Not mentioned |

**What makes input "detailed enough"?** Generally: the deliverable is clear, scope is at least partially defined, and no more than two dimensions are missing. A short prompt that references a detailed spec file counts as rich input. A long prompt with no scope or acceptance criteria counts as thin input. Length doesn't matter — substance does.

**Risk also matters.** High-risk domains (migrations, security, payments, data loss) bias toward questioning even when most dimensions are present, because mistakes are costlier.

## Complexity Routing

Once Quest has enough substance (either from your original input or after questioning), it assesses the **complexity** of the task and combines it with the **risk level** to determine the route.

### Three Complexity Levels

| Level | Signal | Examples |
|-------|--------|----------|
| **Trivial** | Single file, config change, docs, small bug fix | "Fix typo in README", "Add env var to config" |
| **Moderate** | Multi-file change within one module, new function/endpoint, focused refactor | "Add validation to registration form", "Refactor logger to use structured output" |
| **Substantial** | Cross-cutting changes, new module, architecture, security-sensitive | "Add OAuth2 flow", "Migrate database schema", "Implement plugin system" |

### The Complexity × Risk Matrix

This matrix determines which route Quest recommends:

| Risk \ Complexity | Trivial | Moderate | Substantial |
|-------------------|---------|----------|-------------|
| **Low** | Exit | Solo | Full quest |
| **Medium** | Solo | Solo | Full quest |
| **High** | Full quest | Full quest | Full quest |

- **Exit** — Quest suggests you skip the pipeline. No quest folder, no artifacts. You just do the work directly.
- **Solo** — Lightweight quest: single plan reviewer, no arbiter, single code reviewer, capped fix iterations. Same pipeline, fewer stages.
- **Full quest** — The works: dual reviewers (Claude + Codex), arbiter synthesis, full fix loop.

## Solo Mode

Solo mode is a lighter version of the same quest pipeline — not a separate system. Here's what changes:

- **Single plan reviewer** (Reviewer A only — no Reviewer B)
- **No arbiter** — Reviewer A's verdict routes directly to the next step, either forward or back for another iteration
- **Single code reviewer** (Reviewer A only)
- **Fix iterations capped** at `min(solo.max_fix_iterations, allowlist max)` — faster turnaround

The rationale is straightforward: solo mode keeps the same quest structure with fewer reviewers and a shorter fix loop. The lighter process changes throughput, not the scoring rules themselves.

## Override: You Always Choose

The router **recommends** a route. You **choose**.

Every route presents alternatives. When Quest recommends solo, you'll see something like:

```
Quest Assessment:
  Risk: low
  Complexity: moderate
  Recommended route: solo (lightweight quest)

Options:
  1. Run as solo quest (recommended) — single plan review, single code review
  2. Run as full quest — dual reviews, arbiter, the works
  3. Cancel
```

When Quest recommends the full workflow:

```
Quest Assessment:
  Risk: high
  Complexity: substantial
  Recommended route: full quest

Options:
  1. Run as full quest (recommended)
  2. Run as solo quest (lighter) — single reviewer
  3. Cancel
```

If the router recommends exiting (trivial + low risk), you can still override into solo or full quest if you want the pipeline for any reason.

## The Questioning Phase

When Quest determines it needs more information, here's what happens.

### Numbered Questions in Small Batches

Quest asks 1-3 questions at a time, each labeled sequentially:

```
Q1: What user actions should trigger a notification? (API errors, form submissions, background jobs?)
Q2: Should notifications be in-app only, or also email/push?
Q3: What does "done" look like — what should a reviewer check for?
```

The numbering persists across rounds — Round 2 picks up from where Round 1 left off (Q4, Q5, ...).

### Decision After Each Response

After you answer a batch, Quest evaluates your answers and outputs a decision:

```
Decision: CONTINUE
Reason: Scope is clear but testing expectations and deployment concerns remain unresolved.
```

The three decisions:

- **CONTINUE** — important gaps remain, ask more questions
- **EDIT** — your answer was unclear, rephrase and re-ask (doesn't consume new question numbers)
- **STOP** — enough information to produce a solid plan

### Checkpoint Around Q5-Q7

After asking 5-7 questions, Quest offers to stop early:

> "I have enough context to start planning. Would you like to continue refining, or should I proceed?"

You decide whether the remaining gaps are worth addressing or if the planner can work with what it has.

### Hard Cap: 10 Questions

Quest never asks more than 10 questions total. If it reaches Q10 and gaps remain, it stops, documents the unknowns, and proceeds to planning with explicit assumptions.

### Skipping Questions

Say any of these at any point to skip the rest of the questioning phase:

- "just go with it"
- "proceed"
- "skip questions"
- "that's enough"

Quest stops immediately (no "are you sure?"), documents what it knows and what remains unknown, and moves to planning. The planner will work with explicit assumptions rather than implicit guesses.

## What the Questioner Produces

When questioning ends, Quest produces a structured summary:

```
## Questioner Summary

### Requirements
- Notifications triggered by API errors and background job completions
- In-app toast UI, no email/push for now

### Constraints
- No new dependencies
- Must integrate with existing design system components

### Confirmed Assumptions
- Toast notifications only (not a notification center)
- Auto-dismiss after 5 seconds

### Unresolved Unknowns
- Stacking behavior when multiple toasts appear simultaneously
- Whether to persist notification history

### Readiness Statement
Ready to plan with assumptions on: toast stacking (will default to vertical stack)
and notification history (will skip for initial implementation).
```

This summary becomes part of the quest brief and is the authoritative input to the planning phase. The planner sees exactly what was confirmed, what was assumed, and what remains unknown.

## After Questioning: Router Re-check

Once the questioner finishes, Quest re-evaluates the combined input (your original prompt + the questioner summary) against the same seven dimensions. If it's satisfied, planning begins. If gaps remain, it allows one more short questioning pass — still within the same 10-question total cap — then proceeds to planning regardless.

## Session Interruption

The questioning phase happens *before* the quest folder is created. There is no saved state during questioning. If your session is interrupted mid-question, you'll need to re-run `/quest` with your prompt — there's nothing to resume from.

Once Quest creates the quest folder and starts planning, state is saved and you can resume anytime with `/quest <quest-id>`.

## Examples

**Thin input — triggers questioning:**

```bash
/quest "add caching"
# Quest asks: Q1 (what to cache?), Q2 (cache invalidation strategy?), Q3 (scope?)
# After answers, proceeds to planning with a structured summary
```

**Detailed input — skips questioning:**

```bash
/quest "Add Redis caching to the /api/users endpoint. Scope: src/services/userService.ts
and src/middleware/cache.ts. TTL: 5 minutes, invalidate on user update. AC: (1) cache hit
returns in <10ms, (2) cache miss falls through to DB, (3) PUT/DELETE invalidates cache.
Test: integration test with Redis test container."
# Quest routes directly to planning — deliverable, scope, constraints, AC, and testing are clear
```

**Quick override — skip remaining questions:**

```bash
/quest "refactor the authentication system"
# Quest asks Q1, Q2, Q3 about scope and approach
# You respond: "just go with it"
# Quest stops, documents assumptions, proceeds to planning
```

**High-risk domain — extra scrutiny:**

```bash
/quest "migrate user data from PostgreSQL to MongoDB"
# Even with some detail, Quest may question further due to high risk (data migration)
# Risk biases toward gathering more information before planning
```

**Moderate task — routes to solo:**

```bash
/quest "Add input validation to the settings form"
# Quest Assessment: moderate complexity, low risk → solo recommended
# Options: 1. Solo (recommended) 2. Full quest 3. Cancel
# Single reviewer, faster turnaround
```

**Override — escalate solo to full workflow:**

```bash
/quest "Refactor the notification service"
# Quest Assessment: moderate complexity, low risk → solo recommended
# User selects: "Run as full quest"
# Quest creates full workflow with dual reviews and arbiter
```

## File Structure

The routing and questioning logic lives in three delegation files:

```
.skills/quest/
  SKILL.md                        # Entry point: resume check, classify, route
  delegation/
    router.md                     # Evaluates input across 7 dimensions + complexity routing
    questioner.md                 # Structured questioning with caps and decisions
    workflow.md                   # Full quest lifecycle (plan/build/review/fix)
```

`SKILL.md` is the orchestrator — it reads the router's decision, delegates to the questioner if needed, then hands off to the workflow once input is ready.
