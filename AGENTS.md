# Coding Rules & Architecture Boundaries

This document defines the coding conventions and architecture boundaries for this project. AI agents MUST read this before making changes.

## Core Principles

### Code Quality
- **KISS** (Keep It Simple, Stupid) — Prefer simple solutions over clever ones
- **DRY** (Don't Repeat Yourself) — Extract common patterns, but not prematurely
- **YAGNI** (You Aren't Gonna Need It) — Don't add features until they're needed
- **SRP** (Single Responsibility Principle) — Each module/function should do one thing

### Change Philosophy
- Prefer minimal, focused changes
- Avoid broad refactors unless they fix real bugs
- Don't add "improvements" that weren't requested
- Test real logic, skip trivial code (getters, imports, types)

## Architecture Boundaries

Customize this section for your project. Define what each directory/module is responsible for:

```
src/           # Application source code
  components/  # UI components (if applicable)
  services/    # Business logic and external integrations
  utils/       # Shared utility functions
lib/           # Shared libraries
tests/         # Test files
  unit/        # Unit tests
  integration/ # Integration tests
scripts/       # Build and utility scripts
docs/          # Documentation
  architecture/    # System design docs
  implementation/  # Active and historical plans
  guides/          # How-to guides
```

### Boundary Rules (customize for your project)

1. **Components** only handle UI rendering and local state
2. **Services** handle business logic and external API calls
3. **Utils** are pure functions with no side effects
4. **Tests** mock at service boundaries, not internal logic

## Testing Expectations

- Bug fixes use TDD when practical (red → green → verify)
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

### Allowlist Configuration

Customize `.ai/allowlist.json` for your project's:
- Source directories (where builder/fixer can write)
- Test commands (pytest, npm test, etc.)
- Approval gates (which phases need human sign-off)

## Where to Learn More

| Topic | Location |
|-------|----------|
| Quest orchestration | `.ai/quest.md` |
| Available skills | `.skills/SKILLS.md` |
| Quest setup guide | `docs/guides/quest_setup.md` |
| Architecture | `docs/architecture/` (if present) |
