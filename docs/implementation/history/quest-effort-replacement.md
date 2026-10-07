# Quest effort replacement plan

Status: Complete. Implementation and validation finished under user authorization; draft publication handled by the coordinator.
Owner: replacement implementation coordinator. No full Quest workflow requested.

## Goal and scope

Make the effort requested for a Quest role explicit and pass it with the saved model at dispatch. Use the existing Claude background runner from either orchestrator. Keep configuration in the allowlist (defaults) and orchestration.json (quest snapshot), without generated agent Markdown effort.

This is a replacement for closed PR #179, not an instruction to repair or cherry-pick its whole branch. Preserve branch worktree-quest-effort-and-opus55 at 4e4aa756bcf6f03f650a9ddf845d6f3719e9fbcd as reference. Planning inspection used origin/main 2cf4d5815fae1af258af52097e851ae86288494e; fetch and record the actual base before building.

### Lessons and evidence

- Native Claude subagent effort frontmatter worked in the live low/high comparison on Claude Code 2.1.284. Do not justify migration by claiming native effort is broken.
- Background Claude role dispatch with saved medium effort produced valid review and handoff artifacts. Transcript metadata independently showed Opus 5.5 and medium.
- Claude-led Codex role dispatch produced valid artifacts with requested model/effort. Effective settings were not independently reported. Never relabel requested values as effective.
- A customized old agent file survived a successful partial install, then failed the new native effort guard. This proves the old design's upgrade failure, not that the replacement needs the same guard or installer redesign.
- 1389 tests passed on the old PR. Those results do not validate a replacement commit.
- Existing evidence: /tmp/quest179-validation-20260930.md; /tmp/quest179-acceptance-root and /tmp/quest179-install-gate-root point to disposable artifacts. Local temporary evidence may expire. Preserve a sanitized summary with exact tested revisions and runtime versions before relying on it in a PR.

### Included

Saved effort, runtime forwarding, Claude-led background dispatch, required preflight/instruction/permission integration, focused tests, installation acceptance, truthful documentation.

### Excluded

New runners, new configuration UI, automatic effort tuning, provider capability catalogs, cost/quality claims, review-mode changes, iteration-limit changes, automatic runtime fallback, broad installer redesign, removal of unrelated native-agent support. Model upgrades and builder-model changes are a separate decision/patch, not required to implement effort.

## Execution decisions

The user delegated implementation decisions with smallest-change and quality constraints. Coordinator decisions, independently challenged before building:

1. One flat effort.<role> map alongside models.<role>. The existing role model choices can span runtimes and require different effort levels; a single scalar would not cover that existing workflow. No new configuration UI or override grammar.
2. Shipped Claude and Codex roles use medium initially. This preserves current Codex policy and provides a supported, explicitly pinned Claude value. It is not a cost or quality claim. Model IDs remain unchanged from main. Repository owners can edit defaults; saved quests retain their chosen values.
3. Require effort for active Claude/Codex roles when dispatching and in newly saved configuration. New saved orchestration configs contain the map only, not codex_reasoning_effort. The allowlist scalar remains for standalone /gpt only; raw allowlist snapshots can contain it, but Quest snapshot restoration reads only the map. Older incompatible saved quests fail with restart/reconfigure guidance; no migration or fallback hierarchy. Null solo roles need no effort. Preserve unrelated existing migrations and standalone runner flags.
4. Gemini roles have no effort pin. Model-only chooser changes to Gemini explicitly report and remove the inherited default pin before saving; manually supplied unsupported pins fail visibly. Switching to supported runtimes requires a supported value before launch. No Gemini API additions.
5. Both orchestrators use background Claude dispatch by default. Existing explicit bridge support remains explicit, with no automatic fallback and no new API-billed acceptance calls.

The required-map decision was challenged: it is not necessary just to forward a flag, but one map without legacy scalar precedence keeps the accepted per-role feature coherent. Role-map validation must be mode-aware, not require nine active roles unconditionally.

## Acceptance criteria

- AC1: New quests save the approved effort with each active supported role. Resume uses that snapshot despite later allowlist edits. Invalid/missing required settings fail before launching a model, with a recovery instruction.
- AC2: Normal/default Claude dispatch under both orchestrators uses the same existing background runner; separately explicit bridge behavior already shipped on main remains unchanged. The launched request contains saved model/effort, role instructions, target workspace and canonical artifact paths. No generated effort frontmatter or native effort guard participates.
- AC3: Codex retains its established entrypoints: native subagent for Codex-led, role runner for Claude-led. Both receive saved effort; neither silently substitutes a model/runtime when controls are unavailable.
- AC4: Role instructions and existing permission boundaries survive the Claude entrypoint change. Missing setup, denied permission, malformed/missing handoff, timeout and teardown failure remain visible and do not become success or automatic fallback.
- AC5: A fresh installation and a representative customized older installation either complete with working dispatch or refuse with actionable guidance. No success followed by stale native-effort guard failure. Resume behavior matches section 1's approved contract.
- AC6: Replacement diff excludes unrelated policy/model changes. Validation evidence names the replacement SHA, requested versus observed settings, tests completed by agents, and remaining limitations. Humans are not asked to repeat passing agent-executable checks.

## Agent execution sequence

0. Coordinator preserves reference artifacts, verifies clean tree, fetches main, and creates a separate feature worktree for implementation. Do not reset/delete this branch or copy its entire tree. Transfer these plan documents to the replacement worktree. Record base SHA and plan decisions.
1. Before source implementation, an investigation agent completes the read-only prompt/tool-permission feasibility mapping at the start of the dispatch slice. If preserving existing restrictions needs a new permission framework, stop and reassess the transport decision now. Coordinator then resolves the configuration decisions above and hands off [configuration slice](quest-effort-configuration.md). One source-writing agent owns this slice.
2. Independent reviewer challenges the slice: is each new branch necessary, is source-of-truth preserved, and do tests catch a real failure? Findings must cite a path and observable scenario. Coordinator resolves substantive findings before continuing.
3. Builder implements [dispatch and acceptance slice](quest-effort-dispatch.md). Preflight, saved settings, prompt/permissions and dispatch are one vertical change; do not publish an intermediate commit as ready while docs and execution disagree.
4. Independent reviewer examines the complete replacement against the accepted scope and actual diff from main. Review must explicitly look for copied compatibility machinery, extra policy changes and weakening of role permissions. No source writes by reviewer.
5. Validation agent runs deterministic checks plus bounded live acceptance in disposable repositories. It writes a result ledger; coordinator fixes failures and reruns only affected checks before final full checks.
6. Coordinator presents result and remaining limitations. Prepare a replacement draft PR under the repo PR workflow when requested/authorized; do not reopen #179. Include lessons and validation evidence, link closed #179. Do not merge. Move these plans to history only when acceptance criteria are met.

Parallelism: independent read-only investigation/review may run together. After feasibility and the shared helper contract were settled, configuration and dispatch edits run in parallel with disjoint ownership. Configuration owns orchestration.py and Codex consumption; dispatch owns workflow.md and Claude runtime/preflight. Startup effort lines belong to configuration until handoff. No overlapping writers.

Every agent handoff includes: approved scope/decisions, absolute replacement-worktree path, base/head SHA, owned files, acceptance criteria, evidence paths, commands and exit codes, unresolved blockers. Each agent reads AGENTS.md and relevant canonical .skills instructions first. Relative file paths in slice docs resolve under that explicit worktree; never edit the reference branch accidentally.

## Risks and stop rules

| Risk | Impact / likelihood | Mitigation |
| --- | --- | --- |
| Background sessions lose native role prompt/tool restrictions | High / medium | Trace prompt and permissions before editing; live read-only and write-role cases. Stop if existing runner cannot preserve necessary boundaries without a new permission system. |
| Configuration flexibility grows into another framework | Medium / high | Resolve five decisions once; one map, one resolver, no new UI or fallback hierarchy. |
| Saved settings appear forwarded but runtime ignores them | High / medium | CLI argument capture plus independent runtime metadata where available. Unknown stays unknown. |
| Existing/customized installs retain incompatible dispatch instructions | High / medium | Disposable install acceptance; minimum targeted refusal/update only for a reproduced incompatibility. |
| Existing roles regress while transport docs alone look correct | High / medium | Startup probe, role instruction, handoff and failure-path validation across both orchestrators. |

If preserving instructions/permissions requires a new runner, permission architecture or broad installer rewrite, stop that slice and present concrete evidence and a smaller alternative. Do not silently expand scope. Ordinary discovered implementation details do not require another approval round.

## Independent plan review

A read-only reviewer challenged this plan against current source and main. Incorporated corrections: new configs must remove the old scalar when introducing the map, default background dispatch must be distinguished from explicit bridge support, and prompt/permission feasibility must precede configuration implementation. The reviewer found installer scope and model-default exclusions appropriately narrow. Full required maps remain a product decision, not a proven prerequisite of forwarding. The coordinator resolved the decision table under the user's execution authorization; source changes remain sequenced behind the feasibility check.

## Execution tracker

- [x] Step 0: Preserve old branch and create fresh feature worktree.
  - status: done
  - notes: feat/quest-effort-dispatch from main 2cf4d5815fae1af258af52097e851ae86288494e. PR #179 closed by user request.
  - tests: git status and worktree verification
  - ac_coverage: AC6
- [x] Step 1: Feasibility and configuration contract.
  - status: done
  - notes: Local and outside-in background persona probes loaded exact wrapper instructions and tool schema; requested model/effort independently observed in transcripts. Existing CLI controls suffice.
  - tests: Two live subscription probes, clean teardown; baseline main 1316 tests passed.
  - ac_coverage: AC2, AC4

- [x] Step 2: Configuration implementation and independent review.
  - status: done
  - notes: Required saved map, snapshot/resume contract, standalone /gpt preserved; independent review addressed outside-in import and fixture gaps.
  - tests: Focused suites plus full Python run 1351 passed; orchestration 36/36 and state 72/72.
  - ac_coverage: AC1, AC3
- [x] Step 3: Dispatch implementation and independent review.
  - status: done
  - notes: Saved settings forwarded through existing background runner/persona; both orchestrators probe Claude; saved transport preserved on resume.
  - tests: Runtime/background/guardrails 181 passed; preflight 26/26; runtime shell 72/72; independent Codex and live Claude code reviews.
  - ac_coverage: AC2, AC3
- [x] Step 4: Deterministic and live acceptance, review fixes.
  - status: done
  - notes: Upgrade/refusal/recovery, real Claude review and cross-runtime child dispatch passed. Inherited cleanup defect corrected and live-verified, including delayed absence. Draft publication follows completed validation.
  - tests: Final 1356 Python tests, all shell checks, Black, manifest/config checks; live evidence in validation ledger.
  - ac_coverage: AC4, AC5, AC6

## Review decisions during implementation

- Installer acceptance reproduced two partial upgrades: missing effort in preserved allowlists, and a customized old workflow retained beside the new runtime. Added pre-mutation refusal for the required effort-map format and for locally customized copy-as-is framework files whose upstream version changed. Use the existing checksum contract rather than a new version registry or a brittle list of dispatch paths. Unchanged upstream custom files remain supported. The manifest keeps its existing safe backup/replacement path. This deliberately changes skip-modified behavior for conflicting framework updates; help and setup guidance disclose it.
- Independent code review caught outside-in state-validator import resolution and saved-transport resume drift. Fixed both at their existing boundaries. Retired a now-unused native-Claude availability parameter and consolidated runner invocation guidance.
- Existing regression fixtures were updated to include valid saved effort so they continue testing their original state, artifact and retry contracts. Assertions were not weakened.

- Live acceptance also reproduced an inherited cleanup defect on unchanged main: the PID-signaling cleanup reported settlement while the daemon retained the session. The precise timing of the false-settled observation was not captured; a PID-less worker gap is one failure mode reproduced deterministically. Six surviving test sessions were removed successfully with supported `claude stop`. The replacement uses that command and bounded roster verification, rather than introducing a new lifecycle or a PID fallback. This small correction is necessary to make the expanded background dispatch reliably finish.

Validation ledger: [completed checks, live evidence and limitations](quest-effort-validation.md).

Validation scope decision: native Codex uses the existing unchanged tool entrypoint. Current tests cover required saved-pin resolution and dispatch selection; earlier live native controls evidence is retained as historical, not relabeled as a replacement-commit test. Effective Codex metadata remains unobserved.
