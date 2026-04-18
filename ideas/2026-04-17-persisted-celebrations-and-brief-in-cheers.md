# Idea: Persisted Celebrations With Embedded Brief And Journal Cross-Links

## Status: proposed (follow-up quest)

## Origin

Surfaced during the Review Intelligence Phase 2 quest wrap-up. User's stated preference: celebrations are *"much more enjoyable and let you understand things better"* than the structured journal — they carry cast, achievements, quote, and victory narrative that the journal does not — but today they are ephemeral chat output.

The Quest Dashboard surfaces quest stats and briefs well, but the *celebrations* — generated once at `/celebrate` time and then lost — are actually the most valuable record to preserve and re-read.

We want celebrations to survive the session and be cross-linked with the quest journal, so any reader (dashboard, another quest, a human browsing months later) can jump from "I see this quest happened" to "here is what it felt like and what it shipped."

## Reference Project

`doc2md` (Jean-Claude / Dexter) already solves the persistence half:

- `docs/journal/NNN-celebrate-<slug>.md` — narrative celebration entries with frontmatter (`quest-id`, `pr`, `style`, `quality-tier`, `date`).
- `docs/dexter-journal/NNN-requiem-<slug>.md` — parallel style with ascii tombstones.
- `docs/quest-journal/<slug>_<date>.md` — structured quest journal, adjacent to the celebration.
- Both are checked into git at quest completion time.

We will borrow the **pattern** (persist + cross-link + frontmatter), not the double-persona voice. Our single-voice celebrations already exist — we just need to save them.

## Problem

1. **Celebrations are ephemeral.** The `celebrate` skill prints rich markdown to the chat and disappears. The data the skill read (handoffs, fixer summary, arbiter verdict) is archived, but the synthesized *narrative* is not.
2. **Journals are dry.** `docs/quest-journal/<id>.md` captures stats, file list, and brief, but it does not carry achievements, the quote, or the victory narrative. Re-reading it months later is less enjoyable than re-reading a celebration.
3. **No problem statement in the celebration.** The celebration currently focuses on *what happened*, not *why we started*. The brief is already available; it should be pulled in so the celebration is self-contained.
4. **Dashboard has no hook into celebration narratives.** It reads journals and archives but cannot link out to "the good story."

## Proposal

Add three behaviors to the `celebrate` skill and the Step 7 (complete) path of `workflow.md`:

### 1. Embed a short brief in the celebration

Pull from `quest_brief.md`:

- Extract the first paragraph after the "What Started" / "Problem" / brief body heading.
- If a Problem/Impact pair exists, include both as short paragraphs.
- If only a one-line prompt exists, quote it as-is.
- Always link back to the full brief at `.quest/archive/<id>/quest_brief.md`.

Add a new celebration section placed between the title art and the Starring Cast:

```markdown
## 📖 What Started This

<short problem statement>

<short impact statement, optional>

Reference: <ideas/... or other referenced doc, if mentioned in the brief>
```

### 2. Persist the celebration to disk

At the end of the `celebrate` skill's render step, also write the full markdown (block art + all sections) to:

```
docs/quest-journal/celebrations/<slug>_<date>.md
```

Frontmatter at the top (matches doc2md pattern):

```markdown
<!-- quest-id: <id> -->
<!-- pr: <#NN or null> -->
<!-- style: celebration -->
<!-- quality-tier: <tier> -->
<!-- date: <YYYY-MM-DD> -->
<!-- journal: ../<slug>_<date>.md -->
```

The celebrations subdirectory should be created if it does not exist. If the file already exists (replay of `/celebrate` on the same quest), overwrite it — re-running the celebration should produce the same (or improved) artifact, not append.

### 3. Link journal ↔ celebration

When the quest journal is written (Step 7), add two new lines to the header block:

```markdown
- PR: [#NN](<url>)
- Celebration: [`celebrations/<slug>_<date>.md`](celebrations/<slug>_<date>.md)
```

The celebration frontmatter already points back to the journal via the `<!-- journal: -->` comment, closing the loop.

## Where It Plugs In

- `.skills/celebrate/SKILL.md` — add Step 5 ("Persist") and Step 6 ("Emit brief section"). The render instructions already exist; the change is about *where the output goes* and *what new section is included*.
- `.skills/quest/delegation/workflow.md` Step 7 — when the journal entry is being written, add the Celebration link line if a celebration file was produced (or if one is about to be produced — order-of-operations is a design choice, see Open Questions).
- `scripts/quest_celebrate/` — already owns the animation + ASCII side of things. Could own the persistence helper too, as a new `persist.py` that takes the rendered markdown + quest archive path and writes the celebration file.
- `scripts/quest_dashboard/` — the dashboard can add a "Celebration" column/link by reading the journal's Celebration line OR by globbing `docs/quest-journal/celebrations/`.

## Data Flow

```
Quest completes
    │
    ▼
Step 7 Journal Write ──── writes docs/quest-journal/<slug>_<date>.md
    │                         (with Celebration link placeholder)
    ▼
/celebrate skill fires
    │    reads quest_brief.md for problem statement
    │    reads handoffs for cast / metrics / quote
    │    renders markdown (existing behavior)
    │
    ▼
Celebration persist step ──── writes docs/quest-journal/celebrations/<slug>_<date>.md
    │                              (with frontmatter linking to journal)
    ▼
Dashboard next refresh ──── shows "Celebration" link pulled from journal
```

Alternative order: celebration fires FIRST, journal is written SECOND with the celebration path already known. This is cleaner (no placeholder) but moves celebration from an optional post-complete step to part of the complete path. Worth debating; see Open Questions.

## Acceptance Signals

- Every new quest ends with two sibling markdown files: `docs/quest-journal/<id>.md` and `docs/quest-journal/celebrations/<id>.md`, each linking to the other.
- The celebration file includes a brief-derived problem/impact section before the starring cast.
- Dashboard surfaces the celebration link for each completed quest.
- Re-running `/celebrate <id>` on an archived quest regenerates the celebration file in place (idempotent).
- Existing celebrations (this one and any future ones before the quest ships) can be retrofitted by a one-time backfill script that walks `.quest/archive/` and generates missing celebration files.

## Scope Boundaries

**In scope:**
- Celebration persistence to `docs/quest-journal/celebrations/`
- Brief embedding in celebrations
- Journal ↔ celebration cross-linking
- Dashboard surfacing the link (read-only)
- Backfill script for existing archived quests

**Out of scope:**
- Dual-persona voices (we are not building a Dexter)
- Rewriting existing quest journal entries (too risky; only add the Celebration link if a celebration file exists or is being produced)
- Auto-publishing celebrations anywhere external
- Changing the tier scale or the ASCII art rules

## Open Questions

1. **Ordering:** does the celebration fire before or after the journal write? The cleaner path is celebration-first (journal references a real file), but celebration is currently user-triggered (`/celebrate`). Options: auto-celebrate at Step 7 (default on) with an opt-out; or leave celebration user-triggered but have the journal write a placeholder that fills in on next celebration.
2. **Auto-trigger on quest complete:** should Step 7 invoke `/celebrate` automatically? This raises the question of what happens if the user does not want a celebration (e.g., small fix quests). Leaning: yes for `workflow` mode, optional for `solo`, with an allowlist gate.
3. **Backfill of existing quests:** there are ~10 archived quests without celebrations. A one-time `scripts/quest_backfill_celebrations.py` similar to the existing `quest_backfill_journal.py` could generate them. Worth its own small quest slice.
4. **Dashboard surfacing:** should the dashboard embed the celebration (heavy) or just link to it (light)? Light link is safer; avoid inflating dashboard payload.
5. **Filename collisions:** if two quests complete on the same date with the same slug root (rare but possible with solo vs workflow re-runs), include the `__HHMM` part of the quest ID in the celebration filename. Align with whatever the journal naming already does.

## Follow-Up Quest Prompt (Draft)

```text
/quest "Persist quest celebrations to disk with embedded brief and journal cross-links.

Reference: ideas/2026-04-17-persisted-celebrations-and-brief-in-cheers.md
Pattern reference (light): ../doc2md/docs/journal/ + docs/quest-journal/ directory structure.

DELIVERABLES

1. Extend .skills/celebrate/SKILL.md so celebrations include a 'What Started This'
   section pulled from quest_brief.md (problem + impact paragraphs, fallback to
   full brief quote if structured headings are missing).

2. Persist the rendered celebration to
   docs/quest-journal/celebrations/<slug>_<date>.md with frontmatter
   (quest-id, pr, style=celebration, quality-tier, date, journal pointer).
   Re-runs are idempotent (overwrite, do not append).

3. Update .skills/quest/delegation/workflow.md Step 7 to include a
   'Celebration: <path>' link in the journal header when a celebration file
   exists or is about to be produced.

4. New helper scripts/quest_celebrate/persist.py (or equivalent) that takes
   the rendered markdown plus quest archive path and writes the celebration
   file with correct frontmatter.

5. Dashboard integration: scripts/quest_dashboard/ surfaces the celebration
   link per quest by reading the journal's Celebration line. Read-only — do not
   embed full content.

6. Backfill script scripts/quest_backfill_celebrations.py that walks
   .quest/archive/ and generates missing celebration files from available
   handoffs and the brief. Optional companion to quest_backfill_journal.py.

7. Focused tests under tests/ for: brief extraction edge cases (no heading,
   one-line prompt, Problem+Impact pair), celebration persistence (idempotent
   overwrite, frontmatter shape), journal↔celebration link pairing,
   backfill script happy path + skipping cases.

OUT OF SCOPE

- Dual-persona voices (no Dexter-style requiem).
- Dashboard content embedding (links only).
- External publishing of celebrations.
- Tier scale or ASCII art changes.

KILL CRITERIA

Roll back if celebration persistence introduces state churn, if backfill
produces worse narratives than the original skill, or if the journal
link breaks existing dashboard rendering."
```

## Priority

Medium. This is a polish / legibility play, not a correctness play. But the user explicitly noted it "almost got forgotten" and that celebrations are the most enjoyable way to re-read quest history — a high-signal UX feedback worth acting on before the backlog of uncelebrated quests grows.
