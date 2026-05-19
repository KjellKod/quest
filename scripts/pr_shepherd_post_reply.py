#!/usr/bin/env python3
"""Prepare or post PR shepherd replies with durable markers."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from quest_runtime.pr_shepherd import (
    ADDRESSED_MARKER,
    FOLLOWUP_MARKER,
    SUMMARY_MARKER,
    append_marker,
    compact_summary_body,
    has_marker,
)

PER_PAGE = 100


def _run(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True, input=input_text)


def _body_input(body: str) -> str:
    return json.dumps({"body": body}, ensure_ascii=True)


def _load_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _gh_json(args: list[str]) -> tuple[Any | None, str]:
    result = _run(args)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()[:500]
    try:
        return json.loads(result.stdout or "null"), ""
    except json.JSONDecodeError as exc:
        return None, str(exc)


def _author(comment: dict[str, Any]) -> tuple[str, str]:
    user = comment.get("user")
    if not isinstance(user, dict):
        return "", "unknown"
    login = str(user.get("login") or "")
    user_type = str(user.get("type") or "").lower()
    return login, "bot" if user_type == "bot" or login.endswith("[bot]") else "human"


def _current_login() -> str:
    payload, _error = _gh_json(["gh", "api", "user"])
    if isinstance(payload, dict):
        return str(payload.get("login") or "")
    return ""


def _trusted_summary_author(comment: dict[str, Any], trusted_marker_author: str) -> bool:
    author, author_kind = _author(comment)
    return author_kind != "human" or bool(trusted_marker_author and author == trusted_marker_author)


def _collect_issue_comments(pr: int, *, page_cap: int) -> tuple[list[dict[str, Any]], str]:
    comments: list[dict[str, Any]] = []
    endpoint = f"repos/{{owner}}/{{repo}}/issues/{pr}/comments"
    max_pages = max(page_cap, 1)
    for page in range(1, max_pages + 2):
        payload, error = _gh_json(
            ["gh", "api", endpoint, "--method", "GET", "-F", f"per_page={PER_PAGE}", "-F", f"page={page}"]
        )
        if error:
            return comments, error
        if not isinstance(payload, list):
            return comments, "unexpected comments payload"
        if page > max_pages:
            return comments, "pagination_truncated" if payload else ""
        comments.extend(comment for comment in payload if isinstance(comment, dict))
        if len(payload) < PER_PAGE:
            return comments, ""
    return comments, ""


def _find_summary_comment(comments: list[dict[str, Any]], *, trusted_marker_author: str = "") -> dict[str, Any] | None:
    for comment in comments:
        if has_marker(str(comment.get("body") or ""), SUMMARY_MARKER) and _trusted_summary_author(
            comment,
            trusted_marker_author,
        ):
            return comment
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, help="PR number for top-level summary comments")
    parser.add_argument("--thread-id", help="Review thread/comment id for threaded replies")
    parser.add_argument("--body", default="", help="Reply body")
    parser.add_argument("--body-file", help="Read reply body from file")
    parser.add_argument("--followup", action="store_true", help="Append follow-up marker before addressed marker")
    parser.add_argument("--summary", action="store_true", help="Upsert marker-owned top-level summary comment")
    parser.add_argument("--summary-rows", help="JSON file with compact summary rows")
    parser.add_argument("--comments-json", help="Fixture/current top-level PR comments JSON")
    parser.add_argument("--page-cap", type=int, default=10, help="Max issue-comment pages to scan for summary upsert")
    parser.add_argument("--dry-run", action="store_true", help="Do not call gh; emit action/body JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else args.body

    if args.summary:
        rows = _load_json(args.summary_rows) or []
        if not isinstance(rows, list):
            raise ValueError("--summary-rows must contain a JSON list")
        body = compact_summary_body(rows) if rows else append_marker(body, SUMMARY_MARKER)
        comments = _load_json(args.comments_json)
        if comments is None and not args.dry_run:
            if not args.pr:
                raise ValueError("--pr is required when posting a summary")
            comments, comments_error = _collect_issue_comments(args.pr, page_cap=args.page_cap)
            if comments_error:
                print(
                    json.dumps(
                        {"ok": False, "action": "load_summary_comments", "error": comments_error},
                        sort_keys=True,
                    )
                )
                return 1
        if comments is None:
            comments = []
        if not isinstance(comments, list):
            raise ValueError("--comments-json must contain a JSON list")
        trusted_marker_author = _current_login() if not args.dry_run else ""
        existing = _find_summary_comment(comments, trusted_marker_author=trusted_marker_author)
        action = "update_summary" if existing else "create_summary"
        payload = {
            "ok": True,
            "action": action,
            "comment_id": existing.get("id") if existing else None,
            "body": body,
        }
        if args.dry_run:
            print(json.dumps(payload, sort_keys=True))
            return 0
        if not args.pr:
            raise ValueError("--pr is required when posting a summary")
        if existing:
            result = _run(
                [
                    "gh",
                    "api",
                    f"repos/{{owner}}/{{repo}}/issues/comments/{existing['id']}",
                    "-X",
                    "PATCH",
                    "--input",
                    "-",
                ],
                input_text=_body_input(body),
            )
        else:
            result = _run(["gh", "pr", "comment", str(args.pr), "--body", body])
        if result.returncode != 0:
            print(json.dumps({"ok": False, "action": action, "error": (result.stderr or result.stdout)[:500]}, sort_keys=True))
            return result.returncode
        print(json.dumps(payload, sort_keys=True))
        return 0

    marker = FOLLOWUP_MARKER if args.followup else ADDRESSED_MARKER
    marked = append_marker(body, marker)
    if args.followup:
        marked = append_marker(marked, ADDRESSED_MARKER)
    if args.dry_run:
        print(json.dumps({"ok": True, "action": "reply_thread", "thread_id": args.thread_id, "body": marked}, sort_keys=True))
        return 0
    if not args.thread_id or not args.pr:
        raise ValueError("--pr and --thread-id are required unless --summary is used")
    result = _run(
        [
            "gh",
            "api",
            f"repos/{{owner}}/{{repo}}/pulls/{args.pr}/comments/{args.thread_id}/replies",
            "-X",
            "POST",
            "--input",
            "-",
        ],
        input_text=_body_input(marked),
    )
    if result.returncode != 0:
        print(json.dumps({"ok": False, "action": "reply_thread", "error": (result.stderr or result.stdout)[:500]}, sort_keys=True))
        return result.returncode
    print(json.dumps({"ok": True, "action": "reply_thread", "thread_id": args.thread_id}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
