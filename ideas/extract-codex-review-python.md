# Extract Codex CI Review Python from YAML

**Status:** proposed

## Problem

`.github/workflows/codex-ci-review.yml` is 496 lines, ~400 of which are embedded Python in two heredoc blocks. This makes the logic untestable, unlintable, and hard to review — diffs mix workflow plumbing with business logic.

## Goal

Extract the embedded Python into `.github/scripts/codex_review.py` (or similar) so that:
1. The workflow YAML becomes thin glue (~50 lines): checkout, setup-python, env vars, `python3 .github/scripts/codex_review.py`
2. The Python script is importable and testable with pytest
3. Severity normalization, comment validation, escaping, and posting logic all have unit tests

## Quest Prompt

```
Extract the embedded Python from .github/workflows/codex-ci-review.yml into a standalone script at .github/scripts/codex_review.py.

Context:
- The workflow has two `python3 << 'PYEOF'` heredoc blocks (starting at lines 57 and 167)
- The first block handles prompt assembly and Codex invocation
- The second block handles comment parsing, severity normalization, validation, dedup, escaping, and posting via gh API
- Environment variables (REPO, PR_NUMBER, COMMIT_SHA, etc.) are passed from the workflow

Requirements:
1. Move all Python logic into .github/scripts/codex_review.py (split into functions, use if __name__ == "__main__" entry point)
2. The YAML workflow steps should call `python3 .github/scripts/codex_review.py` with env vars, no more heredocs
3. Add tests in tests/test_codex_review.py covering:
   - normalize_severity: valid values normalize (case-insensitive, whitespace-trimmed), invalid returns None
   - is_valid_comment: missing severity accepted, invalid severity stripped, valid severity normalized
   - escape_github_command_field: escapes %, CR, LF, :, and comma
   - Comment structural validation (missing path/body/line rejected)
4. Ensure CI still passes — the codex-review workflow must behave identically
5. Update the PR #84 description validation section to replace the code-review checklist with: `pytest tests/test_codex_review.py -v` and expect all tests to pass

Constraints:
- Do NOT change any behavioral logic — this is a pure extract-and-test refactor
- Keep the same env var interface between YAML and Python
- The script must work when called from the workflow working directory (repo root)
```

## Acceptance Criteria

- [ ] No Python heredocs remain in `codex-ci-review.yml`
- [ ] `python3 .github/scripts/codex_review.py` runs successfully in CI
- [ ] `pytest tests/test_codex_review.py -v` passes with tests for normalization, validation, escaping
- [ ] CI `codex-review` check passes end-to-end
- [ ] PR #84 description updated with the new test command
