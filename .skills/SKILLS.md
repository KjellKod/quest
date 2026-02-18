# Skills Directory

This directory contains specialized skills for AI agents working in this repository. Skills are modular, self-contained packages that extend AI capabilities with specialized knowledge and workflows.

## Available Skills

### quest
**Purpose:** Multi-agent orchestration for non-trivial features. Coordinates Planner, dual Plan Reviewers (Claude + Codex), Arbiter, Builder, Code Reviewer, and Fixer through structured handoffs with human approval gates.

**Use when:** The user invokes `/quest` or `$quest`, or describes a feature that needs planning, review, implementation, and code review as separate coordinated phases. Also use when resuming an existing quest by ID.

**Location:** `.skills/quest/SKILL.md`

**Workflow phases:**
1. Intake (create quest folder, brief)
2. Plan (planner → dual review → arbiter loop)
3. Build (implementation with gate)
4. Review (code review)
5. Fix (fix loop if issues found)
6. Complete (summary, next steps)

### plan-maker
**Purpose:** Create implementation plans with testable acceptance criteria, validation strategies, integration touchpoints, and risk analysis before coding begins.

**Use when:** Creating implementation plans for features, refactors, infrastructure, or architectural changes.

**Location:** `.skills/plan-maker/SKILL.md`

### plan-reviewer
**Purpose:** Review implementation plans, PR specifications, and feature documentation to ensure comprehensive test coverage and validation strategies.

**Use when:** Reviewing any implementation plan or feature specification before coding begins.

**Location:** `.skills/plan-reviewer/SKILL.md`

### code-reviewer
**Purpose:** Review actual code implementations for correctness, maintainability, security, and adherence to patterns.

**Use when:** Reviewing pull requests, code changes, or implementations.

**Location:** `.skills/code-reviewer/SKILL.md`

### ci-code-reviewer
**Purpose:** Automated CI code review for GitHub PRs using OpenAI Codex. Validates PR descriptions, enforces Quest architecture boundaries, checks quality, and maps test coverage to acceptance criteria.

**Use when:** Running automated code review in GitHub Actions when a PR transitions from draft to ready-for-review.

**Location:** `.skills/ci-code-reviewer/SKILL.md`

### implementer
**Purpose:** Implement an approved implementation plan step by step, producing small reviewable changes and mapping code/tests to acceptance criteria.

**Use when:** The plan/spec is already agreed and you want disciplined execution with traceability and a lightweight decision log.

**Location:** `.skills/implementer/SKILL.md`

### git-commit-assistant
**Purpose:** Generate commit messages from staged changes by matching repo conventions (Conventional Commits or plain English), leading with intent, and appending the Quest co-author trailer.

**Use when:** The user asks for a commit message, help with git commit, or when reviewing staged changes for commit.

**Location:** `.skills/git-commit-assistant/SKILL.md`

### pr-assistant
**Purpose:** Create and update GitHub pull requests in draft mode. Generates PR title and description from all branch commits, shows for approval before executing.

**Use when:** The user asks to create a PR, update a PR description, or open a pull request.

**Location:** `.skills/pr-assistant/SKILL.md`

## How Skills Work

Skills use a three-level loading system:

1. **Metadata (name + description)** - Always in context (~100 words)
2. **SKILL.md body** - Loaded when skill triggers (<5k words)
3. **Bundled resources** - Loaded as needed (scripts, references, assets)

Skills are triggered automatically by AI agents based on the description in the YAML frontmatter. The description should clearly indicate when to use the skill.

## Adding New Skills

1. Create a new directory: `.skills/skill-name/`
2. Create `SKILL.md` with:
   - YAML frontmatter with `name` and `description`
   - Clear "When to Use" section
   - Step-by-step process
   - Examples and patterns
3. Update this file to document the new skill
4. Follow the skill-creator guidelines for structure

## Skill Structure

Each skill should have:
- **YAML frontmatter:** `name` and `description` (triggers skill selection)
- **When to Use:** Clear boundaries for when skill applies
- **Process:** Step-by-step workflow
- **Output:** Expected review/documentation structure
- **Principles:** Core review principles
- **Examples:** Common patterns and issues

## Documentation Location Guidance

Planning documents should follow this convention:

| Document State | Location |
|----------------|----------|
| **In Progress** | `docs/implementation/` (root level) |
| **Fully Implemented** | `docs/implementation/history/` |
| **Future/Backlog** | `docs/implementation/backlog/` |

**Workflow:**
1. Create new planning documents in `docs/implementation/` with status `Planned` or `Active`
2. Update the document's status as implementation progresses
3. Once **fully implemented** (all acceptance criteria met), move to `docs/implementation/history/` and update status to `Complete`

## Best Practices

1. **Keep skills focused:** One skill, one purpose
2. **Be specific in descriptions:** Clear triggers for when to use
3. **Provide examples:** Show common patterns and issues
4. **Stay language-aware:** Consider Python, JS/TS, React patterns
5. **Reference existing patterns:** Link to `AGENTS.md` and architecture docs
