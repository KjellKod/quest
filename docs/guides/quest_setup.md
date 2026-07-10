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
| `quest_id_format` | `slug-first` (default) or `date-first`; affects only new Quest folder names |
| `review_mode` | `auto` (default), `fast`, or `full` for Codex reviews |
| `fast_review_thresholds` | File/LOC thresholds used when `review_mode: auto` |

Quest IDs use `<slug>_YYYY-MM-DD__HHMM` by default. Set `"quest_id_format": "date-first"` to create new quests as `YYYY-MM-DD_HHMM__<slug>` for chronological `.quest/` sorting. Existing folders are not renamed, and resume accepts both formats in mixed repositories.


### 2. Gitignore

Add to `.gitignore`:

```
.quest/
```

The `.quest/` folder contains ephemeral run state and should not be committed.

## One-Time MCP Setup (if using Codex)

If you want to use Codex for reviews and arbiter, add the config to `.claude/mcp.json` (see [Prerequisites](#optional-codex-mcp-for-dual-model-reviews) above).

This enables the `mcp__codex-cli__codex` tool for spawning Codex agents.

If you don't have Codex or prefer Claude for all roles, set the role models in
`.ai/allowlist.json` `models` (the same keys shown in the configuration table
above):

```json
{
  "models": {
    "planner": "claude",
    "plan-reviewer-b": "claude",
    "arbiter": "claude",
    "builder": "claude",
    "code-reviewer-b": "claude",
    "fixer": "claude"
  }
}
```

The plan and code reviewers will also fall back to Claude if Codex is unavailable.

## Codex-Led Claude Transports

When Codex orchestrates a quest, Claude-designated roles run through `scripts/quest_claude_runner.py`, which owns one of two transports underneath. Selection is config + probe driven (`.ai/allowlist.json` → `claude_role_transport`, default `auto`):

| Transport | Mechanism | Billing | When |
|---|---|---|---|
| **background-agent** (preferred) | `scripts/claude_bg_run.py` → `claude --bg` daemon-hosted session | **subscription pool** | default on dev machines once the one-time setup below is done |
| **bridge** (explicit) | `scripts/quest_claude_bridge.py` → `claude --print` | **API-metered after June 15, 2026** | daemonless contexts (CI, containers), `ANTHROPIC_API_KEY` billing, or an explicit user/config opt-in |

### One-time machine setup for the background-agent transport

1. `claude login` — subscription sign-in (browser).
2. Accept bypass mode once interactively: run `claude --dangerously-skip-permissions`, accept the disclaimer, exit. Background sessions refuse `bypassPermissions` until this has been done once per machine.
3. Claude CLI ≥ 2.1.143 (`claude --version`); sanity check: `claude agents --json` must print a JSON array.

With `auto` (the default), preflight probes the background-agent transport first. If it fails, Quest stops and asks you to fix bg, explicitly use the API-metered bridge for this run, continue single-model, or cancel. Forcing `"background-agent"` also blocks with remediation when unavailable; forcing `"bridge"` is the deliberate API-billing path.

If the warning says `bypassPermissions` is not accepted, run:

```bash
claude --dangerously-skip-permissions
```

Accept the prompt, exit Claude, return to Quest, and rerun preflight.

Quest sends the initial background prompt on stdin, not as a trailing argv argument. This became required starting with Claude Code 2.1.191, where positional prompt delivery registers a session but parks it at `idle — send a prompt to start`. If Quest still reports `bg_initial_prompt_not_consumed`, treat that as a bg prompt-delivery regression and use `"bridge"` only if you explicitly accept API-metered bridge billing.

`models.<role> = "claude"` is a sentinel for the Claude CLI/account default model. Quest passes the sentinel into its own runner, but the runner omits the CLI `--model` flag. If Claude rejects a concrete model, Quest reports `model_rejected` instead of downgrading or guessing.

To pin a **specific Claude model** for a role, put its full `claude-`-prefixed model ID in `models.<role>` (in `.ai/allowlist.json`, or per quest via the orchestration chooser override, e.g. `planner=claude-fable-5`): `claude-fable-5`, `claude-opus-4-8`, `claude-sonnet-5`, and so on. The ID passes verbatim to the CLI's `--model`. **Do not use bare CLI aliases like `opus` or `sonnet` in `models.<role>`** — Quest classifies the role's runtime by the `claude`/`claude-*` shape, so a bare alias would route the role to the Codex runtime. (Bare aliases are fine only when invoking `scripts/quest_claude_runner.py`/`quest_claude_probe.py` directly with `--model`.) To preflight a concrete model instead of the account default, set `QUEST_CLAUDE_PROBE_MODEL=claude-fable-5`.

**Prerequisites (both transports):** Claude CLI installed and authenticated (`claude auth status` should show a valid session).

If the preflight says the Claude transport is unavailable, first run `claude auth login` in a normal shell and re-check `claude auth status`. If browser login already succeeded but preflight still reports Claude as unavailable, rerun `./scripts/quest_preflight.sh --orchestrator codex` outside any restricted sandbox before concluding the transport is broken; some sandboxed runners cannot see the host Claude CLI auth state.

Successful Codex-led probes are retained for 12 hours: background-agent at `.quest/cache/claude_bg_codex.json`, bridge at `.quest/cache/claude_bridge_codex.json`. That avoids repeating the browser-login remediation on every quest start, but it does **not** make sandbox-local Claude auth trustworthy. Claude-designated roles still need to run in the same host-visible context that produced the successful probe. Override the retention window with `QUEST_PREFLIGHT_CACHE_TTL_SECONDS=<seconds>` or the cache paths with `QUEST_PREFLIGHT_CACHE_FILE=<path>` (bridge) / `QUEST_PREFLIGHT_BG_CACHE_FILE=<path>` (background-agent).

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

- Probes the configured transport once per session and retains recent successful host probes (bg under `auto`; bridge only when explicitly configured/selected)
- Sweeps orphaned `quest-<id>-*` background sessions and stale `quest-bg-probe-*` probe sessions at quest start/resume (`python3 scripts/claude_bg_run.py --sweep quest-<id>-` and `python3 scripts/claude_bg_run.py --sweep quest-bg-probe-`)
- Routes Claude-designated roles (planner, reviewer A, arbiter) through `scripts/quest_claude_runner.py --model <models.<role>> --transport <resolved>` in the same host-visible context used for the probe/cache refresh
- Keeps background-agent `needs_human` sessions parked for same-session resume, then resumes with `--resume <session_id> --answer-file <answer_file>` and updates the chained session id after Claude forks a continuation
- Records the transport per role in `context_health.log` (`transport=background-agent|bridge`) and reports it in the quest end summary and celebration
- Claude-led quests are unaffected, they keep native `Task(...)` execution

If the probe fails, Claude-designated roles will block until the CLI/auth setup is fixed.

### Optional: manual verification

If you want to test a transport before your first Codex-led quest, you can run the probe yourself:

```bash
command -v claude
claude auth status
claude agents --json
ls -la scripts/claude_bg_run.py
python3 scripts/quest_claude_probe.py \
  --quest-dir .quest/<id> \
  --model claude \
  --transport background-agent
```

This is the same bg probe Quest runs automatically under `auto`. It asks Claude to write a real artifact and a handoff JSON, proving the background-agent transport end-to-end. To test the explicit bridge path instead, use `--transport bridge --bridge-script scripts/quest_claude_bridge.py`.

## Resume and recovery

Quest can resume across orchestrators because the authoritative state lives in files, not in one chat transcript. After a Claude outage, rate/session limit, crash, or context loss, start Codex and run `$quest <quest-id>`. After a Codex outage, start Claude Code and run `/quest <quest-id>`. Resume reads `.quest/<id>/state.json` plus the existing plan, review, `handoff.json`, and log artifacts, so the next orchestrator can continue from the recorded phase.

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
