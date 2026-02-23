# Ideas

Working notes for Quest improvements that are not yet fully implemented.

When an idea is implementation-ready, run `/quest "..."` and move execution evidence to `docs/quest-journal/`.

## Status Legend
- `idea`: concept captured, not scoped
- `proposed`: concrete plan exists, not started
- `in-progress`: partially implemented or actively iterating
- `reference`: operational note or incident record (not a build proposal)

## Active Index

### Governance and Enforcement
| File | Status | Purpose |
|---|---|---|
| `quest-policy-canonicalization-and-enforcement-roadmap.md` | in-progress | Canonical plan to reduce policy drift and convert rules into enforced checks. |
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
| `quest-council-mode.md` | idea | Optional dual-plan council mode for high-risk work. |
| `quest-file-attribution-line.md` | idea | File-level Quest attribution and license provenance line. |

### Codex and Operations Notes
| File | Status | Purpose |
|---|---|---|
| `codex-quest-skill.md` | idea | Codex-only quest orchestration runner design. |
| `memory_bank_model.md` | reference | General memory-bank pattern note for AI-guided repos. |

### Graduated
| Idea | Destination |
|---|---|
| codex-quest | [`docs/guides/codex-quest-install.md`](../docs/guides/codex-quest-install.md) |
| pr-body-hard-gate | [`docs/quest-journal/pr-body-gate_2026-02-22.md`](../docs/quest-journal/pr-body-gate_2026-02-22.md) |
| phase4-role-relocation | [`docs/quest-journal/phase4-role-wiring_2026-02-18.md`](../docs/quest-journal/phase4-role-wiring_2026-02-18.md) |
| quest-sequence-enforcement | Absorbed into policy roadmap and branch hardening |
| runtime-attribution-accuracy | Fix shipped in `workflow.md`; validator tracked in policy roadmap |

## Hygiene Rules
- Keep one file per idea family; avoid duplicate variants.
- Keep incident notes in `ideas/` only while they are actively informing roadmap work.
- If a note is superseded, delete it or merge it into the canonical idea file.
- If an idea is implemented, link the quest journal entry in the file and mark status accordingly.
