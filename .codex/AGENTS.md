# Codex Agent Entry Point

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

- **Multi-agent orchestration?** → Use `$quest` (thin wrapper in `.agents/skills/quest/SKILL.md`, which delegates to `.skills/quest/SKILL.md`)
- **Building a feature?** → Use `.skills/implementer/` skill
- **Reviewing an implementation plan?** → Use `.skills/plan-reviewer/` skill
- **Reviewing code?** → Use `.skills/code-reviewer/` skill
- **Commit message?** → Use `.skills/git-commit-assistant/` skill
- **Create or update a PR?** → Use `.skills/pr-assistant/` skill
- **Understanding the system?** → Start with `docs/architecture/` if present

## Quest Discipline (Codex)

When the user invokes `$quest`, follow Quest process exactly:

- Treat `$quest` as workflow orchestration, not direct implementation.
- Do not edit project/source files before the Build Phase is reached through normal Quest gates.
- Plan + dual review + arbiter + presentation/human approval must happen before implementation.
- If the user requests "plan and build now" in one prompt, still run planning and gates first.
- During pre-build phases, write only quest artifacts under `.quest/` (and planning docs under `docs/implementation/` when needed).

## Skills

This repository uses **skills** for specialized workflows. Skills are automatically discovered and used based on task context:

- **quest:** Multi-agent orchestration for features (plan → review → build → review → fix)
- **plan-reviewer:** Review implementation plans and PR specifications for test coverage
- **code-reviewer:** Review actual code for quality, security, and patterns
- **implementer:** Step-by-step implementation with traceability
- **git-commit-assistant:** Generate commit messages from staged diff, match repo conventions, append Quest co-author trailer
- **pr-assistant:** Create and update GitHub PRs in draft mode, generate title/description from branch commits

See `.skills/BOOTSTRAP.md` for how to use skills with different AI platforms.

---

This structure reduces context pollution and keeps agents grounded in authoritative sources.
