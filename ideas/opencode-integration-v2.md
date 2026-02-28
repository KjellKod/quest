# OpenCode Integration v2: Clean Reimplementation

## Status
idea

## Purpose
Redo the OpenCode integration correctly — as a thin wiring layer into the existing shared workflow, not a parallel rewrite.

## Background

The `opencode-integration` branch (PR #46) attempted to add OpenCode runtime support. The idea document (`unified-allowlist-routing.md`) had the right design: one shared workflow driven by allowlist routing. But the implementation deviated — it built a standalone 701-line SKILL.md, introduced an unnecessary `.ai/roles/` layer, and duplicated agent definitions that already exist in `.skills/quest/agents/`.

### What went wrong
1. `.opencode/skills/quest/SKILL.md` was written as a complete standalone workflow (701 lines) instead of delegating to `delegation/workflow.md` (~800 lines, already runtime-agnostic)
2. `.ai/roles/*.md` was created as a "portable role" layer — but `.skills/quest/agents/*.md` already serves this purpose and is what `workflow.md` references
3. `.opencode/agents/*.md` delegates to `.ai/roles/` instead of `.skills/quest/agents/`
4. Result: 3 copies of role definitions, 2 copies of the workflow

### What worked well (keep the learnings)
- Allowlist v3 with `model_routing` + `model_tiers` — correct design
- `opencode.json` structure — agent definitions, commands, permissions all correct
- OpenCode agent YAML frontmatter format (name, description, tools) — needed for OpenCode
- Split reviewers (plan-reviewer-a/b, code-reviewer-a/b) for model diversity — good
- Metadata headers for model self-identification — good
- Artifact persistence fallback (verify files after Task calls) — needed
- State updates at every phase transition — needed
- Free OpenCode Zen models confirmed: big-pickle, minimax-m2.5-free, gpt-5-nano

### What the branch taught us about OpenCode
- `{file:...}` paths resolve relative to `.opencode/` not repo root
- Commands require a `template` field
- `task` tool subagents may return content without writing to disk — orchestrator must verify and persist
- OpenCode can follow multi-file instruction chains (SKILL.md → workflow.md → agents/*.md)
- Model diversity works via per-agent `model` field in opencode.json
- kimi-k2.5-free expired; minimax-m2.5-free works

---

## Proposed Approach: Start Fresh from Main

### Why not clean up the branch
- 6 commits, 2267 lines added, but ~70% is duplication or wrong-layer code
- Untangling the layers is harder than rebuilding correctly
- The quest artifacts (.quest/) from test runs shouldn't be committed anyway
- Cherry-picking individual changes is fragile — the commits are intertwined

### What to build (estimated ~500 lines of new code)

#### 1. Allowlist v3 (~50 lines changed)
Update `.ai/allowlist.json`:
- Add `model_routing` section (claude, opencode, codex)
- Add `model_tiers` section (opencode tier mappings)
- Normalize `role_permissions` keys (reviewer_a/b, code_reviewer_a/b)
- Update `.ai/schemas/allowlist.schema.json` to match

#### 2. OpenCode wiring (~200 lines new)
Create `.opencode/` directory:
- `opencode.json` — agent definitions with `model` fields, command mappings, permissions
- `commands/quest.md` — `/quest` command definition
- `agents/*.md` (6 files, ~30 lines each) — YAML frontmatter (tools, name, description) + one line: "Read and follow `.skills/quest/agents/<role>.md`"
  - NO separate `.ai/roles/` layer
  - OpenCode agents reference the SAME files Claude's workflow already uses

#### 3. OpenCode quest skill shim (~30 lines)
Create `.opencode/skills/quest/SKILL.md`:
- Detect runtime as OpenCode
- Delegate to `.skills/quest/delegation/workflow.md`
- That's it. The shared workflow already handles OpenCode via runtime detection + allowlist routing.

#### 4. Workflow.md updates (~50 lines changed)
- Standardize reviewer file naming: `review_reviewer_a.md` / `review_reviewer_b.md` (all runtimes)
- Add artifact persistence rule (verify files exist after Task calls)
- Add state update reminders at each phase
- Ensure the OpenCode runtime detection path works

#### 5. Validation + docs (~170 lines new)
- Extend `validate-quest-config.sh` for OpenCode files
- Add `docs/guides/opencode-quickstart.md`
- Update README with OpenCode section

### What NOT to build
- `.ai/roles/` — does not exist, should not exist
- Standalone OpenCode SKILL.md with inline prompts — the shared workflow handles it
- Duplicate agent definitions — one set in `.skills/quest/agents/`, referenced by all runtimes

---

## Key Design Principle

```
.skills/quest/agents/*.md    ← Single source of truth for role definitions
.skills/quest/SKILL.md       ← Entry point (thin, delegates to workflow.md)
.skills/quest/delegation/    ← Shared workflow (runtime-agnostic)
.ai/allowlist.json           ← Drives all routing decisions

.opencode/agents/*.md        ← OpenCode YAML frontmatter + pointer to .skills/quest/agents/
.opencode/opencode.json      ← OpenCode config (agents, commands, models)
.opencode/skills/quest/      ← Thin shim → shared workflow
.opencode/commands/quest.md  ← /quest command

.claude/                     ← Claude Code config (already exists, unchanged)
.codex/                      ← Codex config (already exists, unchanged)
```

Each runtime owns its wiring (how to invoke subagents), but the workflow logic, role definitions, and routing config are shared.

---

## Implementation Order

1. Branch from main
2. Allowlist v3 (schema + data)
3. `.opencode/` wiring (opencode.json, agents, command)
4. Thin SKILL.md shim
5. workflow.md updates (naming, persistence, state)
6. Validation script extensions
7. Docs (quickstart + README)
8. Test with OpenCode (same 3-challenge quest)

---

## Risk: Can OpenCode Follow the Indirection?

The shared workflow tells subagents: "Read your instructions: `.skills/quest/agents/plan-reviewer.md`"

OpenCode's agent files would say: "Read and follow `.skills/quest/agents/planner.md`"

This means an OpenCode subagent reads:
1. `.opencode/agents/planner.md` (its own config) → which says read...
2. `.skills/quest/agents/planner.md` (the actual role instructions)

Two hops. The v1 branch proved OpenCode can follow this — the `.ai/roles/` indirection worked the same way. If it fails, the fallback is to inline the role content into `.opencode/agents/*.md` (still no `.ai/roles/` layer — just copy from `.skills/quest/agents/`).

---

## References
- Original idea: `ideas/unified-allowlist-routing.md`
- Branch learnings: PR #46 (`opencode-integration`)
- Test run artifacts: `.quest/opencode-test-run_2026-02-27__1200/` (3 successful runs with iteration)
