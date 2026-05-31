# Quest Journal: code-review-adjudication

**Quest ID:** code-review-adjudication_2026-05-30__1047
**Completed:** 2026-05-31
**Commit:** d9c6df7 (PR #124)
**Mode:** workflow (dual reviews + arbiter)

> Hand-authored after the fact. This quest ran in a human-pre-created worktree
> whose `.quest/` was a real directory rather than a symlink to the shared store,
> so its run artifacts were orphaned and removed during worktree cleanup before
> the normal `quest_complete.py` journaling step ran. This entry was reconstructed
> from the merged `#124` commit series and the run transcript. The root cause is
> being addressed by a follow-up quest (generalize the worktree `.quest` symlink)
> and a proposed completion-gate that makes journaling fail-closed.

## Summary

Brought the code-review phase to plan-phase **adjudication parity**, in two
sequenced parts implemented from `ideas/2026-05-30-code-review-adjudication.md`:

- **Part 1 — per-slot findings, fail closed.** Each code-reviewer must always
  write its canonical findings JSON (`[]` when clean); the orchestrator validates
  that file per slot the moment the reviewer returns, routing a missing/invalid
  file through the existing three-tier ladder ("structure the review you already
  wrote" retry → cross-runtime fallback → human decision). No more silent
  orchestrator hand-authoring of findings.
- **Part 2 — review-arbiter.** A new, impartial adjudicator role that replaces the
  deterministic `merge-findings` union in workflow mode: it judges each finding
  against the diff, never silently drops a correctness/security finding, filters
  only nitpick/scope-creep via AGENTS.md principles, surfaces an A-vs-B coverage
  summary, and fails open to the deterministic merge if it errors.

The feature **dogfooded itself**: during its own code-review round the new gate
caught a real backward-compat regression the build introduced (a newly-required
`review-arbiter` role wedging legacy 8-key `orchestration.json` on resume), the
review-arbiter adjudicated the reviewers' asymmetric severities, and the fixer
resolved it. Extensive human + Codex review then hardened the lockstep across
every surface a new role touches.

## Key Changes

- **New role contract:** `.skills/quest/agents/review-arbiter.md` + thin
  `.claude/agents/` and `.opencode/agents/` mirrors, registered in
  `.opencode/opencode.json` (agent + quest task perms) and the OpenCode
  orchestrator prompt.
- **Orchestration:** `.skills/quest/delegation/workflow.md` Step 5 (per-slot gate,
  arbiter wiring with `.next` staging, fail-open, dual-empty skip, re-anchored
  safety check), `code-reviewer.md` (findings JSON as a required output).
- **Scripts:** `quest_review_intelligence.py` (structured fail-closed
  `validate-findings`), `quest_runtime/orchestration.py` (review-arbiter slot +
  legacy backfill), `quest_runtime/artifacts.py` (role registration),
  `quest_validate-quest-state.sh` (9-role + arbiter-aware completion check),
  `quest_validate-handoff-contracts.sh` (7 role contracts).
- **Config/lockstep:** `.ai/allowlist.json` (`models.review-arbiter` +
  `review_arbiter_agent` permission), `.ai/schemas/allowlist.schema.json`,
  `.skills/quest/SKILL.md` Step 3.
- **Guardrail:** `tests/unit/test_canonical_role_lockstep.py` — a drift guard that
  fails by name if any role-list surface diverges from `CANONICAL_ROLES`.
- **Docs:** removed the unverified `codex-quest-install.md`; README recommends both
  Codex and Claude CLIs.

## Files Changed

29 files, +1289 / −105 (per the squashed `#124` merge): the review-arbiter
contract + mirrors, workflow/SKILL wiring, four `scripts/` modules, three
validators, allowlist + schema, the new drift-guard test plus extended
orchestration/state/review-intelligence/artifacts tests, and doc cleanup.

## Outcome

Completed and merged (PR #124, `d9c6df7`). All required CI checks green; the
advisory Codex review converged at zero new findings after the hardening rounds.
Final local verification: 785 pytest + all shell harnesses passing.

## Carry-Over Findings

No carry-over findings this round; nothing was inherited from earlier quests and
nothing needs to be saved for the next one. (Two *separate* prevention ideas were
spun off from the post-quest retro — generalize the worktree `.quest` symlink, and
make completion/journaling a fail-closed gate — but neither is a deferred backlog
finding from this quest's review.)

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    { "name": "planner", "model": "openai/gpt-5.3-codex", "role": "The Architect" },
    { "name": "plan-reviewer-a", "model": "anthropic/claude-opus", "role": "The A Plan Critic" },
    { "name": "plan-reviewer-b", "model": "openai/gpt-5.3-codex", "role": "The B Plan Critic" },
    { "name": "arbiter", "model": "anthropic/claude-opus", "role": "The Plan Judge" },
    { "name": "builder", "model": "anthropic/claude-opus", "role": "The Implementer" },
    { "name": "code-reviewer-a", "model": "anthropic/claude-opus", "role": "The A Code Critic" },
    { "name": "code-reviewer-b", "model": "openai/gpt-5.3-codex", "role": "The B Code Critic" },
    { "name": "review-arbiter", "model": "anthropic/claude-opus", "role": "The Newborn Code Judge (dogfooded its own birth)" },
    { "name": "fixer", "model": "openai/gpt-5.3-codex", "role": "The Self-Heal Surgeon" }
  ],
  "achievements": [
    { "icon": "🐍", "title": "Ouroboros", "desc": "The feature reviewed itself — its new gate caught a regression the build introduced" },
    { "icon": "⚖️", "title": "Severity Tie-Breaker", "desc": "Review-arbiter adjudicated A(low)-vs-B(high) to a defensible medium, verify_first" },
    { "icon": "🔒", "title": "Fail Closed, Never Drop", "desc": "Per-slot findings enforced; zero correctness findings silently dropped" },
    { "icon": "🎯", "title": "Lockstep Perfectionist", "desc": "review-arbiter registered across every role surface; drift guard added" }
  ],
  "metrics": [
    { "icon": "📊", "label": "Plan iterations: 2" },
    { "icon": "🔧", "label": "Fix iterations: 1" },
    { "icon": "🧪", "label": "Tests: 785 pytest + shell harnesses green" },
    { "icon": "📁", "label": "Files changed: 29 (+1289/-105)" }
  ],
  "quality": { "tier": "Gold", "grade": "B" },
  "inherited_findings_used": { "count": 0, "summaries": [] },
  "findings_left_for_future_quests": { "count": 0, "summaries": [] },
  "test_count": 785,
  "tests_added": null,
  "files_changed": 29
}
```
<!-- celebration-data-end -->
