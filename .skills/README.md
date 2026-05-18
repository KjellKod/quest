# Skills System

This directory contains specialized skills for AI agents working in this repository.

## What Are Skills?

Skills are modular, self-contained packages that extend AI capabilities with specialized knowledge and workflows. They help AI agents perform specific tasks more effectively by providing:

- **Procedural knowledge:** Step-by-step workflows for specific tasks
- **Pattern recognition:** Common issues and how to address them
- **Best practices:** Language-specific and domain-specific guidance

## Available Skills

See **[SKILLS.md](SKILLS.md)** for the canonical, up-to-date index of every skill in this repo. That file is the single source of truth — this README intentionally does not duplicate the enumeration to avoid drift.

## How to Use Skills

### Automatic Discovery

Skills are automatically discovered and used by AI agents based on task context. The YAML `description` field in each skill's `SKILL.md` is used to determine when a skill is relevant.

### Explicit Usage

You can explicitly reference skills in prompts:

```
Review this implementation plan using the plan-reviewer skill.
```

```
Review this pull request using the code-reviewer skill.
```

### Platform Support

- **Claude Code:** Automatically discovers and uses skills
- **Cursor:** Automatically discovers and uses skills
- **OpenAI GPT:** Requires explicit loading (see `BOOTSTRAP.md`)

## Documentation

- **SKILLS.md:** Directory of all available skills
- **BOOTSTRAP.md:** How to use skills with different AI platforms
- **README.md:** This file (overview)

## Adding New Skills

1. Create `.skills/skill-name/SKILL.md`
2. Follow the skill-creator guidelines
3. Update `.skills/SKILLS.md`
4. Test the skill in practice

See `BOOTSTRAP.md` for detailed instructions.
