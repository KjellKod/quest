# Bug Report: Codex-Led Claude Dispatch Passes Runtime Sentinel as CLI Model

Date: 2026-07-03
Status: confirmed incident; implementation follow-up needed
Observed in: `/Users/kjell/ws/ai-tools/internal-ai-tool-platform`
Quest: `d1-cleanup_2026-07-03__1453`

## Summary

Codex-led Claude transport preflight can succeed while real role dispatch fails
because Quest treats the persisted model value `claude` as both:

1. a Quest runtime-family sentinel meaning "use the Claude runtime"; and
2. a concrete Claude CLI model alias passed through as `--model claude`.

The first meaning is valid inside Quest orchestration. The second is not valid
for the currently installed Claude CLI/account combination.

## Evidence

Preflight succeeded from the target repo:

```json
{
  "orchestrator": "codex",
  "second_model": "claude",
  "transport": "background-agent",
  "source": "live_probe",
  "available": true,
  "checks": {
    "claude_cli_installed": true,
    "claude_auth_logged_in": true,
    "bg_runner_script_exists": true,
    "agents_json_ok": true,
    "bg_reachable": true
  }
}
```

But real role dispatch through `scripts/quest_claude_runner.py` failed when the
caller passed `--model claude`:

```json
{
  "exit_code": 5,
  "handoff_state": "missing",
  "result_kind": "timeout",
  "transport": "background-agent",
  "stderr": "bg status=timeout; bg logs_tail=There's an issue with the selected model (claude). It may not exist or you may not have access to it. Run /model to pick a different model."
}
```

A separate reviewer reported the same Claude-side message:

```text
There's an issue with the selected model (claude). It may not exist or you may not have access to it. Run /model to pick a different model.
```

Raw background-agent dispatch succeeded when no explicit model was passed:

```sh
claude --bg --name quest-d1-cleanup-live-review \
  --permission-mode bypassPermissions \
  --settings '{"worktree":{"bgIsolation":"none"}}' \
  < .quest/d1-cleanup_2026-07-03__1453/phase_03_review/claude-live-review.prompt.md
```

Observed:

```text
backgrounded · ff1a5c35 · quest-d1-cleanup-live-review
```

That session completed and its transcript recorded the actual model as:

```text
claude-opus-4-8
```

The live review wrote the requested artifacts and ended with:

```text
CLAUDE_LIVE_REVIEW_STATUS: COMPLETE
```

## Suspected Root Cause

`scripts/quest_runtime/orchestration.py` defines default Claude-designated roles
as `claude` and classifies that value as the Claude runtime:

```python
DEFAULT_MODELS = {
    "planner": "claude",
    "plan-reviewer-a": "claude",
    "arbiter": "claude",
    "code-reviewer-a": "claude",
    "review-arbiter": "claude",
}

def is_claude_model(model: str) -> bool:
    return model == "claude" or model.startswith("claude-")
```

`scripts/quest_runtime/claude_runner.py` then forwards the same string into the
CLI command builder:

```python
"--model",
model,
```

So a role selected as runtime `claude` becomes:

```sh
claude --bg ... --model claude
```

The installed Claude CLI (`2.1.201`) documents model aliases like `opus` and
`sonnet`, or full model names such as `claude-fable-5`; it does not guarantee
that the runtime-family sentinel `claude` is a valid `--model` value.

Quest docs already hint at the split: manual verification examples use
`--model opus`, while the orchestration defaults use `claude`.

## Why This Matters

This failure mode is misleading:

- the transport is healthy;
- auth is healthy;
- `claude agents --json` works;
- raw `claude --bg` works;
- but Quest role dispatch times out with a model-selection message because the
  model string is invalid for the CLI.

That can make a working Codex-led Claude setup look flaky or unavailable, and
can incorrectly push a quest toward Codex-only fallback.

## Suggested Fix

Separate **runtime selection** from **Claude CLI model selection**.

Recommended contract:

1. Keep `models.<role> = "claude"` as a runtime-family sentinel if desired.
2. Before invoking `claude --bg` or `claude --print`, normalize the model:
   - if the configured model is exactly `claude`, omit `--model` and let the
     Claude CLI/account default choose the concrete model; or
   - map `claude` to a configurable concrete alias such as `opus`; do not hard
     code a stale full model string.
3. Preserve explicit concrete values such as `opus`, `sonnet`,
   `claude-opus-4-8`, or future full model IDs.
4. Add a diagnostic distinction:
   - transport unavailable;
   - CLI/auth unavailable;
   - CLI model rejected.
5. Update tests so `build_bg_cmd()` / `build_bridge_cmd()` do not pass
   `--model claude` for the runtime sentinel case.
6. Update docs/examples to state that `claude` means "Claude runtime" in
   orchestration config, not necessarily a valid Claude CLI `--model` token.

## Acceptance Criteria

- `scripts/quest_claude_runner.py --transport background-agent ... --model claude`
  no longer passes `--model claude` to the Claude CLI.
- A live background-agent role can run with default orchestration values on a
  machine where `claude --bg` works with the account default model.
- Explicit model aliases still pass through unchanged.
- If a concrete model is rejected by the CLI, Quest reports a model-selection
  error instead of a generic timeout or transport failure.
- Preflight and real role dispatch use equivalent model semantics, so a green
  preflight is not invalidated by a default model alias mismatch at dispatch.

## Secondary Observation

The installed Claude CLI help for `2.1.201` does not list a `claude logs`
subcommand, even though older Quest helper text says to run `claude logs <id>`.
In this environment, `claude logs ff1a5c35` was interpreted as a normal prompt
about logs. The background session transcript was still available under
`~/.claude/projects/.../<session-id>.jsonl`, and `claude agents --json` remained
usable. This is secondary to the model bug but worth checking when revisiting
background-agent diagnostics.
