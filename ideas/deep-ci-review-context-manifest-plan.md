# Deep CI Review Context Manifest Plan

## Status: proposed

## Origin

Phase 3 shipped bounded whole-file Deep CI review for selected changed code
files. Phase 3.1 shipped chunk fallback for oversized selected files.

Those phases improved review quality, but the context-preparation logic is
still implicit in runtime code. The workflow knows how context was selected,
trimmed, and omitted, but it does not persist one canonical artifact that
downstream steps can inspect and consume deterministically.

This proposal is Review Intelligence Phase 3.2.

References:

- `ideas/archive/deep-ci-whole-file-logic-review.md`
- `ideas/archive/deep-ci-chunked-context-plan.md`
- `docs/quest-journal/deep-ci-file-review_2026-04-21.md`

## Problem

Deep CI context is now richer, but still hard to reason about operationally:

1. Selection, chunking, and omission decisions happen inside runtime helpers.
2. The final prompt text is the main visible output, but it is not the best
   debugging artifact.
3. When review quality looks odd, it is hard to answer:
   - which files were eligible but dropped?
   - which files were full vs chunked vs skipped?
   - which chunk windows were kept?
   - what budget was consumed?
   - what was omitted, and why?

We already have deterministic context logic. What is missing is a deterministic
context artifact.

## Goal

Persist one canonical Deep CI review-context manifest before prompt assembly,
then make downstream steps consume that manifest instead of recomputing context
ad hoc.

## Non-Goals

- No syntax-aware chunk expansion in this phase.
- No review-policy changes.
- No new memory layer.
- No matrix fan-out review design.
- No broad GitHub Actions redesign beyond what is needed to pass the manifest
  between existing steps.

## Proposal

Add one deterministic "prepare review context" step that produces a machine-
readable manifest artifact.

The prepare step is the only place that decides:

- candidate file eligibility
- selected file subset
- full vs chunked vs skipped mode
- chunk windows and changed-line coverage
- total budget usage
- omission reasons

After that:

- prompt assembly reads the manifest and renders Deep CI markdown from it
- review posting can refer back to the same manifest if needed
- tests assert on the manifest structure directly instead of inferring behavior
  from prompt text alone

## Manifest Artifact

Preferred path:

- `/tmp/deep_ci_context_manifest.json` in CI runtime

Optional later follow-up:

- a repo-local debug copy for developer-only smoke scripts

The CI path is enough for this phase.

## Manifest Shape

Top-level example:

```json
{
  "version": 1,
  "generated_at": "2026-04-24T12:34:56Z",
  "source": {
    "pr_diff_path": "/tmp/pr.diff",
    "changed_files_path": "/tmp/pr_files.json"
  },
  "budget": {
    "max_files": 3,
    "selected_files": 2,
    "max_total_chars": 60000,
    "used_total_chars": 41820,
    "remaining_total_chars": 18180,
    "max_file_chars": 20000,
    "max_fetch_chars": 200000,
    "max_chunks_per_file": 4,
    "max_chunk_chars": 12000,
    "context_lines": 100
  },
  "files": [
    {
      "path": "src/app.py",
      "mode": "full",
      "char_count": 18420,
      "line_count": 620,
      "changed_line_ranges": [[188, 204]],
      "omitted": false,
      "reason": ""
    },
    {
      "path": "src/large.py",
      "mode": "chunked",
      "char_count": 48120,
      "line_count": 1300,
      "changed_line_ranges": [[188, 189], [742, 742]],
      "chunks": [
        {
          "start_line": 80,
          "end_line": 260,
          "changed_lines_included": [188, 189],
          "changed_lines_omitted": []
        },
        {
          "start_line": 700,
          "end_line": 860,
          "changed_lines_included": [742],
          "changed_lines_omitted": []
        }
      ],
      "chunk_cap_omitted_windows": [],
      "total_cap_omitted_windows": [],
      "omitted": false,
      "reason": ""
    }
  ],
  "omitted_candidates": [
    {
      "path": "src/generated.py",
      "mode": "skipped",
      "reason": "excluded-path-segment"
    }
  ]
}
```

## What "Budgets Used" Means

The manifest should explicitly record how much of the Deep CI budget was
consumed by the selected context.

That means:

- file budget:
  - max selected files
  - actual selected files
- total character budget:
  - max total chars
  - used total chars
  - remaining total chars
- per-file / per-chunk limits in effect:
  - full-file char cap
  - hard fetch cap
  - max chunks per file
  - max chars per chunk
  - context lines

This is not a separate optimization system. It is just explicit accounting for
the limits already governing Deep CI behavior.

## Modes

Each selected or considered candidate should have one explicit mode:

- `full`
- `chunked`
- `skipped`

This matters because "selected file" alone is not enough. We need to know what
the reviewer actually saw.

## Omission Reasons

Capture omission reasons in stable machine-readable strings.

Examples:

- `excluded-path-segment`
- `unsupported-extension`
- `deleted-file`
- `metadata-too-large`
- `fetch-too-large`
- `total-cap-exhausted`
- `no-changed-line-ranges`
- `chunk-cap-exhausted`
- `unavailable`

Use short stable identifiers in the manifest. Prompt text can render them in
friendlier prose.

## Integration Shape

Keep the current CI shape:

1. gather changed files and diff
2. prepare Deep CI context manifest
3. build prompt from placeholders + manifest
4. run Codex review
5. post findings

Recommended implementation split:

- add a pure helper that returns the manifest dict
- add a renderer that converts the manifest into the existing markdown section
- keep prompt assembly simple by reading the manifest and rendering markdown
  there, rather than embedding context-building decisions in multiple places

## Acceptance Criteria

1. Deep CI context preparation produces one canonical JSON manifest artifact.
2. The manifest records:
   - selected files
   - per-file mode (`full` / `chunked` / `skipped`)
   - chunk ranges for chunked files
   - budgets used
   - omission reasons
3. Prompt assembly consumes the manifest deterministically.
4. Prompt output remains behaviorally equivalent to the current Deep CI prompt
   for the same prepared context.
5. Focused tests cover:
   - manifest generation for full, chunked, and skipped files
   - budget accounting
   - omission-reason recording
   - markdown rendering from manifest
6. No change to the rule that findings must still point to exact RIGHT-side
   changed lines from the diff.

## Out of Scope

- syntax-aware AST chunk expansion
- additional languages
- prompt-policy redesign
- multiple manifest consumers beyond existing Deep CI prompt assembly
- persisted cross-run coverage memory

## Recommended Quest Prompt

```text
/quest "Implement Review Intelligence Phase 3.2: structured Deep CI review-context manifest.

Reference:
- ideas/deep-ci-review-context-manifest-plan.md
- ideas/archive/deep-ci-chunked-context-plan.md
- ideas/archive/deep-ci-whole-file-logic-review.md

Goal:
Persist one canonical Deep CI context manifest before prompt assembly, then
make downstream review steps consume that manifest deterministically.

Deliverables:
1. Add a deterministic Deep CI prepare step that writes one JSON manifest
   artifact for the current PR review run.
2. The manifest must record:
   - selected files
   - per-file mode (full, chunked, skipped)
   - chunk ranges for chunked files
   - budgets used
   - omission reasons
3. Refactor prompt assembly so Deep CI markdown is rendered from the manifest
   rather than rebuilding context decisions ad hoc.
4. Keep current review semantics:
   - trusted-base execution
   - PR-head files treated as data only
   - findings still anchored to exact RIGHT-side changed lines
5. Add focused tests for:
   - manifest generation
   - budget accounting
   - omission-reason recording
   - prompt rendering from manifest

Out of scope:
- syntax-aware chunk expansion
- review-policy changes
- memory retrieval
- matrix fan-out review
- broad workflow redesign beyond passing the manifest between existing steps."
```
