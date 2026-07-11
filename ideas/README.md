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
- `wont-do`: evaluated and deliberately rejected; kept (archived) with reasoning to prevent re-proposal

## Active Index

### Governance and Enforcement
| File | Status | Purpose |
|---|---|---|
| `quest-policy-canonicalization-and-enforcement-roadmap.md` | in-progress | Canonical plan to reduce policy drift and convert rules into enforced checks. |
| `codex-review-severity-emoji.md` | proposed | Add severity emoji to Codex review inline comments for faster scanning in PR threads. |
| `handoff-validation-and-failure-ux.md` | in-progress | Add actionable diagnostics when handoff fallback occurs. |

### Review Intelligence
| File | Status | Purpose |
|---|---|---|
| `2026-04-27-agent-commit-guard-pre-commit-review.md` | proposed | Add an opt-in agent-level commit guard that offers `pre-commit-review` before local commits without installing a raw Git hook. |
| [`archive/2026-05-30-code-review-adjudication.md`](archive/2026-05-30-code-review-adjudication.md) | shipped (PR #124) | Enforce per-slot findings JSON (fail closed) and add a code-review arbiter so A-vs-B findings are judged for truth, bringing the build phase to plan-phase adjudication parity. |

Current roadmap:

| Phase | Status | Focus |
|---|---|---|
| Phase 1 | done | Canonical review findings, decisions, and backlog contracts. |
| Phase 2 | done | Targeted validation and batched PR response. |
| Phase 3 | done | Bounded Deep CI whole-file review for selected changed code files. |
| Phase 3.1 | done | Deep CI oversized-file chunk fallback shipped in PR #98; see [`ideas/archive/deep-ci-chunked-context-plan.md`](archive/deep-ci-chunked-context-plan.md). |
| Phase 3.2 | done | Structured review-context manifest shipped in PR #101; see [`ideas/archive/deep-ci-review-context-manifest-plan.md`](archive/deep-ci-review-context-manifest-plan.md) and [`docs/quest-journal/deep-ci-manifest_2026-04-24.md`](../docs/quest-journal/deep-ci-manifest_2026-04-24.md). |

### Architecture and Workflow Evolution
| File | Status | Purpose |
|---|---|---|
| `2026-04-24-quest-hooks-vs-instructions-boundary.md` | proposed | Define the boundary between instruction files, hooks, and scripts for Quest, with Claude-first enforcement and Codex-aware adapter guidance. |
| `2026-04-29-research-fanout-skill.md` | proposed | Add a reusable research fan-out skill for human-triggered and planner-requested parallel investigation with reconciled findings. |
| `2026-05-19-sharpen-context-grounding.md` | proposed | Require sharpening questions to be grounded in targeted repo evidence before asking the user. |
| `2026-05-30-pre-pr-freshness-and-force-push-guard.md` | proposed | `pr-assistant` syncs the branch with the remote default branch as part of PR creation so we never open a PR stale against main; clean sync proceeds automatically, only conflicts stop for the human. |
| `dual-model-planning.md` | proposed | Explore parallel plan generation with arbiter synthesis instead of a single planner output. |
| `2026-04-13-codex-companion-runtime.md` | proposed | Phased prove-it roadmap for a shared Codex runtime serving both the human `/gpt` command surface and Quest orchestration, with strict go/no-go criteria after the minimum slice. |
| `2026-04-13-feedback-intent-routing.md` | proposed | Canonical feedback-routing proposal: classify live quest feedback by intent and route to clarify, replan, second-opinion, or escalation paths deliberately. |
| `2026-04-13-instruction-architecture.md` | proposed | Unified proposal for Quest instruction architecture: selective rule-pack loading, canonical policy ownership, workflow-first skill structure, prompt assembly/debugging, and migration plan. Supersedes focused-rule-packs and orchestration-improvement-workflow. |
| `2026-04-13-quest-memory-architecture.md` | proposed | Canonical memory architecture proposal: operational and reflective memory layers, structured records, narrow retrieval, freshness model, and strict guardrails. |
| `2026-04-13-quest-memory-evaluation-loop.md` | proposed | Local benchmark design for proving whether Quest memory retrieval actually improves relevance, efficiency, and hallucination resistance versus plain filesystem exploration. |
| `quest-file-attribution-line.md` | idea | File-level Quest attribution and license provenance line. |
| `quest-multi-phase-execution.md` | proposed | Recommended pattern for handling large multi-phase initiatives: umbrella planning quest, then separate phase quests unless the passes still feed one bounded deliverable set. |
| `quest-preflight-sandbox-false-negative-bugfix.md` | in-progress | Host-context probe caching and diagnostics shipped; fallback classification/reporting is still not fully explicit. |
| `quest-requiem-ceremony.md` | idea | Add a reflective archive/abandon ceremony that mirrors completion celebration. |

### Codex and Operations Notes
| File | Status | Purpose |
|---|---|---|
| `codex_calls_claude.sh` | reference | Older experimental bash bridge prototype retained as a reference alongside the supported Python bridge. |
| `2026-07-05-bg-claude-ask-policy-relaxation.md` | proposed | Define when a bg Claude role may write `needs_human` (destructive ambiguity, credentials, genuine product decisions) and encode it in the role agent files; the relay mechanism itself shipped in PR #142. |

### Execution Discipline and Observability
| File | Status | Purpose |
|---|---|---|
| `2026-04-15-claude-insights-priorities.md` | proposed | Canonical Tier/Skip index mapping evaluation suggestions to sanity-checked Quest proposals. |
| `2026-04-15-claude-rule-never-dismiss-acceptance-criteria.md` | proposed | Guardrail against rejecting explicit acceptance criteria as optional. |
| `2026-04-15-pr-create-checklist-via-pr-assistant.md` | proposed | PR checklist workflow via existing `pr-assistant` to avoid duplicate skill drift. |
| `2026-04-15-precommit-status-diffstat-discipline.md` | proposed | Pre-commit staging verification discipline with optional bounded hook. |
| `2026-04-15-tool-failure-two-attempt-cap.md` | proposed | Two-attempt cap rule for failing tool investigations to limit rabbit-holing. |
| `2026-04-29-test-driven-bug-fix-loops.md` | proposed | Safer bug-fix mode: failing test first, bounded distinct strategies, preserved attempt evidence, and no destructive rollback. |
| `2026-04-15-autonomous-pr-shepherd-headless.md` | idea | Long-horizon autonomous PR shepherd design with strict safety boundaries. |

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
| done | ~~deterministic-json-orchestration-overrides~~ | Implemented in PR #144: deterministic parser API and stdin CLI, pair/JSON compatibility, duplicate and delimiter validation, and equivalent orchestration output across accepted formats. Archived at [`ideas/archive/deterministic-json-orchestration-overrides.md`](archive/deterministic-json-orchestration-overrides.md). |
| done | ~~quest-needs-human-resume-relay~~ | Full same-session relay shipped in PR #142 (items 0–6); item 7 (ask-policy) continues as `2026-07-05-bg-claude-ask-policy-relaxation.md`. Archived at [`ideas/archive/quest-needs-human-resume-relay.md`](archive/quest-needs-human-resume-relay.md). |
| done | ~~2026-07-04-bg-transport-hardening-quest-brief~~ | Shipped in PR #142 (quest bg-transport-hardening_2026-07-04__1043): truthful block-cause classification, verified teardown, leak-proof sweeps, needs_human same-session relay, end-to-end model passthrough, docs accuracy sweep. Archived at [`ideas/archive/2026-07-04-bg-transport-hardening-quest-brief.md`](archive/2026-07-04-bg-transport-hardening-quest-brief.md). |
| done | ~~2026-07-03-claude-model-alias-dispatch-bug~~ | Resolved in PR #142: the `claude` sentinel never reaches the CLI as `--model claude`, concrete IDs pass verbatim, rejection reports `model_rejected` naming the model. Archived at [`ideas/archive/2026-07-03-claude-model-alias-dispatch-bug.md`](archive/2026-07-03-claude-model-alias-dispatch-bug.md). |
| done | ~~2026-05-31-codex-driven-interactive-claude-relay~~ | Implemented: Step 1 standalone `claude --bg` runner (PR #136) + Step 2 Quest wiring with `claude_role_transport: auto` default. Archived at [`ideas/archive/2026-05-31-codex-driven-interactive-claude-relay.md`](archive/2026-05-31-codex-driven-interactive-claude-relay.md). |
| done | ~~2026-05-26-native-runtime-dispatch~~ | Encoded in the canonical dispatch matrix (`.skills/quest/delegation/workflow.md`) and `select_role_runtime()`. Archived at [`ideas/archive/2026-05-26-native-runtime-dispatch.md`](archive/2026-05-26-native-runtime-dispatch.md). |
| superseded | ~~2026-05-31-quest-model-capability-improvements~~ | Transport portion landed with the `claude --bg` migration; measurement items re-proposable individually. Archived at [`ideas/archive/2026-05-31-quest-model-capability-improvements.md`](archive/2026-05-31-quest-model-capability-improvements.md). |
| archived | ~~claude-cli-login-context~~ | Reference note; operative guidance moved to `docs/guides/quest_setup.md` + preflight host-context checks. Archived at [`ideas/archive/claude-cli-login-context.md`](archive/claude-cli-login-context.md). |
| archived | ~~claude-bridge-timeout-diagnosis-2026-03-23~~ | Incident encoded as the migration spec's dispatch false-positive finding and the preflight live-probe design. Archived at [`ideas/archive/claude-bridge-timeout-diagnosis-2026-03-23.md`](archive/claude-bridge-timeout-diagnosis-2026-03-23.md). |
| done | ~~2026-05-30-pre-pr-freshness-and-force-push-guard.md~~ | Implemented shared pre-PR default-branch sync helper and skill wiring. See [journal](../docs/quest-journal/pre-pr-sync_2026-05-31.md). |
| won't-do | ~~2026-04-15-pretooluse-branch-dir-verification-hook~~ | `PreToolUse` stdout is debug-log-only (invisible), reads orchestrator cwd not the edit target, and never fires under Codex/MCP. Statusline covers the intent on the Claude side. Built + closed in PR #116. Archived at [`ideas/archive/2026-04-15-pretooluse-branch-dir-verification-hook.md`](archive/2026-04-15-pretooluse-branch-dir-verification-hook.md). |
| won't-do | ~~2026-04-15-claude-rule-confirm-pwd-branch-before-edits~~ | Soft "run `pwd`/`git branch` before edits" prose — no enforcement, instruction sprawl, visibility already covered by statusline. Retired with the hook (PR #116). Archived at [`ideas/archive/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md`](archive/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md). |
| won't-do | ~~2026-04-15-subagent-path-constraints-hardening~~ | Superseded — `quest_validate-quest-state.sh` already blocks transitions on missing/misplaced canonical artifacts (both runtimes); PR #116's second validator was inert + redundant. Residual failure-diagnostics belong to `handoff-validation-and-failure-ux`. Archived at [`ideas/archive/2026-04-15-subagent-path-constraints-hardening.md`](archive/2026-04-15-subagent-path-constraints-hardening.md). |
| done | ~~2026-04-20-runner-cwd-path-hygiene~~ | `cwd` double-apply fixed in PR #96; 2026-05-30 sweep found no remaining instances. Archived at [`ideas/archive/2026-04-20-runner-cwd-path-hygiene.md`](archive/2026-04-20-runner-cwd-path-hygiene.md). |
| done | ~~2026-05-14-pr-shepherd-operational-intake~~ | Implemented PR targeting, idempotent reply markers, compact PR intake scripts, failed-log records, scope annotation, and operational stop states. Archived at [`ideas/archive/2026-05-14-pr-shepherd-operational-intake.md`](archive/2026-05-14-pr-shepherd-operational-intake.md); see [journal](../docs/quest-journal/pr-shepherd-operational-intake_2026-05-15.md). |
| done | ~~2026-04-13-review-intelligence-canonical~~ | Phases 1-3 shipped: canonical findings/backlog, targeted validation/PR batching, and bounded Deep CI whole-file review. Archived at [`ideas/archive/2026-04-13-review-intelligence-canonical.md`](archive/2026-04-13-review-intelligence-canonical.md). |
| done | ~~deep-ci-review-context-manifest-plan~~ | Implemented as Review Intelligence Phase 3.2 in PR #101. Archived at [`ideas/archive/deep-ci-review-context-manifest-plan.md`](archive/deep-ci-review-context-manifest-plan.md). |
| done | ~~deep-ci-chunked-context-plan~~ | Implemented as Review Intelligence Phase 3.1 in PR #98. Archived at [`ideas/archive/deep-ci-chunked-context-plan.md`](archive/deep-ci-chunked-context-plan.md). |
| done | ~~deep-ci-whole-file-logic-review~~ | Implemented as Review Intelligence Phase 3; Codex CI now has bounded whole-file logic review for selected changed code files. Archived at [`ideas/archive/deep-ci-whole-file-logic-review.md`](archive/deep-ci-whole-file-logic-review.md). |
| done | ~~extract-codex-review-python~~ | Codex CI review Python now lives in `.github/scripts/codex_review.py`; workflow heredocs were removed. Archived at [`ideas/archive/extract-codex-review-python.md`](archive/extract-codex-review-python.md). |
| done | ~~generic-artifact-preparation-and-runtime-fallbacks~~ | Implemented on `codex-artifact-staging` / PR #74. Archived at [`ideas/archive/generic-artifact-preparation-and-runtime-fallbacks.md`](archive/generic-artifact-preparation-and-runtime-fallbacks.md). |
| done | ~~quest_dispatcher~~ | Quest now routes Codex-led Claude roles through the Quest runner/probe path with runtime logging and handoff polling. See [journal](../docs/quest-journal/quest-dispatcher_2026-03-09.md). |
| done | ~~codex-led-claude-bridge-runtime-hardening~~ | Codex-led Claude bridge runtime path shipped, documented, and exercised in a solo smoke test. See [journal](../docs/quest-journal/codex-led-claude-bridge-runtime-hardening_2026-03-09.md). |
| done | ~~codex-calls-claude~~ | Claude CLI bridge prototype graduated to supported script/runtime docs. See [journal](../docs/quest-journal/codex-calls-claude_2026-03-09.md). |
| done | ~~celebration-from-journal~~ | Quality tiers, embedded celebration_data JSON, dashboard integration. See [journal](../docs/quest-journal/celebration-from-journal_2026-03-06.md). |
| done | ~~pr-inline-commenting-playbook~~ | Kind, actionable PR inline comment playbook with signature convention. See [journal](../docs/quest-journal/pr-inline-commenting-playbook_2026-03-05.md). |
| done | ~~quest-state-transition-guardrails~~ | Atomic `--transition` flag, mandatory presentation gate enforced, helper-existence checks. Archived at [`ideas/archive/quest-state-transition-guardrails.md`](archive/quest-state-transition-guardrails.md). |
| done | ~~2026-04-13-quest-memory-retrieval-and-freshness.md~~ | Retired and merged into `2026-04-13-quest-memory-architecture.md`; moved to `.ws/`. |
| done | ~~2026-04-13-query-driven-review-memory.md~~ | Retired and merged into `2026-04-13-quest-memory-architecture.md`; moved to `.ws/`. |
| archived | ~~memory_bank_model~~ | Pre-canonical generic memory-bank primer; superseded by `2026-04-13-quest-memory-architecture.md`. Archived at [`ideas/archive/memory_bank_model.md`](archive/memory_bank_model.md). |

## Hygiene Rules
- Keep one file per idea family; avoid duplicate variants.
- Keep incident notes in `ideas/` only while they are actively informing roadmap work.
- If a note is superseded, delete it or merge it into the canonical idea file.
- If an idea is implemented, link the quest journal entry in the file and mark status accordingly.
