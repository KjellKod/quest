---
title: Celebration from Journal — Replayable Celebrations for Archived Quests
purpose: Enable /celebrate to work from quest journal entries and enrich journal data for celebration replay
audience: Quest orchestrator, celebrate skill, dashboard
status: draft
---

# Celebration from Journal — Replayable Celebrations for Archived Quests

## The Problem

Today, `/celebrate` only works when the full quest directory exists (`.quest/<id>/` or `.quest/archive/<id>/`). Once a quest is archived to the journal (`docs/quest-journal/*.md`), the structured artifacts (state.json, handoff JSONs, review MDs) are gone. The celebration skill has to "wing it" from the sparse markdown journal entry — and loses agents, achievements, quality tiers, metrics, and real quotes.

The celebration we just winged for `celebrate-v2` proves this: we got a solid Gold-tier celebration from the journal text, but had to invent the cast, couldn't attribute achievements to specific models, and had no real quotes from reviewers.

## The Insight

We already have **two data readers** that parse quest data:

| Reader | Location | Source | Data |
|--------|----------|--------|------|
| **Dashboard loader** | `scripts/quest_dashboard/loaders.py` | `docs/quest-journal/*.md` | quest_id, slug, title, pitch, status, date, PR#, plan/fix iterations |
| **Celebrate data reader** | `scripts/quest_celebrate/quest_data.py` | `.quest/<id>/` live dirs | agents, achievements, quality score, review findings, files changed, plan summary |

The dashboard loader already reads journals. The celebrate reader already extracts rich data from quest directories. **We need to bridge these** — not reinvent the wheel.

## The Proposal: Two Changes

### Change 1: Enrich Journal Entries with a `celebration_data` JSON Block

At quest archive time (Step 7), the orchestrator already reads all the artifacts. Before writing the journal markdown, it should also write a compact JSON block **inside** the journal entry:

```markdown
## Celebration Data

<!-- celebration-data-start -->
```json
{
  "agents": [
    {"name": "planner", "model": "claude-opus-4-6", "role": "The Architect"},
    {"name": "builder", "model": "gpt-5.3-codex", "role": "The Implementer"},
    {"name": "code-reviewer-a", "model": "claude-opus-4-6", "role": "The A Code Critic"},
    {"name": "code-reviewer-b", "model": "kimi-k2.5", "role": "The B Code Critic"},
    {"name": "fixer", "model": "claude-opus-4-6", "role": "The Bug Slayer"}
  ],
  "achievements": [
    {"icon": "⭐️", "title": "One-Plan Wonder", "desc": "Plan approved in 1 iteration"},
    {"icon": "⭐️", "title": "Three-Gremlin Slayer", "desc": "Fixed 3 bugs in one pass"},
    {"icon": "⭐️", "title": "69 Nice", "desc": "69 tests passing, 31 new"}
  ],
  "metrics": [
    {"icon": "📊", "label": "6 modules reworked or created"},
    {"icon": "🧪", "label": "69 tests passing, zero regressions"},
    {"icon": "🔧", "label": "3 bugs fixed in single fixer pass"}
  ],
  "quality": {"tier": "Gold", "icon": "💎"},
  "quote": {
    "text": "All critical issues from the previous review cycle have been properly addressed.",
    "attribution": "Code Reviewer A, final verdict"
  },
  "victory_narrative": "This quest built the celebration system itself — block letters, achievements, cinematic credits. The snake eating its own tail.",
  "test_count": 69,
  "files_changed": 7
}
```
<!-- celebration-data-end -->
```

**Why embedded in markdown, not a separate file:**
- Journal entries are the permanent record. One file = one quest. No sprawl.
- The HTML comment markers make it invisible in rendered markdown but trivially parseable.
- Dashboard loader already reads these files — it can optionally extract this block too.
- The JSON block is compact (~20-30 lines). Not heavy.

**What goes in the JSON:**
- **Agents** with models and roles — the cast list
- **Achievements** — context-aware, specific to this quest (not generic)
- **Metrics** — domain-specific impact, not "files changed: 22"
- **Quality tier** — Diamond/Platinum/Gold/Silver/Bronze
- **Quote** — a real line from a reviewer, arbiter, or fixer
- **Victory narrative** — what this quest proved or demonstrated
- **test_count, files_changed** — compact numbers for rendering

**What stays in the markdown body** (already there):
- Quest ID, date, outcome, files changed list, iterations, "what started it" quote

### Change 2: Expand Celebrate Skill Resolution to Search Journals

Update the celebrate skill's "Step 1: Resolve the Quest Directory" to add a third search location:

```
If the user provides an argument:
1. Full path → use directly
2. Quest ID → search .quest/<id>/, .quest/archive/<id>/
3. Quest ID or short name → search docs/quest-journal/ for matching filename   ← NEW

If no argument:
- Most recent in .quest/archive/, OR
- Most recent in docs/quest-journal/ (by filename date)                        ← NEW
```

When celebrating from a journal entry:
1. Read the markdown file
2. Extract the `celebration_data` JSON block if present
3. If JSON present → use structured data for a rich celebration
4. If JSON absent (legacy entries) → "wing it" from the markdown text (current behavior, but acknowledged as graceful degradation)

### Non-Goal: Backfilling Old Journals

We won't auto-backfill the ~25 existing journal entries. They predate this convention. The wing-it path handles them. If someone wants to celebrate an old quest, the agent reads the markdown and improvises — which already works well enough.

## What About `celebration.json` (V3 Idea)?

The existing idea doc (`ideas/quest-completion-animations.md`) proposed a separate `celebration.json` file in the quest archive directory. This proposal **replaces** that idea with an embedded approach:

| Approach | Pros | Cons |
|----------|------|------|
| Separate `celebration.json` in archive dir | Clean separation | Another file to track, archive dirs may be cleaned up, celebration data divorced from the permanent journal record |
| Embedded JSON in journal markdown | One file = one quest, survives archive cleanup, dashboard loader can extract it, visible in the permanent record | Slightly unconventional, needs comment-marker parsing |

The embedded approach wins because the journal is the permanent record. Archive directories come and go. The journal is forever.

## Implementation Scope

### Files to Change

1. **`.skills/celebrate/SKILL.md`** — Add journal resolution path, document celebration_data JSON extraction
2. **`scripts/quest_dashboard/loaders.py`** — Add optional `celebration_data` extraction from journal markdown (extend `_parse_journal_entry`)
3. **`scripts/quest_dashboard/models.py`** — Add optional `celebration_data: dict | None` field to `JournalEntry`
4. **`.skills/quest/delegation/workflow.md`** (or wherever Step 7 is defined) — Document that journal writing should include celebration_data JSON block
5. **`scripts/quest_celebrate/quest_data.py`** — Add `load_quest_data_from_journal(path)` that extracts embedded JSON
6. **Tests** — journal loader with/without celebration_data, celebrate data reader from journal

### Effort Estimate

This touches existing modules in focused ways. No new abstractions. The dashboard loader already parses these files, the celebrate reader already has the data model. It's wiring, not architecture.

**Verdict: One-person job.** This doesn't need the full quest orchestration (plan → dual review → build → review → fix). It's a focused enhancement across a few known files with clear inputs and outputs. A single agent with the celebrate skill and dashboard context can handle it.

## Victory Narrative (Meta)

When this ships, every future quest celebration will be replayable forever — even after archive directories are cleaned up. The journal becomes the single source of truth for both the human-readable record AND the structured celebration data. And old quests? They get the "wing it" treatment — which, as we just proved, is already pretty good.
