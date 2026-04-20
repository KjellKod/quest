# Idea: Runner `cwd`-Relative Path Hygiene Sweep

## Status: proposed (follow-up quest)

## Origin

Surfaced during PR #94 review. Bot flagged `scripts/quest_claude_probe.py:31` — `bridge_script=Path(args.cwd) / args.bridge_script` — for double-applying `cwd` when `--cwd` is relative. Traced it to a real bug: with a relative `--cwd` the subprocess ends up looking for `<cwd>/<cwd>/scripts/quest_claude_bridge.py`.

The concern: this pattern (pre-compute a path by prepending `args.cwd` to a path that will then be passed to a subprocess whose own `cwd` is also `args.cwd`) is a common shape. If it appears in one runner helper it probably appears in others. Worth a sweep.

## The bug, concretely

```python
# scripts/quest_claude_probe.py:28-35
result = run_bridge_probe(
    cwd=args.cwd,
    quest_dir=args.quest_dir,
    bridge_script=Path(args.cwd) / args.bridge_script,   # <-- double-applies cwd
    ...
)
```

Downstream, `run_bridge_probe` → `build_bridge_cmd` constructs `cmd = [python, str(bridge_script), ...]` and calls `subprocess.run(cmd, cwd=str(cwd), ...)`. The subprocess resolves `argv[1]` relative to its own `cwd`, which is `args.cwd`. So:

| `args.cwd` | `args.bridge_script` | Computed `bridge_script` | Subprocess lookup |
|---|---|---|---|
| `"."` (default) | `"scripts/quest_claude_bridge.py"` | `Path("scripts/quest_claude_bridge.py")` (Path normalizes `Path(".") / x` → `Path(x)`) | `./scripts/quest_claude_bridge.py` — works |
| `"/abs/path"` | `"scripts/quest_claude_bridge.py"` | `/abs/path/scripts/quest_claude_bridge.py` (absolute) | works |
| `"repo"` (relative) | `"scripts/quest_claude_bridge.py"` | `Path("repo/scripts/quest_claude_bridge.py")` | subprocess cwd is `repo`, argv resolves to `repo/repo/scripts/quest_claude_bridge.py` — **BROKEN** |

So the bug hides when callers pass `--cwd .` (the default) or `--cwd /abs/...` (absolute). It bites anyone passing a relative non-dot path.

## Fix shape (per call site)

Two options per call site:

**Option A — pass the bridge script path unchanged, let subprocess cwd resolve it.**
```python
bridge_script=args.bridge_script,   # leave it as "scripts/quest_claude_bridge.py"
```
Simplest. The subprocess cwd is already `args.cwd`, so relative resolution works.

**Option B — pre-resolve to an absolute path with the existing helper.**
```python
from quest_runtime.claude_runner import resolve_path
bridge_script=resolve_path(args.cwd, args.bridge_script),
```
Consistent with other code in `claude_runner.py` which already uses `resolve_path` for `quest_dir`, probe artifact paths, etc. Returns an absolute `Path`. Double-apply cannot happen.

**Recommendation:** Option B for consistency with the rest of the runner module, plus it makes the intent explicit ("I want the absolute path now, before it goes through subprocess").

## Sweep scope

The same shape could exist in any of these files. The quest should grep all of them for `Path(args.cwd)`, `Path(.*cwd.*)`, and compare each hit against how the computed path is later consumed (same-cwd subprocess? separate subprocess? just logged?).

- `scripts/quest_claude_probe.py` — **confirmed bug.**
- `scripts/quest_claude_runner.py` — uses `resolve_path(cwd, ...)` correctly in several places; verify no `Path(cwd) / ...` slipped in.
- `scripts/quest_claude_bridge.py` — transport script; accepts `--cwd` style args. Check.
- `scripts/quest_startup_branch.py` — path handling for worktree mode.
- `scripts/quest_runtime/claude_runner.py` — canonical runner. `resolve_path` lives here, but also grep for any manual `Path(...) / ...` constructions that duplicate subprocess-cwd behavior.
- `scripts/quest_runtime/pr_review_cycle.py` — we added `_deferred_jsonl_from_backlog` and `allowlist_path_from_context` in this PR. Both walk UP from a context path (no double-apply risk) but worth a second look.
- `scripts/quest_review_intelligence.py` — CLI wrappers. Check that `--backlog`, `--deferred-jsonl`, `--input`, `--output` are handled consistently.

## Proposed approach

1. **Grep sweep.** Find every `Path(args.cwd)` / `Path(cwd)` / `Path(any_cwd_var)` construction in the runner stack.
2. **Classify each hit:** does the resulting path flow into a subprocess whose own `cwd` is the same var? If yes, it's the double-apply shape — fix.
3. **Fix with `resolve_path`** where it exists, or pass unchanged where the helper doesn't apply.
4. **Regression tests:** add one pytest that drives each corrected call site with a relative `--cwd` value and asserts the subprocess resolves the right file (not a double-nested path). The existing test_pr_review_cycle.py CLI-level pattern (`cwd=cwd_dir, --backlog=<elsewhere>`) is a good template.

## Files expected to change

- `scripts/quest_claude_probe.py` (confirmed — line 31)
- Any others the grep uncovers (estimated 0–3)
- New regression test(s) under `tests/unit/` or `tests/integration/` per fixed call site

## Tests

Minimum per fixed call site:

- Pass a relative non-dot `--cwd` value (e.g. `sub/dir`).
- Set up the expected file at `<cwd>/<bridge_or_target_file>`.
- Run the helper.
- Assert the subprocess found the file (no `FileNotFoundError` from a double-applied path).

For the `claude_probe.py` case specifically, that means running the probe helper from a parent directory with `--cwd repo`, where `repo/scripts/quest_claude_bridge.py` exists, and asserting no error.

## Acceptance Criteria

1. Every double-apply site in the runner stack is identified and fixed.
2. Each fix uses `resolve_path` (the existing helper) where applicable; otherwise passes the path through unchanged.
3. One regression test per fixed call site, run from a relative non-dot `--cwd`, asserts correct resolution.
4. Existing absolute-`--cwd` callers and default `--cwd .` callers continue to work unchanged.

## Out of Scope

- Broader refactor of the runner layer.
- Adding new `--cwd` flags to helpers that don't have them.
- Workspace/worktree path handling (separate concern, uses `worktree_path`).

## Priority

Medium. The bug only bites callers passing a relative non-dot `--cwd`. Quest itself runs with `--cwd .` by default, so most real invocations are unaffected. But the bug is a latent hazard: anyone who wires the runner into CI or a wrapper script passing a project-root name as `--cwd` will hit it silently.

## Follow-up Quest Prompt (Draft)

```text
/quest "Sweep runner modules for cwd-relative path double-apply bugs.

Reference: ideas/2026-04-20-runner-cwd-path-hygiene.md

DELIVERABLES

1. Grep the runner stack for every construction of the shape
   Path(args.cwd) / <path> (or equivalent) where the resulting path is
   later passed to a subprocess whose own cwd is the same value.

2. Fix each such site by either:
   - using resolve_path(cwd, path) from scripts/quest_runtime/claude_runner.py, or
   - passing the path through unchanged (letting subprocess cwd resolve it).

3. Add one pytest regression per fixed site, run with a relative non-dot
   --cwd value pointing at a fixture tree under tmp_path, asserting the
   target file resolves correctly (no FileNotFoundError from double-apply).

Known site: scripts/quest_claude_probe.py:31.

OUT OF SCOPE

- Broader runner refactors.
- Worktree path handling (separate concern)."
```
