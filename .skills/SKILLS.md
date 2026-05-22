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

### pre-commit-review
**Purpose:** Review local staged plus unstaged tracked-file changes before commit or before a PR exists.

**Use when:** The user invokes `/pre-commit-review`, asks for a pre-commit review, asks to review local changes before commit, or wants a local working-tree review before a PR exists.

**Location:** `.skills/pre-commit-review/SKILL.md`

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

### pr-shepherd
**Purpose:** Shepherd an existing PR through CI and review comments, then mark ready for review when clean. Uses inline-first review handling; PR creation belongs to pr-assistant.

**Use when:** The user wants to keep an existing PR moving through CI and review, or asks to shepherd/babysit a PR until it's ready.

**Location:** `.skills/pr-shepherd/SKILL.md`

### review-decisions
**Purpose:** Shared policy for translating canonical review findings into deterministic backlog decisions (`fix_now`, `verify_first`, `defer`, `drop`, `needs_human_decision`) including loop-cap behavior and deferred backlog lineage.

**Use when:** Arbiter or automation needs to produce `review_backlog.json`, enforce the review-loop cap, or append deferred findings to `.quest/backlog/deferred_findings.jsonl`.

**Location:** `.skills/review-decisions/SKILL.md`

### gpt
**Purpose:** Delegate tasks to OpenAI Codex (GPT-5.4) via MCP. Provides structured invocation with sensible defaults for sandbox, model, and reasoning effort.

**Use when:** The user invokes `/gpt`, asks to "use codex" or "ask codex", wants a second opinion from a different model, or Quest routes a role to Codex.

**Location:** `.skills/gpt/SKILL.md`

### celebrate
**Purpose:** Play a rich quest completion celebration animation with block letters, achievements, impact metrics, quality score, and end credits. Runs the celebrate script or produces a manual celebration from quest artifacts.

**Use when:** The user invokes `/celebrate`, asks to celebrate a quest, or when a quest reaches completion. Also triggered by the quest workflow Step 7.

**Location:** `.skills/celebrate/SKILL.md`

### sharpen
**Purpose:** Adversarial interview against a plan, design, or write-up — one question at a time, each with a recommended answer attached — to surface contradictions, hidden assumptions, and unresolved tradeoffs before they ship. Also has a `ux-defaults` mode for locking in UX choices (gray ramp, density, mobile relevance, accent) when a backend engineer can recognize good UX but can't articulate it from scratch.

**Use when:** The user invokes `/sharpen` or `$sharpen`, says "sharpen this", "stress-test this", "find the holes", "challenge my plan", or wants to confirm shared understanding before locking a decision. Auto-routes to `ux-defaults` mode when invoked during plan presentation on a `ui_work: true` quest; can also be invoked explicitly as `/sharpen ux-defaults`.

**Location:** `.skills/sharpen/SKILL.md`

### ux-context
**Purpose:** Primer skill that loads the canonical UX guidebook and stress-test rubric. Auto-attached by the orchestrator when the router classifies a quest as `ui_work: true`, so planners, builders, and fixers shape their output against durable UX principles (Norman, Rams, Nielsen, Apple HIG, Refactoring UI, Linear/Vercel/Rauno). Bundles the canonical guidebook so the standard travels with the skill into installed repos.

**Use when:** Auto-attached by quest orchestration when `ui_work: true`. Not user-invocable directly — for direct critique, use `ux-review`.

**Location:** `.skills/ux-context/SKILL.md`

**Resources:** `.skills/ux-context/resources/ux-guidebook.md`, `.skills/ux-context/resources/ux-stress-test.md`

### ux-review
**Purpose:** Run the canonical UX stress-test rubric against a target (file, directory, URL, screenshot, or git diff) and produce a structured critique report with P0–P3 severity, principle citations, and a bright-spots section. Sources its rubric from the `ux-context` skill's bundled guidebook.

**Use when:** The user invokes `/ux-review` or `$ux-review`, asks for a UX critique of a screen / component / app, asks to triage a clunky existing project, or is reviewing UI changes before commit. Also auto-attached to plan-reviewer and code-reviewer agents when the quest router sets `ui_work: true`.

**Location:** `.skills/ux-review/SKILL.md`

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
