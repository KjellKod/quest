#!/usr/bin/env python3
"""claude_bg_run — standalone runner for one Claude background-agent task.

Step 1 of the bg-transport migration; the original spec and its empirical
findings are archived at docs/implementation/history/claude-bg-run-script.md.

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
  * Claude CLI 2.1.x background-session management subcommands are not treated
    as a stable scripting contract here (2.1.201 ships no scriptable
    `logs`/`stop`). This runner deliberately uses ONLY the portable mechanisms:
    transcript JSONL for log tails and signalling the `pid` carried in the
    `agents --json` row. Adopting real subcommands, if the CLI ever ships them,
    is a contained follow-up: the mechanisms live in `logs_tail`/`stop_session`.
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
EXIT_RATE_LIMITED = 7  # account session/rate limit; retry after reset
EXIT_STARTUP_DIALOG = 8  # trust/bypass dialog before the prompt was consumed
EXIT_MODEL_REJECTED = 9  # CLI rejected the selected model
EXIT_NEEDS_HUMAN = 10  # actionable, not a failure: agent asked for a decision
EXIT_INTERRUPTED = 130  # Ctrl-C: session torn down before exit

_SHORTID_RE = re.compile(r"backgrounded\s*·\s*([0-9a-fA-F]+)")
_SESSION_ID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}")
_BYPASS_REFUSAL_RE = re.compile(
    r"bypass[- ]?permissions.*requires accepting|dangerously-skip-permissions",
    re.IGNORECASE,
)
# Anchored to the CLI's own phrasing ("You've hit your session limit · resets
# 2pm"): bare "session limit"/"rate limit" substrings would false-positive on
# assistant prose that merely DISCUSSES limits (routine in infra/AI repos).
_RATE_LIMIT_RE = re.compile(
    r"(?:you(?:'ve| have) (?:hit|reached) (?:your|the) (?:\d+-hour )?(?:session|rate|usage) limit"
    r"|(?:session|rate|usage) limit (?:reached|exceeded))",
    re.IGNORECASE,
)
_RESET_AT_RE = re.compile(
    r"\b(?:resets?|reset(?:s)?(?: at| on)?|try again(?: at| after)?)\s+"
    r"([^\n.;]+(?:\([^)]+\))?)",
    re.IGNORECASE,
)
_MODEL_REJECTED_RE = re.compile(
    r"(?:(?:there(?:'s| is)\s+an\s+)?(?:issue|problem)\s+with\s+the\s+selected\s+model"
    r"|(?:invalid|unknown|unsupported)\s+selected\s+model)"
    r"(?:\s*(?:\(|:)\s*([A-Za-z0-9._:/-]+))?",
    re.IGNORECASE,
)
_STARTUP_DIALOG_RE = re.compile(
    r"(?:send a prompt to start|trust this folder|do you trust|accept.*(?:trust|bypass)|"
    r"bypasspermissions.*accept|dangerously-skip-permissions)",
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
    exited = False  # EOF/EIO: the child ended its own stream
    timed_out = False
    while True:
        if time.monotonic() > deadline:
            timed_out = True
            break
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                exited = True
                break
            if not data:
                exited = True
                break
            chunks.append(data)
            last = time.monotonic()
        elif time.monotonic() - last > idle_timeout:
            break
    try:
        os.close(fd)
    except OSError:
        pass
    # Never leave the loop with a live child: a persistent TUI (the attach
    # use-case) never exits on its own and would outlive the runner.
    status = _reap_pty_child(pid, kill=not exited)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    if timed_out:
        code = 124  # the stream never went quiet: surface as failure, not truncation
    elif not exited:
        code = 0  # idle-quiescence capture of a live TUI: success by design
    elif os.WIFEXITED(status):
        code = os.WEXITSTATUS(status)
    elif os.WIFSIGNALED(status):
        code = 128 + os.WTERMSIG(status)
    else:
        code = 0
    return code, strip_ansi(raw)


def _reap_pty_child(pid: int, *, kill: bool) -> int:
    """Terminate (when asked) and reap the PTY child; return its wait status.

    Reaping unconditionally — not WNOHANG-and-hope — also closes the race where
    a child that had just exited read back as status 0.
    """
    if kill:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    grace = time.monotonic() + 2.0
    while time.monotonic() < grace:
        try:
            wpid, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return 0
        if wpid == pid:
            return status
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        return os.waitpid(pid, 0)[1]
    except ChildProcessError:
        return 0


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
    reset_at: str | None = None
    rejected_model: str | None = None
    teardown_failed: bool = False
    teardown_survivor_id: str | None = None
    teardown_survivor_name: str | None = None
    teardown_survivor_session_id: str | None = None

    def exit_code(self) -> int:
        return {
            "ok": EXIT_OK,
            "precondition_failed": EXIT_PRECONDITION,
            "dispatch_failed": EXIT_DISPATCH_FAILED,
            "blocked": EXIT_BLOCKED,
            "rate_limited": EXIT_RATE_LIMITED,
            "startup_dialog": EXIT_STARTUP_DIALOG,
            "model_rejected": EXIT_MODEL_REJECTED,
            "timeout": EXIT_TIMEOUT,
            "session_failed": EXIT_SESSION_FAILED,
            "incomplete": EXIT_SESSION_FAILED,
            "needs_human": EXIT_NEEDS_HUMAN,
            "interrupted": EXIT_INTERRUPTED,
        }.get(self.status, EXIT_SESSION_FAILED)


@dataclass
class StopResult:
    settled: bool
    survivor_id: str | None = None
    survivor_name: str | None = None
    survivor_session_id: str | None = None
    # "working" when retirement was REFUSED because the row is actively
    # working (likely a concurrent orchestrator) — distinct from a failed kill.
    reason: str | None = None


@dataclass
class DispatchResult:
    terminal_status: str | None
    message: str
    short_id: str | None
    row: dict[str, Any] | None
    reset_at: str | None = None
    rejected_model: str | None = None


def _parse_reset_at(text: str) -> str | None:
    match = _RESET_AT_RE.search(text)
    return match.group(1).strip() if match else None


def _parse_rejected_model(text: str) -> str | None:
    match = _MODEL_REJECTED_RE.search(text)
    if match and match.group(1):
        return match.group(1).strip(").,;: ")
    return None


def _row_active_or_unknown(row: dict) -> bool:
    """True when a live roster row must NOT be auto-killed.

    Actively working/busy rows are a concurrent orchestrator's in-flight work;
    a row carrying NEITHER state nor status is outside the documented roster
    contract — treat unknown as active, because guessing wrong kills work.
    Single owner of this rule for both the same-name guard and sweep().
    """
    activity = {row.get("state"), row.get("status")} - {None}
    return not activity or bool(activity & {"working", "busy"})


def _classify_limit_or_model(text: str) -> tuple[str, str, str | None, str | None] | None:
    """Classify rate-limit / model-rejection evidence into
    (status, message, reset_at, rejected_model).

    Single source of truth for both dispatch-time output and the WAIT loop's
    blocked-state evidence — the wording and parsing must never drift between
    the two exit paths. Returns None when the text carries neither signal.
    """
    if _RATE_LIMIT_RE.search(text):
        reset_at = _parse_reset_at(text)
        reset = f" after reset ({reset_at})" if reset_at else " after the session limit resets"
        return (
            "rate_limited",
            "Claude background session hit the account session limit; "
            f"retry{reset} or ask the human whether to choose a different model.",
            reset_at,
            None,
        )
    if _MODEL_REJECTED_RE.search(text):
        rejected = _parse_rejected_model(text)
        suffix = f" ({rejected})" if rejected else ""
        return (
            "model_rejected",
            f"Claude CLI rejected the selected model{suffix}; "
            "choose a supported Claude model or the `claude` sentinel.",
            None,
            rejected,
        )
    return None


class BgRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.a = args
        self.claude = shlex.split(args.claude_bin)
        # Set once a dispatch is CONFIRMED: the only session interrupt cleanup
        # may kill unconditionally — an unconfirmed same-name row may belong
        # to a concurrent orchestrator.
        self.confirmed_short_id: str | None = None

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

    def _confirm_row(
        self, short_id: str | None, pre_existing: set[str]
    ) -> dict[str, Any] | None:
        """Find the row registered by THIS dispatch.

        The printed short id is authoritative. The name fallback (short-id regex
        missed, or the printed id never surfaced in the roster) only accepts a
        row absent from the pre-dispatch snapshot — a stale same-name row must
        not confirm a dispatch that never registered, poisoning session_id,
        polling, and teardown with the wrong session.
        """
        rows = [r for r in self.agents_json() if r.get("kind") != "interactive"]
        if short_id:
            for row in rows:
                if row.get("id") == short_id:
                    return row
        for row in rows:
            if row.get("name") != self.a.name:
                continue
            if row.get("id") in pre_existing or row.get("sessionId") in pre_existing:
                continue
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

    def _rejected_model_fallback(self) -> str | None:
        """The dispatched model as rejected_model fallback — but never the
        `claude` sentinel: sentinel means --model was omitted, so the CLI
        rejected the account-default model whose name we don't know."""
        if self.a.model and self.a.model != "claude":
            return self.a.model
        return None

    def _transcript_path(self, session_id: str | None) -> Path | None:
        """Path of the session transcript JSONL, or None when it doesn't exist.

        A missing transcript is a load-bearing signal: the session never
        consumed its initial prompt (startup trust/bypass dialog).
        """
        if not session_id:
            return None
        root = Path(self.a.transcripts_root).expanduser()
        matches = list(root.glob(f"*/{session_id}.jsonl")) or list(root.glob(f"{session_id}.jsonl"))
        return matches[0] if matches else None

    def logs_tail(self, session_id: str | None, max_texts: int = 4) -> str:
        """Tail of the session transcript (~/.claude/projects/*/<sid>.jsonl).

        This runner uses transcript JSONL as the portable fallback instead of
        assuming a stable `claude logs <id>` subcommand. Returns the last
        `max_texts` assistant-text lines, distilled. Classification callers
        pass max_texts=1: a CLI dialog (rate limit, model rejection) is always
        the FINAL assistant message, and scanning earlier messages invites
        false positives from agent prose that merely discusses limits/models.
        """
        transcript = self._transcript_path(session_id)
        if transcript is None:
            return ""
        texts: list[str] = []
        try:
            for line in transcript.read_text(encoding="utf-8").splitlines():
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
        return distill("\n".join(texts[-max_texts:]))

    def stop_session(self, short_id: str | None) -> StopResult:
        """Stop a background agent by signalling its supervisor-reported pid.

        This runner uses the pid-signalling fallback instead of assuming a
        stable `claude stop <id>` subcommand. The daemon may RESPAWN a parked
        session once from its spare pool after a kill (the row keeps its id but
        shows a fresh pid), so keep signalling the row's *current* pid until the
        row settles — drops its pid ("settled (killed)" in the daemon log) or
        leaves the listing. Settled rows may linger pid-less in `agents --json`;
        that is retired enough.
        """
        if not short_id:
            return StopResult(settled=True)
        row: dict[str, Any] | None = None
        for attempt in range(6):
            row = self.find_session(short_id=short_id)
            pid = (row or {}).get("pid")
            if not isinstance(pid, int):
                return StopResult(settled=True)
            sig = signal.SIGTERM if attempt < 2 else signal.SIGKILL
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
            time.sleep(self.a.poll_interval)
        row = self.find_session(short_id=short_id)
        if not isinstance((row or {}).get("pid"), int):
            return StopResult(settled=True)
        return StopResult(
            settled=False,
            survivor_id=(row or {}).get("id"),
            survivor_name=(row or {}).get("name"),
            survivor_session_id=(row or {}).get("sessionId"),
        )

    def teardown(self, short_id: str | None) -> StopResult:
        if self.a.keep:
            return StopResult(settled=True)
        return self.stop_session(short_id)

    def _retire_same_name_before_fresh_dispatch(
        self, *, exempt_short_id: str | None = None
    ) -> StopResult:
        """Retire stale same-name rows so a fresh dispatch never duplicates.

        CAUTION for callers: a deliberately PARKED needs_human session reads
        state=blocked and is indistinguishable from a stale crashed row here —
        the roster carries no parked-on-purpose marker. An orchestrator that
        parked a session for resume must resume it (or sweep it and clear its
        state marker) instead of fresh-dispatching the same name over it; see
        the parked-session guard in .skills/quest/delegation/workflow.md.
        Actively working/busy rows are refused (never killed), and the resume
        fallback path passes exempt_short_id to protect the parked parent.
        """
        rows = [
            row
            for row in self.agents_json()
            if row.get("kind") != "interactive"
            and row.get("name") == self.a.name
            and isinstance(row.get("pid"), int)
            and row.get("id") != exempt_short_id
        ]
        result = StopResult(settled=True)
        for row in rows:
            # Never auto-retire an actively working same-name row: it may be a
            # concurrent orchestrator's in-flight session, and killing it loses
            # work. Only parked/blocked/idle/done rows are safe to retire.
            if _row_active_or_unknown(row):
                return StopResult(
                    settled=False,
                    survivor_id=row.get("id"),
                    survivor_name=row.get("name"),
                    survivor_session_id=row.get("sessionId"),
                    reason="working",
                )
            result = self.stop_session(row.get("id"))
            if not result.settled:
                return result
        return result

    def sweep(self, prefix: str, *, include_active: bool = False) -> int:
        """Stop every background session whose name starts with `prefix`.

        Orphan recovery for orchestrators that crashed between dispatch and
        teardown (e.g. quest start/resume runs `--sweep quest-<id>-`).
        By default an actively working/busy row is SKIPPED and reported — a
        concurrent orchestrator on the same quest may own it, and orphan
        recovery must not kill in-flight work. Callers stopping a session
        they OWN (e.g. preflight retiring its own probe) pass include_active.
        """
        try:
            rows = [
                row
                for row in self.agents_json()
                if row.get("kind") != "interactive"
                and isinstance(row.get("name"), str)
                and row["name"].startswith(prefix)
                and isinstance(row.get("pid"), int)
            ]
        except FileNotFoundError:
            print("sweep skipped: claude CLI not found in PATH")
            return EXIT_OK
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"sweep skipped: claude agents roster unavailable: {exc}")
            return EXIT_OK
        failed = 0
        skipped_active = 0
        for row in rows:
            if not include_active and _row_active_or_unknown(row):
                skipped_active += 1
                print(f"skipped active {row.get('id')} ({row.get('name')})")
                continue
            result = self.stop_session(row.get("id"))
            status = "swept" if result.settled else "teardown_failed"
            if not result.settled:
                failed += 1
            print(f"{status} {row.get('id')} ({row.get('name')})")
        stopped = len(rows) - failed - skipped_active
        if skipped_active:
            print(
                f"sweep left {skipped_active} actively working session(s) alive "
                "(pass --sweep-include-active to stop sessions you own)"
            )
        if failed:
            print(
                f"sweep incomplete: {stopped} session(s) matching {prefix!r} stopped; "
                f"{failed} survivor(s) still live"
            )
            return EXIT_BLOCKED
        print(f"sweep complete: {stopped} session(s) matching {prefix!r} stopped")
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

    def _fresh_dispatch_preserving_outputs(
        self, message: str, *, exempt_same_name_short_id: str | None = None
    ) -> DispatchResult:
        """Fresh dispatch wrapped in the reversible stale-output guard.

        Snapshot handoff + wait_for, clear them (stale content must not
        satisfy this run), dispatch fresh; on ANY unconfirmed dispatch —
        including a refused same-name working session, and the resume
        fallback's failed re-dispatch (PR #137 review) — restore the snapshot
        so pre-existing questions/artifacts survive for a later retry. The
        single owner of this transaction: both the plain fresh path and the
        resume fallback must never diverge on restore semantics.
        """
        outputs = self._snapshot_outputs(include_wait_for=True)
        uncleared = self._clear_stale_outputs(include_wait_for=True)
        if uncleared:
            # Stale non-empty content we could not clear would satisfy the
            # WAIT loop instantly — a false success. Fail before dispatching,
            # but FIRST restore whatever the partial clear already truncated
            # (e.g. the parked question) — no dispatch will rewrite it.
            self._restore_outputs(outputs)
            return DispatchResult(
                terminal_status="precondition_failed",
                message=(
                    "could not clear stale output file(s) before dispatch "
                    f"({', '.join(uncleared)}); fix permissions or remove them, "
                    "then retry — proceeding would report stale content as success"
                ),
                short_id=None,
                row=None,
            )
        dispatch = self.dispatch_and_confirm(
            message, None, exempt_same_name_short_id=exempt_same_name_short_id
        )
        if dispatch.terminal_status:
            self._restore_outputs(outputs)
        return dispatch

    def _fallback_prompt(self, answer: str) -> str:
        task = self._read_source(self.a.prompt, self.a.prompt_file, "prompt")
        return f"{task}\n\nThe human answered your earlier question:\n{answer}\n"

    # -- dispatch -------------------------------------------------------------
    def dispatch_argv(self, resume_sid: str | None) -> list[str]:
        argv = [*self.claude, "--bg", "--name", self.a.name]
        if resume_sid:
            argv += ["--resume", resume_sid]
        if self.a.model and self.a.model != "claude":
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
        self,
        message: str,
        resume_sid: str | None,
        *,
        exempt_same_name_short_id: str | None = None,
    ) -> DispatchResult:
        """Return the dispatch terminal status, confirmed row, and metadata."""
        # Roster snapshot BEFORE dispatch: the confirm loop's name fallback may
        # only accept a row that appeared after this dispatch. Callers can pass
        # a stable --name (quest: quest-<id>-<role>-i<n>), so a stale row from a
        # crashed prior run — or a settled pid-less remnant of a torn-down one —
        # would otherwise confirm a dispatch that never registered.
        # A failed snapshot must return the structured envelope, not raise —
        # and must not silently proceed with an empty snapshot, which would
        # quietly reintroduce the stale-row false-confirm this guards against.
        pre_existing: set[str] = set()
        try:
            if resume_sid is None:
                same_name_stop = self._retire_same_name_before_fresh_dispatch(
                    exempt_short_id=exempt_same_name_short_id
                )
                if not same_name_stop.settled:
                    if same_name_stop.reason == "working":
                        detail = (
                            "live same-name background session is actively working; "
                            "refusing to retire it (likely a concurrent orchestrator "
                            f"run): id={same_name_stop.survivor_id} "
                            f"name={same_name_stop.survivor_name} "
                            f"session_id={same_name_stop.survivor_session_id}. "
                            "Wait for it to finish, or stop it deliberately with: "
                            f"python3 scripts/claude_bg_run.py --sweep {self.a.name} "
                            "--sweep-include-active"
                        )
                    else:
                        detail = (
                            "live same-name background session could not be retired "
                            f"before dispatch: id={same_name_stop.survivor_id} "
                            f"name={same_name_stop.survivor_name} "
                            f"session_id={same_name_stop.survivor_session_id}"
                        )
                    return DispatchResult(
                        terminal_status="dispatch_failed",
                        message=detail,
                        short_id=same_name_stop.survivor_id,
                        row=None,
                    )
            for r in self.agents_json():
                for key in ("id", "sessionId"):
                    if r.get(key):
                        pre_existing.add(r[key])
        except FileNotFoundError:
            return DispatchResult("precondition_failed", "claude CLI not found in PATH", None, None)
        except (OSError, subprocess.SubprocessError) as exc:
            return DispatchResult("dispatch_failed", f"roster snapshot before dispatch failed: {exc}", None, None)
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
            return DispatchResult("precondition_failed", "claude CLI not found in PATH", None, None)
        except subprocess.SubprocessError as exc:
            return DispatchResult("dispatch_failed", f"dispatch error: {exc}", None, None)

        out = cp.stdout + cp.stderr
        if _BYPASS_REFUSAL_RE.search(out):
            return DispatchResult(
                terminal_status="precondition_failed",
                message="bypassPermissions not accepted — run `claude --dangerously-skip-permissions` once interactively, then retry.",
                short_id=None,
                row=None,
            )
        classified = _classify_limit_or_model(out)
        if classified:
            status, message, reset_at, rejected = classified
            if status == "model_rejected":
                # Same fallback as the WAIT path: when the CLI phrasing hides
                # the model name, the dispatched model is still the answer.
                rejected = rejected or self._rejected_model_fallback()
            return DispatchResult(
                terminal_status=status,
                message=message,
                short_id=None,
                row=None,
                reset_at=reset_at,
                rejected_model=rejected,
            )
        m = _SHORTID_RE.search(out)
        short_id = m.group(1) if m else None

        deadline = time.monotonic() + self.a.confirm_timeout
        row: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            # Confirm by short id, else by name restricted to NEW rows. Never by
            # sessionId: in resume mode the parked parent's row matches
            # `sessionId == resume_sid` and would falsely confirm a dispatch
            # that never registered.
            row = self._confirm_row(short_id, pre_existing)
            if row:
                break
            time.sleep(self.a.poll_interval)
        if not row:
            return DispatchResult(
                terminal_status="dispatch_failed",
                message="session never registered with the supervisor (printed: %r)" % out.strip()[:200],
                short_id=short_id,
                row=None,
            )
        return DispatchResult(None, "", short_id or row.get("id"), row)

    @staticmethod
    def _copy_stop_result(env: Envelope, result: StopResult) -> None:
        if result.settled:
            return
        env.teardown_failed = True
        env.teardown_survivor_id = result.survivor_id
        env.teardown_survivor_name = result.survivor_name
        env.teardown_survivor_session_id = result.survivor_session_id

    @staticmethod
    def _copy_dispatch_result(env: Envelope, result: DispatchResult) -> None:
        env.status = result.terminal_status or ""
        env.message = result.message
        env.short_id = result.short_id
        env.reset_at = result.reset_at
        env.rejected_model = result.rejected_model

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
    def _clear_file(path: str) -> bool:
        """Truncate a pre-existing file so stale content cannot satisfy this run.

        Returns False when a NON-EMPTY file could not be cleared: that stale
        content would instantly satisfy the WAIT loop's non-empty check — a
        false success — so the caller must fail the run instead of proceeding.
        """
        try:
            target = Path(path)
            if target.is_file():
                target.write_text("", encoding="utf-8")
            elif target.exists():
                # A directory (or other non-file) at an output path satisfies
                # the WAIT loop's stat-size check yet can never be this run's
                # result — unclearable stale state, fail it.
                return False
            return True
        except OSError:
            return not BgRunner._nonempty(path)

    def _clear_stale_outputs(self, *, include_wait_for: bool) -> list[str]:
        """Stale-state guard: pre-existing outputs must not satisfy THIS run.

        Fresh dispatch clears the handoff and every --wait-for target. Resume
        clears only the handoff (a parked needs_human would re-trigger the
        WAIT loop instantly) and keeps --wait-for files the parked session
        already wrote — the resumed agent will not rewrite work it believes
        is done.

        Returns the paths whose stale non-empty content could NOT be cleared;
        callers must fail the run for those (false-success guard).
        """
        failed: list[str] = []
        if self.a.handoff_file and not self._clear_file(self.a.handoff_file):
            failed.append(self.a.handoff_file)
        if include_wait_for:
            for path in self.a.wait_for:
                if not self._clear_file(path):
                    failed.append(path)
        return failed

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
            dispatch = self.dispatch_and_confirm(message, resume_sid)
            have_task = self.a.prompt is not None or bool(self.a.prompt_file)
            if dispatch.terminal_status and self.a.fallback and have_task:
                try:
                    fb = self._fallback_prompt(message)
                except (ValueError, OSError) as exc:
                    env.status, env.message = "precondition_failed", str(exc)
                    return env
                env.resumed, env.fell_back = False, True
                dispatch2 = self._fresh_dispatch_preserving_outputs(
                    fb, exempt_same_name_short_id=parent_short_id
                )
                if dispatch2.terminal_status:
                    # Restore already happened; leave the parked session alive
                    # (teardown below is not reached) so a later retry can
                    # still answer the question.
                    self._copy_dispatch_result(env, dispatch2)
                    env.message = (
                        f"resume failed ({dispatch.message}); "
                        f"re-dispatch also failed ({dispatch2.message})"
                    )
                    env.duration_s = round(time.monotonic() - t0, 1)
                    return env
                short_id, row = dispatch2.short_id, dispatch2.row
                env.message = f"resume failed ({dispatch.message}); re-dispatched fresh with the answer"
            elif dispatch.terminal_status:
                self._copy_dispatch_result(env, dispatch)
                env.duration_s = round(time.monotonic() - t0, 1)
                return env
            else:
                short_id, row = dispatch.short_id, dispatch.row
        else:
            dispatch = self._fresh_dispatch_preserving_outputs(message)
            if dispatch.terminal_status:
                self._copy_dispatch_result(env, dispatch)
                env.duration_s = round(time.monotonic() - t0, 1)
                return env
            short_id, row = dispatch.short_id, dispatch.row

        env.short_id = short_id
        self.confirmed_short_id = short_id
        env.session_id = (row or {}).get("sessionId")

        # Clear the parked handoff only now that the resume continuation is
        # confirmed — a failed resume dispatch (returned above) must leave the
        # parked session's needs_human question on disk. --wait-for files the
        # parked agent already wrote are kept (the resumed agent won't redo
        # them). The fallback path cleared its own stale outputs above.
        if resume_mode and not env.fell_back:
            if self._clear_stale_outputs(include_wait_for=False):
                # The parked needs_human handoff could not be cleared: it
                # would re-trigger the WAIT loop instantly as a false result.
                env.status = "precondition_failed"
                env.message = (
                    f"could not clear the stale handoff file "
                    f"({self.a.handoff_file}) after resume; fix permissions "
                    "and retry — its parked content would masquerade as this "
                    "run's result"
                )
                env.duration_s = round(time.monotonic() - t0, 1)
                if env.short_id:
                    self._copy_stop_result(env, self.teardown(env.short_id))
                return env

        # The conversation has moved on (resumed into a new agent, or re-dispatched
        # fresh); retire the parked parent so it is not orphaned. Respects --keep.
        if parent_short_id and parent_short_id != short_id:
            self._copy_stop_result(env, self.teardown(parent_short_id))

        # WAIT
        deadline = time.monotonic() + self.a.timeout
        next_status = 0.0
        grace_left = 2
        # A freshly confirmed session can read blocked with no transcript for
        # one poll before its first JSONL flush; require a second consecutive
        # observation before inferring a startup dialog from the missing file.
        startup_observations = 0
        try:
          while True:
            now = time.monotonic()
            if now > deadline:
                env.status, env.final_state = "timeout", env.final_state or "working"
                env.message = (
                    f"task exceeded --timeout ({self.a.timeout:g}s); the session "
                    "is being stopped. Increase --timeout or split the task; "
                    "artifacts written so far are listed in artifacts_found."
                )
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
                # Track ONLY the confirmed id: a name fallback could silently
                # adopt a different same-name agent if ours vanished, hiding
                # the real failure. (Daemon respawns keep the row id, so id
                # tracking survives them.)
                row = self.find_session(env.short_id)
                state = (row or {}).get("state") or (row or {}).get("status")
                env.final_state = state
                if row is None:
                    env.status = "session_failed"
                    env.message = (
                        "session disappeared from `claude agents` before "
                        "completing; check `claude agents` and the transcript "
                        "tail (logs_tail) for the last activity, then "
                        "re-dispatch the task."
                    )
                    break
                if state == "blocked" and row.get("status") != "busy":
                    # state=blocked + status=busy is an active session
                    # momentarily awaiting a tool (same mixed-field reality the
                    # retirement guard honors) — keep polling and classify only
                    # once the status settles; a persistent block will still be
                    # here next poll, and a hung one ends at --timeout.
                    # Opportunistic only: Claude Code 2.1.191's initial-prompt
                    # parked signal was observed in dispatch stdout, not here.
                    detail = row.get("waitingFor") or row.get("needs") or row.get("detail")
                    detail_text = str(detail) if detail else ""
                    # Classification evidence: roster detail + the FINAL
                    # assistant message only — a CLI dialog is always the last
                    # message, and earlier prose that merely discusses limits
                    # or models must not classify.
                    last_text = self.logs_tail(env.session_id, max_texts=1)
                    evidence = "\n".join(part for part in (detail_text, last_text) if part)
                    cwd = os.getcwd()
                    classified = _classify_limit_or_model(evidence)
                    if classified:
                        env.status, env.message, env.reset_at, rejected = classified
                        if env.status == "model_rejected":
                            env.rejected_model = rejected or self._rejected_model_fallback()
                    elif (
                        # Transcript FILE missing = the session never consumed
                        # its prompt: a startup dialog (trust/bypass) by
                        # definition. An existing transcript with no text
                        # (e.g. a tool_use-only first turn) is NOT that signal
                        # and falls through to generic blocked. A resumed fork
                        # cannot hit a trust dialog (the parent already
                        # accepted it) — its missing file is just flush lag.
                        (self._transcript_path(env.session_id) is None and not env.resumed)
                        or _STARTUP_DIALOG_RE.search(evidence)
                    ):
                        startup_observations += 1
                        if startup_observations < 2:
                            # First observation may be pre-flush; confirm on
                            # the next poll before committing to the terminal
                            # startup_dialog status and its remediation.
                            time.sleep(self.a.poll_interval)
                            continue
                        detail_note = (
                            f"Claude CLI reported: {detail_text}"
                            if detail_text
                            else "no dialog detail; inferred from the missing transcript"
                        )
                        env.status = "startup_dialog"
                        env.message = (
                            "background session registered but did not consume "
                            f"the initial prompt ({detail_note}); open Claude "
                            f"interactively in the target cwd ({cwd}) and accept "
                            "trust/bypass prompts, then re-run the task."
                        )
                    else:
                        env.status = "blocked"
                        env.message = "session is blocked on an interactive prompt " + (
                            f"({detail_text})"
                            if detail_text
                            else f"(cause unknown; open Claude interactively in the target cwd ({cwd}) to inspect)"
                        )
                    break
                if state in ("done", "idle"):
                    if not self.a.wait_for and not self.a.handoff_file:
                        env.status = "ok"  # --no-wait: completion == reached done
                        break
                    grace_left -= 1
                    if grace_left <= 0:
                        env.status = "incomplete"
                        env.message = (
                            "session finished but declared output files are "
                            "missing/empty (see missing); re-dispatch the task, "
                            "and if it recurs check logs_tail for what the "
                            "agent believed it wrote."
                        )
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
            # Fallback field parsing uses the FINAL message only, like
            # classification — parsing the multi-message tail would pull a
            # reset time or model name out of earlier agent prose.
            last_text = self.logs_tail(env.session_id, max_texts=1)
            if env.status == "model_rejected" and env.rejected_model is None:
                env.rejected_model = _parse_rejected_model(last_text) or self._rejected_model_fallback()
            if env.status == "rate_limited" and env.reset_at is None:
                env.reset_at = _parse_reset_at(last_text)

        # TEARDOWN — by default PRESERVE a needs_human session so it can be
        # resumed (standalone use). Callers with no resume loop pass
        # --teardown-on-needs-human to tear it down like the bridge instead of
        # orphaning a session nobody will collect.
        preserve_for_resume = (
            env.status == "needs_human" and not self.a.teardown_on_needs_human
        )
        if env.short_id and not preserve_for_resume:
            self._copy_stop_result(env, self.teardown(env.short_id))
        env.duration_s = round(time.monotonic() - t0, 1)
        if not env.message and env.status == "ok":
            env.message = "completed; declared artifacts present"
        if env.status == "needs_human":
            # Every needs_human envelope must carry the answer-path guidance,
            # even when an earlier phase (e.g. a resume fallback) already set
            # a message describing how we got here.
            guidance = (
                "agent needs a human decision; session torn down (caller has no resume loop)"
                if self.a.teardown_on_needs_human
                else "agent needs a human decision; session left alive — answer via --resume <session_id|short_id|name> --answer"
            )
            if not env.message:
                env.message = guidance
            elif "agent needs a human decision" not in env.message:
                env.message = f"{env.message} {guidance}."
        # A leaked session must never be silent — appended LAST so it augments
        # (never replaces) the status's own guidance, including the needs_human
        # resume instructions above.
        if env.teardown_failed:
            # The survivor is our own confirmed session and may still read
            # working/busy — the plain sweep would spare it, so the recovery
            # command must include active rows.
            env.message = (
                f"{env.message} WARNING: session teardown failed; "
                f"survivor {env.teardown_survivor_id or env.short_id} is still "
                f"live — stop it with: python3 scripts/claude_bg_run.py "
                f"--sweep {self.a.name} --sweep-include-active"
            ).strip()
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
            "for --resume. For direct callers with no relay: "
            "needs_human then behaves like the bridge — surfaced promptly, "
            "session torn down — rather than parked until a human answers."
        ),
    )
    p.add_argument("--model", default="", help="Claude model; exact `claude` uses the CLI/account default")
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
    p.add_argument("--sweep", help="stop all background sessions whose NAME starts with this prefix, then exit (orphan recovery; skips actively working/busy rows)")
    p.add_argument(
        "--sweep-include-active",
        action="store_true",
        help="with --sweep: also stop actively working/busy rows (only for sessions you own, e.g. retiring your own probe)",
    )
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
        return BgRunner(args).sweep(
            args.sweep, include_active=args.sweep_include_active
        )
    runner = BgRunner(args)
    try:
        env = runner.run()
    except KeyboardInterrupt:
        # run()'s own handler only covers the WAIT loop; an interrupt during
        # dispatch or final teardown would otherwise leak the (possibly just
        # forked) detached session with no envelope. Only a CONFIRMED session
        # is provably ours to kill unconditionally; before confirmation a
        # same-name active row may belong to a concurrent orchestrator, so
        # the fallback sweep spares active/unknown rows and the human gets
        # the manual command for anything left.
        print(
            f"interrupted during dispatch/teardown; cleaning up sessions named "
            f"{args.name!r} best-effort before exit. If one remains and it is "
            f"yours, stop it with: python3 scripts/claude_bg_run.py --sweep "
            f"{args.name} --sweep-include-active",
            file=sys.stderr,
        )
        try:
            if runner.confirmed_short_id:
                runner.stop_session(runner.confirmed_short_id)
            runner.sweep(args.name)
        except Exception:
            pass
        return EXIT_INTERRUPTED
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
