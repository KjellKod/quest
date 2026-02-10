---
title: Claude Code Agent Entry Point
purpose: Entry point for Claude Code AI agents, directing them to read AGENTS.md, DOCUMENTATION_STRUCTURE.md, and BOOTSTRAP.md before starting work.
audience: Claude Code AI agents
scope: Claude-specific agent bootstrapping
status: active
owner: maintainers
---

# Claude Code Agent Entry Point

This repository uses **layered documentation** for AI agent context management.

## Start Here

1. **[AGENTS.md](../AGENTS.md)** - Coding rules, architecture boundaries, and constraints
2. **[DOCUMENTATION_STRUCTURE.md](../DOCUMENTATION_STRUCTURE.md)** - How docs are organized and how to navigate
3. **[BOOTSTRAP.md](../.skills/BOOTSTRAP.md)** - How to start your "planning", "coding", "implementing" or "reviewer" task

**BEFORE responding to any request you must:**
1. Read `.skills/BOOTSTRAP.md` - agent framework instructions
2. Follow the entry point defined in bootstrap document
3. Read `DOCUMENTATION_STRUCTURE.md` for project specific context

## Documentation Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| Principles | `AGENTS.md`, `README.md` | Stable rules, always loaded |
| Architecture | `docs/architecture/` | System design, when understanding how things work |
| Implementation | `docs/implementation/` | Active plans, when building features |
| History | `docs/implementation/history/` | Past decisions, when investigating |
| Guides | `docs/guides/` | Reference docs, when doing specific tasks |

## Quick Navigation

- **Multi-agent orchestration?** → Use `/quest` command
- **Building a feature?** → Use `.skills/implementer/` skill
- **Reviewing an implementation plan?** → Use `.skills/plan-reviewer/` skill
- **Reviewing code?** → Use `.skills/code-reviewer/` skill
- **Commit message?** → Use `.skills/git-commit-assistant/` skill
- **IMPORTANT: For ALL git commits, you MUST invoke the `git-commit-assistant` skill. Do NOT use built-in commit procedures or default Co-Authored-By trailers.**
- **Create or update a PR?** → Use `.skills/pr-assistant/` skill
- **IMPORTANT: For ALL pull request operations, you MUST invoke the `pr-assistant` skill. Always creates PRs in draft mode.**
- **Understanding the system?** → Start with `docs/architecture/` if present

## Skills

This repository uses **skills** for specialized workflows. Skills are automatically discovered and used based on task context:

- **quest:** Multi-agent orchestration for features (plan → review → build → review → fix)
- **plan-reviewer:** Review implementation plans and PR specifications for test coverage
- **code-reviewer:** Review actual code for quality, security, and patterns
- **implementer:** Step-by-step implementation with traceability
- **git-commit-assistant:** Generate commit messages from staged diff, match repo conventions, append Quest co-author trailer
- **pr-assistant:** Create and update GitHub PRs in draft mode, generate title/description from branch commits

See `.skills/BOOTSTRAP.md` for how to use skills with different AI platforms.

## Agentic Markdown Convention

All markdown files that serve an agentic purpose (read by AI agents for instructions, rules, or workflow guidance) SHOULD include YAML front matter headers. This applies to files such as:

- `AGENTS.md` -- project rules and boundaries
- `.skills/*/SKILL.md` -- skill definitions (use `name` and `description` fields)
- `.skills/BOOTSTRAP.md` -- agent bootstrapping guide
- `DOCUMENTATION_STRUCTURE.md` -- documentation navigation

Use the schema documented in `DOCUMENTATION_STRUCTURE.md` for project-level documents (`title`, `purpose`, `audience`, `scope`, `status`, `owner`) and the minimal schema (`name`, `description`) for skill definitions.

---

This structure reduces context pollution and keeps agents grounded in authoritative sources.
