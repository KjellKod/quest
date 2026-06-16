"""Quest Claude runtime helpers for host-aware dispatch and transport execution.

Codex-led Claude roles run through one of two transports, both invoked as
subprocesses speaking the same file contract (poll handoff.json + artifacts):
  * background-agent (default via "auto"): scripts/claude_bg_run.py —
    `claude --bg` sessions billed to the subscription pool.
  * bridge (fallback / forced API path): scripts/quest_claude_bridge.py —
    `claude --print`, works without the background-agent daemon.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
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
# Project state stays cwd-relative on purpose (it lives in the target repo).
DEFAULT_BG_CACHE_FILE = ".quest/cache/claude_bg_codex.json"

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
}


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
    cmd = [
        sys.executable,
        str(bridge_script),
        "--prompt-file",
        str(prompt_file),
        "--output-format",
        "text",
        "--model",
        model,
        "--timeout",
        str(timeout),
        "--permission-mode",
        permission_mode,
    ]
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
    wait_for: Iterable[str | Path],
    add_dirs: Iterable[str | Path] | None = None,
) -> list[str]:
    """argv for the background-agent transport (scripts/claude_bg_run.py).

    Deliberately NO --handoff-file: a needs_human handoff must behave exactly
    like the bridge path (handoff file present → session torn down → the
    orchestrator reads the status). Passing --handoff-file would leave the
    session alive on needs_human, which Quest has no resume loop to collect.
    The handoff path travels in wait_for instead.
    """
    cmd = [
        sys.executable,
        str(bg_runner_script),
        "--json",
        "--no-protocol",
        "--prompt-file",
        str(prompt_file),
        "--name",
        name,
        "--model",
        model,
        "--timeout",
        str(timeout),
        "--permission-mode",
        permission_mode,
    ]
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


def load_bg_transport_available(cache_path: str | Path) -> bool:
    """True when the preflight bg cache proves the background-agent transport.

    Honors the cache wrapper's own TTL (cached_at_epoch + ttl_seconds) because
    the standalone runner has no quest-start timestamp to enforce instead.
    """
    try:
        with Path(cache_path).open("r", encoding="utf-8") as handle:
            wrapper = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(wrapper, dict):
        return False
    payload = wrapper.get("payload")
    if not isinstance(payload, dict) or payload.get("available") is not True:
        return False
    cached_at_epoch = wrapper.get("cached_at_epoch")
    ttl_seconds = wrapper.get("ttl_seconds")
    if isinstance(cached_at_epoch, int) and isinstance(ttl_seconds, int):
        if time.time() > cached_at_epoch + ttl_seconds:
            return False
    return True


def resolve_claude_transport(
    transport: str,
    *,
    bg_cache_file: str | Path = DEFAULT_BG_CACHE_FILE,
) -> tuple[str, bool]:
    """Resolve a configured transport to (resolved, downgraded).

    "auto" → background-agent when the preflight bg cache proves it, else a
    DOWNGRADE to bridge (downgraded=True so callers can report it loudly).
    Forced values pass through unchanged (forced background-agent that cannot
    dispatch fails at run time — never silently bridges).
    """
    if transport == "background-agent":
        return "background-agent", False
    if transport == "bridge":
        return "bridge", False
    if transport == "auto":
        if load_bg_transport_available(bg_cache_file):
            return "background-agent", False
        return "bridge", True
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
    if result.result_kind == "invocation_error":
        return "invocation"

    _, external_paths = check_artifact_paths(artifact_paths, workspace_root)
    if external_paths and any_artifact_missing_or_empty(artifact_paths):
        return "write_boundary"

    if "permission denied" in result.stderr.lower():
        return "permission"

    if artifact_paths and not any_artifact_missing_or_empty(artifact_paths):
        return "model"

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
) -> RunResult:
    if transport not in {"bridge", "background-agent"}:
        raise ValueError(
            f"transport must be 'bridge' or 'background-agent' (got {transport!r})"
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
    if resolved_artifact_paths and not permission_escalation:
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
                )
                combined_stderr = retry_note
                if retry_result.stderr:
                    combined_stderr = f"{retry_note}\n{retry_result.stderr}"
                return RunResult(
                    exit_code=retry_result.exit_code,
                    handoff_state=retry_result.handoff_state,
                    result_kind=retry_result.result_kind,
                    source=retry_result.source,
                    stdout=retry_result.stdout,
                    stderr=combined_stderr,
                )
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
            wait_for=[resolved_handoff_file, *resolved_artifact_paths],
            add_dirs=default_add_dirs,
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
    text_handoff = extract_text_handoff(stdout)
    artifacts_complete = (
        not resolved_artifact_paths
        or not any_artifact_missing_or_empty(resolved_artifact_paths)
    )

    if transport == "background-agent" and (process.returncode or 0) != 0:
        # Surface the bg runner's envelope diagnostics (status/message/logs_tail)
        # so a failed dispatch is debuggable from RunResult.stderr alone.
        detail = _bg_failure_detail(stdout)
        if detail:
            stderr = f"{stderr}\n{detail}".strip()

    bg_exit_kind = (
        _BG_EXIT_RESULT_KINDS.get(process.returncode or 0)
        if transport == "background-agent"
        else None
    )
    result_kind = (
        "handoff_json"
        if handoff_state == "found" and artifacts_complete
        else (
            "timeout"
            if timed_out
            else (
                "handoff_missing"
                if handoff_state == "found" and not artifacts_complete
                else bg_exit_kind
                or classify_result_kind(
                    process.returncode or 1, stderr, handoff_state
                )
            )
        )
    )
    source = "handoff_json" if handoff_state == "found" and artifacts_complete else None
    exit_code = (
        0
        if handoff_state == "found" and artifacts_complete
        else process.returncode or 1
    )
    result = RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=result_kind,
        source=source,
        stdout=stdout,
        stderr=stderr,
    )

    if not permission_escalation and resolved_artifact_paths:
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
            )
            combined_stderr = retry_note
            if retry_result.stderr:
                combined_stderr = f"{retry_note}\n{retry_result.stderr}"
            return RunResult(
                exit_code=retry_result.exit_code,
                handoff_state=retry_result.handoff_state,
                result_kind=retry_result.result_kind,
                source=retry_result.source,
                stdout=retry_result.stdout,
                stderr=combined_stderr,
            )

    if allow_text_fallback and text_handoff is not None:
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
            status=read_handoff_status(resolved_handoff_file),
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
    source = "handoff_json" if handoff_state == "found" else None
    exit_code = 0 if handoff_state == "found" else cp.returncode or 1
    return RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=(
            "handoff_json"
            if handoff_state == "found"
            else classify_result_kind(exit_code, cp.stderr, handoff_state)
        ),
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
        wait_for=[handoff_file, artifact_file],
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
    source = "handoff_json" if handoff_state == "found" else None
    exit_code = 0 if handoff_state == "found" else cp.returncode or 1
    stderr = cp.stderr
    if exit_code != 0:
        detail = _bg_failure_detail(cp.stdout)
        if detail:
            stderr = f"{stderr}\n{detail}".strip()
    return RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=(
            "handoff_json"
            if handoff_state == "found"
            else _BG_EXIT_RESULT_KINDS.get(exit_code)
            or classify_result_kind(exit_code, stderr, handoff_state)
        ),
        source=source,
        stdout=cp.stdout,
        stderr=stderr,
    )
