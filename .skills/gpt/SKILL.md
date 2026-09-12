---
name: gpt
description: Delegate a task to OpenAI Codex through the Quest CLI runner from Claude-led sessions. Use when the user invokes /gpt, asks to use codex, or wants a second opinion from a different model.
---

# Skill: GPT (Codex)

Claude-led sessions use the installed `scripts/quest_codex_runner.py` helper around `codex exec`. Quest roles use its `role` mode and canonical `.skills/quest/delegation/workflow.md` instructions; standalone `/gpt` uses `task` mode below.

## Not for Codex-Led Quest Role Dispatch

If you are already Codex, Codex-led Codex roles must use local Codex subagents using the saved model and effort. Never substitute MCP or nested `codex exec`. If native controls are missing, inherit only after verifying that parent settings match; otherwise block. This skill does not override Quest Build gates or authorize a runtime switch.

## Prerequisites and authentication

Install Codex CLI and prefer `codex login`, then `codex login status` reporting ChatGPT. No MCP server, shim or plugin is required. The runner checks required exec capabilities before invoking the CLI.

Resolve authentication explicitly: user selection first, otherwise `.ai/allowlist.json` `codex_auth_mode`, otherwise `cached`. Quest roles instead use the saved orchestration setting. `cached` uses the CLI's saved identity and excludes ambient `CODEX_API_KEY` and `OPENAI_API_KEY`; report the detected identity kind. Explicit `api-key` uses `CODEX_API_KEY`, otherwise `OPENAI_API_KEY`, from the existing environment and does not require or mutate cached login. Never read keys from `.env`, request secrets in chat, print keys, or silently switch billing/authentication. Codex manages token refresh.

Run a no-inference setup probe using the installed helper:

```bash
python3 "<installation-root>/scripts/quest_codex_runner.py" probe \
  --cwd "<target-workspace>" --auth cached
```

Use `--auth api-key` only when that mode was explicitly selected. Setup readiness does not prove successful inference or model availability.

## Step 1: Resolve and disclose settings

Before dispatch, state the task, resolved model/effort, auth mode and sandbox. Follow authorization already supplied by the user or Quest gates; do not ask again for an already-authorized task. Any change of runtime, model, auth/billing or broader permissions requires an explicit choice.

For standalone `/gpt`, explicit model/effort choices win; otherwise read `.ai/allowlist.json` `codex_fallback_model` and optional `codex_reasoning_effort`. When unset, omit the corresponding option and disclose runtime defaults. Do not invent a model catalog or replace a rejected model automatically.

## Step 2: Invoke the shared runner

Write a UTF-8 prompt file with the host's file-writing tool. Include the task, absolute context paths, constraints and expected output. Invoke the installed runner, keeping installation root, target cwd and output root independent:

```bash
python3 "<installation-root>/scripts/quest_codex_runner.py" task \
  --cwd "<target-workspace>" --prompt-file "<absolute-prompt-file>" \
  --output-dir "<absolute-output-directory>" --auth cached \
  --model "<resolved-model>" --effort "<resolved-effort>" \
  --sandbox workspace-write --timeout 1800
```

Omit `--model` or `--effort` when that setting is unspecified. The helper passes prompt bytes on stdin and constructs CLI argument arrays. Paths may contain spaces; use absolute paths and quote each argument. Add `--allow-non-git` only for intentional non-Git execution. The runner adds external artifact directories to the child write scope. Never initialize a repository or broaden permissions as an implicit workaround.

Use `workspace-write` for implementation and artifact-producing reviews, `read-only` for analysis with no child file writes. `danger-full-access` requires explicit permission or equivalent persisted approval. Actual host permissions still apply; surface a denied runner command for scoped remediation, never install wildcard Bash/MCP permissions.

## Prompts and follow-ups

Codex runs non-interactively. Include enough context to proceed with explicit assumptions; if unsafe to proceed, it returns blocked. For follow-ups, create a fresh task that references the prior output files and states the new work. This helper does not provide a session-resume contract.

## Results and failures

Wait for the full invocation, normally up to 1800 seconds. Silence alone is not failure. Read the result envelope and output files; summarize useful results without dumping raw events or credentials. Effective model/effort requires runtime metadata, not model self-identification. Unknown values remain unknown.

Exit 0 alone is insufficient: task success requires current-attempt valid events, a completed turn and a nonempty final response. Verify any user-requested file output directly. Quest `role` mode additionally validates canonical handoff and required artifacts, including planner lifecycle and findings contracts.

Only `malformed_output` or `artifact_missing` with `retry_eligible: true` permits one same-settings artifact-first retry after clean teardown. All other failures block with the specific result kind. Timeout/cancellation terminate and reap the process tree; `teardown_failed` blocks retry and further dispatch. Never replace missing artifacts with prose, silently raise effort, or fall back to another runtime/authentication mode.
