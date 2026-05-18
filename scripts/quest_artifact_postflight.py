"""Quest sub-agent artifact-path post-flight validator.

This script is invoked by the orchestrator after every sub-agent hand-off (see
``.skills/quest/delegation/workflow.md``). It compares the artifacts declared
in the agent's ``handoff.json`` against the canonical boundary computed by
``scripts/quest_runtime/artifacts.expected_artifacts_for_role(...)`` and the
on-disk filesystem.

Design goals (per plan ``§3``):
* Filesystem-only. No git dependency, no network, no subprocesses.
* Non-zero exit on any mismatch; structured JSON log on disk.
* Pure stdlib + ``quest_runtime.artifacts`` (already imported elsewhere).

Mismatch reasons (enum-like tokens written to the log):
* ``missing``               — declared path does not exist on disk.
* ``outside_boundary``      — declared path resolves outside the role's
                              expected phase directory.
* ``noncanonical_name``     — declared filename is not in the canonical set
                              returned by ``expected_artifacts_for_role``.
* ``nested_quest``           — declared path contains
                              ``.quest/<id>/.quest/`` after the quest dir.
* ``traversal_outside_repo`` — declared path resolves outside the repo root.

CLI exit code:
* ``0`` — every declared artifact passed every check.
* ``1`` — one or more mismatches were recorded.

The orchestrator's halting policy (``accepted_with_warnings``) lives in
``workflow.md`` — this script just records mismatches and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Allow the script to run both as ``python3 scripts/quest_artifact_postflight.py``
# (the documented invocation) and as ``python3 -m quest_artifact_postflight``.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from quest_runtime.artifacts import (  # noqa: E402
    ROLE_ARTIFACTS,
    ROLE_PHASE_ALIASES,
    expected_artifacts_for_role,
)


# Phase-directory names used in ``ROLE_ARTIFACTS`` (e.g. ``phase_01_plan``) are
# the on-disk layout. The orchestrator may pass either the directory name or
# a logical phase token (e.g. ``plan``) on the ``--phase`` flag. The mapping
# below resolves a logical phase from any of the supported inputs for a given
# role so we can call ``expected_artifacts_for_role`` with the value it expects.
def _resolve_logical_phase(role: str, phase: str) -> str:
    """Return a logical phase token accepted by expected_artifacts_for_role.

    ``phase`` may already be a logical token (``plan``, ``implementation``,
    ``code_review`` etc.) or a phase-directory name (``phase_01_plan``,
    ``phase_02_implementation``, ``phase_03_review``). For the directory
    form we look up the role-specific alias set and pick the first match;
    when no role-specific match exists we pass the value through unchanged
    so the helper itself can raise the proper ValueError.
    """

    normalized = phase.strip().lower().replace("-", "_")
    aliases = ROLE_PHASE_ALIASES.get(role.strip(), frozenset())
    if normalized in aliases:
        return normalized

    # Map phase-directory layout names to the role's logical phase.
    role_entry = ROLE_ARTIFACTS.get(role.strip())
    if role_entry is not None:
        role_phase_dir, _ = role_entry
        if normalized == role_phase_dir:
            # Take the first alias deterministically (sorted for stability).
            return sorted(aliases)[0] if aliases else normalized

    return normalized


# ---------------------------------------------------------------------------
# Mismatch record
# ---------------------------------------------------------------------------


def _make_mismatch(
    *,
    phase: str,
    role: str,
    declared: str,
    actual: str,
    reason: str,
) -> dict[str, str]:
    """Build a structured mismatch record (one JSON object per log line)."""

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phase": phase,
        "role": role,
        "declared": declared,
        "actual": actual,
        "reason": reason,
    }


def _append_mismatch_lines(log_path: Path, mismatches: Iterable[dict[str, str]]) -> None:
    """Append one JSON line per mismatch to ``log_path``.

    The parent directory is created if it does not exist. The file is opened
    in append mode so concurrent role validations do not clobber prior runs.
    """

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        for mismatch in mismatches:
            fh.write(json.dumps(mismatch, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Handoff loading
# ---------------------------------------------------------------------------


def _load_declared_artifacts(handoff_path: Path, repo_root: Path) -> list[Path]:
    """Read ``handoff.json`` and return declared artifact paths as Path objects.

    Relative paths are resolved against ``repo_root`` so the validator can
    compare them to the expected boundary, which is absolute.
    """

    raw = handoff_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    artifacts = data.get("artifacts") or []
    if not isinstance(artifacts, list):
        return []
    paths: list[Path] = []
    for entry in artifacts:
        if not isinstance(entry, str) or not entry:
            continue
        candidate = Path(entry)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        paths.append(candidate)
    return paths


# ---------------------------------------------------------------------------
# Public run entry point
# ---------------------------------------------------------------------------


def run(
    *,
    quest_dir: Path,
    phase: str,
    role: str,
    handoff: Path,
    quest_mode: str,
    log: Path | None = None,
    repo_root: Path | None = None,
) -> int:
    """Validate the handoff and return ``0`` (pass) or ``1`` (any mismatch).

    Arguments mirror the CLI shape. ``repo_root`` is the workspace root used
    to resolve relative declared paths and to detect ``traversal_outside_repo``;
    when not supplied, it is computed from ``quest_dir`` (the parent of the
    ``.quest`` directory).
    """

    quest_dir = Path(quest_dir).resolve()
    handoff_path = Path(handoff).resolve()

    if log is None:
        log = quest_dir / "logs" / "path_compliance.log"
    log_path = Path(log)

    if repo_root is None:
        # ``quest_dir`` is ``<repo_root>/.quest/<id>``. Walk two levels up.
        repo_root = quest_dir.parent.parent
    repo_root = Path(repo_root).resolve()

    # Resolve expected boundary. A role with no expected artifacts (solo-mode
    # disabled or runtime-internal) is treated as a pass-through: nothing to
    # validate. ``expected_artifacts_for_role`` raises ``ValueError`` for
    # unsupported roles or phase mismatches — the validator surfaces those as
    # mismatch records rather than crashing.
    logical_phase = _resolve_logical_phase(role, phase)
    try:
        expected_paths = expected_artifacts_for_role(
            quest_dir, logical_phase, role, quest_mode=quest_mode
        )
    except ValueError as exc:
        mismatches = [
            _make_mismatch(
                phase=phase,
                role=role,
                declared="(role/phase resolution)",
                actual=str(exc),
                reason="unsupported_role_or_phase",
            )
        ]
        _append_mismatch_lines(log_path, mismatches)
        return 1

    if not expected_paths:
        # Solo-mode-disabled roles return empty. No artifacts to validate.
        return 0

    declared_paths = _load_declared_artifacts(handoff_path, repo_root)

    canonical_names = {Path(p).name for p in expected_paths}
    # All expected_paths share the same phase directory by construction;
    # take it once for the boundary check.
    boundary_dir = Path(expected_paths[0]).resolve().parent

    mismatches: list[dict[str, str]] = []

    # Coverage check: every expected canonical artifact must be declared and
    # exist on disk at the canonical location. Without this, an empty
    # ``artifacts: []`` array or a handoff that omits one canonical path would
    # pass silently (AC4: "mismatches cause non-zero exit and are not
    # silently accepted").
    resolved_declared = {Path(p).resolve() for p in declared_paths}
    for expected in expected_paths:
        resolved_expected = Path(expected).resolve()
        if resolved_expected not in resolved_declared:
            mismatches.append(
                _make_mismatch(
                    phase=phase,
                    role=role,
                    declared="(undeclared)",
                    actual=str(expected),
                    reason="missing",
                )
            )
        elif not resolved_expected.exists():
            mismatches.append(
                _make_mismatch(
                    phase=phase,
                    role=role,
                    declared=str(expected),
                    actual=str(resolved_expected),
                    reason="missing",
                )
            )

    for declared in declared_paths:
        mismatch = _check_one(
            declared=declared,
            phase=phase,
            role=role,
            quest_dir=quest_dir,
            repo_root=repo_root,
            boundary_dir=boundary_dir,
            canonical_names=canonical_names,
        )
        if mismatch is not None:
            mismatches.append(mismatch)

    if mismatches:
        _append_mismatch_lines(log_path, mismatches)
        return 1
    return 0


def _check_one(
    *,
    declared: Path,
    phase: str,
    role: str,
    quest_dir: Path,
    repo_root: Path,
    boundary_dir: Path,
    canonical_names: set[str],
) -> dict[str, str] | None:
    """Apply the five validation checks to one declared path.

    Returns a mismatch record on the first failing check, or ``None`` when
    the path passes every check.
    """

    # ``resolve(strict=False)`` collapses ``..`` segments without requiring
    # the target to exist (we still need to detect missing files).
    resolved = Path(declared).resolve()

    # 1. Traversal escape outside the repo root.
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return _make_mismatch(
            phase=phase,
            role=role,
            declared=str(declared),
            actual=str(resolved),
            reason="traversal_outside_repo",
        )

    # 2. Nested ``.quest/<id>/.quest/...`` is always wrong.
    quest_id = quest_dir.name
    nested_marker = f".quest/{quest_id}/.quest/"
    if nested_marker in resolved.as_posix():
        return _make_mismatch(
            phase=phase,
            role=role,
            declared=str(declared),
            actual=str(resolved),
            reason="nested_quest",
        )

    # 3. Inside the role's expected boundary (parent directory).
    try:
        resolved.relative_to(boundary_dir)
    except ValueError:
        return _make_mismatch(
            phase=phase,
            role=role,
            declared=str(declared),
            actual=str(resolved),
            reason="outside_boundary",
        )

    # 4. Canonical filename match.
    if canonical_names and resolved.name not in canonical_names:
        return _make_mismatch(
            phase=phase,
            role=role,
            declared=str(declared),
            actual=str(resolved),
            reason="noncanonical_name",
        )

    # Missing-on-disk is owned by the coverage check in ``run(...)`` so we do
    # not double-emit when a declared canonical path is also undeclared or
    # absent. ``_check_one`` returns ``None`` once all path-shape checks pass.
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate sub-agent handoff artifact paths against "
            "expected_artifacts_for_role(...) and the on-disk filesystem."
        ),
    )
    parser.add_argument("--quest-dir", required=True, help="Path to .quest/<id>/")
    parser.add_argument("--phase", required=True, help="Phase token (e.g. phase_01_plan)")
    parser.add_argument("--role", required=True, help="Sub-agent role (e.g. planner)")
    parser.add_argument(
        "--handoff",
        required=True,
        help="Path to the handoff.json the role wrote",
    )
    parser.add_argument(
        "--quest-mode",
        required=True,
        help="state.json.quest_mode value (e.g. workflow, solo, quest_minor)",
    )
    parser.add_argument(
        "--log",
        default=None,
        help=(
            "Override the path_compliance.log location. Defaults to "
            "<quest-dir>/logs/path_compliance.log."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    log_path = Path(args.log) if args.log else None
    return run(
        quest_dir=Path(args.quest_dir),
        phase=args.phase,
        role=args.role,
        handoff=Path(args.handoff),
        quest_mode=args.quest_mode,
        log=log_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
