# Codex→Claude Transport Hardening

Date: 2026-07-25
Status: `proposed`
Origin: surfaced during the `claude-opus-4-8` → `claude-opus-5` model upgrade
(branch `claude/allow-list-model-upgrades-5cof66`). A read-only assessment of
both cross-runtime transports produced these findings. None block the model
upgrade — the transports are model-agnostic and carry `claude-opus-5`
unchanged. This doc parks the hardening work until the new orchestration has
been validated over a quest or two.

## Why this is deferred

The model upgrade is a config/docs/test-contract change with no runtime logic
change. The right sequence is: ship the upgrade, run real quests on the new
lineup, confirm the orchestration behaves, **then** take on transport
hardening as its own quest (or two). Doing both at once would entangle a
low-risk data change with subprocess/lifecycle refactors and make regressions
hard to attribute.

## Scope

Two transports let a Codex/GPT-led session dispatch a Claude-family role:

- **background-agent**: `scripts/quest_claude_bg_run.py` (1475 lines), the default
  (`claude_role_transport: "auto"`). Runs `claude --bg`, bills the
  subscription pool.
- **bridge** — `scripts/quest_claude_bridge.py` (~233 lines), the explicit
  fallback kept for CI/sandbox/daemonless/API-billing contexts. Runs
  `claude --print`.

Shared engine: `scripts/quest_runtime/claude_runner.py`. Preflight probe model
default: `scripts/quest_preflight.sh`.

---

## Findings

### Tier 1 — do first (correctness / user-visible failure modes)

**H1. `quest_claude_bg_run.py` can crash-and-leak a live background session.**
`agents_json()` (`quest_claude_bg_run.py:386-392`) catches only
`json.JSONDecodeError`/`ValueError`, but the underlying `_claude()`
(`:377-384`) uses `subprocess.run(..., timeout=30.0)`, which raises
`subprocess.TimeoutExpired` if the daemon hangs. The WAIT loop (`:1105`) and
the dispatch-confirm loop (`:843-851`) call into it outside any guard, and
`main` (`:1378`) only catches `KeyboardInterrupt`. A transient daemon stall
therefore escapes as an uncaught traceback with **no envelope and no
teardown**, leaking the just-confirmed `claude --bg` session. `sweep` already
guards this at `:608` — the polling paths are the inconsistency.
*Fix:* wrap roster queries so a transient CLI failure degrades to
"keep polling / clean teardown" instead of crashing.

**T1. Preflight probes the account default, not the target model.**
`quest_preflight.sh:46` sets `CLAUDE_PROBE_MODEL="${QUEST_CLAUDE_PROBE_MODEL:-claude}"`.
The `claude` sentinel means `normalize_claude_cli_model`
(`claude_runner.py:110-118`) omits `--model`, so preflight proves the transport
works with the *account default*, not with the configured role model. Preflight
can pass green while `claude-opus-5` (or any pinned model) is unavailable; the
failure only surfaces at real role dispatch.
*Fix:* let preflight optionally probe a concrete target model. This is the one
item most directly tied to safely validating a model change — worth doing
early in the validation phase.

**T2. `--wait-for` success is a size-only check → partial artifact reported as
success.** `_nonempty` (`quest_claude_bg_run.py:901-905`) is
`stat().st_size > 0`, and the WAIT loop treats "all non-empty" as success
(`:1091-1094`). An agent still streaming a file to disk yields a
non-empty-but-incomplete artifact that satisfies the check. The handoff path
(`read_handoff`) is JSON-validated and robust to partial writes; the
`--wait-for` path has no equivalent integrity gate.
*Fix:* add a settle/size-stability check or an atomic-write contract for
declared output files.

**T3. Bridge has no model-rejection signal; the background-agent path does.**
The bg path classifies a bad/unavailable model as `model_rejected`
(exit 9, and it names the rejected model — `claude_runner.py:93-107`). The
bridge just returns generic error 1 (`quest_claude_bridge.py:229`) and relies
on stderr substring luck in `classify_result_kind`
(`claude_runner.py:524-544`, matching `"not found"`). The same unavailable
model produces materially worse UX on the bridge and gets routed into the
retry ladder instead of failing fast.
*Fix:* give the bridge a model-rejection detector so both transports classify
an unavailable model identically.

### Tier 2 — robustness / lifecycle

**T4. Probes call `subprocess.run` with no outer timeout.**
`run_bridge_probe`/`run_bg_probe` (`claude_runner.py:1135-1141`, `1215-1221`)
rely entirely on the wrapped script's internal timeout. A hang in the wrapper
before it arms its own timer is unbounded — and preflight is the first thing
that runs. (The main `run_claude_role` path is guarded via
`communicate(timeout=…)`.)

**T5. `--effort` is a hardcoded allow-list.** `quest_claude_bg_run.py:1374`
pins `choices=["", "low", "medium", "high", "xhigh", "max"]`. If a future model
generation renames/adds a reasoning tier, argparse hard-fails before dispatch.
Verify the tier set stays in sync when the model family changes.

**T6. pid-reuse race in teardown.** `stop_session`
(`quest_claude_bg_run.py:506-539`) reads `pid` from the roster then `os.kill`s it;
between read and kill the OS can recycle the pid. The 6× re-read loop mitigates
respawns but not reuse. *Fix:* verify the roster row still owns the pid before
signalling.

**T7. TOCTOU between same-name runners.**
`_retire_same_name_before_fresh_dispatch` (`:546-584`) and the pre-dispatch
snapshot (`:781-784`) are separate `agents --json` calls with no lock; two
runners sharing a `--name` can interleave. Guarantees are best-effort today.

**T8. Bridge exit code collapses to 0/1.** `quest_claude_bridge.py:229`
returns `0 if ok else 1`, discarding the rich `exit_code` (124 timeout, 127
not-found) except inside the `--json-wrap` payload. This is *why* downstream
classification leans on stderr prose matching. **Timeout kill also lacks a
process-group sweep** (`:181-188`; `claude_runner.py:890-897`), so a bridge
grandchild can orphan — the bg path sweeps by session name and reports an
incomplete sweep.

### Tier 3 — structure / testability (no behavior change)

- **Tier-B retry block is duplicated** in `claude_runner.py:698-725` and
  `:1001-1028` — a drift hazard; extract one helper.
- **`run_claude_role` is ~450 lines** doing path resolution, artifact prep,
  two transport control flows, kill/sweep, multi-branch classification, retry,
  text fallback, and logging in one body. The two transport branches and the
  classification block are natural extractions that would make the invariants
  unit-testable in isolation.
- **`quest_claude_bg_run.py run()` is ~312 lines** (`:1007-1318`) with a 4–5-level
  nested WAIT loop; extract `_dispatch_phase`/`_wait_phase`/
  `_classify_blocked_state`/`_teardown_phase`.
- **~90 lines of self-test-only PTY demo code** (`quest_claude_bg_run.py:151-241`,
  sole caller `_self_test` at `:1416`) inflate the largest script in the repo;
  move to a test/demo module. (`strip_ansi`/`distill` stay — they are live via
  `logs_tail`.)
- **`BgRunner` is coupled to `argparse.Namespace`** (`:369`, pervasive
  `self.a.<attr>`), so unit tests must build Namespaces; introduce a config
  dataclass populated in `main`.
- **Dead field:** `transport_downgraded` is declared `False` and never mutated
  (`quest_claude_runner.py:130`) — always emitted `false`. Wire it or drop it.
- Minor: `logs_tail` parses the whole transcript for a tail
  (`quest_claude_bg_run.py:478-505`); `returncode or 1` masks a genuine 0
  (`claude_runner.py:971`); raw child exit codes propagated as process exit can
  alias under `SystemExit` mod-256 (`quest_claude_probe.py:82`,
  `quest_claude_runner.py:231`).

---

## Cross-cutting theme

The bridge and background-agent transports classify the same failure
differently — model rejection, orphan sweep, and exit-code fidelity all differ.
The unifying goal: **whichever transport a role lands on, an unavailable model
(and every other failure) should fail the same recognizable way, with a clean
teardown.** T1, T3, and H1 are the highest-value steps toward that.

## Related, already tracked (do not duplicate here)

- `ideas/2026-07-05-bg-claude-ask-policy-relaxation.md` — the one open *design*
  decision on this transport line (when a bg Claude role may write
  `needs_human`). Independent of the hardening above.

## Suggested sequencing

1. Validate the Opus 5 orchestration over one or two real quests.
2. Quest A — Tier 1 (H1, T1, T2, T3): the correctness and user-visible items.
3. Quest B — Tier 2 + Tier 3: lifecycle robustness and the structural
   decomposition that makes the transports unit-testable.
