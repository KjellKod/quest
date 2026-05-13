---
title: Review-Skill Ergonomics and Team-Preference Memory
purpose: Tighten Quest's review skills with concrete prompt-engineering and workflow changes, and add a lightweight file-based memory for team preferences that survives across quests.
audience:
  - quest-developers
  - quest-users
scope: Review-adjacent skills (code-reviewer, ci-code-reviewer, plan-reviewer, pr-shepherd, fixer), plus a new pre-commit review entry point and a new team-preference store.
status: proposed
owner: kjell
date: 2026-04-22
---

> Superseded by `ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`.
> Keep this file as historical source material; do not implement directly.

## Problem

Quest's review pipeline is structurally strong (plan review, dual code review, arbiter, fix loop with defer taxonomy) but several ergonomic and memory gaps reduce day-to-day quality:

1. **No pre-commit review entry point.** We review plans and PRs, but there is nothing between "I finished coding" and "I push a PR". Developers either skip review or wait for a PR cycle.
2. **Polling windows are loosely specified.** `pr-shepherd` says "wait ~180s if pending" — an LLM given latitude drifts. Sometimes it retries forever, sometimes gives up after one try.
3. **LLM-default chattiness is unconstrained.** Review outputs frequently include padding ("Great work on X, one small nit..."), restated findings as top-level PR comments, and unsolicited justification replies. Each skill re-derives anti-chat rules locally; nothing is shared.
4. **Parallel sub-agent usage for independent findings is aspirational, not prescribed.** `pr-shepherd` batches fixes but does not mandate parallel sub-agents for disjoint findings, leading to sequential execution even when the findings are independent.
5. **Review output references findings by title, not by number.** When a user says "fix the 2nd and 4th ones", the agent has to re-derive ordering. Numbered lists eliminate this.
6. **No activation announcement.** When several review-adjacent skills could plausibly fire, the user sometimes cannot tell which skill is running.
7. **Team preferences evaporate at the end of the conversation.** When a reviewer consistently marks "silent error-swallowing in `except:` blocks" as a blocker, or when a user says "we always prefer functional composition over class hierarchies here", nothing persists. The same correction happens on the next quest. `deferred_findings.jsonl` does not solve this — it tracks *unresolved findings on touched files*, not *patterns the team tends to apply*.
8. **Fix-loop iterations leave no audit trail.** Between arbiter verdict → fixer → re-review → fixer, there are no commits. A multi-iteration fix loop squashes into one terminal commit (if any). If iteration 3 breaks something that iteration 2 didn't, there is no commit to bisect to and no way to re-review "what the arbiter actually saw in iteration 2". The git history hides the loop's structure completely.
9. **`pr-shepherd` is badly named.** The name is metaphorical, not descriptive. New users encountering `/pr-shepherd` or reading `.skills/pr-shepherd/SKILL.md` do not immediately know that this is the "check-the-PR, respond-to-comments, iterate-until-green" skill. The verb in the actual behavior is "check" — fetch comments, evaluate CI, triage, fix, resolve.
10. **Quest-specific skills are not namespaced.** Skills like `pr-shepherd`, `plan-reviewer`, `code-reviewer`, `fixer`, `arbiter`, `implementer` live alongside completely portable skills (e.g., `gpt`, `celebrate`, `git-commit-assistant`) and alongside skills that come from other installed plugins. There is no visual cue that a skill is part of the Quest orchestration contract vs. a standalone utility. Skill-name collisions with other plugins are also possible — several of Quest's skill names (`run-review`, `check-pr-comments`) are generic enough that a third-party plugin could ship the same name.

## Proposal

Ten changes, grouped by effort. Items 1–4 are same-day changes. Items 5–6 are a week of focused work. Item 7 is the strategic bet. Items 8 and 10 are evaluation items — flagged for decision, not yet for implementation. Item 9 is a concrete rename with a well-bounded blast radius.

### 1. Hard polling budgets across all poll-equipped skills  (XS)

Replace prose like "wait a bit if pending" or "poll until the check completes" with explicit, numeric budgets in each affected skill:

- `pr-shepherd` CI wait: **30 seconds × 30 retries (15-minute cap)**.
- `ci-code-reviewer` existing-comment fetch: **10 seconds × 10 retries (100-second cap)** or single-shot, whichever matches the real API shape.
- Any future local-review skill (see item 5): **15 seconds × 20 retries (5-minute cap)**.

Write them as explicit `interval_seconds × max_retries` pairs in the SKILL.md body. Audit every skill for soft-language polling and convert.

### 2. Canonical review anti-pattern list  (S)

Create `.skills/review-anti-patterns.md` and reference it from every review-adjacent SKILL.md (`code-reviewer`, `ci-code-reviewer`, `plan-reviewer`, `pr-shepherd`, `fixer`). Contents, in rule + rationale form:

- **Do not add reply comments justifying a finding.** The finding is in the review; commentary belongs in the SHA-level summary, not on each thread.
- **Do not restate inline findings as top-level PR comments.** Inline-first is already our rule; this enforces it.
- **Do not ask "which issues to fix" when the severity is unambiguous.** Blockers and Must-fix items are always fixed. Ask only for Should-fix / Nit selection.
- **Do not introduce requirements the plan or PR description did not ask for.** "While you're here…" is scope creep.
- **Do not pad the review with empty PASS sections** when nothing notable was found. Clean output is: PR-description line + summary + APPROVE.
- **Bias toward action on iteration 3+.** Only blockers justify another round. Defer the rest via `review-decisions`.

Each referencing skill includes one line: "See `.skills/review-anti-patterns.md` for the shared rule set."

### 3. Announced skill activation as a global rule  (XS)

Add one line to `BOOTSTRAP.md` and to each review-adjacent SKILL.md opener:

> "At activation, announce the skill name and the scope it will operate on in one line. Example: `[code-reviewer] reviewing PR #97 against plan-2026-04-20.md`."

This eliminates the "which skill is running right now" confusion when multiple could trigger.

### 4. Numbered findings in review output  (XS)

Change the output format in `code-reviewer`, `ci-code-reviewer`, and `plan-reviewer` so every finding is prefixed with a stable number within the current review:

```
[1] Must fix — src/foo.py:42 — null deref when config is missing
[2] Should fix — src/bar.py:18 — redundant re-entry in retry loop
[3] Nit — docs/README.md:10 — typo
```

Downstream effects:
- User can say "fix 1 and 2" and the fixer maps unambiguously.
- `review-backlog.json` can carry the review-local index alongside `finding_id`.
- `pr-shepherd` batch reports become auditable by index.

### 5. Parallel sub-agent directive for independent findings  (S)

Add a reusable block to `pr-shepherd` (Step 4.4) and `fixer`:

> "When multiple findings are independent — disjoint files, no shared invariants, no ordering dependency — dispatch them to parallel sub-agents in a single tool-call round. Each sub-agent must independently validate the finding before fixing. No two sub-agents may edit the same file. Merge results before commit."

Include a short worked example in `delegation/workflow.md` showing when parallelism is and isn't safe (e.g., two findings in the same module with a shared type change must be sequential).

### 6. Pre-commit review skill  (S–M)

New skill: `.skills/pre-commit-review/SKILL.md`. Invocation targets the **working-tree diff**, not a PR URL:

- Inputs: `git diff` (staged + unstaged combined by default; configurable).
- Reuses `code-reviewer`'s severity model and `.skills/review-anti-patterns.md` rules.
- Outputs a numbered finding list (see item 4) with a "fix selected / fix all Must / skip" prompt.
- Stops when the user says "commit" or "skip"; never pushes.
- Also exposed as an explicit slash command `/pre-commit-review` so users can invoke without relying on auto-trigger.

### 7. Team-preference memory (soft-preference framed)  (M–L)

**The bet.** Build a lightweight, file-based memory for team preferences that any review skill loads at start and applies with hedge language — never as rigid rules.

#### Storage

New file: `.quest/memory/team_preferences.jsonl`, append-only. One JSON object per line:

```json
{
  "id": "tp_2026-04-22_001",
  "created_at": "2026-04-22T11:00:00Z",
  "source": "user_correction | arbiter_dismissed | reviewer_repeat",
  "confidence": "high | medium | low",
  "pattern": "We prefer functional composition over class hierarchies in src/pipeline/",
  "example_finding_id": "f_2026-04-20_abc",
  "path_glob": "src/pipeline/**",
  "superseded_by": null
}
```

#### Capture (three narrow sources — no speculative population)

- **Explicit user command**: `/remember "we prefer immutable structs for config objects"` saves `source: user_correction`, `confidence: high`.
- **Arbiter dismissal pattern**: when the arbiter dismisses the same class of finding three times in a row across iterations, it appends `source: arbiter_dismissed`, `confidence: medium` with a proposed pattern the user must confirm on the next review.
- **Repeated reviewer verdict**: when two reviewers in the same quest independently flag the same class of issue, the arbiter appends `source: reviewer_repeat`, `confidence: medium`.

Never auto-promote. Never store a preference without a linked originating finding or explicit user command.

#### Read (consumed by every review skill)

`plan-reviewer`, `code-reviewer`, and `ci-code-reviewer` read `team_preferences.jsonl` at start and filter by `path_glob` against files in scope. They render the matching entries into context with hedge language:

> "The team tends to prefer X in this area (high confidence, from 3 prior reviewer verdicts). Weigh but don't enforce."

Explicit rendering rules — each SKILL.md body must include:

- **"Render preferences as tendencies, not rules. Never open a review with a preference-only blocker."**
- **"If a preference contradicts the current plan's stated direction, note it as context, not as a finding."**

#### Prune

Quarterly (or on-demand via `/prune-preferences`), an explicit command walks `team_preferences.jsonl` and marks entries `superseded_by` another entry or prompts the user to retire low-confidence entries with no recent reinforcement.

#### Why soft preferences

The worst failure mode of any institutional-memory system is turning one grumpy review into eternal gospel. The hedge-language render + confidence scoring + explicit user-promote gate are the anti-dogmatism wiring. Every design decision here should ask "does this make the preference more or less likely to be treated as absolute" and favor less.

### 8. Evaluate fix-loop commit checkpointing  (evaluation — no code yet)

**The open design question.** Today the fix loop — arbiter decides → fixer applies → code-reviewer re-runs → arbiter decides again — runs with no git checkpointing between iterations. All edits land in the working tree and only get committed when the user (or `git-commit-assistant`) says so at the end. Everything gets squashed into one "address review feedback" commit, which is clean for squash-merge workflows but has real downsides:

- **Lost audit trail.** The exact state the arbiter reviewed in iteration 2 is gone by the time iteration 3 runs. If a later regression traces back to "we broke it in the iteration-2 fix", there is no commit to bisect to.
- **No safe rollback point.** If iteration 3's fix turns out worse than iteration 2's, the user has to reconstruct iteration 2 manually from agent transcripts.
- **The arbiter's verdict is coupled to a moving tree.** Re-running a review against "what the arbiter saw" is impossible without committed snapshots.

Evaluate whether to add one of the following checkpointing modes and pick one as default (likely Mode B), with the others available via flag.

#### Mode A — pre-fix snapshot

Commit **after the arbiter emits its verdict, before the fixer runs**. Commit message: `checkpoint: quest-<id> iter-N reviewed state`. The fixer then applies changes. At iteration N+1, another pre-fix snapshot is committed before the next fix.

- **Pros**: captures exactly the tree the arbiter reviewed; enables "re-review the same state" verification; isolates fixer changes cleanly into the next commit.
- **Cons**: commits a tree the team may not want to ship (known-imperfect); requires the author's own pre-fix changes to have already been committed, otherwise the snapshot captures unrelated staged/unstaged work.

#### Mode B — post-fix iteration commit

Commit **after the fixer finishes each iteration**, not before. Commit message: `fix: quest-<id> iter-N address review feedback`.

- **Pros**: each fix is isolated and auditable via `git log`; bisect-friendly; matches the pattern already used by successful review-loop tools; post-fix state is always a deliberate candidate for keeping.
- **Cons**: noisy on squash-merge conventions (mitigation: the commits get squashed at merge anyway, so history cost is bounded to the branch).

#### Mode C — ephemeral checkpoint tags

No commits in the main stream. After each arbiter verdict (or each fix), create a git tag like `quest/<id>/iter-N-reviewed` or `quest/<id>/iter-N-fixed` pointing at the current working-tree state via a temporary detached-HEAD commit on a shadow ref.

- **Pros**: zero pollution of the branch history; full audit trail available when needed.
- **Cons**: more moving parts; requires the user to know tags exist; cleanup policy needed (auto-delete tags on quest archive?).

#### Mode D — status quo

Keep no checkpoints. Accept the audit-trail loss as the cost of clean history.

#### Evaluation criteria (to decide in a follow-up discussion, not in this idea doc)

1. **What is our merge strategy on the repos that use Quest?** If squash-merge is universal, Mode B's noise cost is zero. If merge-commit is used, Mode C starts looking attractive.
2. **Do we ever want to bisect a fix-loop regression?** If yes, Mode B or C is required. Mode A would also work but commits less-desirable intermediate states.
3. **Does the arbiter need to be able to re-review a prior iteration's tree?** If yes, Mode A is the only option that guarantees it. If no (the arbiter always reviews "current state"), Modes B/C are sufficient.
4. **What does `pr-shepherd` do today?** It already commits fix batches during the PR comment-response loop. If Mode B matches that pattern, we unify the model across intra-quest fix loops and post-PR fix loops — worth checking whether the commit-message prefix should match (`fix: address review feedback (iteration N)` vs the intra-quest variant).
5. **Can the user opt out?** A `--no-iteration-commits` flag (or an allowlist gate) must exist for users who genuinely want a single terminal commit. Default-on, opt-out.

#### Interaction with existing gates

`gates.require_approval_before_commit: true` in `.ai/allowlist.json` currently requires human approval before any commit. A fix-loop checkpointing mode would need either (a) a scoped exception that auto-approves checkpoint commits only, or (b) a one-time per-quest approval covering the full loop. Option (b) is preferable — the user approves the loop's commit cadence once, at quest start, and the rest runs unattended.

Keep this item as **evaluation-only** until a decision is reached. Do not implement a mode as part of items 1–7.

### 9. Rename `pr-shepherd` → `check-pr`  (S)

The current name is a metaphor. "Shepherding" describes the behavior poetically but not accurately. A user seeing `/pr-shepherd` for the first time cannot reliably predict what it does. The actual verb is **check** — fetch comments, evaluate CI status, triage findings, fix batches, resolve threads, iterate until clean. "Check the PR" reads correctly.

#### Concrete rename scope

- Directory: `.skills/pr-shepherd/` → `.skills/check-pr/`
- Skill identity: `name: pr-shepherd` → `name: check-pr` in the SKILL.md frontmatter.
- Slash command: `/pr-shepherd` → `/check-pr` (and keep `/pr-shepherd` as an alias for a deprecation window if other users already reference it).
- Catalog entry: `.skills/SKILLS.md` section header + all prose references.
- Installer: `scripts/quest_installer.sh` copies whole skill directories today, so it picks up the new name automatically — but audit any hardcoded skill-name lists (manifest validation, checksum registry, `.quest-manifest`, `.quest-checksums`) that might enumerate `pr-shepherd` explicitly.
- Downstream references to update:
  - `.skills/SKILLS.md`
  - `.claude/skills/pr-shepherd/SKILL.md` (mirror copy — rename directory)
  - `.agents/skills/pr-shepherd/SKILL.md` (mirror copy — rename directory)
  - `tests/unit/test_codex_skill_wrappers.py`
  - `docs/guides/quest_setup.md`
  - `docs/quest-journal/*.md` (several) — update if the journal entries are still authoritative references; leave historical entries alone.
  - Any CLAUDE.md / AGENTS.md mentions.
  - Cross-references inside other skill bodies (e.g., `git-commit-assistant`, `review-decisions`, workflow docs).
- Manifest / checksum artifacts: `.quest-manifest`, `.quest-checksums`, `manifest.json` may need regeneration after the rename. Run the manifest validator (`scripts/quest_validate-manifest.sh`) as the final step of the rename and fix any fallout before committing.

#### Deprecation path

Ship the rename in one atomic PR. Keep a redirect stub at `.skills/pr-shepherd/SKILL.md` for one release that points users to `.skills/check-pr/SKILL.md` and documents the rename in its frontmatter description. Remove the stub in the following release.

#### Why this is worth doing now

It's a rare chance to fix a confusing name before we add the `/pre-commit-review` skill (item 6) and evaluate a `/check-pr-local` variant (item 7). Two "check"-named review skills reading identically is more discoverable than `pre-commit-review` + `pr-shepherd`.

### 10. Namespace Quest-specific skills with a `quest` prefix  (discussion — decision required before acting)

**The discussion.** Skills shipped by Quest are mixed in with standalone utility skills in the same `.skills/` catalog. There is no way to tell, at a glance, that `plan-reviewer` is part of the Quest orchestration contract (meaning: rename it and the whole pipeline breaks) while `git-commit-assistant` is a standalone utility (meaning: rename it and only that skill's invocations break). The risk is low today, but it grows as Quest is installed alongside more third-party plugins and as Quest's own skill set grows.

Decide whether to prefix all orchestration-contract skills with a stable `quest` marker, and pick one of the following naming conventions.

#### Option A — colon namespace: `quest:plan-reviewer`

- Reads cleanly, matches MCP convention (`mcp__codex-cli__codex`).
- Colon may not be a legal directory-name component on Windows (NTFS forbids `:` in filenames). Would require storing skills under a sanitized directory (`quest_plan-reviewer/`) and exposing the `quest:plan-reviewer` identity in frontmatter only.
- User-facing slash commands become `/quest:plan-reviewer`, which is clear but longer to type.

#### Option B — underscore prefix: `quest_plan-reviewer` or `quest_plan_reviewer`

- File-system-safe everywhere.
- Visually clear but less idiomatic for slash commands.
- Some skill names become awkwardly long (`quest_ci-code-reviewer`, `quest_check-pr`).

#### Option C — hyphen prefix: `quest-plan-reviewer`

- File-system-safe, matches existing hyphen-separated style.
- Reads as one long token rather than two (less obvious namespace boundary).
- Slash command: `/quest-plan-reviewer`. OK but verbose.

#### Option D — prefix only what is orchestration-critical, leave utilities alone

Apply the prefix only to skills that are load-bearing to the pipeline (`plan-maker`, `plan-reviewer`, `code-reviewer`, `ci-code-reviewer`, `check-pr` (from item 9), `fixer`, `arbiter`, `implementer`, `review-decisions`, the quest-agent itself). Keep portable skills unprefixed (`gpt`, `celebrate`, `git-commit-assistant`, `pr-assistant`, `pre-commit-review` from item 6).

- **Pros**: preserves portability of utility skills — a user of just `git-commit-assistant` should not have to know Quest exists.
- **Cons**: the boundary between "Quest-contract" and "utility" is fuzzy and will need to be documented explicitly to stay honest.

#### Option E — status quo

Accept that skill names are unnamespaced and rely on catalog documentation plus good skill-name hygiene to avoid collisions.

#### Prerequisite research — platform support for prefixed skill names

Before any of the options below can be chosen, confirm what each target client actually accepts as a skill identifier. The Quest pipeline runs on both Claude Code and Codex, and skill-name conventions may differ.

- **Claude Code**: confirmed supported. Skill names with hyphens are accepted today; colon-namespaced identifiers (`quest:check-pr`) work at the frontmatter-identity level though the on-disk directory name must be filesystem-legal (typically `quest-check-pr/` with the colon form only in the `name:` field).
- **Codex CLI**: unknown. Research required before committing to any option. Specifically:
  - Does Codex accept hyphen-prefixed skill names (`quest-check-pr`) in the `name:` field without transformation?
  - Does Codex accept colon-namespaced identifiers (`quest:check-pr`)?
  - Does Codex's skill-loader care about directory name vs. frontmatter `name:` when the two diverge (e.g., `quest-check-pr/` on disk with `name: quest:check-pr` in frontmatter)?
  - Are slash commands invoked with the same identifier as the skill, or do they have their own naming rules?
  - Does `mcp__codex-cli__codex` (the bridge Quest uses) preserve the prefix in sub-agent hand-offs, or does it strip/rewrite it?

If Codex does not accept one of the forms, that option is off the table — do not choose it for aesthetic reasons alone. The pipeline must function identically across both runtimes.

Output of this research: a one-page finding that maps each of Options A–E to "works on Claude, works on Codex, works on both" and lists any per-runtime caveats. Attach it to this idea doc before the decision meeting.

#### Decision criteria

1. **Collision risk today.** Is any other plugin we (or downstream users) install likely to ship a skill with the same name as one of ours? Run a quick survey of marketplace plugins before deciding.
2. **Install-location collision risk.** When Quest is installed into a repo that already has a `.skills/` directory from another plugin, do our names overwrite theirs today? If yes, prefixing is more urgent.
3. **Slash-command ergonomics.** Measure how often Quest skills are invoked by `/command` vs. auto-trigger. Frequent typing pressure argues against long prefixes.
4. **Cross-repo portability.** If a user takes `.skills/git-commit-assistant/` and drops it into another repo, should it work without any Quest context? If yes, that skill must stay unprefixed — argues for Option D.
5. **Migration cost.** Renaming all Quest orchestration skills touches many files and every stored quest's metadata (model map keys in `.ai/allowlist.json`, role names in `agents/*.md`, manifest entries). Estimate the blast radius before committing.

#### Recommendation (for discussion)

Start with **Option D**: prefix only orchestration-critical skills, use hyphen style (`quest-plan-reviewer`, `quest-arbiter`, `quest-fixer`, etc.), and leave portable utilities unprefixed. Combine with item 9's rename so `pr-shepherd` lands as `quest-check-pr`, not `check-pr`. If we later decide Option A (colon) is worth the cross-platform cost, the migration from hyphen to colon is mechanical.

Keep this item as **discussion-only** until a decision is made. If the decision is "yes, prefix", the rename from item 9 should be folded into the prefix rollout rather than shipped separately — doing the rename twice (once to `check-pr`, once to `quest-check-pr`) is avoidable pain.

## Dual-Mode Sanity Check

### Inside-repo use (Quest developed here)
- Items 1–5 are prompt edits inside existing SKILL.md files. Minimal risk.
- Item 6 (pre-commit review) is a new skill plus a thin Python wrapper. Local-only; no external calls beyond the existing model dispatch.
- Item 7 (team-preference memory) writes only to `.quest/memory/team_preferences.jsonl`. No new infra. The append-only JSONL format matches the existing `deferred_findings.jsonl` pattern.

### Outside-in use (Quest invoked from another repo)
- Items 1–5 propagate with the skill files. No repo-state dependency.
- Item 6: `pre-commit-review` requires `git` and a working tree. When `vcs_available == false`, the skill must refuse with a clear message and exit non-zero, not silently succeed.
- Item 7: `.quest/memory/` is repo-local, same scoping as `.quest/<id>/`. If a target repo has no `.quest/` root yet, the skill creates `memory/` on first write. No global / cross-repo state.

### Conflicts and Required Adaptations
- `code-reviewer` / `ci-code-reviewer` already have severity models and anti-creep rules scattered in their bodies. Items 2 and 4 require moving some of that text into the shared anti-pattern file and the numbered-output template. Keep the existing per-skill rules only if they are genuinely skill-specific (e.g., `ci-code-reviewer`'s PR-description validation, which is CI-only).
- `pr-shepherd` Step 4.4 already describes the intelligence pipeline (`normalize-pr-intake` → `build-backlog` → `select-batch-validation` → `build-fix-batches` → `classify-pr-stop`). Item 5 extends this with an explicit parallelism rule for disjoint findings; it does not replace the batching pipeline.
- `review-decisions/SKILL.md` defines the canonical decision set (`fix_now / verify_first / defer / drop / needs_human_decision`). Item 7's `team_preferences.jsonl` is a separate artifact and must not be consumed as if it were a backlog — the decision taxonomy stays unchanged.
- `.ai/allowlist.json` must grant reviewer roles read access to `.quest/memory/team_preferences.jsonl` and grant `arbiter` + a new `/remember` command path write access. No other role should write.

## Actionable Steps

### Same-day batch
1. Create `.skills/review-anti-patterns.md` with the six rules from item 2. Reference it from `code-reviewer`, `ci-code-reviewer`, `plan-reviewer`, `pr-shepherd`, `fixer` — one line each.
2. Add hard polling budgets (item 1) to `pr-shepherd` (CI poll) and `ci-code-reviewer` (existing-comment fetch). Grep for "wait", "poll", "until complete" to catch remaining soft windows.
3. Add the activation-announcement line (item 3) to `BOOTSTRAP.md` and each review SKILL.md opener.
4. Change `code-reviewer`, `ci-code-reviewer`, and `plan-reviewer` output format to number findings (item 4). Update any downstream consumers that parse review output (check `scripts/quest_review_intelligence.py` and the `review-backlog.json` shape for needed additions — store the review-local index alongside `finding_id`).

### Week-level batch
5. Add the parallel sub-agent directive (item 5) to `pr-shepherd` Step 4.4 and `fixer`. Add a worked example to `delegation/workflow.md`.
6. Build the `pre-commit-review` skill (item 6):
   - `.skills/pre-commit-review/SKILL.md` with numbered output, severity model, and a "fix / skip / commit" terminal prompt.
   - A `/pre-commit-review` slash command entry.
   - Update `.skills/SKILLS.md` catalog.

### Strategic batch
7. Implement team-preference memory (item 7):
   - Add `.quest/memory/` directory convention and add it to `.gitignore` so `team_preferences.jsonl` is local-only for the initial rollout. Revisit committed-vs-ignored once the format has stabilized.
   - Add `/remember` command and its save path.
   - Extend `arbiter` to write `arbiter_dismissed` / `reviewer_repeat` entries on pattern triggers.
   - Extend `plan-reviewer`, `code-reviewer`, `ci-code-reviewer` to read matching entries at start and render them with the mandated hedge language.
   - Add `/prune-preferences` command.
   - Update `.ai/allowlist.json` to allow reads for reviewer roles and writes for `arbiter` + `/remember` paths only.

### Evaluation (no code yet)
8. Decide on fix-loop commit checkpointing (item 8):
   - Survey merge strategies on the repos Quest operates against (squash vs. merge-commit).
   - Confirm whether the arbiter ever needs to re-review a prior iteration's tree state.
   - Compare the four modes (A–D) against criteria 1–5. Pick one as default; flag others as opt-in.
   - Sketch the allowlist-gate change (one-time per-quest approval covering checkpoint commits).
   - Return to this doc with a decision and, only then, add concrete implementation steps.

10. Decide on the `quest` prefix for orchestration-critical skills (item 10):
    - **First: platform support research.** Confirm which naming options actually work on Codex (Claude is already known to support them). Answer the specific questions in the "Prerequisite research" subsection of item 10. Produce a one-page finding mapping each Option A–E to "works on Claude / works on Codex / works on both". This must be done before any naming decision — options unsupported on Codex are not real options.
    - Survey existing plugins for skill-name collision risk.
    - Pick one of Options A–E, constrained by the research result. Recommended starting point (if supported on both runtimes): Option D with hyphen style.
    - If the decision is "yes, prefix", fold item 9's rename into this rollout so `pr-shepherd` lands as `quest-check-pr` in one step.
    - If the decision is "no, status quo", proceed with item 9 as specified.
    - Enumerate all touch points before starting: `.ai/allowlist.json` role names, `.skills/quest/agents/*.md`, model map keys, workflow references, test fixtures, docs.

### Rename (do after item 10's decision)
9. Execute the `pr-shepherd` → `check-pr` rename (or `quest-check-pr` if item 10 decides to prefix):
    - Rename directory and mirror copies (`.claude/skills/`, `.agents/skills/`).
    - Update `name:` in SKILL.md frontmatter.
    - Update catalog entry in `.skills/SKILLS.md`.
    - Update slash command registration and keep the old name as an alias for one release.
    - Update all references grep'd from `.md`, `.py`, `.sh`, `.json`, `.yml` files in the repo (excluding historical journal and archived `ideas/` entries).
    - Regenerate `.quest-manifest` and `.quest-checksums`; run `scripts/quest_validate-manifest.sh`.
    - Single atomic PR; do not interleave with other behavior changes.

## Non-Goals

- **No automatic rule promotion.** Preferences never become blocking rules without explicit user action.
- **No behavior change to existing review severity model.** Blocker / Must fix / Should fix / Nit stays as-is. Preferences are rendered as context, not as findings.
- **No backwards-compatibility shim for the numbered-output format.** Downstream consumers that parse review text are updated in the same batch as item 4.
- **No replacement for `deferred_findings.jsonl`.** Deferred findings (path-keyed, unresolved) and team preferences (pattern-keyed, persistent) are separate stores with separate lifecycles.

## Open Questions

- Should `.quest/memory/team_preferences.jsonl` be committed to the repo (team-shared) or gitignored (local-only)? **Decision for now: gitignored (local-only).** The file lives under `.quest/memory/` and is excluded from version control on initial rollout. Revisit once the format has stabilized and the noise profile is understood; team-sharing is the more valuable end state but only after the content has proven worth sharing. `/prune-preferences` still applies to the local file.
- Activation announcement: always on. Small, low-signal-cost, and consistent across interactive and CI contexts. No env-var suppression, no mode toggle — every skill announces its name and scope on activation, every time.
- Should `pre-commit-review` refuse to run if the tree is clean? Or should it fall back to last-commit review? Recommendation: refuse with a clear message; let the user explicitly pass a ref if they want a commit-scoped review instead.

## Cross-References

- `.skills/code-reviewer/SKILL.md`, `.skills/ci-code-reviewer/SKILL.md`, `.skills/plan-reviewer/SKILL.md`
- `.skills/pr-shepherd/SKILL.md`
- `.skills/review-decisions/SKILL.md`
- `.skills/quest/delegation/workflow.md` (Step 4.4 review-intelligence pipeline)
- `.skills/quest/agents/arbiter.md` (dismissal-pattern capture)
- `.ai/allowlist.json` (reviewer read / arbiter write paths)
- `.quest/backlog/deferred_findings.jsonl` (analogous file-based memory, different lifecycle)
- `ideas/2026-04-13-quest-memory-architecture.md` (prior memory-architecture thinking — sanity-check against existing proposals before implementing)
