#!/usr/bin/env python3
"""Inspect or apply checkout for a PR shepherd target."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def _json_error(reason: str, *, message: str = "", **extra: Any) -> int:
    payload = {
        "ok": False,
        "action": "none",
        "target_pr": None,
        "target_branch": "",
        "current_branch": extra.pop("current_branch", ""),
        "worktree_clean": extra.pop("worktree_clean", False),
        "reason": reason,
    }
    if message:
        payload["message"] = message[:500]
    payload.update(extra)
    print(json.dumps(payload, sort_keys=True))
    return 1


def _current_branch() -> str:
    result = _run(["git", "branch", "--show-current"])
    return result.stdout.strip() if result.returncode == 0 else ""


def _worktree_clean() -> bool:
    result = _run(["git", "status", "--short"])
    return result.returncode == 0 and not result.stdout.strip()


def _git_path(flag: str) -> Path | None:
    result = _run(["git", "rev-parse", flag])
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _is_linked_worktree() -> bool:
    git_dir = _git_path("--git-dir")
    common_dir = _git_path("--git-common-dir")
    if git_dir is None or common_dir is None:
        return False
    try:
        return git_dir.resolve() != common_dir.resolve()
    except OSError:
        return git_dir != common_dir


def _head_oid() -> str:
    result = _run(["git", "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else ""


def _pr_view(target: str | None) -> tuple[dict[str, Any] | None, str]:
    args = ["gh", "pr", "view"]
    if target:
        args.append(target)
    args.extend(["--json", "number,url,headRefName,headRefOid,headRepository,headRepositoryOwner"])
    result = _run(args)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    return payload, ""


def inspect_checkout(target: str | None, *, apply: bool) -> tuple[int, dict[str, Any]]:
    current_branch = _current_branch()
    clean = _worktree_clean()
    pr, error = _pr_view(target)
    if pr is None:
        return 1, {
            "ok": False,
            "action": "none",
            "target_pr": None,
            "target_branch": "",
            "current_branch": current_branch,
            "worktree_clean": clean,
            "reason": "no_pr" if not target else "gh_failure",
            "message": error[:500],
        }

    target_branch = str(pr.get("headRefName") or "")
    target_oid = str(pr.get("headRefOid") or "")
    target_pr = pr.get("number")
    payload: dict[str, Any] = {
        "ok": True,
        "action": "none",
        "target_pr": target_pr,
        "target_branch": target_branch,
        "current_branch": current_branch,
        "worktree_clean": clean,
        "reason": "",
        "url": pr.get("url") or "",
    }

    if current_branch == target_branch:
        if target_oid and _head_oid() != target_oid:
            if not apply:
                payload["action"] = "would_checkout"
                payload["reason"] = "head_mismatch"
                return 0, payload
            payload.update(
                {
                    "ok": False,
                    "action": "none",
                    "reason": "head_mismatch",
                    "message": "Current branch name matches the PR, but HEAD differs from the PR head.",
                }
            )
            return 1, payload
        else:
            return 0, payload
    else:
        payload["action"] = "would_checkout"
        if not apply:
            return 0, payload

    if not clean:
        payload.update({"ok": False, "reason": "dirty_worktree", "action": "none"})
        return 1, payload

    if _is_linked_worktree():
        payload.update({"ok": False, "reason": "worktree_mismatch", "action": "none"})
        return 1, payload

    checkout_target = target or str(target_pr)
    result = _run(["gh", "pr", "checkout", checkout_target])
    if result.returncode != 0:
        payload.update(
            {
                "ok": False,
                "reason": "gh_failure",
                "action": "none",
                "message": (result.stderr or result.stdout).strip()[:500],
            }
        )
        return 1, payload
    payload["action"] = "checked_out"
    payload["current_branch"] = _current_branch()
    payload["worktree_clean"] = _worktree_clean()
    if target_oid and _head_oid() != target_oid:
        payload.update(
            {
                "ok": False,
                "action": "none",
                "reason": "head_mismatch",
                "message": "Checked out branch HEAD does not match the PR head.",
            }
        )
        return 1, payload
    return 0, payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="PR number, URL, or branch")
    parser.add_argument("--target", dest="target_option", help="PR number, URL, or branch")
    parser.add_argument("--apply", action="store_true", help="Apply checkout mutation")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = args.target_option or args.target
    code, payload = inspect_checkout(target, apply=args.apply)
    print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
