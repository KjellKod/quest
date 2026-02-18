# Idea: Phase 4 — Relocate Role Wiring to `.skills/quest/agents/`

## Problem

Four layers between intent and execution:
```
Quest SKILL.md → Task(planner) → .ai/roles/planner_agent.md → plan-maker/SKILL.md → writes plan
```

Roles that are 1:1 with skills add indirection. But the Quest-specific wiring in each role is **substantial** — not just 10 lines. Each role defines: handoff contracts (JSON + text), output paths, slot assignments (Claude vs Codex), phase routing (`NEXT` values), iteration rules, write scopes, and allowed commands. Inlining all of this into `workflow.md` or orchestrator prompts would bloat `workflow.md` from ~880 lines to ~1200+ and interleave wiring with orchestration logic.

## Proposed Solution

Move role files from `.ai/roles/` to `.skills/quest/agents/`, keeping them as separate files owned by the Quest skill. The wiring is Quest's concern, not a top-level project concern.

Before:
```
.ai/roles/planner_agent.md          # Quest wiring, lives outside Quest skill
.ai/roles/plan_review_agent.md
.ai/roles/code_review_agent.md
.ai/roles/builder_agent.md
.ai/roles/fixer_agent.md
.ai/roles/arbiter_agent.md          # Pure Quest logic, no matching skill
.ai/roles/quest_agent.md            # Routing meta-layer, no matching skill
```

After:
```
.skills/quest/agents/planner.md        # Quest wiring: paths, handoff, iteration rules
.skills/quest/agents/plan-reviewer.md  # Quest wiring: slots, paths, NEXT: arbiter
.skills/quest/agents/code-reviewer.md  # Quest wiring: slots, paths, NEXT: fixer|null
.skills/quest/agents/builder.md        # Quest wiring: paths, pr_description, NEXT: code_review
.skills/quest/agents/fixer.md          # Quest wiring: paths, fix-only constraint, NEXT: code_review
.skills/quest/agents/arbiter.md        # Pure Quest logic (no matching skill)
.ai/roles/quest_agent.md              # Stays — routing meta-layer used by SKILL.md before workflow starts
```

### File mapping (6 relocations)

| From | To |
|------|-----|
| `.ai/roles/planner_agent.md` | `.skills/quest/agents/planner.md` |
| `.ai/roles/plan_review_agent.md` | `.skills/quest/agents/plan-reviewer.md` |
| `.ai/roles/code_review_agent.md` | `.skills/quest/agents/code-reviewer.md` |
| `.ai/roles/builder_agent.md` | `.skills/quest/agents/builder.md` |
| `.ai/roles/fixer_agent.md` | `.skills/quest/agents/fixer.md` |
| `.ai/roles/arbiter_agent.md` | `.skills/quest/agents/arbiter.md` |

### What stays in `.ai/roles/` (1)

`quest_agent.md` — routing logic consumed by `SKILL.md` before `workflow.md` runs. Legitimate top-level role.

---

## Is It OK to Have Agents Under a Skill?

Nothing in the skill conventions prohibits it, but it stretches the model slightly. The conventions define skill resources as "scripts, references, assets" — agent persona definitions with contracts and routing rules are wiring, not knowledge.

**However, the precedent is already set.** The quest skill's `delegation/` subdirectory already contains operational wiring files — `router.md`, `questioner.md`, `workflow.md` — none of which are "skills" in the conventional sense. They're Quest internals. The agent role files are the same category: Quest-specific wiring consumed exclusively by `workflow.md` prompts.

**The ownership argument is the real justification.** These 6 role files are consumed only by Quest. No other skill, user workflow, or external tool references them. Putting them under `.skills/quest/agents/` makes ownership truthful — these belong to Quest, not to the project at large. Leaving them in `.ai/roles/` makes them look like a project-level concern when they're really Quest internals that happen to live outside their parent.

---

## Blast Radius Analysis

The evolution doc originally described this as "move 6 files, update ~20 path references in workflow.md." The actual blast radius is significantly larger.

### Runtime references (will break quests if wrong)

| File | References | What breaks |
|------|-----------|-------------|
| `.skills/quest/delegation/workflow.md` | 6 path refs (lines 178, 219, 272, 456, 505, 805) | Subagent prompts: "Read your instructions: .ai/roles/X_agent.md" |
| `.claude/agents/planner.md` | 1 ref | Claude Code subagent type definition |
| `.claude/agents/plan-reviewer.md` | 1 ref | Claude Code subagent type definition |
| `.claude/agents/code-reviewer.md` | 1 ref | Claude Code subagent type definition |
| `.claude/agents/builder.md` | 1 ref | Claude Code subagent type definition |
| `.claude/agents/fixer.md` | 1 ref | Claude Code subagent type definition |
| `.claude/agents/arbiter.md` | 1 ref | Claude Code subagent type definition |

### Validation scripts (will fail)

| File | What it checks |
|------|---------------|
| `scripts/validate-manifest.sh` | Checks files listed in `.quest-manifest` exist |
| `scripts/validate-handoff-contracts.sh` | Hardcoded glob: `.ai/roles/{planner,plan_review,arbiter,builder,code_review,fixer}_agent.md` |
| `scripts/validate-quest-config.sh` | Checks `.ai/roles/` directory exists, checks role files exist, validates required sections |

### Metadata (stale references, non-breaking but misleading)

| File | References |
|------|-----------|
| `.quest-manifest` | 7 entries listing role file paths |
| `.ai/quest.md` | Role-to-path mapping table (8 rows) |
| `CONTRIBUTING.md` | Mentions required sections in `.ai/roles/*.md` |

### Documentation (stale references, non-breaking)

| File | References |
|------|-----------|
| `README.md` | Directory tree showing `.claude/agents/` → `.ai/roles/` |
| `PROVENANCE.md` | Lists role files |
| `docs/guides/quest_setup.md` | Multiple refs, explains roles as source of truth |
| `docs/guides/quest_presentation.md` | Directory tree |
| `ideas/quest-council-mode.md` | References arbiter role path (3 refs) |
| `ideas/codex-quest-skill.md` | Mentions `.ai/roles/*.md` |

### Historical (leave as-is, they describe past state)

| File | References |
|------|-----------|
| `docs/quest-journal/handoff-contract-fix_2026-02-09.md` | 6 role file paths |
| `docs/quest-journal/context-leak-closure_2026-02-15.md` | 6 role file paths |

### Total: ~15+ files need updates (beyond the 6 being moved)

This is not "6-file move + workflow.md path changes." It's a moderate refactor touching runtime, validation, metadata, and documentation.

---

## Pre-Move Validation Baseline

These scripts must pass before AND after the move. Baseline captured 2026-02-17:

### `scripts/validate-quest-config.sh`
```
=== Quest Configuration Validation ===

[PASS] .quest/ is in .gitignore
[PASS] .ai/allowlist.json is valid JSON
[WARN] Schema validation skipped (ajv not installed)
[PASS] code_review_agent.md has all required sections
[PASS] plan_review_agent.md has all required sections
[PASS] quest_agent.md has all required sections
[PASS] arbiter_agent.md has all required sections
[PASS] builder_agent.md has all required sections
[PASS] planner_agent.md has all required sections
[PASS] fixer_agent.md has all required sections

All validations passed!
```

### `scripts/validate-handoff-contracts.sh`
```
=== Handoff Contract Validation ===

1. Checking all role files have text format (not JSON)...
   ✅ No JSON contracts found in role files

2. Checking all role files have ---HANDOFF--- format...
   ⚠️  Found 0/6 role files with ---HANDOFF--- format
   (This is informational - role files define the contract, they don't need to contain literal examples)

3. Checking for 'Context Is In Your Prompt' contradictions...
   ✅ No 'Context Is In Your Prompt' found

4. Checking workflow has Codex-only invocations...
   ✅ No Task tool invocations found (Codex-only: 11)

5. Checking ARTIFACTS field in minimal example...
   ✅ Minimal example includes ARTIFACTS

=== Validation Complete ===

✅ All checks passed
```

### `scripts/validate-manifest.sh`
```
Checking Quest files are listed in .quest-manifest...
[OK] All Quest files are listed in .quest-manifest

Checking for stale manifest entries...
[OK] No stale entries in manifest

Manifest validation complete.
```

---

## Validation Plan (if we proceed)

### Step 1: Pre-move baseline (done — see above)

Run all 3 validation scripts, capture passing output:
```bash
bash scripts/validate-quest-config.sh
bash scripts/validate-handoff-contracts.sh
bash scripts/validate-manifest.sh
```
All three pass as of 2026-02-17 (output captured in "Pre-Move Validation Baseline" section above).

### Step 2: Move files + update all references

**2a. Move the 6 role files:**
```bash
mkdir -p .skills/quest/agents
git mv .ai/roles/planner_agent.md      .skills/quest/agents/planner.md
git mv .ai/roles/plan_review_agent.md  .skills/quest/agents/plan-reviewer.md
git mv .ai/roles/code_review_agent.md  .skills/quest/agents/code-reviewer.md
git mv .ai/roles/builder_agent.md      .skills/quest/agents/builder.md
git mv .ai/roles/fixer_agent.md        .skills/quest/agents/fixer.md
git mv .ai/roles/arbiter_agent.md      .skills/quest/agents/arbiter.md
```

**2b. Update runtime references (breaks quests if missed):**

| File | Change |
|------|--------|
| `.skills/quest/delegation/workflow.md` | 6 path refs: `.ai/roles/X_agent.md` → `.skills/quest/agents/X.md` |
| `.claude/agents/planner.md` | Point to `.skills/quest/agents/planner.md` |
| `.claude/agents/plan-reviewer.md` | Point to `.skills/quest/agents/plan-reviewer.md` |
| `.claude/agents/code-reviewer.md` | Point to `.skills/quest/agents/code-reviewer.md` |
| `.claude/agents/builder.md` | Point to `.skills/quest/agents/builder.md` |
| `.claude/agents/fixer.md` | Point to `.skills/quest/agents/fixer.md` |
| `.claude/agents/arbiter.md` | Point to `.skills/quest/agents/arbiter.md` |

**2c. Update validation scripts (will fail if not updated):**

| File | Change |
|------|--------|
| `scripts/validate-quest-config.sh` | Update `.ai/roles/` directory check → `.skills/quest/agents/` (keep `quest_agent.md` check in `.ai/roles/`) |
| `scripts/validate-handoff-contracts.sh` | Update hardcoded glob from `.ai/roles/{planner,...}_agent.md` → `.skills/quest/agents/{planner,...}.md` |
| `scripts/validate-manifest.sh` | No code change needed — it reads `.quest-manifest` entries |

**2d. Update metadata (stale if not updated):**

| File | Change |
|------|--------|
| `.quest-manifest` | Update 6 role file paths, add new paths |
| `.ai/quest.md` | Update role-to-path mapping table (8 rows) |
| `CONTRIBUTING.md` | Update `.ai/roles/*.md` reference |

**2e. Update documentation (stale if not updated):**

| File | Change |
|------|--------|
| `README.md` | Update directory tree |
| `PROVENANCE.md` | Update role file references |
| `docs/guides/quest_setup.md` | Update multiple refs, "source of truth" explanation |
| `docs/guides/quest_presentation.md` | Update directory tree |

**2f. Leave as-is (historical, describe past state):**
- `docs/quest-journal/handoff-contract-fix_2026-02-09.md`
- `docs/quest-journal/context-leak-closure_2026-02-15.md`
- `ideas/quest-council-mode.md` (references arbiter — update if/when council mode is implemented)

### Step 3: Post-move validation

Run the same 3 scripts — all must pass:
```bash
bash scripts/validate-quest-config.sh
bash scripts/validate-handoff-contracts.sh
bash scripts/validate-manifest.sh
```

Additionally, verify the moved files are readable:
```bash
# Quick sanity: all 6 new files exist and have content
for f in planner plan-reviewer code-reviewer builder fixer arbiter; do
  test -s ".skills/quest/agents/$f.md" && echo "OK: $f" || echo "MISSING: $f"
done

# quest_agent.md still in .ai/roles/
test -s ".ai/roles/quest_agent.md" && echo "OK: quest_agent" || echo "MISSING: quest_agent"
```

### Step 4: Smoke test — run a real quest

This is the only true validation. The paths are consumed at runtime by LLM subagents reading files. A passing validation script proves the scripts were updated, not that the agents can find their instructions.

Run a small, low-risk quest end-to-end:
```
/quest "Add a comment to README.md explaining the .skills/quest/agents/ directory"
```

**What to watch for:**
- Planner agent finds its instructions (no "file not found" or confused behavior)
- Plan reviewers (both Claude and Codex slots) find their instructions
- Arbiter finds its instructions
- Builder finds its instructions
- Code reviewers find their instructions
- If fixes needed: fixer finds its instructions

**Pass criteria:** Quest completes through all phases without any agent failing to read its role file. The context_health.log should show normal handoff.json compliance — no degradation from baseline.

**Fail criteria:** Any agent produces output that suggests it didn't read its role file (missing handoff format, wrong output paths, no handoff.json written). If this happens: `git checkout .ai/roles/` to restore originals, investigate which reference was missed.

---

## Candid Assessment

**Pros:**
- Ownership becomes truthful — Quest internals live under the Quest skill
- `.ai/roles/` shrinks from 7 files to 1, reducing project-root noise
- Makes Quest more self-contained and portable
- Codex-compatible — agents read paths from prompts, path just changes

**Cons:**
- **Zero functional improvement.** Pipeline behaves identically before and after.
- Blast radius is ~15+ files, not the ~2 originally estimated
- Risk of breaking existing quests during transition
- Validation scripts need updating (they hardcode `.ai/roles/` paths)
- Churn for churn's sake if the current structure isn't causing problems

**Verdict:** Safe but larger than it looks. Do it if the misplaced ownership bothers you enough to touch 15+ files for zero functional gain. Skip it if not.
