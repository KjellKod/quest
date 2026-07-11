---
title: Deterministic JSON orchestration overrides
status: implemented
owner: maintainers
origin: host-safe-manifest-validation Quest startup discussion
implemented_by: PR #144
archived: 2026-07-11
---

# Deterministic JSON orchestration overrides

Implemented in PR #144 with a canonical `parse_override_input()` API, the
`parse_override_line()` compatibility wrapper, a stdin parser CLI required by
the chooser, shared validation, and format-equivalence regression coverage.
The implementation deliberately also accepts copied `"models": {...}` fragments
because that was the concrete user input that motivated the change.

## Problem

Quest's per-run orchestration chooser accepts comma-separated `role=model`
pairs. The canonical Python helper already parses that format deterministically,
but the chooser instructions do not require the orchestrator to call the helper.
An orchestrator may therefore reproduce the prose contract itself, reject an
otherwise natural JSON `models` block, or drift from the tested behavior.

## Recommended direction

Keep the conversational chooser in the Quest skill, but make input parsing and
validation deterministic.

1. Add a single parser such as `parse_override_input(text)` in
   `scripts/quest_runtime/orchestration.py`.
2. Preserve the current comma-separated format:

   ```text
   planner=gpt-5.6-sol, builder=gpt-5.6-terra
   ```

3. Also accept valid JSON in either of these forms:

   ```json
   {
     "planner": "gpt-5.6-sol",
     "builder": "gpt-5.6-terra"
   }
   ```

   ```json
   {
     "models": {
       "planner": "gpt-5.6-sol",
       "builder": "gpt-5.6-terra"
     }
   }
   ```

4. Normalize both formats into the existing `Override` representation, then
   reuse the canonical-role, solo-unused-role, model-availability, retry, and
   orchestration-writing rules.
5. Keep `parse_override_line()` as a compatibility wrapper if callers rely on
   it.
6. Provide a small stable CLI/entrypoint and require the Quest chooser to call
   it, so parsing is actually code-driven rather than merely described in
   Markdown.
7. Update the chooser prompt to show both supported formats.

## Validation and errors

- Reject unknown roles, duplicate roles, non-string or empty model values,
  malformed JSON, and unsupported top-level fields with specific messages.
- Treat partial mappings as partial overrides over the existing defaults.
- Ensure JSON and `role=model` inputs normalize to identical override lists and
  produce identical `orchestration.json` output.
- Preserve the existing three-attempt contract and availability checks.
- If a user submits a fragment such as `"models": {...}` without outer braces,
  return a clear instruction to wrap it in `{}` rather than adding a third
  JSON-like grammar.

## Scope boundary

This should be implemented as a separate Quest. It changes orchestration input
parsing, startup instructions, CLI behavior, and tests; it is intentionally not
part of the host-safe manifest-validation fix.

## Alternatives considered

- **Instruction-only JSON detection:** smallest change, but not reliably
  testable and repeats the drift that exposed this issue.
- **Fully code-driven interactive chooser:** deterministic but unnecessarily
  broad; it would need to own prompting, preflight state, retries, and artifact
  writing.
- **Deterministic parser with instructional UI:** preferred balance of KISS,
  testability, compatibility, and maintainable ownership.
