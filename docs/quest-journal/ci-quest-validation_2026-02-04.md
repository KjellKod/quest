# CI Quest Validation

**Completed**: 2026-02-04
**Quest ID**: ci-quest-validation_2026-02-04__1532
**PR**: #TBD

## Summary

Implemented GitHub Actions CI and local pre-commit hooks that validate quest-related artifacts to prevent broken configurations from being committed.

**What was built**:
- JSON schema for `.ai/allowlist.json` validation
- Pre-commit validation script (`scripts/quest_validate-quest-config.sh`)
- GitHub Actions workflow for CI validation
- Role markdown completeness checking
- Quest journal system (`docs/quest-journal/`)

## Quest Brief

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

### Archived Brief

Full original prompt was not recorded for this quest. This is the best available brief context.

Implement GitHub Actions CI and local pre-commit hooks that validate quest-related artifacts to prevent broken configurations from being committed.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/ci-quest-validation_2026-02-04.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "unknown",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    },
    {
      "name": "plan-reviewer-a",
      "model": "anthropic/claude-opus",
      "role": "The A Plan Critic"
    },
    {
      "name": "plan-reviewer-b",
      "model": "openai/gpt-5.3-codex",
      "role": "The B Plan Critic"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    },
    {
      "name": "fixer",
      "model": "",
      "role": "The Bug Slayer"
    },
    {
      "name": "code-reviewer-a",
      "model": "anthropic/claude-opus",
      "role": "The A Code Critic"
    },
    {
      "name": "code-reviewer-b",
      "model": "openai/gpt-5.3-codex",
      "role": "The B Code Critic"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 7 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 5 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 3 times"
    },
    {
      "icon": "[TEAM]",
      "title": "Full Squad",
      "desc": "7 agents collaborated"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 3"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 1"
    },
    {
      "icon": "📝",
      "label": "Review findings: 5"
    }
  ],
  "quality": {
    "tier": "Bronze",
    "grade": "B"
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 0
}
```
<!-- celebration-data-end -->
