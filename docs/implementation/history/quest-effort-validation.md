# Quest effort replacement validation

Status: Complete. Independent reviews addressed, final deterministic and live acceptance passed within the boundaries below. Replacement of closed PR #179, built from main 2cf4d5815fae1af258af52097e851ae86288494e.

## Scope and evidence

The change pins role effort in saved orchestration and routes Claude roles through the existing background runner under either orchestrator. Models, review mode, iteration limits and standalone /gpt effort policy remain unchanged. No generated effort in agent Markdown or native effort synchronization guard.

Native Claude effort was already functional. The reason for background dispatch is one explicit saved-settings path, not a claim that native effort is broken. Actual tests, rather than token-count comparisons or agent self-report, establish the observations below.

## Checks completed by agents

- Unchanged main baseline: 1316 Python tests passed.
- Final replacement Python run after review fixes: 1356 passed in 188.34 seconds. The suite includes configuration, runtime, lifecycle and installer regressions.
- Orchestration shell: 36/36. State shell: 72/72. Runtime shell: 72/72. Preflight: 26/26. Handoff contract checks: 3/3.
- Generated-model check, configuration validator, manifest validator, Black and whitespace checks passed.
- Independent implementation reviews covered configuration, dispatch, installation and KISS/scope. A real Claude code-reviewer role reviewed the full patch and source. Findings were addressed: preserve manifest backup/replacement, disclose changed installer refusal behavior, remove obsolete native availability parameter, consolidate invocation guidance, fix outside-in imports, and preserve saved transport policy on resume.

## Live acceptance

Runtime versions: Claude Code 2.1.286 and Codex CLI 0.159.3. Synthetic acceptance used disposable repositories and existing authenticated background/cached sessions. The independent code-review role read the actual candidate source worktree and wrote only external review artifacts. No API bridge inference was used.

| Case | Requested settings | Independent observation | Result |
| --- | --- | --- | --- |
| Local Claude persona | Opus 5.5, medium | Transcript system prompt equals wrapper body; actual tools Read/Write/Glob/Grep; model and effort metadata match | Passed |
| Outside-in Claude persona | Opus 5.5, medium | Same body/tool proof with installation and target directories separate | Passed |
| Codex-led real Claude code review | Opus 5.5, medium | Role produced markdown, canonical findings and handoff; source review completed | Passed |
| Claude-led Claude builder | Parent medium, child Opus 5.5 high | Parent invoked role runner, no native Agent call; child metadata high; canonical builder instructions loaded from installation; Edit changed OLD to NEW; exact approved Bash test returned VALUE_CHECK_OK | Passed |
| Claude-led Codex builder | GPT-6 Astra, medium, cached auth | Requested settings recorded, synthetic CODEX_ROLE_OK source and three canonical artifacts, Codex cleanup complete | Passed; effective model/effort not reported |
| Controlled permission denial | Claude builder high | Unapproved chained shell command blocked; no source edit and no automatic runtime fallback | Passed failure propagation |

Native Codex entrypoint selection and required saved-pin handling are covered by deterministic tests and review. The earlier #179 native-subagent smoke established that explicit tool controls could launch the requested model/effort; it is historical evidence, not a replacement-commit live test. No claim of independently observed effective Codex effort is made.

### Cleanup finding and correction

Initial live runs revealed an inherited defect: both unchanged-main and replacement runners reported successful PID-based teardown while owned background processes survived. The failure was reproduced on actual sessions, not inferred from silence. All six survivors were explicitly stopped using the supported CLI command.

The narrow correction calls `claude stop` once and verifies session removal through bounded, structurally valid roster reads. Missing PIDs and invalid/unavailable roster responses no longer establish success. Intentional needs_human parking remains unchanged. The fresh fixed-runner retest completed in 16.3 seconds with observed Opus 5.5 high effort and the expected restricted persona tools. Its session was absent immediately and 44.1 seconds later, with no manual stop. Lifecycle tests cover nonzero, unavailable and malformed roster responses as unverified cleanup, not success.

## Installation acceptance

Actual full installer flow was exercised with local upstream payloads replacing network fetches; only optional global Codex setup was suppressed.

- Fresh install succeeds and installed writer saves effort.
- Existing allowlist without the required effort object refuses before any repository changes; error names a pinned defaults URL.
- After explicitly merging effort, pristine installations, customized allowlists and unchanged-upstream native wrappers install successfully.
- A changed customized workflow refuses before any writes. A byte-for-byte file-tree comparison confirms the refusal leaves the target unchanged.
- Backing up and replacing that workflow from the named source allows installation; the installed writer saves effort and the updated workflow specifies background dispatch. This recovery check did not launch a model from the recovered installation.
- A modified manifest still takes the existing backup-and-replace path; its exact previous bytes are preserved in the backup.

## Review boundaries

The initial medium default is policy, not a measured cost/quality optimum. Model availability beyond tested runtime selections is not inferred. Role personas preserve their native tool surfaces; neither add-dir nor prose is claimed to enforce filesystem containment. The API bridge remains explicit and received deterministic interface coverage only.

Passing mechanical checks above do not need human repetition. Human review should assess the configured effort defaults and deliberate upgrade/resume policy.
