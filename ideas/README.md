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
| `pr-body-hard-gate-required-check.md` | proposed | Enforce PR body structure as required CI + branch protection. |
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
| `codex-quest.md` | reference | Installation runbook for making Quest visible in Codex global skills. |
| `quest-sequence-enforcement-feedback-2026-02-21.md` | reference | Incident note on early-build drift and required sequence controls. |
| `runtime-attribution-accuracy-for-context-health.md` | reference | Incident note and fix plan for backend runtime attribution accuracy. |
| `memory_bank_model.md` | reference | General memory-bank pattern note for AI-guided repos. |

## Hygiene Rules
- Keep one file per idea family; avoid duplicate variants.
- Keep incident notes in `ideas/` only while they are actively informing roadmap work.
- If a note is superseded, delete it or merge it into the canonical idea file.
- If an idea is implemented, link the quest journal entry in the file and mark status accordingly.
