---
name: gpt
description: Delegate a task to OpenAI Codex via MCP. Use when the user invokes /gpt, asks to "use codex", "ask codex", "have codex do X", or when a second opinion or parallel implementation from a different model would be valuable.
---

# Skill: GPT (Codex)

Delegate tasks to OpenAI Codex via the `mcp__codex-cli__codex` MCP tool.

## When to Use

- User types `/gpt` or `/gpt <task>`
- User asks to "use codex", "ask codex", "have codex review/write/analyze..."
- User wants a second opinion from a different model
- Quest workflow routes a role to Codex (builder, fixer, code-reviewer-b, plan-reviewer-b)

## Prerequisites

Codex MCP server must be registered. Run once globally:
```bash
claude mcp add --scope user codex-cli -- codex mcp-server
```
If Codex isn't connecting, also run `claude mcp add codex-cli -- codex mcp-server` inside the repo.

If the tool `mcp__codex-cli__codex` is not available, tell the user to add the config above and restart Claude Code.

## Step 1: Confirm Before Calling

Before invoking Codex, **always tell the user what you're about to do** and wait for confirmation:

```
I'll delegate this to Codex with:
- **Model:** gpt-5.4
- **Reasoning:** high
- **Sandbox:** workspace-write

Continue? (y/n)
```

Adjust the defaults based on task complexity:
- Simple question/hello world → `low` reasoning, `read-only` sandbox
- Code review/analysis → `high` reasoning, `workspace-write` sandbox
- Complex architecture/refactor → `xhigh` reasoning, `workspace-write` sandbox
- Needs network/system access → `danger-full-access` sandbox (**always call this out explicitly**)

If the user specifies reasoning or model in their request, use what they asked for.

## Step 2: Call via MCP

Always use the MCP tool. **Never shell out to `codex exec`.**

```
mcp__codex-cli__codex({
  prompt: "<task description>",
  model: "gpt-5.4",
  reasoningEffort: "high",
  sandbox: "workspace-write",
  fullAuto: true
})
```

## Available Models

Use `gpt-5.4` unless the user requests otherwise. The MCP tool schema may lag behind — `gpt-5.4` works even if not listed in the schema's enum.

Known working models:
`gpt-5.4`, `gpt-5.3-codex`

## Parameters

| Parameter | Default | When to change |
|-----------|---------|----------------|
| `model` | `gpt-5.4` | Only if user requests a specific model |
| `reasoningEffort` | `high` | `low`/`medium` for simple tasks, `xhigh` for complex architecture |
| `sandbox` | `workspace-write` | `read-only` for pure Q&A with no file output. `danger-full-access` **only with explicit user permission** — needed for network access, system commands, or out-of-workspace writes |
| `fullAuto` | `true` | Leave true unless user wants approval prompts |
| `sessionId` | (none) | Set to continue a previous Codex conversation within the same task |

## Sandbox Discipline

- **`workspace-write`** (default) — Codex can read everything, write within the project. Covers reviews, implementation, refactoring, test writing.
- **`read-only`** — Pure analysis, explanation, Q&A. No file writes at all.
- **`danger-full-access`** — Full system access. **Always ask the user before using this.** Needed when: installing dependencies, network calls, accessing files outside the workspace.

When called from Quest orchestration, match the sandbox to the role:
- Builder/Fixer: `workspace-write`
- Reviewers: `workspace-write` (may write review artifacts)
- Analysis-only: `read-only`

## Crafting the Prompt

Be specific. Codex runs non-interactively — it can't ask clarifying questions.

Include:
- What to do (clear task description)
- Where to look (file paths, directories)
- What constraints apply (don't modify X, follow pattern Y)
- What output to produce (write to file, return analysis, make changes)

Bad: `"Review this code"`
Good: `"Review src/auth/middleware.ts for security issues. Focus on session handling and input validation. Write findings to .quest/<id>/reviews/codex-review.md"`

## Session Continuity

Use `sessionId` to maintain conversation context across multiple calls:

```
// First call
mcp__codex-cli__codex({ prompt: "Analyze the auth module...", sessionId: "auth-review-1" })

// Follow-up
mcp__codex-cli__codex({ prompt: "Now refactor the issues you found", sessionId: "auth-review-1" })
```

## Interpreting Results

- Summarize findings for the user — don't dump raw output
- If Codex's response seems incomplete, retry with higher `reasoningEffort` or a more specific prompt
- If Codex returns an error, report it clearly — MCP gives structured errors, no guessing needed

## What This Skill Does NOT Cover

- **Arbitration between Claude and Codex** — handled by Quest's arbiter role
- **Critical evaluation of Codex output** — handled by Quest's review pipeline
- **Model routing for Quest phases** — handled by `allowlist.json` and `workflow.md`

This skill is the transport and invocation layer. Quest orchestration handles the judgment layer.
