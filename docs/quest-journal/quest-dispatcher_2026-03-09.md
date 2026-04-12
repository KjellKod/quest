# Quest Dispatcher

Retired from `ideas/` on 2026-03-09.

The dispatcher/runtime concerns captured in the original note are now covered by the Codex-led Claude bridge runtime path:

- `scripts/quest_claude_probe.py` performs the bridge preflight check.
- `scripts/quest_claude_runner.py` is the Quest-owned entrypoint for Claude-designated roles in Codex-led runs.
- `scripts/quest_claude_bridge.py` remains the transport layer under that runner.
- Bridge-backed Claude execution defaults to `--permission-mode bypassPermissions`, adds explicit directory access, polls `handoff.json`, and logs `runtime=claude` in `context_health.log`.
- Workflow and role docs now describe host-specific runtime dispatch and solo-mode behavior.

This note is preserved as historical context only. The active source of truth is the current Quest workflow/runtime implementation and docs.
