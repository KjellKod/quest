"""CLI wrapper for canonical review-intelligence helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quest_runtime.pr_review_cycle import (
    allowlist_path_from_context,
    build_fix_batches,
    classify_pr_loop_stop,
    normalize_pr_review_intake,
    retag_backlog_at_cap,
    select_validation_steps,
)
from quest_runtime.review_intelligence import (
    append_deferred_findings,
    build_review_backlog,
    merge_and_dedupe,
    scan_deferred_backlog,
    utc_now_iso,
    validate_plan_phase_defaults,
    validate_review_backlog,
    validate_findings,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_findings(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("findings"), list):
            return payload["findings"]
        if isinstance(payload.get("items"), list):
            return payload["items"]
    raise ValueError("expected findings JSON as a list or an object with findings/items")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _quest_id_from_backlog_path(backlog_path: Path) -> str:
    parts = backlog_path.parts
    if ".quest" in parts:
        quest_index = parts.index(".quest")
        if quest_index + 1 < len(parts):
            candidate = parts[quest_index + 1]
            if candidate and candidate != "backlog":
                return candidate
    return "unknown-quest"


def _deferred_jsonl_from_backlog(backlog_path: Path) -> Path:
    """Derive the repo-local deferred findings JSONL path from a backlog path.

    The backlog typically lives at ``<repo>/.quest/<quest-id>/phase_*/review_backlog.json``.
    The deferred reservoir is ``<repo>/.quest/backlog/deferred_findings.jsonl``.
    Walk up the backlog's ancestors to find the ``.quest`` directory and emit
    the sibling ``backlog/deferred_findings.jsonl`` under it. Falls back to a
    cwd-relative default if no ``.quest`` ancestor exists.
    """

    for ancestor in backlog_path.resolve().parents:
        if ancestor.name == ".quest":
            return ancestor / "backlog" / "deferred_findings.jsonl"
    return Path(".quest/backlog/deferred_findings.jsonl")


def _cmd_validate_findings(args: argparse.Namespace) -> int:
    findings = _extract_findings(_load_json(Path(args.input)))
    errors = validate_findings(findings)
    payload = {"ok": not errors, "count": len(findings), "errors": errors}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if errors else 0


def _cmd_merge_findings(args: argparse.Namespace) -> int:
    groups: list[list[dict[str, Any]]] = []
    for input_path in args.inputs:
        payload = _load_json(Path(input_path))
        groups.append(_extract_findings(payload))
    merged = merge_and_dedupe(groups)
    _write_json(Path(args.output), merged)
    print(json.dumps({"ok": True, "count": len(merged), "output": args.output}, sort_keys=True))
    return 0


def _cmd_build_backlog(args: argparse.Namespace) -> int:
    payload = _load_json(Path(args.findings))
    findings = _extract_findings(payload)
    backlog = build_review_backlog(
        findings,
        at_loop_cap=args.at_loop_cap,
        phase=args.phase,
    )
    _write_json(Path(args.output), backlog)
    print(json.dumps({"ok": True, "count": len(backlog["items"]), "output": args.output}, sort_keys=True))
    return 0


def _cmd_validate_backlog(args: argparse.Namespace) -> int:
    payload = _load_json(Path(args.input))
    errors = validate_review_backlog(payload)
    expected_phase = getattr(args, "expected_phase", None)
    if expected_phase:
        actual_phase = payload.get("phase") if isinstance(payload, dict) else None
        if actual_phase != expected_phase:
            errors = list(errors) + [
                f"expected phase='{expected_phase}' but backlog has phase='{actual_phase}'"
            ]
    if getattr(args, "strict_plan_defaults", False):
        errors = list(errors) + validate_plan_phase_defaults(payload)
    items = payload.get("items") if isinstance(payload, dict) else None
    item_count = len(items) if isinstance(items, list) else 0
    print(json.dumps({"ok": not errors, "count": item_count, "errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


def _cmd_normalize_pr_intake(args: argparse.Namespace) -> int:
    payload = _load_json(Path(args.input))
    if not isinstance(payload, dict):
        raise ValueError("expected intake JSON object")
    findings = normalize_pr_review_intake(payload)
    _write_json(Path(args.output), findings)
    print(json.dumps({"ok": True, "count": len(findings), "output": args.output}, sort_keys=True))
    return 0


def _cmd_select_batch_validation(args: argparse.Namespace) -> int:
    backlog_path = Path(args.backlog)
    payload = _load_json(backlog_path)
    if not isinstance(payload, dict):
        raise ValueError("backlog must be a JSON object")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("backlog JSON object must contain an 'items' list")

    inventory: dict[str, Any] | None = None
    if args.repo_inventory:
        inventory_payload = _load_json(Path(args.repo_inventory))
        if not isinstance(inventory_payload, dict):
            raise ValueError("repo inventory must be a JSON object")
        inventory = inventory_payload

    actionable_decisions = {"fix_now", "verify_first"}
    annotated = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("decision") not in actionable_decisions:
            continue
        item["validation_steps"] = select_validation_steps(
            item, repo_inventory=inventory
        )
        annotated += 1

    output_path = Path(args.output) if args.output else backlog_path
    _write_json(output_path, payload)
    print(
        json.dumps(
            {"ok": True, "annotated": annotated, "output": str(output_path)},
            sort_keys=True,
        )
    )
    return 0


def _cmd_build_fix_batches(args: argparse.Namespace) -> int:
    payload = _load_json(Path(args.backlog))
    if isinstance(payload, dict):
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("backlog JSON object must contain an 'items' list")
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("backlog must be a list or an object with an 'items' list")

    batches = build_fix_batches(items)
    _write_json(Path(args.output), batches)
    print(json.dumps({"ok": True, "count": len(batches), "output": args.output}, sort_keys=True))
    return 0


def _cmd_classify_pr_stop(args: argparse.Namespace) -> int:
    context_for_allowlist = Path(args.backlog) if args.backlog else None
    allowlist_path = allowlist_path_from_context(context_for_allowlist)
    classification = classify_pr_loop_stop(
        args.ci_state,
        args.actionable,
        args.iteration,
        cap=args.cap,
        allowlist_path=allowlist_path,
    )

    deferred_count = 0
    should_retag = bool(classification["stop"] and classification["retag_required"])
    if should_retag and args.backlog:
        backlog_path = Path(args.backlog)
        payload = _load_json(backlog_path)
        if not isinstance(payload, dict):
            raise ValueError("backlog must be a JSON object")

        existing_defer_ids = {
            str(item.get("finding_id") or "")
            for item in payload.get("items", [])
            if isinstance(item, dict) and item.get("decision") == "defer"
        }

        retagged = retag_backlog_at_cap(payload)
        deferred_items = [
            item
            for item in retagged.get("items", [])
            if isinstance(item, dict)
            and item.get("decision") == "defer"
            and str(item.get("finding_id") or "") not in existing_defer_ids
        ]
        if deferred_items:
            if args.deferred_jsonl is not None:
                deferred_path = Path(args.deferred_jsonl)
            else:
                deferred_path = _deferred_jsonl_from_backlog(backlog_path)

            lineage = {
                "deferred_by_quest": args.deferred_by_quest
                or _quest_id_from_backlog_path(backlog_path),
                "deferred_at": args.deferred_at or utc_now_iso(),
                "defer_reason": args.defer_reason,
                "proposed_followup": args.proposed_followup,
            }
            deferred_count = append_deferred_findings(
                deferred_path,
                deferred_items,
                lineage,
            )

        # Append deferred history first; append_deferred_findings is idempotent
        # per (deferred_by_quest, finding_id), so a retry after a later write
        # failure will not duplicate backlog lineage.
        _write_json(backlog_path, retagged)
        if args.retag_output:
            _write_json(Path(args.retag_output), retagged)

    payload = dict(classification)
    payload["deferred_count"] = deferred_count
    print(json.dumps(payload, sort_keys=True))
    return 0


def _cmd_append_deferred(args: argparse.Namespace) -> int:
    payload = _load_json(Path(args.findings))
    findings = _extract_findings(payload)

    if args.decision_filter:
        findings = [
            finding
            for finding in findings
            if isinstance(finding, dict) and finding.get("decision") == args.decision_filter
        ]

    lineage = {
        "deferred_by_quest": args.deferred_by_quest,
        "deferred_at": args.deferred_at or utc_now_iso(),
        "defer_reason": args.defer_reason,
        "proposed_followup": args.proposed_followup,
    }
    appended = append_deferred_findings(Path(args.jsonl), findings, lineage)
    print(json.dumps({"ok": True, "appended": appended, "jsonl": args.jsonl}, sort_keys=True))
    return 0


def _cmd_scan_backlog(args: argparse.Namespace) -> int:
    matches = scan_deferred_backlog(Path(args.jsonl), set(args.paths or []))
    if args.output:
        _write_json(Path(args.output), matches)
    print(json.dumps({"ok": True, "count": len(matches), "output": args.output}, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    normalize = subparsers.add_parser(
        "normalize-pr-intake",
        help="Normalize PR intake JSON into canonical findings",
    )
    normalize.add_argument("--input", required=True, help="PR intake JSON path")
    normalize.add_argument("--output", required=True, help="Path to normalized findings JSON")
    normalize.set_defaults(func=_cmd_normalize_pr_intake)

    validate = subparsers.add_parser("validate-findings", help="Validate canonical findings JSON")
    validate.add_argument("--input", required=True, help="Path to findings JSON file")
    validate.set_defaults(func=_cmd_validate_findings)

    merge = subparsers.add_parser("merge-findings", help="Merge and dedupe findings from multiple files")
    merge.add_argument("--inputs", nargs="+", required=True, help="Input findings JSON files")
    merge.add_argument("--output", required=True, help="Path to merged findings output JSON")
    merge.set_defaults(func=_cmd_merge_findings)

    backlog = subparsers.add_parser("build-backlog", help="Build review backlog from findings")
    backlog.add_argument("--findings", required=True, help="Input findings JSON file")
    backlog.add_argument("--output", required=True, help="Path to backlog output JSON")
    backlog.add_argument(
        "--phase",
        default="review",
        choices=["plan", "review"],
        help="Backlog decision policy phase (default: review)",
    )
    backlog.add_argument("--at-loop-cap", action="store_true", help="Apply loop-cap decision policy")
    backlog.set_defaults(func=_cmd_build_backlog)

    validate_backlog = subparsers.add_parser(
        "validate-backlog",
        help="Validate canonical review backlog JSON",
    )
    validate_backlog.add_argument("--input", required=True, help="Path to review backlog JSON file")
    validate_backlog.add_argument(
        "--expected-phase",
        choices=["plan", "review"],
        default=None,
        help=(
            "When set, also verify backlog['phase'] matches this value. "
            "A missing phase key or mismatch is reported as an error."
        ),
    )
    validate_backlog.add_argument(
        "--strict-plan-defaults",
        action="store_true",
        help=(
            "Also verify every item matches canonical build-backlog --phase "
            "plan defaults for decision, owner, and batch."
        ),
    )
    validate_backlog.set_defaults(func=_cmd_validate_backlog)

    select_validation = subparsers.add_parser(
        "select-batch-validation",
        help=(
            "For every actionable backlog item, select Level 0/1/2 "
            "validation_steps and persist them in place on the backlog. "
            "Must run before build-fix-batches so batching sees real "
            "validation signatures."
        ),
    )
    select_validation.add_argument(
        "--backlog", required=True, help="Input review_backlog.json path (updated in place unless --output is given)"
    )
    select_validation.add_argument(
        "--repo-inventory",
        default=None,
        help="Optional repo inventory JSON used by select_validation_steps",
    )
    select_validation.add_argument(
        "--output",
        default=None,
        help="Optional output path for the annotated backlog (default: overwrite --backlog)",
    )
    select_validation.set_defaults(func=_cmd_select_batch_validation)

    fix_batches = subparsers.add_parser(
        "build-fix-batches",
        help="Build non-overlapping actionable fix batches from backlog items",
    )
    fix_batches.add_argument("--backlog", required=True, help="Input review_backlog.json path")
    fix_batches.add_argument("--output", required=True, help="Path to fix-batches output JSON")
    fix_batches.set_defaults(func=_cmd_build_fix_batches)

    classify = subparsers.add_parser(
        "classify-pr-stop",
        help="Classify PR loop stop conditions and retag backlog at cap when required",
    )
    classify.add_argument(
        "--ci-state",
        required=True,
        choices=["green", "failing", "pending", "unknown"],
        help="Current CI state",
    )
    classify.add_argument("--actionable", required=True, type=int, help="Open actionable backlog count")
    classify.add_argument("--iteration", required=True, type=int, help="Current iteration number")
    classify.add_argument(
        "--cap",
        default=None,
        type=int,
        help="Iteration cap (default: allowlist gates.max_fix_iterations)",
    )
    classify.add_argument(
        "--backlog",
        default=None,
        help="Optional review_backlog.json path for in-place cap retagging",
    )
    classify.add_argument(
        "--retag-output",
        default=None,
        help="Optional path to write a copy of the retagged backlog",
    )
    classify.add_argument(
        "--deferred-jsonl",
        default=None,
        help=(
            "Deferred findings JSONL path (default: derived from --backlog, "
            "walking to the enclosing .quest/ dir and writing to "
            "<.quest>/backlog/deferred_findings.jsonl; falls back to "
            ".quest/backlog/deferred_findings.jsonl relative to cwd when no "
            "backlog is supplied)"
        ),
    )
    classify.add_argument(
        "--deferred-by-quest",
        default=None,
        help="Quest id used for deferred lineage (defaults from backlog path)",
    )
    classify.add_argument(
        "--deferred-at",
        default=None,
        help="ISO8601 UTC timestamp for deferred lineage (default: now)",
    )
    classify.add_argument(
        "--defer-reason",
        default="Loop cap reached during PR review cycle.",
        help="Deferred lineage reason",
    )
    classify.add_argument(
        "--proposed-followup",
        default="Create a follow-up quest to resolve deferred review findings.",
        help="Deferred lineage follow-up recommendation",
    )
    classify.set_defaults(func=_cmd_classify_pr_stop)

    append = subparsers.add_parser(
        "append-deferred",
        help="Append findings to deferred backlog JSONL with lineage fields",
    )
    append.add_argument("--findings", required=True, help="Findings or backlog JSON file")
    append.add_argument("--jsonl", required=True, help="Deferred backlog JSONL path")
    append.add_argument(
        "--decision-filter",
        choices=["defer"],
        default=None,
        help="Only append findings matching this decision",
    )
    append.add_argument("--deferred-by-quest", required=True, help="Quest id that deferred the findings")
    append.add_argument("--deferred-at", default=None, help="ISO8601 UTC timestamp (default: now)")
    append.add_argument("--defer-reason", required=True, help="Reason for deferral")
    append.add_argument("--proposed-followup", required=True, help="Follow-up recommendation")
    append.set_defaults(func=_cmd_append_deferred)

    scan = subparsers.add_parser("scan-backlog", help="Scan deferred backlog for exact write_scope matches")
    scan.add_argument("--jsonl", required=True, help="Deferred backlog JSONL path")
    scan.add_argument(
        "--paths",
        nargs="*",
        required=True,
        help="Candidate paths to match exactly (empty list is valid)",
    )
    scan.add_argument("--output", default=None, help="Optional output JSON path for matches")
    scan.set_defaults(func=_cmd_scan_backlog)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
