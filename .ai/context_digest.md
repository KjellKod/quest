# Codex Review Context Digest

Purpose: Provide the minimum stable context for GPT 5.2 reviews. Read this before reviewing plans or code.

## Architecture Boundaries (customize for your repo)

Add your project's architecture boundaries here. Example:
- src/: Application source code
- tests/: Test files
- lib/: Shared libraries
- scripts/: Build and utility scripts

## Review Priorities (highest first)
1. Correctness and regressions
2. Security and data handling
3. Missing or insufficient tests
4. Architecture boundary violations
5. Maintainability issues that cause bugs

## Testing Expectations
- Bug fixes use TDD when practical (red → green → verify).
- Unit tests in tests/unit, integration tests in tests/integration.
- Do not hit network in unit tests; mock at API boundaries.

## Style and Change Scope
- Prefer minimal, focused changes.
- Avoid broad refactors unless preventing a real bug.

## Reference Docs
- AGENTS.md (full rules)
- docs/architecture/ (system design if present)
