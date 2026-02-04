---
title: Skills Bootstrap Guide
purpose: Explain how skills are discovered, loaded, and applied by agents.
audience: AI agents and contributors configuring skill usage.
scope: Repo-wide skill system guidance.
status: active
owner: maintainers
last_updated: 2026-02-03
related:
  - .skills/SKILLS.md
  - DOCUMENTATION_STRUCTURE.md
---

# Skills Bootstrap Guide

This guide explains how to discover and use skills in this repository.

**Header-first reading:** Read YAML headers first and only load full documents if needed.

## What Are Skills?
Skills are specialized knowledge packages under `.skills/` with:
- `SKILL.md` (instructions and workflow)
- Optional resources (scripts, references, assets)

## Skill Discovery (Required Order)
1. Read `.skills/SKILLS.md` to see available skills.
2. Match task intent to skill description.
3. Load the skill’s `SKILL.md` only if needed.
4. Load resources only if required by the skill.

## Skill Loading Model
- **Metadata first:** YAML `name` + `description`.
- **Body next:** `SKILL.md` content.
- **Resources last:** only if the skill references them.

## When to Use a Skill
Use a skill when:
- The user names it explicitly, or
- The task clearly matches the skill description.

## Platform Notes
- **Claude Code / Cursor:** skills are auto-discovered.
- **OpenAI GPT:** load the relevant `SKILL.md` explicitly in the prompt or via tooling.

## Manual Loading (OpenAI Example)
```
You are reviewing a plan. Use the plan-reviewer skill:
[Content of .skills/plan-reviewer/SKILL.md]
```

## Creating or Updating Skills
1. Create/update `.skills/<skill-name>/SKILL.md` with YAML frontmatter (`name`, `description`).
2. Update `.skills/SKILLS.md` to list the skill.
3. Test the skill in a real workflow.

## Related Docs
- Documentation map: `DOCUMENTATION_STRUCTURE.md`
- Skills index: `.skills/SKILLS.md`
