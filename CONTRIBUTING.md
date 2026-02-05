# Contributing to Quest

## Development Setup

### Pre-commit Hook (Recommended)

Install the validation hook to catch configuration errors before commit:

```bash
./scripts/validate-quest-config.sh --install
```

This creates a symlink so the hook stays in sync with script updates.

To remove:
```bash
./scripts/validate-quest-config.sh --uninstall
```

### Manual Validation

Run validation without installing the hook:

```bash
./scripts/validate-quest-config.sh
```

### Optional Dependencies

- **jq**: Full JSON validation (falls back to basic check if missing)
- **ajv-cli**: Schema validation (`npm install -g ajv-cli`)

## What Gets Validated

The validation script checks:

1. `.quest/` is in `.gitignore` (prevents committing ephemeral state)
2. `.ai/allowlist.json` is valid JSON
3. `.ai/allowlist.json` matches the schema (requires ajv)
4. `.ai/roles/*.md` files have required sections:
   - `## Role` or `## Overview`
   - `## Tool` or `## Instances`
   - `## Context Required` or `## Context Available`
   - `## Output Contract`
   - `## Responsibilities` and `## Allowed Actions` (most roles)

## CI

GitHub Actions runs the same validation on every push and PR. See `.github/workflows/validate-quest.yml`.
