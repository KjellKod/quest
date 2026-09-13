"""Small, noninteractive Codex CLI adapter for Claude-led delegation.

The CLI owns authentication and configuration. This module owns one attempt,
its process group, and validation of current-attempt output. No runtime fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Literal

from .artifacts import (
    ROLE_PHASE_ALIASES,
    any_artifact_missing_or_empty,
    expected_artifacts_for_role,
    is_workspace_local,
    prepare_artifact_files,
)
from .claude_runner import (
    append_context_health_log,
    classify_handoff_file,
    read_handoff_status,
)
from .orchestration import runtime_for_model, validate_codex_reasoning_effort
from .plan_iterations import PlanIterationError, verify_refinement
from .review_intelligence import validate_findings
from .state import StateError, load_state

AuthMode = Literal["cached", "api-key"]
AuthKind = Literal["chatgpt", "api-key", "unknown"]
REQUIRED_CAPABILITIES = (
    "--json",
    "--cd",
    "--sandbox",
    "--model",
    "--config",
    "--add-dir",
    "--output-last-message",
    "--skip-git-repo-check",
)
NEXT_BY_ROLE: dict[str, tuple[str | None, ...]] = {
    "planner": ("plan_review",),
    "plan-reviewer-a": ("arbiter",),
    "plan-reviewer-b": ("arbiter",),
    "arbiter": ("planner", "builder"),
    "builder": ("code_review",),
    "fixer": ("code_review",),
    "code-reviewer-a": ("fixer", None),
    "code-reviewer-b": ("fixer", None),
    "review-arbiter": ("fixer", None),
}


class CodexError(Exception):
    """An actionable, nonsecret failure. Never include raw CLI diagnostics."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True)
class Credentials:
    mode: AuthMode
    kind: AuthKind
    environment: dict[str, str] = field(repr=False)


@dataclass
class CodexResult:
    result_kind: str
    exit_code: int = 1
    runtime: str = "codex"
    entrypoint: str = "scripts/quest_codex_runner.py"
    requested_model: str | None = None
    requested_effort: str | None = None
    effective_model: str | None = None
    effective_effort: str | None = None
    auth_mode: str = "cached"
    auth_kind: str = "unknown"
    attempt_dir: str | None = None
    session_id: str | None = None
    cleanup: str = "not_started"
    retry_eligible: bool = False
    disabled_self_servers: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    message: str = ""

    def payload(self) -> dict[str, object]:
        return asdict(self)


def _bounded_cli(
    executable: str, args: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    timeout = 10.0
    if args == ["login", "status"]:
        try:
            timeout = float(env.get("QUEST_CODEX_LOGIN_TIMEOUT_SECONDS", "10"))
        except ValueError as exc:
            raise CodexError(
                "precondition_failed", "Login timeout must be a finite positive number."
            ) from exc
        if not math.isfinite(timeout) or timeout <= 0:
            raise CodexError(
                "precondition_failed", "Login timeout must be a finite positive number."
            )
    try:
        return subprocess.run(
            [executable, *args],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CodexError(
            "precondition_failed",
            "CLI setup check timed out; retry the selected auth mode.",
        ) from exc
    except OSError as exc:
        raise CodexError(
            "missing_cli", "Install Codex CLI and ensure its executable is on PATH."
        ) from exc


def resolve_credentials(executable: str, cwd: Path, mode: AuthMode) -> Credentials:
    env = dict(os.environ)
    if mode == "api-key":
        key = env.get("CODEX_API_KEY") or env.get("OPENAI_API_KEY")
        if not key:
            raise CodexError(
                "auth_failed",
                "Explicit API-key mode requires CODEX_API_KEY or OPENAI_API_KEY in the environment.",
            )
        env["CODEX_API_KEY"] = key
        env.pop("OPENAI_API_KEY", None)
        return Credentials(mode, "api-key", env)
    if mode != "cached":
        raise CodexError("precondition_failed", "Auth mode must be cached or api-key.")
    env.pop("CODEX_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    login = _bounded_cli(executable, ["login", "status"], cwd, env)
    status = (login.stdout + login.stderr).lower()
    if login.returncode != 0:
        raise CodexError(
            "auth_failed",
            "Cached login unavailable. Run codex login, then codex login status.",
        )
    if "chatgpt" in status:
        return Credentials(mode, "chatgpt", env)
    if "api key" in status or "api-key" in status:
        return Credentials(mode, "api-key", env)
    raise CodexError(
        "auth_failed",
        "Cached identity kind is unknown; verify codex login status explicitly.",
    )


def probe_codex(cwd: str | Path, auth: AuthMode = "cached") -> dict[str, object]:
    """Setup readiness only, never inference or MCP registration health."""
    root = Path(cwd).resolve()
    executable = shutil.which("codex")
    checks: dict[str, object] = {
        "codex_cli_installed": executable is not None,
        "codex_exec_supported": False,
        "codex_runner_available": True,
        "codex_auth_mode": auth,
        "codex_auth_ready": False,
        "codex_auth_kind": "unknown",
        "codex_auth_reason": "not_checked" if executable else "missing_cli",
    }
    warnings: list[str] = []
    try:
        if auth not in ("cached", "api-key"):
            raise CodexError(
                "precondition_failed", "Auth mode must be cached or api-key."
            )
        if executable is None:
            raise CodexError(
                "missing_cli", "Install Codex CLI and ensure its executable is on PATH."
            )
        if not root.is_dir():
            raise CodexError(
                "precondition_failed", "Target cwd must be an existing directory."
            )
        help_result = _bounded_cli(
            executable, ["exec", "--help"], root, dict(os.environ)
        )
        checks["codex_exec_supported"] = help_result.returncode == 0 and all(
            flag in help_result.stdout for flag in REQUIRED_CAPABILITIES
        )
        if not checks["codex_exec_supported"]:
            warnings.append(
                "Installed Codex lacks required exec capabilities; update the CLI."
            )
        credentials = resolve_credentials(executable, root, auth)
        checks["codex_auth_ready"] = True
        checks["codex_auth_kind"] = credentials.kind
        checks["codex_auth_reason"] = (
            "key_present" if auth == "api-key" else "authenticated"
        )
    except CodexError as exc:
        warnings.append(str(exc))
        if exc.kind == "auth_failed":
            checks["codex_auth_reason"] = (
                "missing_key" if auth == "api-key" else "unauthenticated"
            )
        elif "timed out" in str(exc):
            checks["codex_auth_reason"] = "timeout"
    return {
        "available": all(
            checks[key] is True
            for key in (
                "codex_cli_installed",
                "codex_exec_supported",
                "codex_runner_available",
                "codex_auth_ready",
            )
        ),
        "inference_verified": False,
        "checks": checks,
        "warnings": warnings,
    }


def disabled_self_servers(
    executable: str, cwd: Path, credentials: Credentials
) -> list[str]:
    inventory = _bounded_cli(
        executable, ["mcp", "list", "--json"], cwd, credentials.environment
    )
    try:
        entries = json.loads(inventory.stdout)
        if inventory.returncode != 0 or not isinstance(entries, list):
            raise ValueError
        disabled = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise ValueError
            transport = entry.get("transport")
            if not isinstance(transport, dict):
                raise ValueError
            if transport.get("type") != "stdio":
                if transport.get("type") != "streamable_http":
                    raise ValueError
                continue
            command, args = transport.get("command"), transport.get("args")
            if (
                not isinstance(command, str)
                or not isinstance(args, list)
                or not all(isinstance(a, str) for a in args)
            ):
                raise ValueError
            binary = Path(command).name
            legacy = binary == "codex" and "mcp-server" in args
            shim = binary == "codex-mcp-server" or (
                binary in {"npx", "npm", "pnpm", "bun", "bunx"}
                and any(
                    re.fullmatch(r"codex-mcp-server(?:@[^/]+)?", arg) for arg in args
                )
            )
            if legacy or shim:
                disabled.append(entry["name"])
        return disabled
    except (ValueError, TypeError) as exc:
        raise CodexError(
            "precondition_failed",
            "Cannot inspect Codex MCP inventory. Repair codex mcp list --json before dispatch; no tools were blanket-disabled.",
        ) from exc


def build_codex_command(
    executable: str,
    *,
    cwd: Path,
    model: str | None,
    effort: str | None,
    sandbox: str,
    credentials: Credentials,
    final_path: Path,
    add_dirs: list[Path],
    allow_non_git: bool,
    disabled: list[str],
) -> list[str]:
    command = [
        executable,
        "-a",
        "never",
        "exec",
        "--json",
        "--cd",
        str(cwd),
        "--sandbox",
        sandbox,
    ]
    if model is not None:
        command += ["-m", model]
    if effort is not None:
        command += ["-c", "model_reasoning_effort=" + json.dumps(effort)]
    method = "chatgpt" if credentials.kind == "chatgpt" else "api"
    command += ["-c", "forced_login_method=" + json.dumps(method)]
    if disabled:
        # CLI override keys split on dots without TOML quoting. The table value
        # is parsed as TOML and deep-merged, preserving transports and other tools.
        overrides = ",".join(
            json.dumps(name, ensure_ascii=False) + "={enabled=false}"
            for name in disabled
        )
        command += ["-c", "mcp_servers={" + overrides + "}"]
    for directory in add_dirs:
        command += ["--add-dir", str(directory)]
    if allow_non_git:
        command.append("--skip-git-repo-check")
    return command + ["-o", str(final_path), "-"]


def _group_live(pgid: int) -> bool:
    """POSIX group liveness, excluding zombies that can no longer edit files."""
    try:
        result = subprocess.run(
            ["ps", "-A", "-o", "pgid=,stat="], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if result.returncode:
        return True
    for line in result.stdout.splitlines():
        fields = line.split()
        if (
            len(fields) >= 2
            and fields[0] == str(pgid)
            and not fields[1].startswith("Z")
        ):
            return True
    return False


def terminate_group(process: subprocess.Popen[str]) -> bool:
    """Reap the direct child and remove all live descendants, even after exit 0."""
    for sig, grace in ((signal.SIGTERM, 0.5), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        until = time.monotonic() + grace
        while time.monotonic() < until:
            process.poll()
            if not _group_live(process.pid):
                try:
                    process.wait(timeout=1)
                    return True
                except subprocess.TimeoutExpired:
                    break
            time.sleep(0.03)
    return False


def _failure_kind(text: str) -> str | None:
    diagnostic = text[:32768].lower()
    for kind, phrases in (
        (
            "auth_failed",
            (
                "auth_failed",
                "unauthorized",
                "invalid_api_key",
                "incorrect api key",
                "authentication",
                "forced login method",
                "forced_login_method",
            ),
        ),
        (
            "model_rejected",
            (
                "model_rejected",
                "model_not_found",
                "unsupported model",
                "model is not supported",
                "model does not exist",
            ),
        ),
        (
            "rate_limited",
            ("rate_limited", "rate_limit", "rate limit", "usage limit"),
        ),
    ):
        if any(phrase in diagnostic for phrase in phrases):
            return kind
    status = re.search(
        r"\b(?:http|status|error)(?:\s+code)?[\s:]+(401|429)\b", diagnostic
    )
    if status:
        return "auth_failed" if status[1] == "401" else "rate_limited"
    return None


def validate_codex_result(
    events_path: Path, final_path: Path, returncode: int, stderr_path: Path
) -> tuple[str, str | None]:
    completed = failed = malformed = False
    session_id = None
    failure = None
    with events_path.open(encoding="utf-8", errors="replace") as events:
        for line in events:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(
                    event.get("type"), str
                ):
                    raise ValueError
                event_type = event["type"]
                if event_type == "thread.started":
                    if (
                        not isinstance(event.get("thread_id"), str)
                        or not event["thread_id"]
                    ):
                        raise ValueError
                    session_id = event["thread_id"]
                elif event_type == "turn.completed":
                    usage = event.get("usage")
                    if not isinstance(usage, dict) or any(
                        type(usage.get(key)) is not int or usage[key] < 0
                        for key in ("input_tokens", "output_tokens")
                    ):
                        raise ValueError
                    completed = True
                elif event_type in ("turn.failed", "error"):
                    failed = True
                    failure = _failure_kind(json.dumps(event)) or failure
            except ValueError:
                malformed = True
    if returncode != 0 or failed:
        with stderr_path.open(encoding="utf-8", errors="replace") as errors:
            failure = failure or _failure_kind(errors.read(32768))
    if failure:
        return failure, session_id
    if returncode != 0 or failed:
        return "invocation_error", session_id
    try:
        final_present = final_path.is_file() and bool(
            final_path.read_text(encoding="utf-8").strip()
        )
    except (OSError, UnicodeError):
        final_present = False
    if malformed or not completed or session_id is None or not final_present:
        return "malformed_output", session_id
    return "complete", session_id


def _write_receipt(result: CodexResult) -> None:
    if result.attempt_dir:
        try:
            (Path(result.attempt_dir) / "receipt.json").write_text(
                json.dumps(result.payload(), indent=2) + "\n", encoding="utf-8"
            )
        except (OSError, UnicodeError):
            if result.result_kind == "complete":
                result.result_kind = "invocation_error"
            result.exit_code = 1
            result.retry_eligible = False
            result.message = "Cannot write Codex attempt receipt; execution may already have occurred."


def run_codex(
    *,
    cwd: str | Path,
    output_dir: str | Path,
    prompt: str,
    auth: AuthMode = "cached",
    model: str | None = None,
    effort: str | None = None,
    sandbox: str = "workspace-write",
    timeout: float = 1800,
    allow_non_git: bool = False,
    agent: str = "task",
    iteration: int = 1,
    artifact_roots: tuple[Path, ...] = (),
) -> CodexResult:
    result = CodexResult(
        "precondition_failed",
        requested_model=model,
        requested_effort=effort,
        auth_mode=auth,
    )
    try:
        root = Path(cwd).resolve()
        if (
            os.name != "posix"
            or not root.is_dir()
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise CodexError(
                "precondition_failed",
                "Requires POSIX, an existing cwd and a finite positive timeout.",
            )
        if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
            raise CodexError("precondition_failed", "Invalid sandbox selection.")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", agent) or iteration < 0:
            raise CodexError("precondition_failed", "Invalid agent or iteration.")
        if model is not None and (
            not model.strip()
            or model != model.strip()
            or runtime_for_model(model) != "codex"
        ):
            raise CodexError(
                "precondition_failed", "The selected model is not a Codex model."
            )
        if effort is not None:
            validate_codex_reasoning_effort(effort)
        if not allow_non_git:
            git = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                capture_output=True,
                timeout=10,
            )
            if git.returncode:
                raise CodexError(
                    "precondition_failed",
                    "Non-Git execution requires explicit --allow-non-git.",
                )
        executable = shutil.which("codex")
        if executable is None:
            raise CodexError(
                "missing_cli", "Install Codex CLI and ensure its executable is on PATH."
            )
        help_result = _bounded_cli(
            executable, ["exec", "--help"], root, dict(os.environ)
        )
        if help_result.returncode or not all(
            flag in help_result.stdout for flag in REQUIRED_CAPABILITIES
        ):
            raise CodexError(
                "precondition_failed",
                "Installed Codex lacks required exec capabilities; update the CLI.",
            )
        credentials = resolve_credentials(executable, root, auth)
        result.auth_kind = credentials.kind
        disabled = disabled_self_servers(executable, root, credentials)
        result.disabled_self_servers = disabled
        base = Path(output_dir).resolve() / agent / f"iter-{iteration}"
        base.mkdir(parents=True, exist_ok=True)
        attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=base))
        result.attempt_dir = str(attempt)
        final, events, errors = (
            attempt / name for name in ("final.txt", "events.jsonl", "stderr.txt")
        )
        additions = [
            directory
            for directory in dict.fromkeys(
                (Path(output_dir).resolve(), *artifact_roots)
            )
            if not is_workspace_local(directory, root)
        ]
        command = build_codex_command(
            executable,
            cwd=root,
            model=model,
            effort=effort,
            sandbox=sandbox,
            credentials=credentials,
            final_path=final,
            add_dirs=additions,
            allow_non_git=allow_non_git,
            disabled=disabled,
        )
        deadline = time.monotonic() + timeout
        with (
            events.open("w", encoding="utf-8") as stdout,
            errors.open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                command,
                cwd=root,
                env=credentials.environment,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                text=True,
                encoding="utf-8",
                start_new_session=True,
            )
            cancelled = False

            def cancel(signum: int, frame: object) -> None:
                raise KeyboardInterrupt

            previous = signal.signal(signal.SIGTERM, cancel)
            try:
                process.communicate(
                    prompt, timeout=max(0.001, deadline - time.monotonic())
                )
                result.result_kind = "complete"
            except subprocess.TimeoutExpired:
                result.result_kind = "timeout"
            except KeyboardInterrupt:
                cancelled = True
                result.result_kind = "cancelled"
            finally:
                # Further cancellation must not interrupt cleanup and orphan editors.
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                prior_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
                try:
                    clean = terminate_group(process)
                finally:
                    signal.signal(signal.SIGTERM, previous)
                    signal.signal(signal.SIGINT, prior_int)
                result.cleanup = "complete" if clean else "failed"
                if not clean:
                    result.result_kind = "teardown_failed"
        if result.result_kind == "complete" and not cancelled:
            result.result_kind, result.session_id = validate_codex_result(
                events, final, process.returncode, errors
            )
        result.artifacts = [str(events), str(final), str(errors)]
        result.exit_code = 0 if result.result_kind == "complete" else 1
        result.retry_eligible = result.cleanup == "complete" and result.result_kind in {
            "malformed_output",
            "artifact_missing",
        }
        result.message = (
            "Attempt validated."
            if result.exit_code == 0
            else "Codex attempt failed: "
            + result.result_kind
            + ". No settings or runtime were changed."
        )
    except CodexError as exc:
        result.result_kind, result.message = exc.kind, str(exc)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Filesystem/config errors may contain credential-bearing content; expose category only.
        result.result_kind = (
            "invocation_error" if result.attempt_dir else "precondition_failed"
        )
        result.exit_code = 1
        result.retry_eligible = False
        result.message = (
            "Codex setup/output error: "
            + type(exc).__name__
            + ". Check paths and selected settings."
        )
    _write_receipt(result)
    return result


def _validate_handoff(paths: list[Path], quest_dir: Path, cwd: Path, agent: str) -> str:
    handoff_path = next(path for path in paths if path.name.startswith("handoff"))
    if not handoff_path.is_file() or not handoff_path.stat().st_size:
        return "artifact_missing"
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        if not isinstance(handoff, dict) or handoff.get("status") not in {
            "complete",
            "blocked",
        }:
            return "malformed_output"
        if "next" not in handoff or handoff["next"] not in NEXT_BY_ROLE[agent]:
            return "malformed_output"
        declared = handoff.get("artifacts")
        if (
            not isinstance(declared, list)
            or not all(isinstance(p, str) and p for p in declared)
            or not isinstance(handoff.get("summary"), str)
            or not handoff["summary"].strip()
        ):
            return "malformed_output"
        if agent in {"planner", "plan-reviewer-a", "plan-reviewer-b", "arbiter"}:
            state = load_state(quest_dir)
            request = state.get("user_replan")
            generation = (
                request.get("generation") if isinstance(request, dict) else None
            )
            if (
                handoff.get("plan_iteration") != state.get("plan_iteration")
                or "user_replan_generation" not in handoff
                or handoff["user_replan_generation"] != generation
            ):
                return "malformed_output"
            if agent == "planner" and state["plan_iteration"] > 1:
                refinement = verify_refinement(quest_dir, state["plan_iteration"])
                if handoff.get("refinement_source_plan_iteration") != refinement.get(
                    "source_plan_iteration"
                ) or handoff.get("refinement_verdict_sha256") != refinement.get(
                    "verdict_sha256"
                ):
                    return "malformed_output"
        if handoff["status"] == "blocked":
            return "blocked"
        if any_artifact_missing_or_empty(paths):
            return "artifact_missing"
        resolved_declared = {
            (base / name).resolve() for name in declared for base in (cwd, quest_dir)
        }
        if any(
            path.resolve() not in resolved_declared
            for path in paths
            if path != handoff_path
        ):
            return "malformed_output"
        for path in paths:
            if "findings" in path.name and validate_findings(
                json.loads(path.read_text(encoding="utf-8"))
            ):
                return "malformed_output"
    except (ValueError, OSError, StateError, PlanIterationError):
        return "malformed_output"
    return "complete"


def run_codex_role(
    *,
    cwd: str | Path,
    quest_dir: str | Path,
    phase: str,
    agent: str,
    iteration: int,
    prompt: str,
    output_dir: str | Path | None = None,
    sandbox: str = "workspace-write",
    timeout: float = 1800,
    allow_non_git: bool = False,
    artifact_subset: str | None = None,
) -> CodexResult:
    root, quest = Path(cwd).resolve(), Path(quest_dir).resolve()
    result: CodexResult | None = None
    try:
        saved = json.loads((quest / "orchestration.json").read_text(encoding="utf-8"))
        model = saved["models"][agent]
        effort = saved.get("codex_reasoning_effort")
        auth = saved.get("codex_auth_mode", "cached")
        if (
            not isinstance(model, str)
            or runtime_for_model(model) != "codex"
            or auth not in {"cached", "api-key"}
        ):
            raise ValueError
        state = load_state(quest)
        state_phase = state.get("phase")
        if state_phase not in ROLE_PHASE_ALIASES[agent] and not (
            agent in {"plan-reviewer-a", "plan-reviewer-b", "arbiter"}
            and state_phase == "plan"
        ):
            raise CodexError(
                "precondition_failed", "Saved Quest phase does not authorize this role."
            )
        paths = expected_artifacts_for_role(
            quest, phase, agent, artifact_subset=artifact_subset
        )
        prepare_artifact_files(paths, quest_dir=quest, role=agent)
        result = run_codex(
            cwd=root,
            output_dir=output_dir or quest / "logs/codex",
            prompt=prompt,
            auth=auth,
            model=model,
            effort=effort,
            sandbox=sandbox,
            timeout=timeout,
            allow_non_git=allow_non_git,
            agent=agent,
            iteration=iteration,
            artifact_roots=(quest,),
        )
        if result.result_kind == "complete":
            result.result_kind = _validate_handoff(paths, quest, root, agent)
            result.exit_code = 0 if result.result_kind == "complete" else 1
            result.retry_eligible = result.result_kind in {
                "malformed_output",
                "artifact_missing",
            }
            result.message = (
                "Role artifacts validated."
                if result.exit_code == 0
                else "Role output rejected: " + result.result_kind
            )
        result.artifacts += [str(path) for path in paths]
        handoff_path = next(path for path in paths if path.name.startswith("handoff"))
        append_context_health_log(
            quest,
            phase=phase,
            agent=agent,
            iteration=iteration,
            handoff_state=classify_handoff_file(handoff_path),
            source=(
                "handoff_json"
                if result.result_kind in {"complete", "blocked"}
                else "none"
            ),
            status=(
                read_handoff_status(handoff_path)
                if result.result_kind in {"complete", "blocked"}
                else None
            ),
            runtime="codex",
        )
        _write_receipt(result)
        return result
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        StateError,
        PlanIterationError,
        CodexError,
    ):
        if result is not None:
            if result.result_kind == "complete":
                result.result_kind = "invocation_error"
            result.exit_code = 1
            result.retry_eligible = False
            result.message = (
                "Codex role output/log error; execution may already have occurred."
            )
            _write_receipt(result)
            return result
        return CodexResult(
            "precondition_failed",
            message="Saved role settings, phase or planner lifecycle precondition failed; no fallback dispatched.",
        )
