---
title: OpenCode Quickstart Guide
purpose: Setup and usage instructions for running Quest from the OpenCode runtime.
audience: Developers using OpenCode CLI
scope: OpenCode integration
status: active
owner: maintainers
---

# OpenCode Quickstart Guide

Run the full Quest multi-agent pipeline from the OpenCode CLI using free Zen models.

## What is OpenCode?

OpenCode is an open-source terminal-based AI coding assistant. Quest integrates with OpenCode as a third runtime alongside Claude Code and Codex.

## Prerequisites

- OpenCode CLI installed and configured
- Access to free Zen models (no API key required for free tier)

## Available Free Zen Models

| Model | Tier | Status |
|-------|------|--------|
| big-pickle | Primary | Active |
| minimax-m2.5-free | Secondary | Active |
| gpt-5-nano | Secondary | Active |
| kimi-k2.5-free | -- | Expired |

Model defaults are documented in `.ai/allowlist.json` under `model_routing.opencode`. The authoritative model assignments live in `.opencode/opencode.json` (per-agent `model` fields) — that's what OpenCode actually uses at runtime.

## Setup

1. Ensure your repository has the Quest `.opencode/` directory (included if you installed Quest via the installer or manual copy).

2. Verify the configuration:
   ```bash
   bash scripts/validate-quest-config.sh
   ```

3. Check that `.ai/allowlist.json` has `model_routing.opencode` configured (v3 format).

## Running Quest

```bash
# Start OpenCode in your repo root
opencode

# Run a quest
/quest "Add a loading skeleton to the user list"
```

The `/quest` command reads `.opencode/skills/quest/SKILL.md`, which delegates to the shared workflow at `.skills/quest/delegation/workflow.md`.

## How It Works

OpenCode Quest uses the same shared workflow as Claude Code and Codex:

```
.opencode/skills/quest/SKILL.md    -- thin shim (sets runtime context)
    --> .skills/quest/delegation/workflow.md  -- shared orchestration
    --> .skills/quest/agents/*.md             -- shared agent definitions
```

Subagents are invoked via OpenCode's `task` tool, referencing agents defined in `.opencode/agents/`. Each agent file points to the shared role definition in `.skills/quest/agents/`.

Review artifacts use runtime-agnostic naming: `review_reviewer_a.md` / `review_reviewer_b.md` (not claude/codex).

## Troubleshooting

### Artifact files missing after task calls

OpenCode `task` subagents may return content in their response without writing files to disk. The workflow includes an artifact persistence rule: after each task call, the orchestrator verifies files exist and writes them if missing.

### Model availability

Free Zen models may expire or become unavailable. Check the `model_tiers.opencode.expired` list in `allowlist.json` for known expired models. If a model fails, try switching to another model in the `model_routing.opencode` section.

### Path resolution

OpenCode `{file:...}` paths resolve relative to `.opencode/`, not the repo root. The agent files use plain markdown paths (not `{file:...}` syntax) to reference shared skill files from the repo root.
