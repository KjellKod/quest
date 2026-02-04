# Quest Setup Guide

How to add the `/quest` multi-agent orchestration system to your repository.

## Prerequisites

- Claude Code CLI installed and authenticated
- (Optional) Codex CLI if using GPT 5.2 for reviews/arbiter
- jq for JSON processing

## What to Copy

Copy these folders to your repository root:

```
.ai/                              # Source of truth (AI-agnostic)
  allowlist.json                  # Permission configuration
  quest.md                        # Quick reference
  roles/                          # Agent role definitions
    planner_agent.md
    plan_review_agent.md
    arbiter_agent.md
    builder_agent.md
    code_review_agent.md
    fixer_agent.md
  schemas/
    handoff.schema.json           # Inter-agent communication contract
  templates/
    quest_brief.md
    plan.md
    review.md
    pr_description.md
  context_digest.md               # Short Codex context (review speedup)

.skills/quest/                    # Full skill procedure (AI-agnostic)
  SKILL.md

.claude/                          # Claude Code integration layer
  skills/quest/SKILL.md           # Thin wrapper → .skills/quest/
  agents/                         # Thin wrappers → .ai/roles/
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
| `arbiter.tool` | Set to `"claude"` to use Claude Opus instead of Codex/GPT 5.2 |
| `review_mode` | `auto` (default), `fast`, or `full` for Codex reviews |
| `fast_review_thresholds` | File/LOC thresholds used when `review_mode: auto` |
| `codex_context_digest_path` | Short context file used by Codex (default: `.ai/context_digest.md`) |

### 2. Gitignore

Add to `.gitignore`:

```
.quest/
```

The `.quest/` folder contains ephemeral run state and should not be committed.

## One-Time MCP Setup (if using Codex/GPT 5.2)

If you want to use GPT 5.2 via Codex for reviews and arbiter:

```bash
# Add Codex MCP server
claude mcp add codex -- npx -y @anthropic/codex-mcp-server
```

This enables the `mcp__codex__codex` tool for spawning Codex agents.

If you don't have Codex or prefer Claude for all roles, set in `allowlist.json`:

```json
{
  "arbiter": {
    "tool": "claude"
  }
}
```

The plan and code reviewers will also fall back to Claude if Codex is unavailable.

## Verification

After setup, verify everything is in place:

1. **Check files exist:**
   ```bash
   ls -la .ai/allowlist.json
   ls -la .claude/skills/quest/SKILL.md
   ls -la .claude/agents/
   ls -la .claude/hooks/enforce-allowlist.sh
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
   ```

## Usage

Once set up, use the `/quest` command in Claude Code:

```
/quest "Add a loading skeleton to the candidate list"
```

See `.ai/quest.md` for full usage documentation.

## How It Works

### Clean Context Architecture

Each agent runs in **complete isolation** — no shared conversation history:

**Claude agents** (planner, builder, fixer, plan-reviewer):
- Spawned via Task tool with `subagent_type: general-purpose`
- Receive assembled prompt with role instructions from `.ai/roles/*.md`
- Start fresh, return handoff when done

**Codex agents** (code-reviewer, arbiter when configured):
- Called via `mcp__codex__codex` MCP tool
- Completely separate model (GPT 5.2)
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

The agent role definitions in `.ai/roles/*.md` are the source of truth. The `.claude/agents/*.md` files are thin wrappers that serve as documentation and reference.

To customize behavior, edit the files in `.ai/roles/`. The wrapper files rarely need changes.

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

**Note:** Source of truth is always in AI-agnostic locations (`.ai/`, `.skills/`). The `.claude/` folder contains thin wrappers that delegate to the portable definitions.
