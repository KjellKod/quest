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

### Optional: Codex CLI (for Codex-backed roles)

Claude-led Quest and `/gpt` use the installed `scripts/quest_codex_runner.py` helper. Codex-led Codex roles use native subagents. Neither path requires a Codex MCP server, shim or plugin.

Install [Codex CLI](https://developers.openai.com/codex/cli/) (`npm i -g @openai/codex`), then prefer cached ChatGPT authentication:

```bash
codex login
codex login status
./scripts/quest_preflight.sh --orchestrator claude --codex-auth cached
```

Expected: login status reports ChatGPT and preflight reports `available: true`. The probe verifies CLI capabilities and selected credential readiness without inference (`inference_verified: false`). A model or credential can still be rejected during actual execution.

For explicitly selected API billing, provide `CODEX_API_KEY` or `OPENAI_API_KEY` through the existing environment and select `.ai/allowlist.json` `codex_auth_mode: "api-key"`, or request API-key mode at Quest startup. `--codex-auth api-key` overrides the allowlist for that probe; startup saves the resolved selection in `orchestration.json`. `CODEX_API_KEY` takes precedence when both keys exist. This mode does not require or modify cached login. Never paste keys into prompts or logs. Quest does not read `.env` for credentials.

The default `cached` mode excludes ambient API keys and uses the CLI's saved identity. Setup prefers ChatGPT; a deliberately cached API identity is reported as such. Codex manages token refresh. Failures never silently change authentication, model or billing.

**Host permissions:** Permit the actual installed command used by the task, with its concrete paths, through the host's normal permission flow:

```bash
python3 "/absolute/installation/scripts/quest_codex_runner.py" role \
  --cwd "/absolute/target workspace" --quest-dir "/absolute/quest artifacts/id" \
  --phase build --agent builder --iter 1 --prompt-file "/absolute/prompt.txt" \
  --output-dir "/absolute/run receipts" --sandbox workspace-write --timeout 1800
```

The builder command is used only after explicit Build approval. `/gpt` uses `task` mode; see the [GPT skill](../../.skills/gpt/SKILL.md) for its exact options. Installation, target cwd and artifact directories may be separate and contain spaces. Intentional non-Git execution requires `--allow-non-git`. No broad Bash/MCP wildcard permission or automatic full-access escalation is installed.

**Legacy configuration:** The installer stops registering `codex mcp-server`. It reports recognized old registrations rather than deleting global configuration. Inspect the named registration and follow its scoped removal guidance only for the confirmed obsolete entry; preserve unrelated tools and custom servers. Child invocations disable recognized Codex self-delegation commands per run, without rewriting user files. Custom OpenCode configuration may need a targeted merge removing only the obsolete shipped server. Do not remove all MCP tools or ignore inherited configuration to make a run pass.

Before the per-quest chooser, preflight checks the second runtime regardless of current role defaults. A failed probe pauses for remediation or an explicit single-model choice; it never silently changes the role map.

### Optional: Antigravity CLI (for Gemini-backed roles)

Quest can assign any role to a Gemini model running on Google's Antigravity CLI (`agy`).
This gives you a third model family alongside Claude and GPT, which matters most for the
reviewer slots — independent families disagree in useful ways.

**Requires:**
- [Antigravity CLI](https://antigravity.google/docs/cli/install) on your PATH:
  ```bash
  curl -fsSL https://antigravity.google/cli/install.sh | bash
  ```
- An authenticated session. `agy` authenticates through your OS keyring on first run, so run
  it once interactively before using it from Quest. Verify with `agy models`, which lists the
  slugs you can assign.

There is **no MCP server and no registration step** — Quest invokes `agy --print` as a
subprocess, the same shape as the Claude bridge.

Assign Gemini models by putting a slug from `agy models` in `models.<role>`:

```json
{
  "models": {
    "code-reviewer-b": "gemini-3.6-flash-high",
    "plan-reviewer-b": "gemini-3.1-pro-high"
  }
}
```

Slugs pass through to the CLI verbatim and are never checked against a hardcoded list, so a
newly released model works as soon as `agy models` lists it. The bare `gemini` sentinel means
"use the agy default model" (Quest omits `--model`), mirroring the `claude` sentinel. An
unrecognised slug is reported as `model_rejected` rather than silently downgraded.

Verify the runtime before your first Gemini-backed quest:

```bash
./scripts/quest_preflight.sh --probe antigravity
```

This runs a real probe — `agy` must actually write an artifact and a handoff, not merely
answer — so a green result means a role can do real work. Successful probes are cached with a
TTL, so repeat runs are near-instant; a cached success is only reused for the same model.

**Two behaviours worth knowing before you debug:**

- `agy` reads workspace context on its own, so a Gemini role starts with more context than the
  orchestrator handed it. This is a weaker isolation story than the Claude path.
- Writes outside the runner's `--add-dir` scope are **not refused** — `agy` redirects them to
  `~/.gemini/antigravity-cli/scratch/` and still reports success. If a Gemini role reports a
  missing handoff, suspect scoping before you suspect the model.

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
| `models.<role>` | Set a model ID for each canonical role: `planner`, `plan-reviewer-a`, `plan-reviewer-b`, `arbiter`, `builder`, `code-reviewer-a`, `code-reviewer-b`, `review-arbiter`, and `fixer` |
| `claude_role_transport` | Codex-led Claude transport policy: `auto` (default), `background-agent`, or `bridge` |
| `quest_id_format` | `slug-first` (default) or `date-first`; affects only new Quest folder names |
| `codex_auth_mode` | Codex runner authentication: `cached` (default, prefer ChatGPT login) or explicitly selected `api-key`; saved per quest, never inferred from key presence |
| `review_mode` | `auto` (default), `fast`, or `full` for Codex reviews |
| `fast_review_thresholds` | File/LOC thresholds used when `review_mode: auto` |

Quest IDs use `<slug>_YYYY-MM-DD__HHMM` by default. Set `"quest_id_format": "date-first"` to create new quests as `YYYY-MM-DD_HHMM__<slug>` for chronological `.quest/` sorting. Existing folders are not renamed, and resume accepts both formats in mixed repositories.

The `.ai/allowlist.json` `models.<role>` values are repository defaults used at
Quest startup. The chooser expands them to all nine roles, validates the active
model families against preflight, and allows per-quest overrides. It then saves
the selected role map and Claude transport metadata in
`.quest/<id>/orchestration.json`. Every role dispatch reads that saved per-quest
file; it does not reread the allowlist as live configuration.


### 2. Gitignore

Add to `.gitignore`:

```
.quest/
```

The `.quest/` folder contains ephemeral run state and should not be committed.

## Codex Runtime Readiness

Use the [Codex CLI prerequisites](#optional-codex-cli-for-codex-backed-roles) above. No registration step is required.

Quest runs preflight before creating a new quest. Use the command matching the
current orchestrator:

```bash
./scripts/quest_preflight.sh --orchestrator claude
./scripts/quest_preflight.sh --orchestrator codex
```

Claude-led preflight checks the installed Codex runner, exec capabilities and selected auth mode; Codex-led
preflight always probes the configured Claude transport. This second-runtime
probe happens before the role-model chooser and is independent of the current
`models` defaults. The chooser then validates its active role selections against
the cached preflight result. A failed probe pauses startup for remediation, an
explicit supported transport choice, a deliberate single-model remap, or
cancellation.

To deliberately use Claude for every role, set all nine role models in
`.ai/allowlist.json` `models`:

```json
{
  "models": {
    "planner": "claude",
    "plan-reviewer-a": "claude",
    "plan-reviewer-b": "claude",
    "arbiter": "claude",
    "builder": "claude",
    "code-reviewer-a": "claude",
    "code-reviewer-b": "claude",
    "review-arbiter": "claude",
    "fixer": "claude"
  }
}
```

## Codex-Led Claude Transports

When Codex orchestrates a quest, Claude-designated roles run through `scripts/quest_claude_runner.py`, which owns one of two transports underneath. Selection is config + probe driven (`.ai/allowlist.json` → `claude_role_transport`, default `auto`):

| Transport | Mechanism | Billing | When |
|---|---|---|---|
| **background-agent** (preferred) | `scripts/quest_claude_bg_run.py` → `claude --bg` daemon-hosted session | **subscription pool** | default on dev machines once the one-time setup below is done |
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

`models.<role> = "claude"` is a sentinel for the Claude CLI/account default model. Quest passes the sentinel into its own runner, but the runner omits the CLI `--model` flag. If Claude rejects a concrete model, Quest reports `model_rejected` instead of downgrading or guessing. Because the sentinel does not identify the account-default model, rejection results omit `rejected_model` for it.

To pin a **specific Claude model** for a role, put a supported full `claude-`-prefixed ID in `models.<role>` in `.ai/allowlist.json`, or use the per-quest chooser. The ID passes verbatim to the CLI's `--model`. **Do not use bare CLI aliases like `opus` or `sonnet` in `models.<role>`**: Quest classifies runtime by the `claude`/`claude-*` shape, so bare aliases route to Codex. Bare aliases are only appropriate for direct CLI runner/probe calls. Set `QUEST_CLAUDE_PROBE_MODEL` to your chosen model ID to preflight it. See the root README's model configuration section for generated defaults and Codex effort.

The same shape rule applies to Gemini: a `gemini`/`gemini-*` ID routes the role to the Antigravity runtime, and anything else falls through to Codex. Override the runtime's probe model with `QUEST_AGY_PROBE_MODEL=gemini-3.1-pro-high`, or point Quest at a different binary with `QUEST_AGY_BINARY`.

**Prerequisites (both transports):** Claude CLI installed and authenticated (`claude auth status` should show a valid session).

If the preflight says the Claude transport is unavailable, first run `claude auth login` in a normal shell and re-check `claude auth status`. If browser login already succeeded but preflight still reports Claude as unavailable, rerun `./scripts/quest_preflight.sh --orchestrator codex` outside any restricted sandbox before concluding the transport is broken; some sandboxed runners cannot see the host Claude CLI auth state.

Successful Codex-led probes are retained for 12 hours: background-agent at `.quest/cache/claude_bg_codex.json`, bridge at `.quest/cache/claude_bridge_codex.json`. Each cache records the normalized `probe_model` (`claude` for the account default, or the exact trimmed concrete model) and is reusable only for that same identity. A cache written before `probe_model` was added is ignored once and refreshed by the next successful live probe; it cannot validate either a concrete model or the sentinel. This avoids repeating browser-login remediation without letting one model's success validate another, but it does **not** make sandbox-local Claude auth trustworthy. Claude-designated roles still need to run in the same host-visible context that produced the successful probe. Override the retention window with `QUEST_PREFLIGHT_CACHE_TTL_SECONDS=<seconds>` or the cache paths with `QUEST_PREFLIGHT_CACHE_FILE=<path>` (bridge) / `QUEST_PREFLIGHT_BG_CACHE_FILE=<path>` (background-agent).

### What the bridge does

Quest uses a purpose-built CLI bridge (`scripts/quest_claude_bridge.py`) instead of MCP for cross-model calls. This gives Quest per-invocation control that a static MCP connection can't provide:

- **Filesystem scoping**, each role gets access to only the directories it needs via `--add-dir`
- **Permission modes**, builder runs with `bypassPermissions`, read-only roles use `plan` mode
- **Tool restrictions**, reviewers can't write files, planners can't run arbitrary bash
- **Handoff polling**, the runner watches for `handoff.json` on disk instead of retaining Claude's full response in the Codex orchestrator's context
- **Context health logging**, every cross-model call is logged to `.quest/<id>/logs/context_health.log` with timestamp, phase, agent, runtime, and handoff state
- **True isolation**, each call is a fresh `claude --print` invocation with no session state between roles

The bridge script itself is Quest-agnostic, it's a generic utility for calling Claude CLI with structured options. The Quest-specific behavior (handoff polling, logging, text fallback) lives in `quest_claude_runner.py`.

When the Claude CLI rejects the selected model, direct bridge execution exits
`9` and the Quest runtime reports `result_kind=model_rejected`. For a concrete
request, the runtime derives `rejected_model` from that requested model; it does
not parse the bridge's agent-response stdout. The `claude` sentinel therefore
has no concrete rejected-model field. A completed handoff with all declared
artifacts still wins over a late bridge exit `9`; otherwise model rejection
wins over ordinary missing/unparsable handoff, missing-artifact, invocation,
and generic-error classifications. The bridge process itself exits `1` for a
timeout and for a missing CLI; `124` and `127` appear only as the `exit_code`
field of the out-of-band `--json-wrap` payload.

Quest invokes the bridge in text mode and does not pass `--json-wrap`.
`--json-wrap` remains an out-of-band interface for direct/external bridge
callers; its envelope is not part of the Quest runtime protocol.

### What Quest handles automatically

- Probes the configured transport once per session and retains recent successful host probes (bg under `auto`; bridge only when explicitly configured/selected)
- Sweeps orphaned `quest-<id>-*` background sessions and stale `quest-bg-probe-*` probe sessions at quest start/resume (`python3 scripts/quest_claude_bg_run.py --sweep quest-<id>-` and `python3 scripts/quest_claude_bg_run.py --sweep quest-bg-probe-`)
- Routes every role whose saved model is Claude-family through `scripts/quest_claude_runner.py --model <models.<role>> --transport <resolved>` in the same host-visible context used for the probe/cache refresh
- Keeps background-agent `needs_human` sessions parked for same-session resume, then resumes with `--resume <session_id> --answer-file <answer_file>` and updates the chained session id after Claude forks a continuation
- Records the transport per role in `context_health.log` (`transport=background-agent|bridge`) and reports it in the quest end summary and celebration
- Claude-family roles in Claude-led quests keep native `Task(...)` execution

If the probe fails, Quest pauses startup for the explicit remediation or
single-model choices described above; it does not silently select the bridge or
rewrite role models.

### Optional: manual verification

If you want to test a transport before your first Codex-led quest, you can run the probe yourself:

```bash
command -v claude
claude auth status
claude agents --json
ls -la scripts/quest_claude_bg_run.py
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

For every role, Quest reads `models.<role>` from the active quest's
`orchestration.json`, derives the Claude or Codex runtime family, and then uses
the entrypoint for the current orchestrator:

- Claude-led + Claude-family: native isolated task
- Claude-led + Codex-backed: `scripts/quest_codex_runner.py role`, using saved model, effort and auth
- Codex-led + Codex-backed: local Codex subagent
- Codex-led + Claude-family: `scripts/quest_claude_runner.py` with the resolved
  `background-agent` or explicitly selected `bridge` transport

Each role receives an assembled prompt with its instructions and returns an
artifact-backed handoff without sharing conversation history with other roles.

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

1. Run the preflight command for the active orchestrator and address every
   reported availability warning.
2. Inspect `.quest/<id>/orchestration.json` and verify the affected
   `models.<role>` entries select the intended Codex-backed model.
3. For Claude-led quests, rerun `scripts/quest_preflight.sh --orchestrator claude --codex-auth <saved-mode>` and follow its selected-auth/CLI warning. Legacy quests without `codex_auth_mode` use `cached`.
4. To change repository defaults for future quests, update the corresponding
   `.ai/allowlist.json` `models.<role>` values. Existing quests continue using
   their saved orchestration file.

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
