#!/usr/bin/env python3
"""Collect compact records-shaped PR intake for shepherding."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from quest_runtime.pr_shepherd import (
    SUMMARY_MARKER,
    activity_state,
    has_marker,
    stable_fingerprint,
)

PER_PAGE = 100
CHECK_FAILURE_STATES = {
    "action_required",
    "cancelled",
    "error",
    "failure",
    "failed",
    "stale",
    "startup_failure",
    "timed_out",
}


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def _gh_json(args: list[str]) -> tuple[Any | None, str]:
    result = _run(args)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()[:500]
    try:
        return json.loads(result.stdout or "null"), ""
    except json.JSONDecodeError as exc:
        return None, str(exc)


def _gh_api_page(endpoint: str, page: int) -> tuple[Any | None, str]:
    return _gh_json(
        ["gh", "api", endpoint, "--method", "GET", "-F", f"per_page={PER_PAGE}", "-F", f"page={page}"]
    )


def _collect_paginated(endpoint: str, *, page_cap: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for page in range(1, max(page_cap, 1) + 1):
        payload, error = _gh_api_page(endpoint, page)
        if error:
            unavailable.append(
                {
                    "source_kind": "github_api",
                    "unavailable_reason": "api_unavailable",
                    "url": endpoint,
                    "message": error,
                }
            )
            break
        if not isinstance(payload, list):
            unavailable.append(
                {
                    "source_kind": "github_api",
                    "unavailable_reason": "unexpected_payload",
                    "url": endpoint,
                }
            )
            break
        page_records = [item for item in payload if isinstance(item, dict)]
        records.extend(page_records)
        if len(payload) < PER_PAGE:
            break
        if page == max(page_cap, 1):
            unavailable.append(
                {
                    "source_kind": "github_api",
                    "unavailable_reason": "pagination_truncated",
                    "url": endpoint,
                    "page_cap": page_cap,
                }
            )
    return records, unavailable


def _author(comment: dict[str, Any]) -> tuple[str, str]:
    user = comment.get("user")
    if not isinstance(user, dict):
        return "", "unknown"
    login = str(user.get("login") or "")
    user_type = str(user.get("type") or "").lower()
    return login, "bot" if user_type == "bot" or login.endswith("[bot]") else "human"


def _trusted_marker_author(author: str, author_kind: str, trusted_marker_author: str) -> bool:
    if author_kind == "bot":
        return True
    return author_kind == "human" and bool(trusted_marker_author and author == trusted_marker_author)


def _activity(comment: dict[str, Any], *, trusted_marker_author: str = "") -> dict[str, Any]:
    author, author_kind = _author(comment)
    body = str(comment.get("body") or "")
    marker_trusted = _trusted_marker_author(author, author_kind, trusted_marker_author)
    return {
        "body": body,
        "created_at": comment.get("created_at") or "",
        "updated_at": comment.get("updated_at") or "",
        "author": author,
        "author_kind": author_kind,
        "marker_trusted": marker_trusted,
    }


def _line(comment: dict[str, Any]) -> int | None:
    value = comment.get("line")
    if value is None:
        value = comment.get("original_line")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _excerpt(text: object, limit: int = 600) -> str:
    return " ".join(str(text or "").split())[:limit]


def _review_thread_records(comments: list[dict[str, Any]], *, trusted_marker_author: str = "") -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    roots: dict[int, dict[str, Any]] = {}
    for comment in comments:
        root_id = comment.get("in_reply_to_id") or comment.get("id")
        if not isinstance(root_id, int):
            continue
        grouped.setdefault(root_id, []).append(comment)
        if not comment.get("in_reply_to_id"):
            roots[root_id] = comment

    records: list[dict[str, Any]] = []
    for root_id, activities in grouped.items():
        ordered = sorted(activities, key=lambda item: str(item.get("created_at") or ""))
        root = roots.get(root_id) or ordered[0]
        author, author_kind = _author(root)
        record = {
            "source_kind": "review_thread",
            "source_label": "github-review-thread",
            "activity_state": activity_state(
                [_activity(item, trusted_marker_author=trusted_marker_author) for item in ordered]
            ),
            "author": author,
            "author_kind": author_kind,
            "path": root.get("path") or "",
            "line": _line(root),
            "body_excerpt": _excerpt(root.get("body")),
            "url": root.get("html_url") or "",
            "reply_target": {"kind": "review_comment", "id": root_id},
        }
        record["fingerprint"] = stable_fingerprint(record)
        records.append(record)
    return records


def _issue_comment_record(comment: dict[str, Any], *, trusted_marker_author: str = "") -> dict[str, Any]:
    author, author_kind = _author(comment)
    body = str(comment.get("body") or "")
    marker_trusted = _trusted_marker_author(author, author_kind, trusted_marker_author)
    source_kind = "shepherd_summary" if marker_trusted and has_marker(body, SUMMARY_MARKER) else "issue_comment"
    record = {
        "source_kind": source_kind,
        "source_label": "github-pr-comment",
        "activity_state": activity_state([_activity(comment, trusted_marker_author=trusted_marker_author)]),
        "author": author,
        "author_kind": author_kind,
        "path": "pr/comment",
        "line": None,
        "body_excerpt": _excerpt(body),
        "url": comment.get("html_url") or "",
        "reply_target": {"kind": "issue_comment", "id": comment.get("id")},
    }
    if source_kind == "shepherd_summary":
        record["body"] = body
    record["fingerprint"] = stable_fingerprint(record)
    return record


def _review_body_record(review: dict[str, Any], *, trusted_marker_author: str = "") -> dict[str, Any] | None:
    body = str(review.get("body") or "").strip()
    if not body:
        return None
    state = str(review.get("state") or "").strip().upper()
    if state in {"APPROVED", "DISMISSED"}:
        return None
    author, author_kind = _author(review)
    record = {
        "source_kind": "review_body_item",
        "source_label": "github-review-body",
        "activity_state": activity_state([_activity(review, trusted_marker_author=trusted_marker_author)]),
        "author": author,
        "author_kind": author_kind,
        "path": "pr/review",
        "line": None,
        "body_excerpt": _excerpt(body),
        "url": review.get("html_url") or "",
    }
    record["fingerprint"] = stable_fingerprint(record)
    return record


def _check_records(checks: object) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not isinstance(checks, list):
        return records
    for check in checks:
        if not isinstance(check, dict):
            continue
        conclusion = str(check.get("conclusion") or "").lower()
        status = str(check.get("status") or "").lower()
        context_state = str(check.get("state") or "").lower()
        state = conclusion or status or context_state or "unknown"
        if state not in CHECK_FAILURE_STATES:
            continue
        name = str(check.get("name") or check.get("workflowName") or check.get("context") or "check")
        record = {
            "source_kind": "check_run",
            "source_label": name,
            "activity_state": "active",
            "author": "",
            "author_kind": "automation",
            "body_excerpt": f"{name}: Check state: {state}",
            "path": "ci/check",
            "line": None,
            "url": check.get("detailsUrl") or check.get("url") or check.get("targetUrl") or "",
        }
        record["fingerprint"] = stable_fingerprint(record)
        records.append(record)
    return records


def _merge_failed_log_summary(payload: dict[str, Any], summary: Any) -> None:
    if not isinstance(summary, dict):
        payload["unavailable"].append(
            {
                "source_kind": "failed_log_summary",
                "unavailable_reason": "unexpected_payload",
            }
        )
        return
    records = summary.get("records")
    if isinstance(records, list):
        payload["records"].extend(record for record in records if isinstance(record, dict))
    unavailable = summary.get("unavailable")
    if isinstance(unavailable, list):
        payload["unavailable"].extend(item for item in unavailable if isinstance(item, dict))


def _load_failed_log_summary(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        return {
            "records": [],
            "unavailable": [
                {
                    "source_kind": "failed_log_summary",
                    "unavailable_reason": "read_failed",
                    "path": path,
                    "message": str(exc)[:500],
                }
            ],
        }
    except UnicodeDecodeError as exc:
        return {
            "records": [],
            "unavailable": [
                {
                    "source_kind": "failed_log_summary",
                    "unavailable_reason": "decode_failed",
                    "path": path,
                    "message": str(exc)[:500],
                }
            ],
        }
    except json.JSONDecodeError as exc:
        return {
            "records": [],
            "unavailable": [
                {
                    "source_kind": "failed_log_summary",
                    "unavailable_reason": "parse_failed",
                    "path": path,
                    "message": str(exc)[:500],
                }
            ],
        }
    if not isinstance(payload, dict):
        return {
            "records": [],
            "unavailable": [
                {
                    "source_kind": "failed_log_summary",
                    "unavailable_reason": "unexpected_payload",
                    "path": path,
                }
            ],
        }
    return payload


def _current_login() -> str:
    payload, _error = _gh_json(["gh", "api", "user"])
    if isinstance(payload, dict):
        return str(payload.get("login") or "")
    return ""


def collect(
    pr: int,
    *,
    page_cap: int,
    failed_log_summaries: list[dict[str, Any]] | None = None,
    trusted_marker_author: str = "",
) -> dict[str, Any]:
    pr_payload, pr_error = _gh_json(["gh", "pr", "view", str(pr), "--json", "number,url,headRefName,baseRefName,isDraft,statusCheckRollup"])
    payload: dict[str, Any] = {
        "pr": pr_payload or {"number": pr},
        "records": [],
        "unavailable": [],
    }
    if pr_error:
        payload["unavailable"].append({"source_kind": "pr", "unavailable_reason": "api_unavailable", "message": pr_error})
        return payload

    checks = pr_payload.get("statusCheckRollup") if isinstance(pr_payload, dict) else []
    payload["records"].extend(_check_records(checks))

    review_comments, review_unavailable = _collect_paginated(
        f"repos/{{owner}}/{{repo}}/pulls/{pr}/comments",
        page_cap=page_cap,
    )
    issue_comments, issue_unavailable = _collect_paginated(
        f"repos/{{owner}}/{{repo}}/issues/{pr}/comments",
        page_cap=page_cap,
    )
    reviews, review_body_unavailable = _collect_paginated(
        f"repos/{{owner}}/{{repo}}/pulls/{pr}/reviews",
        page_cap=page_cap,
    )

    payload["records"].extend(_review_thread_records(review_comments, trusted_marker_author=trusted_marker_author))
    payload["records"].extend(
        _issue_comment_record(comment, trusted_marker_author=trusted_marker_author) for comment in issue_comments
    )
    payload["records"].extend(
        record
        for record in (_review_body_record(review, trusted_marker_author=trusted_marker_author) for review in reviews)
        if record is not None
    )
    payload["unavailable"].extend(review_unavailable)
    payload["unavailable"].extend(issue_unavailable)
    payload["unavailable"].extend(review_body_unavailable)
    for summary in failed_log_summaries or []:
        _merge_failed_log_summary(payload, summary)
    payload["page_cap"] = page_cap
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--page-cap", type=int, default=10)
    parser.add_argument(
        "--failed-log-summary",
        action="append",
        default=[],
        help="JSON output from pr_shepherd_fetch_failed_logs.py to merge into records",
    )
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failed_log_summaries = [_load_failed_log_summary(path) for path in args.failed_log_summary]
    payload = collect(
        args.pr,
        page_cap=args.page_cap,
        failed_log_summaries=failed_log_summaries,
        trusted_marker_author=_current_login(),
    )
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
