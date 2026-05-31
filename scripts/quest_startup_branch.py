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


def resolve_shared_quest_dir(workdir: Path) -> Path | None:
    """Return the main repo's shared .quest dir for a linked worktree."""
    try:
        common_dir_raw = run_git(
            workdir,
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
            check=True,
        )
    except Exception:
        try:
            common_dir_raw = run_git(
                workdir,
                "rev-parse",
                "--git-common-dir",
                check=True,
            )
        except Exception:
            return None

    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = (workdir / common_dir).resolve()
    else:
        common_dir = common_dir.resolve()

    main_root = common_dir.parent.resolve()
    if main_root == workdir.resolve():
        return None
    return main_root / ".quest"


def _unique_destination(path: Path) -> Path:
    if not path.exists() and not path.is_symlink():
        return path
    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.name}-{index}")
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise RuntimeError(f"Unable to find unique destination for {path}")


def _conflict_dir_for(worktree_quest: Path, shared_quest: Path) -> Path:
    worktree_name = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "-",
        worktree_quest.parent.name,
    ).strip("-")
    if not worktree_name:
        worktree_name = "worktree"
    return shared_quest.parent / ".quest_conflicts" / worktree_name


def _symlink_points_to(path: Path, target: Path) -> bool:
    link_target = path.readlink()
    if not link_target.is_absolute():
        link_target = path.parent / link_target
    return link_target.resolve() == target.resolve()


def apply_quest_symlink(worktree_quest: Path, shared_quest: Path) -> str:
    """Ensure a worktree .quest symlink with migration and no data loss."""
    if worktree_quest.is_symlink():
        if _symlink_points_to(worktree_quest, shared_quest):
            return "present"
        shared_quest.mkdir(parents=True, exist_ok=True)
        conflict_dir = _conflict_dir_for(worktree_quest, shared_quest)
        conflict_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(
            str(worktree_quest),
            str(_unique_destination(conflict_dir / ".quest")),
        )
        worktree_quest.symlink_to(shared_quest)
        return "conflict"

    shared_quest.mkdir(parents=True, exist_ok=True)

    if not worktree_quest.exists():
        worktree_quest.symlink_to(shared_quest)
        return "created"

    if not worktree_quest.is_dir():
        raise RuntimeError(f"{worktree_quest} exists but is not a directory or symlink")

    moved_any = False
    had_conflict = False
    conflict_dir = _conflict_dir_for(worktree_quest, shared_quest)

    try:
        for entry in list(worktree_quest.iterdir()):
            destination = shared_quest / entry.name
            if destination.exists() or destination.is_symlink():
                conflict_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(entry), str(_unique_destination(conflict_dir / entry.name)))
                had_conflict = True
                continue

            shutil.move(str(entry), str(destination))
            moved_any = True

        # Empty-only removal is deliberate: never force-delete migrated state.
        worktree_quest.rmdir()
        worktree_quest.symlink_to(shared_quest)
    except Exception as exc:
        raise RuntimeError(f"Unable to replace {worktree_quest} with shared symlink") from exc

    if had_conflict:
        return "conflict"
    if moved_any:
        return "migrated"
    return "created"


def ensure_shared_quest_symlink(repo_root: Path, workdir: Path) -> str:
    """Ensure linked worktrees use the main repo's shared .quest directory."""
    del repo_root  # Signature keeps the caller contract explicit.
    shared_quest = resolve_shared_quest_dir(workdir)
    if shared_quest is None:
        return "n/a"
    return apply_quest_symlink(workdir / ".quest", shared_quest)


def combine_quest_symlink_outcomes(*outcomes: str) -> str:
    """Return the most important .quest symlink outcome to surface."""
    priority = {
        "n/a": 0,
        "present": 1,
        "created": 2,
        "migrated": 3,
        "conflict": 4,
    }
    return max(outcomes, key=lambda outcome: priority.get(outcome, 0))


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
    quest_symlink: str = "n/a",
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
        "quest_symlink": quest_symlink,
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

        current_quest_symlink = ensure_shared_quest_symlink(repo_root, repo_root)

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
                quest_symlink=current_quest_symlink,
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
                quest_symlink=current_quest_symlink,
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
                quest_symlink=current_quest_symlink,
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
                quest_symlink=current_quest_symlink,
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
                    quest_symlink=current_quest_symlink,
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
                quest_symlink=current_quest_symlink,
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
                quest_symlink=current_quest_symlink,
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

        quest_symlink = combine_quest_symlink_outcomes(
            current_quest_symlink,
            ensure_shared_quest_symlink(repo_root, worktree_path),
        )

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
            quest_symlink=quest_symlink,
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
