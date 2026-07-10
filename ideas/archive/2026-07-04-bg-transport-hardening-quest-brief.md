---
title: Quest Brief — Harden the Claude background-agent transport
purpose: Ready-to-run quest prompt fixing the six confirmed bg-transport defects from the 2026-07-03/04 incidents.
audience: Quest orchestrator (Claude-led or Codex-led) and human maintainers.
scope: scripts/claude_bg_run.py, scripts/quest_runtime/claude_runner.py, scripts/quest_claude_runner.py, scripts/quest_preflight.sh, .skills/quest/delegation/workflow.md, scripts/quest_installer.sh
status: shipped — PR #142 (quest bg-transport-hardening_2026-07-04__1043); all six work items + docs workstream implemented; the rate_limited park-until-reset stretch was explicitly de-scoped in the approved plan
owner: maintainers
---

# Quest Brief: Harden the Claude Background-Agent Transport

## Incident evidence (2026-07-03 / 2026-07-04, verified on a live machine)

1. **Session-limit dialog misdiagnosed as a permission problem.** Two quest
   arbiter sessions (difflyx, `quest-rel1-...-arbiter-i1`) parked with
   `state=blocked, waitingFor="dialog open"`. Their transcripts end with
   *"You've hit your session limit · resets 2pm (America/Chicago)"* — an OAuth
   subscription rate limit. The runner reported *"session is blocked on an
   interactive prompt (a permission hook likely did not cover it)"* and the
   probe classified it `invocation_error`. A Codex orchestrator, reading that
   stderr at face value, prescribed re-accepting bypassPermissions — the wrong
   fix. The true cause was present but unclassified in `logs_tail`.
2. **Startup-dialog park, distinct signature, same misreport.** Three preflight
   probes (internal-delivery-metrics-automation) parked blocked with **no
   transcript file at all** — the session never consumed its initial prompt
   (trust/bypass acceptance dialog at startup; `hasTrustDialogAccepted: false`
   for that repo in `~/.claude.json`). Script output is identical to case 1.
3. **Runtime sentinel passed as CLI model.** A live dispatch ran
   `claude ... --model claude`. The CLI rejected it — *"There's an issue with
   the selected model (claude)"* — and the run surfaced as a generic `timeout`
   (exit 5). Full report: `ideas/2026-07-03-claude-model-alias-dispatch-bug.md`.
4. **Silent teardown failure + daemon respawn = leaks.** Six blocked sessions
   (some 22+ days old) were alive in `claude agents --json`. One SIGTERM round
   respawned ALL of them with fresh pids from the daemon spare pool; retirement
   required re-signalling each row's *current* pid until it settled.
   `stop_session()` already loops, but gives up silently and the envelope never
   reports teardown failure. Probe sessions named `quest-bg-probe-tmp.*` are
   never covered by any sweep (sweep keys on `quest-<id>-`).
5. **Duplicate dispatch onto a parked name.** Two sessions with the identical
   name `...-arbiter-i1` existed simultaneously: a retry dispatched while the
   first was parked on the limit dialog; nothing stopped the first.
6. **Stale CLI assumptions.** Claude CLI 2.1.201 has **no** `claude stop` or
   `claude logs` subcommands, contrary to docstrings in
   `scripts/claude_bg_run.py` (they claim 2.1.191 added them). pid-signalling
   and transcript JSONL remain the only mechanisms. Also, the installer does
   not ship `docs/guides/quest_setup.md`, which
   `.skills/quest/delegation/workflow.md` references — installed repos get a
   dangling pointer.

## Quest prompt (paste into /quest)

> Harden the Claude background-agent transport so failures are diagnosed
> truthfully, sessions never leak, and the human's model choice is honored
> end-to-end. Ground every change in
> `ideas/2026-07-04-bg-transport-hardening-quest-brief.md` (incident evidence)
> and `ideas/2026-07-03-claude-model-alias-dispatch-bug.md`. Scope:
>
> **1. Classify the real block cause in `scripts/claude_bg_run.py`.**
> When the WAIT loop sees `state=blocked`, distinguish:
> (a) **rate_limited** — transcript/`logs_tail` matches a session/usage-limit
> message (e.g. "You've hit your session limit · resets <time>"); parse and
> surface the reset time; new envelope status `rate_limited` with its own exit
> code; (b) **startup_dialog** — the session has no transcript file / never
> consumed the prompt (trust or bypass-acceptance dialog at startup);
> (c) generic **blocked** otherwise. Never emit "a permission hook likely did
> not cover it" as a guess.
>
> **2. Make every failure envelope carry cause-matched remediation.**
> `waitingFor` detail and `logs_tail` are already captured — use them.
> rate_limited → "wait for reset at <time>, or re-run with a different/cheaper
> model (human's choice)"; startup_dialog → "open claude interactively once in
> <cwd> and accept the trust/bypass dialog"; model_rejected (see item 6) →
> name the rejected model. Extend `classify_bg_probe_failure()` in
> `scripts/quest_runtime/claude_runner.py` with `rate_limited`,
> `startup_dialog`, and `model_rejected` kinds, and map `rate_limited` to a
> retry-after-reset result kind — not `invocation_error` — so the retry ladder
> stops prescribing bypass re-acceptance for limits.
>
> **3. Verify teardown; never fail silently.** `stop_session()` must confirm
> the row settled (pid dropped or row gone) and the envelope must report
> `teardown_failed: true` plus the surviving id when it did not — observed
> behavior is that the daemon respawns killed sessions once from its spare
> pool, so re-signal the row's current pid until settled. Correct the stale
> docstrings: Claude CLI 2.1.201 has no `claude stop`/`claude logs`
> subcommands; pid-signalling and transcript JSONL are the real mechanisms
> (keep a capability probe so real subcommands are adopted if/when they ship).
>
> **4. Close the sweep gaps and the duplicate-dispatch hole.** Preflight and
> quest start must sweep `quest-bg-probe-*` sessions (they are named from
> mktemp quest dirs, so the `quest-<id>-` sweep never matches them), and
> preflight must clean up its own probe on every exit path. Before
> dispatching, if a live session with the same `--name` is already parked,
> stop it first (or fail with a clear message) — never create a second session
> under the same name.
>
> **5. Wire the interactive needs_human relay into quest (Step 3).**
> `claude_bg_run.py` already supports park + `--resume <ref> --answer`. Per
> `ideas/quest-needs-human-resume-relay.md`, replace the
> `--teardown-on-needs-human` stopgap for Codex-led Claude roles: on
> needs_human, keep the session parked, surface the question to the human,
> resume the SAME session with the answer, and define the parked-session
> lifecycle (sweep on quest end/abandon so parked sessions cannot leak). This
> is the "as interactive as possible" requirement. Stretch: for rate_limited,
> offer park-until-reset + resume as an alternative to teardown.
>
> **6. Honor the human's model choice end-to-end — no silent defaults.**
> Policy: the human picks the model; the scripts obey and report.
> - `models.<role> = "claude"` is a runtime-family sentinel, never a CLI
>   model: when in effect, OMIT `--model` so the account default applies
>   (today it becomes `--model claude`, which the CLI rejects).
> - A concrete configured model (`opus`, `sonnet`, `claude-opus-4-8`, a full
>   model ID) must flow verbatim: allowlist/orchestration.json → workflow →
>   `scripts/quest_claude_runner.py` → `claude_bg_run.py`/bridge. Remove the
>   hardcoded `default="opus"` in `scripts/quest_claude_runner.py` and
>   `scripts/quest_claude_probe.py`: require an explicit model or the explicit
>   sentinel (→ omit flag). Update
>   `.skills/quest/delegation/workflow.md` so the orchestrator actually passes
>   `--model` from `models.<role>` — today it never does and the default wins
>   regardless of config.
> - Do NOT auto-downgrade to a cheaper model on limits; instead surface the
>   option so the human can change the configured model and re-run.
> - Detect CLI model rejection ("There's an issue with the selected model
>   (<m>)") as `model_rejected`, not a generic timeout.
> - The preflight probe must use the same model-resolution semantics as role
>   dispatch, so a green preflight cannot be invalidated by a model mismatch.
>
> **Housekeeping (small, in scope):** ship `docs/guides/quest_setup.md` in
> `scripts/quest_installer.sh` or repoint the workflow reference; keep
> `claude_bg_run.py` quest-agnostic (no quest imports).
>
> **Acceptance criteria:**
> - Unit tests cover: limit-message classification (with reset-time parsing),
>   no-transcript startup_dialog detection, model_rejected detection, sentinel
>   → omitted `--model`, concrete model passthrough, teardown-failure
>   reporting, respawn-loop retirement, probe sweep, same-name dispatch guard.
> - `build_bg_cmd()`/`build_bridge_cmd()` never emit `--model claude`.
> - A rate-limited run reports `rate_limited` with the reset time in the
>   envelope and a retry-after-reset result kind in the quest ladder.
> - A parked needs_human role resumes the same session with the human's
>   answer, and quest end/abandon sweeps any still-parked sessions.
> - No new blocked session remains in `claude agents --json` after any runner
>   exit path (verified in an integration-style test with a fake roster).

## Non-goals

- Structured-output (`--json-schema`) artifacts, per-role permission
  enforcement (tracked separately in the migration spec).
- Changing default role models or billing policy — model choice stays with
  the human.
- Deleting the bridge; it remains the explicit API-metered fallback.

## Related

- `ideas/2026-07-03-claude-model-alias-dispatch-bug.md` — model sentinel bug
- `ideas/quest-needs-human-resume-relay.md` — relay design + measurement gate
- `docs/implementation/claude-bg-transport-migration.md`, `claude-bg-run-script.md`,
  `claude-bg-transport-step2-wiring.md` — transport specs
- PRs #136, #137, #141 — prior bg-transport steps
