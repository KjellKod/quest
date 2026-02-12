# Code Review (Codex/GPT-5.3): PR #26 — Quest Dashboard

## Overall Assessment
Verdict: **Request changes**.

The package is well-structured and the implementation is mostly clean, but there is a **must-fix security issue** in HTML link rendering. Tests are strong for happy paths and parsing variants, but they currently miss the highest-risk edge case.

## Strengths
1. Clear module boundaries: models (`scripts/quest_dashboard/models.py`), loading/parsing (`scripts/quest_dashboard/loaders.py`), and rendering (`scripts/quest_dashboard/render.py`) are cleanly separated.
2. Good defensive loading behavior: malformed or missing quest artifacts are converted into warnings instead of crashing (`scripts/quest_dashboard/loaders.py:102`, `scripts/quest_dashboard/loaders.py:472`).
3. Active-vs-journal deduplication is implemented and tested, preventing duplicate card appearance across sections (`scripts/quest_dashboard/loaders.py:61`, `tests/unit/test_quest_dashboard_loaders.py:343`).
4. Rendering is self-contained (inline CSS, no JS/external assets), matching the single-file output goal (`scripts/quest_dashboard/render.py:39`, `tests/unit/test_quest_dashboard_render.py:189`).
5. Test suite quality is solid for core behavior (29 passing tests, including integration execution of the build CLI).

## Issues
### Must-Fix
1. **HTML attribute injection/XSS via unescaped `href` values**.
File references: `scripts/quest_dashboard/render.py:489`, `scripts/quest_dashboard/render.py:499`, `scripts/quest_dashboard/render.py:601`, `scripts/quest_dashboard/render.py:627`.

`journal_link` and `pr_link` are inserted directly into `href="..."` without attribute escaping/validation. Because `github_url` can come from CLI (`--github-url`) or git remote auto-detection, a value containing `"` can break out of the attribute and inject arbitrary attributes/JS into the generated HTML.

Concrete reproduction:
`--github-url 'https://github.com/o/r" onclick="alert(1)'`
produces an anchor like:
`<a href="https://github.com/o/r" onclick="alert(1)/blob/main/...">`

Fix direction: escape attribute values before interpolation and/or validate URLs strictly (allow only `https://github.com/<owner>/<repo>`), then build links from validated components.

### Should-Fix
1. **Hardcoded `main` branch in journal links can generate broken links in repos not using `main`**.
File reference: `scripts/quest_dashboard/render.py:601`.

`/blob/main/...` is always used. This package is framed as reusable; branch assumptions should be configurable or detected.

2. **Loader has side effects (prints to stderr) in addition to returning warnings**.
File reference: `scripts/quest_dashboard/loaders.py:542`.

`_parse_active_quest` prints directly, while callers also receive warnings and may print them (`scripts/quest_dashboard/build_quest_dashboard.py:85`). This mixes library concerns with CLI output and can duplicate warnings.

### Nit / Consider
1. Generated artifact `docs/dashboard/index.html` is committed with runtime timestamp content, which can create noisy diffs over time (`docs/dashboard/index.html`). Consider documenting regeneration policy explicitly or generating in CI.
2. A few tests import `pytest` but do not use it (`tests/unit/test_quest_dashboard_loaders.py:7`, `tests/unit/test_quest_dashboard_render.py:6`).

## Security
- **High**: Attribute injection/XSS risk in rendered anchor tags due to unescaped link values (`scripts/quest_dashboard/render.py:489`, `scripts/quest_dashboard/render.py:499`).
- No evidence of secret leakage or dangerous command execution patterns in the new package.
- Input parsing is local-file based and generally bounded, but URL input paths need strict sanitization.

## Test Coverage Analysis
- Command run: `python3 -m pytest tests/ -v`
- Result: **29 passed, 0 failed**.

Coverage is good for:
- Markdown metadata extraction variants.
- Active quest parsing and archive skipping.
- Dedup between journal and active quests.
- HTML section ordering, KPI counts, warning rendering, and self-contained output.
- End-to-end CLI build invocation.

Coverage gaps:
1. No test for malicious `github_url`/remote URL escaping in HTML attributes (this missed the must-fix issue).
2. No test for non-`main` branch link behavior.
3. No test asserting loader functions are side-effect free (no direct stderr prints from parsing layer).

## Summary
The PR delivers a well-organized, test-backed Quest Dashboard implementation with strong baseline behavior. However, the unescaped `href` interpolation in `render.py` is a security-critical bug and should be fixed before merge. After that, branch configurability and loader logging boundaries are the next improvements to make this package robust and reusable.
