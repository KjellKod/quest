# Handoff Validation and Failure UX

## Status: proposed

## Problem

The Quest workflow specifies that agents must write `handoff.json` files and that
the orchestrator should fall back to parsing `---HANDOFF---` text blocks when the
file is missing or unparsable. In practice, when fallback triggers there is no
diagnosis of *why* — the orchestrator silently continues and the only evidence is
a `source=text_fallback` entry in `context_health.log`. This makes it hard to
tell whether the agent never wrote the file, wrote it to the wrong path, or
produced invalid JSON.

## Goal

Two targeted improvements that strengthen the existing handoff contract without
adding new configuration surface area:

1. **Post-agent JSON schema validation** — catch malformed handoffs immediately.
2. **Diagnostic failure logging** — when fallback triggers, record the reason so
   failures are actionable.

## Proposed Changes

### 1. Add a handoff.json schema check after each agent invocation

After the orchestrator reads a `handoff.json` file, validate it against the
expected schema before using it for routing:

```bash
jq -e '
  (.status  | type == "string") and
  (.artifacts | type == "array") and
  (has("next")) and
  (.summary | type == "string")
' < handoff.json
```

If validation fails, treat the file as unparsable and fall back to text parsing
(same as today). The key difference is that the *reason* is now recorded (see
change 2 below).

Update the orchestrator instructions in `.skills/quest/delegation/workflow.md`
to include this check in the "Handoff File Polling" section, between steps 2
(read the file) and 3 (extract routing fields).

### 2. Enrich context_health.log with failure diagnostics

When fallback is triggered, the log entry should include a `reason` field that
classifies the failure:

| reason | meaning |
|--------|---------|
| `file_missing` | Expected path does not exist |
| `json_parse_error` | File exists but is not valid JSON |
| `schema_invalid` | File is valid JSON but missing required fields |
| `text_fallback_ok` | Text `---HANDOFF---` block parsed successfully |
| `text_fallback_fail` | Text fallback also failed (quest phase should block) |

Example enriched log line:

```
agent=planner phase=plan source=text_fallback reason=schema_invalid timestamp=...
```

This replaces the current binary `source=handoff_json | text_fallback` with a
three-part signal: source + reason + timestamp.

## What This Accomplishes

- **Faster debugging:** When a quest run has low handoff compliance, the log
  immediately tells you whether agents are skipping the file, writing bad JSON,
  or using wrong paths — no guesswork.
- **No new config knobs:** Works within the existing workflow. No toggles, no
  compliance thresholds to tune, no retry machinery.
- **Foundation for strict mode:** If we later decide to hard-fail on missing
  handoffs (as proposed in the strict-handoff-proposal), the diagnostic
  categories are already in place. Strict mode becomes: "treat any reason other
  than `handoff_json` as a phase failure" — a one-line policy change rather than
  a new subsystem.
- **Better compliance reporting:** The Step 7 completion summary can surface
  failure reasons alongside the compliance percentage, giving the user actionable
  information instead of just a number.

## Scope

- Edit: `.skills/quest/delegation/workflow.md` (Handoff File Polling section,
  context health logging section)
- No new files, scripts, or config entries required.

## Relationship to Other Ideas

This is a lightweight alternative to the full strict-handoff-proposal. It
delivers the observability benefits without the enforcement machinery (retry
logic, compliance gates, allowlist config). If the data from enriched logging
shows that handoff failures are rare and easily fixed, strict mode may not be
needed at all.
