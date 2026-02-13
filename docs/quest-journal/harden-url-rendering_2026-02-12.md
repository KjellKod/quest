# Quest Journal: Harden URL Rendering

**Quest ID:** `harden-url-rendering_2026-02-12__1522`
**Slug:** harden-url-rendering
**Status:** Completed
**Completed:** 2026-02-12

## Summary

Fixed HTML attribute injection (XSS) vulnerability in the Quest Dashboard's URL rendering. Added `_sanitize_url()` function that validates scheme (HTTPS-only), validates GitHub URL pattern via regex, and applies HTML attribute escaping before any URL is interpolated into `href="..."` attributes. Also escaped fallback relative paths, removed stderr side effect from loaders, and unified the `github_url` missing-value convention.

## What Changed

- **scripts/quest_dashboard/render.py** — Added `_sanitize_url()` with scheme validation, GitHub URL pattern matching, and HTML attribute escaping. Applied to `_compute_journal_link()` and `_compute_pr_link()`. Escaped fallback relative paths with `_escape_html()`.
- **scripts/quest_dashboard/loaders.py** — Removed `print()` to stderr for missing quest_brief.md. Added `github_url = github_url or ""` normalization.
- **tests/unit/test_quest_dashboard_render.py** — Added 5 new tests: XSS regression (double-quote injection, javascript: scheme, single-quote injection), valid URL preservation, and fallback path with malicious filename.
- **tests/unit/test_quest_dashboard_loaders.py** — Added 2 new tests: no stderr output verification, None-to-empty normalization.

## Iterations

**Plan iterations:** 1
**Fix iterations:** 1

## Origin

This quest was driven by `ideas/final-decision-code-review.md`, the arbitration of two independent code reviews (Claude and Codex) of PR #26. The security fix was identified as a merge gate requirement.
