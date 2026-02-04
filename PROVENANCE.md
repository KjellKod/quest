# Quest Blueprint Provenance

This document records the origin and creation of this repository for future AI agents and contributors.

## Origin

This repository was created on **2026-02-04** by extracting and generalizing the Quest multi-agent orchestration system from:

```
Source Repository: /Users/kjell/ws/extra/candid_talent_edge-TownHall
Branch: TownHall
```

The source repository is a production application with project-specific configurations. This blueprint repository contains a **generalized, portable** version suitable for copying into any project.

## What Was Extracted

### Files Copied Directly (then generalized)
- `.ai/roles/*.md` - All 7 agent role definitions
- `.ai/schemas/handoff.schema.json` - Inter-agent communication contract
- `.ai/templates/*.md` - Document templates (brief, plan, review, pr_description)
- `.skills/quest/SKILL.md` - Quest orchestration procedure
- `.skills/plan-maker/SKILL.md` - Planning methodology
- `.skills/plan-reviewer/SKILL.md` - Plan review checklist
- `.skills/code-reviewer/SKILL.md` - Code review checklist
- `.skills/implementer/SKILL.md` - Implementation methodology
- `.skills/BOOTSTRAP.md` - Skill discovery guide
- `.skills/README.md` - Skills overview
- `.claude/agents/*.md` - Agent wrappers
- `.claude/hooks/enforce-allowlist.sh` - Permission enforcement hook
- `.claude/skills/quest/SKILL.md` - Thin wrapper
- `docs/guides/quest_setup.md` - Setup guide
- `docs/guides/quest_presentation.md` - Presentation with diagrams

### Files Created Fresh (generalized versions)
- `.ai/allowlist.json` - Generic permissions using `src/**`, `lib/**`, `tests/**`
- `.ai/quest.md` - Quick reference (no project-specific references)
- `.ai/context_digest.md` - Generic Codex context template
- `.claude/AGENTS.md` - Generic Claude Code entry point
- `.claude/settings.json` - Minimal hooks config (audit logging only)
- `.cursor/rules` - Generic Cursor entry point
- `.codex/AGENTS.md` - Generic Codex entry point
- `AGENTS.md` - Generic coding rules template
- `DOCUMENTATION_STRUCTURE.md` - Generic documentation navigation
- `README.md` - Getting started guide for the blueprint
- `.gitignore` - Includes `.quest/`
- `.skills/SKILLS.md` - Skills index (without project-specific skills like feature-dev)

### Files NOT Copied (project-specific)
- `.skills/feature-dev/` - Project-specific feature development workflow
- `.skills/git-worktrees/` - Optional, not core to quest
- `.skills/small-change/` - Optional, not core to quest
- `docs/architecture/ARCHITECTURE.md` - Project-specific architecture
- `DOCUMENTATION_STRUCTURE.md` (original) - Project-specific doc structure
- Root `AGENTS.md` (original) - Project-specific coding rules

## Generalization Changes Made

1. **allowlist.json**: Changed project-specific paths (`api/**`, `engine/**`, `parsing/**`, `policy/**`, `ui/src/**`) to generic paths (`src/**`, `lib/**`)

2. **builder_agent.md** and **fixer_agent.md**: Updated "Allowed Actions" section to use generic paths and note that they should be customized in allowlist.json

3. **context_digest.md**: Removed project-specific architecture boundaries, made it a template

4. **AGENTS.md** (root): Created generic coding rules template with placeholder architecture sections

5. **SKILLS.md**: Removed project-specific skills (feature-dev, git-worktrees, small-change) that aren't core to quest

## Validation Checklist

To verify the blueprint is complete, check these files exist and are valid:

```bash
# Core quest files
ls -la .ai/allowlist.json
ls -la .ai/quest.md
ls -la .ai/roles/planner_agent.md
ls -la .ai/roles/builder_agent.md
ls -la .ai/roles/arbiter_agent.md
ls -la .ai/schemas/handoff.schema.json

# Skills
ls -la .skills/quest/SKILL.md
ls -la .skills/BOOTSTRAP.md

# Claude Code integration
ls -la .claude/agents/planner.md
ls -la .claude/hooks/enforce-allowlist.sh
ls -la .claude/skills/quest/SKILL.md

# Validate JSON
jq '.' .ai/allowlist.json > /dev/null && echo "allowlist.json OK"
jq '.' .ai/schemas/handoff.schema.json > /dev/null && echo "handoff.schema.json OK"

# Check hook is executable
test -x .claude/hooks/enforce-allowlist.sh && echo "Hook is executable"
```

## If Something Is Missing

If you discover a missing file or incomplete configuration, the source repository is at:

```
/Users/kjell/ws/extra/candid_talent_edge-TownHall
```

Key source locations:
- `.ai/` - All AI-agnostic quest configuration
- `.skills/` - All skill definitions
- `.claude/` - Claude Code integration
- `docs/guides/quest_*.md` - Quest documentation

## Future Work (Phase 2)

Ideas for making this easier to distribute:

1. **Packaging Script**: Create `scripts/pack-quest.sh` and `scripts/unpack-quest.sh`
2. **MCP Package**: Publish as an npm package with `claude mcp add quest-blueprint`
3. **GitHub Template**: Make this repo a GitHub template repository
4. **Installer Script**: Single curl command that clones and sets up

---

*Created: 2026-02-04*
*Source: candid_talent_edge-TownHall @ TownHall branch*
