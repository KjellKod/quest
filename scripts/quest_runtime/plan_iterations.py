"""Immutable plan-iteration snapshots and refinement bindings."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from .state import _lock_file, load_state
from .review_intelligence import validate_findings


class PlanIterationError(Exception):
    """A stable plan-iteration lifecycle failure."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PlanIterationError(f"invalid_json:{path.name}") from exc
    if not isinstance(value, dict):
        raise PlanIterationError(f"invalid_json:{path.name}")
    return value


def _iteration_dir(quest_dir: Path, iteration: int) -> Path:
    return quest_dir / "history" / "plan" / f"iteration-{iteration:04d}"


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_publish_bytes(path: Path, data: bytes) -> None:
    """Durably replace one file while leaving its source bytes untouched."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
        temp_path = None
        _fsync_dir(path.parent)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _read_refinement_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PlanIterationError(f"refinement_output_missing:{path.name}") from exc


def _has_plan_history(quest_dir: Path) -> bool:
    history_root = quest_dir / "history" / "plan"
    return any(history_root.glob("iteration-*/snapshot.json")) or any(
        history_root.glob("iteration-*/snapshot.sha256")
    )


def _decision(quest_dir: Path, mode: str) -> str:
    phase_dir = quest_dir / "phase_01_plan"
    handoff_name = (
        "handoff_plan-reviewer-a.json" if mode == "solo" else "handoff_arbiter.json"
    )
    next_value = _read_json(phase_dir / handoff_name).get("next")
    if next_value == "planner":
        return "planner"
    if next_value in {"builder", "arbiter"}:
        return "builder"
    raise PlanIterationError(f"invalid_decision:{handoff_name}")


def _inventory(quest_dir: Path, mode: str, decision: str) -> dict[str, str]:
    inventory = {
        "plan.md": "plan.md",
        "handoff.json": "handoff_planner.json",
        "review_plan-reviewer-a.md": "review_plan-reviewer-a.md",
        "handoff_plan-reviewer-a.json": "handoff_plan-reviewer-a.json",
    }
    if mode != "solo":
        inventory.update(
            {
                "review_plan-reviewer-b.md": "review_plan-reviewer-b.md",
                "handoff_plan-reviewer-b.json": "handoff_plan-reviewer-b.json",
                "arbiter_verdict.md": "arbiter_verdict.md",
                "handoff_arbiter.json": "handoff_arbiter.json",
            }
        )
        if decision == "builder":
            inventory.update(
                {
                    "review_findings.json": "review_findings.json",
                    "review_backlog.json": "review_backlog.json",
                }
            )
        else:
            inventory["refinement_binding.json"] = "refinement_binding.json"
    return inventory


def _legacy_inventory(phase_dir: Path, mode: str) -> dict[str, str]:
    """Return the pre-identity canonical producer files that are present."""

    inventory = {
        "plan.md": "plan.md",
        "handoff.json": "handoff_planner.json",
        "review_plan-reviewer-a.md": "review_plan-reviewer-a.md",
        "handoff_plan-reviewer-a.json": "handoff_plan-reviewer-a.json",
    }
    if mode != "solo":
        inventory.update(
            {
                "review_plan-reviewer-b.md": "review_plan-reviewer-b.md",
                "handoff_plan-reviewer-b.json": "handoff_plan-reviewer-b.json",
                "arbiter_verdict.md": "arbiter_verdict.md",
                "handoff_arbiter.json": "handoff_arbiter.json",
            }
        )
        for name in (
            "review_findings.json",
            "review_backlog.json",
            "refinement_binding.json",
        ):
            if (phase_dir / name).is_file():
                inventory[name] = name
    return inventory


def _is_legacy_handoff_set(phase_dir: Path, inventory: dict[str, str]) -> bool:
    """Identify only a wholly pre-identity handoff set as legacy."""

    identities: list[bool] = []
    for canonical_name in inventory:
        if not canonical_name.startswith("handoff"):
            continue
        handoff = _read_json(phase_dir / canonical_name)
        has_iteration = "plan_iteration" in handoff
        has_generation = "user_replan_generation" in handoff
        if has_iteration != has_generation:
            return False
        identities.append(has_iteration)
    return bool(identities) and not any(identities)


def _validate_handoff_identity(
    phase_dir: Path,
    inventory: dict[str, str],
    iteration: int,
    generation: object,
) -> None:
    for canonical_name in inventory:
        if not canonical_name.startswith("handoff"):
            continue
        handoff = _read_json(phase_dir / canonical_name)
        _validate_handoff_values(handoff, canonical_name, iteration, generation)


def _validate_handoff_values(
    handoff: dict[str, object],
    canonical_name: str,
    iteration: int,
    generation: object,
) -> None:
    if handoff.get("plan_iteration") != iteration:
        raise PlanIterationError(f"handoff_iteration_mismatch:{canonical_name}")
    if handoff.get("user_replan_generation") != generation:
        raise PlanIterationError(f"handoff_generation_mismatch:{canonical_name}")


def _replan_generation(state: dict[str, object]) -> object:
    request = state.get("user_replan")
    return request.get("generation") if isinstance(request, dict) else None


def _snapshot_reason(state: dict[str, object]) -> str:
    request = state.get("user_replan")
    if isinstance(request, dict) and request.get("lifecycle") in {
        "recorded",
        "planning",
    }:
        return "human_replan"
    return "completed"


def _validate_refinement_identity(
    phase_dir: Path,
    inventory: dict[str, str],
    iteration: int,
) -> None:
    if "refinement_binding.json" not in inventory:
        return
    binding = _read_json(phase_dir / "refinement_binding.json")
    if (
        binding.get("source_plan_iteration") != iteration
        or binding.get("requested_plan_iteration") != iteration + 1
    ):
        raise PlanIterationError("refinement_iteration_mismatch")


def _manifest_file_metadata(metadata: object) -> tuple[object, object]:
    if isinstance(metadata, str):
        return metadata, None
    if isinstance(metadata, dict):
        return metadata.get("sha256"), metadata.get("size")
    raise PlanIterationError("snapshot_manifest_invalid")


def _verify_manifest(snapshot_dir: Path) -> dict[str, object]:
    manifest_path = snapshot_dir / "snapshot.json"
    seal_path = snapshot_dir / "snapshot.sha256"
    try:
        manifest_bytes = manifest_path.read_bytes()
        seal = seal_path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise PlanIterationError("snapshot_unsealed") from exc
    if seal != _digest(manifest_bytes):
        raise PlanIterationError("snapshot_seal_mismatch")
    try:
        manifest = json.loads(manifest_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PlanIterationError("snapshot_manifest_invalid") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise PlanIterationError("snapshot_manifest_invalid")
    files = manifest["files"]
    for archive_name, metadata in files.items():
        if not isinstance(archive_name, str):
            raise PlanIterationError("snapshot_manifest_invalid")
        path = snapshot_dir / archive_name
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise PlanIterationError(f"snapshot_file_missing:{archive_name}") from exc
        expected_digest, expected_size = _manifest_file_metadata(metadata)
        if expected_digest != _digest(data) or (
            expected_size is not None and expected_size != len(data)
        ):
            raise PlanIterationError(f"snapshot_file_mismatch:{archive_name}")
    return manifest


def verify_plan_iteration_snapshot(quest_dir: str | Path, iteration: int) -> None:
    """Verify archived bytes, adding the one-time seal for a legacy manifest."""

    root = Path(quest_dir).resolve()
    snapshot_dir = _iteration_dir(root, iteration)
    manifest_path = snapshot_dir / "snapshot.json"
    seal_path = snapshot_dir / "snapshot.sha256"
    if manifest_path.exists() and not seal_path.exists():
        try:
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise PlanIterationError("snapshot_manifest_invalid") from exc
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("files"), dict
        ):
            raise PlanIterationError("snapshot_manifest_invalid")
        for archive_name, metadata in manifest["files"].items():
            if not isinstance(archive_name, str):
                raise PlanIterationError("snapshot_manifest_invalid")
            try:
                data = (snapshot_dir / archive_name).read_bytes()
            except OSError as exc:
                raise PlanIterationError(
                    f"snapshot_file_missing:{archive_name}"
                ) from exc
            expected, _ = _manifest_file_metadata(metadata)
            if expected != _digest(data):
                raise PlanIterationError(f"snapshot_file_mismatch:{archive_name}")
        try:
            with seal_path.open("w", encoding="ascii") as handle:
                handle.write(f"{_digest(manifest_bytes)}\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise PlanIterationError("snapshot_seal_write_failed") from exc
        _fsync_dir(snapshot_dir)
    manifest = _verify_manifest(snapshot_dir)
    manifest_iteration = manifest.get("iteration", manifest.get("plan_iteration"))
    if manifest_iteration != iteration:
        raise PlanIterationError("snapshot_iteration_mismatch")


def snapshot_plan_iteration(quest_dir: str | Path, iteration: int) -> Path:
    """Atomically seal the current completed plan iteration."""

    root = Path(quest_dir).resolve()
    state_path = root / "state.json"
    with _lock_file(state_path) as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = load_state(root)
        if state.get("plan_iteration") != iteration:
            raise PlanIterationError("iteration_mismatch")
        target = _iteration_dir(root, iteration)
        if target.exists():
            verify_plan_iteration_snapshot(root, iteration)
            return target

        mode = str(state.get("quest_mode", "workflow"))
        decision = _decision(root, mode)
        phase_dir = root / "phase_01_plan"
        current_inventory = _inventory(root, mode, decision)
        legacy_inventory = _legacy_inventory(phase_dir, mode)
        bootstrap_snapshot = not _has_plan_history(root) and _is_legacy_handoff_set(
            phase_dir,
            legacy_inventory,
        )
        inventory = legacy_inventory if bootstrap_snapshot else current_inventory
        generation = _replan_generation(state)
        if not bootstrap_snapshot:
            _validate_handoff_identity(phase_dir, inventory, iteration, generation)
            _validate_refinement_identity(phase_dir, inventory, iteration)
        sources: dict[str, bytes] = {}
        for canonical_name, archive_name in inventory.items():
            source = phase_dir / canonical_name
            try:
                data = source.read_bytes()
            except OSError as exc:
                raise PlanIterationError(
                    f"snapshot_source_missing:{canonical_name}"
                ) from exc
            if not data:
                raise PlanIterationError(f"snapshot_source_empty:{canonical_name}")
            sources[archive_name] = data

        target.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
        try:
            file_manifest: dict[str, dict[str, object]] = {}
            for archive_name, data in sorted(sources.items()):
                output = temp_dir / archive_name
                with output.open("wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                canonical_name = next(
                    name for name, mapped in inventory.items() if mapped == archive_name
                )
                file_manifest[archive_name] = {
                    "source": canonical_name,
                    "size": len(data),
                    "sha256": _digest(data),
                }
            manifest = {
                "version": 1,
                "iteration": iteration,
                "mode": mode,
                "decision": decision,
                "reason": _snapshot_reason(state),
                "bootstrap_snapshot": bootstrap_snapshot,
                "files": file_manifest,
            }
            manifest_bytes = (
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            ).encode()
            manifest_path = temp_dir / "snapshot.json"
            with manifest_path.open("wb") as handle:
                handle.write(manifest_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            seal_path = temp_dir / "snapshot.sha256"
            with seal_path.open("w", encoding="ascii") as handle:
                handle.write(f"{_digest(manifest_bytes)}\n")
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_dir(temp_dir)
            os.replace(temp_dir, target)
            _fsync_dir(target.parent)
        except BaseException:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return target


def cleanup_current(quest_dir: str | Path, iteration: int) -> None:
    """Remove repurposable current artifacts only after sealing iteration."""

    root = Path(quest_dir).resolve()
    state_path = root / "state.json"
    with _lock_file(state_path) as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = load_state(root)
        if state.get("plan_iteration") != iteration:
            raise PlanIterationError("iteration_mismatch")
        verify_plan_iteration_snapshot(root, iteration)
        phase_dir = root / "phase_01_plan"
        for pattern in ("handoff*.json", "*.next"):
            for path in phase_dir.glob(pattern):
                path.unlink(missing_ok=True)


def cleanup_current_plan_iteration(quest_dir: str | Path, iteration: int) -> None:
    """Public, explicit name for cleanup-current lifecycle behavior."""

    cleanup_current(quest_dir, iteration)


def _publish_refinement_locked(
    root: Path,
    state: dict[str, object],
    iteration: int,
) -> Path:
    if state.get("quest_mode", "workflow") == "solo":
        raise PlanIterationError("workflow_only")
    if state.get("plan_iteration") != iteration:
        raise PlanIterationError("iteration_mismatch")
    phase_dir = root / "phase_01_plan"
    handoff = _read_json(phase_dir / "handoff_arbiter.json")
    if handoff.get("status") != "complete" or handoff.get("next") != "planner":
        raise PlanIterationError("arbiter_not_refining")
    _validate_handoff_values(
        handoff,
        "handoff_arbiter.json",
        iteration,
        _replan_generation(state),
    )
    handoff_bytes = _read_refinement_bytes(phase_dir / "handoff_arbiter.json")
    verdict_next = phase_dir / "arbiter_verdict.md.next"
    findings_next = phase_dir / "review_findings.json.next"
    canonical = phase_dir / "arbiter_verdict.md"
    binding_path = phase_dir / "refinement_binding.json"
    if not verdict_next.exists() and binding_path.exists():
        binding = _read_json(binding_path)
        canonical_verdict = _read_refinement_bytes(canonical)
        if (
            binding.get("source_plan_iteration") == iteration
            and binding.get("requested_plan_iteration") == iteration + 1
            and binding.get("verdict_sha256") == _digest(canonical_verdict)
            and binding.get("arbiter_handoff_sha256") == _digest(handoff_bytes)
            and binding.get("next") == "planner"
        ):
            return binding_path
    verdict = _read_refinement_bytes(verdict_next)
    findings_bytes = _read_refinement_bytes(findings_next)
    if not verdict.strip() or not findings_bytes.strip():
        raise PlanIterationError("refinement_output_empty")
    try:
        findings = json.loads(findings_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PlanIterationError("findings_invalid") from exc
    if not isinstance(findings, list) or validate_findings(findings):
        raise PlanIterationError("findings_invalid")
    binding = {
        "source_plan_iteration": iteration,
        "requested_plan_iteration": iteration + 1,
        "verdict_sha256": _digest(verdict),
        "arbiter_handoff_sha256": _digest(handoff_bytes),
        "next": "planner",
    }
    binding_bytes = (json.dumps(binding, indent=2, sort_keys=True) + "\n").encode()
    _atomic_publish_bytes(canonical, verdict)
    _atomic_publish_bytes(binding_path, binding_bytes)
    verdict_next.unlink(missing_ok=True)
    _fsync_dir(phase_dir)
    return binding_path


def publish_refinement(quest_dir: str | Path, iteration: int) -> Path:
    """Bind validated Arbiter scratch output to the next Planner iteration."""

    root = Path(quest_dir).resolve()
    state_path = root / "state.json"
    with _lock_file(state_path) as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return _publish_refinement_locked(root, load_state(root), iteration)


def verify_refinement(quest_dir: str | Path, iteration: int) -> dict[str, object]:
    """Verify that current Planner iteration is bound to its sealed predecessor."""

    root = Path(quest_dir).resolve()
    state = load_state(root)
    if state.get("plan_iteration") != iteration:
        raise PlanIterationError("iteration_mismatch")
    predecessor = iteration - 1
    verify_plan_iteration_snapshot(root, predecessor)
    if state.get("quest_mode", "workflow") == "solo":
        return {
            "mode": "solo",
            "source_plan_iteration": predecessor,
            "requested_plan_iteration": iteration,
        }
    phase_dir = root / "phase_01_plan"
    binding = _read_json(phase_dir / "refinement_binding.json")
    if (
        binding.get("source_plan_iteration") != predecessor
        or binding.get("requested_plan_iteration") != iteration
    ):
        raise PlanIterationError("refinement_iteration_mismatch")
    verdict = _read_refinement_bytes(phase_dir / "arbiter_verdict.md")
    if binding.get("verdict_sha256") != _digest(verdict):
        raise PlanIterationError("refinement_verdict_mismatch")
    return binding
