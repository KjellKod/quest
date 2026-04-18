# Quest Setup Guide

How to add the `/quest` and `$quest` multi-agent orchestration system to your repository.

This is the single setup source of truth. Use the README for the quick start; use this guide for the full install and configuration path.

## Prerequisites

### Required: Claude Code CLI

Claude Code is Anthropic's official CLI for Claude. Install it:

```bash
# Install via npm
npm install -g @anthropic-ai/claude-code

# Authenticate
claude auth
```

**Documentation:** https://docs.anthropic.com/en/docs/claude-code

### Optional: Codex MCP (for dual-model reviews)

Quest can use Codex as a second reviewer. This gives you two different model families reviewing your code (different blind spots).

**Requires:**
- [Codex CLI](https://developers.openai.com/codex/cli/) installed globally (`npm i -g @openai/codex`)
- Either `OPENAI_API_KEY` in your environment or a Codex login (`codex` → `/login`)

Register the Codex MCP server globally (one-time setup):

```bash
claude mcp add --scope user codex-cli -- codex mcp-server
```

> **Note:** If a repo has its own `.claude/mcp.json`, it shadows the global config. In that case, also run `claude mcp add codex-cli -- codex mcp-server` inside that repo so the project-level config includes it too. If Codex isn't connecting for any reason, running the per-repo command is a safe first troubleshooting step.

**Verify it's registered:** `claude mcp list` should show `codex-cli` as a configured server.

**Add the permission** so Claude Code won't prompt on every Codex call:

```bash
# If you have jq installed:
jq '.permissions.allow += ["mcp__codex-cli__*"]' ~/.claude/settings.json > /tmp/cs.json && mv /tmp/cs.json ~/.claude/settings.json
```

Or manually add `"mcp__codex-cli__*"` to the `permissions.allow` array in `~/.claude/settings.json`.

> **Why `codex-cli` not `codex`?** The MCP server self-identifies as `codex-cli` at startup, so Claude Code names the tools `mcp__codex-cli__codex`, `mcp__codex-cli__review`, etc. — regardless of what you called it in your config.

If the MCP server isn't showing up, you can manually add it to `.claude/mcp.json` as a last resort:

```json
{
  "mcpServers": {
    "codex-cli": {
      "command": "codex",
      "args": ["mcp-server"]
    }
  }
}
```

**Documentation:** https://platform.openai.com/docs/quickstart

If you skip this, Quest uses Claude for all roles (still works, just single-model).

### Optional: jq (for validation)

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt install jq
```

Used by the validation script for JSON checks. Falls back to basic validation if missing.

## Installation

### Option A: Use the Installer (Recommended)

```bash
# Download the installer
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh -o quest_installer.sh
chmod +x quest_installer.sh

# Preview what will be installed (dry-run)
./quest_installer.sh --check

# Install Quest
./quest_installer.sh

# For CI/automation (non-interactive)
./quest_installer.sh --force
```

The installer:
- Handles fresh installs AND updates
- Tracks file checksums to detect your modifications
- Preserves local customizations and writes `.quest_updated` sidecars when manual merge is needed
- Updates `AGENTS.md` in place only when it still matches the stored Quest-managed checksum
- Self-updates when a newer version is available

To use Quest as a global Codex skill outside a specific repo, see [Installing Quest for Codex](codex-quest-install.md).

### Option B: Manual Copy

## What to Copy

Copy these folders to your repository root:

```
.ai/                              # Source of truth (AI-agnostic)
  allowlist.json                  # Permission configuration
  quest.md                        # Quick reference
  roles/                          # Agent role definitions
    quest_agent.md
  schemas/
    handoff.schema.json           # Inter-agent communication contract
  templates/
    quest_brief.md
    plan.md
    review.md
    pr_description.md


.skills/quest/                    # Full skill procedure (AI-agnostic)
  SKILL.md
  agents/                         # Quest-owned role files
    planner.md
    plan-reviewer.md
    arbiter.md
    builder.md
    code-reviewer.md
    fixer.md

.agents/skills/                   # Codex thin wrapper layer for repo-local user-invocable skills
  quest/SKILL.md                  # Thin wrapper → .skills/quest/
  celebrate/SKILL.md              # Thin wrapper → .skills/celebrate/
  pr-assistant/SKILL.md           # Thin wrapper → .skills/pr-assistant/
  pr-shepherd/SKILL.md            # Thin wrapper → .skills/pr-shepherd/
  git-commit-assistant/SKILL.md   # Thin wrapper → .skills/git-commit-assistant/

.claude/                          # Claude Code integration layer
  skills/quest/SKILL.md           # Thin wrapper → .skills/quest/
  agents/                         # Thin wrappers → .skills/quest/agents/
    planner.md
    plan-reviewer.md
    arbiter.md
    builder.md
    code-reviewer.md
    fixer.md
  hooks/
    enforce-allowlist.sh          # Permission enforcement
```

## What to Edit

### 1. Allowlist Configuration (`.ai/allowlist.json`)

Update the `role_permissions` section to match your project structure:

```json
{
  "role_permissions": {
    "builder_agent": {
      "file_write": [
        ".quest/**",
        "src/**",           // Your source directories
        "tests/**",
        "docs/**"
      ],
      "bash": ["npm test", "npm run build", "pytest"]  // Your test commands
    },
    "fixer_agent": {
      "file_write": [
        ".quest/**",
        "src/**",
        "tests/**"
      ],
      "bash": ["npm test", "pytest"]
    }
  }
}
```

Key sections to customize:

| Section | What to change |
|---------|---------------|
| `role_permissions.builder_agent.file_write` | Paths where builder can write (source, tests, docs) |
| `role_permissions.fixer_agent.file_write` | Paths where fixer can write (usually same as builder minus docs) |
| `role_permissions.*.bash` | Shell commands each role can run (test runners, build tools) |
| `auto_approve_phases` | Which phases run without human confirmation |
| `models.arbiter` | Set to `"claude"` or `"gpt-5.4"` to choose arbiter runtime |
| `review_mode` | `auto` (default), `fast`, or `full` for Codex reviews |
| `fast_review_thresholds` | File/LOC thresholds used when `review_mode: auto` |


### 2. Gitignore

Add to `.gitignore`:

```
.quest/
```

The `.quest/` folder contains ephemeral run state and should not be committed.

## One-Time MCP Setup (if using Codex)

If you want to use Codex for reviews and arbiter, add the config to `.claude/mcp.json` (see [Prerequisites](#optional-codex-mcp-for-dual-model-reviews) above).

This enables the `mcp__codex-cli__codex` tool for spawning Codex agents.

If you don't have Codex or prefer Claude for all roles, set in `allowlist.json`:

```json
{
  "arbiter": {
    "tool": "claude"
  }
}
```

The plan and code reviewers will also fall back to Claude if Codex is unavailable.

If you want Codex to discover Quest as a global skill (outside the repository), see [Installing Quest for Codex](codex-quest-install.md).

## Codex-Led Claude Bridge

When Codex orchestrates a quest, it probes and sets up the Claude bridge before the first Claude-designated role. For browser-login auth, Quest treats Claude availability as host-context state, not sandbox-local state.

**Prerequisites:** Claude CLI installed and authenticated (`claude auth status` should show a valid session).

If the preflight says the Claude bridge is unavailable, first run `claude auth login` in a normal shell and re-check `claude auth status`. If browser login already succeeded but preflight still reports Claude as unavailable, rerun `./scripts/quest_preflight.sh --orchestrator codex` outside any restricted sandbox before concluding the bridge is broken; some sandboxed runners cannot see the host Claude CLI auth state.

A successful Codex-led Claude bridge probe is retained at `.quest/cache/claude_bridge_codex.json` by default for 12 hours. That avoids repeating the browser-login remediation on every quest start, but it does **not** make sandbox-local Claude auth trustworthy. Claude-designated roles still need to run in the same host-visible context that produced the successful probe. Override the retention window with `QUEST_PREFLIGHT_CACHE_TTL_SECONDS=<seconds>` or the cache path with `QUEST_PREFLIGHT_CACHE_FILE=<path>`.

### What the bridge does

Quest uses a purpose-built CLI bridge (`scripts/quest_claude_bridge.py`) instead of MCP for cross-model calls. This gives Quest per-invocation control that a static MCP connection can't provide:

- **Filesystem scoping**, each role gets access to only the directories it needs via `--add-dir`
- **Permission modes**, builder runs with `bypassPermissions`, read-only roles use `plan` mode
- **Tool restrictions**, reviewers can't write files, planners can't run arbitrary bash
- **Handoff polling**, the runner watches for `handoff.json` on disk instead of retaining Claude's full response in the Codex orchestrator's context
- **Context health logging**, every cross-model call is logged to `.quest/<id>/logs/context_health.log` with timestamp, phase, agent, runtime, and handoff state
- **True isolation**, each call is a fresh `claude --print` invocation with no session state between roles

The bridge script itself is Quest-agnostic, it's a generic utility for calling Claude CLI with structured options. The Quest-specific behavior (handoff polling, logging, text fallback) lives in `quest_claude_runner.py`.

For the full architecture rationale, see [Why the Bridge, Not MCP](quest_presentation.md#why-the-bridge-not-mcp) in the presentation doc.

### What Quest handles automatically

- Probes `scripts/quest_claude_bridge.py` once per session and retains a recent successful host probe
- Routes Claude-designated roles (planner, reviewer A, arbiter) through `scripts/quest_claude_runner.py` in the same host-visible context used for the probe/cache refresh
- Claude-led quests are unaffected, they keep native `Task(...)` execution

If the probe fails, Claude-designated roles will block until the CLI/auth setup is fixed.

### Optional: manual verification

If you want to test the bridge before your first Codex-led quest, you can run the probe yourself:

```bash
command -v claude
claude auth status
ls -la scripts/quest_claude_bridge.py
python3 scripts/quest_claude_probe.py \
  --quest-dir .quest/<id> \
  --model opus
```

This is the same probe Quest runs automatically. It asks Claude to write a real artifact and a handoff JSON, proving the bridge works end-to-end. Useful for debugging if Claude-designated roles aren't connecting.

If you need Codex to discover Quest as a global skill outside the repository, see [Installing Quest for Codex](codex-quest-install.md).

## Verification

After setup, verify everything is in place:

1. **Check files exist:**
   ```bash
   ls -la .ai/allowlist.json
   ls -la .agents/skills/quest/SKILL.md
   ls -la .claude/skills/quest/SKILL.md
   ls -la .claude/agents/
   ls -la .claude/hooks/enforce-allowlist.sh
   ls -la scripts/quest_claude_bridge.py
   ls -la scripts/quest_claude_probe.py
   ls -la scripts/quest_claude_runner.py
   ```

2. **Validate allowlist:**
   ```bash
   jq '.' .ai/allowlist.json
   ```

3. **Check hook is executable:**
   ```bash
   test -x .claude/hooks/enforce-allowlist.sh && echo "OK" || echo "Run: chmod +x .claude/hooks/enforce-allowlist.sh"
   ```

4. **Test the skill loads:**
   ```
   /quest status
   $quest status
   ```

## Usage

Once set up, use the Quest command from your client:

```
/quest "Add a loading skeleton to the candidate list"
$quest "Add a loading skeleton to the candidate list"
```

See `.ai/quest.md` for full usage documentation.

## How It Works

### Clean Context Architecture

Each agent runs in **complete isolation** — no shared conversation history:

**Claude agents** (planner, builder, fixer, plan-reviewer):
- Spawned via Task tool with `subagent_type: general-purpose`
- Receive assembled prompt with role instructions from `.skills/quest/agents/*.md`
- Start fresh, return handoff when done

**Codex agents** (code-reviewer, arbiter when configured):
- Called via `mcp__codex-cli__codex` MCP tool
- Completely separate model (GPT 5.x)
- Receive assembled prompt, return handoff

### Human as Gatekeeper

The orchestrator (Claude following the skill) pauses for human approval at configured gates:

```json
// .ai/allowlist.json
"auto_approve_phases": {
  "plan_creation": true,      // Auto-proceed
  "implementation": false,    // STOP: Ask human
  "fix_loop": false           // STOP: Ask human
}
```

### Dual-Model Review

Plans are reviewed by both Claude AND Codex independently:
- Different model families catch different blind spots
- Arbiter synthesizes both reviews, filters nitpicks
- Prevents groupthink and improves plan quality

## Customizing Roles

The agent role definitions in `.skills/quest/agents/*.md` are the source of truth. The quest router role stays in `.ai/roles/quest_agent.md`. The `.claude/agents/*.md` files are thin wrappers that serve as documentation and reference. See `.skills/quest/agents/README.md` for how agent wiring files relate to portable skills.

To customize behavior, edit `.skills/quest/agents/` (or `.ai/roles/quest_agent.md` for routing behavior). The wrapper files rarely need changes.

## Troubleshooting

### "Permission denied" when writing files

Check that your `allowlist.json` has the correct paths in `file_write` for the role that's failing. Paths use glob patterns:

- `src/**` matches `src/foo.ts` and `src/bar/baz.ts`
- `*.md` matches markdown files in the root only
- `**/*.test.ts` matches test files anywhere

### Arbiter/reviewers not using Codex

If you have Codex installed but it's not being used:

1. Check MCP is configured: `claude mcp list`
2. Verify `allowlist.json` has `"arbiter": {"tool": "codex"}`
3. The system falls back to Claude if Codex fails

### Quest state is stale

Quest state is stored in `.quest/<id>/state.json`. To reset:

```bash
rm -rf .quest/<quest-id>
```

Or remove just the state file to replay from the beginning:

```bash
rm .quest/<quest-id>/state.json
```

## File Layout Summary

```
your-repo/
├── .ai/                          # Source of truth (AI-agnostic)
│   ├── allowlist.json            # Permissions (edit this)
│   ├── quest.md                  # Quick reference
│   ├── roles/                    # Agent behavior definitions
│   ├── schemas/                  # Handoff contract
│   └── templates/                # Document templates
├── .skills/
│   └── quest/
│       └── SKILL.md              # Full skill procedure (AI-agnostic)
├── .agents/
│   └── skills/quest/
│       └── SKILL.md              # Thin wrapper → .skills/quest/ (Codex)
├── .claude/
│   ├── agents/                   # Thin wrappers (reference only)
│   ├── hooks/
│   │   └── enforce-allowlist.sh  # Permission enforcement
│   ├── settings.json             # Claude Code settings
│   └── skills/quest/
│       └── SKILL.md              # Thin wrapper → .skills/quest/
└── .quest/                       # Ephemeral run state (gitignored)
    ├── briefs/                   # Saved quest briefs
    └── <quest-id>/               # Per-quest run folders
        ├── state.json            # Current phase/status
        ├── quest_brief.md        # The brief for this quest
        ├── phase_01_plan/        # Plan artifacts
        ├── phase_02_implementation/
        ├── phase_03_review/
        └── logs/                 # Raw agent outputs
```

**Note:** Source of truth is always in AI-agnostic locations (`.ai/`, `.skills/`). Wrapper folders (`.claude/`, `.agents/`) delegate to the portable definitions.
