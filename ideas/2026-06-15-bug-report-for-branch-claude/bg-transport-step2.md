# Bug Report: Quest Claude Transport Preflight Is CWD-Fragile

Date: 2026-06-15
Branch: `claude/bg-transport-step2`
Status: confirmed; fix scope broadened 2026-06-16 (see Correction)

## Correction (2026-06-16, after code review)

The original diagnosis is correct but the proposed fix was **scoped too narrowly**.
Fixing only `quest_preflight.sh` would make the *probe* green while the real
Claude role dispatch still breaks in the same topology. Four additions:

1. **Same defect on the hot path.** `scripts/quest_claude_runner.py` and
   `scripts/quest_claude_probe.py` default `--bridge-script` to the cwd-relative
   `scripts/quest_claude_bridge.py`, and `--bg-runner-script` to
   `DEFAULT_BG_RUNNER_SCRIPT = "scripts/claude_bg_run.py"` (defined in
   `scripts/quest_runtime/claude_runner.py`). `workflow.md` invokes the runner
   (`python3 scripts/quest_claude_runner.py --transport …`) for **real role
   execution** without passing an absolute `--bridge-script`. So even after the
   preflight fix, a Claude role dispatched from a target repo fails identically.
   **Fix: resolve the sibling helper scripts off `__file__`** in
   `quest_runtime/claude_runner.py` (they all live in `scripts/`), so the Python
   helpers are install-location-robust regardless of cwd. Project state
   (`.quest/cache/...`, `.ai/allowlist.json`) stays cwd-relative.
2. **Symlink-safe `SCRIPT_DIR`.** `cd "$(dirname "${BASH_SOURCE[0]}")" && pwd`
   resolves the *symlink's* directory, not the real file's — and quest installs
   can symlink the entrypoints (#130). On macOS `readlink -f` is also unreliable.
   Resolve via `python3 -c 'os.path.realpath(...)'` (python3 is already a hard
   dependency) with a `pwd -P` fallback.
3. **Two probe call sites**, not one: the bg probe and the bridge probe both
   hard-code `python3 scripts/quest_claude_probe.py`. Both must use
   `"$CLAUDE_PROBE_SCRIPT"`.
4. **Documented entrypoints are cwd-relative too** (`scripts/quest_preflight.sh`,
   `python3 scripts/quest_claude_runner.py` in `workflow.md`). Once the scripts
   self-resolve their helpers (1–2), invoking them by absolute path from the
   target repo works; cwd is used only for project state.

The sections below are the original report, kept as-is; the **Proposed Fix**,
**Acceptance Criteria**, and **Regression Tests** are updated to cover 1–4.

## Summary

Codex-led Quest preflight can falsely report Claude transport unavailable when Quest is installed outside the target repo and the preflight script is invoked from inside that target repo.

The root issue is that `/Users/kjell/ws/scripts/quest_preflight.sh` is executable by absolute path, but it resolves its helper scripts with cwd-relative defaults such as `scripts/quest_claude_bridge.py`, `scripts/claude_bg_run.py`, and a hard-coded `python3 scripts/quest_claude_probe.py`.

When the active project is `/Users/kjell/ws/diffly`, those helper paths resolve under `/Users/kjell/ws/diffly/scripts/`, which does not exist. Preflight then records Claude bridge unavailable even though the bridge works when run from the Quest install root.

## Why This Matters

This caused Quest `p4b-view-modes_2026-06-15__1202` to run Codex-only even though Claude bridge transport was actually healthy.

The quest artifact recorded:

```json
{
  "available": false,
  "transport": "bridge",
  "transport_downgraded": true,
  "checks": {
    "claude_cli_installed": true,
    "claude_auth_logged_in": true,
    "bridge_script_exists": false,
    "bridge_reachable": false
  }
}
```

That result was not a true Claude availability result. It was a helper-path resolution failure.

## Reproduction

Environment:

- Quest scripts installed at `/Users/kjell/ws/scripts/`
- Target repo at `/Users/kjell/ws/diffly`
- Claude CLI installed and authenticated
- Claude CLI version observed: `2.1.177 (Claude Code)`

From the target repo cwd:

```sh
cd /Users/kjell/ws/diffly
/Users/kjell/ws/scripts/quest_preflight.sh --orchestrator codex
```

Observed:

```json
{
  "available": false,
  "transport": "bridge",
  "checks": {
    "bridge_script_exists": false,
    "bridge_reachable": false
  }
}
```

From the Quest install/workspace root:

```sh
cd /Users/kjell/ws
scripts/quest_preflight.sh --orchestrator codex
```

Observed:

```json
{
  "available": true,
  "transport": "bridge",
  "transport_downgraded": true,
  "checks": {
    "bridge_script_exists": true,
    "bridge_reachable": true
  },
  "diagnostic": {
    "probe_result_kind": "handoff_json"
  }
}
```

Direct bridge probe from the Quest install root:

```sh
cd /Users/kjell/ws
tmp="$(mktemp -d)"
python3 scripts/quest_claude_probe.py \
  --quest-dir "$tmp" \
  --model opus \
  --transport bridge \
  --bridge-script scripts/quest_claude_bridge.py \
  --cwd /Users/kjell/ws
```

Observed:

```json
{
  "transport": "bridge",
  "exit_code": 0,
  "handoff_state": "found",
  "result_kind": "handoff_json",
  "source": "handoff_json"
}
```

## Separate Background-Agent Setup Finding

The background-agent transport also failed, but for a different and legitimate setup reason:

```json
{
  "transport": "background-agent",
  "exit_code": 2,
  "result_kind": "invocation_error",
  "stderr": "bg status=precondition_failed; bg message=bypassPermissions not accepted — run `claude --dangerously-skip-permissions` once interactively, then retry."
}
```

So there are two distinct outcomes:

1. Background-agent is correctly unavailable until `claude --dangerously-skip-permissions` is accepted once interactively.
2. Bridge fallback is incorrectly reported unavailable when preflight runs from a target repo that does not contain Quest helper scripts.

## Suspected Root Cause

`quest_preflight.sh` defines helper paths relative to the current working directory:

```sh
CLAUDE_BRIDGE_SCRIPT="${QUEST_CLAUDE_BRIDGE_SCRIPT:-scripts/quest_claude_bridge.py}"
CLAUDE_BG_RUNNER_SCRIPT="${QUEST_CLAUDE_BG_RUNNER_SCRIPT:-scripts/claude_bg_run.py}"
```

It also invokes the probe helper with a cwd-relative hard-coded path:

```sh
python3 scripts/quest_claude_probe.py ...
```

This is wrong when the preflight script is installed outside the target repo and run by absolute path.

## Expected Behavior

The preflight script should distinguish:

- **Quest install root / helper script root**: where `quest_preflight.sh`, `quest_claude_probe.py`, `quest_claude_bridge.py`, and `claude_bg_run.py` live.
- **Project cwd**: where `.quest/`, `.ai/allowlist.json`, repo files, and quest artifacts should be read/written.

Running this from a target repo should work:

```sh
cd /Users/kjell/ws/diffly
/Users/kjell/ws/scripts/quest_preflight.sh --orchestrator codex
```

If bridge is healthy, it should report `available=true` with `bridge_reachable=true`, regardless of whether the target repo has its own `scripts/` directory.

## Proposed Fix

In `quest_preflight.sh`:

1. Resolve the script directory once, **symlink-safe** (entrypoints may be
   symlinked; macOS lacks `readlink -f`):

   ```sh
   if SCRIPT_DIR="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "${BASH_SOURCE[0]}" 2>/dev/null)"; then :; else
     SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
   fi
   ```

2. Default helper paths relative to `SCRIPT_DIR`, not cwd:

   ```sh
   CLAUDE_BRIDGE_SCRIPT="${QUEST_CLAUDE_BRIDGE_SCRIPT:-$SCRIPT_DIR/quest_claude_bridge.py}"
   CLAUDE_BG_RUNNER_SCRIPT="${QUEST_CLAUDE_BG_RUNNER_SCRIPT:-$SCRIPT_DIR/claude_bg_run.py}"
   CLAUDE_PROBE_SCRIPT="${QUEST_CLAUDE_PROBE_SCRIPT:-$SCRIPT_DIR/quest_claude_probe.py}"
   ```

3. Replace **both** hard-coded probe calls (the background-agent probe AND the
   bridge probe) — `python3 scripts/quest_claude_probe.py ...` → `python3
   "$CLAUDE_PROBE_SCRIPT" ...`.

4. Keep project-relative paths project-relative:

   - `.quest/cache/...`
   - `.ai/allowlist.json`
   - probe temp quest dir contents

5. Preserve environment overrides for all helper paths.

In the Python helpers (so real role execution, not just preflight, is fixed):

6. In `scripts/quest_runtime/claude_runner.py`, resolve sibling scripts off
   `__file__` instead of cwd:

   ```python
   _SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # scripts/
   DEFAULT_BRIDGE_SCRIPT = str(_SCRIPTS_DIR / "quest_claude_bridge.py")
   DEFAULT_BG_RUNNER_SCRIPT = str(_SCRIPTS_DIR / "claude_bg_run.py")
   # DEFAULT_BG_CACHE_FILE stays project-relative: ".quest/cache/claude_bg_codex.json"
   ```

7. Use those constants as the argparse defaults in `quest_claude_probe.py` and
   `quest_claude_runner.py` (`--bridge-script`, `--bg-runner-script`). Explicit
   relative values still resolve against `--cwd` as before — only the *default*
   changes.

## Diagnostic Improvement

When helper script invocation fails before JSON is produced, preflight currently swallows stderr and returns blank diagnostics:

```json
"diagnostic": {
  "probe_result_kind": null,
  "probe_message": null
}
```

It should report a path or invocation diagnostic, for example:

```json
{
  "probe_result_kind": "preflight_invocation_error",
  "probe_message": "quest_claude_probe.py not found at /Users/kjell/ws/diffly/scripts/quest_claude_probe.py"
}
```

## Acceptance Criteria

- Running `/Users/kjell/ws/scripts/quest_preflight.sh --orchestrator codex` from `/Users/kjell/ws/diffly` succeeds via bridge when bridge is healthy.
- Running `scripts/quest_preflight.sh --orchestrator codex` from `/Users/kjell/ws` still succeeds.
- Forced environment overrides still work:

  ```sh
  QUEST_CLAUDE_BRIDGE_SCRIPT=/custom/quest_claude_bridge.py \
  QUEST_CLAUDE_BG_RUNNER_SCRIPT=/custom/claude_bg_run.py \
  QUEST_CLAUDE_PROBE_SCRIPT=/custom/quest_claude_probe.py \
  scripts/quest_preflight.sh --orchestrator codex
  ```

- Missing helper scripts produce explicit diagnostics instead of blank `probe_message`.
- The Python helper defaults (`--bridge-script`, `--bg-runner-script`) resolve to
  absolute paths next to the script regardless of cwd, so a Claude role
  dispatched by `quest_claude_runner.py` from a target repo without a `scripts/`
  dir still finds the bridge / bg-runner. Explicit relative `--bridge-script`
  values still resolve against `--cwd` (no regression).
- `SCRIPT_DIR` resolution survives a symlinked entrypoint.
- Background-agent precondition failure still reports the existing actionable message:

  ```text
  bypassPermissions not accepted — run `claude --dangerously-skip-permissions` once interactively, then retry.
  ```

## Regression Tests To Add

1. Preflight called by absolute path from a temp target repo without a `scripts/` directory.
2. Preflight called from install root.
3. Preflight with helper script env overrides.
4. Missing probe helper path yields explicit diagnostic.
5. Background-agent precondition failure remains distinct from bridge path failures.
6. Preflight invoked through a **symlinked** entrypoint still resolves helpers to the real install dir.
7. Python helper defaults: with cwd in a target repo lacking `scripts/`, `quest_claude_probe.py` / `quest_claude_runner.py` (no `--bridge-script` given) still resolve the sibling bridge / bg-runner to an absolute path next to the script.

## Notes

This bug is independent of the background-agent one-time setup requirement. Fixing this path issue should allow bridge fallback to work correctly while BG setup remains surfaced as a separate actionable warning.
