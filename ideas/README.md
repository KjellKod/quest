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
| `codex-review-severity-emoji.md` | proposed | Add severity emoji to Codex review inline comments for faster scanning in PR threads. |
| `deep-ci-whole-file-logic-review.md` | proposed | Add a bounded Deep CI mode that reviews whole changed code files for resulting behavior, not just diff hunks. |
| `extract-codex-review-python.md` | in-progress | CI review Python was extracted into a real script with tests; the workflow still has one large heredoc block to finish removing. |
| `handoff-validation-and-failure-ux.md` | in-progress | Add actionable diagnostics when handoff fallback occurs. |
| `opencode-integration-deferred-items.md` | in-progress | Follow-up list from the first OpenCode rollout; some permission/alignment items are now resolved, others remain. |

### Architecture and Workflow Evolution
| File | Status | Purpose |
|---|---|---|
| `dual-model-planning.md` | proposed | Explore parallel plan generation with arbiter synthesis instead of a single planner output. |
| `quest-file-attribution-line.md` | idea | File-level Quest attribution and license provenance line. |
| `quest-multi-phase-execution.md` | proposed | Recommended pattern for handling large multi-phase initiatives: umbrella planning quest, then separate phase quests unless the passes still feed one bounded deliverable set. |
| `quest-preflight-sandbox-false-negative-bugfix.md` | in-progress | Host-context probe caching and diagnostics shipped; fallback classification/reporting is still not fully explicit. |
| `quest-requiem-ceremony.md` | idea | Add a reflective archive/abandon ceremony that mirrors completion celebration. |

### Codex and Operations Notes
| File | Status | Purpose |
|---|---|---|
| `claude-bridge-timeout-diagnosis-2026-03-23.md` | reference | Incident record showing sandbox-local Claude bridge probes can fail even when host execution is healthy. |
| `claude-cli-login-context.md` | reference | Operational note: external `claude` CLI login must be validated in the same execution context; an open app session is not enough. |
| `codex_calls_claude.sh` | reference | Older experimental bash bridge prototype retained as a reference alongside the supported Python bridge. |
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
| done | ~~generic-artifact-preparation-and-runtime-fallbacks~~ | Implemented on `codex-artifact-staging` / PR #74. Archived at [`ideas/archive/generic-artifact-preparation-and-runtime-fallbacks.md`](archive/generic-artifact-preparation-and-runtime-fallbacks.md). |
| done | ~~quest_dispatcher~~ | Quest now routes Codex-led Claude roles through the Quest runner/probe path with runtime logging and handoff polling. See [journal](../docs/quest-journal/quest-dispatcher_2026-03-09.md). |
| done | ~~codex-led-claude-bridge-runtime-hardening~~ | Codex-led Claude bridge runtime path shipped, documented, and exercised in a solo smoke test. See [journal](../docs/quest-journal/codex-led-claude-bridge-runtime-hardening_2026-03-09.md). |
| done | ~~codex-calls-claude~~ | Claude CLI bridge prototype graduated to supported script/runtime docs. See [journal](../docs/quest-journal/codex-calls-claude_2026-03-09.md). |
| done | ~~celebration-from-journal~~ | Quality tiers, embedded celebration_data JSON, dashboard integration. See [journal](../docs/quest-journal/celebration-from-journal_2026-03-06.md). |
| done | ~~pr-inline-commenting-playbook~~ | Kind, actionable PR inline comment playbook with signature convention. See [journal](../docs/quest-journal/pr-inline-commenting-playbook_2026-03-05.md). |
| done | ~~quest-state-transition-guardrails~~ | Atomic `--transition` flag, mandatory presentation gate enforced, helper-existence checks. Archived at [`ideas/archive/quest-state-transition-guardrails.md`](archive/quest-state-transition-guardrails.md). |

## Hygiene Rules
- Keep one file per idea family; avoid duplicate variants.
- Keep incident notes in `ideas/` only while they are actively informing roadmap work.
- If a note is superseded, delete it or merge it into the canonical idea file.
- If an idea is implemented, link the quest journal entry in the file and mark status accordingly.
