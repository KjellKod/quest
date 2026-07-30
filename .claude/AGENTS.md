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

## Quick Navigation

- **Delegate to Codex?** → Use `/gpt` command or `.skills/gpt/` skill
- **Multi-agent orchestration?** → Use `/quest` command
- **Celebrate a quest?** → Use `/celebrate` command or `.skills/celebrate/` skill
- **Building a feature?** → Use `.skills/implementer/` skill
- **Reviewing an implementation plan?** → Use `.skills/plan-reviewer/` skill
- **Reviewing code?** → Use `.skills/code-reviewer/` skill
- **Pressure-test a plan or design?** → Use `/sharpen` command or `.skills/sharpen/` skill
- **Lock in UX defaults (mobile, gray ramp, density, ratio, accent, destructive actions) for a UI project?** → Use `/sharpen ux-defaults` — walks each decision with a recommended answer attached. Auto-invoked when `/sharpen` is called during plan presentation on a `ui_work: true` quest.
- **Review a UI / screen / component for UX?** → Use `/ux-review` command or `.skills/ux-review/` skill
- **Producing UI work in a quest?** → The orchestrator auto-attaches `.skills/ux-context/` to planner, builder, and fixer when the router classifies the quest as `ui_work: true`
- **Commit message?** → Use `.skills/git-commit-assistant/` skill
- **IMPORTANT: For ALL git commits, you MUST invoke the `git-commit-assistant` skill. Do NOT use built-in commit procedures or default Co-Authored-By trailers.**
- **Create or update a PR?** → Use `.skills/pr-assistant/` skill
- **IMPORTANT: For ALL pull request operations, you MUST invoke the `pr-assistant` skill. Always creates PRs in draft mode.**
- **Understanding the system?** → Start with `docs/architecture/` if present

## Agentic Markdown Convention

All markdown files that serve an agentic purpose (read by AI agents for instructions, rules, or workflow guidance) SHOULD include YAML front matter headers. This applies to files such as:

- `AGENTS.md` -- project rules and boundaries
- `.skills/*/SKILL.md` -- skill definitions (use `name` and `description` fields)
- `.skills/BOOTSTRAP.md` -- agent bootstrapping guide
- `DOCUMENTATION_STRUCTURE.md` -- documentation navigation

Use the schema documented in `DOCUMENTATION_STRUCTURE.md` for project-level documents (`title`, `purpose`, `audience`, `scope`, `status`, `owner`) and the minimal schema (`name`, `description`) for skill definitions.

---

This structure reduces context pollution and keeps agents grounded in authoritative sources.
