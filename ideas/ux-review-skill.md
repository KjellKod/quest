# Idea: /ux-review skill

**Status:** Draft. Lives in the rough room until the maintainer signs off on the spec.

## What

A Claude Code skill — `/ux-review [target]` — that runs the UX guidebook's stress test against a target (file, directory, URL, deployed app, screenshot) and produces a structured critique report.

The skill is the executable lens that points at [`docs/guides/ux-guidebook.md`](../docs/guides/ux-guidebook.md). The book is the source of truth; the skill is operational.

## Why

The guidebook alone has a problem: it requires the engineer to remember to look at it. A skill that runs on demand (and ideally on PRs touching UI) closes the gap between "we have a standard" and "the standard is applied."

The skill is also the natural way to apply this knowledge to clunky existing projects — point it at a screen, get a triaged punch list back, decide which fixes are worth landing.

## Approach

### Inputs
- `/ux-review` (no target) → review the staged or local-uncommitted UI changes in the current repo.
- `/ux-review <path>` → review a file or directory.
- `/ux-review <url>` → fetch the page, take a screenshot, run the visual checks plus DOM heuristics.
- `/ux-review <image>` → review a screenshot or mockup (no DOM available; visual-only).

### What it does
1. Identify the target's surface area (which screens / components / states).
2. Walk the 15-point red-flags list — flag each hit with `file:line` or screenshot region.
3. Walk the 12-question stress test — note each "no" with evidence.
4. For mobile-relevant code, walk the 20-point mobile-feel pass/fail.
5. For macOS-native code, walk the 15-point Mac-native pass/fail.
6. Group findings by severity (P0 signifier → P1 feedback/traps → P2 consistency → P3 chrome bloat).
7. For each finding: cite the principle ID from the guidebook, name the smallest fix, state the one-sentence user impact.

### Output format
Markdown report following the schema at the end of [`ux-stress-test.md`](../docs/guides/ux-stress-test.md).

```
## /ux-review report

**Target:** <path | url | screenshot>
**Surface area:** <which screens/components>
**Score:** N findings (P0: x, P1: y, P2: z, P3: w)

### P0 findings
### P1 findings
### P2 findings
### P3 findings

### Bright spots
<what's actually good here — counterbalance the punch list>
```

### Non-goals
- Not a redesign generator. Resist the urge to "what if we rebuilt this?" Tesler's Law says you'd just move complexity.
- Not a style police for taste-only choices (lowercase vs sentence case, font selection, accent hue). Only flag inconsistency, never preference.
- Not a code reviewer. Don't comment on architecture, performance, or correctness unless they manifest as UX symptoms (e.g. a 5s wait with no progress indicator is a UX bug *and* a perf bug — flag it as UX).

## Open questions

1. **Auto-screenshot a Next.js dev server?** Nice but heavy. v1 probably handles files + URLs only; v2 spins up a Playwright headless browser for in-repo apps.
2. **Should it write fixes?** v1 produces the report only. v2 could offer an `--apply` mode that proposes diffs for P0/P1 findings.
3. **PR mode.** A `/ux-review --pr <num>` that pulls the diff and reviews UI changes only.
4. **Calibration.** First few runs need human review to verify it doesn't flag false positives or miss obvious P0s. Plan: dogfood on `sketch2md` and the quest dashboard.
5. **Cost.** The skill will likely run on Sonnet for speed. Reserve Opus for the synthesis pass on long reports.

## Decision needed

- Does the guidebook need another round before we hardcode a skill against it?
- v1 scope: files-only? URLs? Screenshots?
- Lives under `~/.claude/skills/ux-review/` (global) or as a project-level skill in `.claude/skills/`?

## Not yet

This is in `ideas/` for a reason. The guidebook should bed in first — let teams use it manually, refine the principle IDs and rubric questions based on what people actually argue about. Then encode it.
