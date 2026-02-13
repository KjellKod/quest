# Final Decision: PR #26 Code Review Arbitration

## Scope
- Inputs reviewed:
  - `ideas/dashboard-pr26-code-review.md` (Claude)
  - `ideas/dashboard-pr26-code-review-codex.md` (Codex/GPT-5.3)
- Goal: decide what must change for PR #26, what can be deferred, and what we are explicitly not changing.

## Final Arbiter Decision

### Must change before merge
1. **Fix HTML attribute injection risk in links (security)**
   - Source: Codex review (must-fix), corroborated in `scripts/quest_dashboard/render.py:489`, `scripts/quest_dashboard/render.py:499`, `scripts/quest_dashboard/render.py:601`, `scripts/quest_dashboard/render.py:627`.
   - Decision: **Required**.
   - Rationale: `href` values are interpolated without attribute escaping/validation. A crafted `github_url` can break attributes and inject HTML/JS.
   - Required acceptance:
     - Escape URL attribute values before rendering into `href="..."`.
     - Validate/sanitize `github_url` input to a strict expected format (or fall back safely).
     - Add tests that cover malicious quote-containing URL input.

### Should change in this PR if low risk
1. **Remove parsing-layer stderr side effects**
   - Source: Codex should-fix, `scripts/quest_dashboard/loaders.py:542`.
   - Decision: **Do now if straightforward**.
   - Rationale: loader already returns warnings; printing inside parser mixes library and CLI concerns and can duplicate output.

2. **Unify `github_url` “missing value” convention**
   - Source: Claude should-fix (`str | None` vs `""`), `scripts/quest_dashboard/loaders.py:37`, `scripts/quest_dashboard/loaders.py:626`.
   - Decision: **Do now if touched by security fix**.
   - Rationale: not a functional bug, but inconsistent semantics increase confusion during URL hardening work.

### Defer (valid, non-blocking)
1. **Hardcoded `/blob/main/` links**
   - Source: Codex should-fix, `scripts/quest_dashboard/render.py:601`.
   - Decision: **Defer**.
   - Rationale: current repository uses `main`; configurability is useful for reuse but is not a correctness/security blocker for this PR.

2. **Replace custom `_escape_html` with stdlib `html.escape`**
   - Source: Claude should-fix, `scripts/quest_dashboard/render.py:631`.
   - Decision: **Defer**.
   - Rationale: current text escaping is functionally correct. Security issue is specifically in unescaped attributes; fix that first.

3. **Unused `pytest` imports in tests**
   - Source: Codex nit, `tests/unit/test_quest_dashboard_loaders.py:7`, `tests/unit/test_quest_dashboard_render.py:6`.
   - Decision: **Defer**.
   - Rationale: cleanup only; no behavior impact.

### Not changing for this PR
1. **Package/installability refactor for `sys.path` insertion**
   - Source: Claude should-fix, `scripts/quest_dashboard/build_quest_dashboard.py:15`.
   - Decision: **Not doing in PR #26**.
   - Rationale: broader packaging change, not required to ship dashboard behavior.

2. **Journal README ordering/style note**
   - Source: Claude nit.
   - Decision: **Not doing**.
   - Rationale: no bug; ordering is already valid.

3. **`_extract_first_paragraph` regex fragility concern**
   - Source: Claude nit, `scripts/quest_dashboard/loaders.py:367`.
   - Decision: **Not doing**.
   - Rationale: current behavior is acceptable for current journal format and covered by tests; no concrete failing case provided.

4. **`_normalize_display_label` acronym edge case (`PR` -> `Pr`)**
   - Source: Claude nit, `scripts/quest_dashboard/loaders.py:562`.
   - Decision: **Not doing**.
   - Rationale: no current input uses problematic acronyms; speculative only.

5. **Trim or remove `ideas/quest-dashboard-analysis-and-plan.md`**
   - Source: Claude nit.
   - Decision: **Not doing**.
   - Rationale: documentation size concern only, no functional risk.

6. **Change generated `docs/dashboard/index.html` commit policy right now**
   - Source: both reviews.
   - Decision: **Not doing in PR #26**.
   - Rationale: current workflow intentionally commits generated output; policy changes should be handled separately.

7. **Split unrelated allowlist / SKILL changes into separate commit**
   - Source: Claude nit.
   - Decision: **Not doing in this arbitration file**.
   - Rationale: commit hygiene suggestion is reasonable but not a blocker for dashboard correctness/security.

## Consolidated Merge Gate
- Merge gate for PR #26 is:
  1. Fix link attribute injection risk.
  2. Add regression tests for malicious `github_url`.
- All other items are non-blocking and either deferred or explicitly out of scope for this PR.
