# OpenCode Integration via Unified Allowlist Routing

## Status
idea

## Purpose
Enable Quest orchestration to run from OpenCode (alongside Claude Code and Codex) using a single unified allowlist with runtime-aware model routing.

## Background

Quest currently works in:
- **Claude Code:** `/quest` command (stable)
- **Codex:** `$quest` command (beta)

OpenCode is an open-source AI coding CLI with 75+ provider support, a full agent/subagent system, and MCP server support. Users want to run Quest from OpenCode using its native models or any supported provider.

### What users want
- Run `/quest` from OpenCode with the same workflow (plan → review → build → fix)
- Use OpenCode's default models (configurable per-slot)
- Mix providers freely — e.g., Claude for planning, Trinity for review, Big Pickle for building
- Keep Claude Code and Codex working unchanged

### Options evaluated
1. **Separate allowlist copy** (`allowlist-opencode.json`) — duplicates permissions, will drift
2. **Pointer approach** (main allowlist references separate file) — still two files to maintain
3. **Unified allowlist with runtime sections** — single source of truth, shared permissions, per-runtime model routing

**Decision:** Option 3. One allowlist to rule them all.

---

## Research Findings (2026-02-27)

### OpenCode's agent system — confirmed and capable

- Subagents defined in `.opencode/agents/*.md` (markdown + YAML frontmatter) or `opencode.json`
- **`task` tool** is OpenCode's equivalent of Claude Code's `Task(subagent_type=...)`
- Per-agent `model` field in frontmatter or config (format: `provider/model-id`)
- `mode: "subagent"` hides agents from primary UI — only AI-invocable
- `permission` block controls which subagents an orchestrator can spawn
- Full MCP server support (local + remote + OAuth)

### OpenCode agent config format

**In `opencode.json`:**
```json
{
  "agent": {
    "planner": {
      "description": "Creates implementation plans",
      "mode": "subagent",
      "model": "anthropic/claude-opus-4-5-20251101",
      "prompt": "{file:.opencode/agents/planner.md}",
      "tools": { "write": true, "edit": true, "bash": true }
    }
  }
}
```

**As markdown files** in `.opencode/agents/`:
```yaml
---
description: Creates implementation plans
mode: subagent
model: anthropic/claude-opus-4-5-20251101
tools:
  write: true
  edit: true
---
You are a Planner agent...
```

### OpenCode-native models available

| Model | ID | Context | Notes |
|-------|----|---------|-------|
| **Trinity Large Preview** | `arcee-ai/trinity-large-preview` | 131K | 400B MoE, 13B active, free on OpenRouter |
| **Big Pickle** | `opencode/big-pickle` | 200K | Stealth model via OpenCode Zen, 128K output, free (limited time) |

### Key differences from Claude Code

| Feature | Claude Code | OpenCode |
|---------|------------|----------|
| Spawn subagent | `Task(subagent_type="X")` | `task` tool (AI selects by agent description) |
| Agent config | `.claude/agents/X.md` | `.opencode/agents/X.md` or `opencode.json` |
| Model format | `sonnet`, `opus`, `haiku` | `provider/model-id` |
| Cross-provider | Codex via MCP only | Native (any of 75+ providers) |
| Parallel tasks | Yes (same message, two tool calls) | Unverified — may need sequential fallback |
| Commands | `.skills/X/SKILL.md` | `.opencode/commands/X.md` or config |

### What the first attempt built (reusable)

The `.opencode/` scaffolding from the stalled quest is solid and should be kept:
- `opencode.json` — agent definitions, command mappings, permission blocks
- `.opencode/agents/*.md` — thin wrappers (planner, plan-reviewer, builder, code-reviewer, arbiter, fixer)
- `.opencode/skills/quest/SKILL.md` — skill structure
- `.opencode/commands/quest.md` — command definition

What needs to change: agent wrappers should delegate to `.ai/roles/` instead of inlining instructions, and `opencode.json` should stop duplicating model choices.

---

## Proposed Design

### Core principle: shared permissions, runtime-specific routing

The allowlist has two kinds of config:
1. **Shared across all runtimes:** permissions, gates, approval phases, review thresholds
2. **Per-runtime:** which tool + model fills each orchestration slot

Today these are tangled (model routing hardcoded in `SKILL.md`, permissions duplicated across files). The fix is to make the allowlist the single control surface for both.

### Allowlist v3 schema

```json
{
  "version": 3,

  "auto_approve_phases": {
    "plan_creation": true,
    "plan_review": true,
    "plan_refinement": true,
    "implementation": false,
    "code_review": true,
    "fix_loop": false
  },

  "gates": {
    "require_approval_before_commit": true,
    "require_approval_before_push": true,
    "require_approval_before_delete": true,
    "max_plan_iterations": 4,
    "max_fix_iterations": 3
  },

  "role_permissions": {
    "planner": {
      "file_write": [".quest/**", "docs/implementation/**"],
      "file_read": ["**"],
      "bash": ["find", "grep", "wc", "tree", "ls"]
    },
    "reviewer_a": {
      "file_write": [".quest/**"],
      "file_read": ["**"],
      "bash": []
    },
    "reviewer_b": {
      "file_write": [".quest/**"],
      "file_read": ["**"],
      "bash": []
    },
    "arbiter": {
      "file_write": [".quest/**"],
      "file_read": ["**"],
      "bash": []
    },
    "builder": {
      "file_write": [".quest/**", "src/**", "lib/**", "tests/**", "scripts/**"],
      "file_read": ["**"],
      "bash": ["pytest", "npm test", "npm run build", "python", "pip", "npx"]
    },
    "code_reviewer_a": {
      "file_write": [".quest/**"],
      "file_read": ["**"],
      "bash": ["git diff", "git log", "git status"]
    },
    "code_reviewer_b": {
      "file_write": [".quest/**"],
      "file_read": ["**"],
      "bash": ["git diff", "git log", "git status"]
    },
    "fixer": {
      "file_write": [".quest/**", "src/**", "lib/**", "tests/**"],
      "file_read": ["**"],
      "bash": ["pytest", "npm test", "npm run build", "python"]
    }
  },

  "model_routing": {
    "claude": {
      "planner":         { "tool": "task", "subagent": "planner" },
      "reviewer_a":      { "tool": "task", "subagent": "plan-reviewer" },
      "reviewer_b":      { "tool": "mcp",  "server": "codex", "model": "gpt-5.2" },
      "arbiter":         { "tool": "task", "subagent": "arbiter" },
      "builder":         { "tool": "task", "subagent": "builder" },
      "code_reviewer_a": { "tool": "task", "subagent": "code-reviewer" },
      "code_reviewer_b": { "tool": "mcp",  "server": "codex", "model": "gpt-5.2" },
      "fixer":           { "tool": "task", "subagent": "fixer" }
    },
    "opencode": {
      "planner":         { "tool": "task", "subagent": "planner",       "tier": "advanced" },
      "reviewer_a":      { "tool": "task", "subagent": "plan-reviewer", "tier": "advanced" },
      "reviewer_b":      { "tool": "task", "subagent": "plan-reviewer", "tier": "standard" },
      "arbiter":         { "tool": "task", "subagent": "arbiter",       "tier": "advanced" },
      "builder":         { "tool": "task", "subagent": "builder",       "tier": "advanced" },
      "code_reviewer_a": { "tool": "task", "subagent": "code-reviewer", "tier": "advanced" },
      "code_reviewer_b": { "tool": "task", "subagent": "code-reviewer", "tier": "standard" },
      "fixer":           { "tool": "task", "subagent": "fixer",         "tier": "advanced" }
    },
    "codex": {
      "planner":         { "tool": "task", "subagent": "planner" },
      "reviewer_a":      { "tool": "task", "subagent": "plan-reviewer" },
      "reviewer_b":      { "tool": "task", "subagent": "plan-reviewer" },
      "arbiter":         { "tool": "task", "subagent": "arbiter" },
      "builder":         { "tool": "task", "subagent": "builder" },
      "code_reviewer_a": { "tool": "task", "subagent": "code-reviewer" },
      "code_reviewer_b": { "tool": "task", "subagent": "code-reviewer" },
      "fixer":           { "tool": "task", "subagent": "fixer" }
    }
  },

  "model_tiers": {
    "opencode": {
      "quick":    "anthropic/claude-haiku-4-5-20250307",
      "standard": "anthropic/claude-sonnet-4-5-20251101",
      "advanced": "anthropic/claude-opus-4-5-20251101"
    }
  },

  "review_mode": "auto",
  "fast_review_thresholds": {
    "max_files": 5,
    "max_loc": 200
  }
}
```

### How the workflow reads it

```
1. Detect runtime (claude | opencode | codex)
2. Read model_routing[runtime] for each slot
3. For each slot:
   - If tool == "task": invoke Task(subagent_type=subagent)
     - If tier set: resolve via model_tiers[runtime][tier]
   - If tool == "mcp": invoke mcp__<server>__<server>(model=model)
4. Permissions always come from role_permissions (shared)
```

The workflow becomes runtime-agnostic. The allowlist drives everything.

### Experimenting with opencode-native models

To try all-opencode-native models, change `model_tiers.opencode`:

```json
"model_tiers": {
  "opencode": {
    "quick":    "anthropic/claude-haiku-4-5-20250307",
    "standard": "arcee-ai/trinity-large-preview",
    "advanced": "opencode/big-pickle"
  }
}
```

Every slot mapped to "standard" or "advanced" picks up the new models. No other changes needed.

To mix providers per-slot, override with an explicit model in model_routing:

```json
"reviewer_b": { "tool": "task", "subagent": "plan-reviewer", "model": "openai/gpt-5.2" }
```

`model` takes precedence over `tier` when both are present.

---

## File Changes

### Keep from first attempt
- `.opencode/agents/*.md` — update to delegate to `.ai/roles/` instead of inlining instructions
- `.opencode/skills/quest/SKILL.md` — rewrite to use runtime-agnostic dispatch
- `opencode.json` — keep structure, remove per-agent `model` fields (allowlist drives models)
- `.opencode/commands/quest.md` — keep as-is

### Modify
- `.ai/allowlist.json` — bump to version 3, add `model_routing` + `model_tiers`
- `SKILL.md` (both Claude and OpenCode versions) — read routing from allowlist instead of hardcoding `mcp__codex__codex`
- `.opencode/agents/*.md` — delegate to `.ai/roles/*.md` (portable role definitions)

### Delete
- `.ai/allowlist-opencode.json` — absorbed into unified allowlist

---

## Open Questions

1. **Parallel task invocation in OpenCode** — does it support two `task` calls in the same turn? The current OpenCode SKILL.md notes "may not support true parallel." If not, reviewer_a and reviewer_b run sequentially. Not a blocker, just slower.

2. **Runtime detection** — how does the workflow know it's running in opencode vs claude? Options:
   - Check for `.opencode/` directory presence
   - Explicit `runtime` field in allowlist (user sets it)
   - Environment variable (`$OPENCODE_HOME` or similar)

3. **OpenCode Zen availability** — Big Pickle is free "for a limited time." Need a fallback tier mapping for when it goes paid.

4. **State management across subagent invocations** — Quest's orchestrator retains only artifact paths + one-line summaries between phases (Context Retention Rule). This works because state lives in `.quest/<id>/` files, not in conversation memory. OpenCode's `task` tool spawns independent sessions (navigable via `<Leader>+Right/Left`), so each subagent starts with a clean context — same as Claude Code's Task tool. The file-based handoff contract (HANDOFF block + artifact files) should transfer cleanly. **Needs verification:** does the parent agent reliably receive the subagent's final output text so it can parse the HANDOFF block? If not, the orchestrator falls back to reading artifact files directly (already works).

---

## Implementation Order

1. Abandon stalled quest `opencode-integration_2026-02-27__1200`
2. Start new quest with this design as the brief
3. Steps:
   a. Update allowlist schema to v3 with `model_routing` + `model_tiers`
   b. Update `.opencode/agents/*.md` to delegate to `.ai/roles/`
   c. Rewrite `.opencode/skills/quest/SKILL.md` with runtime-agnostic dispatch
   d. Slim down `opencode.json` (remove model duplication)
   e. Delete `.ai/allowlist-opencode.json`
   f. Test with all-Anthropic tiers first, then swap in opencode-native models

---

## References
- OpenCode docs: https://opencode.ai/docs/
- OpenCode agents: https://opencode.ai/docs/agents/
- OpenCode models: https://opencode.ai/docs/models/
- OpenCode MCP: https://opencode.ai/docs/mcp-servers/
- OpenCode config: https://opencode.ai/docs/config/
- Trinity Large Preview: https://www.arcee.ai/blog/trinity-large
