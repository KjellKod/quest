# Deep CI Chunked Context Plan

Status: proposed
Date: 2026-04-21

## Problem

The current Deep CI whole-file review is safe but too binary:

- eligible small files are included as full PR-head snapshots
- oversized files are omitted entirely

The live validation against PR #97 showed the weakness: Deep CI selected two relevant Python files, but both exceeded the default `20000` character per-file cap, so the whole-file pass contributed no code context for those files. The raw GitHub metadata and raw PR-head content fetch boundaries worked; the useful context budget strategy is the weak point.

## Recommendation

Implement a chunked fallback for oversized Deep CI files.

Keep the current full-file behavior for files under the cap. For files over the cap, include bounded chunks around changed RIGHT-side diff lines, expanded by a fixed context window and merged when ranges overlap.

This gives the reviewer enough surrounding code to reason about lifecycle, initialization, fallback paths, and invariants without dumping a whole large file into the prompt.

## Research Notes

Relevant external inputs:

- GitHub Agentic Workflows emphasizes repository automation in GitHub Actions with guardrails: read-only agent tokens, no secrets in the agent process, safe structured outputs, and a separate scoped write job. Source: https://github.github.com/gh-aw/
- InfoQ's February 18, 2026 coverage highlights that agentic repository workflows should augment deterministic CI/CD, use Actions permissions and auditability, and keep humans in the loop for approval decisions. Source: https://www.infoq.com/news/2026/02/github-agentic-workflows/
- Baz's code review agent write-up argues that plain git diffs are insufficient for AI review because they lack surrounding syntax, structure, and dependency context. It points toward syntax-aware diffing and parsing as later improvements, while preserving token budget. Source: https://baz.co/resources/building-an-ai-code-review-agent-advanced-diffing-parsing-and-agentic-workflows
- Emergent Mind's agentic PR overview summarizes that agentic PRs have distinct structure and review dynamics, and that adoption needs automated governance and quality controls. Source: https://www.emergentmind.com/topics/agentic-pull-requests-prs
- The arXiv empirical study of agentic coding PRs reports that agent-authored PRs are commonly used for refactoring, documentation, and testing, and still benefit from human oversight for correctness, maintainability, and project-specific standards. Source: https://arxiv.org/html/2509.14745v1

Implementation implication: Deep CI should stay deterministic, reviewable, and human-governed. It should provide better context, not more autonomy.

## Design Principles

1. Keep trusted-base execution.
   The workflow should continue running review code from the trusted base checkout. PR-head files are data, not executable code.

2. Keep output bounded.
   Every chunking decision must be controlled by explicit constants: max files, max chunks per file, context lines, per-chunk chars, and total chars.

3. Prefer semantic proximity over arbitrary byte chunks.
   The first version should chunk by changed diff lines plus surrounding line windows. Later versions can add syntax-aware expansion.

4. Preserve changed-line anchoring.
   Deep CI findings must still point to exact RIGHT-side changed lines from the diff. Context chunks are evidence, not permission to comment on unchanged lines.

5. Make omissions explicit.
   If a file or chunk is omitted due to caps, the prompt should say why and what was omitted.

## Proposed Behavior

For each selected Deep CI candidate:

1. Fetch PR-head file content.
2. If content length is `<= DEEP_CI_MAX_FILE_CHARS`, render the full file as today.
3. If content length is greater than `DEEP_CI_MAX_FILE_CHARS`:
   - parse `/tmp/pr.diff`
   - collect changed RIGHT-side line ranges for that path
   - expand each range by `DEEP_CI_CHUNK_CONTEXT_LINES`
   - merge overlapping or adjacent windows
   - cap to `DEEP_CI_MAX_CHUNKS_PER_FILE`
   - render only those chunks
   - record full file size, total line count, selected ranges, and omitted remainder
4. If the total Deep CI budget would be exceeded:
   - include as many chunks as fit
   - emit a structured omission note for the rest

## New Constants

Add to `.github/scripts/codex_review.py`:

```python
DEEP_CI_MAX_FILE_CHARS = 20000
DEEP_CI_MAX_TOTAL_CHARS = 60000
DEEP_CI_MAX_FILES = 3
DEEP_CI_CHUNK_CONTEXT_LINES = 100
DEEP_CI_MAX_CHUNKS_PER_FILE = 4
DEEP_CI_MAX_CHUNK_CHARS = 12000
DEEP_CI_MAX_FETCH_CHARS = 200000
```

Notes:

- `DEEP_CI_MAX_FILE_CHARS` remains the full-file threshold.
- `DEEP_CI_MAX_FETCH_CHARS` is a hard safety cap. Files above it are skipped rather than fetched/rendered further.
- `DEEP_CI_MAX_CHUNK_CHARS` prevents a single dense window from consuming the budget.
- The existing total budget stays authoritative.

## Data Model

Use one snapshot shape for full, chunked, and skipped files:

```python
{
    "path": "src/app.py",
    "mode": "full" | "chunked" | "skipped",
    "content": "...",              # full mode only
    "chunks": [                    # chunked mode only
        {
            "start_line": 120,
            "end_line": 260,
            "changed_lines": [188, 189, 204],
            "content": "..."
        }
    ],
    "char_count": 48120,
    "line_count": 1300,
    "omitted": False,
    "reason": ""
}
```

Skipped example:

```python
{
    "path": "src/generated.py",
    "mode": "skipped",
    "content": "",
    "chunks": [],
    "char_count": 250000,
    "line_count": 9000,
    "omitted": True,
    "reason": "file exceeds Deep CI hard fetch cap of 200000 chars"
}
```

## Diff Parsing Algorithm

Add a stdlib-only parser for unified diff text:

```python
def parse_changed_line_ranges(diff_text):
    """Return {path: [(start_line, end_line), ...]} for RIGHT-side additions."""
```

Rules:

- Track current file from `+++ b/<path>`.
- Ignore `+++ /dev/null`.
- Parse hunk headers like `@@ -12,6 +20,9 @@`.
- Track RIGHT-side line number.
- For lines starting with `+` but not `+++`, record the current RIGHT-side line and increment.
- For context lines, increment RIGHT-side line.
- For deletion lines, do not increment RIGHT-side line.
- Collapse consecutive added lines into ranges.

Example:

```diff
@@ -10,6 +10,8 @@
 context
+new line 11
+new line 12
 old context
```

Produces:

```python
{"path/to/file.py": [(11, 12)]}
```

## Chunk Window Algorithm

Add:

```python
def build_line_windows(changed_ranges, line_count, context_lines, max_chunks):
    """Expand changed ranges, merge overlaps, and cap the number of windows."""
```

Rules:

- Expand each range to:
  - `start = max(1, changed_start - context_lines)`
  - `end = min(line_count, changed_end + context_lines)`
- Sort by start line.
- Merge windows when `next.start <= current.end + 1`.
- If more than `max_chunks`, keep the windows containing the most changed lines first, then restore file order for rendering.
- Preserve original `changed_lines` inside each chunk.

## Rendering Format

Full file:

````markdown
## src/app.py
Mode: full-file
Size: 18420 chars, 620 lines
```python
...
```
````

Chunked file:

````markdown
## src/app.py
Mode: chunked-large-file
Size: 48120 chars, 1300 lines
Included chunks: 2
Included line ranges: 80-260, 700-860
Omitted: full file exceeded 20000 chars; only changed-line windows are included.

### src/app.py lines 80-260
Changed RIGHT-side lines in this chunk: 188, 189, 204
```python
...
```

### src/app.py lines 700-860
Changed RIGHT-side lines in this chunk: 742
```python
...
```
````

Skipped file:

```markdown
## src/huge.py
Mode: skipped
Skipped Deep CI review for src/huge.py because file exceeds Deep CI hard fetch cap of 200000 chars.
```

Use the existing dynamic markdown fence helper for each full file or chunk.

## Prompt Changes

Update `.github/codex-review-prompt.md` Deep CI section:

- State that Deep CI may provide full files or changed-line chunks.
- Tell the reviewer that chunked context is partial and should be used only to reason about changed-line behavior.
- Preserve the rule: findings must point to exact RIGHT-side changed lines from the diff.
- Tell the reviewer to avoid findings that depend on omitted code unless the diff alone proves the issue.

Suggested wording:

```markdown
Deep CI context may include either full changed files or bounded chunks around changed lines for oversized files. Chunked files are partial views. Use them to reason about the behavior of changed lines and nearby logic, but do not infer issues that require omitted code unless the diff itself proves the problem.
```

## Workflow Changes

Keep the current workflow shape:

- `gh pr diff ... > /tmp/pr.diff`
- `gh pr view ... --json files > /tmp/changed_files_payload.json`
- `jq -r '.files[].path' ... > /tmp/changed_files.txt`
- `jq '.files' ... > /tmp/changed_files.json`
- `python3 .github/scripts/codex_review.py gather-context`

No workflow split is required for the first chunking pass.

Optional later split:

1. `prepare-review-context`
   - read-only
   - builds context chunks and emits artifacts
2. `review`
   - read-only
   - reviews one or more chunks
3. `publish-review`
   - pull-requests write
   - validates review output and posts comments

That split is useful if prompt size or latency grows, but it is not necessary to fix oversized-file omissions.

## Implementation Steps

### Step 1: Add Diff Parsing

Files:

- `.github/scripts/codex_review.py`
- `tests/unit/test_codex_review.py`

Add:

- `parse_changed_line_ranges(diff_text)`
- unit tests for additions, deletions, multiple hunks, renamed paths if supported by GitHub diff output

### Step 2: Add Chunk Window Selection

Files:

- `.github/scripts/codex_review.py`
- `tests/unit/test_codex_review.py`

Add:

- `build_line_windows(...)`
- `extract_line_chunk(content, start_line, end_line)`
- tests for overlapping windows, max chunk cap, start/end boundaries

### Step 3: Extend Deep CI Fetching

Change:

```python
fetch_deep_ci_files(repo, head_sha, selected_files, ...)
```

to accept diff ranges:

```python
fetch_deep_ci_files(
    repo,
    head_sha,
    selected_files,
    changed_line_ranges=None,
    max_chars_per_file=DEEP_CI_MAX_FILE_CHARS,
    max_total_chars=DEEP_CI_MAX_TOTAL_CHARS,
)
```

Behavior:

- full mode for files under `max_chars_per_file`
- chunked mode for oversized files under hard fetch cap when changed ranges exist
- skipped mode for files over hard fetch cap or without usable ranges

### Step 4: Update `gather_context()`

Read `/tmp/pr.diff`:

```python
diff_text = Path("/tmp/pr.diff").read_text(encoding="utf-8")
changed_line_ranges = parse_changed_line_ranges(diff_text)
deep_ci_snapshots = fetch_deep_ci_files(
    repo,
    head_sha,
    selected_deep_ci_files,
    changed_line_ranges=changed_line_ranges,
)
```

### Step 5: Update Rendering

Extend `render_deep_ci_context()` to render `full`, `chunked`, and `skipped` modes.

Keep a stable, machine-scannable header for each file:

```markdown
Mode: full-file
Mode: chunked-large-file
Mode: skipped
```

### Step 6: Update Prompt

Update `.github/codex-review-prompt.md` to explain chunked partial context and unchanged-line restrictions.

### Step 7: Validate Against Live PR Data

Add an optional local smoke command, not necessarily a CI test:

```bash
gh pr view <PR> --json headRefOid --jq '.headRefOid' > /tmp/pr_head_sha.txt
gh pr view <PR> --json files > /tmp/changed_files_payload.json
jq -r '.files[].path' /tmp/changed_files_payload.json > /tmp/changed_files.txt
jq '.files' /tmp/changed_files_payload.json > /tmp/changed_files.json
gh pr diff <PR> --patch > /tmp/pr.diff
REPO=KjellKod/quest python3 .github/scripts/codex_review.py gather-context
```

Expected:

- `/tmp/deep_ci_files.md` includes `Mode: chunked-large-file` for oversized selected files
- line ranges include changed RIGHT-side lines
- no selected oversized file is skipped solely because it exceeds the full-file threshold

## Tests

Add unit tests for:

1. `parse_changed_line_ranges()` maps additions to RIGHT-side line ranges.
2. Deletions do not create RIGHT-side review targets.
3. Multiple hunks in one file produce multiple ranges.
4. Multiple files produce independent ranges.
5. `build_line_windows()` expands and merges overlapping windows.
6. `build_line_windows()` caps windows deterministically.
7. Oversized fetched file with changed ranges renders `chunked-large-file`.
8. Oversized fetched file without ranges is skipped with a clear reason.
9. Hard fetch cap skips the file.
10. Total char cap can omit later chunks while preserving earlier chunks.
11. Dynamic markdown fence still protects chunks containing backticks.
12. Existing full-file behavior remains unchanged for small files.

## Acceptance Criteria

- Deep CI no longer skips selected oversized files solely because they exceed the full-file cap.
- Oversized files render bounded chunks around changed RIGHT-side lines.
- Chunk windows are deterministic and budgeted.
- The prompt clearly distinguishes full and partial context.
- Review findings remain restricted to changed RIGHT-side lines.
- Existing CI review posting, dedupe, and severity behavior are unchanged.
- Unit tests cover diff parsing, chunk selection, rendering, and cap behavior.
- The workflow keeps trusted-base execution and treats PR-head content as data.

## Risks

### Risk: Chunked context can hide relevant distant code

Mitigation:

- Clearly mark chunked context as partial.
- Keep normal diff review active.
- Later add syntax-aware expansion for functions/classes if needed.

### Risk: Parsing GitHub diff incorrectly maps lines

Mitigation:

- Unit-test hunk parsing thoroughly.
- Keep the final comment rule tied to GitHub's accepted RIGHT-side line numbers.
- If line mapping is missing, omit the Deep CI finding.

### Risk: Prompt size grows too much

Mitigation:

- Use per-file, per-chunk, per-total budgets.
- Emit omission notes rather than exceeding budget.
- Consider matrix chunk review later.

### Risk: Agent over-trusts partial chunks

Mitigation:

- Prompt explicitly says chunked context is partial.
- Findings requiring omitted code must be omitted unless proven by the diff.

## Later Enhancements

1. Syntax-aware chunk expansion
   - For Python, expand to containing function/class using `ast`.
   - For JS/TS, consider external parser only if the repo accepts the dependency and CI setup.

2. Matrix chunk review
   - Prepare context artifacts once.
   - Review chunks independently.
   - Publish validated inline comments in one write-capable job.

3. Context manifest artifact
   - Persist `.codex/deep-ci-context-manifest.json`.
   - Include mode, ranges, omitted reasons, and budget usage.
   - Useful for debugging review quality and explaining omissions.

4. Live PR smoke validation script
   - Add a developer-only script that builds Deep CI context for an existing PR number.
   - Keep it out of required CI unless it can run without secrets and without network flakiness.

## Recommended Next Quest

```text
Implement Deep CI oversized-file chunk fallback.

When a selected Deep CI file exceeds the full-file cap, parse the PR diff to find changed RIGHT-side line ranges, render bounded context chunks around those ranges, and preserve existing full-file behavior for smaller files. Keep the workflow trusted-base, keep PR-head file contents as data only, keep comments restricted to changed RIGHT-side diff lines, and add focused unit tests for diff parsing, chunk windowing, rendering, and cap behavior.
```
