---
title: Step 2 — Wire the claude --bg transport into Quest (bg default, bridge fallback)
purpose: Executable implementation plan for making the background-agent transport the default for Codex-led Claude roles, with loud bridge fallback, transport visibility in the quest summary/celebration, ideas archival, and self-archival on completion.
audience: Implementing engineer (Sr→mid) and reviewers.
scope: Transport wiring only — quest_claude_runner/preflight/orchestration config, summary+celebration callout, docs/ideas housekeeping. Role prompts and handoff contracts unchanged.
status: active
owner: maintainers
last_updated: 2026-06-11
related:
  - docs/implementation/claude-bg-transport-migration.md
  - docs/implementation/claude-bg-run-script.md
  - scripts/claude_bg_run.py
  - scripts/quest_claude_bridge.py
---

# Step 2 — Wire the `claude --bg` transport into Quest (bg default, bridge fallback)


## Context

PR #136 landed Step 1: `scripts/claude_bg_run.py`, a standalone, live-validated runner that executes one Claude task via `claude --bg` (subscription billing) with dispatch confirmation, file-based completion, transcript-based logs, pid-based teardown, and a `needs_human → --resume` relay. Quest, however, still talks to Claude **only** through `scripts/quest_claude_bridge.py` (`claude --print`), which bills to the metered API pool after **June 15, 2026**.

This plan wires the bg transport into Quest as the **default** (`auto`: bg when preflight proves it, loud bridge fallback otherwise — user decision: ship `auto` from day one, no dark-launch), makes the transport **visible** in the quest end summary and celebration (only when Codex called Claude), archives the superseded ideas, and archives itself when done.

**Design invariant** (from the migration spec): the swap happens entirely underneath `scripts/quest_claude_runner.py`. Role prompts, handoff contract, artifact prep, Tier A/B/C ladder, `context_health.log` keep their contracts. Only the mechanism that gets a prompt to a Claude process changes.

**Supersedes one spec detail:** `docs/implementation/claude-bg-transport-migration.md` (written pre-Step-1) proposed reimplementing dispatch/confirm/teardown (`dispatch_bg()`, T1–T5) *inside* `quest_runtime/claude_runner.py`. Step 1 already encapsulates all of that in `claude_bg_run.py` with the same file contract and distinct exit codes. **DRY/KISS: invoke `claude_bg_run.py` as a subprocess exactly the way the bridge is invoked** — one selector, two argv builders, same poll/classify/health-log machinery. The spec also predates the discovery that `claude logs/stop/rm` are not real subcommands (corrected in Step 1).

## Key design decisions (read before coding)

1. **Quest does NOT pass `--handoff-file` to `claude_bg_run.py`.** The role's `handoff.json` is passed via `--wait-for` only. Rationale: with `--handoff-file`, a `needs_human` handoff makes the bg runner exit 10 and **leave the session alive** — Quest's orchestrator has no resume loop today, so that would leak live sessions. Without it, a `needs_human` handoff is just "handoff file present" → session torn down → orchestrator reads the status exactly as it does on the bridge path. Identical semantics, zero leak risk. The resume relay stays a documented non-goal (see Out of scope).
2. **Transport is resolved by scripts, never by agent prose.** `claude_role_transport` config enum `auto | background-agent | bridge`; `auto` resolves from the preflight cache. Forced `background-agent` fails loudly (never silently bridges); forced `bridge` is the API-billing / fully-automated path.
3. **`transport=` becomes a first-class `context_health.log` field for Codex→Claude runs** (the only writer is `quest_runtime/claude_runner.py`, so absence of the field = the role wasn't a Codex-led Claude run). End summary and celebration read it from there — single source, no new state files (DRY).
4. **Session naming**: `--name quest-<quest_id>-<agent>-i<iter>` — deterministic, and the recovery key for the orphan sweep.

## Implementation steps

### Step A — config plumbing (`claude_role_transport`)

| File | Change |
|---|---|
| `.ai/allowlist.json` | add `"claude_role_transport": "auto"` |
| `.ai/schemas/allowlist.schema.json` | add the key, `enum: ["auto", "background-agent", "bridge"]`, default `auto` |
| `scripts/quest_runtime/orchestration.py` (`write_orchestration_json`, `:328-351`) | copy the key into `orchestration.json`; add `claude_transport_resolved` + `claude_transport_downgraded: bool` fields (written at preflight-validation time; `null`/`false` until resolved). Backfill in `migrate_from_snapshot()` like `review-arbiter` is backfilled. |
| `scripts/quest_validate-quest-state.sh` (if it validates orchestration fields) | accept the new keys |

### Step B — preflight probe (`quest_preflight.sh` + `quest_claude_probe.py`)

Two probes, selector on top (SRP — don't mutate the proven bridge probe):

1. New `probe_claude_bg()` in `scripts/quest_preflight.sh`, mirroring `probe_claude_bridge()` (`:257-387`): checks `claude` CLI + `claude auth status` loggedIn + `claude agents --json` parses as JSON (old CLIs print non-JSON → bg unavailable), then runs the **live probe**: `python3 scripts/quest_claude_probe.py --transport background-agent ...` which dispatches a trivial bg task (tiny artifact + probe handoff under `.quest/<id>/logs/bg_probe/`) through `claude_bg_run.py`. Cache: `.quest/cache/claude_bg_codex.json` (same TTL machinery — reuse `write_success_cache`/`load_success_cache`).
2. Selector: for `--orchestrator codex`, run bg probe first; on failure fall back to the existing bridge probe. Output JSON gains `"transport": "background-agent" | "bridge"` and keeps all existing fields (`available`, `checks`, `cache`, `diagnostic`, `warning`). A bg→bridge downgrade adds a loud `warning` line.
3. `scripts/quest_claude_probe.py`: add `--transport {background-agent,bridge}` (default bridge — backward compatible); bg path calls a new `run_bg_probe()` in `claude_runner.py` that mirrors `run_bridge_probe()` (`:584-661`) but builds the bg command.

### Step C — runtime wiring (`quest_runtime/claude_runner.py` + `quest_claude_runner.py`)

1. `build_bg_cmd()` next to `build_bridge_cmd()` (`:177-204`), ~25 lines:
   `python3 scripts/claude_bg_run.py --json --no-protocol --prompt-file <p> --name quest-<id>-<agent>-i<iter> --model <m> --permission-mode <mode> --timeout <t> --wait-for <handoff> [--wait-for <artifact>…] [--add-dir <d>…]`
   (no `--handoff-file` — decision 1).
2. `run_claude_role()` (`:302-581`): add `transport: str = "bridge"` param. The **only** transport-conditional code: which cmd builder runs, and the exit-code mapping on child exit. Poll loop, Tier B, text fallback, artifact prep: untouched.
3. Exit-code → `classify_result_kind` mapping for the bg child (`claude_bg_run.py` EXIT_* constants):
   - `0` → normal classification (handoff found wins, as today)
   - `2` precondition, `3` dispatch_failed, `4` blocked → `invocation_error` (Tier C blocks fast with remediation; Tier B can't fix a daemon/dialog problem). Include the envelope's `message` + `logs_tail` in stderr so failures are diagnosable.
   - `5` → `timeout`; `6`, `130`, anything else → fall through to the standard handoff-state classification (typically `handoff_missing`) so the existing missing-handoff retry ladder applies unchanged. (`10` cannot occur — no `--handoff-file`.)
4. `append_context_health_log()` (`:283-299`): add optional `transport: str | None = None`; when set, append ` | transport=<value>` to the line. `run_claude_role` passes it on every log call (`:440, :554, :572`).
5. `scripts/quest_claude_runner.py`: add `--transport auto|background-agent|bridge` (default `auto`). Resolution for `auto`: read `.quest/cache/claude_bg_codex.json` → payload.available → bg, else bridge (so the runner also works standalone, without orchestration.json). Echo the resolved transport in the output JSON envelope (`"transport": "..."`).
6. **Orphan sweep**: add `--sweep <name-prefix>` mode to `claude_bg_run.py` (reuses `find_session`/`stop_session`; stops every background row whose `name` starts with the prefix; prints what it stopped; ~20 lines). Workflow Step 1/resume prose tells the orchestrator to run `python3 scripts/claude_bg_run.py --sweep quest-<id>-` at quest start/resume. Belt-and-braces for crashed orchestrators.

### Step D — end summary + celebration transport callout (user requirement)

Only shown when Codex called Claude (i.e., `transport=` entries exist in `context_health.log`):

1. `.skills/quest/delegation/workflow.md` Step 7 context-health reflection (`:1183-1237`): after the compliance block, add:
   ```
   Claude transport (Codex-led roles only):
     background-agent: <N>    bridge: <N>    [downgraded from background-agent: yes/no — from orchestration.json claude_transport_downgraded]
   ```
   Omit the whole block when no `transport=` entries exist (Claude-led quests stay unchanged).
2. `scripts/quest_celebrate/quest_data.py`: parse `context_health.log`; add `transport: Optional[str]` to `AgentInfo` (match log line `agent=` to handoff-derived agents) and `claude_transport_counts: dict[str, int]` to `QuestData`. No transport entries → empty dict → all display suppressed.
3. `.skills/celebrate/SKILL.md`: cast line gains a `via background-agent` / `via bridge` tag for agents that have transport data; one metric line (e.g. `🚌 Claude transport: background-agent ×4, bridge ×1`) when counts are non-empty. Explicit empty-state rule: when no transport data, show nothing (don't print "N/A").
4. `scripts/quest_complete.py` `_build_celebration_json()` (`:40-73`): include `"transport"` per agent (when set) and a `claude_transport` metric entry (when non-empty) so journal replays carry it.

### Step E — prose, docs, contracts

1. `.skills/quest/delegation/workflow.md`:
   - "Claude Bridge Probe And Runtime Dispatch" (`:74-92`) → "Claude Transport Probe And Runtime Dispatch": bg preferred, bridge fallback, forced modes, orphan sweep, the `--transport` flag on the runner. Dispatch matrix row (Codex-led/Claude) keeps the entrypoint `python3 scripts/quest_claude_runner.py` (canary tests `tests/unit/test_quest_dispatch_guardrails.py:195-260` require that string and the runtime/entrypoint split — keep required phrases, update the tests ONLY if the renamed section header breaks an assertion).
   - context-health format spec (`:230-280`): document the `transport=` field (mandatory for Codex-led Claude roles, absent otherwise); update the example block.
2. `.ai/quest.md` (`:77-82`): rewrite the Codex-led note: bg default via `auto`, bridge fallback/API path, `quest_claude_runner.py` unchanged as entrypoint. (Also fix the existing typo `claude_cli_bridge.py` → `quest_claude_bridge.py`.)
3. `scripts/quest_claude_bridge.py`: docstring note only — "fallback/API transport; default for CI, `ANTHROPIC_API_KEY`, and daemonless contexts". No code change.
4. `docs/guides/quest_setup.md`: one-time machine setup — `claude login`; one-time interactive `claude --dangerously-skip-permissions` acceptance; CLI ≥ 2.1.143; how to check (`claude agents --json` returns JSON).
5. `scripts/quest_validate-handoff-contracts.sh`: update grep-count contract checks for the renamed workflow section + new transport prose.
6. `.quest-manifest`: add every new/moved file (validated by `scripts/quest_validate-manifest.sh` — the commit skill runs it).
7. `docs/implementation/claude-bg-transport-migration.md`: revise in place — status `active`, add a short "Revisions (2026-06-11)" section: claude_bg_run.py subsumes T1–T5; no `logs/stop/rm` subcommands (pid teardown); rollout collapsed to auto-from-day-one (user decision; Phase-0 evidence = Step 1's live validation); link this plan.
8. This plan is committed as `docs/implementation/claude-bg-transport-step2-wiring.md` (frontmatter: status `active`) and indexed in `docs/implementation/README.md`.

### Step F — ideas archival (user decision: aggressive sweep)

`git mv` to `ideas/archive/` with a status line prepended (per existing archive conventions) + update `ideas/README.md` (move rows to Done Index, with reasons):

| File | Archive status / reason |
|---|---|
| `ideas/2026-05-31-codex-driven-interactive-claude-relay.md` | `done` — implemented by Step 1 (#136) + this plan |
| `ideas/2026-05-26-native-runtime-dispatch.md` | `done` — encoded in workflow.md dispatch matrix + `select_role_runtime()` |
| `ideas/claude-cli-login-context.md` | `reference` (archived) — operative guidance now lives in `docs/guides/quest_setup.md` + preflight checks |
| `ideas/claude-bridge-timeout-diagnosis-2026-03-23.md` | `reference` (archived) — incident encoded as migration-spec fact 5 / preflight live-probe design |
| `ideas/2026-05-31-quest-model-capability-improvements.md` | `superseded` — transport portion landed; measurement items re-proposable if wanted |

Fix dangling references: `docs/implementation/claude-bg-transport-migration.md` and `claude-bg-run-script.md` frontmatter `related:` lists point at two of these — update paths to `ideas/archive/...`. `grep -rn` for each moved filename to catch others.

### Step G — tests

Match existing patterns (pytest + fake shims in `tests/unit/`, bash harnesses in `tests/`):

1. `tests/unit/test_quest_runtime.py` (extend): transport resolution matrix `{auto, background-agent, bridge} × {bg cache ok, bg cache missing/failed}` → `{bg, bridge, blocked-on-forced-bg}`; `build_bg_cmd` argv pinned (incl. `--no-protocol`, no `--handoff-file`, name scheme); bg exit-code → result_kind mapping (2/3/4/5/6/10/130); `append_context_health_log` emits `transport=` only when given.
2. `tests/unit/test_claude_bg_run.py` (extend): `--sweep` stops only matching-prefix rows (uses the existing fake-kill fixture).
3. `tests/unit/test_quest_celebrate*` / new: `quest_data.py` parses transport from a fixture `context_health.log`; empty-state (no transport lines) yields empty counts; `quest_complete._build_celebration_json` includes/omits transport correctly.
4. `tests/test-quest-preflight.sh` (extend): shim scenarios — bg probe ok → `transport=background-agent`; `agents` prints non-JSON (old CLI) → bridge fallback with warning; both probes fail → `available=false`.
5. `tests/unit/test_quest_dispatch_guardrails.py`: update only the assertions tied to the renamed workflow section; canary intent (thin pointers, no MCP for Codex-led) unchanged.
6. Full suite green: `uv run pytest tests/ -q` + `bash tests/test-quest-preflight.sh` + `bash tests/test-quest-runtime.sh` + `scripts/quest_validate-handoff-contracts.sh` + `scripts/quest_validate-manifest.sh`.

## Acceptance criteria

Code/config:
- [ ] `claude_role_transport` flows allowlist → schema → orchestration.json, with `claude_transport_resolved`/`claude_transport_downgraded` recorded at preflight.
- [ ] `quest_claude_runner.py --transport` works for all three values; `auto` resolves from the bg cache; forced `background-agent` **blocks loudly** when preflight fails (never silently bridges); forced `bridge` untouched behavior.
- [ ] Bridge path byte-for-byte unchanged (`build_bridge_cmd` and `quest_claude_bridge.py` diffs are docstring-only).
- [ ] `context_health.log` lines for Codex-led Claude roles carry `transport=background-agent|bridge`; all other lines unchanged.
- [ ] All suites/validators in Step G pass; manifest valid.

Visibility (the user requirement):
- [ ] Quest end summary (Step 7) shows the Claude-transport block **iff** Codex called Claude; Claude-led quests show no new output.
- [ ] Celebration + journal `celebration_data` carry per-agent transport and the transport metric, with a silent empty state.

Human-runnable (see runbook): 
- [ ] Runbook items 1–5 executed on a real machine; outcomes recorded in the PR description.

Housekeeping:
- [ ] 5 ideas files archived per Step F; `ideas/README.md` indexes them; no dangling links (`grep` clean).
- [ ] Migration spec revised (status `active` + Revisions section); this plan committed as `docs/implementation/claude-bg-transport-step2-wiring.md`.
- [ ] **Self-archival:** as the FINAL change of this effort (after the runbook passes), `git mv docs/implementation/claude-bg-transport-step2-wiring.md docs/implementation/claude-bg-transport-migration.md docs/implementation/claude-bg-run-script.md` → `docs/implementation/history/` (create the directory — DOCUMENTATION_STRUCTURE.md already documents it), set their status to `complete`, and update `docs/implementation/README.md`. The effort is not "done" until the plans are out of the active index.

## Human test runbook (what "it works" looks like)

Prereqs once per machine: `claude login`; accept bypass once (`claude --dangerously-skip-permissions`, then exit); `claude agents --json` prints a JSON array.

1. **Preflight says bg**: `scripts/quest_preflight.sh --orchestrator codex` → JSON has `"transport": "background-agent"`, `"available": true`; cache file `.quest/cache/claude_bg_codex.json` exists. *Fail signal:* `transport: bridge` + warning lines on a logged-in dev machine.
2. **Standalone role smoke** (no quest): `python3 scripts/quest_claude_runner.py --transport background-agent --quest-dir /tmp/qtest --phase plan --agent planner --iter 1 --prompt-file <tiny prompt asking to write handoff.json> --handoff-file /tmp/qtest/handoff.json` → exit 0, output JSON `"transport": "background-agent"`, handoff present. While it runs, `claude agents` shows a `quest-…planner-i1` session; after, it's gone (teardown works).
3. **Forced-bg real quest**: run a small `/quest` with `claude_role_transport: "background-agent"`. Verify: `.quest/<id>/logs/context_health.log` lines for Claude roles end with `transport=background-agent`; Step 7 summary shows the transport block; celebration shows `via background-agent` + the transport metric; `/usage` in Claude attributes the runs to **subscription** (this closes the migration spec's machine-validation item 2 — record it).
4. **Forced-bridge quest**: same small quest with `"bridge"` → `transport=bridge` everywhere above. Proves the callout distinguishes, and the fallback path still works.
5. **Downgrade drill**: temporarily break bg (e.g. `CLAUDE_CONFIG_DIR=/tmp/empty scripts/quest_preflight.sh --orchestrator codex`, or run where the daemon can't start) with `auto` → preflight reports `transport: bridge` **with a warning**, `claude_transport_downgraded: true` lands in orchestration.json, and the quest still completes via bridge. *Fail signal:* silent bridge use with no downgrade record.

## Out of scope (YAGNI — value over good-to-have)

- **needs_human resume relay inside quest phases** (keep-alive + `--resume` orchestration): real value, but requires orchestrator-side conversation state Quest doesn't have; the capability exists standalone in `claude_bg_run.py`. Capture as a fresh idea file `ideas/quest-needs-human-resume-relay.md` (status `proposed`, 10 lines) instead of building it.
- **Per-role `--effort`** (deferred by the spec; unrelated to transport).
- **Deleting the bridge** (post-soak decision per the spec; revisit with `transport=` log data).
- Any change to Claude-led (`Task(...)`) or Codex-role dispatch.

## Execution order & PR shape

One PR on `claude/bg-transport-step2`: Steps A→B→C (code+tests green) → D (visibility) → E (prose/docs; run contract validators) → F (ideas) → G rounding. Commits via the git-commit-assistant skill; PR (draft) via pr-assistant; runbook items 1–5 executed and pasted into the PR description before marking ready. Self-archival (last AC) lands as the final commit once the runbook passes — same PR if validated promptly, follow-up commit otherwise.
