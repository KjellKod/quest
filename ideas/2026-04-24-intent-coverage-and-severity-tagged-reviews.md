---
title: Intent-Coverage + Severity-Tagged Reviews — Findings & Non-Breaking Integration Plan
purpose: Document two CI/PR-comment patterns observed in a reference project, compare against Quest's current CI, and propose how to add them without breaking what we already ship.
audience: Quest maintainers and CI-touching agents
scope: .github/workflows, .github/scripts, prompt templates
status: draft
owner: KjellKod (research by Claude)
date: 2026-04-24
---

# Suggested quest prompt to take this on

I agree this idea is worth doing, but it should stay split into two PRs. The
first PR should land the low-risk presentation cleanup for existing inline
comments. The second PR should add the new intent-review conversation surface.

Ready-to-paste first quest prompt:

```
/quest "Implement PR 1 of the intent-coverage + severity-tagged reviews idea: severity-tagged inline Codex CI review comments.

Reference:
- ideas/2026-04-24-intent-coverage-and-severity-tagged-reviews.md, especially Change 2.

Context:
- PR #101 already shipped the Deep CI review-context manifest. Do not add or redesign Deep CI context artifacts in this quest.
- Keep the existing three severity levels: blocker, must-fix, should-fix.
- Avoid drift: move severity label and advisory footer fully into .github/scripts/codex_review.py. Remove their generation from the prompt template.
- Add a regression test that the fallback PR review only fires when every inline post fails.

Branch:
- off main, name it severity-emoji-inline-reviews.

Scope:
1. .github/scripts/codex_review.py
   - Add SEVERITY_EMOJI = {\"blocker\": \"\\U0001f534\", \"must-fix\": \"\\U0001f7e0\", \"should-fix\": \"\\U0001f7e1\"} near VALID_SEVERITIES.
   - Add ADVISORY_FOOTER = \"*Automated review by Codex (advisory PR review).*\".
   - Add format_inline_body(severity: str | None, body: str) -> str.
   - The formatter must be idempotent: strip the body, prepend emoji + **Label** - only when not already present, append the footer only when not already present.
   - Unknown or missing severities must skip emoji and label but still get the footer.
   - In post_comments, call format_inline_body(comment.get(\"severity\"), comment[\"body\"]) before writing the temp-file payload.
   - Do not change dedup semantics. Keywords must still be derived from the unformatted model body.
2. .github/codex-review-prompt.md
   - Remove instructions telling the model to include **Blocker** / **Must fix** / **Should fix** prefixes in the body.
   - Remove examples or instructions that tell the model to include an automated-review footer.
   - Keep the structured severity JSON field requirement.
3. tests/unit/test_codex_review.py
   - Add test_format_inline_body_prefixes_emoji.
   - Add test_format_inline_body_unknown_severity_no_emoji.
   - Add test_format_inline_body_idempotent.
   - Add test_dedup_unaffected_by_emoji_prefix.
   - Add test_fallback_review_only_when_all_inline_posts_fail, covering all inline posts succeed, one succeeds/one fails, and all fail.

Constraints:
- Do not modify .github/workflows/codex-ci-review.yml or any other workflow.
- Do not modify VALID_SEVERITIES.
- Do not modify parse_review_output, is_duplicate, build_dedup_state, extract_keywords, build_deep_ci_manifest, render_deep_ci_markdown_from_manifest, or post_fallback_review logic.
- Doc/comment updates only where strictly required by the change.
- format_inline_body must accept severity: str | None and never raise on unknown values.

Acceptance:
- pytest tests/unit/test_codex_review.py -v passes.
- python -m py_compile .github/scripts/codex_review.py passes.
- Manual trace of post_comments with one finding per severity shows the body sent to GitHub starts with the correct emoji and bold label.
- The prompt no longer asks the model to own presentation formatting.

Out of scope:
- Intent-review workflow/helper/prompt. That is PR 2.
- Deep CI context manifest changes. PR #101 already shipped that.
- pr-body-gate.yml, security.yml, test-python.yml, validate-quest-config.yml, deploy-dashboard.yml.
- Adding nit, praise, info, low, or critical severities.

PR title:
Add severity emoji and consolidated formatting for inline CI reviews.

PR description:
Link to ideas/2026-04-24-intent-coverage-and-severity-tagged-reviews.md, summarize the prompt-vs-script consolidation decision, list the five new tests, and note this is the first of two PRs. The intent-review workflow follows separately."
```



# Intent-Coverage + Severity-Tagged Reviews — Findings

## TL;DR

A reference project's CI does two things we want:

1. **Intent-Coverage review** — a single PR-conversation comment that says
   `### Codex Intent Review: \`PASS\`` (or `WARN` / `FAIL`), followed by an
   `Item | Status | Evidence` table and a short notes section. Posted **once**
   per PR; on every push it is **PATCHed in place** (same comment, edited
   contents) using a hidden HTML-comment marker for lookup. Never spams.

2. **Severity-tagged inline review comments** — each finding renders as
   `🟠 **High** - <body>` then a trailing italic
   `*Automated review by Codex (advisory PR review).*` footer. Anchored to a
   specific file+line on the diff. The color emoji + bold severity makes the
   list parseable at a glance.

Quest already has a sophisticated inline-review system (`codex-ci-review.yml`
+ `codex_review.py` + Deep CI). PR #101 added a canonical
`/tmp/deep_ci_context_manifest.json` artifact for Deep CI selection,
chunking, budgets, and omission reasons. It still does **not** have:

- An intent / acceptance-coverage summary surface.
- Color emojis on severity.
- An update-in-place comment for any PR-conversation surface.

This document proposes additive workflows + minimal touch-ups. Existing
inline-review behaviour, dedup, fallback, security guard, and severity schema
all stay untouched.

---

## What we want to copy

### Pattern A — Intent-Coverage upsert comment

The reference workflow runs a non-blocking advisory job that:

1. Pulls the PR title + body and the full unified diff.
2. Sends both to a model with a system prompt that asks: "does what the diff
   actually changes match what the PR description says it changes?"
3. Asks the model to return a single JSON object:

   ```json
   {
     "status": "pass|warn|fail",
     "summary": "short summary",
     "coverage": [
       { "item": "intent or acceptance criterion",
         "status": "implemented|partial|missing|unclear",
         "evidence": "brief evidence from the diff" }
     ],
     "scope_creep": ["brief item"],
     "missing_items": ["brief item"],
     "notes": ["optional brief note"]
   }
   ```

4. Renders that JSON to a markdown block with a fixed marker as the first
   line, then **upserts** it on the PR.

Comment body shape (verbatim, with the marker):

```markdown
<!-- quest-codex-intent-check -->
### Codex Intent Review: `PASS`

<one-paragraph summary>

**Intent Coverage**
| Item | Status | Evidence |
| --- | --- | --- |
| Guarded release workflow | `implemented` | new release workflow added with separate jobs ... |
| Version-sync validator   | `implemented` | new validator script + unit tests |
| ... | ... | ... |

**Missing or Partial Items**
- ...

**Potential Scope Creep**
- ...

**Notes**
- ...

_Automated review by Codex focused on declared PR intent and acceptance coverage._
```

The marker `<!-- quest-codex-intent-check -->` is invisible in GitHub's
rendered UI but lets the helper script find the existing comment on the
next push and PATCH it instead of POSTing a new one.

#### The upsert logic (this is the key trick)

Lookup pattern, in pseudocode then real Python:

```text
- list all PR conversation comments via `GET /repos/{R}/issues/{N}/comments` (paginated)
- jq filter: `.[] | select(.user.login == "github-actions[bot]" and (.body | startswith("<!-- quest-codex-intent-check -->"))) | .id`
- if found  → PATCH /repos/{R}/issues/comments/{id}   with new body
- if absent → POST  /repos/{R}/issues/{N}/comments    with new body
```

```python
MARKER = "<!-- quest-codex-intent-check -->"

def upsert_intent_comment(repo: str, pr_number: int, body: str) -> bool:
    existing = subprocess.run(
        ["gh", "api", "--paginate",
         f"repos/{repo}/issues/{pr_number}/comments",
         "--jq", f'.[] | select(.user.login == "github-actions[bot]" and (.body | startswith("{MARKER}"))) | .id'],
        capture_output=True, text=True, check=False,
    )
    comment_id = next(
        (line.strip() for line in existing.stdout.splitlines() if line.strip()),
        "",
    )

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fh:
        json.dump({"body": body}, fh)
        payload_path = fh.name
    try:
        if comment_id:
            result = subprocess.run(
                ["gh", "api", "-X", "PATCH",
                 f"repos/{repo}/issues/comments/{comment_id}",
                 "--input", payload_path],
                capture_output=True, text=True, check=False,
            )
        else:
            result = subprocess.run(
                ["gh", "api", "-X", "POST",
                 f"repos/{repo}/issues/{pr_number}/comments",
                 "--input", payload_path],
                capture_output=True, text=True, check=False,
            )
    finally:
        Path(payload_path).unlink(missing_ok=True)
    return result.returncode == 0
```

Key properties to preserve when porting:

- The marker is **the first line** of the rendered comment body — so the
  `startswith(...)` filter is exact and cheap.
- The marker is project-scoped (`quest-` prefix) so it never collides with
  comments left by other automation in shared accounts.
- Lookup should also constrain on bot author, so a human copy-paste or
  edited comment cannot hijack the upsert target.
- Body is uploaded via a temp-file `--input` (NOT positional `-f body=...`),
  to dodge shell-quoting / size limits / interpolation traps.
- Status surfaces as a backtick code-span inside an `### H3` heading. No
  shield SVG, no third-party badge — keeps the comment portable and renders
  identically dark/light.
- Status enum is `pass | warn | fail`, uppercased for display.
- The `coverage[].status` enum values (`implemented | partial | missing |
  unclear`) are also rendered as backtick code-spans — same visual treatment
  the Status column shows.

#### Triggers and gating

```yaml
on:
  pull_request:
    types: [opened, edited, reopened, ready_for_review, synchronize]

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: codex-intent-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  intent-review:
    name: "advisory: intent-review"
    if: >-
      github.event.pull_request.draft == false &&
      github.event.pull_request.user.login == 'KjellKod' &&
      github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    environment: codex-intent-review
    timeout-minutes: 10
```

Notes:

- The job name is prefixed `advisory:` so reviewers and branch-protection
  rules can recognise it as non-blocking.
- `cancel-in-progress: true` per-PR concurrency means rapid pushes don't
  queue up multiple model calls — only the latest commit's review runs.
- Same trusted-author gate + same checkout-base-not-head + same-repo gate +
  environment-secret pattern Quest's `codex-ci-review.yml` already uses.
  (`security_ci_guard.py` will enforce this on us anyway.)
- `continue-on-error: true` on the model step + `if: always()` on the
  process step → the lane never blocks merge even if the model fails.

#### Failure modes after the job starts

Once the job passes its top-level gates, the helper should still upsert a
degraded comment for runtime failures instead of failing silently:

| Skip / failure reason  | Status surfaced |
|------------------------|-----------------|
| `missing_openai_key`   | `warn`          |
| `prepare_failure`      | `warn`          |
| `parse_failure`        | `warn`          |
| `missing_output`       | `warn`          |

Draft PRs and fork PRs are better treated as clean job-level skips, matching
Quest's current advisory workflow pattern and GitHub token constraints.

When the model returns malformed JSON, a lenient parser is tried before
giving up:

```python
def load_json_lenient(raw: str) -> Any:
    raw = raw.strip()
    # 1. raw parse
    try: return json.loads(raw)
    except json.JSONDecodeError: pass
    # 2. strip ```json fences
    fenced = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try: return json.loads(fenced)
    except json.JSONDecodeError: pass
    # 3. extract first fenced block
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass
    raise ValueError("Could not parse model output as JSON")
```

This is the same parse-fallback shape `codex_review.py::parse_review_output`
already implements, but not the same return type. For intent review we should
reuse the strategy, not the helper verbatim, because the existing function only
returns JSON arrays.

---

### Pattern B — Severity-tagged inline review comments

The reference repo posts each finding as its own inline review comment via
`POST /repos/{owner}/{repo}/pulls/{number}/comments` (the **individual
review-comment** endpoint, not the batched-review endpoint). Body shape:

```
🟠 **High** - $${{ github.ref_name }} is interpolated directly inside the
shell script (`echo` lines). In a double-quoted string back-ticks are still
evaluated, so a tag like `v1.0.0\ whoami\`` would run on the runner. Export
the ref through env (e.g. RELEASE_TAG: $${{ github.ref_name }}) and
reference $RELEASE_TAG instead to eliminate this injection vector.

*Automated review by Codex (advisory PR review).*
```

Three things make this readable:

1. **Color emoji prefix** — instant severity sort.
2. **Bold severity label** — `**High**` / `**Critical**` etc.
3. **Italic footer** — every bot comment ends with the same one-liner so
   humans can tell bot from human at a glance.

Severity → emoji map used by the reference:

```python
SEVERITY_ORDER = ("critical", "high", "medium", "low", "praise")
SEVERITY_EMOJI = {
    "critical": "\U0001f534",  # 🔴
    "high":     "\U0001f7e0",  # 🟠
    "medium":   "\U0001f7e1",  # 🟡
    "low":      "\U0001f535",  # 🔵
    "praise":   "\U0001f7e2",  # 🟢
}
```

Body builder (idempotent — won't double-prefix if model already added
markup):

```python
def format_inline_body(severity: str, body: str) -> str:
    label = severity.capitalize()
    rendered = body.strip()
    if not rendered.startswith("**"):
        rendered = f"**{label}** - {rendered}"
    if "Automated review by Codex" not in rendered:
        rendered = f"{rendered}\n\n*Automated review by Codex (advisory PR review).*"
    return rendered

# at post time:
emoji = SEVERITY_EMOJI.get(finding["severity"], "")
body  = format_inline_body(finding["severity"], finding["body"])
body  = f"{emoji} {body}" if emoji else body
```

Note the order: bold-prefix and footer are added in `format_inline_body`,
emoji is prepended at post time. The model itself never has to know about
emojis — the script owns presentation.

#### What the model returns

A JSON array, one element per finding:

```json
{
  "path": "src/example.py",
  "line": 147,
  "side": "RIGHT",
  "severity": "critical|high|medium|low|praise",
  "body": "<prose, no emoji, no bold prefix, no footer>"
}
```

Lines reference **absolute file line numbers at the head SHA** with
`side: "LEFT"|"RIGHT"`. GitHub accepts that form on the new
`pulls/{n}/comments` API — no diff-position arithmetic required. If the
line isn't on the diff, GitHub returns a 422; the script counts the failed
post and moves on.

#### Posting endpoint

```bash
gh api -X POST \
  repos/${REPO}/pulls/${PR_NUMBER}/comments \
  --input <tempfile.json>     # {body, commit_id, path, line, side}
```

This is **already what `codex_review.py::post_comments` does** today. The
only change to adopt Pattern B is: prepend the emoji and apply the
bold-label format string before the body goes into the temp file.

#### Idempotency (already in Quest)

The reference repo dedupes new findings against the pre-fetched
`existing_comments.json` snapshot of inline review comments — same logic
Quest already has in `codex_review.py::is_duplicate` /
`build_dedup_state`. No marker on inline comments, no PATCHing — just
"don't re-post anything already there or already replied to." Quest's
existing dedup is, if anything, slightly better (resolved-thread + 40%
keyword overlap). **Keep ours; no change needed for Pattern B's
idempotency.**

---

## Where Quest is today

Existing PR-comment surfaces (post-research inventory):

| Surface                | Mechanism                                                               | Update vs. fresh | When fired                                        |
|------------------------|-------------------------------------------------------------------------|------------------|---------------------------------------------------|
| Inline review comments | `POST /repos/.../pulls/{n}/comments`, one POST per finding              | Always fresh     | Codex review job; deduped against existing posts  |
| Fallback PR review     | `POST /repos/.../pulls/{n}/reviews` with `event: COMMENT`               | Always fresh     | Only when *every* inline post fails               |
| PR-body gate           | No comment — uses `core.setFailed()` to mark check failed               | N/A              | Missing required Summary / Changes / Validation heading variants |

What we **don't** have:

- ❌ Any `POST /repos/.../issues/{n}/comments` PR-conversation summary.
- ❌ Any PATCH-in-place upsert pattern.
- ❌ Any color emoji on severity (proposed in
  `ideas/codex-review-severity-emoji.md`, not implemented).
- ❌ Any intent/acceptance-coverage extraction or grading.

Severity vocab today (from `codex_review.py::VALID_SEVERITIES`):
`{"blocker", "must-fix", "should-fix"}`. Three levels, all via prompt
guidance + JSON `severity` field. The bold label (`**Blocker**` etc.) is
already produced by the model — emoji prefix is the only missing visual
layer.

Roadmap docs and shipped work that this plugs into:

- `ideas/deep-ci-review-context-manifest-plan.md` / PR #101 — Phase 3.2
  shipped the canonical Deep CI review-context manifest. This proposal should
  treat that manifest as existing infrastructure and should not add a second
  context artifact.
- `ideas/archive/2026-04-13-review-intelligence-canonical.md` — Section 3
  describes a future `review-coverage` job mapping acceptance criteria to
  test/validation evidence. Intent-coverage is the lighter cousin of that
  proposal and can ship first as an advisory lane.
- `ideas/codex-review-severity-emoji.md` — already proposes a 5-level
  emoji scale (critical/high/medium/low/praise). Decision needed:
  reconcile with the current 3-level taxonomy or extend it.

---

## Non-breaking integration plan

Two strict invariants from the user request:

> **Inline comments stay inline.** Only the intent review lives in the PR
> conversation, and that one updates in place.
> **Don't break existing CI.** Add to it.

That maps to two independent changes:

### Change 1 — New advisory workflow: intent review

Net new files. Nothing existing is touched.

```
.github/workflows/intent-review.yml         (new)
.github/scripts/intent_review.py            (new)
.github/intent-review-prompt.md             (new)
tests/unit/test_intent_review.py            (new)
```

`intent-review.yml` mirrors the security posture of `codex-ci-review.yml`
exactly — identical permissions, environment gate, author/same-repo gate,
base-SHA checkout — so `security_ci_guard.py` accepts it without changes.
The job is named `advisory: intent-review`. It does require the same
trusted-author gate (`user.login == 'KjellKod'`) as long as it remains a
secret-bearing PR workflow. If we later want intent reviews on collaborator
PRs, that requires either a `security_ci_guard.py` policy change or a
different non-secret-bearing design.

`intent_review.py` is a small (~250-line) script with three sub-commands
mirroring the existing pattern in `codex_review.py`:

- `prepare`: writes diff + PR description to `/tmp/intent-review/*` and
  interpolates `intent-review-prompt.md`. It should not create another Deep
  CI context manifest; PR #101 already made that artifact canonical.
- `process`: parses Codex's JSON output (lenient), renders to markdown
  with the marker, calls `upsert_intent_comment`. Handles all skip /
  failure cases by writing a degraded `warn` payload and still upserting.
- `summarize`: emits `::warning::` if the upsert failed; always exits 0.

Open decision points (**default in bold**):

- Marker string: **`<!-- quest-codex-intent-check -->`** (project-scoped).
- Status enum: **`pass | warn | fail`** (simple 3-state display model).
- Required PR-body sections: the reference relies on the existing
  `pr-body-gate.yml` requiring Summary / Changes / Validation headings.
  **Quest's existing `pr-body-gate.yml` already enforces accepted variants
  of those headings.** No change to that workflow.
- Whether to also extract a `## Acceptance` section: not strictly
  required — the model handles free-form intent extraction from the whole
  body. **Don't add another required section yet.**
- Should the lane ever be made blocking? **No, not in v1.** Advisory only.
  Phase 3 of the review-intelligence canonical roadmap can promote it
  later if the signal is reliable.

### Change 2 — Add severity emoji to existing inline reviews

This is a 1-file, ~15-line surgical change to `.github/scripts/codex_review.py`.

#### 2a. Add the emoji map and a body formatter (top of file, near `VALID_SEVERITIES`):

```python
SEVERITY_EMOJI = {
    "blocker":    "\U0001f534",  # 🔴
    "must-fix":   "\U0001f7e0",  # 🟠
    "should-fix": "\U0001f7e1",  # 🟡
}

ADVISORY_FOOTER = "*Automated review by Codex (advisory PR review).*"

def format_inline_body(severity: str | None, body: str) -> str:
    """Idempotently prepend severity label/emoji and append advisory footer."""
    rendered = body.strip()
    if severity:
        label = severity.replace("-", " ").title()  # "must-fix" -> "Must Fix"
        if not rendered.startswith("**"):
            rendered = f"**{label}** - {rendered}"
    if "Automated review by Codex" not in rendered:
        rendered = f"{rendered}\n\n{ADVISORY_FOOTER}"
    if severity:
        emoji = SEVERITY_EMOJI.get(severity, "")
        if emoji and not rendered.startswith(emoji):
            rendered = f"{emoji} {rendered}"
    return rendered
```

#### 2b. Use it in `post_comments` just before the temp-file write:

```python
# inside post_comments, before json.dump({"body": body, ...})
body = format_inline_body(comment.get("severity"), comment["body"])
```

Why this is non-breaking:

- The model output schema doesn't change.
- `VALID_SEVERITIES` doesn't change. Findings without a severity still get
  posted (just without an emoji prefix — same as today).
- `is_valid_comment` still strips bad severities before they reach the
  formatter.
- New-comment dedup keywords are extracted from the **model's** body before
  we wrap it, and existing-comment keywords are extracted from posted text
  with a regex that ignores emoji. That keeps the fuzzy-overlap path stable.
  (Verify in tests — we already have `test_codex_review.py` to cover this.)
- The advisory footer gets added once and only once thanks to the
  `"Automated review by Codex" not in rendered` guard, so re-runs over
  the same finding produce the same body and the dedup catches it.

#### 2c. Optional: add a 4th level for `nit` / `praise`

Only if we want them. Today Quest has 3 severities. The reference has 5
(adds `praise` 🟢 and a `low` 🔵). We can keep our 3 for now and grow
later — the formatter handles unknown severities by skipping the emoji.
**Recommendation: ship with 3, evaluate need for `nit` / `praise` after
two weeks of usage.**

---

## Test plan

### Intent review (new)

`tests/unit/test_intent_review.py`:

- `test_render_comment_pass` — golden-file check on a known JSON →
  expected markdown table.
- `test_render_comment_warn_with_missing_items`.
- `test_render_comment_fail_with_scope_creep`.
- `test_marker_first_line` — every rendered body starts with the marker.
- `test_pipe_chars_escaped` — items/evidence containing `|` are rendered
  as `\|`.
- `test_lenient_json_strips_fences` — model output wrapped in
  ` ```json ` blocks parses cleanly.
- `test_upsert_calls_patch_when_id_found` — mock `subprocess.run`,
  verify PATCH path.
- `test_upsert_calls_post_when_no_id` — mock `subprocess.run`, verify
  POST path.
- `test_upsert_ignores_human_marker_comment` — lookup only patches the
  bot-authored marker comment.
- `test_skip_reason_renders_warn_payload` — missing_key / prepare_failure /
  parse_failure / missing_output all produce a `warn` comment that still
  upserts.

### Severity emoji (existing)

Add to `tests/unit/test_codex_review.py`:

- `test_format_inline_body_prefixes_emoji` — each severity → expected
  emoji.
- `test_format_inline_body_unknown_severity_no_emoji` — unknown
  severity returns body unchanged except for footer.
- `test_format_inline_body_idempotent` — calling twice yields the same
  body (no double-emoji, no double-footer, no double-bold).
- `test_dedup_unaffected_by_emoji_prefix` — fuzzy-overlap match still
  hits when comparing pre-formatted vs. existing comments.

### Smoke / manual (post-merge)

1. Open a PR with a clear `## Summary / ## Changes / ## Validation`
   body. Confirm:
   - `pr-body-gate` passes.
   - `advisory: intent-review` posts a single conversation comment with
     the marker.
   - `advisory: codex-ci-review` posts inline comments now prefixed with
     `🔴 **Blocker** - ...` / `🟠 **Must Fix** - ...` / `🟡 **Should Fix**
     - ...`.
2. Push another commit. Confirm the intent-review comment is **edited in
   place** (same comment id), not re-posted.
3. Force-push or rebase the PR branch. Confirm the same intent-review
   conversation comment is updated in place; issue comments survive
   force-pushes.
4. Retarget the PR to a different base branch or substantially edit the PR
   body. Confirm `intent-review.yml` reruns and rewrites the same comment
   against the new diff/intended scope.
5. Open a draft PR. Confirm both advisory lanes skip cleanly with no
   intent-review comment and no inline review.
6. Open a fork PR. Confirm both advisory lanes skip cleanly; no intent
   comment should be expected under the current same-repo / secret-bearing
   design.
7. Delete the marker comment manually. Push another commit. Confirm the
   next run creates one fresh conversation comment.

---

## Compatibility checklist

- [x] No change to existing inline-review behaviour (Pattern B is purely
      additive presentation).
- [x] No change to dedup logic; severity prefix doesn't break fuzzy
      matching because keywords come from the model body, not the
      formatted body.
- [x] No change to `pr-body-gate.yml`. Existing required headings stay.
- [x] No change to `security.yml`, `test-python.yml`,
      `validate-quest-config.yml`, `deploy-dashboard.yml`.
- [x] New `intent-review.yml` honours every guard in
      `security_ci_guard.py` (permissions block, environment gate,
      trusted-author gate, same-repo gate, base-SHA checkout, no broad
      writes).
- [x] No new required CI checks. `advisory: intent-review` is advisory
      only and not added to branch protection.
- [x] Severity vocab kept at 3 levels for now (`blocker` / `must-fix` /
      `should-fix`); emoji map mirrors the same keys.
- [x] Marker string is project-scoped (`quest-` prefix) so it never
      collides with any other automation.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Model returns malformed JSON, comment never appears | Lenient parser + degraded `warn` comment with reason field. Always upsert something. |
| Two intent-review runs race and both POST a fresh comment | Per-PR concurrency group with `cancel-in-progress: true` reduces this sharply, but it does not make duplicate POSTs impossible if two runs both observe "no existing comment" before either writes. Bot-author filtering keeps later updates targeted; duplicate cleanup may still be needed in the rare race case. |
| Marker collides with an unrelated comment (manual or another bot) | Marker is project-namespaced (`quest-codex-intent-check`), lookup should key on bot author, and `startswith()` narrows the match to the marker line rather than any substring hit. |
| Human edits or deletes the marker line | If the marker is removed, the next run will POST a new comment instead of PATCHing. This is acceptable, but it should be called out in docs/tests so the behavior is unsurprising. |
| PR is force-pushed or retargeted to a different base | GitHub PR conversation comments persist across force-pushes, so the same comment can be PATCHed. Retargeting should trigger a rerun via pull-request events and replace the content against the new base/diff. |
| Emoji prefix breaks accessibility / screen readers | Bold label still present (`**Must Fix**`); emoji is decorative pre-text; severity also encoded structurally in the JSON `severity` field. |
| Cost — every PR push fires a model call | Same OpenAI key + environment gate as existing `codex-ci-review`; concurrency cancels superseded runs; trusted-author gate constrains who triggers it. |
| Branch protection accidentally requires `advisory: intent-review` | Document explicitly in the workflow file's job comment that the lane is non-blocking; `advisory:` prefix on job name signals the same. |
| Existing `codex-ci-review` tests fail because output bodies changed | Update fixture expectations once; `format_inline_body` is idempotent so golden-file format is stable. |

---

## What we're explicitly NOT doing in v1

- Not promoting intent-review to a blocking lane.
- Not extracting a structured `## Acceptance` section from the PR body.
- Not adding `praise` / `nit` / `info` severities.
- Not implementing the `review-coverage` job from the canonical roadmap
  (intent-coverage is the lightweight precursor, not a replacement).
- Not changing the existing PR-body required headings.
- Not adding or redesigning a context-manifest artifact for Deep CI. PR #101
  already shipped Phase 3.2's canonical manifest.

---

## Open decision points (one-liners for the maintainer)

1. **Trusted-author gate on intent review?** Default: yes, mirror
   `codex-ci-review`. Relax later only with a guard-policy change or a
   non-secret-bearing design.
2. **Marker string?** Default: `<!-- quest-codex-intent-check -->`.
3. **Severity emoji set — 3 or 5 levels?** Default: 3, matching current
   `VALID_SEVERITIES`.
4. **Environment name for the new workflow?** Default:
   `codex-intent-review` (separate from `codex-ci-review` so secret
   scopes can differ).
5. **Should `intent-review.yml` reuse the existing `OPENAI_API_KEY`
   secret or have its own?** Default: reuse — same key, different
   environment scope.
6. **Model + effort?** Default: same effort tier as the current advisory
   lane, with the exact model kept configurable — intent-review reads diff
   + body, ~10K-50K tokens; cost acceptable.

---

## Concrete deliverables (when this gets implemented)

```
.github/workflows/intent-review.yml          NEW
.github/scripts/intent_review.py             NEW (~250 LOC)
.github/intent-review-prompt.md              NEW
.github/scripts/codex_review.py              EDIT (~15 LOC: emoji map + format_inline_body + 1-line call site)
tests/unit/test_intent_review.py             NEW
tests/unit/test_codex_review.py              EDIT (5 new tests)
docs/architecture/ci-review-surfaces.md      NEW or EDIT (one-page diagram of the three surfaces)
ideas/codex-review-severity-emoji.md         UPDATE → mark "implemented (3-level)"
ideas/archive/2026-04-13-review-intelligence-canonical.md  UPDATE → cross-link intent-review as Phase-3 prelude
```

Suggested rollout order (smallest blast radius first):

1. Land Change 2 (severity emoji) on its own. Tiny, reversible, immediate
   readability win on existing reviews.
2. Land Change 1 (intent-review workflow) as a separate PR. Watch one
   week of advisory output. If signal-to-noise is good, link it in
   `AGENTS.md` as a standard surface.

End of findings.
