# Deep CI Whole-File Logic Review

## Status: proposed

## Problem

Current CI review is still too diff-centered.

Even when the prompt says "review correctness" and "check edge cases," the
actual review context and human habits often stay close to the changed lines.
That is good for local patch quality, but it misses a common bug class:

- the diff changes one branch of a function
- the real behavior depends on the whole function or module
- the bug only appears on a create path, first-run path, error path, or later
  lifecycle step that was not directly touched in the diff

Example shape:

- a new invariant is introduced
- the changed branch looks plausible
- another branch in the same file now violates that invariant
- the bug shows up only on the next run or in a path the author did not test

This is not a Quest-specific problem. It is a review-mode problem.

## Goal

Add a **Deep CI** review mode that reasons about the resulting behavior of
changed code by reading the **whole file**, not just the diff hunk.

The purpose is not broader style review. The purpose is better logic review.

## Core Idea

When a PR changes a code file, Deep CI should:

1. read the diff
2. read the full current contents of the changed code file
3. review the changed logic in the context of the whole file
4. ask "how does this file behave now?" instead of only "does this patch line
   look reasonable?"

This should focus on:

- variable lifecycle
- state initialization
- create vs update vs failure paths
- first-run vs later-run behavior
- fallback logic
- values persisted now but consumed later
- invariants introduced by the diff that may be violated elsewhere in the file

## Scope Boundaries

Deep CI should **ignore markdown and prose files**. The target is code logic.

Initial file types:

- `*.py`
- `*.sh`
- `*.js`
- `*.ts`

Maybe later:

- `*.tsx`
- `*.jsx`

Probably exclude in the first version:

- generated files
- vendored assets
- minified bundles
- large lockfiles

## Feasible Operating Model

Do **not** send every changed file on every run if that makes the prompt too
large or slow.

Preferred first model:

- normal CI review still runs on the full diff
- Deep CI takes a **small subset of changed code files** each run
- the subset is chosen deterministically or round-robin
- once a file has been deep-reviewed for a given PR head lineage, do not spend
  another Deep CI slot on it unless that file changes again

This gives broad enough coverage without exploding token use.

## Alternative Operating Models

### Option A: Subset per run

Review only N changed code files deeply on each run.

Pros:

- cheapest
- easiest to ship
- preserves fast CI behavior

Cons:

- a PR with many changed code files may not get full-file review coverage on
  every file

### Option B: One file at a time until complete

Deep CI reviews one changed code file per run and keeps progress state for the
PR until every changed code file has been covered.

Pros:

- predictable full coverage over time
- easier to control prompt size

Cons:

- needs PR-level memory/state
- some files may wait several pushes before getting deep review

### Option C: All changed code files, one by one in one job

Deep CI loops through all changed code files and reviews each whole file.

Pros:

- maximum coverage

Cons:

- expensive
- slower
- more likely to hit context or runtime limits
- higher risk of noisy review volume

## Recommendation

Start with **Option A**:

- diff review remains the default review
- Deep CI adds full-file reasoning for a bounded subset of changed code files
- skip files already deep-reviewed unless they changed again

That is the most feasible balance between quality and cost.

## Review Prompt Shape

Deep CI prompt should explicitly instruct the model:

- do not review markdown, docs, or prose files
- for selected code files, read the **entire file snapshot**
- reason about resulting behavior of the file after the diff
- look for bugs that arise from interaction between changed and unchanged code
- prefer real logic problems over style
- emphasize:
  - used-before-assigned values
  - inconsistent state writes
  - create/update/error-path asymmetry
  - values persisted before validation
  - first-run vs second-run bugs
  - fallback paths that now disagree with the primary path

## Minimum Viable Implementation

1. Add a second review workflow or second pass in the existing review workflow.
2. Filter changed files down to code files only.
3. Select a bounded subset for deep review.
4. Fetch the full current file contents for those files.
5. Build a prompt that includes:
   - PR summary
   - diff
   - full file snapshots for selected code files
   - existing comments/replies for dedupe
6. Post findings inline, same as current review flow.

## Why This Is Worth Trying

This directly targets the class of bug where the patch looks fine locally but
the file-level behavior is wrong.

That is exactly the kind of miss that basic diff review can let through, and it
is one of the highest-value places to spend extra review tokens.
