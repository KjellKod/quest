# Quest: Multi-Agent Orchestration Blueprint

**Part of the [Candid Talent Edge](https://candidtalentedge.com) initiative by KjellKod**

> *New here?* Watch the [Quest Demo](docs/media/quest-demo.mov), listen to the [Fellowship of the Code](docs/media/critique-fellowship-of-the-code.m4a) (AI-generated audio critique), or read Claude's [honest analysis](docs/guides/quest_analysis.md) of this tool.

A portable framework for coordinated AI agents with human oversight. Copy this to any repository to enable structured, auditable AI workflows.

![Adventurers in our quest](docs/media/quest_v0.12.png)

## What is Quest?

Quest is a multi-agent workflow where specialized AI agents (planner, reviewers, builder) work in **isolated contexts** with **human approval gates**. Two different models (Claude + GPT) review independently, an arbiter filters nitpicks, and you approve before anything gets built.

**One sentence:** *"Structured AI teamwork with checks and balances."*

```
┌─────────────── PLAN PHASE ───────────────┐    ┌─────────── BUILD PHASE ───────────┐
│                                          │    │                                   │
│  You → Planner → Reviewers → Arbiter  ───┼────→  Builder → Reviewers ──┬──→ Done  │
│            ▲      (Claude)      │        │    │              (Claude)  │          │
│            │      (Codex)       │        │    │              (Codex)   │          │
│            └───── iterate ──────┘        │    │                 │      │          │
│                                          │    │                 ▼      │          │
│                                          │    │              Fixer ────┘          │
│                                          │    │           (if issues)             │
└──────────────────────────────────────────┘    └───────────────────────────────────┘
                                   ▲
                                GATE: human approval
```

## Prerequisites

### Required: Claude Code CLI

Install Claude Code (Anthropic's official CLI):

```bash
# Install via npm
npm install -g @anthropic-ai/claude-code

# Or download from:
# https://docs.anthropic.com/en/docs/claude-code
```

### Optional: Codex MCP (for dual-model reviews)

Quest uses GPT 5.2 via Codex as a second reviewer. If you want dual-model reviews:

```bash
# Add Codex MCP server to Claude Code
claude mcp add codex -- npx -y @anthropic/codex-mcp-server

# Requires OpenAI API key configured
# https://platform.openai.com/docs/quickstart
```

If you skip this, Quest will use Claude for all roles (still works, just single-model).

## Quick Start

### Option A: Use the Installer (Recommended)

```bash
# Download the installer
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh -o quest_installer.sh
chmod +x quest_installer.sh

# Preview what will be installed
./quest_installer.sh --check

# Install Quest
./quest_installer.sh
```

The installer:
- Handles fresh installs AND updates
- Tracks file checksums to detect your modifications
- Never overwrites your customizations (uses `.quest_updated` suffix)
- Supports `--force` for CI/automation

### Option B: Manual Copy

Copy these folders to your repository root:
- `.ai/` - Source of truth (permissions, roles, templates)
- `.skills/` - Skill procedures (plan-maker, code-reviewer, etc.)
- `.claude/` - Claude Code integration (agents, hooks)
- `.cursor/` - Cursor integration
- `.codex/` - Codex integration
- `docs/guides/quest_setup.md` - Setup documentation
- `AGENTS.md` - Coding rules (customize for your project)
- `DOCUMENTATION_STRUCTURE.md` - Navigation guide

### Customize allowlist

Edit `.ai/allowlist.json` to match your project:

```json
{
  "role_permissions": {
    "builder_agent": {
      "file_write": [".quest/**", "src/**", "tests/**"],
      "bash": ["npm test", "pytest"]
    }
  }
}
```

### Add to .gitignore

```
.quest/
```

### Use it

```bash
claude
/quest "Add a loading skeleton to the user list"
```

Quest scales from simple to complex — just describe what you want:

```bash
# Quick feature
/quest "Add a loading spinner to the save button"

# Multi-file change
/quest "Implement user preferences with localStorage"

# Large refactor
/quest "Add weekly update checking with opt-out config"

# Resume where you left off
/quest feature-x_2026-02-04__1430

# Resume with new direction
/quest feature-x_2026-02-04__1430 "only use claude, skip codex"
```

Abort anytime, resume later. State persists in `.quest/<id>/state.json`.

## Key Features

- **Clean context** — each agent starts fresh (no drift)
- **Dual-model review** — Claude + Codex review plans AND code (different blind spots)
- **Arbiter** — filters nitpicks, decides "good enough", prevents spin
- **Human gates** — you approve before building
- **Artifacts saved** — full audit trail in `.quest/`
- **Scales up** — step-by-step approach shines on large tasks (context stays manageable)

## How the Orchestrator Works

The Quest Orchestrator (main Claude running `/quest`) coordinates specialized agents. During review phases, it dispatches **both reviewers in parallel**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      QUEST ORCHESTRATOR                             │
│                 (Main Claude executing /quest skill)                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Review Phase (Plan or Code)
                                  │
                    ┌─────────────┴─────────────┐
                    │   SINGLE MESSAGE with     │
                    │   TWO TOOL CALLS          │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   │                   ▼
┌─────────────────────────┐       │       ┌─────────────────────────┐
│   Tool Call 1:          │       │       │   Tool Call 2:          │
│   Task tool             │  PARALLEL     │   mcp__codex__codex     │
│   (Claude subagent)     │   EXECUTION   │   (Codex MCP server)    │
│                         │       │       │                         │
│  → plan-reviewer or     │       │       │  → GPT-5.2 reviews      │
│    code-reviewer agent  │       │       │    same artifacts       │
└───────────┬─────────────┘       │       └───────────┬─────────────┘
            │                     │                   │
            ▼                     │                   ▼
   review_claude.md               │          review_codex.md
                                  │
              └───────────────────┼───────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │   Runtime collects BOTH   │
                    │   results, then continues │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                          Arbiter synthesizes
```

**Why parallel?** Both reviewers are independent (write separate files, read same inputs). Claude's API executes multiple tool calls from the same message concurrently.

## File Structure

```
your-repo/
├── .ai/                          # Source of truth (AI-agnostic)
│   ├── allowlist.json            # Permissions (customize this!)
│   ├── quest.md                  # Quick reference
│   ├── context_digest.md         # Short context for Codex reviews
│   ├── roles/                    # Agent behavior definitions
│   ├── schemas/                  # Handoff contract
│   └── templates/                # Document templates
├── .skills/                      # Skill procedures (AI-agnostic)
│   ├── quest/SKILL.md            # Quest orchestration procedure
│   ├── plan-maker/SKILL.md       # Planning methodology
│   ├── plan-reviewer/SKILL.md    # Plan review checklist
│   ├── code-reviewer/SKILL.md    # Code review checklist
│   └── implementer/SKILL.md      # Implementation methodology
├── .claude/                      # Claude Code integration
│   ├── agents/                   # Thin wrappers → .ai/roles/
│   ├── hooks/                    # Permission enforcement
│   └── skills/quest/SKILL.md     # Thin wrapper → .skills/quest/
├── .cursor/                      # Cursor integration
├── .codex/                       # Codex integration
└── .quest/                       # Ephemeral run state (gitignored)
```

## Documentation

- **[Quest Setup Guide](docs/guides/quest_setup.md)** - Detailed setup instructions
- **[Quest Presentation](docs/guides/quest_presentation.md)** - How it works (with diagrams)
- **[AGENTS.md](AGENTS.md)** - Coding rules to customize
- **[.ai/quest.md](.ai/quest.md)** - Quick reference

## The Quest Party: Agent Roles

### Planner
Creates the implementation plan from your quest brief. Explores the codebase, identifies files to change, and writes a detailed plan with acceptance criteria.

### Reviewers (Claude + Codex)
Two independent reviewers examine plans and code:
- **Claude reviewer**: Uses Claude's understanding of the codebase
- **Codex reviewer**: Uses GPT 5.2 for a different perspective

Having two different model families catches different blind spots.

### Arbiter
Synthesizes both reviews, filters nitpicks, and decides: **approve** (proceed) or **iterate** (revise). Prevents endless review cycles by focusing on what matters.

### Builder
Implements the approved plan. Writes code, runs tests, and produces a PR description. Works only after you approve the plan.

### Fixer
**The cleanup specialist.** When code reviewers find issues after the builder finishes:

1. Fixer receives the review feedback
2. Makes targeted fixes to address the issues
3. Re-runs tests to verify
4. Code is re-reviewed

The fix loop continues until reviewers approve (or max iterations reached). This keeps the builder's original work intact while addressing review feedback.

**Key difference from Builder:**
- **Builder**: Implements the full plan from scratch
- **Fixer**: Makes surgical fixes to existing implementation based on review feedback

## License

Public Domain (Unlicense). No warranty. See [LICENSE](LICENSE).
