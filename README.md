# Quest: Multi-Agent Orchestration Blueprint

**Part of the [Candid Talent Edge](https://candidtalentedge.com) initiative by KjellKod**

> *New here?* Listen to the [Fellowship of the Code](docs/media/critique-fellowship-of-the-code.m4a) - an AI-generated audio overview of what Quest is all about.

A portable framework for coordinated AI agents with human oversight. Copy this to any repository to enable structured, auditable AI workflows.

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

## Quick Start

### 1. Copy to your repository

Copy these folders to your repository root:
- `.ai/` - Source of truth (permissions, roles, templates)
- `.skills/` - Skill procedures (plan-maker, code-reviewer, etc.)
- `.claude/` - Claude Code integration (agents, hooks)
- `.cursor/` - Cursor integration
- `.codex/` - Codex integration
- `docs/guides/quest_setup.md` - Setup documentation
- `AGENTS.md` - Coding rules (customize for your project)
- `DOCUMENTATION_STRUCTURE.md` - Navigation guide

### 2. Customize allowlist

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

### 3. Add to .gitignore

```
.quest/
```

### 4. Use it

```
/quest "Add a loading skeleton to the user list"
```

## Key Features

- **Clean context** — each agent starts fresh (no drift)
- **Dual-model review** — Claude + Codex review plans AND code (different blind spots)
- **Arbiter** — filters nitpicks, decides "good enough", prevents spin
- **Human gates** — you approve before building
- **Artifacts saved** — full audit trail in `.quest/`

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

## Optional: Codex MCP Setup

If you want to use GPT 5.2 via Codex for reviews and arbiter:

```bash
claude mcp add codex -- npx -y @anthropic/codex-mcp-server
```

If you don't have Codex, set in `.ai/allowlist.json`:
```json
{
  "arbiter": {
    "tool": "claude"
  }
}
```

## License

Public Domain (Unlicense) - Use however you like, no strings attached. See [LICENSE](LICENSE) for details.
