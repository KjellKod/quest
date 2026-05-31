"""Tests for Quest startup .quest symlink handling."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import quest_startup_branch
from quest_startup_branch import apply_quest_symlink, ensure_shared_quest_symlink


SCRIPT = Path(quest_startup_branch.__file__).resolve()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.name", "Quest Test")
    _git(path, "config", "user.email", "quest-test@example.com")
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")
    return path


def _write_allowlist(repo: Path, branch_mode: str) -> Path:
    allowlist = repo / ".ai" / "allowlist.json"
    allowlist.parent.mkdir(parents=True, exist_ok=True)
    allowlist.write_text(
        json.dumps(
            {
                "quest_startup": {
                    "branch_mode": branch_mode,
                    "branch_prefix": "quest/",
                    "worktree_root": ".worktrees/quest",
                }
            }
        ),
        encoding="utf-8",
    )
    return allowlist


def _run_startup(repo_root: Path, allowlist: Path, slug: str, mode: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--allowlist",
            str(allowlist),
            "--slug",
            slug,
            "--mode",
            mode,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _target(path: Path) -> Path:
    return Path(path.readlink()).resolve()


def test_apply_quest_symlink_absent_creates_symlink(tmp_path: Path) -> None:
    worktree_quest = tmp_path / "worktree" / ".quest"
    shared_quest = tmp_path / "main" / ".quest"
    worktree_quest.parent.mkdir()

    assert apply_quest_symlink(worktree_quest, shared_quest) == "created"

    assert worktree_quest.is_symlink()
    assert _target(worktree_quest) == shared_quest
    assert shared_quest.is_dir()


def test_apply_quest_symlink_real_dir_migrates_without_loss(tmp_path: Path) -> None:
    worktree_quest = tmp_path / "worktree" / ".quest"
    shared_quest = tmp_path / "main" / ".quest"
    (worktree_quest / "quest-a").mkdir(parents=True)
    (worktree_quest / "quest-a" / "state.json").write_text("a", encoding="utf-8")
    (worktree_quest / "quest-b").mkdir()
    (worktree_quest / "quest-b" / "state.json").write_text("b", encoding="utf-8")
    (shared_quest / "quest-c").mkdir(parents=True)
    (shared_quest / "quest-c" / "state.json").write_text("c", encoding="utf-8")

    assert apply_quest_symlink(worktree_quest, shared_quest) == "migrated"

    assert worktree_quest.is_symlink()
    assert (shared_quest / "quest-a" / "state.json").read_text() == "a"
    assert (shared_quest / "quest-b" / "state.json").read_text() == "b"
    assert (shared_quest / "quest-c" / "state.json").read_text() == "c"


def test_apply_quest_symlink_existing_symlink_is_present_noop(tmp_path: Path) -> None:
    worktree_quest = tmp_path / "worktree" / ".quest"
    shared_quest = tmp_path / "main" / ".quest"
    worktree_quest.parent.mkdir()
    shared_quest.mkdir(parents=True)
    worktree_quest.symlink_to(shared_quest)

    assert apply_quest_symlink(worktree_quest, shared_quest) == "present"
    assert _target(worktree_quest) == shared_quest


def test_apply_quest_symlink_wrong_symlink_preserves_and_replaces(
    tmp_path: Path,
) -> None:
    worktree_quest = tmp_path / "worktree" / ".quest"
    shared_quest = tmp_path / "main" / ".quest"
    wrong_quest = tmp_path / "wrong" / ".quest"
    worktree_quest.parent.mkdir()
    shared_quest.mkdir(parents=True)
    wrong_quest.mkdir(parents=True)
    worktree_quest.symlink_to(wrong_quest)

    assert apply_quest_symlink(worktree_quest, shared_quest) == "conflict"

    assert worktree_quest.is_symlink()
    assert _target(worktree_quest) == shared_quest
    preserved = shared_quest.parent / ".quest_conflicts" / "worktree" / ".quest"
    assert preserved.is_symlink()
    assert _target(preserved) == wrong_quest


def test_apply_quest_symlink_empty_real_dir_returns_created(tmp_path: Path) -> None:
    worktree_quest = tmp_path / "worktree" / ".quest"
    shared_quest = tmp_path / "main" / ".quest"
    worktree_quest.mkdir(parents=True)

    assert apply_quest_symlink(worktree_quest, shared_quest) == "created"

    assert worktree_quest.is_symlink()
    assert _target(worktree_quest) == shared_quest


def test_apply_quest_symlink_conflict_preserves_both_outside_quest(
    tmp_path: Path,
) -> None:
    worktree_quest = tmp_path / "worktree" / ".quest"
    shared_quest = tmp_path / "main" / ".quest"
    (worktree_quest / "same-id").mkdir(parents=True)
    (worktree_quest / "same-id" / "state.json").write_text(
        "worktree",
        encoding="utf-8",
    )
    (shared_quest / "same-id").mkdir(parents=True)
    (shared_quest / "same-id" / "state.json").write_text(
        "shared",
        encoding="utf-8",
    )

    assert apply_quest_symlink(worktree_quest, shared_quest) == "conflict"

    assert worktree_quest.is_symlink()
    assert (shared_quest / "same-id" / "state.json").read_text() == "shared"
    conflict_copy = (
        shared_quest.parent
        / ".quest_conflicts"
        / "worktree"
        / "same-id"
        / "state.json"
    )
    assert conflict_copy.read_text() == "worktree"
    assert shared_quest not in conflict_copy.parents
    assert not list(shared_quest.glob("**/.quest_conflicts"))


def test_ensure_shared_quest_symlink_main_repo_returns_na(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert ensure_shared_quest_symlink(repo, repo) == "n/a"
    assert not (repo / ".quest").exists()
    assert not (repo / ".quest").is_symlink()


def test_ensure_shared_quest_symlink_linked_worktree_creates(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    worktree = tmp_path / "linked"
    _git(repo, "worktree", "add", "-b", "feature/linked", str(worktree), "main")

    assert ensure_shared_quest_symlink(repo, worktree) == "created"
    assert (worktree / ".quest").is_symlink()
    assert _target(worktree / ".quest") == repo / ".quest"


def test_startup_skipped_in_linked_worktree_migrates_real_quest_dir(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    allowlist = _write_allowlist(repo, "branch")
    worktree = tmp_path / "human-worktree"
    _git(repo, "worktree", "add", "-b", "feature/human", str(worktree), "main")
    (worktree / ".quest" / "orphaned-quest").mkdir(parents=True)
    (worktree / ".quest" / "orphaned-quest" / "state.json").write_text(
        "orphan",
        encoding="utf-8",
    )

    payload = _run_startup(worktree, allowlist, "new-quest", "branch")

    assert payload["status"] == "skipped"
    assert payload["branch_mode"] == "none"
    assert payload["quest_symlink"] == "migrated"
    assert (worktree / ".quest").is_symlink()
    assert _target(worktree / ".quest") == repo / ".quest"
    assert (repo / ".quest" / "orphaned-quest" / "state.json").read_text() == "orphan"


def test_startup_none_mode_in_linked_worktree_creates_symlink(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    allowlist = _write_allowlist(repo, "none")
    _git(repo, "checkout", "-b", "holder")
    worktree = tmp_path / "main-linked"
    _git(repo, "worktree", "add", str(worktree), "main")

    payload = _run_startup(worktree, allowlist, "new-quest", "none")

    assert payload["status"] == "skipped"
    assert payload["branch_mode"] == "none"
    assert payload["quest_symlink"] == "created"
    assert (worktree / ".quest").is_symlink()
    assert _target(worktree / ".quest") == repo / ".quest"


def test_startup_branch_mode_in_linked_worktree_creates_symlink(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    allowlist = _write_allowlist(repo, "branch")
    _git(repo, "checkout", "-b", "holder")
    worktree = tmp_path / "main-linked"
    _git(repo, "worktree", "add", str(worktree), "main")

    payload = _run_startup(worktree, allowlist, "new-quest", "branch")

    assert payload["status"] == "created"
    assert payload["branch_mode"] == "branch"
    assert payload["quest_symlink"] == "created"
    assert _git(worktree, "branch", "--show-current") == "quest/new-quest"
    assert (worktree / ".quest").is_symlink()
    assert _target(worktree / ".quest") == repo / ".quest"


def test_startup_worktree_mode_creates_symlink_and_reports_created(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    allowlist = _write_allowlist(repo, "worktree")

    payload = _run_startup(repo, allowlist, "new-quest", "worktree")
    worktree = Path(payload["worktree_path"])

    assert payload["status"] == "created"
    assert payload["branch_mode"] == "worktree"
    assert payload["quest_symlink"] == "created"
    assert (worktree / ".quest").is_symlink()
    assert _target(worktree / ".quest") == repo / ".quest"


def test_startup_worktree_mode_from_linked_worktree_migrates_current_workspace(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    allowlist = _write_allowlist(repo, "worktree")
    _git(repo, "checkout", "-b", "holder")
    current_worktree = tmp_path / "main-linked"
    _git(repo, "worktree", "add", str(current_worktree), "main")
    (current_worktree / ".quest" / "orphaned-quest").mkdir(parents=True)
    (current_worktree / ".quest" / "orphaned-quest" / "state.json").write_text(
        "orphan",
        encoding="utf-8",
    )

    payload = _run_startup(current_worktree, allowlist, "new-quest", "worktree")
    created_worktree = Path(payload["worktree_path"])

    assert payload["status"] == "created"
    assert payload["branch_mode"] == "worktree"
    assert payload["quest_symlink"] == "migrated"
    assert (current_worktree / ".quest").is_symlink()
    assert _target(current_worktree / ".quest") == repo / ".quest"
    assert (created_worktree / ".quest").is_symlink()
    assert _target(created_worktree / ".quest") == repo / ".quest"
    assert (repo / ".quest" / "orphaned-quest" / "state.json").read_text() == "orphan"


def test_startup_main_repo_none_and_branch_report_na(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    allowlist = _write_allowlist(repo, "none")

    none_payload = _run_startup(repo, allowlist, "no-branch", "none")
    branch_payload = _run_startup(repo, allowlist, "with-branch", "branch")

    assert none_payload["quest_symlink"] == "n/a"
    assert branch_payload["quest_symlink"] == "n/a"
    assert not (repo / ".quest").is_symlink()
