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
     (--resume <ref> --answer "<reply>") to continue the SAME conversation.
     <ref> may be the session_id, the agent's short id, or its NAME — names are
     resolved live via `claude agents --json`, so a session renamed in the agent
     view stays resumable. If resume fails and an original --prompt is available,
     it falls back to a fresh dispatch carrying the answer.
  3. Resuming spawns a NEW background agent (new short id, NEW session id) that
     continues the conversation; the parked parent agent stays alive and would be
     orphaned, so after the new agent is confirmed the runner retires the parent.
     The envelope reports the NEW session_id (chain further resumes off that) and
     `resumed_from` (the session id that was continued).

It is also the "noise firewall": the orchestrator only ever sees the tiny
envelope below, never the raw ANSI TUI buffer. `pty_capture()` demonstrates the
same strip-to-signal behavior for the interactive (`attach`) responder path.

Transport facts this encodes (observed across Claude Code 2.1.x):
  * `claude --bg` prints `backgrounded · <id>[ · <name>]` and may exit 0 even on
    the bypass-acceptance refusal, so success requires parsing the id AND
    confirming via `claude agents --json` — not the exit code.
  * `claude agents --json` reports per-session `state` (working/done/blocked) and
    `status` (busy/idle); completion and blocking are read from there. A parked
    (idle, awaiting-input) session ALSO reads `state==blocked`, so resume-mode
    polling must never match the parked parent's row (id/name take precedence
    over sessionId).
  * Early 2.1.x builds did not expose scriptable `logs|stop|rm`; this runner
    still uses the portable fallback: transcript JSONL for log tails and
    signalling the `pid` carried in the `agents --json` row. Claude Code 2.1.191
    exposes real `claude logs <id>` and `claude stop <id>` commands; adopting
    those subcommands is tracked as follow-up cleanup.
  * `claude --bg --resume <sid>` FORKS: the new agent continues the conversation
    under a NEW sessionId (daemon roster: launch.mode=resume, fork=true).

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
import signal
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
_SESSION_ID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}")
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
    resumed_from: str | None = None
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
        self,
        short_id: str | None = None,
        name: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Match a background row by short id, then name, then sessionId.

        STRICT PRECEDENCE, not OR-in-row-order: when resuming, the parked parent
        session matches `sessionId` and appears earlier in the list than the new
        agent — an unordered match returns the parent (whose state is `blocked`
        merely because it is idle awaiting input) and misreports the run.
        """
        rows = [r for r in self.agents_json() if r.get("kind") != "interactive"]
        for key, want in (("id", short_id), ("name", name), ("sessionId", session_id)):
            if not want:
                continue
            for row in rows:
                if row.get(key) == want:
                    return row
        return None

    def resolve_resume_target(self, ref: str) -> tuple[str | None, str | None]:
        """Resolve --resume <ref> to (session_id, parent_short_id).

        <ref> may be a session id, an agent short id, or an agent NAME (incl. one
        renamed in the agent view) — resolved live against `claude agents --json`.
        A session-id-shaped ref with no live row is passed through as-is (the
        transcript may still be resumable); anything else unresolved is an error.
        """
        row = self.find_session(short_id=ref, name=ref, session_id=ref)
        if row and row.get("sessionId"):
            return row["sessionId"], row.get("id")
        if _SESSION_ID_RE.fullmatch(ref):
            return ref, None
        return None, None

    def logs_tail(self, session_id: str | None) -> str:
        """Tail of the session transcript (~/.claude/projects/*/<sid>.jsonl).

        Claude Code 2.1.191 has `claude logs <id>`, but this runner still uses
        transcript JSONL as the portable fallback. Returns the last few
        assistant-text lines, distilled.
        """
        if not session_id:
            return ""
        root = Path(self.a.transcripts_root).expanduser()
        matches = list(root.glob(f"*/{session_id}.jsonl")) or list(root.glob(f"{session_id}.jsonl"))
        if not matches:
            return ""
        texts: list[str] = []
        try:
            for line in matches[0].read_text(encoding="utf-8").splitlines():
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "assistant":
                    continue
                for block in obj.get("message", {}).get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
        except OSError:
            return ""
        return distill("\n".join(texts[-4:]))

    def stop_session(self, short_id: str | None) -> None:
        """Stop a background agent by signalling its supervisor-reported pid.

        Claude Code 2.1.191 has `claude stop <id>`, but this runner still uses
        the older pid-signalling fallback. The daemon may RESPAWN a parked
        session once from its spare pool after a kill (the row keeps its id but
        shows a fresh pid), so keep signalling the row's *current* pid until the
        row settles — drops its pid ("settled (killed)" in the daemon log) or
        leaves the listing. Settled rows may linger pid-less in `agents --json`;
        that is retired enough.
        """
        if not short_id:
            return
        for attempt in range(6):
            row = self.find_session(short_id=short_id)
            pid = (row or {}).get("pid")
            if not isinstance(pid, int):
                return  # gone, or settled with no live process
            sig = signal.SIGTERM if attempt < 2 else signal.SIGKILL
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
            time.sleep(self.a.poll_interval)

    def teardown(self, short_id: str | None) -> None:
        if self.a.keep:
            return
        self.stop_session(short_id)

    def sweep(self, prefix: str) -> int:
        """Stop every background session whose name starts with `prefix`.

        Orphan recovery for orchestrators that crashed between dispatch and
        teardown (e.g. quest start/resume runs `--sweep quest-<id>-`).
        """
        rows = [
            row
            for row in self.agents_json()
            if row.get("kind") != "interactive"
            and isinstance(row.get("name"), str)
            and row["name"].startswith(prefix)
            and isinstance(row.get("pid"), int)
        ]
        for row in rows:
            self.stop_session(row.get("id"))
            print(f"swept {row.get('id')} ({row.get('name')})")
        print(f"sweep complete: {len(rows)} session(s) matching {prefix!r} stopped")
        return EXIT_OK

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
    def dispatch_argv(self, resume_sid: str | None) -> list[str]:
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
        return argv

    def dispatch_and_confirm(
        self, message: str, resume_sid: str | None
    ) -> tuple[str | None, str, str | None, dict[str, Any] | None]:
        """Returns (terminal_status_or_None, message, short_id, session_row)."""
        argv = self.dispatch_argv(resume_sid)
        try:
            cp = subprocess.run(
                argv,
                input=message,
                text=True,
                capture_output=True,
                timeout=60.0,
                check=False,
            )
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
            # Confirm by short id / name ONLY: in resume mode the parked parent's
            # row matches `sessionId == resume_sid` and would falsely confirm a
            # dispatch that never registered.
            row = self.find_session(short_id, self.a.name)
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

    @staticmethod
    def _clear_file(path: str) -> None:
        """Truncate a pre-existing file so stale content cannot satisfy this run."""
        try:
            target = Path(path)
            if target.is_file():
                target.write_text("", encoding="utf-8")
        except OSError:
            pass  # an unwritable path surfaces later as incomplete, never as false success

    def _clear_stale_outputs(self, *, include_wait_for: bool) -> None:
        """Stale-state guard: pre-existing outputs must not satisfy THIS run.

        Fresh dispatch clears the handoff and every --wait-for target. Resume
        clears only the handoff (a parked needs_human would re-trigger the
        WAIT loop instantly) and keeps --wait-for files the parked session
        already wrote — the resumed agent will not rewrite work it believes
        is done.
        """
        if self.a.handoff_file:
            self._clear_file(self.a.handoff_file)
        if include_wait_for:
            for path in self.a.wait_for:
                self._clear_file(path)

    def _snapshot_outputs(self, *, include_wait_for: bool) -> dict[str, bytes]:
        """Capture non-empty parked outputs (handoff + optionally --wait-for) so
        the stale-guard clear can be reversed if a re-dispatch is not confirmed.

        Bytes, not text: --wait-for artifacts may be binary or non-UTF-8, so
        read_text() could raise (before the restore runs) or corrupt content.
        """
        paths: list[str] = []
        if self.a.handoff_file:
            paths.append(self.a.handoff_file)
        if include_wait_for:
            paths.extend(self.a.wait_for)
        snapshot: dict[str, bytes] = {}
        for path in paths:
            if not self._nonempty(path):
                continue
            try:
                snapshot[path] = Path(path).read_bytes()
            except OSError:
                pass
        return snapshot

    def _restore_outputs(self, snapshot: dict[str, bytes]) -> None:
        for path, content in snapshot.items():
            try:
                Path(path).write_bytes(content)
            except OSError:
                pass

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
        parent_short_id: str | None = None
        if resume_mode:
            resume_sid, parent_short_id = self.resolve_resume_target(self.a.resume)
            if not resume_sid:
                env.status = "precondition_failed"
                env.message = (
                    f"--resume target {self.a.resume!r} matches no live agent "
                    "(by session id, short id, or name) and is not session-id-shaped"
                )
                return env
            env.resumed = True
            env.resumed_from = resume_sid
            status, msg, short_id, row = self.dispatch_and_confirm(message, resume_sid)
            have_task = self.a.prompt is not None or bool(self.a.prompt_file)
            if status and self.a.fallback and have_task:
                try:
                    fb = self._fallback_prompt(message)
                except (ValueError, OSError) as exc:
                    env.status, env.message = "precondition_failed", str(exc)
                    return env
                env.resumed, env.fell_back = False, True
                # Committing to a fresh run: clear the parked handoff + wait_for
                # as the stale guard (the answer is carried into the new prompt).
                # Snapshot them FIRST so a failed fresh dispatch can restore the
                # parked session's question AND any artifacts it already wrote —
                # clearing before the re-dispatch is confirmed must be reversible
                # (PR #137 review).
                parked_outputs = self._snapshot_outputs(include_wait_for=True)
                self._clear_stale_outputs(include_wait_for=True)
                status2, msg2, short_id, row = self.dispatch_and_confirm(fb, None)
                if status2:
                    # Fresh re-dispatch failed too: restore the parked outputs so
                    # the question (and any artifacts) survive for a later retry,
                    # and leave the parked session alive (teardown below is not
                    # reached).
                    self._restore_outputs(parked_outputs)
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
            self._clear_stale_outputs(include_wait_for=True)
            status, msg, short_id, row = self.dispatch_and_confirm(message, None)
            if status:
                env.status, env.message, env.short_id = status, msg, short_id
                env.duration_s = round(time.monotonic() - t0, 1)
                return env

        env.short_id = short_id
        env.session_id = (row or {}).get("sessionId")

        # Clear the parked handoff only now that the resume continuation is
        # confirmed — a failed resume dispatch (returned above) must leave the
        # parked session's needs_human question on disk. --wait-for files the
        # parked agent already wrote are kept (the resumed agent won't redo
        # them). The fallback path cleared its own stale outputs above.
        if resume_mode and not env.fell_back:
            self._clear_stale_outputs(include_wait_for=False)

        # The conversation has moved on (resumed into a new agent, or re-dispatched
        # fresh); retire the parked parent so it is not orphaned. Respects --keep.
        if parent_short_id and parent_short_id != short_id:
            self.teardown(parent_short_id)

        # WAIT
        deadline = time.monotonic() + self.a.timeout
        next_status = 0.0
        grace_left = 2
        try:
          while True:
            now = time.monotonic()
            if now > deadline:
                env.status, env.final_state = "timeout", env.final_state or "working"
                break  # final teardown below stops the session

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
                row = self.find_session(env.short_id, self.a.name)
                state = (row or {}).get("state") or (row or {}).get("status")
                env.final_state = state
                if row is None:
                    env.status = "session_failed"
                    env.message = "session disappeared from `claude agents` before completing"
                    break
                if state == "blocked":
                    env.status = "blocked"
                    # Opportunistic only: Claude Code 2.1.191's initial-prompt
                    # parked signal was observed in dispatch stdout, not here.
                    detail = row.get("waitingFor") or row.get("needs") or row.get("detail")
                    detail_text = str(detail) if detail else ""
                    if "send a prompt to start" in detail_text.lower():
                        env.message = (
                            "background session registered but did not consume "
                            "the initial prompt (Claude CLI reported: "
                            f"{detail_text})"
                        )
                    else:
                        env.message = "session is blocked on an interactive prompt " + (
                            f"({detail_text})" if detail_text else "(a permission hook likely did not cover it)"
                        )
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
        if env.status != "ok":
            env.logs_tail = self.logs_tail(env.session_id)

        # TEARDOWN — by default PRESERVE a needs_human session so it can be
        # resumed (standalone use). Callers with no resume loop pass
        # --teardown-on-needs-human to tear it down like the bridge instead of
        # orphaning a session nobody will collect.
        preserve_for_resume = (
            env.status == "needs_human" and not self.a.teardown_on_needs_human
        )
        if env.short_id and not preserve_for_resume:
            self.teardown(env.short_id)
        env.duration_s = round(time.monotonic() - t0, 1)
        if not env.message and env.status == "ok":
            env.message = "completed; declared artifacts present"
        if env.status == "needs_human" and not env.message:
            env.message = (
                "agent needs a human decision; session torn down (caller has no resume loop)"
                if self.a.teardown_on_needs_human
                else "agent needs a human decision; session left alive — answer via --resume <session_id|short_id|name> --answer"
            )
        return env


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run one Claude background-agent task to a file-based result.")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--prompt", help="task prompt (also the fallback task in resume mode)")
    src.add_argument("--prompt-file", help="path or '-' for stdin")
    p.add_argument("--resume", help="resume an existing session: session id, agent short id, or agent name (rename-safe)")
    p.add_argument("--answer", help="resume mode: the human's reply to send back")
    p.add_argument("--answer-file", help="resume mode: read the reply from a file ('-' for stdin)")
    p.add_argument("--no-fallback", dest="fallback", action="store_false", help="resume mode: do not fall back to a fresh re-dispatch if resume fails")
    p.set_defaults(fallback=True)
    p.add_argument("--wait-for", action="append", default=[], help="output file(s) that must exist & be non-empty (repeatable)")
    p.add_argument("--handoff-file", help="optional JSON the agent writes; status needs_human bubbles back")
    p.add_argument(
        "--teardown-on-needs-human",
        action="store_true",
        help=(
            "tear the session down on needs_human instead of leaving it alive "
            "for --resume. For callers with no resume loop (e.g. Quest): "
            "needs_human then behaves like the bridge — surfaced promptly, "
            "session torn down — rather than parked until a human answers."
        ),
    )
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
    p.add_argument(
        "--transcripts-root",
        default="~/.claude/projects",
        help="where session transcript JSONLs live (logs_tail source)",
    )
    p.add_argument("--self-test", action="store_true", help="run the PTY noise-firewall demo and exit")
    p.add_argument("--sweep", help="stop all background sessions whose NAME starts with this prefix, then exit (orphan recovery)")
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
    if args.sweep:
        return BgRunner(args).sweep(args.sweep)
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
