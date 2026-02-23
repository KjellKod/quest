# Runtime Attribution Accuracy for Quest Context Health Logs

## Problem Observed
Quest completion reports can mislabel runtime by role name (for example `slot_a_claude`) instead of recording the backend that actually executed the step.

In one real run, all sub-agents were executed through Codex-backed tools, but compliance output showed mixed Claude/Codex because the runtime field followed role naming conventions.

## Why This Matters
- Runtime-level compliance metrics become misleading.
- Tooling quality signals (Claude vs Codex success rates) become untrustworthy.
- Postmortems and optimization decisions can target the wrong backend.

## Root Cause
`context_health.log` runtime attribution was sometimes treated as role metadata rather than invocation metadata.

## Proposed Fix (Quest Core)
1. Make runtime attribution source-of-truth explicit:
- `runtime=claude` only if invocation used Claude `Task(...)`.
- `runtime=codex` if invocation used `mcp__codex__codex` or Codex agent tools (`spawn_agent`/`worker`/`explorer`).

2. Keep role labels and runtime independent:
- Role label remains (`slot_a_claude`, `arbiter`, etc.) for phase accounting.
- Runtime is logged from actual backend used at invocation time.

3. Add a completion-time consistency check:
- If a role label implies Claude but runtime is Codex, allow it (valid fallback).
- Warn only when runtime is missing or inferred from label.

4. Add regression test/fixture for codex-only execution:
- Expected output must show `Claude agents: 0/0 (n/a)` when no true Claude calls happened.

## How Existing Runs Should Be Corrected
For runs already completed with incorrect runtime attribution:

1. Preserve original evidence first.
- Copy `context_health.log` to `context_health.log.bak` in the same quest log folder.

2. Correct runtime values to actual backend execution.
- Update only the `runtime=` field in each line.
- Do not modify timestamps, phase, agent, iter, handoff_json, or source fields.
- Role labels (`slot_a_claude`, etc.) remain unchanged; they are role identifiers.

3. Regenerate compliance summary from corrected log.
- Recompute runtime totals from corrected `runtime=` values only.
- Recompute role-level compliance by `(phase, agent)` pairs.
- Emit `Claude agents: 0/0 (n/a)` when no true Claude invocations occurred.

4. Store corrected outputs with provenance.
- Save regenerated summary as a separate artifact (for example `context_health_compliance_summary.txt`).
- Keep `.bak` file so correction remains auditable.

5. Record the correction event.
- Add a diary/journal note describing why correction was needed and exactly what fields changed.

## Implementation Guidance (Prevent Recurrence)
- In orchestrator code/prompt, bind runtime logging to invocation path:
  - `Task(...)` -> `runtime=claude`
  - `mcp__codex__codex` or Codex agents -> `runtime=codex`
- Never derive runtime from role names or filenames.
- Add a guard in completion summary generation that rejects inferred runtime attribution.

## Downstream Mitigation Already Applied
In a downstream repo, we corrected archived log entries, regenerated compliance summary, and updated local Quest instructions so runtime attribution is backend-derived, not label-derived.
