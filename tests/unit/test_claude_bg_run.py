"""Unit tests for the standalone claude --bg runner proof of concept.

These exercise the full dispatch -> confirm -> wait -> collect -> teardown
lifecycle against a fake `claude` shim (no real model calls, no bypass-acceptance
needed), the needs_human bubble-back and resume continuation, plus the ANSI/PTY
noise-firewall primitive.

The shim mirrors the REAL CLI surface: `--bg` (incl. `--resume`) and
`agents --json` only — there are no `logs`/`stop`/`rm` subcommands. State is a
LIST of session rows (each with a pid), so resume scenarios can model the parked
parent session sitting next to the newly dispatched agent. Teardown is a signal
to the row's pid; tests intercept `os.kill` and drop the row to simulate exit.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

import claude_bg_run as bg

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
    is_resume = "--resume" in args
    sid_arg = args[args.index("--resume") + 1] if is_resume else ""
    name = args[args.index("--name") + 1] if "--name" in args else "?"
    log(("resume " if is_resume else "bg ") + name + (f" sid={sid_arg}" if is_resume else ""))
    if S == "bypass_refused":
        print("--bg with bypassPermissions requires accepting the disclaimer first. "
              "Run `claude --dangerously-skip-permissions` once interactively.")
        sys.exit(0)
    eff = S
    if S == "resume_ok":
        eff = "ok"
    if S == "resume_fallback":
        eff = "never_confirm" if is_resume else "ok"
    sid = "abc12345"
    if eff != "never_confirm":
        st = {"blocked": "blocked", "incomplete": "done"}.get(eff, "working")
        rs = rows()
        rs.append({"pid": 222, "id": sid, "name": name, "sessionId": sid + "-uuid",
                   "kind": "background", "state": st, "status": "idle"})
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
# Anything else (e.g. the nonexistent logs/stop/rm) parses as a PROMPT: no-op.
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


# ---- lifecycle scenarios ---------------------------------------------------
def test_ok_completes_on_artifact_and_tears_down(shim, tmp_path, monkeypatch, kills):
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.exit_code() == bg.EXIT_OK
    assert str(wait) in env.artifacts_found and not env.missing
    # Teardown = SIGTERM to the supervisor-reported pid (there is no stop/rm).
    assert (222, bg.signal.SIGTERM) in kills


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
    # PR #137 stopgap: callers with no resume loop (Quest) pass
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
    # re-dispatch also fails, the parked needs_human handoff is restored (it was
    # cleared as the stale guard before the unconfirmed re-dispatch), and the
    # parked parent is not torn down — so the question survives for a retry.
    _seed_parent(tmp_path)
    hand = tmp_path / "handoff.json"
    hand.write_text(json.dumps({"status": "needs_human", "questions": ["A or B?"]}))
    monkeypatch.setenv("FAKE_BG_SCENARIO", "never_confirm")  # resume AND fresh both fail
    env = bg.BgRunner(
        _args(shim, resume=PARENT_SID, answer="use A", handoff_file=str(hand),
              wait_for=str(tmp_path / "out.json"))
    ).run()
    assert env.status == "dispatch_failed"
    assert env.fell_back is True
    assert "re-dispatch also failed" in env.message
    # The parked question survived the failed fallback dispatch.
    assert json.loads(hand.read_text())["questions"] == ["A or B?"]
    # And the parked parent was not retired.
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


def test_dispatch_failed_when_never_registers(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "never_confirm")
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "x"))).run()
    assert env.status == "dispatch_failed"
    assert env.exit_code() == bg.EXIT_DISPATCH_FAILED


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
