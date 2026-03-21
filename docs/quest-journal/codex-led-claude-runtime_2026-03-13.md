# Codex-Led Claude Bridge Runtime

- PR: #68
- Merged: 2026-03-13
- Outcome: First-class Codex-led Claude runtime path for Quest orchestration.

## What Shipped

- **Codex-led Claude bridge runtime** so Quest can dispatch Claude-designated roles through `scripts/quest_claude_runner.py` when Codex is the orchestrator.
- **Runtime helpers** (`quest_claude_probe.py`, bridge preflight) ensure the Claude CLI is available before dispatching.
- **Trust boundary preserved**: Codex retains privileged review roles while Claude handles builder/planner work through the bridge.
- Workflow and role docs updated to describe host-specific runtime dispatch and solo-mode behavior.

## Why It Matters

Before this, running a Quest with Codex as orchestrator required manual prompt engineering to invoke Claude. Now the bridge is a Quest-owned runtime path -- the operator describes the task, not the plumbing.
