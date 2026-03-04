# Opus ↔ Codex: Cross-Model Agent Communication

**Status:** Idea / RFC
**Author:** Kjell
**Date:** 2026-03-04
**Priority:** B (Codex → Opus) is the higher-value direction

---

## Problem

You want two frontier models — Claude Opus and OpenAI Codex — to collaborate on tasks, each playing to its strengths. Opus for reasoning, synthesis, and orchestration; Codex for fast code generation and execution in its sandboxed environment.

Two directions, very different implementation profiles.

---

## A) Opus Calling Codex

**The simpler direction.** Opus already has Bash access (via Cowork, Claude Code, or any agent framework). Codex CLI exposes `codex exec` for non-interactive use.

### Approach 1: Skill + Bash (Minimal)

A Cowork skill or Claude Code slash command that instructs Opus to shell out:

```bash
codex exec --model gpt-5.3-codex "your prompt here" 2>&1 | head -500
```

Opus gets stdout back directly. No temp files, no server, no framework.

**Pros:** Zero infrastructure. Works today. 3 lines in a SKILL.md.
**Cons:** No structured output. Timeout risk on long tasks. Output truncation at ~30k chars. No streaming.

### Approach 2: Python Subprocess Wrapper

A thin script that adds error handling, timeout, and structured output:

```python
#!/usr/bin/env python3
"""opus_calls_codex.py — thin bridge for Opus → Codex"""
import subprocess, json, sys

def ask_codex(prompt: str, model: str = "gpt-5.3-codex", timeout: int = 120) -> dict:
    try:
        result = subprocess.run(
            ["codex", "exec", "--model", model, prompt],
            capture_output=True, text=True, timeout=timeout
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "output": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": "", "stderr": f"Timed out after {timeout}s"}

if __name__ == "__main__":
    r = ask_codex(sys.argv[1])
    print(json.dumps(r, indent=2))
```

Opus invokes: `python3 opus_calls_codex.py "write hello world + identify yourself"`
Parses JSON back. Clean separation.

**Pros:** Structured returns. Timeout handling. Easy to extend (retries, logging).
**Cons:** Requires codex CLI installed. Still one-shot per call.

### Approach 3: MCP Server (Codex's built-in)

Per the docs, Codex can run as an MCP server:

```bash
claude mcp add codex -s user -- codex -m gpt-5.3-codex mcp-server
```

Opus (via Claude Code) sees Codex as a tool with typed parameters and returns.

**Pros:** First-class tool integration. Structured I/O. Persistent session possible.
**Cons:** Requires Claude Code specifically. MCP plumbing. Heavier setup.

### Recommendation for Direction A

Start with **Approach 1** for prototyping, graduate to **Approach 2** for anything real. Use **Approach 3** only if you need Codex as a persistent tool across many sessions.

---

## B) Codex Calling Opus (Higher Priority)

**The harder and more interesting direction.** Codex needs a way to reach Opus for reasoning, review, or synthesis tasks. Codex runs in its own sandbox and doesn't natively know about Claude.

### Approach 1: Claude CLI from Inside Codex

If `claude` CLI (Claude Code) is installed in the same environment:

```bash
# Inside a Codex session, instruct it to:
claude -p "Review this code for security issues: $(cat main.py)" --output-format json
```

Or using the `--dangerously-skip-permissions` flag for non-interactive:

```bash
echo "Summarize this architecture" | claude -p --output-format json
```

**Pros:** Direct. No server. Claude CLI handles auth.
**Cons:** Requires both CLIs installed side-by-side. Codex sandbox may restrict outbound calls. Auth token management.

### Approach 2: HTTP API Call (Most Portable)

Codex can run arbitrary code. Have it call the Anthropic API directly:

```python
#!/usr/bin/env python3
"""codex_calls_opus.py — Codex → Opus via API"""
import anthropic, sys, os

def ask_opus(prompt: str) -> str:
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
    message = client.messages.create(
        model="claude-opus-4-6-20250929",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

if __name__ == "__main__":
    print(ask_opus(sys.argv[1]))
```

Codex prompt: *"Run `python3 codex_calls_opus.py 'Review this code and identify bugs'` and incorporate the feedback."*

**Pros:** Works anywhere. No CLI dependency. Full control over model params, system prompt, temperature. Most portable across environments.
**Cons:** Requires API key in env. Cost per call. No tool use / multi-turn without more scaffolding.

### Approach 3: Claude as MCP Server for Codex

Claude Code can expose itself as an MCP server. If Codex supports MCP clients (or you wrap it):

```bash
# Claude side: serve as MCP
claude mcp-serve --port 3333

# Codex side: connect as client
codex exec --mcp-server http://localhost:3333 "Ask the reasoning model to review this"
```

**Note:** This is speculative — depends on both tools' MCP client/server support evolving. Worth tracking but not buildable today without custom glue.

**Pros:** Structured, bidirectional, sessionful.
**Cons:** Neither tool fully supports this pattern natively yet. Custom middleware needed.

### Approach 4: Agent-Mux / Orchestration Framework

Frameworks like [agent-mux](https://github.com/buildoak/agent-mux) or similar sit above both models and route tasks:

```
User → Orchestrator → routes "generate code" → Codex
                    → routes "review code"   → Opus
                    → routes "explain bug"   → Opus
                    → merges results         → User
```

**Pros:** Clean separation of concerns. Model-agnostic routing. Can add more models trivially. Context management. Retry/fallback logic.
**Cons:** Significant setup. Another dependency. Overkill for simple ping-pong. You're building infrastructure, not shipping features.

### Recommendation for Direction B

**Start with Approach 2 (API call).** It's the most portable, requires no special CLI setup inside Codex's sandbox, and gives you full control. The pattern is:

1. Codex generates code or encounters a task needing reasoning
2. Codex shells out to a Python script that calls the Anthropic API
3. Opus responds with review/synthesis/reasoning
4. Codex incorporates the response and continues

A working prototype exists at `ideas/claude_bridge.py` — implements Approach 2 with retries, timeout, and structured JSON output.

Graduate to **Approach 4** only when you have multiple models and routing logic that justifies the complexity.

---

## Decision Matrix

| Criterion | Skill+Bash | Python Wrapper | MCP | API Call | Agent-Mux |
|---|---|---|---|---|---|
| Setup time | Minutes | 30 min | Hours | 30 min | Days |
| Direction A (Opus→Codex) | ✅ Best start | ✅ Production | ✅ Works | — | ✅ Overkill |
| Direction B (Codex→Opus) | ❌ N/A | ✅ Best start | ⚠️ Not ready | ✅ Most portable | ✅ Overkill |
| Structured I/O | ❌ | ✅ | ✅ | ✅ | ✅ |
| Multi-turn context | ❌ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ |
| Sandbox-friendly | ✅ | ✅ | ⚠️ | ✅ | ⚠️ |
| Maintenance burden | None | Low | Medium | Low | High |

---

## Suggested Next Steps

1. **Prototype Direction B** with `codex_calls_opus.py` — get a round-trip working
2. **Prototype Direction A** with a Cowork skill — `codex exec` in Bash
3. **Validate sandbox constraints** — does Codex's sandbox allow outbound HTTPS to `api.anthropic.com`?
4. **Define the handoff protocol** — what does Opus send to Codex and vice versa? (System prompts, context windows, output format contracts)
5. **Decide if orchestration is needed** — if you find yourself writing routing logic, that's the signal to evaluate agent-mux

---

## Open Questions

- Does Codex's sandbox permit outbound API calls? (If not, file-based IPC is the fallback)
- What's the latency budget? Opus API calls add 5-30s depending on task complexity
- Should the models share context (conversation history) or work in isolation?
- Who owns error handling when one model fails mid-collaboration?
- Cost model: each cross-call burns tokens on both sides — is that acceptable for the use case?
