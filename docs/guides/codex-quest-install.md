# Installing Quest for Codex

## Why Quest May Not Show Up
Quest installed in a repository (`.agents/skills/quest`) is not automatically visible in Codex's global skill list. Codex discovers global skills from `~/.codex/skills` (plus system skills).

## Install Steps

1. Verify Quest exists in repo-local location:
```bash
ls -la .agents/skills/quest/SKILL.md
```

2. Install to global Codex skills:
```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo KjellKod/quest \
  --path .agents/skills/quest \
  --name quest
```

3. Verify installation:
```bash
ls -la ~/.codex/skills/quest/SKILL.md
```

4. Restart Codex so it reloads skills.

## Claude Bridge For Codex-Led Quests

Quest's default design assumes a Claude orchestrator can call Codex through MCP. For the inverse setup, where Codex orchestrates a quest and still needs Claude Opus review/planning slots, Codex needs a local Claude bridge.

This repo now provides that bridge at `scripts/claude_cli_bridge.py`.

### Prerequisites

1. Claude CLI installed and on `PATH`:
```bash
command -v claude
```

2. Claude CLI authenticated:
```bash
claude auth status
```

3. Bridge script present:
```bash
ls -la scripts/claude_cli_bridge.py
```

4. Bridge probe succeeds:
```bash
python3 scripts/quest_claude_probe.py \
  --quest-dir .quest/<id> \
  --model opus
```

### What This Enables

This bridge is the missing runtime adapter for Codex-led dual-model quests:
- Codex-native slots can stay on Codex
- Claude-native slots can be reached by shelling out through `scripts/claude_cli_bridge.py`
- Model diversity can remain symmetrical across Claude-led and Codex-led quest runs

### Runtime Behavior

With the current Quest workflow:
- Codex-native slots still run on Codex.
- Claude-designated slots in Codex-led quests run through `scripts/quest_claude_runner.py`.
- `scripts/claude_cli_bridge.py` remains the transport layer under that runner.
- Codex-led role execution uses `scripts/quest_claude_runner.py` so bridge calls default to `--permission-mode bypassPermissions`, add explicit repo/quest access via `--add-dir`, poll `handoff.json`, and append `context_health.log` automatically.
- Quest probes the bridge once per session before the first Claude-designated slot.
- Bridge-invoked Claude roles keep the normal `handoff.json` and artifact contracts, and `context_health.log` still records them as `runtime=claude`.

### Failure Handling

- Bridge timeout: retry once, then block the step if it still times out.
- Claude CLI missing or not authenticated: block immediately and fix the local Claude setup.
- Malformed output or missing handoff: retry once with a stricter reminder, then use text handoff fallback if available; otherwise block.

## Troubleshooting
If Quest still does not appear after restart, check:
- `~/.codex/skills/quest/SKILL.md` exists
- The file has valid frontmatter with `name: quest`
- Direct script execution may fail with permission issues — use `python3` prefix
