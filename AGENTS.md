---
title: Coding Rules & Architecture Boundaries
purpose: Defines coding conventions, architecture boundaries, and project rules that AI agents must follow before making changes.
audience: AI agents and contributors
scope: Repo-wide coding standards and constraints
status: active
owner: maintainers
---

# Coding Rules & Architecture Boundaries

This document defines the coding conventions and architecture boundaries for this project. AI agents MUST read this before making changes.

## Core Principles

We drive with a quality mindset in everything — planning, reviewing, and building.

- **KISS** (Keep It Simple, Stupid) — Prefer simple solutions over clever ones
- **DRY** (Don't Repeat Yourself) — Extract common patterns, but not prematurely
- **YAGNI** (You Aren't Gonna Need It) — Don't add features until they're needed
- **SRP** (Single Responsibility Principle) — Each change, function or module should focusing on doing one thing

## Change Discipline

- Prefer minimal, focused changes
- Avoid broad refactors unless they fix real bugs
- Don't add "improvements" that weren't requested
- Run linters, formatting, and tests before commits
- Test real logic, skip trivial code (getters, imports, types)

## Testing Expectations

- Bug fixes: add a test that reproduces the bug (fails first), fix the code without changing that test, then re-run it to verify it passes.
- Unit tests in `tests/unit/`, integration tests in `tests/integration/`
- Mock at boundaries (APIs, DBs, I/O), not internal logic
- Test names describe behavior: `test_create_user_when_email_invalid_returns_400()`

## Security Hygiene

- No secrets in code, logs, or API responses
- No sensitive data leaks in error messages
- Input validation at trust boundaries
- Authorization checks where required

## Documentation Requirements

- Update docs when changing user-facing behavior
- Move completed plans to `docs/implementation/history/`
- Keep README.md focused on getting started

## Quest Orchestration

This repository uses the `/quest` command for multi-agent feature development:

```
/quest "Add a new feature"
```

See `.ai/quest.md` for full documentation.

### Skills Discovery READ THIS
Check this location for available skills. 
1. `.skills` --> see .skills/SKILLS.md
2. `.agents/skills/`

### Skills Source of Truth & Precedence
- Before starting any task, inspect `.skills/SKILLS.md` and `.agents/skills/` for available skills
- Repo-local skill definitions are authoritative
- Preloaded or session-provided skill lists are hints/fallbacks, not source of truth
- If sources disagree, report the mismatch explicitly and follow repo-local definitions

### Allowlist Configuration

Customize `.ai/allowlist.json` for your project's:
- Source directories (where builder/fixer can write)
- Test commands (pytest, npm test, etc.)
- Approval gates (which phases need human sign-off)

## Where to Learn More

| Topic | Location |
|-------|----------|
| Quest orchestration | `.ai/quest.md` |
| SKILLs directory  | `.skills/SKILLS.md` |
| Quest setup guide | `docs/guides/quest_setup.md` |
| Architecture | `docs/architecture/` (if present) |

## Quest Execution Discipline
- For `$quest`, follow the full gate sequence: routing -> plan -> dual plan review -> arbiter -> walkthrough -> explicit approval -> build -> dual code review -> fixes.
- Do not edit project/source files before Build gate approval.
- If implementation starts early, stop, disclose, and return to required gates.

## PR Review Gate
- Always use feature branches and draft PRs.
- Before merge, post an explicit review comment on the draft/ready PR.
- Merge only after filtering low-value NITs and judging through readability-first, KISS, YAGNI, SRP, and DRY.
- Prefer simple robust over complex elegance.
- Keep tests high quality and avoid mocking-hell.
