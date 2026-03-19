"""Quest Claude runtime helpers for host-aware dispatch and bridge execution."""

from __future__ import annotations

import json
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

    This preserves native Claude execution for Claude-led quests and activates the
    bridge-backed Claude runner only for Codex-led Claude-designated roles.
    """

    normalized_orchestrator = orchestrator.strip().lower()
    normalized_target = target_runtime.strip().lower()

    if normalized_target == "codex":
        return RuntimeSelection(
            runtime="codex",
            entrypoint="mcp__codex-cli__codex",
            reason="Codex-designated role stays on Codex tooling.",
            requires_probe=False,
        )

    if normalized_target != "claude":
        raise ValueError(f"Unsupported target runtime: {target_runtime}")

    if normalized_orchestrator == "codex":
        if claude_bridge_available:
            return RuntimeSelection(
                runtime="claude",
                entrypoint="scripts/quest_claude_runner.py",
                reason="Codex-led Claude role uses the additive bridge-backed Quest runner.",
                requires_probe=True,
            )
        return RuntimeSelection(
            runtime="blocked",
            entrypoint="",
            reason=(
                "Codex-led Claude role requires the Quest Claude bridge runner, "
                "but the bridge probe is unavailable."
            ),
            requires_probe=True,
        )

    if native_claude_available:
        return RuntimeSelection(
            runtime="claude",
            entrypoint="Task(...)",
            reason="Claude-led or native-Claude host keeps native Claude task execution.",
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


def classify_handoff_file(path: str | Path) -> str:
    handoff_path = Path(path)
    if not handoff_path.exists():
        return "missing"
    try:
        json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unparsable"
    return "found"


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
) -> None:
    log_dir = Path(quest_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_line = (
        f"{utc_now_iso()} | phase={phase} | agent={agent} | runtime=claude | "
        f"iter={iteration} | handoff_json={handoff_state} | source={source}\n"
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
) -> RunResult:
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

    result_kind = (
        "handoff_json"
        if handoff_state == "found" and artifacts_complete
        else (
            "timeout"
            if timed_out
            else (
                "handoff_missing"
                if handoff_state == "found" and not artifacts_complete
                else classify_result_kind(
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
        )

    return result


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
