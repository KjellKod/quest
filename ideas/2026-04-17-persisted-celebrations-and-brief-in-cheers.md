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

## Decided Defaults (2026-04-18)

1. **Ordering — celebration-first, journal-second.** At Step 7, generate the celebration *before* the journal is written so the journal's `Celebration:` link always points to an existing file. No placeholder pattern.

2. **Auto-trigger — allowlist-gated, solo always asks.** Add an `allowlist.celebration.auto` boolean:
   - `celebration.auto: true` → run automatically at Step 7 (render + persist).
   - `celebration.auto: false` → *always prompt* "celebrate now?" at Step 7. Never silently skip.
   - **Solo mode override:** always prompt regardless of the flag. Solo quests are often polish-only and do not deserve auto-ceremony.
   - The celebration *file is always written* when the skill runs. The allowlist flag controls whether it *renders in chat* automatically or waits for the prompt.

3. **Backfill — manual only (user-driven).** No batch script in the first pass. User will run `/celebrate <archived-id>` for past quests on demand. A backfill script can be promoted later if the batch need emerges. See the list of backfill candidates below.

4. **Dashboard — link only.** A `Celebration:` line per quest that links to the file. No inline excerpts, no full rendering. The dashboard is a navigation surface, not a reader.

5. **Filename and overwrite — context-aware, additive by default.** The filename is `<slug>_<date>.md` (matches journal). But "just overwrite" is wrong once you consider *who* is regenerating:

   - **Original write at Step 7** (context-rich): the orchestrator that just completed the quest has full in-session context (handoffs, commit diffs, what happened in chat). The celebration it produces is authoritative.
   - **Cold regen from archive** (context-thin): a fresh Claude/Codex instance running `/celebrate <archived-id>` later only has the archive files. Its celebration is reconstructed, not relived. Silently replacing a Step-7 original with a cold-regen would erode quality.
   - **Post-review regen** (context-enriched): after a long PR review cycle with multiple fix iterations, merged state, or follow-up commits, a revised celebration is legitimate — there's new material the original did not know about.

   **Rule:**
   - Frontmatter carries an `origin:` marker: `step7-original` | `cold-regen` | `post-pr-revision`.
   - `/celebrate` on a quest that has no file yet: write as `step7-original` (or `cold-regen` if invoked on an archived quest without a prior Step-7 write).
   - `/celebrate` on a quest that has a `step7-original` file:
     - Detect meaningful context change since the original (new commits on branch, PR comments, merged/closed state). Cheap checks only — `git log`, `gh pr view`.
     - **No new context** → warn "original celebration is authoritative and nothing meaningful has changed since; the current regeneration has less context than the original. Overwrite anyway? (y/N)" with default **no**.
     - **New context exists** → offer a revision mode: append `## Revision: <date>` section to the existing file *or* write a sibling `<slug>_<date>__revision-<YYYYMMDD>.md`. Pick per invocation. Mark the revision's `origin:` as `post-pr-revision` and add a `revision-of:` frontmatter pointer.
   - `/celebrate` on a quest that has a `cold-regen` file: normal overwrite prompt (cold can replace cold).
   - In all cases, *render the proposed celebration before any write* so the user can see what they'd be replacing.

   This preserves git history for free (commits still snapshot each revision) while making "don't clobber the context-rich original with a thin one" the default.

## Backfill Candidates (as of 2026-04-18)

35 archived quests under `.quest/archive/` lack a celebration file. User can invoke `/celebrate <id>` on any of these when they feel like reminiscing.

See [Appendix A](#appendix-a-backfill-candidates) at the bottom of this doc for the full list.

## Appendix A: Backfill Candidates

These 35 quests exist under `.quest/archive/` with no matching celebration file. Listed newest-first for convenience. Run `/celebrate <quest-id>` on any that feel worth preserving.

Journal-backed quests (richer source material for the celebration) are marked `✓`. Celebrations can still be generated for quests without a journal — the skill will fall back to the archive handoffs and quest_brief.

| Quest ID | Journal |
|---|---|
| `review-intelligence-canonical_2026-04-16__0218` | ✓ |
| `celebration-review-intel_2026-04-16__0828` | ✓ |
| `claude-insights-ideas_2026-04-15__1629` | ✓ |
| `quest-dashboard-briefs_2026-04-15__2048` | — |
| `feedback-intent-routing_2026-04-13__1101` | ✓ |
| `prompt-surface-consolidation_2026-04-13__1701` | ✓ |
| `caveman-review_2026-04-12__1353` | ✓ |
| `multi-cleanup_2026-04-11__1049` | ✓ |
| `ci-review-severity_2026-04-06__1820` | — |
| `quest-housekeeping-blitz_2026-03-21__0600` | ✓ |
| `artifact-runtime-fallbacks_2026-03-17__1416` | — |
| `artifact-prep-runtime_2026-03-17__0518` | — |
| `legion-manifesto-review_2026-03-09__1314` | — |
| `codex-led-claude-bridge-runtime-hardening_2026-03-09__1039` | ✓ |
| `claude-runtime-dispatch_2026-03-09__1236` | — |
| `codex-bridge-smoke_2026-03-09__1032` | — |
| `codex-bridge-smoke-v2_2026-03-09__1021` | — |
| `codex-bridge-smoke_2026-03-09__1012` | — |
| `codex-claude-bridge_2026-03-09__0935` | — |
| `celebrate-v2_2026-03-05__0643` | ✓ |
| `pr-inline-commenting-playbook_2026-03-05__0250` | ✓ |
| `quest-next-architecture_2026-03-05__2353` | — |
| `quest-completion-animations_2026-03-04__1953` | ✓ |
| `opencode-model-suitability_2026-02-28__1755` | ✓ |
| `model-suitability-guide_2026-02-28__2016` | — |
| `phase4-role-wiring_2026-02-17__2218` | — |
| `quest-dashboard_2026-02-11__0936` | — |
| `handoff-contract-fix_2026-02-09__2228` | ✓ |
| `thin-orchestrator_2026-02-09__1845` | ✓ |
| `skill-strategy_2026-02-09__1200` | ✓ |
| `installer-script_2026-02-04__1841` | ✓ |
| `ci-quest-validation_2026-02-04__1532` | ✓ |
| `interactive-plan-presentation_2026-02-04__1516` | ✓ |
| `validate-and-launch_2026-02-04__1045` | ✓ |
| `weekly-update-check_2026-02-04__2349` | — |

Totals: **35** archived quests without celebrations; **21** have journals, **14** do not.

The three `codex-bridge-smoke*` quests and `codex-claude-bridge` look like rapid re-runs during the Codex bridge work on 2026-03-09 — only the last (or `codex-led-claude-bridge-runtime-hardening`, which has a journal) is worth celebrating. Safe to skip the smoke-test duplicates.

## Follow-Up Quest Prompt (Draft)

```text
/quest "Persist quest celebrations to disk with embedded brief and journal cross-links.

Reference: ideas/2026-04-17-persisted-celebrations-and-brief-in-cheers.md (see Decided Defaults)
Pattern reference (light): ../doc2md/docs/journal/ + docs/quest-journal/ directory structure.

DELIVERABLES

1. Extend .skills/celebrate/SKILL.md so celebrations include a 'What Started This'
   section pulled from quest_brief.md (problem + impact paragraphs, fallback to
   full brief quote if structured headings are missing).

2. Persist the rendered celebration to
   docs/quest-journal/celebrations/<slug>_<date>.md with frontmatter
   (quest-id, pr, style=celebration, quality-tier, date, journal pointer,
   origin={step7-original|cold-regen|post-pr-revision}, and
   revision-of=<path> when applicable). Always render the celebration
   before any write so the user can see what would be saved.

   Overwrite policy (context-aware, additive by default):
   - If no prior file exists: write fresh; origin=step7-original when
     invoked at Step 7, else cold-regen.
   - If prior file has origin=step7-original and no meaningful context
     change (no new commits on branch, no new PR activity): default to
     NOT overwriting; warn that the current run has less context.
     Require explicit 'overwrite anyway' confirmation.
   - If prior file has origin=step7-original AND new context exists:
     offer revision mode — append '## Revision: <date>' section OR
     write sibling <slug>_<date>__revision-<YYYYMMDD>.md, user chooses.
     Mark origin=post-pr-revision and set revision-of.
   - If prior file has origin=cold-regen: normal overwrite prompt.

3. Update .skills/quest/delegation/workflow.md Step 7 to:
   (a) run the celebration BEFORE writing the journal (celebration-first order)
       so the journal's Celebration link always points at a real file;
   (b) include a 'Celebration: <path>' line in the journal header;
   (c) gate auto-run on allowlist.celebration.auto:
       - true  -> run automatically (render + persist);
       - false -> always prompt 'celebrate now?' (never silently skip);
       - solo  -> always prompt regardless of the flag.

4. Add allowlist.celebration.auto (boolean, default true) to .ai/allowlist.json
   schema. Document it in the allowlist reference.

5. New helper scripts/quest_celebrate/persist.py (or equivalent) that takes
   the rendered markdown plus quest archive path and writes the celebration
   file with correct frontmatter.

6. Dashboard integration: scripts/quest_dashboard/ surfaces the celebration
   as a link per quest by reading the journal's Celebration line.
   **Link only, no inline embedding.**

7. Focused tests under tests/ for:
   - brief extraction edge cases (no heading, one-line prompt,
     Problem+Impact pair)
   - frontmatter shape (all fields including origin and revision-of)
   - journal <-> celebration link pairing
   - allowlist flag behavior (auto-run vs prompt vs solo override)
   - overwrite policy matrix:
     - no prior file at Step 7 -> writes origin=step7-original
     - no prior file via /celebrate <archived-id> -> writes origin=cold-regen
     - prior step7-original + no new context -> default declines overwrite
     - prior step7-original + new commits/PR activity -> offers revision mode
     - prior cold-regen -> normal overwrite prompt
   - context-change detection (new commits on branch, new PR comments,
     merged/closed state) without requiring a live gh call in tests.

OUT OF SCOPE

- Backfill script for archived quests (user does this manually via /celebrate
  <archived-id>; promote to script only if batch need emerges).
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
