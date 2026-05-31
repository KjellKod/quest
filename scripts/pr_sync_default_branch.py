#!/usr/bin/env python3
"""Inspect or apply a PR branch sync with the remote default branch.

The inspect path uses git merge-tree as a best-effort, merge-based estimate.
For the default rebase strategy, the authoritative conflict detector is the
--apply path: if rebase conflicts, this helper aborts and returns a conflict
payload. The helper never pushes and never uses blanket -X ours/theirs
resolution strategies.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any


STRATEGIES = ("rebase", "merge")
STATUS_UP_TO_DATE = "up_to_date"
STATUS_CLEAN = "clean"
STATUS_SYNCED = "synced"
STATUS_CONFLICT = "conflict"
STATUS_ERROR = "error"

_TREE_OID_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=False, text=True, capture_output=True)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def _base_payload(strategy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": STATUS_ERROR,
        "action": "none",
        "default_branch": "",
        "default_branch_source": "",
        "strategy": strategy,
        "applied": False,
        "push_required": False,
        "force_with_lease": False,
        "conflict_files": [],
        "reason": "",
    }


def _emit(payload: dict[str, Any], *, code: int) -> int:
    print(json.dumps(payload, sort_keys=True))
    return code


def _message(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip()[:500]


def _parse_remote_head(output: str) -> str:
    prefix = "refs/heads/"
    for raw_line in output.splitlines():
        parts = raw_line.strip().split()
        if len(parts) == 3 and parts[0] == "ref:" and parts[2] == "HEAD" and parts[1].startswith(prefix):
            return parts[1][len(prefix) :]
    return ""


def detect_default_branch() -> tuple[str, str]:
    remote_head = _run(["git", "ls-remote", "--symref", "origin", "HEAD"])
    if remote_head.returncode == 0:
        branch = _parse_remote_head(remote_head.stdout)
        if branch:
            return branch, "ls-remote"

    symbolic = _run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"])
    if symbolic.returncode == 0:
        ref = symbolic.stdout.strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix) and len(ref) > len(prefix):
            return ref[len(prefix) :], "symbolic-ref"

    gh = _run(["gh", "repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"])
    if gh.returncode == 0 and gh.stdout.strip():
        return gh.stdout.strip(), "gh"

    return "", ""


def is_up_to_date(default_ref: str) -> bool:
    result = _run(["git", "merge-base", "--is-ancestor", default_ref, "HEAD"])
    return result.returncode == 0


def _parse_conflict_files(output: str) -> list[str]:
    if not output:
        return []

    if "\0" in output:
        parts = [part for part in output.split("\0") if part]
        if parts and _TREE_OID_RE.fullmatch(parts[0]):
            parts = parts[1:]
        return [part for part in parts if _looks_like_path(part)]

    files: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or _TREE_OID_RE.fullmatch(line):
            continue
        if line.startswith(("Auto-merging ", "CONFLICT ", "changed in both", "base ")):
            break
        if _looks_like_path(line):
            files.append(line)
    return files


def _looks_like_path(value: str) -> bool:
    if not value or value.startswith(("CONFLICT", "Auto-merging", "error:")):
        return False
    return "\n" not in value and "\r" not in value


def probe_merge(default_ref: str) -> tuple[str, list[str], str]:
    result = _run(
        [
            "git",
            "merge-tree",
            "--write-tree",
            "--no-messages",
            "-z",
            "--name-only",
            default_ref,
            "HEAD",
        ]
    )
    if result.returncode == 0:
        return STATUS_CLEAN, [], ""
    if result.returncode == 1:
        return STATUS_CONFLICT, _parse_conflict_files(result.stdout), _message(result)
    return STATUS_ERROR, [], _message(result)


def _conflicted_files_from_index() -> list[str]:
    result = _run(["git", "diff", "--name-only", "--diff-filter=U"])
    if result.returncode == 0:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return []


def _abort(strategy: str) -> None:
    if strategy == "rebase":
        _run(["git", "rebase", "--abort"])
    else:
        _run(["git", "merge", "--abort"])


def _apply_sync(strategy: str, default_ref: str) -> tuple[int, str]:
    if strategy == "rebase":
        result = _run(["git", "rebase", default_ref])
    else:
        result = _run(["git", "merge", "--no-edit", default_ref])
    return result.returncode, _message(result)


def _pre_apply_error() -> tuple[str, str]:
    status = _run(["git", "status", "--porcelain"])
    if status.returncode != 0:
        return "status_failed", _message(status)
    if status.stdout.strip():
        return "worktree_dirty", ""

    for ref, reason in (
        ("MERGE_HEAD", "merge_in_progress"),
        ("REBASE_HEAD", "rebase_in_progress"),
        ("CHERRY_PICK_HEAD", "cherry_pick_in_progress"),
    ):
        result = _run(["git", "rev-parse", "--verify", "-q", ref])
        if result.returncode == 0:
            return reason, ""

    return "", ""


def _pre_rebase_lease_error() -> tuple[str, str]:
    upstream = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream.returncode == 0 and upstream.stdout.strip():
        return _branch_contains(upstream.stdout.strip())

    branch = _run(["git", "branch", "--show-current"])
    if branch.returncode != 0 or not branch.stdout.strip():
        return "", ""

    remote_ref = f"origin/{branch.stdout.strip()}"
    remote_tracking_ref = f"refs/remotes/{remote_ref}"
    remote_exists = _run(["git", "rev-parse", "--verify", "-q", remote_tracking_ref])
    if remote_exists.returncode != 0:
        return "", ""

    return _branch_contains(remote_ref)


def _branch_contains(ref: str) -> tuple[str, str]:
    contains = _run(["git", "merge-base", "--is-ancestor", ref, "HEAD"])
    if contains.returncode == 0:
        return "", ""
    if contains.returncode == 1:
        return "upstream_not_contained", f"local HEAD does not contain {ref}"
    return "upstream_check_failed", _message(contains)


def sync(strategy: str = "rebase", *, apply: bool = False) -> tuple[int, dict[str, Any]]:
    payload = _base_payload(strategy)

    fetch = _run(["git", "fetch", "origin"])
    if fetch.returncode != 0:
        payload.update({"reason": "fetch_failed", "message": _message(fetch)})
        return 1, payload

    default_branch, source = detect_default_branch()
    payload.update({"default_branch": default_branch, "default_branch_source": source})
    if not default_branch:
        payload["reason"] = "default_branch_undetected"
        return 1, payload

    default_ref = f"origin/{default_branch}"
    if is_up_to_date(default_ref):
        payload.update(
            {
                "ok": True,
                "status": STATUS_UP_TO_DATE,
                "reason": "",
            }
        )
        return 0, payload

    probe_status, conflict_files, message = probe_merge(default_ref)
    if probe_status == STATUS_ERROR:
        payload.update(
            {
                "status": STATUS_ERROR,
                "reason": "merge_tree_failed",
            }
        )
        if message:
            payload["message"] = message
        return 1, payload

    if probe_status == STATUS_CONFLICT:
        payload.update(
            {
                "status": STATUS_CONFLICT,
                "conflict_files": conflict_files,
                "reason": "merge_tree_conflict",
            }
        )
        if message:
            payload["message"] = message
        return 1, payload

    action = "would_rebase" if strategy == "rebase" else "would_merge"
    if not apply:
        payload.update(
            {
                "ok": True,
                "status": STATUS_CLEAN,
                "action": action,
                "reason": "",
            }
        )
        return 0, payload

    guard_reason, guard_message = _pre_apply_error()
    if guard_reason:
        payload.update({"status": STATUS_ERROR, "reason": guard_reason})
        if guard_message:
            payload["message"] = guard_message
        return 1, payload

    if strategy == "rebase":
        lease_reason, lease_message = _pre_rebase_lease_error()
        if lease_reason:
            payload.update({"status": STATUS_ERROR, "reason": lease_reason})
            if lease_message:
                payload["message"] = lease_message
            return 1, payload

    apply_code, apply_message = _apply_sync(strategy, default_ref)
    if apply_code != 0:
        conflict_files = _conflicted_files_from_index()
        _abort(strategy)
        if not conflict_files:
            payload.update(
                {
                    "status": STATUS_ERROR,
                    "conflict_files": [],
                    "reason": f"{strategy}_failed",
                }
            )
            if apply_message:
                payload["message"] = apply_message
            return 1, payload
        payload.update(
            {
                "status": STATUS_CONFLICT,
                "conflict_files": conflict_files,
                "reason": f"{strategy}_conflict",
            }
        )
        if apply_message:
            payload["message"] = apply_message
        return 1, payload

    payload.update(
        {
            "ok": True,
            "status": STATUS_SYNCED,
            "action": "rebased" if strategy == "rebase" else "merged",
            "applied": True,
            "push_required": True,
            "force_with_lease": strategy == "rebase",
            "reason": "",
        }
    )
    return 0, payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=STRATEGIES, default="rebase")
    parser.add_argument("--apply", action="store_true", help="Apply the clean sync")
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, payload = sync(args.strategy, apply=args.apply)
    return _emit(payload, code=code)


if __name__ == "__main__":
    sys.exit(main())
