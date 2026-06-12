---
title: Claude Background-Agent Transport — Migration Spec
purpose: Define exactly what must change to move Codex-led Claude role execution from the `claude --print` bridge to the official background-agent surface (`claude --bg` + per-user supervisor), and why the bridge is demoted to fallback rather than deleted.
audience: Quest maintainers and the implementing quest.
scope: Transport layer only — the runner entrypoint, handoff contract, and role prompts are unchanged.
status: active — being implemented per claude-bg-transport-step2-wiring.md (see Revisions)
owner: maintainers
last_updated: 2026-06-11
related:
  - docs/implementation/claude-bg-transport-step2-wiring.md
  - docs/implementation/claude-bg-run-script.md
  - ideas/archive/2026-05-31-codex-driven-interactive-claude-relay.md
  - ideas/archive/2026-05-26-native-runtime-dispatch.md
  - ideas/archive/2026-05-31-quest-model-capability-improvements.md
  - ideas/archive/claude-cli-login-context.md
  - scripts/quest_claude_bridge.py
  - scripts/quest_claude_runner.py
  - scripts/quest_runtime/claude_runner.py
  - scripts/quest_preflight.sh
  - .skills/quest/delegation/workflow.md
---

# Claude Background-Agent Transport — Migration Spec

## Revisions (2026-06-11)

Step 1 landed (#136) and changed three things this spec assumed; the execution
plan in `docs/implementation/claude-bg-transport-step2-wiring.md` supersedes the
corresponding details below:

1. **T1–T5 live in `scripts/claude_bg_run.py`, not in `quest_runtime/claude_runner.py`.**
   The standalone runner already encapsulates dispatch confirmation, file-based
   completion, teardown, and the resume relay — the quest runtime invokes it as
   a subprocess exactly like the bridge (one selector, two argv builders), so no
   `dispatch_bg()` is added to `claude_runner.py`.
2. **`claude logs|stop|rm` do not exist as subcommands** on the current CLI
   (2.1.173) — they parse as a *prompt* and silently no-op. Teardown signals the
   `pid` carried in the session's `agents --json` row until the row settles;
   logs come from the transcript JSONL. Fact 3 below and every stop/rm mention
   are corrected accordingly (see Step-1 doc, findings F1/F9).
3. **Rollout collapsed to auto-from-day-one** (user decision, 2026-06-11): the
   dark-launch phase's purpose was served by Step 1's live end-to-end
   validation, so the repo ships `claude_role_transport: "auto"` directly.
   Phases 0–2 below are historical; Phase 3 (post-soak review of the bridge's
   CI/API role) still stands.

## Goal

After June 15, 2026, `claude --print` (the current bridge transport,
`scripts/quest_claude_bridge.py:132`) bills to the metered Agent-SDK credit pool
at API rates. Background-agent sessions (`claude --bg`, hosted by the per-user
supervisor) bill to the **subscription pool** ("background sessions consume your
subscription usage the same as interactive sessions" — agent-view.md,
Limitations). This spec migrates Codex-led Claude role execution to the
background-agent transport as the **default**, with the bridge demoted to an
explicit fallback.

**Design invariant:** the swap happens entirely *underneath*
`scripts/quest_claude_runner.py`. The runner stays the orchestration entrypoint;
role prompts, artifact preparation, `handoff.json` polling, the three-tier
fallback ladder, and `context_health.log` keep their existing contracts. Only
the mechanism that gets a prompt to a Claude process changes. Claude-led
sessions (native `Task(...)`) are untouched.

## Verified facts this spec rests on

Checked live in this repo's environment (Claude Code 2.1.159, auto-updated to
2.1.170 mid-session) and against `code.claude.com/docs/en/agent-view.md`:

1. `claude --bg "<prompt>"` dispatches a detached background session and prints:
   `backgrounded · <shortID> [· <name>]` plus the management commands. Confirmed
   live (an idle no-prompt dispatch printed `backgrounded · e590de4c (idle — send
   a prompt to start)`).
2. `claude agents --json` prints live sessions as a JSON array
   (`pid, cwd, kind, startedAt, sessionId[, name, status]`) and needs no TTY.
3. `claude attach|logs|stop|respawn|rm <id>` and `claude daemon status` exist.
   State lives in `~/.claude/jobs/<id>/state.json` + `~/.claude/daemon/roster.json`.
4. Billing: subscription pool, verbatim quote above; the supervisor
   "authenticate[s] with the same credentials as your interactive sessions."
5. **Dispatch can false-positive.** In this sandboxed container the `--bg`
   dispatch printed success while `claude daemon status` reported `not running`,
   `control.sock unreachable`, `0 bg workers`, and the session never appeared in
   `agents --json`. The success line alone is NOT proof of dispatch.
6. **Research-preview churn is real.** The feature is flagged research preview
   (v2.1.139+); the CLI auto-updated 2.1.159 → 2.1.170 during a single working
   session. `--bg` is not yet listed in `claude --help` even though it works.
7. Background sessions auto-move into a Claude-created git worktree under
   `.claude/worktrees/` before editing files; `claude rm` can delete that
   worktree including uncommitted changes. `worktree.bgIsolation: "none"`
   (v2.1.143+) disables this; the `--settings` flag carries into dispatched
   sessions.
8. `bypassPermissions`/`auto` are refused for background sessions "until you
   have accepted that mode by running claude with it once interactively" —
   one-time per machine.
9. There is no `--bg` proof-of-concept in the repo today. Both existing scripts
   (`scripts/quest_claude_bridge.py`, `ideas/codex_calls_claude.sh`) are
   `--print`-based.

## Architecture: before and after

```
BEFORE (bridge)
  orchestrator (Codex)
    └─ quest_claude_runner.py ──► quest_claude_bridge.py ──► claude --print  [blocks]
         └─ polls handoff.json + artifacts (claude_runner.run_claude_role)

AFTER (background-agent default, bridge fallback)
  orchestrator (Codex)
    └─ quest_claude_runner.py ──► transport selected from orchestration.json/preflight
         ├─ background-agent:  claude --bg ... ──► supervisor-hosted session  [detached]
         │     └─ SAME poll loop on handoff.json + artifacts
         │     └─ NEW side-channel: claude agents --json (status), claude logs (diagnostics)
         └─ bridge (fallback): quest_claude_bridge.py ──► claude --print      [unchanged]
```

## The background-agent transport contract

### T1. Dispatch

```bash
claude --bg \
  --name "quest-<quest_id>-<agent>-i<iter>" \
  --model <models.<role> from orchestration.json> \
  --permission-mode bypassPermissions \
  --settings '{"worktree":{"bgIsolation":"none"}}' \
  --add-dir <repo_root> --add-dir <quest_dir> [--add-dir <extra>...] \
  "<prompt text>"
```

- The prompt is passed as the positional argument (Quest prompts are small by
  design — path references only). The runner reads it from `--prompt-file`
  exactly as today and passes the text through.
- `--name` is deterministic and unique (`quest-<id>-<agent>-i<iter>`); it is the
  recovery key for everything below.
- `--effort` may be added later per the deferred per-role effort proposal
  (`ideas/archive/2026-05-31-quest-model-capability-improvements.md`); not in scope here.

### T2. Dispatch confirmation (closes the false-positive gap — fact 5)

After the `--bg` command returns:

1. Parse `<shortID>` from the `backgrounded · <shortID>` stdout line (regex
   `backgrounded\s*·\s*([0-9a-f]+)`).
2. **Confirm within a short window (default 10s):** poll `claude agents --json`
   until an entry with the dispatched `name` (or `shortID`) appears. Capture its
   `sessionId`.
3. If parse fails but confirmation succeeds, proceed with the `agents --json`
   record (name lookup). If confirmation fails, classify as
   `invocation_error` → the existing ladder routes it (Tier C: bridge fallback).
4. Record `{short_id, session_id, name, dispatched_at}` to
   `.quest/<id>/logs/bg_sessions.jsonl` for teardown and orphan cleanup.

### T3. Completion detection (reuses today's loop)

The existing `run_claude_role` poll loop (`scripts/quest_runtime/claude_runner.py`,
handoff-state + artifact-completeness every 0.5s until deadline) is reused
unchanged as the **primary** signal: handoff.json found + artifacts complete →
success.

Add a low-frequency session-status check (every ~10s, one `claude agents --json`
subprocess) as the **secondary** signal:

| Session status / condition | Runner action |
|---|---|
| working | keep polling files |
| completed, handoff found | success (normal) |
| completed/failed, handoff missing | capture `claude logs <id>` tail to stderr context; classify via existing `classify_result_kind` (`handoff_missing` → ladder) |
| needs input | see T4 |
| absent from `agents --json` and no handoff | `invocation_error` (supervisor died / session evaporated) → ladder |

Timeout enforcement moves to the runner: `--bg` has no per-session timeout flag,
so the existing wall-clock deadline (default 1800s, same as the bridge) is
enforced by the runner issuing `claude stop <id>` at deadline, then classifying
`timeout` (existing ladder: retry-once-reduced-prompt, then blocked).

### T4. `needs input` policy

Quest's Claude roles signal questions via `STATUS: needs_human` in the handoff —
that path is unchanged. A background session stuck in `needs input` *without* a
handoff means an interactive blocker (typically a permission prompt) leaked
through. Policy:

1. Capture the question via `claude logs <id>` (tail).
2. `claude stop <id>`.
3. Treat as the existing `needs_human` route with the captured text as the
   question — never silently retry, never attempt TUI keystroke replies.
4. Prevention is primary: `bypassPermissions` + the one-time acceptance (fact 8)
   + pre-trusted workspace settings should make this path rare; its frequency is
   logged (see Logging) and reviewed.

### T5. Teardown and orphan cleanup

- On success or final failure: verify artifacts exist under `.quest/<id>/`
  (they always live in the repo, never in a Claude-created worktree, because
  `bgIsolation` is disabled and artifact paths are absolute), then
  `claude stop <id>` (if alive) and `claude rm <id>`. Order matters: never `rm`
  before artifacts are confirmed on disk (fact 7).
- **Orphan sweep:** at quest start and resume, list `claude agents --json` and
  `claude stop`/`rm` any session whose `name` matches `quest-<this quest_id>-*`
  but has no corresponding in-flight runner (stale from a crashed orchestrator).
  Sessions from *other* quests are left alone.

### T6. Worktree isolation (fact 7)

`--settings '{"worktree":{"bgIsolation":"none"}}'` on every dispatch. Rationale:
Quest already owns branch/worktree strategy at startup
(`scripts/quest_startup_branch.py`); a second, Claude-managed worktree layer
would split source edits from the orchestrator's workspace and is deleted by
`claude rm`. Artifact paths in prompts remain absolute (already required when
`source_workspace_root != repo root`).

Phase 0 must validate: (a) the settings flag is honored on dispatch, (b) writes
to gitignored `.quest/**` do not trigger a worktree move even without the
setting, (c) a write role (builder/fixer on Claude) edits the real workspace.

## Configuration: the hard switch

`.ai/allowlist.json` (and copied into `.quest/<id>/orchestration.json` by the
startup chooser, like `models.*`):

```jsonc
"claude_role_transport": "auto"   // default
// "auto"             → background-agent when preflight proves it; else bridge (downgrade recorded)
// "background-agent" → forced; preflight failure blocks with remediation (never silent bridge)
// "bridge"           → forced legacy/API path (CI, API-billing contexts)
```

This is a config value consumed by scripts — not workflow prose — so the
orchestrator cannot reinterpret it. The resolved transport and any downgrade are
written into `orchestration.json` (`claude_transport_resolved`,
`claude_transport_downgraded: bool`) at preflight time and logged.

`auto` is the recommended default: it makes background-agent the de-facto
replacement on developer machines while CI/sandboxes (like the environment that
produced fact 5) degrade loudly to the bridge.

## Preflight and probe changes

`scripts/quest_preflight.sh` (`probe_claude_bridge` → generalized
`probe_claude_transport`):

1. `command -v claude`; `claude auth status` must report `loggedIn: true` in the
   same execution context (see `ideas/archive/claude-cli-login-context.md`; honor
   `CLAUDE_CONFIG_DIR`/HOME — the supervisor is per-config-dir).
2. Feature check: `claude agents --json` exits 0 and returns JSON (older
   versions list subagents instead — that output is not JSON → bridge).
3. Supervisor check: dispatch nothing; run `claude daemon status`. "not running"
   is acceptable (it autostarts) **only if** step 4 passes.
4. **Real probe (the authoritative check, replacing `run_bridge_probe`):**
   dispatch a trivial `--bg` role (`write "ok" + probe handoff under
   .quest/<id>/logs/bg_probe/`), run T2 confirmation, poll to completion
   (short timeout, e.g. 120s), tear down per T5. This exercises dispatch
   confirmation, supervisor liveness, bypass-acceptance, and file-write in one
   shot — and would have caught fact 5's false positive.
5. Bypass-acceptance detection: if the probe fails with the acceptance-required
   error, emit a remediation warning: "run `claude --permission-mode
   bypassPermissions` once interactively and accept, then rerun preflight."
6. Cache the result in `.quest/cache/claude_bg_codex.json` with the same TTL
   semantics as today's `claude_bridge_codex.json`; keep the bridge cache as the
   fallback probe. Preflight JSON output gains `transport` and keeps
   `runtime_requirement: "host_context"` semantics.

`scripts/quest_claude_probe.py` gains `--transport {background-agent,bridge,auto}`
and drives step 4.

## File-by-file change list

| File | Change |
|---|---|
| `scripts/quest_runtime/claude_runner.py` | Add `dispatch_bg()` (T1+T2), session-status polling hook in the poll loop (T3), `stop/rm` teardown + deadline `claude stop` (T3/T5), orphan sweep helper (T5). `build_bridge_cmd`/bridge path unchanged. `classify_failure_kind` gains the `absent-session → invocation` case. |
| `scripts/quest_claude_runner.py` | New `--transport auto\|background-agent\|bridge` (default `auto`: resolve from orchestration.json, then preflight cache). Existing flags unchanged; `--bridge-script` applies to bridge path only. |
| `scripts/quest_claude_bridge.py` | **Unchanged.** Docstring note: fallback/API transport; default for CI and `ANTHROPIC_API_KEY` contexts. |
| `scripts/quest_claude_probe.py` | `--transport` flag; bg probe per preflight step 4. |
| `scripts/quest_preflight.sh` | `probe_claude_transport` per above; new cache file; `transport` in output JSON. |
| `.ai/allowlist.json` + `.ai/schemas/allowlist.schema.json` | `claude_role_transport` key (enum, default `auto`). |
| `scripts/quest_runtime/orchestration.py` | Copy/validate the transport key into `orchestration.json`; record resolved transport + downgrade flag. |
| `.skills/quest/delegation/workflow.md` | "Claude Bridge Probe…" section → "Claude Transport Probe and Runtime Dispatch": background-agent preferred, bridge fallback, forced modes; Tier-C rows extended to bg-invoked Claude (timeout/stop semantics per T3); context-health format gains optional `transport=` field. |
| `.ai/quest.md` | Transport section rewritten (bridge → bg default + fallback table). |
| `docs/guides/quest_setup.md` | One-time machine setup: `claude login`; one-time interactive `bypassPermissions` acceptance; note version ≥ 2.1.139 (prefer ≥ 2.1.143 for `bgIsolation`). |
| `scripts/quest_validate-handoff-contracts.sh` | Update grep-count contract checks (bridge refs remain but new transport refs required in workflow.md). |
| `.quest-manifest` | Add any new files. |
| Tests | See below. |

## Logging

`context_health.log` line format gains one optional field, documented in
workflow.md:

```
... | handoff_json=found | source=handoff_json | transport=bg|bridge
```

`runtime=claude` semantics are unchanged (bg-invoked Claude is still
`runtime=claude`). New events logged: dispatch-confirmation failures, bg→bridge
downgrades, `needs input` captures, orphan sweeps. This feeds the
measurement-first doctrine (`ideas/archive/2026-05-31-quest-model-capability-improvements.md`):
the same log answers "how often does bg fail and fall back."

## Tests

Unit (no live model; `claude` faked with a shim script on PATH):
- Dispatch argv construction pins the full `--bg` command including `--settings`
  bgIsolation and `--name` scheme.
- shortID parse of `backgrounded · <id> [· <name>]` incl. the idle variant; name
  fallback via faked `agents --json`.
- Status mapping table (T3) including absent-session → `invocation_error`.
- False-positive case (fact 5): success print + empty `agents --json` →
  `invocation_error`, no infinite poll.
- Teardown ordering: `rm` never precedes artifact confirmation; deadline issues
  `stop` then classifies `timeout`.
- Transport resolution matrix: {auto, background-agent, bridge} ×
  {probe ok, probe failed} → {bg, bridge, blocked} with downgrade recording.
- Orphan sweep matches only `quest-<id>-*` names.

Contract/text:
- `quest_validate-handoff-contracts.sh` counts updated; workflow.md documents
  bg-preferred + bridge-fallback + forced modes.
- `tests/test-quest-preflight.sh` extended with shim behaviors: old CLI
  (non-JSON `agents` output), auth false, daemon dead, acceptance-required.

Live (manual, env-guarded, Phase 0): one real probe dispatch on a logged-in dev
machine; results recorded in the PR.

## Rollout

- **Phase 0 — validation spike (manual, ~1 hour on a real logged-in machine).**
  Verify: probe dispatch end-to-end; `--settings` bgIsolation honored;
  gitignored `.quest/**` writes don't trigger worktree moves; bypass acceptance
  flow + error text; `backgrounded` output format on current version; behavior
  when supervisor can't start (expect fact-5 signature). Record findings in the
  PR description. **Gate: implementation does not start until Phase 0 passes.**
- **Phase 1 — dark launch.** Land everything with default `auto` but ship one
  release with `claude_role_transport: "bridge"` in the repo allowlist so the
  new path is opt-in. Run ≥2 real quests with `background-agent` forced.
- **Phase 2 — flip.** Set allowlist to `auto` (bg-by-default with loud
  fallback). This is the "replacement" in practice — before June 15.
- **Phase 3 — post-soak review.** With `transport=` log data, decide whether the
  bridge remains fallback-only or also keeps the CI/API role. (Spoiler: it keeps
  the CI/API role — see below.)

## Why not delete the bridge outright (the direct answer)

Replace **as default**: yes, that is this spec. Delete the code: no, for four
evidence-backed reasons:

1. **Environments where bg cannot run exist and look healthy.** Fact 5 was
   observed in this repo's own cloud sandbox: dispatch printed success while the
   supervisor was dead. CI runners, containers, and locked-down sandboxes need a
   transport that is a plain child process — that is the bridge. It is also the
   *intended* Anthropic path there (API key / Agent-SDK credit for headless).
2. **Research preview.** The surface is explicitly subject to change, `--bg` is
   not yet in `--help`, and the binary auto-updated mid-session (fact 6).
   Betting the *only* Claude transport on it violates the repo's own
   change-discipline rules (AGENTS.md) and the prove-then-delete doctrine
   (`ideas/archive/2026-05-31-quest-model-capability-improvements.md`).
3. **The three-tier ladder needs a Tier C.** Today, Codex-slot failures fall
   back to Claude and vice versa; bg-transport failures need a same-family
   fallback (bridge) before cross-family fallback, per
   `ideas/archive/2026-05-26-native-runtime-dispatch.md` (no silent family switches).
4. **Deletion buys nothing.** The bridge is ~225 lines, dependency-free, and
   tested. Removing it saves no maintenance and removes the only path that works
   everywhere. KISS cuts both ways.

Revisit deletion only after Phase 3 shows `transport=bridge` is exercised
exclusively by CI/API contexts for a sustained period.

## Out of scope

- Per-role `effort` config and prompt-cache reordering (deferred; see
  `ideas/archive/2026-05-31-quest-model-capability-improvements.md`).
- Structured-output (`--json-schema`) transport-owned artifacts (separate
  measurement-gated track, same doc).
- Claude-led dispatch (`Task(...)`) — unchanged by design.
- Replying to `needs input` sessions programmatically (no sanctioned surface;
  explicitly not attempted).
- Per-role permission enforcement (tracked separately; this migration is
  permission-neutral like the bridge).
