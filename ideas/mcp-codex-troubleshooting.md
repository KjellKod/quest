---
title: MCP Codex Timeout Blocks OpenCode Command Autocomplete
purpose: Document root cause and fix for custom commands not appearing in OpenCode autocomplete
audience: Quest maintainers
status: active
---

# MCP Codex Timeout Blocks OpenCode Command Autocomplete

## Problem

Custom commands (`/quest`, `/celebrate`) don't appear in OpenCode's autocomplete for ~60 seconds after startup. Only built-in commands like `/models` show up. After the timeout fires, custom commands appear.

## Root Cause

OpenCode's `Command.list()` function loads commands from three sources **sequentially**:

1. Built-in commands (instant)
2. Config-defined commands from `opencode.json` (instant)
3. **MCP prompts from all connected MCP servers** (blocks on timeout)
4. Skill-sourced commands (blocked by step 3)

Step 3 calls `client.listPrompts()` for every MCP server. The Codex MCP server doesn't support the `prompts/list` method, causing a **60-second timeout**. The entire command list is held up until this completes.

### Two MCP Servers Are Loaded

Even when running "just Claude Opus 4.6" (no MCP intended), OpenCode loads MCP servers from both configs:

| Config | Server | Source |
|--------|--------|--------|
| `~/.config/opencode/opencode.json` | `codex` | Global config |
| `.opencode/opencode.json` | `mcp__codex` | Project config |

The `mcp__codex` server connects and exposes tools, but does NOT support `prompts/list`. The SDK's default timeout on `listPrompts()` is ~60 seconds.

### Evidence from Logs

From `/Users/kjell/.local/share/opencode/log/2026-03-05T052958.log`:

```
Line 60-61: GET /command starts at 05:29:59
Line 983:   ERROR service=mcp clientName=mcp__codex error=MCP error -32001: Request timed out failed to get prompts
Line 984:   GET /command completes at 05:31:00 with duration=61021ms (61 seconds)
```

## Fix Applied (2026-03-05)

### Attempt 1: Remove MCP section entirely

Removed the `mcp` section from `.opencode/opencode.json`.

**Result:** `/quest` and `/celebrate` commands appeared in autocomplete immediately. However, quest agents that use Codex via MCP (`mcp__codex__codex` tool calls in the workflow) lost access to Codex.

### Attempt 2: Replace with correct MCP server

The project config had a broken MCP server:
```json
// BROKEN — uses `codex` CLI directly, doesn't support prompts/list, 120s timeout
"mcp__codex": {
  "type": "local",
  "command": ["codex", "-m", "gpt-5.3-codex", "mcp-server"],
  "timeout": 120000
}
```

The global config (`~/.config/opencode/opencode.json`) uses the correct server:
```json
// WORKS — uses @cexll/codex-mcp-server via npx
"codex": {
  "type": "local",
  "command": ["npx", "-y", "@cexll/codex-mcp-server"],
  "enabled": true
}
```

**Final fix:** Replaced the project-level MCP with the correct server and a 5s timeout:
```json
"mcp": {
  "codex": {
    "type": "local",
    "command": ["npx", "-y", "@cexll/codex-mcp-server"],
    "enabled": true,
    "timeout": 5000
  }
}
```

### Key findings

1. **Two different Codex MCP servers exist:** The `codex` CLI's built-in `mcp-server` mode and `@cexll/codex-mcp-server` (npm package). The CLI version doesn't support `prompts/list` and causes the 60s timeout.
2. **The `gpt-5.3-codex` model doesn't exist** in the current OpenAI project (`proj_zvJsIK0hs9A0vpxzXIimuVPB`), causing `model_not_found` errors. This is a separate issue from the MCP timeout — it affects the OpenCode agent configs (plan-reviewer-b, code-reviewer-b) which reference `opencode/gpt-5.3-codex` as their model.
3. **Timeout must be short.** Even with the correct server, `Command.list()` blocks on `MCP.prompts()`. A 5s timeout ensures commands appear quickly.

## Impact

This affects ALL custom commands in the project, not just `/celebrate`. The `/quest` command that was previously working is also blocked by this timeout. The issue is pre-existing in the quest repo's `.opencode/opencode.json` — it wasn't caused by the celebration changes.

## How to Verify

Check OpenCode logs after startup:

```bash
ls -t ~/.local/share/opencode/log/ | head -1 | xargs -I{} grep "GET /command" ~/.local/share/opencode/log/{}
```

If the duration is >5000ms, the MCP timeout is the culprit.

## Resolved: gpt-5.3-codex Model Access

The OpenCode agent configs for `plan-reviewer-b` and `code-reviewer-b` referenced `opencode/gpt-5.3-codex`, which was not accessible from the current OpenAI project.

**Fix applied:** Changed both to `opencode/gpt-5.4` (the current flagship model, combines coding + reasoning + tool use).

**Location:** `.opencode/opencode.json` lines 65 and 134 (plan-reviewer-b, code-reviewer-b)

**Available Codex models** (from https://developers.openai.com/codex/models):
- `gpt-5.4` — flagship, recommended for most tasks
- `gpt-5.3-codex` — industry-leading coding (requires project access)
- `gpt-5.3-codex-spark` — near-instant real-time (ChatGPT Pro only)
- `gpt-5.2-codex`, `gpt-5.1-codex-max`, `gpt-5.1`, `gpt-5` — older alternatives

## MCP Server Migration: Tool Name Change

### Old server (broken)
- Server name: `mcp__codex`  
- Command: `codex -m gpt-5.3-codex mcp-server` (Codex CLI built-in)
- Tool exposed: `codex` → OpenCode tool name: `mcp__codex__codex`
- Problem: doesn't support `prompts/list`, 60s timeout; model not found

### Interim server (third-party, replaced)
- Server name: `codex`
- Command: `npx -y @cexll/codex-mcp-server`
- Tool exposed: `ask-codex` → OpenCode tool name: `codex_ask-codex`
- Also exposes: `ping`, `Help`, `version`
- Problem: third-party package, different tool interface than official

### Final server (official Codex CLI MCP — current)
- Server name: `codex`
- Command: `npx -y codex mcp-server`
- Tools exposed: `codex` (start session), `codex-reply` (continue session) → OpenCode tool names: `codex_codex`, `codex_codex-reply`
- Accepts: `prompt`, `model`, `approval-policy`, `sandbox`, `cwd`, `config`, `profile`, `base-instructions`
- Verified working: tested manually via stdin JSON-RPC protocol
- Reference: https://developers.openai.com/codex/guides/agents-sdk/

### Files updated per platform

**OpenCode (`.opencode/`):**
- `.opencode/opencode.json` — MCP command changed to `["npx", "-y", "codex", "mcp-server"]`, models to `gpt-5.4`
- `.opencode/agents/quest.md` — tool reference changed to `codex_codex` and `codex_codex-reply`

**Claude Code (`.claude/`):**
- `.claude/mcp.json` — removed `-m gpt-5.3-codex` flag, now just `codex mcp-server` (uses default model)
- `.claude/settings.local.json` — unchanged, `mcp__codex__codex` permission stays (tool name didn't change, only the server command)

**Codex CLI (`.codex/`):**
- No changes needed — Codex CLI doesn't use MCP to call itself

**Global config (`~/.config/opencode/opencode.json`):**
- Updated to use official `codex mcp-server` instead of `@cexll/codex-mcp-server`

**Shared files (untouched):**
- `.skills/quest/delegation/workflow.md` — references `mcp__codex__codex` throughout; Claude Code resolves this correctly since the server is still named `codex` and the tool is still `codex`
- `.skills/quest/agents/*.md` — mention `mcp__codex__codex` as default; platform-specific configs handle the mapping

## Impact

This affects ALL custom commands in the project, not just `/celebrate`. The `/quest` command that was previously working is also blocked by this timeout. The issue is pre-existing in the quest repo's `.opencode/opencode.json` — it wasn't caused by the celebration changes.

## How to Verify

Check OpenCode logs after startup:

```bash
ls -t ~/.local/share/opencode/log/ | head -1 | xargs -I{} grep "GET /command" ~/.local/share/opencode/log/{}
```

If the duration is >5000ms, the MCP timeout is the culprit.
