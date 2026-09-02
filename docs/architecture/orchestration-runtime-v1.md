---
title: Orchestration Runtime Contract v1
purpose: Define the minimal reliable control-plane contract for all approaches and hosts.
audience: Runtime implementers and adapter maintainers
scope: Execution lifecycle, events, adapters, retries, and question propagation
status: active
owner: maintainers
last_updated: 2026-09-02
related:
  - docs/architecture/quest-platform-constellations.md
  - docs/guides/opencode-model-observations.md
  - ideas/handoff-validation-and-failure-ux.md
---

# Orchestration Runtime Contract v1

This is the normative contract for reliable orchestration.

If host/runtime behavior conflicts with this document, the host is wrong.

## 1) Runtime Object Model

### Run
- `run_id`
- `approach_name`
- `host` (`cli`, `claude`, `codex`, `opencode`, `cursor`, ...)
- `status`
- `started_at`, `ended_at`

### Step
- `step_id`
- `step_type` (`task`, `review`, `gate`, `parallel`, `reduce`)
- `status`
- `attempt`
- `timeout_ms`
- `policy` (`retry`, `fallback`, `ask_user`)

### Attempt
- `attempt_id`
- `adapter` (`claude_direct`, `codex_direct`, `mcp_codex`, ...)
- `model`
- `result` (`success`, `timed_out`, `failed`, `cancelled`)

## 2) Lifecycle States

Run states:
- `queued`
- `running`
- `heartbeat_late`
- `waiting_for_user`
- `failed`
- `completed`
- `cancelled`

Step states:
- `pending`
- `running`
- `timed_out`
- `retrying`
- `fallback_running`
- `needs_user`
- `failed`
- `completed`

## 3) Event Stream (append-only)

Each run writes ordered events to:
- `.quest/<run_id>/events.jsonl`

Minimum event types:
- `run_started`
- `step_started`
- `heartbeat`
- `adapter_call_started`
- `adapter_call_completed`
- `adapter_call_failed`
- `question_raised`
- `question_resolved`
- `retry_scheduled`
- `fallback_started`
- `step_completed`
- `run_completed`
- `run_failed`

Event shape:

```json
{
  "ts": "2026-03-04T19:00:00Z",
  "run_id": "quest_2026-03-04__1900",
  "event": "heartbeat",
  "step_id": "review_b",
  "data": {
    "adapter": "codex_direct",
    "elapsed_ms": 45000,
    "last_activity": "reading src/auth/session.ts"
  }
}
```

## 4) Heartbeat and Watchdog

- Heartbeat interval: 10-15 seconds.
- Heartbeat timeout: 2 intervals without heartbeat -> `heartbeat_late`.
- On `heartbeat_late`, watchdog must:
  1. emit `heartbeat_late`,
  2. attempt graceful cancel,
  3. apply retry/fallback policy.

No silent hangs.

## 5) Question Propagation Contract

Any agent question must become a structured event, not free text only.

`question_raised` required fields:
- `question_id`
- `step_id`
- `agent`
- `question`
- `blocking` (boolean)
- `assumption_if_unanswered`

If `blocking=false`, runtime proceeds with documented assumption.
If `blocking=true`, run enters `waiting_for_user`.

## 6) Adapter Interface (all transports)

All adapters must implement:
- `start(request) -> attempt_id`
- `poll(attempt_id) -> heartbeat/result/error`
- `cancel(attempt_id)`

Adapter result must include:
- `status`
- `text_output`
- `structured_findings` (optional)
- `usage` (tokens/cost when available)
- `activity` (files read/changed, commands, tool calls)

No adapter-specific payloads at orchestration boundary.

## 7) Retry and Fallback

Defaults:
- max retries per step: 2
- backoff: exponential with jitter
- fallback chain: explicit per step policy

Required behavior:
- retries use idempotency key
- repeated identical failure trips adapter circuit breaker
- circuit breaker emits explicit event
- when a rejected artifact is retry input, it remains immutable
- that repair attempt writes separate scratch artifacts, validates them, then atomically promotes them
- failed repair dispatch or validation retains both the rejected input and retry scratch for diagnosis

## 8) MCP Policy

MCP is treated as untrusted I/O.

Mandatory safeguards:
- per-call timeout
- bounded retries
- circuit breaker
- fallback adapter or model path
- structured error classification

No orchestration-critical logic may depend on unchecked MCP success.

## 9) Persistence and Replay

Required artifacts:
- `.quest/<run_id>/events.jsonl`
- `.quest/<run_id>/state.json`
- `.quest/<run_id>/artifacts/`

Recommended index:
- SQLite ledger for query/reporting.

Replay requirement:
- Runtime must reconstruct run timeline from persisted events.

## 10) KISS/YAGNI Guardrails

v1 intentionally excludes:
- distributed event bus,
- DAG scheduling engine,
- dynamic policy DSL,
- autonomous recursive swarm planning.

Add only after measured pain and explicit acceptance criteria.
