# CI: Add pytest to GitHub Actions

## Problem

The current CI (`validate-quest-config.yml`) only validates Quest configuration files (allowlist schema, manifest, handoff contracts). It does not run the Python test suite. This means the 36 unit and integration tests for the Quest Dashboard are only run locally — regressions can slip through PRs undetected.

## Proposal

Add a pytest job to the existing CI workflow (or a new workflow) that runs on push/PR to `main`.

### Minimal scope

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.12'

- name: Install dependencies
  run: pip install pytest

- name: Run tests
  run: python3 -m pytest tests/ -v
```

### Considerations

- **No external dependencies:** The dashboard package has zero pip dependencies beyond stdlib. Only `pytest` itself is needed.
- **`pyproject.toml` exists:** The repo now has a `pyproject.toml` with `[tool.pytest.ini_options]`. Could use `pip install -e .` for cleaner imports, or rely on `conftest.py` sys.path fallback.
- **Speed:** 36 tests run in ~0.7s. Negligible CI cost.
- **Placement:** Could be a new job in `validate-quest-config.yml` (keeps all validation together) or a separate `test.yml` workflow (cleaner separation).

## Priority

High. Tests exist but aren't enforced in CI. This is the lowest-effort, highest-value CI improvement available.
