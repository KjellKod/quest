# Code Review: Celebration from Journal

**Reviewer:** Code Review Agent
**Date:** 2026-03-06
**Recommendation:** Approve with minor fixes (no blockers)

---

## 1. Summary

- Implementation aligns well with the idea document's goals: quality tiers, embedded celebration_data JSON, dashboard integration, celebrate skill journal resolution, and workflow Step 7 documentation are all present.
- Code is clean, well-structured, and follows existing patterns. Error handling is consistently defensive (try/except with graceful fallback).
- Test coverage is solid: 15 new celebrate tests + 6 new dashboard loader tests cover the key paths.
- Two instances of duplicated logic between `quest_data.py` and `loaders.py` create a DRY violation that should be addressed.
- No security issues found; HTML output is properly escaped.

---

## 2. Blockers

None.

---

## 3. Must Fix

### 3a. Duplicated `_extract_celebration_data` regex between two modules

**Files:** `scripts/quest_celebrate/quest_data.py:622-642` and `scripts/quest_dashboard/loaders.py:483-503`

These two functions contain identical regex patterns and identical logic. If the marker format changes (e.g., whitespace tolerance, marker names), both must be updated in lockstep. This is a textbook DRY violation.

**Fix:** Extract a shared utility (e.g., in a small `scripts/shared/celebration_json.py` or a `scripts/quest_celebrate/journal_parser.py`), and have both modules import from it. Alternatively, have the dashboard loader import from `quest_celebrate.quest_data._extract_celebration_data_from_journal` if cross-package import is acceptable in this codebase.

### 3b. Duplicated `friendly_model` logic in three locations

**Files:**
- `scripts/quest_celebrate/quest_data.py:404-418` (nested function inside `_compute_achievements`)
- `scripts/quest_celebrate/ascii_art.py:516` (another copy)
- `scripts/quest_dashboard/loaders.py:506-523` (`_friendly_model_name`)

All three use the same keyword-match logic (kimi, opus/claude, codex/gpt) with the same output labels. Same DRY risk as above.

**Fix:** Same approach -- extract to a shared location and import.

---

## 4. Should Fix

### 4a. `compute_quality_tier` has a confusing overlap between Platinum and Gold for `plan=1, fix=1, findings=0`

In `quest_data.py:604-619`, consider the case: `plan_iterations=1, fix_iterations=1, review_findings_count=0, status="complete"`.

Walkthrough:
- Not abandoned, not Cardboard, not Tin, not Bronze (iterations below thresholds).
- Not Silver (`fix_iterations != 2`).
- Gold check at line 604: `fix_iterations == 1 and plan_iterations > 1` -- fails because `plan_iterations == 1`, so **not** Gold.
- Platinum check at line 608: `plan_iterations <= 1 and fix_iterations <= 1 and review_findings_count > 0` -- fails because `review_findings_count == 0`.
- Diamond check at line 612: `fix_iterations == 0` -- fails because `fix_iterations == 1`.
- Fallback at line 616: `plan_iterations <= 1 and fix_iterations == 0` -- fails.
- Falls to default return "Gold" at line 619.

So a quest with 1 plan iteration, 1 fix iteration, and zero findings gets Gold. But the idea doc says: `plan_iterations=1, fix_iterations=1, issues all fixed -> Platinum`. The implementation diverges from the spec because it requires `review_findings_count > 0` for Platinum, but the idea doc says "issues all fixed" which implies there WERE issues. A fix iteration with zero findings is an ambiguous edge case.

**Fix:** Either document this as intentional (zero findings + 1 fix iteration is unusual), or relax the Platinum check to `fix_iterations <= 1` without the findings constraint when `plan_iterations == 1`.

### 4b. Dashboard tier badge is not wrapped in a flex container with the status badge

In `render.py:1012`:
```html
<span class="badge badge--{badge_class}">{badge_text}</span>{tier_badge_html}
```

The tier badge is appended as a raw sibling inside `quest-card-header`, which uses `display: flex; justify-content: space-between`. With the title taking `flex: 1`, the two badges float right but have no explicit gap between them (just a leading space character). This works but is fragile.

**Fix:** Wrap both badges in a `<div style="display:flex;gap:0.5rem">` or add a dedicated `.badges-group` class. Low priority since it renders fine today.

### 4c. `celebration_data` stored as raw `dict` on frozen dataclass `JournalEntry`

In `models.py:36`, `celebration_data: dict | None = None` on a `frozen=True` dataclass. While Python allows this (frozen only prevents attribute reassignment, not mutation of mutable contents), storing a raw dict on what is conceptually an immutable value object is a design smell. A consumer could mutate the dict, violating the frozen intent.

**Fix:** Consider storing as `tuple` of items, or a frozen dataclass, or documenting that consumers must not mutate it. Low priority -- no current consumers mutate it.

---

## 5. Test Coverage vs Acceptance Criteria

| Acceptance Criterion (from idea doc) | Test Coverage | Verdict |
|---------------------------------------|--------------|---------|
| Quality tiers (Diamond through Cardboard + Abandoned) | `TestQualityTier` - 8 tests cover all tiers, plus `test_all_tiers_in_quality_tiers_dict` | Covered |
| Embedded celebration_data JSON extraction | `TestJournalCelebrationData` - 3 extraction tests + 2 load tests; `test_extract_celebration_data_*` in dashboard tests (3 tests) | Covered |
| Dashboard: tier badges with hover tooltips | No rendering test verifies badge HTML output contains tier icon/tooltip | **Gap** |
| Dashboard: agent model credits display | No rendering test verifies Cast line in meta | **Gap** |
| Dashboard: test count display | No rendering test verifies Tests line in meta | **Gap** |
| Celebrate skill: journal resolution | Covered by `test_load_quest_data_from_journal_*` (celebrate side) | Covered |
| Legacy entries graceful degradation | `test_load_quest_data_from_journal_legacy_no_celebration_data`, `test_journal_entry_without_celebration_data_has_none_fields` | Covered |
| Workflow Step 7 docs | Documentation only, no test needed | N/A |
| `_friendly_model_name` mapping | `test_friendly_model_name_mapping` covers all branches | Covered |
| Nonexistent file handling | `test_load_quest_data_from_journal_nonexistent_file` | Covered |

**Missing test coverage (Should fix):** There are no tests for `_render_quest_card` or `render_dashboard` that verify the new tier badge HTML, Cast meta line, or Tests meta line actually appear in the rendered output. These are the user-visible parts of the dashboard integration. Even a simple test that creates a `JournalEntry` with `quality_tier="Gold"` and `agent_models=("Claude Opus",)` and asserts the rendered card contains the expected badge and meta strings would close this gap.

---

## 6. Security

- HTML rendering in `render.py` uses `html.escape()` consistently for all user-derived strings (title, quest_id, elevator_pitch, model names, test counts, tooltips). No injection risk.
- JSON parsing in both `_extract_celebration_data` functions uses `json.loads` on content extracted via regex -- safe, since malformed JSON returns `None`.
- URL sanitization in `_sanitize_url` rejects non-HTTPS schemes and validates GitHub URL patterns. Solid.
- No secrets or sensitive data in any output path.

---

## 7. Consistency Between Two Data Readers

The celebrate `quest_data.py` and dashboard `loaders.py` both parse `celebration_data` JSON using identical regex patterns (Must Fix 3a above). Beyond the duplication, they handle the parsed data **differently but correctly for their contexts**:

- `quest_data.py` maps into `AgentInfo`/`Achievement` dataclasses with full field mapping
- `loaders.py` maps into `JournalEntry` fields (quality_tier, agent_models tuple, test_count, tests_added)

The `_friendly_model_name` / `friendly_model` functions use the same keyword matching in both places, which is good for consistency but bad for DRY (Must Fix 3b).

One subtle inconsistency: `quest_data.py:friendly_model` returns empty string for empty input, while `loaders.py:_friendly_model_name` returns the input string unchanged for empty input (line 515: `return model`). In practice this does not cause bugs because both callers skip empty models, but it is a contract divergence that would be resolved by sharing the function.

---

## 8. Skill and Workflow Docs

- **`.skills/celebrate/SKILL.md`**: Clear and complete. Journal resolution path documented in Step 1, celebration_data extraction in Step 2, full tier table with tone guidance. The non-goal about backfilling is handled correctly (wing-it for legacy).
- **`.skills/quest/delegation/workflow.md` Step 7**: The celebration_data JSON block schema is documented with the example structure and clear guidance ("context-aware and specific -- not generic"). Good.

Both docs are consistent with the implementation.

---

## Verdict

**Approve with fixes.** The Must Fix items (DRY violations) are real maintenance risks but do not block functionality. The Should Fix items are quality improvements. No blockers, no security issues, and the implementation faithfully delivers all five goals from the idea document.
