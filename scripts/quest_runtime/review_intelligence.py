"""Canonical review-finding helpers for Quest review-intelligence workflows."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_FINDING_FIELDS: tuple[str, ...] = (
    "finding_id",
    "source",
    "kind",
    "severity",
    "confidence",
    "path",
    "line",
    "summary",
    "why_it_matters",
    "evidence",
    "action",
    "needs_test",
    "write_scope",
    "related_acceptance_criteria",
)

ALLOWED_SEVERITIES = ("critical", "high", "medium", "low", "info")
ALLOWED_CONFIDENCE = ("high", "medium", "low")
ALLOWED_DECISIONS = (
    "fix_now",
    "verify_first",
    "defer",
    "drop",
    "needs_human_decision",
)

_SEVERITY_RANK = {name: index for index, name in enumerate(ALLOWED_SEVERITIES)}
_CONFIDENCE_RANK = {name: index for index, name in enumerate(ALLOWED_CONFIDENCE)}


def utc_now_iso() -> str:
    """Return a UTC ISO-8601 timestamp with a trailing Z."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _normalize_summary(value: str) -> str:
    return " ".join(value.lower().split())


def _is_string_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return all(isinstance(item, str) for item in value)


def _severity_rank(value: str) -> int:
    return _SEVERITY_RANK.get(value, -1)


def _confidence_rank(value: str) -> int:
    return _CONFIDENCE_RANK.get(value, -1)


def _dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    line_value = finding.get("line")
    line_part = "" if line_value is None else str(line_value)
    return (
        str(finding.get("path", "")),
        line_part,
        str(finding.get("kind", "")),
        _normalize_summary(str(finding.get("summary", ""))),
    )


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def validate_finding(finding: dict[str, Any]) -> list[str]:
    """Validate one canonical finding and return deterministic error strings."""

    errors: list[str] = []
    if not isinstance(finding, dict):
        return ["finding must be an object"]

    for field in REQUIRED_FINDING_FIELDS:
        if field not in finding:
            errors.append(f"missing required field '{field}'")

    if errors:
        return errors

    string_fields = (
        "finding_id",
        "source",
        "kind",
        "severity",
        "confidence",
        "path",
        "summary",
        "why_it_matters",
        "action",
    )
    for field in string_fields:
        value = finding.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"field '{field}' must be a non-empty string")

    line_value = finding.get("line")
    if line_value is not None and (isinstance(line_value, bool) or not isinstance(line_value, int) or line_value < 1):
        errors.append("field 'line' must be null or an integer >= 1")

    if not isinstance(finding.get("needs_test"), bool):
        errors.append("field 'needs_test' must be a boolean")

    list_fields = ("evidence", "write_scope", "related_acceptance_criteria")
    for field in list_fields:
        value = finding.get(field)
        if not _is_string_list(value):
            errors.append(f"field '{field}' must be a list[str]")

    severity_value = finding.get("severity")
    if severity_value not in ALLOWED_SEVERITIES:
        errors.append(
            f"field 'severity' must be one of {', '.join(ALLOWED_SEVERITIES)}"
        )

    confidence_value = finding.get("confidence")
    if confidence_value not in ALLOWED_CONFIDENCE:
        errors.append(
            f"field 'confidence' must be one of {', '.join(ALLOWED_CONFIDENCE)}"
        )

    return errors


def validate_findings(findings: list[dict[str, Any]]) -> list[str]:
    """Validate a list of canonical findings and return indexed errors."""

    if not isinstance(findings, list):
        return ["findings must be a list"]

    errors: list[str] = []
    for index, finding in enumerate(findings):
        for error in validate_finding(finding):
            errors.append(f"[{index}] {error}")
    return errors


def merge_and_dedupe(findings_by_source: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge findings from multiple reviewers and dedupe by canonical key."""

    flattened: list[dict[str, Any]] = []
    for source_findings in findings_by_source:
        if not source_findings:
            continue
        flattened.extend(copy.deepcopy(source_findings))

    validation_errors = validate_findings(flattened)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    merged_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for finding in flattened:
        key = _dedupe_key(finding)
        existing = merged_by_key.get(key)
        if existing is None:
            candidate = copy.deepcopy(finding)
            candidate["source_lineage"] = [candidate["source"]]
            candidate["finding_id_lineage"] = [candidate["finding_id"]]
            merged_by_key[key] = candidate
            continue

        if _severity_rank(finding["severity"]) < _severity_rank(existing["severity"]):
            existing["severity"] = finding["severity"]

        if _confidence_rank(finding["confidence"]) < _confidence_rank(existing["confidence"]):
            existing["confidence"] = finding["confidence"]

        existing["needs_test"] = bool(existing["needs_test"] or finding["needs_test"])

        existing["evidence"] = _unique_strings(
            list(existing["evidence"]) + list(finding["evidence"])
        )
        existing["write_scope"] = _unique_strings(
            list(existing["write_scope"]) + list(finding["write_scope"])
        )
        existing["related_acceptance_criteria"] = _unique_strings(
            list(existing["related_acceptance_criteria"])
            + list(finding["related_acceptance_criteria"])
        )

        source_lineage = list(existing.get("source_lineage", []))
        source_lineage.append(finding["source"])
        existing["source_lineage"] = _unique_strings(source_lineage)

        finding_id_lineage = list(existing.get("finding_id_lineage", []))
        finding_id_lineage.append(finding["finding_id"])
        existing["finding_id_lineage"] = _unique_strings(finding_id_lineage)

        if len(existing["source_lineage"]) > 1:
            existing["source"] = "+".join(existing["source_lineage"])

    return list(merged_by_key.values())


def _owner_from_finding(finding: dict[str, Any]) -> str:
    if isinstance(finding.get("write_scope"), list) and finding["write_scope"]:
        first_scope = sorted(finding["write_scope"])[0]
        return first_scope.split("/", 1)[0] or "builder_agent"
    return "builder_agent"


def _batch_from_finding(finding: dict[str, Any]) -> str:
    if isinstance(finding.get("write_scope"), list) and finding["write_scope"]:
        return sorted(finding["write_scope"])[0]
    if isinstance(finding.get("path"), str) and finding["path"]:
        return finding["path"]
    return "misc"


def select_decision(finding: dict[str, Any], *, at_loop_cap: bool) -> dict[str, Any]:
    """Select a deterministic backlog decision for one finding."""

    errors = validate_finding(finding)
    if errors:
        raise ValueError("; ".join(errors))

    severity = finding["severity"]
    confidence = finding["confidence"]
    evidence_count = len(finding["evidence"])

    if at_loop_cap:
        if severity in {"critical", "high"} and confidence == "high":
            decision = "needs_human_decision"
            reason = "Loop cap reached with high-severity/high-confidence risk."
        else:
            decision = "defer"
            reason = "Loop cap reached; deferred with accepted debt rationale."
    else:
        if severity in {"critical", "high"} and confidence == "high":
            decision = "fix_now"
            reason = "High-severity and high-confidence finding."
        elif severity in {"critical", "high"}:
            decision = "verify_first"
            reason = "High-severity finding needs verification before fixing."
        elif confidence == "low" or evidence_count <= 1:
            decision = "verify_first"
            reason = "Evidence or confidence is limited and needs verification."
        elif severity == "medium":
            decision = "verify_first"
            reason = "Medium severity should be reproduced before code changes."
        elif severity in {"low", "info"} and confidence == "high":
            decision = "drop"
            reason = "Low-risk finding with low expected value for immediate work."
        else:
            decision = "defer"
            reason = "Non-urgent finding deferred for later follow-up."

    decision_confidence = confidence
    needs_validation: list[str] = []
    if finding["needs_test"]:
        needs_validation.append("unit_test")
    if decision in {"fix_now", "verify_first"}:
        needs_validation.append("typecheck")
        needs_validation.append("lint")

    return {
        "decision": decision,
        "decision_confidence": decision_confidence,
        "reason": reason,
        "needs_validation": needs_validation,
        "owner": _owner_from_finding(finding),
        "batch": _batch_from_finding(finding),
    }


def build_review_backlog(
    findings: list[dict[str, Any]],
    *,
    at_loop_cap: bool,
) -> dict[str, Any]:
    """Build canonical review backlog entries from findings."""

    merged = merge_and_dedupe([findings])
    items: list[dict[str, Any]] = []
    counts = {decision: 0 for decision in ALLOWED_DECISIONS}

    for finding in merged:
        decision_data = select_decision(finding, at_loop_cap=at_loop_cap)
        item = copy.deepcopy(finding)
        item.update(decision_data)
        items.append(item)
        counts[decision_data["decision"]] += 1

    return {
        "version": 1,
        "generated_at": utc_now_iso(),
        "at_loop_cap": at_loop_cap,
        "allowed_decisions": list(ALLOWED_DECISIONS),
        "counts": counts,
        "items": items,
    }


def append_deferred_findings(
    jsonl_path: Path,
    findings: list[dict[str, Any]],
    lineage: dict[str, Any],
) -> int:
    """Append deferred findings with lineage to an append-only JSONL backlog."""

    required_lineage = (
        "deferred_by_quest",
        "deferred_at",
        "defer_reason",
        "proposed_followup",
    )
    missing = [field for field in required_lineage if field not in lineage]
    if missing:
        raise ValueError(f"lineage missing required fields: {', '.join(missing)}")

    validation_errors = validate_findings(findings)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    target = Path(jsonl_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with target.open("a", encoding="utf-8") as handle:
        for finding in findings:
            record = copy.deepcopy(finding)
            for field in required_lineage:
                record[field] = lineage[field]
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            written += 1
    return written


def scan_deferred_backlog(
    jsonl_path: Path,
    candidate_paths: set[str],
) -> list[dict[str, Any]]:
    """Return deferred backlog entries whose write_scope intersects candidate paths."""

    target = Path(jsonl_path)
    if not target.exists():
        return []

    normalized_paths = {path.strip() for path in candidate_paths if path and path.strip()}
    if not normalized_paths:
        return []

    matches: list[dict[str, Any]] = []
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        write_scope = record.get("write_scope", [])
        if isinstance(write_scope, str):
            scope_values = [write_scope]
        elif isinstance(write_scope, list):
            scope_values = [value for value in write_scope if isinstance(value, str)]
        else:
            scope_values = []

        if any(scope in normalized_paths for scope in scope_values):
            matches.append(record)
    return matches


_SEVERITY_RE = re.compile(r"\b(critical|high|medium|low|info)\b", flags=re.IGNORECASE)
_PATH_RE = re.compile(
    r"([A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)(?::(\d+))?"
)


def synthesize_findings_from_review_markdown(
    review_markdown: str,
    *,
    source: str,
    default_path: str = "phase_01_plan/plan.md",
) -> list[dict[str, Any]]:
    """Heuristically map review markdown bullets into canonical findings."""

    findings: list[dict[str, Any]] = []
    for line in review_markdown.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not (
            stripped.startswith("- ")
            or stripped.startswith("* ")
            or re.match(r"^\d+\.\s+", stripped)
        ):
            continue

        normalized = re.sub(r"^[-*]\s+|^\d+\.\s+", "", stripped).strip()
        if len(normalized) < 8:
            continue

        severity_match = _SEVERITY_RE.search(normalized)
        severity = severity_match.group(1).lower() if severity_match else "medium"

        path_match = _PATH_RE.search(normalized)
        finding_path = default_path
        line_number: int | None = None
        write_scope = [default_path]
        if path_match:
            finding_path = path_match.group(1)
            line_token = path_match.group(2)
            line_number = int(line_token) if line_token else None
            write_scope = [finding_path]

        index = len(findings) + 1
        findings.append(
            {
                "finding_id": f"{source}-{index:03d}",
                "source": source,
                "kind": "plan_review",
                "severity": severity,
                "confidence": "medium",
                "path": finding_path,
                "line": line_number,
                "summary": normalized,
                "why_it_matters": "Potential issue surfaced during plan review.",
                "evidence": [normalized],
                "action": "Confirm and adjust the plan if required.",
                "needs_test": False,
                "write_scope": write_scope,
                "related_acceptance_criteria": [],
            }
        )
    return findings


def synthesize_plan_review_findings(
    review_a_markdown: str,
    review_b_markdown: str,
) -> list[dict[str, Any]]:
    """Synthesize canonical plan findings from dual reviewer markdown inputs."""

    findings_a = synthesize_findings_from_review_markdown(
        review_a_markdown,
        source="plan-reviewer-a",
    )
    findings_b = synthesize_findings_from_review_markdown(
        review_b_markdown,
        source="plan-reviewer-b",
    )
    return merge_and_dedupe([findings_a, findings_b])
