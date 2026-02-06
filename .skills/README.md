# Skills System

This directory contains specialized skills for AI agents working in this repository.

## What Are Skills?

Skills are modular, self-contained packages that extend AI capabilities with specialized knowledge and workflows. They help AI agents perform specific tasks more effectively by providing:

- **Procedural knowledge:** Step-by-step workflows for specific tasks
- **Pattern recognition:** Common issues and how to address them
- **Best practices:** Language-specific and domain-specific guidance

## Available Skills

### plan-reviewer
**Purpose:** Review implementation plans, PR specifications, and feature documentation to ensure comprehensive test coverage and validation strategies.

**Use when:** Reviewing any implementation plan or feature specification before coding begins.

**Key focus areas:**
- Acceptance criteria completeness
- Manual validation procedures
- Automated testing specifications
- Integration point validation

### code-reviewer
**Purpose:** Review actual code implementations (Python, JavaScript, TypeScript, React) for correctness, maintainability, security, and adherence to patterns.

**Use when:** Reviewing pull requests, code changes, or implementations.

**Key focus areas:**
- Architecture boundary compliance
- Code quality and patterns
- Security review
- Test coverage
- Performance considerations

### implementer
**Purpose:** Implement an approved implementation plan step by step, producing small reviewable changes and mapping code/tests to acceptance criteria.

**Use when:** The plan/spec is already agreed and you want disciplined execution with traceability and a lightweight decision log.

### git-commit-assistant
**Purpose:** Generate commit messages from staged changes by matching repo conventions (Conventional Commits or plain English), leading with intent, and appending the Quest co-author trailer.

**Use when:** The user asks for a commit message, help with git commit, or when reviewing staged changes for commit.

### pr-assistant
**Purpose:** Create and update GitHub pull requests in draft mode. Generates PR title and description from all branch commits, shows for approval before executing.

**Use when:** The user asks to create a PR, update a PR description, or open a pull request.

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
