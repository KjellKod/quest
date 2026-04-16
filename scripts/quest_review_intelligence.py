"""CLI wrapper for canonical review-intelligence helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quest_runtime.review_intelligence import (
    append_deferred_findings,
    build_review_backlog,
    merge_and_dedupe,
    scan_deferred_backlog,
    utc_now_iso,
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
    backlog = build_review_backlog(findings, at_loop_cap=args.at_loop_cap)
    _write_json(Path(args.output), backlog)
    print(json.dumps({"ok": True, "count": len(backlog["items"]), "output": args.output}, sort_keys=True))
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
    backlog.add_argument("--at-loop-cap", action="store_true", help="Apply loop-cap decision policy")
    backlog.set_defaults(func=_cmd_build_backlog)

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
