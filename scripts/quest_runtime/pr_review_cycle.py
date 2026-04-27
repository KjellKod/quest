"""PR review-cycle helpers for canonical intake, batching, validation, and stop logic."""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath

from quest_runtime.review_intelligence import (
    ALLOWED_DECISIONS,
    _batch_from_finding,
    merge_and_dedupe,
    review_local_index_from_value,
    select_decision,
    validate_findings,
)

INTAKE_SOURCES = ("ci_check", "inline_comment", "general_comment", "existing_finding")
BLOCKER_KEYWORDS = ("blocker", "blocking", "critical")
_BLOCKER_TOKEN_STRIP = ".,:;!?()[]{}\"'"
FALLBACK_LOOP_CAP = 3
_ALLOWLIST_PATH = Path(".ai/allowlist.json")
CI_GREEN_STATES = ("green",)
CI_FAILURE_STATES = (
    "failing",
    "failure",
    "failed",
    "error",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
)

JsonObject = dict[str, object]


def allowlist_path_from_context(context_path: Path | None) -> Path:
    """Find ``.ai/allowlist.json`` in the enclosing repo of ``context_path``.

    Walks up from ``context_path`` (a path known to live inside the target
    repo, typically the backlog or a quest artifact) and returns the first
    ancestor that contains ``.ai/allowlist.json``. Falls back to the
    module-level cwd-relative default when no context is given or no
    enclosing repo is found.
    """

    if context_path is None:
        return _ALLOWLIST_PATH
    try:
        resolved = context_path.resolve()
    except (OSError, RuntimeError):
        return _ALLOWLIST_PATH
    # Include the resolved path itself in the candidate chain so passing a
    # directory (e.g. the repo root) finds .ai/allowlist.json at that level,
    # not only under ancestors above it.
    for ancestor in [resolved, *resolved.parents]:
        candidate = ancestor / ".ai" / "allowlist.json"
        if candidate.exists():
            return candidate
    return _ALLOWLIST_PATH


def resolve_loop_cap(allowlist_path: Path | None = None) -> int:
    """Resolve the PR fix-loop cap from the allowlist; fall back to FALLBACK_LOOP_CAP."""

    path = allowlist_path if allowlist_path is not None else _ALLOWLIST_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FALLBACK_LOOP_CAP
    gates = data.get("gates") if isinstance(data, dict) else None
    if not isinstance(gates, dict):
        return FALLBACK_LOOP_CAP
    value = gates.get("max_fix_iterations")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return FALLBACK_LOOP_CAP
    return value

_ACTIONABLE_DECISIONS = {"fix_now", "verify_first"}
_SHARED_INFRA_KINDS = {"build_failure", "shared_infrastructure", "cross_cutting"}
_SHARED_SCOPE_PREFIXES = ("scripts/quest_runtime/", ".skills/", "docs/architecture/")


def _as_dict_list(value: object, *, field_name: str) -> list[JsonObject]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"'{field_name}' must be a list")
    result: list[JsonObject] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValueError(f"'{field_name}[{index}]' must be an object")
        result.append(entry)
    return result


def _first_200_chars(text: str) -> str:
    return text[:200]


def _finding_line(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _copy_review_local_index(source: JsonObject, target: JsonObject) -> None:
    index = review_local_index_from_value(source.get("review_local_index"))
    if index is not None:
        target["review_local_index"] = index


def _normalize_scope_entry(value: str) -> str:
    trimmed = value.strip().strip("/")
    if not trimmed:
        return ""
    return trimmed


def normalize_pr_review_intake(intake: JsonObject) -> list[JsonObject]:
    """Normalize heterogeneous PR intake into canonical findings and merge existing findings."""

    if not isinstance(intake, dict):
        raise ValueError("intake must be an object")

    ci_checks = _as_dict_list(intake.get("ci_checks"), field_name="ci_checks")
    inline_comments = _as_dict_list(intake.get("inline_comments"), field_name="inline_comments")
    general_comments = _as_dict_list(intake.get("general_comments"), field_name="general_comments")
    existing_findings = _as_dict_list(intake.get("existing_findings"), field_name="existing_findings")

    existing_errors = validate_findings(existing_findings)
    if existing_errors:
        raise ValueError("; ".join(existing_errors))

    normalized_findings: list[JsonObject] = []
    ci_counter = 0
    inline_counter = 0
    general_counter = 0

    for check in ci_checks:
        job = str(check.get("job") or "unknown-job").strip() or "unknown-job"
        state = str(check.get("state") or "unknown").strip().lower() or "unknown"
        if state not in CI_FAILURE_STATES:
            # Skip green, pending, in-progress, unknown, and any other
            # non-actionable state. Only confirmed failures become findings;
            # transient/unknown states should not produce fix_now work.
            continue

        ci_counter += 1
        kind_hint = str(check.get("kind_hint") or "test_failure").strip()
        if kind_hint not in {"test_failure", "build_failure"}:
            kind_hint = "test_failure"

        failed_path_raw = check.get("failed_path")
        failed_path = (
            str(failed_path_raw).strip()
            if isinstance(failed_path_raw, str) and failed_path_raw.strip()
            else ""
        )
        path = failed_path or "ci/unknown"
        write_scope = [failed_path] if failed_path else []

        normalized_findings.append(
            {
                "finding_id": f"pr-ci-{ci_counter:03d}",
                "source": f"pr-ci:{job}",
                "kind": kind_hint,
                "severity": "high",
                "confidence": "high",
                "path": path,
                "line": None,
                "summary": f"CI check '{job}' reported state '{state}'.",
                "why_it_matters": "A non-green CI check indicates unresolved build or test risk.",
                "evidence": [f"ci:{job} state={state}"],
                "action": "Fix the failing CI check.",
                "needs_test": kind_hint == "test_failure",
                "write_scope": write_scope,
                "related_acceptance_criteria": [],
            }
        )

    for comment in inline_comments:
        inline_counter += 1
        commenter = str(comment.get("commenter") or "unknown-reviewer").strip()
        commenter = commenter or "unknown-reviewer"
        body = str(comment.get("body") or "").strip()
        path = str(comment.get("path") or "").strip() or "pr/inline"
        line = _finding_line(comment.get("line"))
        body_lower = body.lower()
        tokens = {
            token.strip(_BLOCKER_TOKEN_STRIP)
            for token in body_lower.split()
        }
        severity = "high" if tokens & set(BLOCKER_KEYWORDS) else "medium"
        summary = body[:120].strip() or f"Inline review feedback from {commenter}."

        finding: JsonObject = {
            "finding_id": f"pr-inline-{inline_counter:03d}",
            "source": f"pr-inline:{commenter}",
            "kind": "review_comment",
            "severity": severity,
            "confidence": "medium",
            "path": path,
            "line": line,
            "summary": summary,
            "why_it_matters": "Unaddressed inline feedback can leave review concerns unresolved.",
            "evidence": [_first_200_chars(body)],
            "action": "Address reviewer feedback.",
            "needs_test": severity == "high",
            "write_scope": [path],
            "related_acceptance_criteria": [],
        }
        _copy_review_local_index(comment, finding)
        normalized_findings.append(finding)

    for comment in general_comments:
        general_counter += 1
        commenter = str(comment.get("commenter") or "unknown-reviewer").strip()
        commenter = commenter or "unknown-reviewer"
        body = str(comment.get("body") or "").strip()
        summary = body[:120].strip() or f"General PR feedback from {commenter}."

        finding = {
            "finding_id": f"pr-general-{general_counter:03d}",
            "source": f"pr-general:{commenter}",
            "kind": "review_comment",
            "severity": "medium",
            "confidence": "low",
            "path": "pr/general",
            "line": None,
            "summary": summary,
            "why_it_matters": "General PR comments can signal unresolved quality or scope concerns.",
            "evidence": [_first_200_chars(body)],
            "action": "Address reviewer feedback.",
            "needs_test": False,
            "write_scope": [],
            "related_acceptance_criteria": [],
        }
        _copy_review_local_index(comment, finding)
        normalized_findings.append(finding)

    return merge_and_dedupe([normalized_findings, existing_findings])


def _validation_steps_from_item(item: JsonObject) -> list[JsonObject]:
    raw_steps = item.get("validation_steps")
    if not isinstance(raw_steps, list):
        return []

    steps: list[JsonObject] = []
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        level_raw = step.get("level")
        level = level_raw if isinstance(level_raw, int) and not isinstance(level_raw, bool) else 0
        target = str(step.get("target") or "").strip()
        command = str(step.get("command") or "").strip()
        steps.append({"level": level, "target": target, "command": command})
    return steps


def _validation_scope_signature(item: JsonObject) -> tuple[tuple[int, str, str], ...]:
    steps = _validation_steps_from_item(item)
    return tuple((step["level"], step["target"], step["command"]) for step in steps)


def _scope_entries(item: JsonObject) -> list[str]:
    raw_scope = item.get("write_scope")
    if not isinstance(raw_scope, list):
        return []
    normalized: list[str] = []
    for value in raw_scope:
        if not isinstance(value, str):
            continue
        candidate = _normalize_scope_entry(value)
        if candidate:
            normalized.append(candidate)
    return normalized


def _path_is_prefix(prefix: str, candidate: str) -> bool:
    return prefix == candidate or candidate.startswith(prefix + "/")


def _write_scopes_overlap(scope_a: list[str], scope_b: list[str]) -> bool:
    if not scope_a or not scope_b:
        return False
    for path_a in scope_a:
        for path_b in scope_b:
            if _path_is_prefix(path_a, path_b) or _path_is_prefix(path_b, path_a):
                return True
    return False


def _min_finding_id(items: list[JsonObject]) -> str:
    if not items:
        return ""
    finding_ids = [str(item.get("finding_id") or "") for item in items]
    return min(finding_ids)


def build_fix_batches(backlog_items: list[JsonObject]) -> list[JsonObject]:
    """Group actionable backlog items into deterministic non-overlapping fix batches."""

    grouped: dict[
        tuple[str, tuple[tuple[int, str, str], ...], str], list[JsonObject]
    ] = {}

    for item in backlog_items:
        if not isinstance(item, dict):
            continue
        decision = item.get("decision")
        if decision not in _ACTIONABLE_DECISIONS:
            continue

        batch_key = _batch_from_finding(item)
        signature = _validation_scope_signature(item)
        unknown_scope_bucket = (
            str(item.get("finding_id") or "") if not signature else ""
        )
        group_key = (batch_key, signature, unknown_scope_bucket)
        grouped.setdefault(group_key, []).append(copy.deepcopy(item))

    batches: list[JsonObject] = []
    for (batch_key, signature, _unknown_scope_bucket), items in grouped.items():
        sorted_items = sorted(items, key=lambda value: str(value.get("finding_id") or ""))
        partitions: list[list[JsonObject]] = []

        for item in sorted_items:
            item_scope = _scope_entries(item)
            placed = False
            for partition in partitions:
                if any(
                    _write_scopes_overlap(item_scope, _scope_entries(existing))
                    for existing in partition
                ):
                    continue
                partition.append(item)
                placed = True
                break
            if not placed:
                partitions.append([item])

        for index, partition in enumerate(partitions, start=1):
            batch_id = batch_key if len(partitions) == 1 else f"{batch_key}-{index}"
            batches.append(
                {
                    "batch_id": batch_id,
                    "batch_key": batch_key,
                    "validation_scope": [
                        {"level": level, "target": target, "command": command}
                        for (level, target, command) in signature
                    ],
                    "items": sorted(
                        partition,
                        key=lambda value: str(value.get("finding_id") or ""),
                    ),
                }
            )

    batches.sort(key=lambda batch: (str(batch["batch_key"]), _min_finding_id(batch["items"])))
    return batches


def _inventory_command(repo_inventory: JsonObject | None, *keys: str) -> str | None:
    if not isinstance(repo_inventory, dict):
        return None

    for key in keys:
        value = repo_inventory.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    commands = repo_inventory.get("commands")
    if isinstance(commands, dict):
        for key in keys:
            value = commands.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _repo_inventory_test_paths(repo_inventory: JsonObject | None) -> list[str]:
    if isinstance(repo_inventory, dict):
        for key in ("test_paths", "tests", "test_inventory"):
            value = repo_inventory.get(key)
            if isinstance(value, list):
                paths = [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
                if paths:
                    return sorted(set(paths))

    tests_dir = Path("tests")
    if not tests_dir.exists():
        return []
    discovered = {
        str(path.as_posix())
        for path in tests_dir.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    }
    return sorted(discovered)


def _normalize_repo_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _is_test_path(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    name = PurePosixPath(normalized).name
    return normalized.endswith(".py") and (
        name.startswith("test_") or name.endswith("_test.py")
    )


def _candidate_source_paths(finding: JsonObject) -> list[str]:
    paths: list[str] = []
    write_scope = finding.get("write_scope")
    if isinstance(write_scope, list):
        for raw in write_scope:
            if isinstance(raw, str) and raw.strip():
                paths.append(_normalize_repo_path(raw))

    path_value = finding.get("path")
    if isinstance(path_value, str) and path_value.strip():
        paths.append(_normalize_repo_path(path_value))

    unique: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _explicit_test_targets(finding: JsonObject) -> list[str]:
    targets: list[str] = []
    suggested = finding.get("suggested_test")
    if isinstance(suggested, str) and suggested.strip():
        targets.append(_normalize_repo_path(suggested))

    for path in _candidate_source_paths(finding):
        if _is_test_path(path):
            targets.append(path)

    unique: list[str] = []
    seen: set[str] = set()
    for target in targets:
        if target and target not in seen:
            seen.add(target)
            unique.append(target)
    return unique


def _nearest_test_targets(finding: JsonObject, test_paths: list[str]) -> list[str]:
    normalized_test_paths = [_normalize_repo_path(path) for path in test_paths]
    by_dir: dict[str, list[str]] = {}
    for test_path in normalized_test_paths:
        directory = str(PurePosixPath(test_path).parent)
        by_dir.setdefault(directory, []).append(test_path)

    for paths in by_dir.values():
        paths.sort()

    for source_path in _candidate_source_paths(finding):
        source_dir = str(PurePosixPath(source_path).parent)
        current: PurePosixPath | None = PurePosixPath(source_dir or ".")
        while current is not None:
            current_dir = "" if str(current) == "." else str(current)
            mirrored_prefix = f"tests/{current_dir}" if current_dir else ""
            if mirrored_prefix:
                mirrored_matches = [
                    path
                    for path in normalized_test_paths
                    if path.startswith(mirrored_prefix + "/")
                ]
                mirrored_matches = [
                    path for path in mirrored_matches if _is_test_path(path)
                ]
                if mirrored_matches:
                    return sorted(set(mirrored_matches))

            same_dir_matches = [
                path for path in by_dir.get(current_dir or ".", []) if _is_test_path(path)
            ]
            if same_dir_matches:
                return sorted(set(same_dir_matches))

            parent = current.parent
            if parent == current or str(parent) == ".":
                break
            current = parent

    return []


def _scope_intersects_shared_boundary(scope_path: str) -> bool:
    normalized = _normalize_repo_path(scope_path)
    if not normalized:
        return False
    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in _SHARED_SCOPE_PREFIXES
    ):
        return True
    if normalized.startswith("src/"):
        remainder = normalized[len("src/") :].strip("/")
        return bool(remainder) and "/" not in remainder
    return False


def select_validation_steps(
    finding: JsonObject,
    *,
    repo_inventory: JsonObject | None = None,
) -> list[JsonObject]:
    """Select ordered validation steps for one finding."""

    errors = validate_findings([finding])
    if errors:
        raise ValueError("; ".join(errors))

    steps: list[JsonObject] = []
    has_inventory = isinstance(repo_inventory, dict)
    pytest_cmd = _inventory_command(repo_inventory, "pytest_command", "pytest") or "python3 -m pytest"

    level0_config = (
        ("format", "format_command"),
        ("lint", "lint_command"),
        ("typecheck", "typecheck_command"),
    )
    for guard_name, command_key in level0_config:
        command = _inventory_command(repo_inventory, command_key, guard_name)
        if command:
            reason = f"Level 0 {guard_name} guard from repo inventory."
        elif has_inventory:
            command = "true"
            reason = (
                f"Level 0 {guard_name} guard configured as passthrough because repo "
                "inventory does not declare a command."
            )
        else:
            command = "true"
            reason = (
                f"Level 0 {guard_name} guard configured as passthrough because repo "
                "inventory is unavailable."
            )
        steps.append(
            {"level": 0, "target": ".", "command": command, "reason": reason}
        )

    level1_found = False
    explicit_targets = _explicit_test_targets(finding)
    if explicit_targets:
        for target in explicit_targets:
            steps.append(
                {
                    "level": 1,
                    "target": target,
                    "command": f"{pytest_cmd} {target}",
                    "reason": "Level 1 selected from explicit test target on the finding.",
                }
            )
        level1_found = True
    else:
        test_paths = _repo_inventory_test_paths(repo_inventory)
        nearest_targets = _nearest_test_targets(finding, test_paths)
        if nearest_targets:
            for target in nearest_targets:
                steps.append(
                    {
                        "level": 1,
                        "target": target,
                        "command": f"{pytest_cmd} {target}",
                        "reason": "Level 1 selected nearest mirrored/sibling tests.",
                    }
                )
            level1_found = True
        else:
            module_target = (
                _inventory_command(
                    repo_inventory,
                    "module_tests_target",
                    "module_test_target",
                )
                or "tests/unit/"
            )
            steps.append(
                {
                    "level": 1,
                    "target": module_target,
                    "command": f"{pytest_cmd} {module_target}",
                    "reason": "Level 1 fell back to module-level tests because no nearer tests were found.",
                }
            )
            level1_found = True

    finding_kind = str(finding.get("kind") or "").strip().lower()
    write_scope = _scope_entries(finding)
    shared_boundary_flag = finding.get("shared_boundary") is True
    shared_scope_trigger = any(
        _scope_intersects_shared_boundary(path) for path in write_scope
    )
    missing_level1_with_test_need = bool(finding.get("needs_test")) and not level1_found

    if (
        finding_kind in _SHARED_INFRA_KINDS
        or shared_scope_trigger
        or shared_boundary_flag
        or missing_level1_with_test_need
    ):
        level2_target = _inventory_command(
            repo_inventory, "level2_tests_target", "level2_target"
        ) or "tests/"
        level2_command = _inventory_command(
            repo_inventory, "level2_command", "broad_test_command"
        ) or f"{pytest_cmd} {level2_target}"

        trigger_reason = "shared-scope changes"
        if finding_kind in _SHARED_INFRA_KINDS:
            trigger_reason = "shared infrastructure kind"
        elif shared_boundary_flag:
            trigger_reason = "explicit shared boundary flag"
        elif missing_level1_with_test_need:
            trigger_reason = "needs_test with no level-1 tests found"

        steps.append(
            {
                "level": 2,
                "target": level2_target,
                "command": level2_command,
                "reason": f"Level 2 selected due to {trigger_reason}.",
            }
        )

    return steps


def classify_pr_loop_stop(
    ci_state: str,
    actionable_count: int,
    iteration: int,
    *,
    cap: int | None = None,
    allowlist_path: Path | None = None,
) -> JsonObject:
    """Classify whether the PR fix loop should stop and whether retagging is required.

    When ``cap`` is ``None`` the value is resolved from the allowlist at
    ``allowlist_path`` (``gates.max_fix_iterations``), falling back to
    ``FALLBACK_LOOP_CAP``. When ``allowlist_path`` is ``None`` the module
    default (``.ai/allowlist.json`` relative to cwd) is used; callers that
    know the target repo context should pass an explicit path (see
    ``allowlist_path_from_context``) so cap enforcement honors that repo's
    configured gate regardless of cwd.
    """

    normalized_state = (ci_state or "").strip().lower()
    if normalized_state not in {"green", "failing", "pending", "unknown"}:
        normalized_state = "unknown"

    actionable = max(0, int(actionable_count))
    current_iteration = max(0, int(iteration))
    resolved_cap = cap if cap is not None else resolve_loop_cap(allowlist_path)
    max_iterations = max(1, int(resolved_cap))

    if normalized_state == "green" and actionable == 0 and current_iteration <= max_iterations:
        return {
            "stop": True,
            "outcome": "success",
            "reason": "CI is green and no actionable backlog items remain.",
            "retag_required": False,
        }

    if current_iteration >= max_iterations:
        retag_required = actionable > 0
        reason = "Iteration cap reached; enforce loop cap policy."
        if current_iteration > max_iterations:
            reason = "Iteration cap exceeded; enforce loop cap policy."
        if retag_required:
            reason += " Actionable findings must be retagged."
        return {
            "stop": True,
            "outcome": "cap_enforced",
            "reason": reason,
            "retag_required": retag_required,
        }

    return {
        "stop": False,
        "outcome": "continue",
        "reason": "Continue loop: CI/actionable state has not met a stop condition.",
        "retag_required": False,
    }


def retag_backlog_at_cap(backlog: JsonObject) -> JsonObject:
    """Retag actionable backlog entries using loop-cap decision policy."""

    if not isinstance(backlog, dict):
        raise ValueError("backlog must be an object")

    items = backlog.get("items")
    if not isinstance(items, list):
        raise ValueError("backlog.items must be a list")

    counts = {decision: 0 for decision in ALLOWED_DECISIONS}

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("decision") in _ACTIONABLE_DECISIONS:
            decision_fields = select_decision(item, at_loop_cap=True)
            item.update(decision_fields)

        decision = item.get("decision")
        if isinstance(decision, str) and decision in counts:
            counts[decision] += 1

    backlog["counts"] = counts
    backlog["at_loop_cap"] = True
    return backlog
