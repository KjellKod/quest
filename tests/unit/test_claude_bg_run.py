"""Unit tests for the standalone claude --bg runner proof of concept.

These exercise the full dispatch -> confirm -> wait -> collect -> teardown
lifecycle against a fake `claude` shim (no real model calls, no bypass-acceptance
needed), the needs_human bubble-back and resume continuation, plus the ANSI/PTY
noise-firewall primitive.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

import claude_bg_run as bg

# A fake `claude` CLI. Behavior is driven by FAKE_BG_* env vars so each test can
# script a scenario. It emulates: `--bg` (incl. `--resume`), `agents --json`,
# `logs`, `stop`, `rm`.
FAKE_CLAUDE = r'''#!/usr/bin/env python3
import os, sys, json, pathlib
D = pathlib.Path(os.environ["FAKE_BG_DIR"])
S = os.environ.get("FAKE_BG_SCENARIO", "ok")
WAIT = os.environ.get("FAKE_BG_WAITFOR", "")
HAND = os.environ.get("FAKE_BG_HANDOFF", "")
state = D / "state.json"
calls = D / "calls.log"

def log(line): calls.open("a").write(line + "\n")
def read_state():
    try: return json.loads(state.read_text())
    except Exception: return None

args = sys.argv[1:]
if args[:1] == ["--bg"]:
    is_resume = "--resume" in args
    name = args[args.index("--name") + 1] if "--name" in args else "?"
    log(("resume " if is_resume else "bg ") + name)
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
        state.write_text(json.dumps(
            {"id": sid, "name": name, "sessionId": sid + "-uuid",
             "kind": "background", "state": st, "status": "idle"}))
    if eff == "ok" and WAIT:
        pathlib.Path(WAIT).write_text("RESULT")
    if eff == "needs_human" and HAND:
        pathlib.Path(HAND).write_text(json.dumps(
            {"status": "needs_human", "questions": ["A or B?"]}))
    print(f"backgrounded · {sid} · {name}")
    sys.exit(0)
if args[:2] == ["agents", "--json"]:
    s = read_state()
    print(json.dumps([s] if s else []))
    sys.exit(0)
if args[:1] == ["logs"]:
    print("\x1b[2J\x1b[H\x1b[31mneeds input: choose A or B?\x1b[0m\r\n")
    sys.exit(0)
if args and args[0] in ("stop", "rm"):
    log(f"{args[0]} {args[1] if len(args) > 1 else ''}")
    if args[0] == "rm" and state.exists(): state.unlink()
    sys.exit(0)
sys.exit(0)
'''


@pytest.fixture
def shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "fake_claude.py"
    p.write_text(FAKE_CLAUDE, encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("FAKE_BG_DIR", str(tmp_path))
    return p


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
def test_ok_completes_on_artifact_and_tears_down(shim, tmp_path, monkeypatch):
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.exit_code() == bg.EXIT_OK
    assert str(wait) in env.artifacts_found and not env.missing
    calls = _calls(tmp_path)
    assert any(c.startswith("stop ") for c in calls)
    assert any(c.startswith("rm ") for c in calls)
    # teardown order: stop precedes rm
    assert [c.split()[0] for c in calls if c.split()[0] in ("stop", "rm")] == ["stop", "rm"]


def test_needs_human_bubbles_back(shim, tmp_path, monkeypatch):
    hand = tmp_path / "handoff.json"
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "needs_human")
    monkeypatch.setenv("FAKE_BG_HANDOFF", str(hand))
    env = bg.BgRunner(_args(shim, wait_for=str(wait), handoff_file=str(hand))).run()
    assert env.status == "needs_human"
    assert env.exit_code() == bg.EXIT_NEEDS_HUMAN
    assert env.questions == ["A or B?"]


def test_needs_human_keeps_session_alive_for_resume(shim, tmp_path, monkeypatch):
    hand = tmp_path / "handoff.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "needs_human")
    monkeypatch.setenv("FAKE_BG_HANDOFF", str(hand))
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "out.json"), handoff_file=str(hand))).run()
    assert env.status == "needs_human"
    # Session must NOT be torn down: no stop/rm, so it can be resumed.
    calls = _calls(tmp_path)
    assert not any(c.startswith("stop") or c.startswith("rm") for c in calls)
    assert env.session_id  # surfaced so the orchestrator can --resume it


def test_resume_continues_same_session(shim, tmp_path, monkeypatch):
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, resume="abc12345-uuid", answer="use option A", wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.resumed is True and env.fell_back is False
    assert any(c.startswith("resume ") for c in _calls(tmp_path))


def test_resume_falls_back_to_fresh_dispatch(shim, tmp_path, monkeypatch):
    wait = tmp_path / "out.json"
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_fallback")
    monkeypatch.setenv("FAKE_BG_WAITFOR", str(wait))
    env = bg.BgRunner(_args(shim, resume="dead-session", answer="use option A", wait_for=str(wait))).run()
    assert env.status == "ok"
    assert env.fell_back is True
    assert "re-dispatched" in env.message
    calls = [c.split()[0] for c in _calls(tmp_path)]
    assert "resume" in calls and "bg" in calls  # tried resume, then fresh


def test_resume_without_answer_is_precondition_failed(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "resume_ok")
    env = bg.BgRunner(_args(shim, resume="abc12345-uuid", wait_for=str(tmp_path / "x"))).run()
    assert env.status == "precondition_failed"
    assert env.exit_code() == bg.EXIT_PRECONDITION


def test_blocked_is_detected_with_distilled_logs(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "blocked")
    env = bg.BgRunner(_args(shim)).run()  # no wait_for -> relies on state
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


def test_timeout_stops_session(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "timeout")  # state stays working, no artifact
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "never"), timeout="0.4")).run()
    assert env.status == "timeout"
    assert env.exit_code() == bg.EXIT_TIMEOUT
    assert any(c.startswith("stop ") for c in _calls(tmp_path))


def test_incomplete_when_done_without_artifact(shim, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BG_SCENARIO", "incomplete")  # state done, artifact never written
    env = bg.BgRunner(_args(shim, wait_for=str(tmp_path / "missing"))).run()
    assert env.status == "incomplete"
    assert env.exit_code() == bg.EXIT_SESSION_FAILED
    assert str(tmp_path / "missing") in env.missing


def test_self_test_passes_in_this_env():
    assert bg._self_test() == bg.EXIT_OK
