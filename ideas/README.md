# Ideas

Working notes for Quest improvements that are not yet fully implemented.

When an idea is implementation-ready, run `/quest "..."` and move execution evidence to `docs/quest-journal/`.

## Status Legend
- `idea`: concept captured, not scoped
- `proposed`: concrete plan exists, not started
- `in-progress`: partially implemented or actively iterating
- `reference`: operational note or incident record (not a build proposal)
- `implemented`: completed; retained for historical context

## Active Index

### Governance and Enforcement
| File | Status | Purpose |
|---|---|---|
| `quest-policy-canonicalization-and-enforcement-roadmap.md` | proposed | Canonical plan to reduce policy drift and convert rules into enforced checks. |
| ~~pr-body-hard-gate~~ | implemented | PR body CI gate shipped. See [journal](../docs/quest-journal/pr-body-gate_2026-02-22.md). Branch protection enforcement is a follow-up. |
| `handoff-validation-and-failure-ux.md` | proposed | Add actionable diagnostics when handoff fallback occurs. |
| `quest-abandon-flow.md` | proposed | Add `/quest abandon <id>` flow with state-safe transitions. |
| `quest-completion-gate.md` | idea | Define when a quest should be considered complete. |
| `quest-readme-auto-update.md` | idea | Auto-maintain `.quest/README.md` on quest completion. |

### Architecture and Workflow Evolution
| File | Status | Purpose |
|---|---|---|
| `quest-architecture-evolution.md` | in-progress | Multi-phase roadmap for Quest architecture maturity. |
| `phase2b-context-leak-closure.md` | in-progress | Concrete closure plan and findings for remaining context leaks. |
| `quest-context-optimization.md` | in-progress | Token/context reduction tactics for orchestrator paths. |
| `parallel-reviewer-orchestration.md` | in-progress | Ensure reviewer phases are truly parallel and observable. |
| `phase4-role-relocation.md` | implemented | Historical record for role file relocation decision/work. |
| `quest-council-mode.md` | idea | Optional dual-plan council mode for high-risk work. |
| `quest-file-attribution-line.md` | idea | File-level Quest attribution and license provenance line. |

### Codex and Operations Notes
| File | Status | Purpose |
|---|---|---|
| `codex-quest-skill.md` | idea | Codex-only quest orchestration runner design. |
| ~~codex-quest~~ | implemented | Moved to [`docs/guides/codex-quest-install.md`](../docs/guides/codex-quest-install.md). |
| `quest-sequence-enforcement-feedback-2026-02-21.md` | reference | Incident note on early-build drift and required sequence controls. |
| `runtime-attribution-accuracy-for-context-health.md` | reference | Incident note and fix plan for backend runtime attribution accuracy. |
| `memory_bank_model.md` | reference | General memory-bank pattern note for AI-guided repos. |

## OPINIONS

Current ideas/ walkthrough (excluding ideas/README.md):

  1. ideas/codex-quest-skill.md
     Elevator: Add a Codex-native $quest runner so Quest can run end-to-end with GPT-only role execution.
     Recommendation + opinion: Defer until demand is clear; strong strategic idea, but not core stability
     work.
     Risk: Medium-High. Impact: High (if Codex-first workflow matters).
  2. ~~ideas/codex-quest.md~~ — Implemented. Moved to `docs/guides/codex-quest-install.md`.
  3. ideas/handoff-validation-and-failure-ux.md
     Elevator: Validate handoff.json and log explicit fallback reasons to make failures diagnosable.
     Recommendation + opinion: Prioritize soon; this is high-value reliability hardening.
     Risk: Low-Medium. Impact: High.
  4. ideas/memory_bank_model.md
     Elevator: Generic “memory bank” pattern for curated AI context docs.
     Recommendation + opinion: Keep as reference; good concept, not Quest-core priority.
     Risk: Low. Impact: Medium.
  5. ideas/parallel-reviewer-orchestration.md
     Elevator: Ensure/verify reviewer phases actually run in parallel and capture observability evidence.
     Recommendation + opinion: Do instrumentation pass, not major redesign.
     Risk: Medium. Impact: Medium-High (latency + independence confidence).
  6. ideas/phase2b-context-leak-closure.md
     Elevator: Concrete closure plan for remaining context leaks and runtime isolation gaps.
     Recommendation + opinion: Continue and close; this is core architecture quality work.
     Risk: Medium. Impact: High.
  7. ideas/phase4-role-relocation.md
     Elevator: Historical record of moving role wiring under Quest skill ownership.
     Recommendation + opinion: Keep as implemented history; no new work needed.
     Risk: Low. Impact: Low (now).
  8. ~~ideas/pr-body-hard-gate-required-check.md~~ — Implemented. See `docs/quest-journal/pr-body-gate_2026-02-22.md`.
  9. ideas/quest-abandon-flow.md
     Elevator: Add formal /quest abandon <id> lifecycle handling with safe state transitions.
     Recommendation + opinion: Worth doing; medium priority but clean operational value.
     Risk: Low-Medium. Impact: Medium.
  10. ideas/quest-architecture-evolution.md
     Elevator: Master phased roadmap for Quest architecture maturity.
     Recommendation + opinion: Keep as top-level roadmap; trim/refresh as phases complete.
     Risk: Low. Impact: High (alignment).
  11. ideas/quest-completion-gate.md
     Elevator: Define true “done” semantics for quest lifecycle and closure timing.
     Recommendation + opinion: Decide and codify soon to reduce workflow ambiguity.
     Risk: Low. Impact: Medium.
  12. ideas/quest-context-optimization.md
     Elevator: Tactical token/context reduction (handoff-first orchestration, fewer heavy reads).
     Recommendation + opinion: Merge with Phase 2b execution plan to avoid split ownership.
     Risk: Medium. Impact: High.
  13. ideas/quest-council-mode.md
     Elevator: Optional dual-plan council mode with comparison and human winner selection.
     Recommendation + opinion: Defer; powerful but expensive/complex before core hardening completes.
     Risk: High. Impact: Medium-High (for high-risk projects only).
  14. ideas/quest-file-attribution-line.md
     Elevator: Add standardized Quest attribution/license line in managed files.
     Recommendation + opinion: Low priority; governance nice-to-have, little runtime value.
     Risk: Low. Impact: Low.
  15. ideas/quest-policy-canonicalization-and-enforcement-roadmap.md
     Elevator: Canonical-source map + enforcement roadmap to prevent policy drift and instruction-only
     gaps.
     Recommendation + opinion: Highest-priority governance doc; use this as the single hardening plan.
     Risk: Medium (touches multiple docs/workflows). Impact: High.
  16. ideas/quest-readme-auto-update.md
     Elevator: Automatically maintain .quest/README.md completion index.
     Recommendation + opinion: Useful convenience; defer behind stronger enforcement work.
     Risk: Low. Impact: Low-Medium.
  17. ideas/quest-sequence-enforcement-feedback-2026-02-21.md
     Elevator: Incident note documenting early-build sequencing failure and corrective controls.
     Recommendation + opinion: Keep as reference evidence until enforcement is fully automated.
     Risk: Low. Impact: Medium (decision support).
  18. ideas/runtime-attribution-accuracy-for-context-health.md
     Elevator: Incident note and correction protocol for runtime attribution errors in context logs.
     Recommendation + opinion: Keep as reference until runtime validator is implemented and stable.
     Risk: Low. Impact: Medium-High (metrics trustworthiness).

## Hygiene Rules
- Keep one file per idea family; avoid duplicate variants.
- Keep incident notes in `ideas/` only while they are actively informing roadmap work.
- If a note is superseded, delete it or merge it into the canonical idea file.
- If an idea is implemented, link the quest journal entry in the file and mark status accordingly.
