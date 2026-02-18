# Quest Council Mode

## What

An optional `/quest council "description"` mode that generates two competing plans in parallel, reviews each independently, then presents a comparison report for human decision-making. The human picks the winning plan and optionally borrows strengths from the losing plan.

## Why

Single-plan iteration improves a plan but can't reimagine it. Two plans from different starting points surface genuinely different architectures. The user already does this manually — two plans, two review cycles, compare, pick the best, borrow golden nuggets — and it consistently produces stronger outcomes for high-risk or ambiguous features.

## Detailed Design

### Invocation

```
/quest council "description of what to build"
```

`council` is a **mode flag**, not a route. It is stored in `state.json` as `"mode": "council"`. Normal routing still happens: the router classifies the input, the questioner fires if the input is vague, and when the workflow begins it enters the council variant of Step 3 instead of the standard one. Council mode does not bypass intake quality.

### Flow

```
                    ┌─── plan-maker-A ──→ review-A:claude + review-A:codex ──→ arbiter-A ───┐
questioner (if needed) ──┤                                                                       ├──→ council-arbiter ──→ human decision ──→ (optional refinement) ──→ build
                    └─── plan-maker-B ──→ review-B:claude + review-B:codex ──→ arbiter-B ───┘
```

### Phase 1: Parallel Plan Generation

Both planners run simultaneously (same message, two Task calls):

- **Planner A** (Claude/Opus): `Task(subagent_type="planner", run_in_background: true)`
  - Writes to: `.quest/<id>/phase_01_plan/plan_a.md`
  - Same prompt as today, same quest brief

- **Planner B** (Codex or Claude with different model): `mcp__codex__codex` or `Task` with a different model override
  - Writes to: `.quest/<id>/phase_01_plan/plan_b.md`
  - Same quest brief, same constraints
  - Key: does NOT see Plan A. Independence is critical.

**Model configuration** via allowlist:
```json
{
  "council": {
    "planner_a": "opus",
    "planner_b": "gpt-5.3-codex",
    "council_arbiter": "opus"
  }
}
```

No `enabled` flag — the `/quest council` command itself is the opt-in. The allowlist only configures model choices.

Default is Claude + Codex for maximum diversity. User can set both to Claude with different models, or any combination.

### Phase 2: Independent Review Cycles

Each plan gets its own full review cycle — the same dual-reviewer + arbiter flow that exists today. This means the council arbiter works with two *vetted* plans, not two raw drafts.

**Plan A review:**
- Review A:Claude → `.quest/<id>/phase_01_plan/review_a_claude.md`
- Review A:Codex → `.quest/<id>/phase_01_plan/review_a_codex.md`
- Arbiter A → `.quest/<id>/phase_01_plan/arbiter_a.md`

**Plan B review:**
- Review B:Claude → `.quest/<id>/phase_01_plan/review_b_claude.md`
- Review B:Codex → `.quest/<id>/phase_01_plan/review_b_codex.md`
- Arbiter B → `.quest/<id>/phase_01_plan/arbiter_b.md`

**Parallelism:** Plan A reviews and Plan B reviews can run in parallel (4 reviewers simultaneously). The two arbiters also run in parallel with each other — Arbiter A launches as soon as Track A reviews complete, Arbiter B launches as soon as Track B reviews complete. They don't depend on each other, so if both tracks' reviews finish around the same time, both arbiters run simultaneously.

**Iteration within each track:** If arbiter-A says "iterate", Plan A goes through refinement just like today. Same for Plan B. Each track iterates independently up to `max_plan_iterations` (independent caps — Track A iterating doesn't penalize Track B's budget).

**Convergence logic:** The council arbiter runs when BOTH tracks reach a terminal state:
- **Terminal state:** approved by its arbiter, OR `max_plan_iterations` exhausted
- If a track exhausts iterations without approval, it enters council with a flag: `"track_b": { "status": "max_iterations", "plan_iteration": 4 }`. The council arbiter sees this and factors it into the comparison (an unapproved plan is weaker signal).
- If one track is approved and the other is still iterating, the orchestrator continues the iterating track. No blocking, no sleeping — the approved track's artifacts sit on disk until the other finishes.
- If BOTH tracks exhaust iterations without approval, pause and ask the human: "Neither plan was approved after max iterations. Review manually, or proceed to council comparison anyway?"

### Phase 3: Council Arbiter — Comparison Report

The council arbiter is NOT a new role file. It uses the existing `.skills/quest/agents/arbiter.md` which will gain a "Council Mode" section with council-specific criteria and the strict output template below. This inherits the arbiter's core philosophy (KISS, YAGNI, anti-spin, bias toward action) while adding comparison-specific guidance: "Which plan has the stronger architecture?", "Where do they diverge?", "Are there transferable elements?"

It does NOT merge plans. It compares and recommends.

**Input:**
- Plan A: `.quest/<id>/phase_01_plan/plan_a.md`
- Plan B: `.quest/<id>/phase_01_plan/plan_b.md`
- Arbiter A verdict: `.quest/<id>/phase_01_plan/arbiter_a.md`
- Arbiter B verdict: `.quest/<id>/phase_01_plan/arbiter_b.md`

**Output:** `.quest/<id>/phase_01_plan/council_verdict.md`

**Output structure (strict):**

```markdown
## Recommendation

**Winner: Plan [A|B]**
Rationale: <2-3 sentences on why this plan is stronger overall>

## Plan A — Strengths
- <strength 1>
- <strength 2>
- ...

## Plan B — Strengths
- <strength 1>
- <strength 2>
- ...

## Key Differences
| Aspect | Plan A | Plan B |
|--------|--------|--------|
| <architecture choice> | <approach> | <approach> |
| <scope decision> | <approach> | <approach> |
| ... | ... | ... |

## Similarity Assessment
<!-- Always present. Prevents fabricated differences. -->
<"Plans are substantially similar / moderately different / fundamentally different">
<If substantially similar: "Both plans converge on the same architecture. Differences are minor. Recommend the stronger execution." — do not fabricate differences that don't exist.>

## Golden Nuggets from [Losing Plan]
<!-- This section is ONLY present if the losing plan has specific, concrete
     strengths that would improve the winning plan. If not, this section
     is omitted entirely. No filler. -->
- <specific element>: "<quote or reference from losing plan>" → suggested integration point in winning plan's <section>
- ...

## Decision: HUMAN
```

**Critical constraint:** The council arbiter MUST NOT rewrite, merge, or produce a new plan. Its output is analysis only. The human decides.

### Phase 4: Human Decision (Interactive Presentation)

The orchestrator presents the council verdict interactively:

1. **Summary:** "Two plans generated and independently reviewed. Council arbiter recommends Plan [A|B]."
2. **Show:** The council verdict (comparison report)
3. **Ask:** One of:
   - "Go with Plan [A|B] as recommended" → winning plan becomes `plan.md`, proceed to build
   - "Go with Plan [A|B] but incorporate these golden nuggets: <user specifies>" → winning plan goes through one refinement pass with the user's feedback (planner reads the golden nuggets section + user instructions), then proceeds to build
   - "Go with Plan [other]" → user overrides recommendation, that plan becomes `plan.md`
   - "Neither — let me explain what I want differently" → back to questioner or new planning round

**After decision:**
- Copy the winning plan to `.quest/<id>/phase_01_plan/plan.md` (the canonical path the builder reads)
- If golden nuggets are being incorporated:
  1. Write user feedback to `.quest/<id>/phase_01_plan/user_feedback.md`
  2. Run one planner iteration on the winning plan only
  3. Run a **light review pass** on the refined plan (single reviewer, fast mode) — the integration of nuggets from Plan B into Plan A is new work that could introduce inconsistencies. This is cheap insurance.
  4. If the light review flags issues, present them to the human for a quick decision (proceed anyway or fix)
- Update state and proceed to Step 3.5 (existing interactive plan presentation) then build

### Folder Structure

```
.quest/<id>/phase_01_plan/
  plan_a.md                  # Planner A output
  plan_b.md                  # Planner B output
  review_a_claude.md         # Plan A review (Claude)
  review_a_codex.md          # Plan A review (Codex)
  review_b_claude.md         # Plan B review (Claude)
  review_b_codex.md          # Plan B review (Codex)
  arbiter_a.md               # Plan A arbiter verdict
  arbiter_b.md               # Plan B arbiter verdict
  council_verdict.md         # Comparison report
  plan.md                    # Final chosen plan (copied from winner, possibly refined)
  user_feedback.md           # Optional: golden nugget incorporation request
```

### State Machine Extension

New state values for council mode:

```json
{
  "mode": "council",
  "phase": "plan_council",
  "council": {
    "track_a": { "status": "reviewing", "plan_iteration": 1 },
    "track_b": { "status": "approved", "plan_iteration": 2 },
    "council_arbiter": "pending",
    "winner": null
  }
}
```

Phases: `plan_council` → `plan_council_review` → `plan_council_verdict` → `presenting` → (existing flow from here)

### Resume Support

`/quest <id>` resumes a council quest by reading `state.json`:
- If both tracks not done → continue pending track(s)
- If tracks done but no council verdict → run council arbiter
- If council verdict exists but no human decision → present verdict
- If human decided → continue to build (existing resume logic)

### What This Does NOT Change

- **Default mode:** `/quest "description"` still runs single-plan. Council is opt-in.
- **Build/review/fix phases:** Identical to today. Once `plan.md` exists, everything downstream is the same.
- **Role files:** No new role files. Council arbiter adds a "Council Mode" section to the existing `.skills/quest/agents/arbiter.md`.
- **Router/questioner:** Still runs before planning. Council mode doesn't skip intake quality.

## Cost and Time Implications

Council mode roughly **doubles** the planning phase cost and time:
- 2 planners + 4 reviewers + 2 arbiters + 1 council arbiter = 9 agent invocations (vs 1 planner + 2 reviewers + 1 arbiter = 4 today)
- Parallelism helps: both tracks run simultaneously, so wall-clock time is ~1.2x (not 2x) assuming similar plan complexity
- Worth it for high-risk, ambiguous, or architecturally significant features
- Not worth it for simple bug fixes or small features — hence opt-in only

## Resolved Questions

- [x] **Documentation location:** SKILL.md Usage section only. Once implemented, council is a feature, not an idea.
- [x] **Council arbiter instructions:** "Council Mode" section in `.skills/quest/agents/arbiter.md`. Inherits core philosophy, adds comparison-specific criteria.
- [x] **Both tracks rejected:** Iterate both in parallel up to `max_plan_iterations`. If one exhausts, continue the other. If both exhaust, pause and ask the human.
- [x] **Iteration caps:** Independent per track. Track A iterating doesn't penalize Track B's budget.
- [x] **Post-nugget review:** Light review pass (single reviewer, fast mode) on the refined plan after golden nugget incorporation.

## Open Questions

- [ ] **Council model config in allowlist.json:** The idea references a `council` config block for model choices but doesn't define where it lives in `allowlist.json`. Options: (a) add a `council.model_overrides` block separate from the existing `model_overrides`, or (b) add new keys to the existing `model_overrides` (e.g., `planner_b`, `arbiter_council`). Must be explicit about which keys Planner A, Planner B, and the council arbiter read.

- [ ] **Planner B prompt template (Codex MCP pattern):** If Planner B uses `mcp__codex__codex`, its prompt must follow the "short Codex prompts" guidance from `workflow.md` — point to files, don't inline content. A concrete prompt template for Planner B should be specified, mirroring the existing Codex reviewer patterns (role file path, context digest path, quest brief path, output path, handoff block).

- [ ] **Top-level `plan_iteration` semantics during council mode:** In normal mode, `plan_iteration` is top-level in `state.json` and referenced throughout `workflow.md` (Step 3 loop, iteration cap checks). In council mode, each track has its own `plan_iteration` inside the `council` object. Specify what happens to the top-level `plan_iteration`: set to 0 and ignored, set to the winning track's final value after human decision, or removed entirely. Downstream steps (Step 3.5 change handling) increment `plan_iteration` — this must work correctly after council mode resolves.

- [ ] **Resume logic additions to Step 0 for council phases:** The existing Step 0 in `workflow.md` doesn't know about `plan_council`, `plan_council_review`, or `plan_council_verdict` phases. Specify the resume mapping: `plan_council` → continue pending tracks, `plan_council_review` → continue pending reviews/arbiters, `plan_council_verdict` → run council arbiter, `presenting` (with `mode: council`) → present council verdict for human decision. This should be additive to the existing Step 0 table without breaking normal-mode resume.

- [ ] **Audit and parallelism logging for council events:** The existing workflow appends to `.quest/audit.log` and `.quest/<id>/logs/parallelism.log`. Council mode should: (a) log council-specific audit events (council arbiter invoked, human chose Plan A/B, golden nuggets incorporated), (b) log parallelism for the 4-reviewer parallel execution (two tracks × two reviewers) using the same YAML timestamp/overlap pattern, and (c) log parallelism for the two parallel arbiter runs.

## Status

idea
