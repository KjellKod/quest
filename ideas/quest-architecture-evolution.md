# Quest Architecture Evolution: Closing the Gap Between Philosophy and Implementation

## What

A phased roadmap to evolve Quest from a prompt-orchestrated pipeline toward a system that enforces its own principles. Each phase is a standalone improvement that delivers value independently.

The philosophy is right. The architecture is pragmatically correct. The gap between them is the roadmap.

## Why

Quest's philosophy demands discipline, process, and constraints enforced by the system. Today, the system is a SKILL.md that *asks* an LLM to follow steps. The gap shows up in three ways:

1. **No exploration capability.** Quest assumes you know what to build. When you don't, there's no structured path for discovery.
2. **Context contamination.** The orchestrator accumulates plan content, review content, and build output. By the fix loop, it's drowning in context.
3. **Unnecessary indirection.** Four layers between "write a plan" and the plan being written. Roles that duplicate what skills already say.

## Phases

### Phase 1: Add `/explore` skill

**Problem:** Quest has no capability for research, analysis, or discovery tasks. When someone says "analyze how we should proceed," the agent recognizes it's not an implementation task — then has nowhere to go.

**Solution:** A standalone skill at `.skills/explore/SKILL.md` that:
- Uses `context: fork` + `agent: Explore` for clean isolation
- Follows a structured process: Scope → Search → Synthesize → Recommend
- Produces findings as conversational output (standalone) or `findings.md` (quest context)
- Auto-triggers when Claude detects exploratory intent via the `description` field
- Is user-invocable as `/explore "topic"`

**Key design decisions:**
- Skill, not a role. It exists independently of Quest.
- No coupling to the Quest pipeline. Quest can invoke it optionally as a pre-phase, but that's Quest's choice.
- The name `explore` aligns with Claude Code's built-in Explore agent type.

**Estimated size:** ~80 lines SKILL.md + thin Claude Code wrapper.

**Impact:** Fills the known gap between "I have a question" and "I know what to build."

---

### Phase 2: Thin orchestrator (pass paths, not content) — DONE

**Status:** Completed via quest `thin-orchestrator_2026-02-09__1845`. Commit: `ebfaf43`.

**Problem:** The Quest orchestrator accumulates context from every phase. After plan + two reviews + arbiter + build + two code reviews + fix iterations, the main session is bloated. This violates the philosophy: "Clean context and focus are mandatory."

**Solution:** Change how the orchestrator handles subagent responses:

Today:
```
Orchestrator reads plan content → passes content to reviewer prompts
Orchestrator reads review content → passes content to arbiter prompt
Orchestrator reads arbiter verdict content → decides next step
```

After:
```
Orchestrator verifies plan.md exists → passes PATH to reviewer prompts
Orchestrator verifies review files exist → passes PATHs to arbiter prompt
Orchestrator reads ONLY the SUMMARY line from handoff → decides next step
```

**Specific changes to Quest orchestration files:**
- After each subagent returns, the orchestrator extracts ONE line (the SUMMARY from the handoff) and the artifact path. Nothing else enters the orchestrator's context.
- Subagent invocation prompts reference file paths, not file contents. Subagents read files themselves.
- For user presentation (Step 3.5), the orchestrator reads the plan at that moment — but this is an intentional, bounded context load for human interaction, not accumulated drift.

**What the orchestrator keeps:** Current phase, artifact paths, one-line summaries, what to tell the user.
**What the orchestrator discards:** Plan content, review content, build output, fix details.

**Impact:** Directly addresses the context contamination problem. The orchestrator stays light through the entire quest lifecycle.

---

### Phase 2b: Close remaining context leaks — IN PROGRESS

**Status:** Mostly implemented. 5 of 7 items shipped incrementally alongside Phase 2.

**Full findings moved:** `ideas/phase2b-context-leak-closure.md`

**Original proposal:** `ideas/quest-context-optimization.md`

**Current summary:**
- The core `handoff.json` contract and thin-context routing discipline are in place.
- Remaining gap is runtime behavior: background invocation path for Claude/Codex flows and proving that transcript bodies no longer pollute orchestrator context.
- Latest recommendation is to complete Phase 2b with a small, measurable rollout (explicit poll timeout, token cap assertion, fallback rehearsal, and cloud-contract rehearsal) rather than starting a new architecture layer.

---

### Phase 3: State validation script

**Problem:** The orchestrator is told to check state before proceeding. If it doesn't, nothing prevents a phase from starting without its prerequisites.

**Solution:** A `scripts/validate-quest-state.sh` script that the orchestrator calls before each phase transition.

```bash
# Usage: validate-quest-state.sh <quest-id> <target-phase>
# Returns 0 if valid to proceed, 1 if not
# Checks:
#   - state.json exists and is valid JSON
#   - Current phase matches expected predecessor
#   - Required artifacts from previous phase exist
#   - plan_iteration / fix_iteration within bounds
```

**Phase transition requirements:**
- `plan → plan_reviewed`: plan.md, review_claude.md, review_codex.md, arbiter_verdict.md must exist
- `plan_reviewed → building`: plan.md exists, arbiter verdict says "builder"
- `building → reviewing`: builder artifacts exist (changed files)
- `reviewing → fixing`: review files exist with issues
- `reviewing → complete`: review files exist, both say clean

**Integration:** The orchestrator calls this script before every phase transition. This is the first piece of *system-enforced* correctness — a shell script that runs regardless of what the LLM thinks the state is.

**Impact:** First real infrastructure enforcement. Moves one critical check from "prompt hopes model verifies" to "script actually verifies."

---

### Phase 4: Relocate role wiring to `.skills/quest/agents/`

**Status:** Not started. See `ideas/phase4-role-relocation.md` for full analysis.

**Summary:** Move 6 role files from `.ai/roles/` to `.skills/quest/agents/` so Quest wiring lives under the Quest skill. Zero functional change — ownership cleanup only.

**Key finding from analysis:** Blast radius is ~15+ files (runtime, validation scripts, metadata, docs), not the ~2 originally estimated. The move is safe but larger than it looks. See the idea file for the full reference list, validation baseline, and validation plan.

---

### Phase 5: Infrastructure migration (future, when platform catches up)

**Problem:** The orchestrator is instructions that a model may or may not follow. As Claude Code's hooks, agents, and plugins mature, enforcement can move from prompt to infrastructure.

**Solution:** Migrate incrementally:
- Use hooks to enforce state validation before tool calls
- Use `context: fork` for every phase (not just reviews)
- Use plugin architecture if skills need to be distributed

**When:** Watch Claude Code releases. When hooks can block tool calls based on script output, that's the migration trigger.

**Impact:** Long-term. The gap between philosophy and implementation closes further.

---

## Implementation Strategy

Each phase is a standalone quest. The phases are ordered by impact and independence:

1. **Phase 1 (explore):** No dependencies. Can ship independently. Lowest urgency — Claude Code's built-in Explore agent covers the capability informally; this formalizes it.
2. **Phase 2 (thin orchestrator):** Done.
3. **Phase 2b (context leaks):** In progress. See `ideas/phase2b-context-leak-closure.md` for findings and the concrete next-step rollout.
4. **Phase 3 (state validation):** Done.
5. **Phase 4 (role relocation):** No dependencies. Safe, low-risk housekeeping. Zero functional change.
6. **Phase 5 (infrastructure):** Depends on external platform evolution. Backlog.

**Honest take on remaining work:** Phases 2, 2b (mostly), and 3 delivered the real improvements — context discipline and state enforcement. What remains is either cosmetic (Phase 4), nice-to-have (Phase 1), platform-dependent (2b remainder), or long-term (Phase 5). The system works. Doing nothing is a legitimate option. Time spent on Quest meta-improvement is time not spent using Quest to build features.

## Status

| Phase | Status |
|-------|--------|
| Phase 1: `/explore` skill | Not started |
| Phase 2: Thin orchestrator | **Done** (`thin-orchestrator_2026-02-09__1845`) |
| Phase 2b: Close context leaks | **In progress** — 5/7 items shipped. Findings + next step: `ideas/phase2b-context-leak-closure.md` (proposal history: `ideas/quest-context-optimization.md`) |
| Phase 3: State validation | **Done** (`state-validation-script_2026-02-15__1508`) |
| Phase 4: Role relocation | Not started — ownership cleanup, zero functional change |
| Phase 5: Infrastructure | Backlog |
