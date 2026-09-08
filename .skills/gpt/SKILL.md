---
name: gpt
description: Delegate a task to OpenAI Codex via MCP from Claude-led sessions. Use when the user invokes /gpt, asks to "use codex", "ask codex", "have codex do X", or when a second opinion or parallel implementation from a different model would be valuable.
---

# Skill: GPT (Codex)

Delegate tasks to OpenAI Codex via the `mcp__codex-cli__codex` MCP tool from Claude-led sessions.

## When to Use

- User types `/gpt` or `/gpt <task>`
- User asks to "use codex", "ask codex", "have codex review/write/analyze..."
- User wants a second opinion from a different model
- Claude-led Quest workflow routes a role to Codex (builder, fixer, code-reviewer-b, plan-reviewer-b)

## Not for Codex-Led Quest Role Dispatch

If you are already Codex and a Quest role is assigned to Codex, do not call Codex MCP to create another Codex role. Codex-led Quest dispatch must use local Codex subagents (the `spawn_agent` tool family — versioned namespace varies by Codex CLI release — or the repo-supported equivalent) using the saved model and effort, following the canonical dispatch contract in `.skills/quest/delegation/workflow.md`.

Codex MCP is only the cross-runtime path when the orchestrator is Claude-led and needs to dispatch a Codex runtime role. A Codex-led attempt to use `mcp__codex*`, `codex_codex`, `codex mcp-server`, or Codex CLI model aliases for a Codex role is an orchestration violation, not a model-selection problem.

## Prerequisites

Codex MCP server must be registered. Run once globally:
```bash
claude mcp add --scope user codex-cli -- codex mcp-server
```
If Codex isn't connecting, also run `claude mcp add codex-cli -- codex mcp-server` inside the repo.

If the tool `mcp__codex-cli__codex` is not available, tell the user to add the config above and restart Claude Code.

## Step 1: Confirm Before Calling From Claude

Before invoking Codex from a Claude-led session, **always tell the user what you're about to do** and wait for confirmation:

```
I'll delegate this to Codex with:
- **Model:** <resolved model>
- **Reasoning:** <resolved effort or runtime default>
- **Sandbox:** workspace-write

Continue? (y/n)
```

Resolve settings before displaying the preview:
- Quest role: use `models.<role>` and optional `codex_reasoning_effort` from the saved `orchestration.json`. Follow the Quest gate authorization already given.
- Standalone `/gpt`: use an explicit user selection first; otherwise use `.ai/allowlist.json` `codex_fallback_model` and optional `codex_reasoning_effort`. If no repo configuration exists, omit these parameters and disclose that the runtime defaults apply.
- Validate availability against the current tool/account. Do not maintain a model catalog or presume an unlisted model works.
- Choose sandbox from task needs and the role's permissions.

## Step 2: Call via MCP From Claude

For this Claude-led skill, use the MCP tool. **Never shell out to `codex exec`.** Do not use this step for Codex-led Quest role dispatch; use local Codex subagents there.

```
mcp__codex-cli__codex({
  prompt: "<task description>",
  model: "<resolved model>",
  sandbox: "workspace-write",
  fullAuto: true,
  config: { model_reasoning_effort: "<resolved effort>" } // omit when unset
})
```

> Reasoning effort is **not** a top-level `reasoningEffort` param — the MCP schema doesn't accept one. It must be passed inside `config` as `model_reasoning_effort`. Passing `reasoningEffort` at top level is silently ignored.

## Parameters

| Parameter | Default | When to change |
|-----------|---------|----------------|
| `model` | Resolved configuration | Explicit user override or saved Quest role assignment |
| `config.model_reasoning_effort` | Resolved configuration, omitted when unset | Explicit effort change supported by the model; pass inside `config` |
| `sandbox` | `workspace-write` | `read-only` for pure Q&A with no file output. `danger-full-access` **only with explicit user permission** — needed for network access, system commands, or out-of-workspace writes |
| `fullAuto` | `true` | Leave true unless user wants approval prompts |
| `sessionId` | (none) | Set to continue a previous Codex conversation within the same task |

## Sandbox Discipline

- **`workspace-write`** (default) — Codex can read everything, write within the project. Covers reviews, implementation, refactoring, test writing.
- **`read-only`** — Pure analysis, explanation, Q&A. No file writes at all.
- **`danger-full-access`** — Full system access. **Always ask the user before using this.** Needed when: installing dependencies, network calls, accessing files outside the workspace.

When called from Claude-led Quest orchestration, match the sandbox to the role:
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
- If Codex's response seems incomplete, retry with an explicitly selected, supported higher `config.model_reasoning_effort` or a more specific prompt
- If Codex returns an error, report it clearly — MCP gives structured errors, no guessing needed

## What This Skill Does NOT Cover

- **Arbitration between Claude and Codex** — handled by Quest's arbiter role
- **Critical evaluation of Codex output** — handled by Quest's review pipeline
- **Model routing for Quest phases** — handled by `allowlist.json` and `workflow.md`

This skill is the transport and invocation layer. Quest orchestration handles the judgment layer.
