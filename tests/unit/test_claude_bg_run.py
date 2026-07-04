"""Unit tests for the standalone claude --bg runner proof of concept.

These exercise the full dispatch -> confirm -> wait -> collect -> teardown
lifecycle against a fake `claude` shim (no real model calls, no bypass-acceptance
needed), the needs_human bubble-back and resume continuation, plus the ANSI/PTY
noise-firewall primitive.

The shim models the runner surface used by these tests: `--bg` (incl.
`--resume`) and `agents --json`. State is a LIST of session rows (each with a
pid), so resume scenarios can model the parked parent session sitting next to
the newly dispatched agent. The current runner tears down via process signals;
tests intercept `os.kill` and drop the row to simulate exit.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

import claude_bg_run as bg

# Captured at import, BEFORE the autouse `kills` fixture patches bg.os.kill:
# `bg.os` and this module's `os` are the same module object, so by test time
# `os.kill` already IS the fake — restoring from it would be a no-op.
_REAL_OS_KILL = os.kill

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import os, sys, json, pathlib
D = pathlib.Path(os.environ["FAKE_BG_DIR"])
S = os.environ.get("FAKE_BG_SCENARIO", "ok")
WAIT = os.environ.get("FAKE_BG_WAITFOR", "")
HAND = os.environ.get("FAKE_BG_HANDOFF", "")
state = D / "state.json"
calls = D / "calls.log"

def log(line): calls.open("a").write(line + "\n")
def rows():
    try: return json.loads(state.read_text())
    except Exception: return []

args = sys.argv[1:]
if args[:1] == ["--bg"]:
    stdin_text = sys.stdin.read()
    (D / "last_bg_stdin.txt").write_text(stdin_text)
    (D / "last_bg_argv.json").write_text(json.dumps(args))
    is_resume = "--resume" in args
    sid_arg = args[args.index("--resume") + 1] if is_resume else ""
    name = args[args.index("--name") + 1] if "--name" in args else "?"
    log(("resume " if is_resume else "bg ") + name + (f" sid={sid_arg}" if is_resume else ""))
    if S == "bypass_refused":
        print("--bg with bypassPermissions requires accepting the disclaimer first. "
              "Run `claude --dangerously-skip-permissions` once interactively.")
        sys.exit(0)
    if S == "dispatch_rate_limited":
        print("You've hit your session limit. resets 2pm (America/Chicago)")
        sys.exit(0)
    if S == "dispatch_model_rejected":
        print("There's an issue with the selected model (claude-bad-1).")
        sys.exit(0)
    eff = S
    if S == "resume_ok":
        eff = "ok"
    if S == "resume_fallback":
        eff = "never_confirm" if is_resume else "ok"
    sid = "abc12345"
    if eff != "never_confirm":
        st = {"blocked": "blocked", "startup_dialog": "blocked", "model_rejected": "blocked", "rate_limited": "blocked", "incomplete": "done"}.get(eff, "working")
        row = {"pid": 222, "id": sid, "name": name, "sessionId": sid + "-uuid",
               "kind": "background", "state": st, "status": "idle"}
        if eff == "startup_dialog":
            row["detail"] = "idle — send a prompt to start"
        rs = rows()
        rs.append(row)
        state.write_text(json.dumps(rs))
    if eff == "ok" and WAIT:
        pathlib.Path(WAIT).write_text("RESULT")
    if eff == "needs_human" and HAND:
        pathlib.Path(HAND).write_text(json.dumps(
            {"status": "needs_human", "questions": ["A or B?"]}))
    print(f"backgrounded · {sid} · {name}")
    sys.exit(0)
if args[:2] == ["agents", "--json"]:
    print(json.dumps(rows()))
    sys.exit(0)
# Older Claude Code builds treated unknown management verbs as a prompt. This
# shim keeps that historical behavior for tests that exercise pid fallback paths.
log("unknown " + " ".join(args[:2]))
sys.exit(0)
'''

PARENT_SID = "11111111-1111-1111-1111-111111111111"
PARENT = {
    "pid": 111,
    "id": "parent01",
    "name": "bgrun-parked",
    "kind": "background",
    "sessionId": PARENT_SID,
    # A parked (idle, awaiting-input) session reads state==blocked — exactly the
    # row that used to shadow the new resume agent.
    "state": "blocked",
    "status": "idle",
}


@pytest.fixture
def shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "fake_claude.py"
    p.write_text(FAKE_CLAUDE, encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("FAKE_BG_DIR", str(tmp_path))
    return p


@pytest.fixture(autouse=True)
def kills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Intercept os.kill: record (pid, sig) and drop the row, simulating exit."""
    recorded: list[tuple[int, int]] = []
    state = tmp_path / "state.json"

    def fake_kill(pid: int, sig: int) -> None:
        recorded.append((pid, sig))
        try:
            rows = json.loads(state.read_text())
        except (OSError, json.JSONDecodeError):
            rows = []
        state.write_text(json.dumps([r for r in rows if r.get("pid") != pid]))

    monkeypatch.setattr(bg.os, "kill", fake_kill)
    return recorded


def _seed_parent(tmp_path: Path, **over) -> dict:
    row = {**PARENT, **over}
    (tmp_path / "state.json").write_text(json.dumps([row]))
    return row


def _args(shim: Path, **over):
    argv = [
        "--claude-bin", f"{shim}",
        "--prompt", "do the thing",
        "--confirm-timeout", "1",
        "--poll-interval", "0.05",
        "--status-interval", "0",
        "--timeout", "2",
    ]
    for k, v in over.items():
        flag = "--" + k.replace("_", "-")
        if v is True:
            argv.append(flag)
        else:
            argv += [flag, str(v)]
    return bg.build_parser().parse_args(argv)


def _calls(tmp_path: Path) -> list[str]:
    f = tmp_path / "calls.log"
    return f.read_text().splitlines() if f.exists() else []


def _last_bg_stdin(tmp_path: Path) -> str:
    return (tmp_path / "last_bg_stdin.txt").read_text()


def _last_bg_argv(tmp_path: Path) -> list[str]:
    return json.loads((tmp_path / "last_bg_argv.json").read_text())


# ---- pure helpers ----------------------------------------------------------
def test_strip_ansi_removes_escapes():
    raw = "\x1b[2J\x1b[31mHELLO\x1b[0m world\r\n"
    assert bg.strip_ansi(raw).strip() == "HELLO world"


def test_shortid_parses_with_and_without_name_and_idle_suffix():
    assert bg._SHORTID_RE.search("backgrounded · 7c5dcf5d · my-name").group(1) == "7c5dcf5d"
    assert bg._SHORTID_RE.search("backgrounded · e590de4c (idle — send a prompt to start)").group(1) == "e590de4c"


def test_bypass_refusal_regex():
    assert bg._BYPASS_REFUSAL_RE.search("requires accepting the disclaimer; run claude --dangerously-skip-permissions")


def test_pty_capture_strips_noise_to_signal():
    code, text = bg.pty_capture(
        ["sh", "-c", "printf '\\033[2J\\033[31mHELLO\\033[0m clean\\n'"],
        total_timeout=5.0, idle_timeout=1.0,
    )
    assert "HELLO clean" in text
    assert "\x1b" not in text


def test_pty_capture_total_timeout_kills_child_and_returns_failure(monkeypatch):
    # A child that streams forever: total_timeout must kill+reap it and surface
    # a non-zero exit instead of success-with-partial-text (and a leaked child).
    monkeypatch.setattr(bg.os, "kill", _REAL_OS_KILL)  # undo the autouse kill shim
    code, text = bg.pty_capture(
        ["sh", "-c", "while :; do printf x; sleep 0.05; done"],
        total_timeout=0.5, idle_timeout=5.0,
    )
    assert code == 124
    assert "x" in text  # partial capture still returned for diagnostics


def test_pty_capture_idle_quiescence_is_success_and_reaps_child(monkeypatch):
    # Idle-quiescence is the DESIGNED completion signal for capturing a live
    # TUI screen (the attach responder use-case): exit 0, and the child is
    # terminated+reaped rather than left running past the runner's lifetime.
    # If reaping regressed, the blocking waitpid would hold this test ~30s.
    monkeypatch.setattr(bg.os, "kill", _REAL_OS_KILL)  # undo the autouse kill shim
    code, text = bg.pty_capture(
        ["sh", "-c", "printf 'SCREEN'; sleep 30"],
        total_timeout=15.0, idle_timeout=0.4,
    )
    assert code == 0
    assert "SCREEN" in text


def test_pty_capture_reports_child_exit_code():
    # A child that exits non-zero on its own must not read back as success
    # (the old WNOHANG race could miss the just-exited status entirely).
    code, _ = bg.pty_capture(
        ["sh", "-c", "printf 'boom'; exit 3"],
        total_timeout=5.0, idle_timeout=1.0,
    )
    assert code == 3


# ---- lifecycle scenarios ---------------------------------------------------
def test_ok_completes_on_artifact_and_tears_down(shim, tmp_path, monkeypatch, kills):
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.exit_code() == bg.EXIT_OK
    assert str(wait) in env.artifacts_found and not env.missing
    # Current teardown = SIGTERM to the supervisor-reported pid.
    assert (222, bg.signal.SIGTERM) in kills


def test_dispatch_sends_prompt_on_stdin_not_argv(shim, tmp_path, monkeypatch):
    wait = tmp_path / "out.json"
    prompt = "write ok from stdin"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))

    env = bg.BgRunner(_args(shim, prompt=prompt, wait_for=str(wait))).run()

    assert env.status == "ok"
    assert _last_bg_stdin(tmp_path).startswith(prompt)
    assert all(prompt not in arg for arg in _last_bg_argv(tmp_path))


def test_keep_skips_teardown(shim, tmp_path, monkeypatch, kills):
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, wait_for=str(wait), keep=True)).run()
    assert env.status == "ok"
    assert kills == []


def test_needs_human_bubbles_back(shim, tmp_path, monkeypatch):
    hand = tmp_path / "handoff.json"
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "needs_human")
    monkeypatch.setenv("FAKE_BG_HANDOFF", str(hand))
    env = bg.BgRunner(_args(shim, wait_for=str(wait), handoff_file=str(hand))).run()
    assert env.status == "needs_human"
    assert env.exit_code() == bg.EXIT_NEEDS_HUMAN
    assert env.questions == ["A or B?"]


def test_needs_human_keeps_session_alive_for_resume(shim, tmp_path, monkeypatch, kills):
    hand = tmp_path / "handoff.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "needs_human")
    monkeypatch.setenv("FAKE_BG_HANDOFF", str(hand))
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "out.json"), handoff_file=str(hand))).run()
    assert env.status == "needs_human"
    # Session must NOT be torn down: no signals sent, so it can be resumed.
    assert kills == []


def test_needs_human_teardown_flag_tears_session_down(shim, tmp_path, monkeypatch, kills):
    # Direct callers with no relay pass
    # --teardown-on-needs-human so needs_human is surfaced AND the session is
    # torn down (like the bridge), instead of left alive to leak.
    hand = tmp_path / "handoff.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "needs_human")
    monkeypatch.setenv("FAKE_BG_HANDOFF", str(hand))
    env = bg.BgRunner(
        _args(
            shim,
            wait_for=str(tmp_path / "out.json"),
            handoff_file=str(hand),
            teardown_on_needs_human=True,
        )
    ).run()
    assert env.status == "needs_human"
    assert env.exit_code() == bg.EXIT_NEEDS_HUMAN
    # Session IS torn down: a SIGTERM was sent to the supervisor-reported pid.
    assert any(sig == bg.signal.SIGTERM for _, sig in kills)
    assert "session torn down" in env.message
    assert env.session_id  # surfaced so the orchestrator can --resume it


def test_teardown_on_needs_human_help_is_relay_agnostic():
    help_text = " ".join(bg.build_parser().format_help().split())
    stale_quest_no_relay_phrase = "callers with no resume loop" + " (e.g. Quest)"
    assert "For direct callers with no relay" in help_text
    assert stale_quest_no_relay_phrase not in help_text


def test_resume_continues_same_session_not_shadowed_by_parked_parent(shim, tmp_path, monkeypatch, kills):
    # Regression: the parked parent (state==blocked because it is idle awaiting
    # input) matches sessionId==resume target and used to shadow the new agent,
    # misreporting the whole run as `blocked`.
    _seed_parent(tmp_path)
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, resume=PARENT_SID, answer="use option A", wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.resumed is True and env.fell_back is False
    assert env.resumed_from == PARENT_SID
    assert env.session_id == "abc12345-uuid"  # the NEW session id, for chained resumes
    assert any(c.startswith("resume ") and f"sid={PARENT_SID}" in c for c in _calls(tmp_path))
    # The parked parent is retired once the conversation moved on; the new agent
    # is torn down at the end as usual.
    assert (111, bg.signal.SIGTERM) in kills
    assert (222, bg.signal.SIGTERM) in kills


def test_resume_by_agent_name_survives_rename(shim, tmp_path, monkeypatch, kills):
    # A human renamed the parked agent in the agent view; --resume by the new
    # name must resolve to its sessionId.
    _seed_parent(tmp_path, name="fix-login-bug")
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, resume="fix-login-bug", answer="use option A", wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.resumed_from == PARENT_SID
    assert any(f"sid={PARENT_SID}" in c for c in _calls(tmp_path))
    assert (111, bg.signal.SIGTERM) in kills


def test_resume_by_short_id(shim, tmp_path, monkeypatch):
    _seed_parent(tmp_path)
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, resume="parent01", answer="use option A", wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.resumed_from == PARENT_SID


def test_resume_unknown_target_is_precondition_failed(shim, tmp_path, monkeypatch):
    # Not a live agent (by sid/short id/name) and not session-id-shaped.
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    env = bg.BgRunner(_args(shim, resume="no-such-agent", answer="A", wait_for=str(tmp_path / "x"))).run()
    assert env.status == "precondition_failed"
    assert env.exit_code() == bg.EXIT_PRECONDITION
    assert "no live agent" in env.message


def test_failed_resume_dispatch_preserves_parked_handoff(shim, tmp_path, monkeypatch, kills):
    # Regression (PR #137 review): the parked needs_human handoff must NOT be
    # cleared until a continuation is confirmed. With --no-fallback and a resume
    # dispatch that never registers, the parked session lives on, so its
    # question must still be on disk for a later retry.
    _seed_parent(tmp_path)
    hand = tmp_path / "handoff.json"
    hand.write_text(json.dumps({"status": "needs_human", "questions": ["A or B?"]}))
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_fallback")  # resume never confirms
    env = bg.BgRunner(
        _args(shim, resume=PARENT_SID, answer="use A", handoff_file=str(hand),
              no_fallback=True, wait_for=str(tmp_path / "out.json"))
    ).run()
    assert env.status == "dispatch_failed"
    # The parked question survived the failed resume dispatch.
    assert json.loads(hand.read_text())["questions"] == ["A or B?"]
    # And the parked parent was not retired (no signal to its pid).
    assert (111, bg.signal.SIGTERM) not in kills


def test_failed_fallback_dispatch_preserves_parked_handoff(shim, tmp_path, monkeypatch, kills):
    # Regression (PR #137 review): when resume fails AND the fresh fallback
    # re-dispatch also fails, the parked needs_human handoff AND any artifacts
    # the parked session already wrote are restored (both cleared as the stale
    # guard before the unconfirmed re-dispatch), and the parked parent is not
    # torn down — so the question + work survive for a retry.
    _seed_parent(tmp_path)
    hand = tmp_path / "handoff.json"
    hand.write_text(json.dumps({"status": "needs_human", "questions": ["A or B?"]}))
    out = tmp_path / "out.bin"
    # A non-UTF-8 (binary) artifact: snapshot/restore must be byte-safe, never
    # decode it (read_text would raise UnicodeDecodeError before the restore).
    out.write_bytes(b"\xff\xfePARTIAL")
    monkeypatch.setenv("FAKE_BG_SCENARIO", "never_confirm")  # resume AND fresh both fail
    env = bg.BgRunner(
        _args(shim, resume=PARENT_SID, answer="use A", handoff_file=str(hand),
              wait_for=str(out))
    ).run()
    assert env.status == "dispatch_failed"
    assert env.fell_back is True
    assert "re-dispatch also failed" in env.message
    # The parked question AND the parked (binary) artifact survived the fallback.
    assert json.loads(hand.read_text())["questions"] == ["A or B?"]
    assert out.read_bytes() == b"\xff\xfePARTIAL"
    # And the parked parent was not retired.
    assert (111, bg.signal.SIGTERM) not in kills


def test_failed_fallback_dispatch_preserves_colliding_parked_parent(
    shim, tmp_path, monkeypatch, kills
):
    name = "quest-q7-planner-i1"
    _seed_parent(tmp_path, name=name)
    hand = tmp_path / "handoff.json"
    hand.write_text(json.dumps({"status": "needs_human", "questions": ["A or B?"]}))
    monkeypatch.setenv("FAKE_BG_SCENARIO", "never_confirm")

    env = bg.BgRunner(
        _args(
            shim,
            name=name,
            resume=PARENT_SID,
            answer="use A",
            handoff_file=str(hand),
            wait_for=str(tmp_path / "out.json"),
        )
    ).run()

    assert env.status == "dispatch_failed"
    assert env.fell_back is True
    assert json.loads(hand.read_text())["questions"] == ["A or B?"]
    assert (111, bg.signal.SIGTERM) not in kills


def test_resume_falls_back_to_fresh_dispatch(shim, tmp_path, monkeypatch):
    # Session-id-shaped target with no live row: try the resume, fall back fresh.
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_fallback")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    dead = "22222222-2222-2222-2222-222222222222"
    env = bg.BgRunner(_args(shim, resume=dead, answer="use option A", wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.fell_back is True
    assert "re-dispatched" in env.message
    calls = [c.split()[0] for c in _calls(tmp_path)]
    assert "resume" in calls and "bg" in calls  # tried resume, then fresh


def test_resume_without_answer_is_precondition_failed(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    env = bg.BgRunner(_args(shim, resume=PARENT_SID, wait_for=str(tmp_path / "x"))).run()
    assert env.status == "precondition_failed"
    assert env.exit_code() == bg.EXIT_PRECONDITION


def test_blocked_is_detected_with_transcript_logs(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "blocked")
    tdir = tmp_path / "transcripts" / "proj"
    tdir.mkdir(parents=True)
    (tdir / "abc12345-uuid.jsonl").write_text(json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "\x1b[31mneeds input: choose A or B?\x1b[0m"}]},
    }) + "\n")
    env = bg.BgRunner(_args(shim, transcripts_root=str(tmp_path / "transcripts"))).run()
    assert env.status == "blocked"
    assert env.exit_code() == bg.EXIT_BLOCKED
    assert "choose A or B" in env.logs_tail
    assert "\x1b" not in env.logs_tail
    assert "permission hook likely did not cover it" not in env.message


def test_rate_limit_block_reports_reset_time(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "rate_limited")
    tdir = tmp_path / "transcripts" / "proj"
    tdir.mkdir(parents=True)
    (tdir / "abc12345-uuid.jsonl").write_text(json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "You've hit your session limit. resets 2pm (America/Chicago)"}]},
    }) + "\n")

    env = bg.BgRunner(_args(shim, transcripts_root=str(tmp_path / "transcripts"))).run()

    assert env.status == "rate_limited"
    assert env.reset_at == "2pm (America/Chicago)"
    assert "retry after reset" in env.message
    assert "permission hook" not in env.message


def test_startup_dialog_without_transcript_is_not_permission_guess(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "startup_dialog")

    env = bg.BgRunner(_args(shim, transcripts_root=str(tmp_path / "missing-transcripts"))).run()

    assert env.status == "startup_dialog"
    assert "did not consume" in env.message
    assert "open Claude interactively in the target cwd" in env.message
    assert "accept trust/bypass prompts" in env.message
    assert "permission hook likely did not cover it" not in env.message


def test_model_rejected_from_logs_tail_is_model_rejected(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "model_rejected")
    tdir = tmp_path / "transcripts" / "proj"
    tdir.mkdir(parents=True)
    (tdir / "abc12345-uuid.jsonl").write_text(json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "There's an issue with the selected model (claude-bad-1)."}]},
    }) + "\n")

    env = bg.BgRunner(_args(shim, transcripts_root=str(tmp_path / "transcripts"))).run()

    assert env.status == "model_rejected"
    assert env.rejected_model == "claude-bad-1"
    assert "rejected the selected model" in env.message


def test_dispatch_output_rate_limit_reports_reset_time(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "dispatch_rate_limited")

    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "x"))).run()

    assert env.status == "rate_limited"
    assert env.reset_at == "2pm (America/Chicago)"
    assert env.exit_code() == bg.EXIT_BLOCKED
    assert "retry after reset" in env.message


def test_dispatch_output_model_rejected_sets_structured_model(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "dispatch_model_rejected")

    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "x"))).run()

    assert env.status == "model_rejected"
    assert env.rejected_model == "claude-bad-1"
    assert env.exit_code() == bg.EXIT_PRECONDITION


def test_generic_data_model_prose_does_not_classify_as_model_rejected(
    shim, tmp_path, monkeypatch
):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "blocked")
    tdir = tmp_path / "transcripts" / "proj"
    tdir.mkdir(parents=True)
    (tdir / "abc12345-uuid.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "There is an issue with the data model: foo",
                        }
                    ]
                },
            }
        )
        + "\n"
    )

    env = bg.BgRunner(_args(shim, transcripts_root=str(tmp_path / "transcripts"))).run()

    assert env.status == "blocked"
    assert env.rejected_model is None


def test_dispatch_failed_when_never_registers(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "never_confirm")
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "x"))).run()
    assert env.status == "dispatch_failed"
    assert env.exit_code() == bg.EXIT_DISPATCH_FAILED


def test_missing_claude_cli_is_precondition_failed(tmp_path):
    # The pre-dispatch roster snapshot is the first `claude` invocation now; a
    # missing CLI must still surface as the structured envelope, not a raised
    # FileNotFoundError (cubic review on PR #141).
    env = bg.BgRunner(
        _args(Path("/nonexistent/claude-cli"), wait_for=str(tmp_path / "x"))
    ).run()
    assert env.status == "precondition_failed"
    assert env.exit_code() == bg.EXIT_PRECONDITION
    assert "not found" in env.message


def test_bypass_refusal_is_precondition_failed(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "bypass_refused")
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "x"))).run()
    assert env.status == "precondition_failed"
    assert env.exit_code() == bg.EXIT_PRECONDITION
    assert "dangerously-skip-permissions" in env.message


def test_timeout_stops_session(shim, tmp_path, monkeypatch, kills):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "timeout")  # state stays working, no artifact
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "never"), timeout="0.4")).run()
    assert env.status == "timeout"
    assert env.exit_code() == bg.EXIT_TIMEOUT
    assert (222, bg.signal.SIGTERM) in kills


def test_runner_exit_paths_leave_no_new_blocked_session_except_intentional_park(
    shim, tmp_path, monkeypatch
):
    state = tmp_path / "state.json"

    def live_pid_rows() -> list[dict]:
        try:
            rows = json.loads(state.read_text())
        except (OSError, json.JSONDecodeError):
            return []
        return [row for row in rows if isinstance(row.get("pid"), int)]

    def reset_case() -> None:
        state.write_text("[]", encoding="utf-8")
        monkeypatch.delenv("FAKE_BG_HANDOFF", raising=False)
        monkeypatch.delenv("FAKE_BG_WAITFOR", raising=False)

    # Generic blocked requires a transcript with unrecognizable content: a
    # blocked row with NO transcript is the startup-dialog signature and must
    # classify as startup_dialog, not generic blocked.
    generic_transcripts = tmp_path / "generic-transcripts"
    generic_dir = generic_transcripts / "generic"
    generic_dir.mkdir(parents=True, exist_ok=True)
    (generic_dir / "abc12345-uuid.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Mid-task note with no known block markers."}
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases = [
        ("blocked", {"transcripts_root": str(generic_transcripts)}, "blocked", False),
        ("startup_dialog", {"transcripts_root": str(tmp_path / "missing-transcripts")}, "startup_dialog", False),
        ("timeout", {"timeout": "0.1", "wait_for": str(tmp_path / "never")}, "timeout", False),
    ]

    for scenario, args_overrides, expected_status, expect_live in cases:
        reset_case()
        monkeypatch.setenv("FAKE_BG_SCENARIO", scenario)
        env = bg.BgRunner(_args(shim, **args_overrides)).run()
        assert env.status == expected_status
        assert bool(live_pid_rows()) is expect_live

    reset_case()
    monkeypatch.setenv("FAKE_BG_SCENARIO", "rate_limited")
    tdir = tmp_path / "transcripts" / "rate"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "abc12345-uuid.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "You've hit your session limit. resets 2pm (America/Chicago)",
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = bg.BgRunner(_args(shim, transcripts_root=str(tmp_path / "transcripts"))).run()
    assert env.status == "rate_limited"
    assert live_pid_rows() == []

    reset_case()
    monkeypatch.setenv("FAKE_BG_SCENARIO", "model_rejected")
    model_transcripts = tmp_path / "model-transcripts"
    tdir = model_transcripts / "model"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "abc12345-uuid.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "There's an issue with the selected model (claude-bad-1).",
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = bg.BgRunner(_args(shim, transcripts_root=str(model_transcripts))).run()
    assert env.status == "model_rejected"
    assert live_pid_rows() == []

    reset_case()
    handoff = tmp_path / "handoff.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "needs_human")
    monkeypatch.setenv("FAKE_BG_HANDOFF", str(handoff))
    env = bg.BgRunner(_args(shim, handoff_file=str(handoff))).run()
    assert env.status == "needs_human"
    assert len(live_pid_rows()) == 1

    reset_case()
    monkeypatch.setenv("FAKE_BG_SCENARIO", "timeout")
    runner = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "interrupt"), timeout="2"))

    def raise_interrupt():
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "read_handoff", raise_interrupt)
    env = runner.run()
    assert env.status == "interrupted"
    assert live_pid_rows() == []


def test_teardown_failure_reported_in_envelope(shim, tmp_path, monkeypatch, kills):
    recorded: list[tuple[int, int]] = []

    def fake_kill_without_settle(pid: int, sig: int) -> None:
        recorded.append((pid, sig))

    monkeypatch.setattr(bg.os, "kill", fake_kill_without_settle)
    monkeypatch.setenv("FAKE_BG_SCENARIO", "timeout")

    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "never"), timeout="0.1")).run()

    assert env.status == "timeout"
    assert env.teardown_failed is True
    assert env.teardown_survivor_id == "abc12345"
    assert env.teardown_survivor_name
    assert env.teardown_survivor_session_id == "abc12345-uuid"
    assert len(recorded) >= 6


def test_stop_session_resignals_respawned_pid_until_settled(shim, tmp_path, monkeypatch):
    rows = [{**PARENT, "pid": 111, "id": "respawn1", "name": "quest-q7-builder-i1"}]
    (tmp_path / "state.json").write_text(json.dumps(rows))
    recorded: list[tuple[int, int]] = []
    state = tmp_path / "state.json"

    def fake_kill_respawn(pid: int, sig: int) -> None:
        recorded.append((pid, sig))
        current = json.loads(state.read_text())
        if pid == 111:
            current[0]["pid"] = 222
        else:
            current[0].pop("pid", None)
        state.write_text(json.dumps(current))

    monkeypatch.setattr(bg.os, "kill", fake_kill_respawn)

    result = bg.BgRunner(_args(shim)).stop_session("respawn1")

    assert result.settled is True
    assert recorded[:2] == [(111, bg.signal.SIGTERM), (222, bg.signal.SIGTERM)]


def test_fresh_dispatch_retires_live_same_name_before_launch(shim, tmp_path, monkeypatch, kills):
    name = "quest-q7-builder-i1"
    (tmp_path / "state.json").write_text(json.dumps([
        {**PARENT, "pid": 111, "id": "old11111", "name": name}
    ]))
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))

    env = bg.BgRunner(_args(shim, name=name, wait_for=str(wait))).run()

    assert env.status == "ok"
    assert (111, bg.signal.SIGTERM) in kills


def test_fresh_dispatch_fails_when_same_name_cannot_be_retired(shim, tmp_path, monkeypatch):
    name = "quest-q7-builder-i1"
    (tmp_path / "state.json").write_text(json.dumps([
        {**PARENT, "pid": 111, "id": "old11111", "name": name}
    ]))

    def fake_kill_without_settle(pid: int, sig: int) -> None:
        return None

    monkeypatch.setattr(bg.os, "kill", fake_kill_without_settle)

    env = bg.BgRunner(_args(shim, name=name, wait_for=str(tmp_path / "out.json"))).run()

    assert env.status == "dispatch_failed"
    assert "same-name" in env.message


def test_incomplete_when_done_without_artifact(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "incomplete")  # state done, artifact never written
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "missing"))).run()
    assert env.status == "incomplete"
    assert env.exit_code() == bg.EXIT_SESSION_FAILED
    assert str(tmp_path / "missing") in env.missing


def test_self_test_passes_in_this_env():
    assert bg._self_test() == bg.EXIT_OK


def test_sweep_stops_only_matching_prefix_sessions(shim, tmp_path, monkeypatch, kills, capsys):
    rows = [
        {**PARENT, "pid": 111, "id": "aaa11111", "name": "quest-q7-planner-i1"},
        {**PARENT, "pid": 112, "id": "bbb22222", "name": "quest-q7-builder-i2"},
        {**PARENT, "pid": 113, "id": "ccc33333", "name": "quest-OTHER-fixer-i1"},
        {**PARENT, "pid": 114, "id": "ddd44444", "name": "bgrun-unrelated"},
    ]
    (tmp_path / "state.json").write_text(json.dumps(rows))
    rc = bg.main(["--claude-bin", str(shim), "--poll-interval", "0.05", "--sweep", "quest-q7-"])
    out = capsys.readouterr().out
    assert rc == bg.EXIT_OK
    killed_pids = {pid for pid, _ in kills}
    assert killed_pids == {111, 112}
    assert "swept aaa11111" in out and "swept bbb22222" in out
    assert "2 session(s)" in out


def test_sweep_reports_incomplete_when_teardown_survives(
    shim, tmp_path, monkeypatch, capsys
):
    rows = [{**PARENT, "pid": 111, "id": "aaa11111", "name": "quest-q7-planner-i1"}]
    (tmp_path / "state.json").write_text(json.dumps(rows))

    def fake_kill_without_settle(pid: int, sig: int) -> None:
        return None

    monkeypatch.setattr(bg.os, "kill", fake_kill_without_settle)

    rc = bg.main(["--claude-bin", str(shim), "--poll-interval", "0.05", "--sweep", "quest-q7-"])
    out = capsys.readouterr().out

    assert rc == bg.EXIT_BLOCKED
    assert "teardown_failed aaa11111" in out
    assert "sweep incomplete" in out


def test_sweep_skips_without_traceback_when_claude_cli_missing(tmp_path, capsys):
    rc = bg.main(["--claude-bin", str(tmp_path / "missing-claude"), "--sweep", "quest-q7-"])
    out = capsys.readouterr().out

    assert rc == bg.EXIT_OK
    assert "sweep skipped: claude CLI not found" in out


# ---- stale-state guard (PR #137 review feedback) ---------------------------
def test_fresh_dispatch_clears_stale_wait_for_no_false_success(
    shim, tmp_path, monkeypatch, kills
):
    """A pre-existing non-empty --wait-for file must not satisfy this run."""
    wait = tmp_path / "out.json"
    wait.write_text("STALE FROM A PRIOR RUN", encoding="utf-8")
    # Session reaches done without writing anything ("incomplete" scenario).
    monkeypatch.setenv("FAKE_BG_SCENARIO", "incomplete")

    env = bg.BgRunner(_args(shim, wait_for=str(wait))).run()

    assert env.status == "incomplete"  # was: instant false "ok" off stale file
    assert wait.read_text(encoding="utf-8") == ""  # cleared at dispatch


def test_fresh_dispatch_clears_stale_complete_handoff(
    shim, tmp_path, monkeypatch, kills
):
    """A leftover complete handoff must not complete this run."""
    hand = tmp_path / "handoff.json"
    hand.write_text(json.dumps({"status": "complete"}), encoding="utf-8")
    monkeypatch.setenv("FAKE_BG_SCENARIO", "incomplete")

    env = bg.BgRunner(_args(shim, handoff_file=str(hand))).run()

    assert env.status == "incomplete"  # was: instant false "ok" off stale handoff


def test_fresh_dispatch_clears_stale_needs_human_handoff(
    shim, tmp_path, monkeypatch, kills
):
    """A leftover needs_human handoff must not bubble back for a fresh run."""
    wait = tmp_path / "out.json"
    hand = tmp_path / "handoff.json"
    hand.write_text(
        json.dumps({"status": "needs_human", "questions": ["stale?"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))

    env = bg.BgRunner(
        _args(shim, wait_for=str(wait), handoff_file=str(hand))
    ).run()

    assert env.status == "ok"  # was: instant needs_human replay of the stale file
    assert env.questions == []


def test_resume_clears_parked_handoff_but_keeps_wait_for(
    shim, tmp_path, monkeypatch, kills
):
    """Resume must clear the parked needs_human handoff (it would re-trigger
    instantly) while preserving --wait-for files the parked session wrote."""
    _seed_parent(tmp_path)
    wait = tmp_path / "out.json"
    wait.write_text("PARKED-WORK", encoding="utf-8")
    hand = tmp_path / "handoff.json"
    hand.write_text(
        json.dumps({"status": "needs_human", "questions": ["A or B?"]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")

    env = bg.BgRunner(
        _args(
            shim,
            resume="bgrun-parked",
            answer="B",
            wait_for=str(wait),
            handoff_file=str(hand),
        )
    ).run()

    assert env.status == "ok"
    assert env.resumed is True
    assert env.questions == []  # stale questions did not replay
    assert wait.read_text(encoding="utf-8") == "PARKED-WORK"  # preserved


# ---- confirm must not adopt a stale same-name row ---------------------------
def test_stale_same_name_row_does_not_confirm_failed_dispatch(shim, tmp_path, monkeypatch):
    """Quest passes deterministic names (quest-<id>-<role>-i<n>), so a settled
    row left by a crashed prior run shares the new dispatch's name. A dispatch
    that never registers must report dispatch_failed — not adopt the stale row
    and misreport its state (here done → 'incomplete') for the wrong session."""
    _seed_parent(tmp_path, name="quest-q7-planner-i1", state="done", status="idle")
    monkeypatch.setenv("FAKE_BG_SCENARIO", "never_confirm")
    env = bg.BgRunner(
        _args(shim, name="quest-q7-planner-i1", wait_for=str(tmp_path / "x"))
    ).run()
    assert env.status == "dispatch_failed"
    assert env.exit_code() == bg.EXIT_DISPATCH_FAILED
    assert env.session_id != PARENT_SID  # never adopted the stale row


def test_confirm_name_fallback_prefers_new_row_over_stale(shim, monkeypatch):
    """With no parsed short id, the name fallback must skip rows that existed
    before the dispatch and accept the newly registered one — even when the
    stale row lists first."""
    runner = bg.BgRunner(_args(shim, name="quest-q7-planner-i1"))
    stale = {"id": "old00001", "sessionId": "old-sid", "name": "quest-q7-planner-i1", "kind": "background"}
    fresh = {"id": "new00002", "sessionId": "new-sid", "name": "quest-q7-planner-i1", "kind": "background"}
    monkeypatch.setattr(runner, "agents_json", lambda: [stale, fresh])
    row = runner._confirm_row(None, {"old00001", "old-sid"})
    assert row is not None and row["id"] == "new00002"
    # And when only the stale row exists, nothing confirms.
    monkeypatch.setattr(runner, "agents_json", lambda: [stale])
    assert runner._confirm_row(None, {"old00001", "old-sid"}) is None
