"""Quest Claude runtime helpers for host-aware dispatch and transport execution.

Codex-led Claude roles run through one of two transports, both invoked as
subprocesses speaking the same file contract (poll handoff.json + artifacts):
  * background-agent (default via "auto"): scripts/claude_bg_run.py —
    `claude --bg` sessions billed to the subscription pool.
  * bridge (explicit API path): scripts/quest_claude_bridge.py —
    `claude --print`, works without the background-agent daemon.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from quest_runtime.artifacts import (
    any_artifact_missing_or_empty,
    check_artifact_paths,
    prepare_artifact_files,
)
from quest_runtime.orchestration import runtime_for_model
from quest_runtime.state import utc_now_iso


@dataclass
class RuntimeSelection:
    runtime: str
    entrypoint: str
    reason: str
    requires_probe: bool


@dataclass
class RunResult:
    exit_code: int
    handoff_state: str
    result_kind: str
    source: str | None
    stdout: str
    stderr: str
    status: str | None = None
    session_id: str | None = None
    short_id: str | None = None
    questions: list[str] | None = None
    resumed_from: str | None = None
    teardown_failed: bool = False
    teardown_survivor_id: str | None = None
    teardown_survivor_name: str | None = None
    teardown_survivor_session_id: str | None = None
    reset_at: str | None = None
    rejected_model: str | None = None


# Canonical message for reporting an actual violation (a Codex-led session
# attempting to dispatch a Codex role through Codex MCP). Not part of the
# success-path selection reason — a correct selection must not log
# "Orchestration violation", or the log itself becomes a misdiagnosis trap.
CODEX_LED_CODEX_VIOLATION_GUIDANCE = (
    "Orchestration violation: Codex-led Codex roles must use local Codex "
    "subagents that inherit the active Codex model. Codex MCP is only valid "
    "for Claude-led sessions dispatching Codex roles."
)


# Helper scripts live next to this package (…/scripts/). Resolve them off
# __file__ so they are found regardless of the caller's cwd — Quest may be
# installed outside the target repo and invoked by absolute path (see
# ideas/2026-06-15-bug-report-for-branch-claude/bg-transport-step2.md).
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # …/scripts
DEFAULT_BRIDGE_SCRIPT = str(_SCRIPTS_DIR / "quest_claude_bridge.py")
DEFAULT_BG_RUNNER_SCRIPT = str(_SCRIPTS_DIR / "claude_bg_run.py")

# Background-agent teardown can take several signal attempts after the child's
# own --timeout fires. Wait this much BEYOND `timeout` for claude_bg_run.py to
# finish (including teardown) before terminating it — killing the child does not
# stop the detached supervisor session, so racing it would orphan the session.
_BG_TEARDOWN_MARGIN_SECONDS = 30.0

# scripts/claude_bg_run.py exit codes → quest result kinds, used only when the
# handoff contract was NOT satisfied (a found handoff always wins).
# 2 precondition / 3 dispatch_failed / 4 blocked: daemon, auth, or bypass
# problems — Tier B (permission escalation) cannot fix those, so they classify
# as invocation_error and the ladder blocks fast with remediation.
# 6 (session finished without artifacts) and 130 (interrupted) deliberately
# fall through to the standard handoff-state classification (handoff_missing)
# so the existing missing-handoff retry ladder applies unchanged.
_BG_EXIT_RESULT_KINDS: dict[int, str] = {
    2: "invocation_error",
    3: "invocation_error",
    4: "invocation_error",
    5: "timeout",
    7: "rate_limited",
    8: "startup_dialog",
    9: "model_rejected",
}

_BG_STATUS_RESULT_KINDS: dict[str, str] = {
    "rate_limited": "rate_limited",
    "startup_dialog": "startup_dialog",
    "model_rejected": "model_rejected",
}


def normalize_claude_cli_model(model: str) -> str | None:
    normalized = model.strip()
    if not normalized:
        raise ValueError("Claude model must be a non-empty value or the `claude` sentinel")
    if normalized == "claude":
        return None
    return normalized


def _effective_permission_mode(
    permission_mode: str, permission_escalation: bool
) -> str:
    if not permission_escalation:
        return permission_mode
    if permission_mode in {"default", "auto", "plan"}:
        return "acceptEdits"
    return permission_mode


def select_role_runtime(
    *,
    orchestrator: str,
    target_runtime: str,
    native_claude_available: bool = True,
    claude_bridge_available: bool = False,
) -> RuntimeSelection:
    """Select the additive runtime path for a Quest role.

    Runtime names describe the backend family. Entrypoints describe how the
    current orchestrator invokes that backend.

    `target_runtime` accepts either a runtime family (`claude`/`codex`) or a
    persisted `models.<role>` model ID (for example `gpt-5.5` or
    `claude-opus-4-6`) — model IDs are normalized through the canonical
    `runtime_for_model()` mapping before entrypoint selection, so callers do
    not need their own model-to-runtime translation.

    This is the reference implementation of the dispatch matrix in
    `.skills/quest/delegation/workflow.md`. Orchestrators follow that
    document at runtime; this helper and its tests keep the matrix
    semantics pinned in code.
    """

    normalized_orchestrator = orchestrator.strip().lower()
    normalized_target = runtime_for_model(target_runtime)

    if normalized_orchestrator not in {"claude", "codex"}:
        raise ValueError(f"Unsupported orchestrator: {orchestrator}")

    if normalized_target == "codex":
        if normalized_orchestrator == "codex":
            return RuntimeSelection(
                runtime="codex",
                entrypoint="subagent",
                reason=(
                    "runtime=codex entrypoint=subagent: Codex-led Codex role "
                    "uses local Codex subagents and inherits the active Codex "
                    "model. Codex MCP is only valid for Claude-led sessions "
                    "dispatching Codex roles."
                ),
                requires_probe=False,
            )
        return RuntimeSelection(
            runtime="codex",
            entrypoint="codex_mcp",
            reason=(
                "runtime=codex entrypoint=codex_mcp: Claude-led session may "
                "dispatch Codex roles through Codex MCP."
            ),
            requires_probe=False,
        )

    if normalized_orchestrator == "codex":
        if claude_bridge_available:
            return RuntimeSelection(
                runtime="claude",
                entrypoint="scripts/quest_claude_runner.py",
                reason=(
                    "runtime=claude entrypoint=scripts/quest_claude_runner.py: "
                    "Codex-led Claude role uses the additive bridge-backed "
                    "Quest runner."
                ),
                requires_probe=True,
            )
        return RuntimeSelection(
            runtime="blocked",
            entrypoint="",
            reason=(
                "runtime=claude entrypoint=blocked: Codex-led Claude role "
                "requires the Quest Claude bridge runner "
                "(scripts/quest_claude_runner.py), but the bridge probe is "
                "unavailable. Re-run the host-context Claude bridge probe or "
                "assign this role to Codex."
            ),
            requires_probe=True,
        )

    if native_claude_available:
        return RuntimeSelection(
            runtime="claude",
            entrypoint="Task(...)",
            reason=(
                "runtime=claude entrypoint=Task(...): Claude-led or "
                "native-Claude host keeps native Claude task execution."
            ),
            requires_probe=False,
        )

    return RuntimeSelection(
        runtime="blocked",
        entrypoint="",
        reason="Claude runtime requested but native Claude tasks are unavailable.",
        requires_probe=False,
    )


def resolve_path(cwd: str | Path, path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (Path(cwd) / candidate).resolve()


def unique_dirs(paths: Iterable[str | Path]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        resolved = str(Path(path).resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def build_bridge_cmd(
    *,
    cwd: str | Path,
    bridge_script: str | Path,
    prompt_file: str | Path,
    model: str,
    timeout: float,
    permission_mode: str,
    add_dirs: Iterable[str | Path] | None = None,
) -> list[str]:
    cli_model = normalize_claude_cli_model(model)
    cmd = [
        sys.executable,
        str(bridge_script),
        "--prompt-file",
        str(prompt_file),
        "--output-format",
        "text",
        "--timeout",
        str(timeout),
        "--permission-mode",
        permission_mode,
    ]
    if cli_model is not None:
        cmd.extend(["--model", cli_model])
    if add_dirs:
        for directory in unique_dirs(add_dirs):
            cmd.extend(["--add-dir", directory])
    return cmd


def build_bg_cmd(
    *,
    cwd: str | Path,
    bg_runner_script: str | Path,
    prompt_file: str | Path,
    name: str,
    model: str,
    timeout: float,
    permission_mode: str,
    handoff_file: str | Path,
    wait_for: Iterable[str | Path],
    add_dirs: Iterable[str | Path] | None = None,
    teardown_on_needs_human: bool = False,
    resume: str | None = None,
    answer_file: str | Path | None = None,
) -> list[str]:
    """argv for the background-agent transport (scripts/claude_bg_run.py).

    Passes --handoff-file so a needs_human handoff is recognized promptly. By
    default Quest leaves background-agent needs_human sessions parked so the
    orchestrator can resume the same session with --resume/--answer-file.
    Direct callers with no relay can opt into --teardown-on-needs-human.
    """
    cli_model = normalize_claude_cli_model(model)
    cmd = [
        sys.executable,
        str(bg_runner_script),
        "--json",
        "--no-protocol",
        "--name",
        name,
        "--timeout",
        str(timeout),
        "--permission-mode",
        permission_mode,
        "--handoff-file",
        str(handoff_file),
    ]
    if resume:
        cmd.extend(["--resume", resume])
        if answer_file is not None:
            cmd.extend(["--answer-file", str(answer_file)])
        cmd.extend(["--prompt-file", str(prompt_file)])
    else:
        cmd.extend(["--prompt-file", str(prompt_file)])
    if cli_model is not None:
        cmd.extend(["--model", cli_model])
    if teardown_on_needs_human:
        cmd.append("--teardown-on-needs-human")
    for path in wait_for:
        cmd.extend(["--wait-for", str(path)])
    if add_dirs:
        for directory in unique_dirs(add_dirs):
            cmd.extend(["--add-dir", directory])
    return cmd


def bg_session_name(quest_id: str, agent: str, iteration: int) -> str:
    """Deterministic background-session name; also the orphan-sweep key."""
    return f"quest-{quest_id}-{agent}-i{iteration}"


def _bg_failure_detail(stdout: str) -> str:
    """Distill the bg runner's JSON envelope into a one-line diagnostic."""
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(envelope, dict):
        return ""
    parts = [
        f"bg {key}={envelope[key]}"
        for key in ("status", "message", "logs_tail")
        if envelope.get(key)
    ]
    return "; ".join(parts)


def _bg_envelope(stdout: str) -> dict | None:
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return envelope if isinstance(envelope, dict) else None


def _run_result_fields_from_bg(stdout: str) -> dict:
    envelope = _bg_envelope(stdout) or {}
    questions = envelope.get("questions")
    return {
        "status": envelope.get("status") if isinstance(envelope.get("status"), str) else None,
        "session_id": envelope.get("session_id") if isinstance(envelope.get("session_id"), str) else None,
        "short_id": envelope.get("short_id") if isinstance(envelope.get("short_id"), str) else None,
        "questions": [str(q) for q in questions] if isinstance(questions, list) else None,
        "resumed_from": envelope.get("resumed_from") if isinstance(envelope.get("resumed_from"), str) else None,
        "teardown_failed": bool(envelope.get("teardown_failed")),
        "teardown_survivor_id": envelope.get("teardown_survivor_id") if isinstance(envelope.get("teardown_survivor_id"), str) else None,
        "teardown_survivor_name": envelope.get("teardown_survivor_name") if isinstance(envelope.get("teardown_survivor_name"), str) else None,
        "teardown_survivor_session_id": envelope.get("teardown_survivor_session_id") if isinstance(envelope.get("teardown_survivor_session_id"), str) else None,
        "reset_at": envelope.get("reset_at") if isinstance(envelope.get("reset_at"), str) else None,
        "rejected_model": envelope.get("rejected_model") if isinstance(envelope.get("rejected_model"), str) else None,
    }


def sweep_left_survivor(returncode: int, stdout: str) -> bool:
    """True when a `claude_bg_run.py --sweep` did NOT verifiably clean up.

    Single owner of the sweep-output vocabulary (nonzero exit, teardown_failed
    survivors, "sweep skipped:" when the CLI/roster is unavailable, and
    "skipped active" rows a default sweep deliberately spares) so the callers
    that warn about leaks can never drift apart on what counts as one.
    """
    return (
        returncode != 0
        or "teardown_failed" in stdout
        or "sweep skipped:" in stdout
        or "skipped active" in stdout
    )


def classify_bg_probe_failure(stderr: str) -> str | None:
    """Return a specific bg preflight failure kind when stderr is recognizable.

    Legacy stderr-only signals. The rate_limited/startup_dialog/model_rejected
    kinds are NOT classified here: they arrive as the structured envelope
    `status`, which run_bg_probe reads directly — substring-matching prose for
    them would misclassify agent text that merely mentions limits/models.
    """
    normalized = stderr.lower()
    if "dangerously-skip-permissions" in normalized or (
        "bypasspermissions" in normalized and "accepted" in normalized
    ):
        return "bypass_not_accepted"
    if (
        "send a prompt to start" in normalized
        or "did not consume the initial prompt" in normalized
    ):
        return "bg_initial_prompt_not_consumed"
    if "sessionstart" in normalized and (
        "permission denied" in normalized or "hook" in normalized
    ):
        return "hook_startup_failed"
    return None


def resolve_claude_transport(transport: str) -> str:
    """Resolve a configured transport to the concrete runner transport.

    "auto" → background-agent. Quest startup preflight is responsible for
    proving it first; if this helper is reached without a cache, it still must
    not silently choose the API-metered bridge. Explicit bridge passes through.
    """
    if transport == "background-agent":
        return "background-agent"
    if transport == "bridge":
        return "bridge"
    if transport == "auto":
        return "background-agent"
    raise ValueError(
        f"transport must be auto|background-agent|bridge (got {transport!r})"
    )


def classify_handoff_file(path: str | Path) -> str:
    handoff_path = Path(path)
    if not handoff_path.exists():
        return "missing"
    try:
        json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unparsable"
    return "found"


# Status values the handoff contract allows; anything else is treated as
# unknown and the status= log field is omitted rather than guessed. Lines
# without status= are excluded from status statistics by contract (legacy
# lines predate the field).
HANDOFF_STATUSES = frozenset({"complete", "needs_human", "blocked"})


def read_handoff_status(path: str | Path) -> str | None:
    """Return the handoff's status when it is a known contract value."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if isinstance(status, str) and status in HANDOFF_STATUSES:
        return status
    return None


def extract_text_status(text_handoff: str) -> str | None:
    """Pull STATUS: <value> out of a ---HANDOFF--- text block."""
    match = re.search(r"^STATUS:\s*(\S+)", text_handoff, flags=re.MULTILINE)
    if match and match.group(1) in HANDOFF_STATUSES:
        return match.group(1)
    return None


def extract_text_handoff(text: str) -> str | None:
    marker = "---HANDOFF---"
    if marker not in text:
        return None
    return text[text.index(marker) :].strip()


def classify_result_kind(exit_code: int, stderr: str, handoff_state: str) -> str:
    normalized_stderr = stderr.lower()
    if handoff_state == "found":
        return "handoff_json"
    if exit_code == 124 or "timed out" in normalized_stderr:
        return "timeout"
    if any(
        marker in normalized_stderr
        for marker in (
            "not found",
            "no such file",
            "not authenticated",
            "claude cli",
        )
    ):
        return "invocation_error"
    if handoff_state == "unparsable":
        return "handoff_unparsable"
    if handoff_state == "missing":
        return "handoff_missing"
    return "error"


def classify_failure_kind(
    result: RunResult,
    artifact_paths: list[Path],
    workspace_root: Path,
) -> str:
    """Classify run failures for retry routing."""

    if result.result_kind == "timeout":
        return "timeout"
    # Transport-terminal kinds must never route into the Tier B
    # permission-escalation retry: artifacts are missing because the run never
    # ran, not because of a write boundary — escalating just burns a retry
    # against the same rate limit / rejected model / startup dialog.
    if result.result_kind in {
        "invocation_error",
        "rate_limited",
        "startup_dialog",
        "model_rejected",
    }:
        return "invocation"

    _, external_paths = check_artifact_paths(artifact_paths, workspace_root)
    if external_paths and any_artifact_missing_or_empty(artifact_paths):
        return "write_boundary"

    if "permission denied" in result.stderr.lower():
        return "permission"

    return "model"


def _retry_artifact_dirs(
    artifact_paths: list[Path],
    workspace_root: Path,
) -> list[Path]:
    """Return out-of-workspace artifact directories for escalation retries."""

    _, external_paths = check_artifact_paths(artifact_paths, workspace_root)
    return [path.parent for path in external_paths]


def append_context_health_log(
    quest_dir: str | Path,
    *,
    phase: str,
    agent: str,
    iteration: int,
    handoff_state: str,
    source: str,
    status: str | None = None,
    transport: str | None = None,
) -> None:
    """Append one context-health line.

    `status` (complete|needs_human|blocked) is the handoff's own status when
    known — omitted (never guessed) when the handoff is missing, unparsable,
    or carries an unknown value. Consumers count only lines that carry the
    field, so legacy lines stay out of status statistics.

    `transport` (background-agent|bridge) is set for Codex-led Claude roles —
    this module is their only writer, so the field's presence is what the quest
    end summary and celebration key on. Other runtimes never set it.
    """
    log_dir = Path(quest_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    status_field = f" | status={status}" if status else ""
    transport_field = f" | transport={transport}" if transport else ""
    log_line = (
        f"{utc_now_iso()} | phase={phase} | agent={agent} | runtime=claude | "
        f"iter={iteration} | handoff_json={handoff_state} | source={source}"
        f"{status_field}{transport_field}\n"
    )
    with (log_dir / "context_health.log").open("a", encoding="utf-8") as handle:
        handle.write(log_line)


def run_claude_role(
    *,
    cwd: str | Path,
    quest_dir: str | Path,
    phase: str,
    agent: str,
    iteration: int,
    prompt_file: str | Path,
    handoff_file: str | Path,
    bridge_script: str | Path,
    model: str,
    timeout: float,
    permission_mode: str,
    artifact_paths: Iterable[str | Path] | None = None,
    permission_escalation: bool = False,
    allow_text_fallback: bool = False,
    add_dirs: Iterable[str | Path] | None = None,
    poll_interval: float = 0.5,
    exit_grace_seconds: float = 2.0,
    transport: str = "bridge",
    bg_runner_script: str | Path = DEFAULT_BG_RUNNER_SCRIPT,
    teardown_on_needs_human: bool = False,
    resume: str | None = None,
    answer_file: str | Path | None = None,
) -> RunResult:
    if transport not in {"bridge", "background-agent"}:
        raise ValueError(
            f"transport must be 'bridge' or 'background-agent' (got {transport!r})"
        )
    if resume is not None and not resume.strip():
        # Presence means intent: an empty resume reference must fail loudly,
        # not silently coerce into a fresh (artifact-truncating) dispatch.
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr="resume must be a non-empty session id/short id/name when provided",
        )
    workspace_root = Path(cwd).resolve()
    resolved_quest_dir = resolve_path(cwd, quest_dir)
    resolved_prompt_file = resolve_path(cwd, prompt_file)
    resolved_handoff_file = resolve_path(cwd, handoff_file)
    resolved_artifact_paths = [resolve_path(cwd, path) for path in artifact_paths or []]
    local_artifact_paths, external_artifact_paths = check_artifact_paths(
        resolved_artifact_paths,
        workspace_root,
    )
    # NEVER truncate artifacts on a resume: the parked agent may have written
    # them before asking its question, and claude_bg_run.py's resume mode
    # deliberately preserves --wait-for files ("the resumed agent will not
    # rewrite work it believes is done"). Truncating here destroys that work
    # and turns a successfully answered relay into handoff_missing/incomplete.
    if resolved_artifact_paths and not permission_escalation and resume is None:
        try:
            prepare_artifact_files(resolved_artifact_paths)
        except OSError as exc:
            failure_kind = (
                "write_boundary"
                if external_artifact_paths
                else (
                    "permission"
                    if isinstance(exc, PermissionError)
                    or "permission denied" in str(exc).lower()
                    else "invocation"
                )
            )
            if failure_kind in {"write_boundary", "permission"}:
                retry_add_dirs = list(add_dirs or [])
                retry_add_dirs.extend(path.parent for path in external_artifact_paths)
                retry_note = (
                    f"Tier B retry: agent={agent} phase={phase} "
                    f"failure_kind={failure_kind} permission_escalation=True"
                )
                retry_result = run_claude_role(
                    cwd=cwd,
                    quest_dir=resolved_quest_dir,
                    phase=phase,
                    agent=agent,
                    iteration=iteration,
                    prompt_file=resolved_prompt_file,
                    handoff_file=resolved_handoff_file,
                    bridge_script=bridge_script,
                    model=model,
                    timeout=timeout,
                    permission_mode=permission_mode,
                    artifact_paths=resolved_artifact_paths,
                    permission_escalation=True,
                    allow_text_fallback=allow_text_fallback,
                    add_dirs=retry_add_dirs,
                    poll_interval=poll_interval,
                    exit_grace_seconds=exit_grace_seconds,
                    transport=transport,
                    bg_runner_script=bg_runner_script,
                    teardown_on_needs_human=teardown_on_needs_human,
                    resume=resume,
                    answer_file=answer_file,
                )
                combined_stderr = retry_note
                if retry_result.stderr:
                    combined_stderr = f"{retry_note}\n{retry_result.stderr}"
                return replace(retry_result, stderr=combined_stderr)
            return RunResult(
                exit_code=1,
                handoff_state="missing",
                result_kind="invocation_error",
                source=None,
                stdout="",
                stderr=str(exc),
            )
    default_add_dirs = [
        resolve_path(cwd, "."),
        resolved_quest_dir,
        resolved_prompt_file.parent,
        resolved_handoff_file.parent,
    ]
    default_add_dirs.extend(path.parent for path in local_artifact_paths)
    if add_dirs:
        default_add_dirs.extend(add_dirs)
    try:
        if transport == "background-agent":
            cmd = build_bg_cmd(
                cwd=cwd,
                bg_runner_script=bg_runner_script,
                prompt_file=resolved_prompt_file,
                name=bg_session_name(resolved_quest_dir.name, agent, iteration),
                model=model,
                timeout=timeout,
                permission_mode=_effective_permission_mode(
                    permission_mode, permission_escalation
                ),
                handoff_file=resolved_handoff_file,
                wait_for=[resolved_handoff_file, *resolved_artifact_paths],
                add_dirs=default_add_dirs,
                teardown_on_needs_human=teardown_on_needs_human,
                resume=resume,
                answer_file=resolve_path(cwd, answer_file) if answer_file else None,
            )
        else:
            cmd = build_bridge_cmd(
                cwd=cwd,
                bridge_script=bridge_script,
                prompt_file=resolved_prompt_file,
                model=model,
                timeout=timeout,
                permission_mode=_effective_permission_mode(
                    permission_mode, permission_escalation
                ),
                add_dirs=default_add_dirs,
            )
    except ValueError as exc:
        # e.g. an empty models.<role> value reaching normalize_claude_cli_model:
        # library callers get a structured invocation_error, never a traceback.
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=str(exc),
        )
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.monotonic() + timeout + 5.0
    handoff_state = "missing"
    stdout = ""
    stderr = ""
    timed_out = False

    if transport == "background-agent":
        # The child (claude_bg_run.py) owns confirm -> wait -> teardown and exits
        # with a meaningful code (ok / needs_human / timeout / bg error). Killing
        # the child does NOT stop the detached supervisor session, so we must not
        # race it the way we poll-and-kill the bridge. Wait for it to finish (its
        # own --timeout plus a teardown margin), then classify from the handoff +
        # exit code below. Only a pathological overrun terminates it as a last
        # resort.
        try:
            stdout, stderr = process.communicate(
                timeout=timeout + _BG_TEARDOWN_MARGIN_SECONDS
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=exit_grace_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            # Killing the child does NOT stop the detached supervisor session,
            # and the killed child never finished its own teardown — sweep the
            # session by name so the overrun cannot leak it. An incomplete
            # sweep must be REPORTED, not discarded: a bare `timeout` with no
            # recovery guidance is exactly the silent-leak the sweep prevents.
            session_name = bg_session_name(resolved_quest_dir.name, agent, iteration)
            sweep_warning = (
                f"WARNING: overrun cleanup incomplete; a background session may "
                f"still be live — stop it manually: python3 {bg_runner_script} "
                f"--sweep {session_name} --sweep-include-active"
            )
            try:
                sweep_cp = subprocess.run(
                    [
                        sys.executable,
                        str(bg_runner_script),
                        "--sweep",
                        session_name,
                        # our own overrunning session: active rows included
                        "--sweep-include-active",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60.0,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                stderr = f"{stderr}\n{sweep_warning}".strip()
            else:
                if sweep_left_survivor(sweep_cp.returncode, sweep_cp.stdout):
                    stderr = f"{stderr}\n{sweep_warning}".strip()
    else:
        while time.monotonic() < deadline:
            handoff_state = classify_handoff_file(resolved_handoff_file)
            artifacts_complete = (
                not resolved_artifact_paths
                or not any_artifact_missing_or_empty(resolved_artifact_paths)
            )
            if handoff_state == "found" and artifacts_complete:
                try:
                    stdout, stderr = process.communicate(timeout=exit_grace_seconds)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=exit_grace_seconds)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                append_context_health_log(
                    resolved_quest_dir,
                    phase=phase,
                    agent=agent,
                    iteration=iteration,
                    handoff_state=handoff_state,
                    source="handoff_json",
                    status=read_handoff_status(resolved_handoff_file),
                    transport=transport,
                )
                return RunResult(
                    exit_code=0,
                    handoff_state=handoff_state,
                    result_kind="handoff_json",
                    source="handoff_json",
                    stdout=stdout,
                    stderr=stderr,
                )
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                break
            time.sleep(poll_interval)

        if process.poll() is None:
            timed_out = True
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=exit_grace_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()

    handoff_state = classify_handoff_file(resolved_handoff_file)
    handoff_status = read_handoff_status(resolved_handoff_file)
    text_handoff = extract_text_handoff(stdout)
    artifacts_complete = (
        not resolved_artifact_paths
        or not any_artifact_missing_or_empty(resolved_artifact_paths)
    )
    # A found handoff whose status is a terminal state the role legitimately
    # reaches WITHOUT writing primary artifacts (needs_human asks for a decision;
    # blocked gives up) is a real handoff result, not a missing-artifact failure.
    # Treat it as one so the orchestrator enters the human path instead of
    # retrying/falling back, and so the status= health-log line is recorded.
    handoff_terminal_without_artifacts = (
        handoff_state == "found" and handoff_status in {"needs_human", "blocked"}
    )
    handoff_result = handoff_state == "found" and (
        artifacts_complete or handoff_terminal_without_artifacts
    )

    if transport == "background-agent" and (process.returncode or 0) != 0:
        # Surface the bg runner's envelope diagnostics (status/message/logs_tail)
        # so a failed dispatch is debuggable from RunResult.stderr alone.
        detail = _bg_failure_detail(stdout)
        if detail:
            stderr = f"{stderr}\n{detail}".strip()

    bg_fields = (
        _run_result_fields_from_bg(stdout)
        if transport == "background-agent"
        else {}
    )
    bg_status_kind = _BG_STATUS_RESULT_KINDS.get(str(bg_fields.get("status") or ""))
    # A found handoff only wins when the bg child actually succeeded (exit 0)
    # or intentionally parked (exit 10, needs_human). Any other terminal bg
    # failure — rate_limited/model_rejected/startup_dialog, but equally
    # dispatch_failed/precondition_failed/timeout — must outrank the handoff:
    # a failed resume deliberately RESTORES the parked needs_human handoff,
    # and letting that stale handoff win would report success, re-ask the
    # human their already-answered question, and bury the real failure.
    bg_failed = transport == "background-agent" and (process.returncode or 0) not in (0, 10)
    if bg_failed:
        handoff_result = False
    bg_exit_kind = (
        _BG_EXIT_RESULT_KINDS.get(process.returncode or 0)
        if transport == "background-agent"
        else None
    )
    # Precedence, explicit and in order. Terminal bg kinds come BEFORE
    # handoff_missing: a restored parked handoff with missing artifacts must
    # not relabel a rate_limited/dispatch_failed run. Exit 6 (incomplete) and
    # 130 stay unmapped so the ordinary missing-artifact flow still reaches
    # handoff_missing.
    if handoff_result:
        result_kind = "handoff_json"
    elif timed_out:
        result_kind = "timeout"
    elif bg_status_kind or bg_exit_kind:
        result_kind = bg_status_kind or bg_exit_kind
    elif handoff_state == "found" and not artifacts_complete:
        result_kind = "handoff_missing"
    else:
        # On a failed bg run (exit not 0/10) the generic classifier must never
        # see handoff_state="found": that back door would re-grant handoff_json
        # to e.g. exit 130 with a restored handoff, violating the
        # only-wins-on-0/10 invariant.
        result_kind = classify_result_kind(
            process.returncode or 1,
            stderr,
            "missing" if (bg_failed and handoff_state == "found") else handoff_state,
        )
    source = "handoff_json" if handoff_result else None
    exit_code = 0 if handoff_result else process.returncode or 1
    result = RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=result_kind,
        source=source,
        stdout=stdout,
        stderr=stderr,
        **bg_fields,
    )

    if (
        not permission_escalation
        and resolved_artifact_paths
        and result.source != "handoff_json"
    ):
        failure_kind = classify_failure_kind(
            result,
            resolved_artifact_paths,
            workspace_root,
        )
        if failure_kind in {"write_boundary", "permission"}:
            retry_add_dirs = list(add_dirs or [])
            retry_add_dirs.extend(
                _retry_artifact_dirs(resolved_artifact_paths, workspace_root)
            )
            retry_note = (
                f"Tier B retry: agent={agent} phase={phase} "
                f"failure_kind={failure_kind} permission_escalation=True"
            )
            retry_result = run_claude_role(
                cwd=cwd,
                quest_dir=resolved_quest_dir,
                phase=phase,
                agent=agent,
                iteration=iteration,
                prompt_file=resolved_prompt_file,
                handoff_file=resolved_handoff_file,
                bridge_script=bridge_script,
                model=model,
                timeout=timeout,
                permission_mode=permission_mode,
                artifact_paths=resolved_artifact_paths,
                permission_escalation=True,
                allow_text_fallback=allow_text_fallback,
                add_dirs=retry_add_dirs,
                poll_interval=poll_interval,
                exit_grace_seconds=exit_grace_seconds,
                transport=transport,
                bg_runner_script=bg_runner_script,
                teardown_on_needs_human=teardown_on_needs_human,
                resume=resume,
                answer_file=answer_file,
            )
            combined_stderr = retry_note
            if retry_result.stderr:
                combined_stderr = f"{retry_note}\n{retry_result.stderr}"
            return replace(retry_result, stderr=combined_stderr)

    # Text fallback is a LAST resort for a bridge run with no structured
    # result. It must never override a found handoff (e.g. bridge needs_human
    # without artifacts — a real terminal result the orchestrator routes on)
    # nor stamp exit 0 over a failed bg run whose stdout happens to embed a
    # ---HANDOFF--- block via the envelope's logs_tail.
    if (
        allow_text_fallback
        and text_handoff is not None
        and result.source is None
        and not bg_failed
    ):
        append_context_health_log(
            resolved_quest_dir,
            phase=phase,
            agent=agent,
            iteration=iteration,
            handoff_state=handoff_state,
            source="text_fallback",
            status=extract_text_status(text_handoff),
            transport=transport,
        )
        return RunResult(
            exit_code=0,
            handoff_state=handoff_state,
            result_kind="text_fallback",
            source="text_fallback",
            stdout=stdout,
            stderr=stderr,
        )

    if result.source == "handoff_json":
        append_context_health_log(
            resolved_quest_dir,
            phase=phase,
            agent=agent,
            iteration=iteration,
            handoff_state=result.handoff_state,
            source="handoff_json",
            status=handoff_status,
            transport=transport,
        )

    return result


def _write_probe_prompt(
    prompt_file: Path, artifact_file: Path, handoff_file: Path
) -> None:
    prompt_file.write_text(
        "\n".join(
            [
                "Do not ask questions. Do not return needs_human.",
                f"Write exactly the text ok to {artifact_file}.",
                (
                    "Write this exact JSON to "
                    f"{handoff_file}: "
                    '{"status":"complete","artifacts":["'
                    f"{artifact_file}"
                    '"],"next":null,"summary":"probe ok"}'
                ),
                "Reply with exactly:",
                "---HANDOFF---",
                "STATUS: complete",
                f"ARTIFACTS: {artifact_file}",
                "NEXT: null",
                "SUMMARY: probe ok",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_bridge_probe(
    *,
    cwd: str | Path,
    quest_dir: str | Path,
    bridge_script: str | Path,
    model: str,
    timeout: float,
    permission_mode: str,
) -> RunResult:
    resolved_quest_dir = resolve_path(cwd, quest_dir)
    probe_dir = resolved_quest_dir / "logs" / "bridge_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = probe_dir / "probe_prompt.txt"
    artifact_file = probe_dir / "probe_artifact.txt"
    handoff_file = probe_dir / "probe_handoff.json"
    prepare_artifact_files([artifact_file, handoff_file])
    _write_probe_prompt(prompt_file, artifact_file, handoff_file)

    cmd = build_bridge_cmd(
        cwd=cwd,
        bridge_script=bridge_script,
        prompt_file=prompt_file,
        model=model,
        timeout=timeout,
        permission_mode=permission_mode,
        add_dirs=[
            resolve_path(cwd, "."),
            resolved_quest_dir,
            probe_dir,
        ],
    )
    cp = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )

    handoff_state = classify_handoff_file(handoff_file)
    # Same artifact contract as run_bg_probe: a handoff alone must not
    # cache/select the bridge on a machine that never proved the write.
    # Deliberately UNLIKE run_bg_probe, the exit code is NOT required: the
    # bridge wrapper may timeout-kill the process after the work completed
    # (handoff + artifact written), and its exit code is not a structured
    # contract the way claude_bg_run.py's envelope exit codes are — pinned by
    # test_run_bridge_probe_treats_found_handoff_as_success_even_on_nonzero_exit.
    artifact_present = not any_artifact_missing_or_empty([artifact_file])
    probe_ok = handoff_state == "found" and artifact_present
    source = "handoff_json" if probe_ok else None
    exit_code = 0 if probe_ok else cp.returncode or 1
    if probe_ok:
        result_kind = "handoff_json"
    elif handoff_state == "found" and not artifact_present:
        # Distinct from handoff_missing (handoff never written): the transport
        # responded, only the artifact write failed.
        result_kind = "artifact_missing"
    else:
        result_kind = classify_result_kind(exit_code, cp.stderr, handoff_state)
    return RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=result_kind,
        source=source,
        stdout=cp.stdout,
        stderr=cp.stderr,
    )


def run_bg_probe(
    *,
    cwd: str | Path,
    quest_dir: str | Path,
    bg_runner_script: str | Path = DEFAULT_BG_RUNNER_SCRIPT,
    model: str,
    timeout: float,
    permission_mode: str,
) -> RunResult:
    """Live background-agent probe: dispatch a trivial bg task end-to-end.

    Same artifact/handoff contract as run_bridge_probe, but through
    scripts/claude_bg_run.py — exercising dispatch confirmation, supervisor
    liveness, bypass acceptance, and a real file write in one shot.
    """
    resolved_quest_dir = resolve_path(cwd, quest_dir)
    probe_dir = resolved_quest_dir / "logs" / "bg_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = probe_dir / "probe_prompt.txt"
    artifact_file = probe_dir / "probe_artifact.txt"
    handoff_file = probe_dir / "probe_handoff.json"
    prepare_artifact_files([artifact_file, handoff_file])
    _write_probe_prompt(prompt_file, artifact_file, handoff_file)

    cmd = build_bg_cmd(
        cwd=cwd,
        bg_runner_script=bg_runner_script,
        prompt_file=prompt_file,
        name=f"quest-bg-probe-{resolved_quest_dir.name}",
        model=model,
        timeout=timeout,
        permission_mode=permission_mode,
        handoff_file=handoff_file,
        wait_for=[handoff_file, artifact_file],
        add_dirs=[
            resolve_path(cwd, "."),
            resolved_quest_dir,
            probe_dir,
        ],
        teardown_on_needs_human=True,
    )
    cp = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )

    handoff_state = classify_handoff_file(handoff_file)
    artifact_present = not any_artifact_missing_or_empty([artifact_file])
    # Success requires the FULL contract: the bg child reported ok (exit 0), the
    # handoff parsed, AND the declared artifact was actually written. A handoff
    # alone must not cache/select background-agent on a machine that never proved
    # the artifact write — claude_bg_run.py exits non-zero (e.g. incomplete) then.
    probe_ok = cp.returncode == 0 and handoff_state == "found" and artifact_present
    source = "handoff_json" if probe_ok else None
    exit_code = 0 if probe_ok else cp.returncode or 1
    stderr = cp.stderr
    if exit_code != 0:
        detail = _bg_failure_detail(cp.stdout)
        if detail:
            stderr = f"{stderr}\n{detail}".strip()
    # Structured envelope status is authoritative for the transport kinds;
    # the stderr classifier only covers legacy signals with no envelope.
    bg_status_kind = _BG_STATUS_RESULT_KINDS.get(
        str((_bg_envelope(cp.stdout) or {}).get("status") or "")
    )
    specific_failure = bg_status_kind or classify_bg_probe_failure(stderr)
    if probe_ok:
        result_kind = "handoff_json"
    elif handoff_state == "found" and not artifact_present:
        # Distinct from handoff_missing (handoff never written): the transport
        # responded, only the artifact write failed.
        result_kind = "artifact_missing"
    else:
        result_kind = specific_failure or _BG_EXIT_RESULT_KINDS.get(
            exit_code
        ) or classify_result_kind(exit_code, stderr, handoff_state)
    return RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=result_kind,
        source=source,
        stdout=cp.stdout,
        stderr=stderr,
    )
