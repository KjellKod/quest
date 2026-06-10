#!/usr/bin/env python3
"""claude_bg_run — standalone runner for one Claude background-agent task.

PROOF OF CONCEPT (Step 1 of docs/implementation/claude-bg-run-script.md).

Quest-agnostic on purpose: this knows nothing about quest phases, handoff
schemas, or orchestration.json. It does exactly one thing — dispatch a single
`claude --bg` task, confirm it registered with the supervisor, wait for the
task's declared output FILES to appear (results never come from screen output),
surface a `needs_human` bubble-back if the agent asks for a decision, then tear
the session down — and return a small structured envelope.

Bubble-back loop (orchestrator stops and asks the human):
  1. Agent writes its question to the handoff file as {"status":"needs_human",...}
     and ends its turn. The runner returns status=needs_human (+session_id) and
     LEAVES THE SESSION ALIVE (no teardown), so it can be resumed.
  2. The orchestrator asks the human, then calls this runner again in resume mode
     (--resume <session_id> --answer "<reply>") to continue the SAME conversation.
     If resume fails and an original --prompt is available, it falls back to a
     fresh dispatch carrying the answer.

It is also the "noise firewall": the orchestrator only ever sees the tiny
envelope below, never the raw ANSI TUI buffer. `pty_capture()` demonstrates the
same strip-to-signal behavior for the interactive (`attach`) responder path.

Transport facts this encodes (validated against Claude Code 2.1.170):
  * `claude --bg` prints `backgrounded · <id>[ · <name>]` and may exit 0 even on
    the bypass-acceptance refusal, so success requires parsing the id AND
    confirming via `claude agents --json` — not the exit code.
  * `claude agents --json` reports per-session `state` (working/done/blocked) and
    `status` (busy/idle); completion and blocking are read from there.
  * `claude logs` is a raw TUI buffer; we strip it to a few signal lines only.

Run the built-in firewall demo (no `claude` needed):
    python3 scripts/claude_bg_run.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import re
import select
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---- exit codes (distinct so a shell/orchestrator can route without parsing) -
EXIT_OK = 0
EXIT_PRECONDITION = 2  # CLI/auth/bypass-acceptance missing
EXIT_DISPATCH_FAILED = 3  # never registered with the supervisor
EXIT_BLOCKED = 4  # leaked interactive prompt (state=blocked)
EXIT_TIMEOUT = 5
EXIT_SESSION_FAILED = 6  # vanished / done-without-artifacts (incomplete)
EXIT_NEEDS_HUMAN = 10  # actionable, not a failure: agent asked for a decision
EXIT_INTERRUPTED = 130  # Ctrl-C: session torn down before exit

_SHORTID_RE = re.compile(r"backgrounded\s*·\s*([0-9a-fA-F]+)")
_BYPASS_REFUSAL_RE = re.compile(
    r"bypass[- ]?permissions.*requires accepting|dangerously-skip-permissions",
    re.IGNORECASE,
)
# CSI / OSC / single-char escapes — covers the TUI redraw soup from `claude logs`.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"  # CSI
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC
    r"|\x1b[@-Z\\-_]"  # 2-char escapes
)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

COMPLETION_PROTOCOL = (
    "\n\nWhen you have finished you MUST write your output to the file(s):\n"
    "{files}\n"
    "Write files directly with the Write tool. Do not ask the user questions; "
    "if details are missing, make explicit assumptions and proceed. If you "
    "genuinely cannot proceed without a human decision, write your question to "
    "the handoff file instead of pausing.\n"
)


def strip_ansi(text: str) -> str:
    """Reduce raw terminal output to plain, signal-only text."""
    text = _ANSI_RE.sub("", text)
    text = _CTRL_RE.sub("", text)
    return text


def distill(text: str, max_lines: int = 12) -> str:
    """Strip ANSI then keep the last few non-empty lines (the live signal)."""
    lines = [ln.strip() for ln in strip_ansi(text).splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines[-max_lines:])


def pty_capture(
    argv: list[str],
    *,
    total_timeout: float = 30.0,
    idle_timeout: float = 3.0,
) -> tuple[int, str]:
    """Run `argv` under a headless PTY, consume the stream, return clean text.

    This is the noise-firewall primitive: the child believes it has a terminal
    (so it runs its full TUI), but we read the master side, throw the raw redraw
    stream away, and return only ANSI-stripped text. Used for the `attach`/`logs`
    responder path so TUI noise never reaches the orchestrator's context.
    """
    pid, fd = pty.fork()
    if pid == 0:  # child
        try:
            os.execvp(argv[0], argv)
        except OSError:
            os._exit(127)
    chunks: list[bytes] = []
    deadline = time.monotonic() + total_timeout
    last = time.monotonic()
    while True:
        if time.monotonic() > deadline:
            break
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
            last = time.monotonic()
        elif time.monotonic() - last > idle_timeout:
            break
    status = 0
    try:
        _, status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    return (os.WEXITSTATUS(status) if status else 0), strip_ansi(raw)


@dataclass
class Envelope:
    status: str
    short_id: str | None = None
    session_id: str | None = None
    name: str | None = None
    resumed: bool = False
    fell_back: bool = False
    wait_for: list[str] = field(default_factory=list)
    artifacts_found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    final_state: str | None = None
    duration_s: float = 0.0
    logs_tail: str = ""
    message: str = ""

    def exit_code(self) -> int:
        return {
            "ok": EXIT_OK,
            "precondition_failed": EXIT_PRECONDITION,
            "dispatch_failed": EXIT_DISPATCH_FAILED,
            "blocked": EXIT_BLOCKED,
            "timeout": EXIT_TIMEOUT,
            "session_failed": EXIT_SESSION_FAILED,
            "incomplete": EXIT_SESSION_FAILED,
            "needs_human": EXIT_NEEDS_HUMAN,
            "interrupted": EXIT_INTERRUPTED,
        }.get(self.status, EXIT_SESSION_FAILED)


class BgRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.a = args
        self.claude = shlex.split(args.claude_bin)

    # -- thin claude subcommand wrappers (all clean, structured) --------------
    def _claude(self, *sub: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
        return subprocess.run(
            [*self.claude, *sub],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def agents_json(self) -> list[dict[str, Any]]:
        cp = self._claude("agents", "--json")
        try:
            data = json.loads(cp.stdout)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def find_session(
        self, short_id: str | None, name: str, session_id: str | None = None
    ) -> dict[str, Any] | None:
        for row in self.agents_json():
            if row.get("kind") == "interactive":
                continue
            if (
                (short_id and row.get("id") == short_id)
                or row.get("name") == name
                or (session_id and row.get("sessionId") == session_id)
            ):
                return row
        return None

    def logs_tail(self, short_id: str) -> str:
        try:
            cp = self._claude("logs", short_id, timeout=15.0)
        except subprocess.SubprocessError:
            return ""
        return distill(cp.stdout + cp.stderr)

    def teardown(self, short_id: str) -> None:
        if self.a.keep:
            return
        for verb in ("stop", "rm"):
            try:
                self._claude(verb, short_id, timeout=20.0)
            except subprocess.SubprocessError:
                pass

    # -- message construction -------------------------------------------------
    def _read_source(self, value: str | None, file_value: str | None, what: str) -> str:
        if value is not None:
            text = value
        elif file_value == "-" or (file_value is None and not sys.stdin.isatty()):
            text = sys.stdin.read()
        elif file_value:
            text = Path(file_value).read_text(encoding="utf-8")
        else:
            raise ValueError(f"No {what} provided.")
        text = text.strip()
        if not text:
            raise ValueError(f"{what} is empty.")
        return text

    def _with_protocol(self, text: str) -> str:
        if self.a.wait_for and not self.a.no_protocol:
            files = "\n".join(f"  {p}" for p in self.a.wait_for)
            return text + COMPLETION_PROTOCOL.format(files=files)
        return text

    def build_prompt(self) -> str:
        return self._with_protocol(
            self._read_source(self.a.prompt, self.a.prompt_file, "prompt (use --prompt/--prompt-file or stdin)")
        )

    def build_answer(self) -> str:
        return self._with_protocol(
            self._read_source(self.a.answer, self.a.answer_file, "answer (resume mode needs --answer/--answer-file)")
        )

    def _fallback_prompt(self, answer: str) -> str:
        task = self._read_source(self.a.prompt, self.a.prompt_file, "prompt")
        return f"{task}\n\nThe human answered your earlier question:\n{answer}\n"

    # -- dispatch -------------------------------------------------------------
    def dispatch_argv(self, message: str, resume_sid: str | None) -> list[str]:
        argv = [*self.claude, "--bg", "--name", self.a.name]
        if resume_sid:
            argv += ["--resume", resume_sid]
        if self.a.model:
            argv += ["--model", self.a.model]
        if self.a.effort:
            argv += ["--effort", self.a.effort]
        argv += ["--permission-mode", self.a.permission_mode]
        if self.a.bg_isolation == "none":
            argv += ["--settings", json.dumps({"worktree": {"bgIsolation": "none"}})]
        for d in self.a.add_dir or []:
            argv += ["--add-dir", d]
        argv.append(message)
        return argv

    def dispatch_and_confirm(
        self, message: str, resume_sid: str | None
    ) -> tuple[str | None, str, str | None, dict[str, Any] | None]:
        """Returns (terminal_status_or_None, message, short_id, session_row)."""
        argv = self.dispatch_argv(message, resume_sid)
        try:
            cp = subprocess.run(argv, text=True, capture_output=True, timeout=60.0, check=False)
        except FileNotFoundError:
            return "precondition_failed", "claude CLI not found in PATH", None, None
        except subprocess.SubprocessError as exc:
            return "dispatch_failed", f"dispatch error: {exc}", None, None

        out = cp.stdout + cp.stderr
        if _BYPASS_REFUSAL_RE.search(out):
            return (
                "precondition_failed",
                "bypassPermissions not accepted — run `claude --dangerously-skip-permissions` once interactively, then retry.",
                None,
                None,
            )
        m = _SHORTID_RE.search(out)
        short_id = m.group(1) if m else None

        deadline = time.monotonic() + self.a.confirm_timeout
        row: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            row = self.find_session(short_id, self.a.name, resume_sid)
            if row:
                break
            time.sleep(self.a.poll_interval)
        if not row:
            return (
                "dispatch_failed",
                "session never registered with the supervisor (printed: %r)" % out.strip()[:200],
                short_id,
                None,
            )
        return None, "", short_id or row.get("id"), row

    # -- file/handoff helpers -------------------------------------------------
    @staticmethod
    def _nonempty(path: str) -> bool:
        try:
            return Path(path).stat().st_size > 0
        except OSError:
            return False

    def read_handoff(self) -> dict[str, Any] | None:
        if not self.a.handoff_file or not self._nonempty(self.a.handoff_file):
            return None
        try:
            return json.loads(Path(self.a.handoff_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    # -- the lifecycle --------------------------------------------------------
    def run(self) -> Envelope:
        t0 = time.monotonic()
        env = Envelope(status="", name=self.a.name, wait_for=list(self.a.wait_for))
        resume_mode = bool(self.a.resume)

        try:
            message = self.build_answer() if resume_mode else self.build_prompt()
        except (ValueError, OSError) as exc:
            env.status, env.message = "precondition_failed", str(exc)
            return env

        # DISPATCH (+ resume / fallback)
        if resume_mode:
            env.resumed = True
            status, msg, short_id, row = self.dispatch_and_confirm(message, self.a.resume)
            have_task = self.a.prompt is not None or bool(self.a.prompt_file)
            if status and self.a.fallback and have_task:
                try:
                    fb = self._fallback_prompt(message)
                except (ValueError, OSError) as exc:
                    env.status, env.message = "precondition_failed", str(exc)
                    return env
                env.resumed, env.fell_back = False, True
                status2, msg2, short_id, row = self.dispatch_and_confirm(fb, None)
                if status2:
                    env.status = status2
                    env.message = f"resume failed ({msg}); re-dispatch also failed ({msg2})"
                    env.short_id = short_id
                    env.duration_s = round(time.monotonic() - t0, 1)
                    return env
                env.message = f"resume failed ({msg}); re-dispatched fresh with the answer"
            elif status:
                env.status, env.message, env.short_id = status, msg, short_id
                env.duration_s = round(time.monotonic() - t0, 1)
                return env
        else:
            status, msg, short_id, row = self.dispatch_and_confirm(message, None)
            if status:
                env.status, env.message, env.short_id = status, msg, short_id
                env.duration_s = round(time.monotonic() - t0, 1)
                return env

        env.short_id = short_id
        env.session_id = (row or {}).get("sessionId")

        # WAIT
        deadline = time.monotonic() + self.a.timeout
        next_status = 0.0
        grace_left = 2
        try:
          while True:
            now = time.monotonic()
            if now > deadline:
                if env.short_id:
                    try:
                        self._claude("stop", env.short_id, timeout=15.0)
                    except subprocess.SubprocessError:
                        pass
                env.status, env.final_state = "timeout", env.final_state or "working"
                break

            hf = self.read_handoff()
            if hf and hf.get("status") == "needs_human":
                qs = hf.get("questions") or ([hf["question"]] if hf.get("question") else [])
                env.status, env.questions = "needs_human", [str(q) for q in qs]
                break

            if self.a.wait_for:
                if all(self._nonempty(p) for p in self.a.wait_for):
                    env.status = "ok"
                    break
            elif hf and hf.get("status") == "complete":
                env.status = "ok"
                break

            if now >= next_status:
                next_status = now + self.a.status_interval
                row = self.find_session(env.short_id, self.a.name, env.session_id)
                state = (row or {}).get("state") or (row or {}).get("status")
                env.final_state = state
                if row is None:
                    env.status = "session_failed"
                    env.message = "session disappeared from `claude agents` before completing"
                    break
                if state == "blocked":
                    env.status = "blocked"
                    env.message = "session is blocked on an interactive prompt (a permission hook likely did not cover it)"
                    break
                if state in ("done", "idle"):
                    if not self.a.wait_for and not self.a.handoff_file:
                        env.status = "ok"  # --no-wait: completion == reached done
                        break
                    grace_left -= 1
                    if grace_left <= 0:
                        env.status = "incomplete"
                        env.message = "session finished but declared output files are missing/empty"
                        break
            time.sleep(self.a.poll_interval)
        except KeyboardInterrupt:
            env.status = "interrupted"
            env.message = "interrupted by user; tearing the session down"

        # COLLECT
        env.artifacts_found = [p for p in self.a.wait_for if self._nonempty(p)]
        env.missing = [p for p in self.a.wait_for if not self._nonempty(p)]
        if env.status != "ok" and env.short_id:
            env.logs_tail = self.logs_tail(env.short_id)

        # TEARDOWN — but PRESERVE a needs_human session so it can be resumed.
        if env.short_id and env.status != "needs_human":
            self.teardown(env.short_id)
        env.duration_s = round(time.monotonic() - t0, 1)
        if not env.message and env.status == "ok":
            env.message = "completed; declared artifacts present"
        if env.status == "needs_human" and not env.message:
            env.message = "agent needs a human decision; session left alive — answer via --resume <session_id> --answer"
        return env


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run one Claude background-agent task to a file-based result.")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--prompt", help="task prompt (also the fallback task in resume mode)")
    src.add_argument("--prompt-file", help="path or '-' for stdin")
    p.add_argument("--resume", help="resume an existing session: continue this session_id")
    p.add_argument("--answer", help="resume mode: the human's reply to send back")
    p.add_argument("--answer-file", help="resume mode: read the reply from a file ('-' for stdin)")
    p.add_argument("--no-fallback", dest="fallback", action="store_false", help="resume mode: do not fall back to a fresh re-dispatch if resume fails")
    p.set_defaults(fallback=True)
    p.add_argument("--wait-for", action="append", default=[], help="output file(s) that must exist & be non-empty (repeatable)")
    p.add_argument("--handoff-file", help="optional JSON the agent writes; status needs_human bubbles back")
    p.add_argument("--model", default="")
    p.add_argument("--effort", default="", choices=["", "low", "medium", "high", "xhigh", "max"])
    p.add_argument("--permission-mode", default="bypassPermissions")
    p.add_argument("--add-dir", action="append", default=[])
    p.add_argument("--name", default=f"bgrun-{uuid.uuid4().hex[:8]}")
    p.add_argument("--bg-isolation", default="none", choices=["none", "inherit"])
    p.add_argument("--timeout", type=float, default=1800.0)
    p.add_argument("--confirm-timeout", type=float, default=20.0)
    p.add_argument("--poll-interval", type=float, default=2.0)
    p.add_argument("--status-interval", type=float, default=10.0)
    p.add_argument("--keep", action="store_true", help="skip teardown (debugging)")
    p.add_argument("--no-protocol", action="store_true", help="do not append the completion-protocol block")
    p.add_argument("--json", action="store_true", help="emit the result envelope as JSON")
    p.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"))
    p.add_argument("--self-test", action="store_true", help="run the PTY noise-firewall demo and exit")
    return p


def _self_test() -> int:
    """Prove the headless-PTY firewall: spawn a child that emits ANSI, get clean text."""
    noisy = "printf '\\033[2J\\033[H\\033[31mHELLO\\033[0m \\033[1mclean\\033[0m\\n'"
    code, text = pty_capture(["sh", "-c", noisy], total_timeout=5.0, idle_timeout=1.0)
    print(f"pty exit={code}")
    print(f"distilled signal: {text.strip()!r}")
    ok = "HELLO clean" in text and "\x1b" not in text
    print("PASS" if ok else "FAIL")
    return EXIT_OK if ok else EXIT_SESSION_FAILED


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        return _self_test()
    env = BgRunner(args).run()
    if args.json:
        print(json.dumps(asdict(env), indent=2))
    else:
        print(f"[{env.status}] {env.name} ({env.short_id}) — {env.message}")
        if env.questions:
            print("questions:")
            for q in env.questions:
                print(f"  - {q}")
        if env.logs_tail:
            print("--- logs (distilled) ---")
            print(env.logs_tail)
    return env.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
