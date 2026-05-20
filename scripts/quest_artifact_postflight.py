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

Path classification (matches the agent ARTIFACTS contract):
* **Quest-artifact path** — resolves under ``<repo_root>/.quest/<id>/``.
  Subject to traversal + nested-``.quest`` + role-boundary + canonical-name
  checks.
* **Workspace-file path** — anywhere else in the repo (changed source files,
  tests, configs, docs that the builder or fixer touched). The
  builder/fixer ARTIFACTS contract lists these alongside the canonical
  quest deliverables. Traversal + existence apply (a declared workspace
  file that was never written is path drift) — boundary and canonical
  name are not meaningful for workspace files. Paths inside ``.quest/``
  that target a *sibling* quest's directory are flagged
  ``outside_boundary``: writing into another quest's space is the
  precise wrong-location failure this validator exists to catch.

Worktree symlink invariant
--------------------------
Quest always provisions a ``<worktree>/.quest`` symlink back to the repo's
canonical ``<repo>/.quest/`` (regardless of whether the worktree is in-repo
at ``<repo>/.worktrees/<x>/`` or outside the repo entirely). The validator
honors this invariant so the three forms an agent might write for the same
quest artifact —
  * absolute repo path:     ``<repo>/.quest/<id>/.../pr_description.md``
  * absolute worktree path: ``<worktree>/.quest/<id>/.../pr_description.md``
  * worktree-relative path: ``.quest/<id>/.../pr_description.md``
— all canonicalize to the same on-disk identity for coverage comparison.
Both ``_check_one`` (per-path classification) and the run-level coverage
identity collapse ``.quest/`` paths through ``Path.resolve()``. Non-``.quest/``
workspace files keep the ``os.path.normpath(os.path.abspath(...))`` identity
so the anti-symlink-collision defense for genuine workspace files stays
intact. ``--workspace-root`` governs only non-``.quest/`` workspace files,
where the worktree-vs-repo distinction is real (and only matters when the
worktree sits outside the repo).

Mismatch reasons (enum-like tokens written to the log):
* ``missing``               — declared path does not exist on disk, OR an
                              expected canonical quest artifact was not
                              declared at all (coverage check).
* ``outside_boundary``      — quest-artifact path resolves outside the
                              role's expected phase directory.
* ``noncanonical_name``     — quest-artifact filename is not in the
                              canonical set returned by
                              ``expected_artifacts_for_role``.
* ``nested_quest``           — declared path contains
                              ``.quest/<id>/.quest/`` after the quest dir.
* ``traversal_outside_repo`` — declared path resolves outside the repo root.
* ``unsupported_role_or_phase`` — defensive: ``expected_artifacts_for_role``
                              raised ``ValueError`` for the input.

CLI exit code:
* ``0`` — every declared artifact passed every check.
* ``1`` — one or more mismatches were recorded.

The orchestrator's halting policy (``accepted_with_warnings``) lives in
``workflow.md`` — this script just records mismatches and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
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


# Names directly under ``.quest/`` that are shared cross-quest infrastructure,
# not quest-id-keyed directories. A declared path under one of these is NOT
# a sibling-quest cross-write and must not be flagged as ``outside_boundary``.
# Source of truth for each:
# * ``cache``     — preflight stores host-verified bridge probes here
#                   (``scripts/quest_preflight.sh --orchestrator codex``).
# * ``backlog``   — deferred findings JSONL (canonical review-intelligence).
# * ``audit.log`` — persistent tool-call audit log across quest runs
#                   (``.claude/hooks/`` writes to it via PostToolUse).
# ``archive`` is intentionally NOT shared: builders/fixers should never write
# into ``.quest/archive/`` mid-quest; archival is the orchestrator's
# completion-time ceremony.
_SHARED_DOT_QUEST_NAMES = frozenset({"cache", "backlog", "audit.log"})


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


def _emit_mismatch_lines(mismatches: Iterable[dict[str, str]]) -> None:
    """Print one JSON line per mismatch to stdout.

    The orchestrator's ``workflow.md`` instruction surfaces the **current
    run's** mismatches to the user. The persistent ``path_compliance.log``
    is an append-only audit trail spanning every validator invocation in
    the quest — reading it after the fact would surface stale records
    from earlier roles, retries, or iterations and misattribute them to
    the current handoff. Writing the current-run mismatches to stdout
    lets the orchestrator capture exactly the records produced by this
    invocation, with no offset bookkeeping required.

    Stdout stays empty on a clean run (exit 0) so callers can use the
    presence of output as a "had mismatches" signal.
    """

    for mismatch in mismatches:
        print(json.dumps(mismatch, sort_keys=True))


# ---------------------------------------------------------------------------
# Handoff loading
# ---------------------------------------------------------------------------


def _load_declared_artifacts(
    handoff_path: Path, workspace_root: Path
) -> list[Path]:
    """Read ``handoff.json`` and return declared artifact paths as Path objects.

    Relative paths are resolved against ``workspace_root`` — the directory the
    agent was actually editing in. In non-worktree mode this is the repo root;
    in worktree mode (``state.json.worktree_path``) it is the worktree path.
    The workflow doctrine says orchestrators pass quest-artifact paths as
    absolute in worktree mode, so relative paths in the handoff are
    workspace-relative by convention.

    Defensive parsing: an unreadable handoff (missing file, non-UTF-8 bytes,
    invalid JSON) or a non-dict payload must not crash the validator — the
    orchestrator's text-fallback path can produce any of these, and the
    validator's contract is to report mismatches, not raise. In those cases
    we return an empty declared list and let the run-level coverage check
    flag every expected canonical path as ``missing``.
    """

    try:
        raw = handoff_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    artifacts = data.get("artifacts") or []
    if not isinstance(artifacts, list):
        return []
    paths: list[Path] = []
    for entry in artifacts:
        if not isinstance(entry, str) or not entry:
            continue
        candidate = Path(entry)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
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
    workspace_root: Path | None = None,
) -> int:
    """Validate the handoff and return ``0`` (pass) or ``1`` (any mismatch).

    Arguments mirror the CLI shape.

    * ``repo_root`` — the directory that contains ``.quest/<id>/``. Used to
      anchor quest-artifact path checks and the sibling-quest detector. When
      not supplied, it is computed as ``quest_dir.parent.parent``.
    * ``workspace_root`` — where the agent was actually editing (``state
      .json.worktree_path`` in worktree mode, otherwise the repo root).
      Used to anchor workspace-file path checks: traversal containment,
      relative-path resolution in ``handoff.artifacts``, and existence on
      disk. When not supplied, falls back to ``repo_root`` (non-worktree
      mode).

    In non-worktree mode the two are the same and the prior behavior is
    preserved. In worktree mode the orchestrator MUST pass
    ``workspace_root`` so workspace-file artifacts (changed source files in
    the worktree) are validated against the right tree.
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

    if workspace_root is None:
        workspace_root = repo_root
    workspace_root = Path(workspace_root).resolve()

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
        _emit_mismatch_lines(mismatches)
        return 1

    if not expected_paths:
        # Solo-mode-disabled roles return empty. No artifacts to validate.
        return 0

    declared_paths = _load_declared_artifacts(handoff_path, workspace_root)

    canonical_names = {Path(p).name for p in expected_paths}
    # All expected_paths share the same phase directory by construction;
    # take it once for the boundary check. Resolve the PARENT (to
    # canonicalize a worktree ``.quest`` directory symlink) but not the
    # file itself — if the canonical artifact is provisioned as a
    # file-level symlink to outside the quest tree, ``.resolve()`` would
    # follow the link and corrupt the boundary to wherever it points.
    boundary_dir = Path(expected_paths[0]).parent.resolve()

    mismatches: list[dict[str, str]] = []

    # Coverage check: every expected canonical artifact must be declared and
    # exist on disk at the canonical location. Without this, an empty
    # ``artifacts: []`` array or a handoff that omits one canonical path would
    # pass silently (AC4: "mismatches cause non-zero exit and are not
    # silently accepted").
    #
    # Identity comparison strategy depends on path location:
    #
    # * **Paths under ``<repo>/.quest/``** (either directly, or via the
    #   ``<worktree>/.quest`` symlink Quest provisions for worktree mode):
    #   canonicalize through ``Path.resolve()`` so the worktree mount and
    #   the repo mount produce the SAME identity for the SAME on-disk
    #   inode. Without this, a worktree-rooted relative handoff entry like
    #   ``.quest/<id>/.../pr_description.md`` would resolve against
    #   ``workspace_root`` to ``<worktree>/.quest/.../pr_description.md``,
    #   miss the abspath comparison against the canonical
    #   ``<repo>/.quest/.../pr_description.md``, and emit a false
    #   ``missing`` — even though the path is the same file.
    #
    # * **Paths outside ``.quest/``** (true workspace files): keep the
    #   ``os.path.normpath(os.path.abspath(...))`` identity to preserve
    #   the anti-symlink-collision defense for non-quest paths. Two
    #   distinct workspace files that happen to symlink to one target on
    #   disk remain distinct identities.
    def _identity(p: Path) -> str:
        try:
            resolved = Path(p).resolve()
            resolved.relative_to(repo_root / ".quest")
            # Path lives (possibly via .quest symlink) under <repo>/.quest/
            # — collapse symlinks so the worktree mount matches the repo.
            return os.path.normpath(str(resolved))
        except (ValueError, OSError):
            # Not under <repo>/.quest/, or resolve failed — keep abspath
            # identity so non-quest symlink collisions stay distinct.
            return os.path.normpath(os.path.abspath(str(p)))

    # The handoff file itself is part of ``expected_artifacts_for_role(...)``
    # by construction (every role writes one), but agent contracts do NOT ask
    # roles to declare their own handoff envelope inside ``artifacts`` — that
    # field is reserved for the role's deliverables. Exclude the handoff path
    # from the coverage comparison: the validator was invoked on that exact
    # file via ``--handoff``, so its existence and identity are implicit.
    handoff_identity = _identity(handoff_path)
    declared_identities = {_identity(p) for p in declared_paths}
    for expected in expected_paths:
        expected_identity = _identity(Path(expected))
        if expected_identity == handoff_identity:
            continue
        if expected_identity not in declared_identities:
            mismatches.append(
                _make_mismatch(
                    phase=phase,
                    role=role,
                    declared="(undeclared)",
                    actual=str(expected),
                    reason="missing",
                )
            )
        elif not Path(expected_identity).exists():
            mismatches.append(
                _make_mismatch(
                    phase=phase,
                    role=role,
                    declared=str(expected),
                    actual=expected_identity,
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
            workspace_root=workspace_root,
            boundary_dir=boundary_dir,
            canonical_names=canonical_names,
        )
        if mismatch is not None:
            mismatches.append(mismatch)

    if mismatches:
        _append_mismatch_lines(log_path, mismatches)
        _emit_mismatch_lines(mismatches)
        return 1
    return 0


def _check_one(
    *,
    declared: Path,
    phase: str,
    role: str,
    quest_dir: Path,
    repo_root: Path,
    workspace_root: Path,
    boundary_dir: Path,
    canonical_names: set[str],
) -> dict[str, str] | None:
    """Apply the per-path validation checks to one declared artifact.

    Path classification (matches the agent ARTIFACTS contract):

    * **Quest-artifact path** — resolves under ``<repo_root>/.quest/<id>/``.
      Subject to the full check set: traversal (against ``repo_root``),
      nested ``.quest``, role boundary (must live in ``boundary_dir``), and
      canonical filename match.
    * **Workspace-file path** — anywhere else inside ``workspace_root``
      (changed source files, tests, docs, configs). The builder and fixer
      contracts legitimately list these in ARTIFACTS alongside the
      canonical quest deliverables. Traversal is checked against
      ``workspace_root``; existence is required; boundary and
      canonical-name are not meaningful for workspace files.

    In worktree mode ``workspace_root`` differs from ``repo_root``: quest
    artifacts live with the original repo (``repo_root``) while changed
    source files live in the worktree (``workspace_root``). The validator
    uses the correct anchor for each class.

    Returns a mismatch record on the first failing check, or ``None`` when
    the path passes every applicable check.
    """

    # ``resolve(strict=False)`` collapses ``..`` segments without requiring
    # the target to exist (we still need to detect missing files).
    resolved = Path(declared).resolve()

    # Classify by the DECLARED path's directory, not the resolved target.
    # A symlink at a canonical quest path (e.g.
    # ``.quest/<id>/phase_X/pr_description.md`` -> ``scripts/foo.py``)
    # would otherwise be misclassified as a workspace file — ``resolved``
    # lives outside ``.quest/<id>/`` — and slip through with success.
    # Canonicalizing the PARENT lets the worktree ``.quest`` symlink
    # resolve to the real inode while keeping the file-level symlink
    # visible to the downstream boundary check, which now flags the
    # escape via the ``resolved.parent != boundary_dir`` invariant.
    declared_path = Path(declared)
    declared_logical = declared_path.parent.resolve() / declared_path.name
    quest_id = quest_dir.name
    quest_root = repo_root / ".quest" / quest_id
    try:
        declared_logical.relative_to(quest_root)
        is_quest_artifact = True
    except ValueError:
        is_quest_artifact = False

    # Anything inside ``<repo>/.quest/`` (our quest, a sibling quest, or
    # shared infrastructure like ``cache/`` and ``backlog/``) lives with the
    # original repo, NOT the worktree. Use ``repo_root`` as the traversal
    # anchor for those paths so worktree-mode declarations don't falsely
    # trip ``traversal_outside_repo`` when the worktree sits outside the
    # original repo's directory tree.
    try:
        rel_to_dot_quest = resolved.relative_to(repo_root / ".quest")
        in_dot_quest_tree = True
    except ValueError:
        rel_to_dot_quest = None
        in_dot_quest_tree = False

    # 1. Traversal escape outside the relevant root.
    # Paths under ``.quest/`` anchor to ``repo_root``; everything else
    # anchors to ``workspace_root`` (which differs in worktree mode). A
    # path outside both is genuine traversal.
    traversal_anchor = repo_root if in_dot_quest_tree else workspace_root
    try:
        resolved.relative_to(traversal_anchor)
    except ValueError:
        return _make_mismatch(
            phase=phase,
            role=role,
            declared=str(declared),
            actual=str(resolved),
            reason="traversal_outside_repo",
        )

    if not is_quest_artifact:
        # Workspace file OR sibling/shared ``.quest/`` path. Boundary and
        # canonical-name don't apply, but the path must still exist on disk
        # (a declared file that was never actually written is path drift),
        # and paths inside ``.quest/`` that target a sibling quest's
        # directory (not ours, not one of the shared infrastructure names)
        # are wrong-location by definition.
        #
        # Order matters: check sibling-quest BEFORE existence so a
        # wrong-location declaration is reported as ``outside_boundary``,
        # not downgraded to ``missing`` when the file happens not to exist.
        # The shared-name allowlist excludes paths that are legitimately
        # cross-quest (preflight cache, deferred-findings backlog,
        # persistent audit log).
        if in_dot_quest_tree:
            first_segment = (
                rel_to_dot_quest.parts[0] if rel_to_dot_quest.parts else ""
            )
            if first_segment not in _SHARED_DOT_QUEST_NAMES:
                # Quest-id-keyed sibling directory (not ours, not shared).
                return _make_mismatch(
                    phase=phase,
                    role=role,
                    declared=str(declared),
                    actual=str(resolved),
                    reason="outside_boundary",
                )
            # fall through to existence check for shared paths.

        if not resolved.exists():
            return _make_mismatch(
                phase=phase,
                role=role,
                declared=str(declared),
                actual=str(resolved),
                reason="missing",
            )
        return None

    # 2. Nested ``.quest/<id>/.quest/...`` is always wrong.
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
    # Require exact-parent equality, not ``relative_to(boundary_dir)``: a
    # canonical-named file at a nested depth inside the boundary (e.g.
    # ``phase_01_plan/nested/plan.md``) would otherwise pass the shape
    # checks and let an off-spec declaration through whenever the real
    # canonical path is also declared (which satisfies coverage).
    if resolved.parent != boundary_dir:
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
    parser.add_argument(
        "--workspace-root",
        default=None,
        help=(
            "Source-workspace root the agent was editing in (state.json."
            "worktree_path in worktree mode; the repo root otherwise). "
            "Workspace-file artifacts are anchored to this path. Defaults "
            "to the repo containing .quest/<id>/."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    log_path = Path(args.log) if args.log else None
    workspace_root = Path(args.workspace_root) if args.workspace_root else None
    return run(
        quest_dir=Path(args.quest_dir),
        phase=args.phase,
        role=args.role,
        handoff=Path(args.handoff),
        quest_mode=args.quest_mode,
        log=log_path,
        workspace_root=workspace_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
