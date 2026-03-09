# Ideas

Working notes for Quest improvements that are not yet fully implemented.

When an idea is implementation-ready, run `/quest "..."` and move execution evidence to `docs/quest-journal/`.

Architecture source of truth now lives in `docs/architecture/`. Use this
folder for proposals and draft spikes; promote stable direction to
architecture docs.

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

### Architecture and Workflow Evolution
| File | Status | Purpose |
|---|---|---|
| `phase2b-context-leak-closure.md` | in-progress | Concrete closure plan and findings for remaining context leaks. |
| `quest-file-attribution-line.md` | idea | File-level Quest attribution and license provenance line. |

### Codex and Operations Notes
| File | Status | Purpose |
|---|---|---|
| `memory_bank_model.md` | reference | General memory-bank pattern note for AI-guided repos. |

### Graduated
| Idea | Destination |
|---|---|
| pr-inline-commenting-playbook | [`docs/quest-journal/pr-inline-commenting-playbook_2026-03-05.md`](../docs/quest-journal/pr-inline-commenting-playbook_2026-03-05.md) |
| pr-body-hard-gate | [`docs/quest-journal/pr-body-gate_2026-02-22.md`](../docs/quest-journal/pr-body-gate_2026-02-22.md) |
| phase4-role-relocation | [`docs/quest-journal/phase4-role-wiring_2026-02-18.md`](../docs/quest-journal/phase4-role-wiring_2026-02-18.md) |
| quest-sequence-enforcement | Absorbed into policy roadmap and branch hardening |
| runtime-attribution-accuracy | Fix shipped in `workflow.md`; validator tracked in policy roadmap |

### Done Index
| Status | Idea | Note |
|---|---|---|
| done | ~~celebration-from-journal~~ | Quality tiers, embedded celebration_data JSON, dashboard integration. See [journal](../docs/quest-journal/celebration-from-journal_2026-03-06.md). |
| done | ~~pr-inline-commenting-playbook~~ | Kind, actionable PR inline comment playbook with signature convention. See [journal](../docs/quest-journal/pr-inline-commenting-playbook_2026-03-05.md). |

## Hygiene Rules
- Keep one file per idea family; avoid duplicate variants.
- Keep incident notes in `ideas/` only while they are actively informing roadmap work.
- If a note is superseded, delete it or merge it into the canonical idea file.
- If an idea is implemented, link the quest journal entry in the file and mark status accordingly.
