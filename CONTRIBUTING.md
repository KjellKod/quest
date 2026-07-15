# Contributing to Quest

## Development Setup

### Required Development Setup

Install the pinned development dependencies and configure this repository to
use its versioned pre-commit hook:

```bash
python3 -m pip install -e '.[dev]'
git config core.hooksPath .githooks
```

Every Quest contributor must configure `core.hooksPath` after cloning because
Git cannot propagate this local setting through a clone. The hook runs the
existing Quest configuration validation followed by
`python3 -m black --check .`. It is check-only and never rewrites files during
a commit.

Check or format the source repository directly with:

```bash
python3 -m black --check .
python3 -m black .
```

The local hook can be bypassed, so CI is the authoritative, non-bypassable
formatting gate.

### Manual Validation

Run validation without installing the hook:

```bash
./scripts/quest_validate-quest-config.sh
```

### Optional Dependencies

- **jq**: Full JSON validation (falls back to basic check if missing)
- **ajv-cli**: Schema validation (`npm install -g ajv-cli`)

## What Gets Validated

The validation script checks:

1. `.quest/` is in `.gitignore` (prevents committing ephemeral state)
2. `.ai/allowlist.json` is valid JSON
3. `.ai/allowlist.json` matches the schema (requires ajv)
4. `.skills/quest/agents/*.md` and `.ai/roles/quest_agent.md` have required sections:
   - `## Role` or `## Overview`
   - `## Tool` or `## Instances`
   - `## Context Required` or `## Context Available`
   - `## Output Contract`
   - `## Responsibilities` and `## Allowed Actions` (most roles)

## CI

GitHub Actions runs the same validation on every push and PR. See
`.github/workflows/validate-quest-config.yml`. The Python workflow also enforces
Black formatting for the Quest source repository.

## UI/UX Contributions

If your change touches user-facing UI (any of `*.tsx`/`*.jsx`/`*.css`/`*.svelte`/SwiftUI files, or modifies a visible surface), run `/ux-review <path>` against the change before opening the PR. The rubric and principles live in `.skills/ux-context/resources/`. In a quest, the router will auto-attach these when `ui_work: true`.
