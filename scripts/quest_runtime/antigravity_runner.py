"""Quest Antigravity runtime helpers.

Gemini-designated Quest roles run on the Antigravity CLI (`agy`) as a plain
subprocess speaking the same file contract as every other Quest runtime: poll
`handoff.json` plus the role's declared artifacts. There is no MCP server and
no transport choice — `agy --print` is the only path, which is why this module
is much smaller than its Claude counterpart.

Behaviour below is pinned to `agy 1.1.10` and was measured, not read off the
docs. Three published claims did not hold:

  * The prompt cannot be delivered on stdin. Piping into `agy -p` runs an
    *empty* prompt. The prompt must be the `-p` flag value, on argv.
  * Errors are reported on **stdout** inside the JSON envelope
    (`{"status": "ERROR", "error": ...}`), not on stderr. stderr came back
    empty for a rejected model, so classification must read the envelope.
  * `--model` with an unrecognised slug does exit non-zero (1), which is what
    lets a rejected model map onto Quest's existing `model_rejected` kind.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Iterable

from quest_runtime.artifacts import (
    any_artifact_missing_or_empty,
    prepare_artifact_files,
)
from quest_runtime.claude_runner import (
    RunResult,
    append_context_health_log,
    classify_handoff_file,
    extract_text_handoff,
    extract_text_status,
    read_handoff_status,
    resolve_path,
    unique_dirs,
)

DEFAULT_AGY_BINARY = "agy"

# `agy` has no --prompt-file, so the whole role prompt travels on argv. Guard
# it rather than letting exec() fail with a bare E2BIG that surfaces as an
# unexplained invocation error. macOS allows ~1MB total / 256KB per argument;
# this leaves generous headroom for the rest of the command line. Counted in
# UTF-8 bytes because the OS limit is a byte limit, not a character one.
MAX_PROMPT_ARGV_BYTES = 100_000

# Roles that only ever write their own review/verdict artifacts under
# `.quest/**`, never source. They are dispatched in `--mode plan`.
#
# WARNING — `--mode plan` is NOT a write barrier. Measured on agy 1.1.10: in
# plan mode agy still writes files that fall inside `--add-dir` scope. The
# ONLY containment boundary is `--add-dir`, which the caller supplies. Plan
# mode changes the agent's posture, not its permissions; do not describe it
# as the read-only guarantee.
#
# Worse, when a requested path is OUTSIDE --add-dir scope, agy does not
# refuse: it silently redirects the write to ~/.gemini/antigravity-cli/scratch/
# and still reports status=SUCCESS. For Quest that means a mis-scoped role
# looks like it succeeded while its artifacts landed outside the quest dir,
# and only the handoff check catches it (as handoff_missing).
READ_ONLY_ROLES = frozenset(
    {
        "plan-reviewer-a",
        "plan-reviewer-b",
        "arbiter",
        "code-reviewer-a",
        "code-reviewer-b",
        "review-arbiter",
    }
)

AGY_MODE_READ_ONLY = "plan"
AGY_MODE_WRITE = "accept-edits"

# Handoff statuses that legitimately carry no finished artifacts. A role that
# stopped to ask a question or reported a blocker did its job; requiring
# artifacts from it would route a terminal outcome into the failure path.
TERMINAL_STATUSES_WITHOUT_ARTIFACTS = frozenset({"needs_human", "blocked"})

# Upper bound for --timeout. Anything beyond this is a config error rather
# than an intent, and rejecting it early keeps absurd values away from the
# subprocess and from agy's own --print-timeout parsing.
MAX_TIMEOUT_SECONDS = 2_147_483_647

# The bare `gemini` sentinel means "let agy choose its own default model", so
# the runner omits --model entirely. Mirrors the `claude` sentinel.
AGY_DEFAULT_MODEL_SENTINEL = "gemini"


def positive_finite_timeout(value: str) -> float:
    """Parse a --timeout argument, rejecting values a subprocess cannot use.

    Shared by both CLI entrypoints so the policy cannot drift between them.
    `type=float` alone accepts "inf", which reaches int(timeout) in
    build_agy_cmd and crashes the process instead of returning the structured
    failure envelope callers parse.
    """
    parsed = float(value)
    if parsed != parsed or not 0 < parsed <= MAX_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError(
            "timeout must be a finite positive number of seconds "
            f"no greater than {MAX_TIMEOUT_SECONDS} (got {value!r})"
        )
    return parsed


def agy_mode_for_agent(agent: str) -> str:
    """Return the agy execution mode for a canonical Quest role name.

    This selects posture, not permissions. Containment comes from the
    `add_dirs` the caller passes — see the WARNING on READ_ONLY_ROLES.
    """
    return AGY_MODE_READ_ONLY if agent in READ_ONLY_ROLES else AGY_MODE_WRITE


def normalize_agy_cli_model(model: str) -> str | None:
    """Return the slug to pass as --model, or None to omit the flag.

    Slugs pass through verbatim and are never validated against a hardcoded
    list, so a newly released model (for example `gemini-3.5-pro-high`) works
    the day it ships. An unknown slug is rejected by agy itself, which is the
    behaviour `model_rejected` classification relies on.
    """
    normalized = model.strip()
    if not normalized:
        raise ValueError(
            "Antigravity model must be a non-empty value or the `gemini` sentinel"
        )
    if normalized == AGY_DEFAULT_MODEL_SENTINEL:
        return None
    return normalized


def build_agy_cmd(
    *,
    prompt: str,
    model: str,
    timeout: float,
    mode: str,
    add_dirs: Iterable[str | Path] | None = None,
    json_schema: str | Path | None = None,
    agy_binary: str = DEFAULT_AGY_BINARY,
) -> list[str]:
    """Build the `agy` argv for one role dispatch."""
    # Measured in UTF-8 bytes, not characters: the OS argv limit is a byte
    # limit, so a multibyte prompt could pass a character count and still fail
    # exec with a bare E2BIG that surfaces as an unexplained invocation error.
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > MAX_PROMPT_ARGV_BYTES:
        raise ValueError(
            f"prompt is {prompt_bytes} UTF-8 bytes, over the "
            f"{MAX_PROMPT_ARGV_BYTES}-byte argv limit for agy "
            "(it has no --prompt-file equivalent)"
        )
    cmd = [
        agy_binary,
        "--print",
        prompt,
        "--output-format",
        "json",
        # Role prompts are data, not a place to expand agy's own slash
        # commands or skills — that would let prompt content alter execution.
        "--disable-slash-commands",
        "--print-timeout",
        f"{int(timeout)}s",
        "--mode",
        mode,
    ]
    cli_model = normalize_agy_cli_model(model)
    if cli_model is not None:
        cmd.extend(["--model", cli_model])
    if json_schema is not None:
        cmd.extend(["--json-schema", str(json_schema)])
    for directory in unique_dirs(add_dirs or []):
        cmd.extend(["--add-dir", directory])
    return cmd


def check_containment(
    handoff_file: str | Path, add_dirs: Iterable[str | Path] | None
) -> str | None:
    """Return an error string when a dispatch would run without containment.

    `--add-dir` is agy's only write boundary (see READ_ONLY_ROLES). Dispatching
    with none of it, or with scoping that does not cover where the handoff must
    land, is never correct: agy does not refuse an out-of-scope write, it
    redirects it to its own scratch directory and still reports SUCCESS. The
    role then looks like it simply failed to write a handoff, which sends you
    debugging the model instead of the scoping. Fail loudly up front instead.
    """
    resolved_dirs = [Path(d).resolve() for d in add_dirs or []]
    if not resolved_dirs:
        return (
            "refusing to dispatch with no --add-dir: agy would redirect "
            "out-of-scope writes to its scratch directory and still report "
            "success, surfacing later as an unexplained missing handoff"
        )
    handoff_parent = Path(handoff_file).resolve().parent
    if not any(handoff_parent.is_relative_to(d) for d in resolved_dirs):
        return (
            f"refusing to dispatch: --add-dir scoping {[str(d) for d in resolved_dirs]} "
            f"does not cover the handoff directory {handoff_parent}, so the "
            "handoff write would be silently redirected out of the workspace"
        )
    return None


def parse_agy_envelope(stdout: str) -> dict | None:
    """Return agy's JSON envelope, or None when stdout is not a JSON object."""
    text = stdout.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def agy_error_text(envelope: dict | None) -> str:
    """Return the envelope's error string, or empty when there is none."""
    if not envelope:
        return ""
    error = envelope.get("error")
    return error if isinstance(error, str) else ""


def classify_agy_result_kind(
    *,
    exit_code: int,
    envelope: dict | None,
    handoff_state: str,
    stderr: str = "",
) -> str:
    """Classify one agy run into a Quest result kind.

    Deliberately does not reuse `classify_result_kind` from the Claude runner:
    that one inspects stderr, and agy reports failures on stdout inside the
    JSON envelope instead.
    """
    if handoff_state == "found":
        return "handoff_json"

    error_text = f"{agy_error_text(envelope)}\n{stderr}".lower()

    if (
        "invalid model selection" in error_text
        or "is not recognized as a" in error_text
    ):
        return "model_rejected"
    if (
        exit_code == 124
        or "timed out" in error_text
        or "deadline exceeded" in error_text
    ):
        return "timeout"
    if any(
        marker in error_text
        for marker in (
            "not found",
            "no such file",
            "not authenticated",
            "unauthenticated",
            "executable file not found",
        )
    ):
        return "invocation_error"
    if handoff_state == "unparsable":
        return "handoff_unparsable"
    if handoff_state == "missing":
        return "handoff_missing"
    return "error"


def rejected_model_for(model: str) -> str | None:
    """Return the concrete slug to report on a model rejection.

    The `gemini` sentinel does not name a model, so there is nothing truthful
    to report for it — mirrors the Claude runner's handling of `claude`.
    """
    normalized = model.strip()
    if not normalized or normalized == AGY_DEFAULT_MODEL_SENTINEL:
        return None
    return normalized


def run_antigravity_role(
    *,
    cwd: str | Path,
    quest_dir: str | Path,
    phase: str,
    agent: str,
    iteration: int,
    prompt_file: str | Path,
    handoff_file: str | Path,
    model: str,
    timeout: float,
    artifact_paths: Iterable[str | Path] | None = None,
    add_dirs: Iterable[str | Path] | None = None,
    json_schema: str | Path | None = None,
    allow_text_fallback: bool = True,
    agy_binary: str = DEFAULT_AGY_BINARY,
) -> RunResult:
    """Dispatch one Quest role to `agy` and resolve its handoff."""
    resolved_quest_dir = resolve_path(cwd, quest_dir)
    resolved_prompt_file = resolve_path(cwd, prompt_file)
    resolved_handoff_file = resolve_path(cwd, handoff_file)
    resolved_artifact_paths = [resolve_path(cwd, path) for path in artifact_paths or []]
    # Materialize once: add_dirs is typed Iterable, and a generator would be
    # drained by the containment check, leaving build_agy_cmd to dispatch with
    # no --add-dir at all — losing the very boundary we just validated.
    resolved_add_dirs = list(add_dirs or [])

    containment_error = check_containment(resolved_handoff_file, resolved_add_dirs)
    if containment_error:
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=containment_error,
        )

    try:
        prompt = resolved_prompt_file.read_text(encoding="utf-8")
    except OSError as exc:
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=f"could not read prompt file: {exc}",
        )

    if resolved_artifact_paths:
        try:
            prepare_artifact_files(resolved_artifact_paths)
        except OSError as exc:
            return RunResult(
                exit_code=1,
                handoff_state="missing",
                result_kind="invocation_error",
                source=None,
                stdout="",
                stderr=f"could not prepare artifact files: {exc}",
            )

    try:
        cmd = build_agy_cmd(
            prompt=prompt,
            model=model,
            timeout=timeout,
            mode=agy_mode_for_agent(agent),
            add_dirs=resolved_add_dirs,
            json_schema=json_schema,
            agy_binary=agy_binary,
        )
    except ValueError as exc:
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=str(exc),
        )

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(Path(cwd).resolve()),
            capture_output=True,
            text=True,
            # agy hangs in non-interactive use when stdin stays open
            # (antigravity-cli#76). Close it explicitly.
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except FileNotFoundError as exc:
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=f"agy executable not found: {exc}",
        )
    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout = ""
        stderr = f"agy timed out after {timeout}s"

    envelope = parse_agy_envelope(stdout)
    handoff_state = classify_handoff_file(resolved_handoff_file)
    source = "handoff_json" if handoff_state == "found" else None
    status = read_handoff_status(resolved_handoff_file) if source else None

    # Text fallback: agy completed but never wrote handoff.json. Recover a
    # ---HANDOFF--- block from the envelope's response so a finished role is
    # not thrown away over a missing file.
    if allow_text_fallback and handoff_state != "found" and envelope:
        response = envelope.get("response")
        if isinstance(response, str):
            text_handoff = extract_text_handoff(response)
            if text_handoff:
                handoff_state = "found"
                source = "text_fallback"
                status = extract_text_status(text_handoff)

    result_kind = classify_agy_result_kind(
        exit_code=exit_code,
        envelope=envelope,
        handoff_state=handoff_state,
        stderr=stderr,
    )

    # A handoff alone is not completion. Later Quest stages read the role's
    # declared artifacts, so accepting a handoff while those are missing or
    # still empty hands the next stage files with nothing in them. The Claude
    # runner requires the artifact write too; this keeps the contract uniform.
    # `needs_human` and `blocked` are legitimate terminal outcomes, not
    # failures: a role that stopped to ask a question or reported a blocker is
    # SUPPOSED to have no finished artifacts. Flagging those as
    # artifact_missing would route them into retry/failure instead of the
    # human/blocked path, burying the question the role actually asked.
    if (
        source
        and status not in TERMINAL_STATUSES_WITHOUT_ARTIFACTS
        and resolved_artifact_paths
        and any_artifact_missing_or_empty(resolved_artifact_paths)
    ):
        result_kind = "artifact_missing"
    elif source == "text_fallback":
        # Distinct kind so routing keyed on result_kind can tell a recovered
        # ---HANDOFF--- block apart from a real handoff.json on disk, matching
        # the Claude runner rather than reporting both as handoff_json.
        result_kind = "text_fallback"

    append_context_health_log(
        resolved_quest_dir,
        phase=phase,
        agent=agent,
        iteration=iteration,
        handoff_state=handoff_state,
        source=source or "none",
        status=status,
        runtime="antigravity",
    )

    return RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=result_kind,
        source=source,
        stdout=stdout,
        stderr=stderr or agy_error_text(envelope),
        status=status,
        rejected_model=(
            rejected_model_for(model) if result_kind == "model_rejected" else None
        ),
    )


def _write_probe_prompt(
    prompt_file: Path, artifact_file: Path, handoff_file: Path
) -> str:
    """Write and return the probe prompt.

    Mirrors the Claude probe's contract: prove a real artifact write plus a
    real handoff write, so a green probe means the runtime can actually do the
    work a role needs — not merely that the binary answered.
    """
    prompt = (
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
        + "\n"
    )
    prompt_file.write_text(prompt, encoding="utf-8")
    return prompt


def run_antigravity_probe(
    *,
    cwd: str | Path,
    quest_dir: str | Path,
    model: str,
    timeout: float = 120.0,
    agy_binary: str = DEFAULT_AGY_BINARY,
) -> RunResult:
    """Probe the Antigravity runtime by requiring a real artifact + handoff."""
    resolved_quest_dir = resolve_path(cwd, quest_dir)
    probe_dir = resolved_quest_dir / "logs" / "agy_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = probe_dir / "probe_prompt.txt"
    artifact_file = probe_dir / "probe_artifact.txt"
    handoff_file = probe_dir / "probe_handoff.json"
    prepare_artifact_files([artifact_file, handoff_file])
    prompt = _write_probe_prompt(prompt_file, artifact_file, handoff_file)

    try:
        cmd = build_agy_cmd(
            prompt=prompt,
            model=model,
            timeout=timeout,
            # The probe must write files, so it never runs in plan mode.
            mode=AGY_MODE_WRITE,
            add_dirs=[resolve_path(cwd, "."), resolved_quest_dir, probe_dir],
            agy_binary=agy_binary,
        )
    except ValueError as exc:
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=str(exc),
        )

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(Path(cwd).resolve()),
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
        )
        returncode = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except FileNotFoundError as exc:
        return RunResult(
            exit_code=1,
            handoff_state="missing",
            result_kind="invocation_error",
            source=None,
            stdout="",
            stderr=f"agy executable not found: {exc}",
        )
    except subprocess.TimeoutExpired:
        returncode = 124
        stdout = ""
        stderr = f"agy probe timed out after {timeout}s"

    envelope = parse_agy_envelope(stdout)
    handoff_state = classify_handoff_file(handoff_file)
    # A handoff alone must not green-light the runtime on a machine that never
    # proved the artifact write — same contract as the Claude probes.
    artifact_present = not any_artifact_missing_or_empty([artifact_file])
    probe_ok = handoff_state == "found" and artifact_present
    source = "handoff_json" if probe_ok else None
    exit_code = 0 if probe_ok else returncode or 1

    if probe_ok:
        result_kind = "handoff_json"
    elif handoff_state == "found" and not artifact_present:
        # Distinct from handoff_missing (handoff never written): agy responded
        # and wrote a handoff, only the artifact write failed. Mirrors
        # run_bridge_probe/run_bg_probe so preflight's artifact_missing branch
        # applies to this runtime too. Without it a handoff alone would report
        # handoff_json and appear to green-light a runtime that never proved
        # the write.
        result_kind = "artifact_missing"
    else:
        result_kind = classify_agy_result_kind(
            exit_code=returncode,
            envelope=envelope,
            handoff_state=handoff_state,
            stderr=stderr,
        )

    return RunResult(
        exit_code=exit_code,
        handoff_state=handoff_state,
        result_kind=result_kind,
        source=source,
        stdout=stdout,
        stderr=stderr or agy_error_text(envelope),
        rejected_model=(
            rejected_model_for(model) if result_kind == "model_rejected" else None
        ),
    )
