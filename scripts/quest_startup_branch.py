#!/usr/bin/env python3
"""Prepare branch/worktree context for a new quest run."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_BRANCH_MODE = "branch"
DEFAULT_BRANCH_PREFIX = "quest/"
DEFAULT_WORKTREE_ROOT = ".worktrees/quest"
VALID_BRANCH_MODES = {"branch", "worktree", "none"}
SAFE_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create quest startup branch or worktree context."
    )
    parser.add_argument("--slug", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--allowlist", default=".ai/allowlist.json")
    parser.add_argument(
        "--mode",
        choices=["branch", "worktree", "none"],
        default=None,
        help="Override branch mode from allowlist (user's interactive choice).",
    )
    return parser.parse_args()


def run_git(repo_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout.strip()


def git_success(repo_root: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def load_allowlist(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def detect_requested_branch_mode(args: argparse.Namespace, allowlist_path: Path) -> str:
    if args.mode:
        return args.mode
    try:
        allowlist = load_allowlist(allowlist_path)
    except Exception:
        return DEFAULT_BRANCH_MODE
    startup = allowlist.get("quest_startup") or {}
    return str(startup.get("branch_mode", DEFAULT_BRANCH_MODE))


def detect_default_branch(repo_root: Path, current_branch: str) -> str:
    remote_head = run_git(
        repo_root,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        check=False,
    )
    if remote_head.startswith("refs/remotes/origin/"):
        return remote_head.rsplit("/", 1)[-1]

    for candidate in ("main", "master"):
        if git_success(repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"):
            return candidate

    # Cannot determine default branch — assume current branch is it.
    return current_branch


def is_git_repo(repo_root: Path) -> bool:
    return git_success(repo_root, "rev-parse", "--is-inside-work-tree")


def safe_is_git_repo(repo_root: Path) -> bool:
    try:
        return is_git_repo(repo_root)
    except Exception:
        return False


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    return git_success(repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}")


def repo_dirty(repo_root: Path) -> bool:
    return bool(
        run_git(
            repo_root,
            "status",
            "--porcelain",
            "--untracked-files=no",
            check=False,
        ).strip()
    )


def build_result(
    *,
    status: str,
    vcs_available: bool,
    branch: str | None,
    branch_mode: str,
    requested_branch_mode: str,
    current_branch: str | None,
    default_branch: str | None,
    branch_created: bool,
    worktree_path: Path | None,
    message: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "vcs_available": vcs_available,
        "branch": branch,
        "branch_mode": branch_mode,
        "requested_branch_mode": requested_branch_mode,
        "current_branch": current_branch,
        "default_branch": default_branch,
        "branch_created": branch_created,
        "worktree_path": str(worktree_path) if worktree_path else None,
        "message": message,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    allowlist_path = Path(args.allowlist)
    if not allowlist_path.is_absolute():
        allowlist_path = (repo_root / allowlist_path).resolve()
    requested_branch_mode = detect_requested_branch_mode(args, allowlist_path)

    if not SAFE_SLUG_RE.match(args.slug) or ".." in args.slug:
        payload = build_result(
            status="blocked",
            vcs_available=safe_is_git_repo(repo_root),
            branch=None,
            branch_mode="none",
            requested_branch_mode=requested_branch_mode,
            current_branch=None,
            default_branch=None,
            branch_created=False,
            worktree_path=None,
            message=(
                f"Invalid slug '{args.slug}'. "
                "Slugs must be lowercase alphanumeric with single hyphens, "
                "no path separators or '..'."
            ),
        )
        print(json.dumps(payload, indent=2))
        return 0

    try:
        allowlist = load_allowlist(allowlist_path)
        startup = allowlist.get("quest_startup") or {}
        requested_branch_mode = args.mode or startup.get("branch_mode", DEFAULT_BRANCH_MODE)
        branch_prefix = startup.get("branch_prefix", DEFAULT_BRANCH_PREFIX)
        worktree_root = startup.get("worktree_root", DEFAULT_WORKTREE_ROOT)

        if requested_branch_mode not in VALID_BRANCH_MODES:
            payload = build_result(
                status="blocked",
                vcs_available=safe_is_git_repo(repo_root),
                branch=None,
                branch_mode="none",
                requested_branch_mode=str(requested_branch_mode),
                current_branch=None,
                default_branch=None,
                branch_created=False,
                worktree_path=None,
                message=(
                    "Invalid quest_startup.branch_mode in allowlist.json. "
                    "Expected one of: branch, worktree, none."
                ),
            )
            print(json.dumps(payload, indent=2))
            return 0

        if not is_git_repo(repo_root):
            payload = build_result(
                status="skipped",
                vcs_available=False,
                branch=None,
                branch_mode="none",
                requested_branch_mode=requested_branch_mode,
                current_branch=None,
                default_branch=None,
                branch_created=False,
                worktree_path=None,
                message=(
                    "Not a git repository — skipping quest startup branch/worktree creation "
                    "and staying in the current workspace."
                ),
            )
            print(json.dumps(payload, indent=2))
            return 0

        current_branch = run_git(repo_root, "branch", "--show-current", check=False)
        if not current_branch:
            payload = build_result(
                status="blocked",
                vcs_available=True,
                branch=None,
                branch_mode="none",
                requested_branch_mode=requested_branch_mode,
                current_branch=None,
                default_branch=None,
                branch_created=False,
                worktree_path=None,
                message="Detached HEAD detected. Quest startup branch setup requires a named branch checkout.",
            )
            print(json.dumps(payload, indent=2))
            return 0

        default_branch = detect_default_branch(repo_root, current_branch)
        branch_name = f"{branch_prefix}{args.slug}"

        if current_branch != default_branch:
            payload = build_result(
                status="skipped",
                vcs_available=True,
                branch=current_branch,
                branch_mode="none",
                requested_branch_mode=requested_branch_mode,
                current_branch=current_branch,
                default_branch=default_branch,
                branch_created=False,
                worktree_path=None,
                message=f"Already on branch {current_branch} — skipping quest startup branch creation.",
            )
            print(json.dumps(payload, indent=2))
            return 0

        if requested_branch_mode == "none":
            payload = build_result(
                status="skipped",
                vcs_available=True,
                branch=current_branch,
                branch_mode="none",
                requested_branch_mode=requested_branch_mode,
                current_branch=current_branch,
                default_branch=default_branch,
                branch_created=False,
                worktree_path=None,
                message="Quest startup branch mode disabled — staying on the current branch.",
            )
            print(json.dumps(payload, indent=2))
            return 0

        if branch_exists(repo_root, branch_name):
            payload = build_result(
                status="blocked",
                vcs_available=True,
                branch=branch_name,
                branch_mode="none",
                requested_branch_mode=requested_branch_mode,
                current_branch=current_branch,
                default_branch=default_branch,
                branch_created=False,
                worktree_path=None,
                message=(
                    f"Branch {branch_name} already exists. "
                    "Choose a different quest slug or clean up the existing branch first."
                ),
            )
            print(json.dumps(payload, indent=2))
            return 0

        if requested_branch_mode == "branch":
            if repo_dirty(repo_root):
                payload = build_result(
                    status="blocked",
                    vcs_available=True,
                    branch=current_branch,
                    branch_mode="none",
                    requested_branch_mode=requested_branch_mode,
                    current_branch=current_branch,
                    default_branch=default_branch,
                    branch_created=False,
                    worktree_path=None,
                    message=(
                        "Working tree is dirty on the default branch. "
                        "Commit or stash changes before Quest creates a startup branch."
                    ),
                )
                print(json.dumps(payload, indent=2))
                return 0

            run_git(repo_root, "checkout", "-b", branch_name)
            payload = build_result(
                status="created",
                vcs_available=True,
                branch=branch_name,
                branch_mode="branch",
                requested_branch_mode=requested_branch_mode,
                current_branch=current_branch,
                default_branch=default_branch,
                branch_created=True,
                worktree_path=None,
                message=f"Created and checked out quest branch {branch_name}.",
            )
            print(json.dumps(payload, indent=2))
            return 0

        worktree_path = (repo_root / worktree_root / args.slug).resolve()
        if worktree_path.exists():
            payload = build_result(
                status="blocked",
                vcs_available=True,
                branch=branch_name,
                branch_mode="none",
                requested_branch_mode=requested_branch_mode,
                current_branch=current_branch,
                default_branch=default_branch,
                branch_created=False,
                worktree_path=worktree_path,
                message=(
                    f"Worktree path already exists: {worktree_path}. "
                    "Remove it or choose a different quest slug first."
                ),
            )
            print(json.dumps(payload, indent=2))
            return 0

        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        run_git(
            repo_root,
            "worktree",
            "add",
            str(worktree_path),
            "-b",
            branch_name,
            default_branch,
        )

        # Symlink .quest/ into the worktree so subagents can use
        # relative .quest/<id>/... paths without special handling.
        # git worktree checkout may create a real .quest/ dir from
        # force-tracked files — replace it with a symlink to the
        # main repo's .quest/ so the active quest is visible.
        quest_link = worktree_path / ".quest"
        quest_source = repo_root / ".quest"
        if quest_link.is_symlink():
            pass  # already a symlink, leave it
        elif quest_link.is_dir():
            shutil.rmtree(quest_link)
            quest_link.symlink_to(quest_source)
        elif not quest_link.exists():
            quest_link.symlink_to(quest_source)

        payload = build_result(
            status="created",
            vcs_available=True,
            branch=branch_name,
            branch_mode="worktree",
            requested_branch_mode=requested_branch_mode,
            current_branch=current_branch,
            default_branch=default_branch,
            branch_created=True,
            worktree_path=worktree_path,
            message=f"Created quest worktree {worktree_path} on branch {branch_name}.",
        )
        print(json.dumps(payload, indent=2))
        return 0
    except Exception as exc:
        payload = build_result(
            status="blocked",
            vcs_available=safe_is_git_repo(repo_root),
            branch=None,
            branch_mode="none",
            requested_branch_mode=requested_branch_mode,
            current_branch=None,
            default_branch=None,
            branch_created=False,
            worktree_path=None,
            message=f"Quest startup branch preparation failed: {exc}",
        )
        print(json.dumps(payload, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
