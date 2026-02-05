# CI Quest Validation

**Completed**: 2026-02-04
**Quest ID**: ci-quest-validation_2026-02-04__1532
**PR**: #TBD

## Summary

Implemented GitHub Actions CI and local pre-commit hooks that validate quest-related artifacts to prevent broken configurations from being committed.

**What was built**:
- JSON schema for `.ai/allowlist.json` validation
- Pre-commit validation script (`scripts/validate-quest-config.sh`)
- GitHub Actions workflow for CI validation
- Role markdown completeness checking
- Quest journal system (`docs/quest-journal/`)

## This is where it all began... an idea

> # GitHub CI for Commit-Time Quest Validation
>
> ## What
> A GitHub Actions workflow that validates quest artifacts at commit time.
>
> ## Why
> Ensure that quest-related changes maintain consistency:
> - Handoff schema compliance
> - Allowlist configuration is valid JSON
> - Role definitions are complete
> - No accidental commits of ephemeral `.quest/` state
>
> ## Approach
> - Pre-commit hook for local validation
> - GitHub Actions for CI validation
> - Schema validation for all JSON files in `.ai/`
> - Markdown structure validation for role definitions
> - Check that `.quest/` is properly gitignored
