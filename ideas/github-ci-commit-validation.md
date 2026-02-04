# GitHub CI for Commit-Time Quest Validation

## What
A GitHub Actions workflow that validates quest artifacts at commit time.

## Why
Ensure that quest-related changes maintain consistency:
- Handoff schema compliance
- Allowlist configuration is valid JSON
- Role definitions are complete
- No accidental commits of ephemeral `.quest/` state

## Approach
- Pre-commit hook for local validation
- GitHub Actions for CI validation
- Schema validation for all JSON files in `.ai/`
- Markdown structure validation for role definitions
- Check that `.quest/` is properly gitignored

## Status
idea
