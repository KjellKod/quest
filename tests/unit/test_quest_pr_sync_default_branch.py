from __future__ import annotations

import quest_pr_sync_default_branch


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _install_runner(monkeypatch, handler):
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> _Result:
        calls.append(args)
        return handler(args)

    monkeypatch.setattr(quest_pr_sync_default_branch, "_run", fake_run)
    return calls


def _standard_success(args: list[str]) -> _Result:
    if args == ["git", "fetch", "origin"]:
        return _Result()
    if args == ["git", "ls-remote", "--symref", "origin", "HEAD"]:
        return _Result(stdout="ref: refs/heads/main\tHEAD\n")
    if args == ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"]:
        return _Result(returncode=1)
    if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
        return _Result(stdout="a" * 40 + "\0")
    if args == ["git", "status", "--porcelain"]:
        return _Result()
    if args == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
        return _Result(returncode=1)
    if args == ["git", "branch", "--show-current"]:
        return _Result(stdout="feature\n")
    if args == ["git", "rev-parse", "--verify", "-q", "refs/remotes/origin/feature"]:
        return _Result(returncode=1)
    if len(args) == 5 and args[:4] == ["git", "rev-parse", "--verify", "-q"]:
        return _Result(returncode=1)
    return _Result()


def test_detects_default_branch_via_remote_head(monkeypatch) -> None:
    calls = _install_runner(
        monkeypatch,
        lambda args: (
            _Result(stdout="ref: refs/heads/trunk\tHEAD\nc0ffee\tHEAD\n")
            if args == ["git", "ls-remote", "--symref", "origin", "HEAD"]
            else _Result(returncode=1)
        ),
    )

    assert quest_pr_sync_default_branch.detect_default_branch() == (
        "trunk",
        "ls-remote",
    )
    assert ["git", "symbolic-ref", "refs/remotes/origin/HEAD"] not in calls
    assert [
        "gh",
        "repo",
        "view",
        "--json",
        "defaultBranchRef",
        "--jq",
        ".defaultBranchRef.name",
    ] not in calls


def test_falls_back_to_symbolic_ref_when_remote_head_fails(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "ls-remote", "--symref", "origin", "HEAD"]:
            return _Result(returncode=1)
        if args == ["git", "symbolic-ref", "refs/remotes/origin/HEAD"]:
            return _Result(stdout="refs/remotes/origin/trunk\n")
        raise AssertionError(f"unexpected call: {args}")

    calls = _install_runner(monkeypatch, fake_run)

    assert quest_pr_sync_default_branch.detect_default_branch() == (
        "trunk",
        "symbolic-ref",
    )
    assert [
        "gh",
        "repo",
        "view",
        "--json",
        "defaultBranchRef",
        "--jq",
        ".defaultBranchRef.name",
    ] not in calls


def test_falls_back_to_gh_when_git_default_detection_fails(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "ls-remote", "--symref", "origin", "HEAD"]:
            return _Result(returncode=1)
        if args == ["git", "symbolic-ref", "refs/remotes/origin/HEAD"]:
            return _Result(returncode=1)
        if args == [
            "gh",
            "repo",
            "view",
            "--json",
            "defaultBranchRef",
            "--jq",
            ".defaultBranchRef.name",
        ]:
            return _Result(stdout="develop\n")
        raise AssertionError(f"unexpected call: {args}")

    _install_runner(monkeypatch, fake_run)

    assert quest_pr_sync_default_branch.detect_default_branch() == ("develop", "gh")


def test_up_to_date_is_noop_no_rebase(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "fetch", "origin"]:
            return _Result()
        if args == ["git", "ls-remote", "--symref", "origin", "HEAD"]:
            return _Result(stdout="ref: refs/heads/main\tHEAD\n")
        if args == ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"]:
            return _Result(returncode=0)
        raise AssertionError(f"unexpected call: {args}")

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync(apply=True)

    assert code == 0
    assert payload["status"] == "up_to_date"
    assert payload["push_required"] is False
    assert not any(call[:2] == ["git", "rebase"] for call in calls)
    assert not any(call[:2] == ["git", "merge"] for call in calls)


def test_clean_inspect_reports_would_rebase_without_mutating(monkeypatch) -> None:
    calls = _install_runner(monkeypatch, _standard_success)
    code, payload = quest_pr_sync_default_branch.sync(apply=False)

    assert code == 0
    assert payload["status"] == "clean"
    assert payload["action"] == "would_rebase"
    assert payload["applied"] is False
    assert not any(call == ["git", "rebase", "origin/main"] for call in calls)


def test_clean_apply_rebase_sets_force_with_lease_true(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("rebase", apply=True)

    assert code == 0
    assert payload["status"] == "synced"
    assert payload["action"] == "rebased"
    assert payload["push_required"] is True
    assert payload["force_with_lease"] is True
    assert ["git", "rebase", "origin/main"] in calls


def test_clean_apply_merge_sets_force_with_lease_false(monkeypatch) -> None:
    calls = _install_runner(monkeypatch, _standard_success)
    code, payload = quest_pr_sync_default_branch.sync("merge", apply=True)

    assert code == 0
    assert payload["status"] == "synced"
    assert payload["action"] == "merged"
    assert payload["push_required"] is True
    assert payload["force_with_lease"] is False
    assert ["git", "merge", "--no-edit", "origin/main"] in calls


def test_apply_dirty_worktree_reports_error_without_rebase(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "status", "--porcelain"]:
            return _Result(stdout=" M scripts/quest_pr_sync_default_branch.py\n")
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("rebase", apply=True)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "worktree_dirty"
    assert ["git", "rebase", "origin/main"] not in calls


def test_apply_in_progress_merge_reports_error_without_merge(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "rev-parse", "--verify", "-q", "MERGE_HEAD"]:
            return _Result(stdout="abc123\n")
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("merge", apply=True)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "merge_in_progress"
    assert ["git", "merge", "--no-edit", "origin/main"] not in calls


def test_rebase_apply_refuses_when_upstream_not_contained(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Result(stdout="origin/feature\n")
        if args == ["git", "merge-base", "--is-ancestor", "origin/feature", "HEAD"]:
            return _Result(returncode=1)
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("rebase", apply=True)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "upstream_not_contained"
    assert payload["message"] == "local HEAD does not contain origin/feature"
    assert ["git", "rebase", "origin/main"] not in calls


def test_rebase_apply_refuses_when_same_named_remote_branch_not_contained(
    monkeypatch,
) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _Result(returncode=1)
        if args == ["git", "branch", "--show-current"]:
            return _Result(stdout="quest/pre-pr-sync\n")
        if args == [
            "git",
            "rev-parse",
            "--verify",
            "-q",
            "refs/remotes/origin/quest/pre-pr-sync",
        ]:
            return _Result(stdout="abc123\n")
        if args == [
            "git",
            "merge-base",
            "--is-ancestor",
            "origin/quest/pre-pr-sync",
            "HEAD",
        ]:
            return _Result(returncode=1)
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("rebase", apply=True)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "upstream_not_contained"
    assert payload["message"] == "local HEAD does not contain origin/quest/pre-pr-sync"
    assert ["git", "rebase", "origin/main"] not in calls


def test_conflict_lists_files_and_exits_nonzero(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
            return _Result(
                returncode=1, stdout="b" * 40 + "\0src/app.py\0docs/notes.md\0"
            )
        return _standard_success(args)

    _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync(apply=False)

    assert code == 1
    assert payload["status"] == "conflict"
    assert payload["conflict_files"] == ["src/app.py", "docs/notes.md"]
    assert payload["applied"] is False


def test_apply_rebase_runs_even_when_advisory_probe_would_conflict(monkeypatch) -> None:
    # The old test encoded the defective contract: an advisory probe blocked apply.
    def fake_run(args: list[str]) -> _Result:
        if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
            return _Result(returncode=1, stdout="b" * 40 + "\0src/app.py\0")
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync(apply=True)

    assert code == 0
    assert payload["status"] == "synced"
    assert payload["action"] == "rebased"
    assert ["git", "rebase", "origin/main"] in calls


def test_apply_merge_runs_even_when_advisory_probe_would_conflict(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
            return _Result(returncode=1, stdout="b" * 40 + "\0src/app.py\0")
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("merge", apply=True)

    assert code == 0
    assert payload["status"] == "synced"
    assert payload["action"] == "merged"
    assert ["git", "merge", "--no-edit", "origin/main"] in calls


def test_conflict_never_uses_strategy_theirs_or_ours(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
            return _Result(returncode=1, stdout="b" * 40 + "\0src/app.py\0")
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    quest_pr_sync_default_branch.sync(apply=True)

    flattened = " ".join(part for call in calls for part in call)
    assert "-X theirs" not in flattened
    assert "-X ours" not in flattened


def test_inspect_merge_tree_failure_reports_error_not_conflict(monkeypatch) -> None:
    # The old test encoded the defective contract by expecting probe failure in apply.
    def fake_run(args: list[str]) -> _Result:
        if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
            return _Result(returncode=128, stderr="fatal: not a tree object\n")
        return _standard_success(args)

    _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync(apply=False)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "merge_tree_failed"
    assert payload["conflict_files"] == []


def test_apply_runs_when_advisory_probe_would_fail(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:4] == ["git", "merge-tree", "--write-tree", "--no-messages"]:
            return _Result(returncode=128, stderr="fatal: not a tree object\n")
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync(apply=True)

    assert code == 0
    assert payload["status"] == "synced"
    assert ["git", "rebase", "origin/main"] in calls


def test_apply_time_rebase_conflict_aborts_and_reports_conflict(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "rebase", "origin/main"]:
            return _Result(
                returncode=1,
                stderr="CONFLICT (content): Merge conflict in src/app.py\n",
            )
        if args == ["git", "diff", "--name-only", "--diff-filter=U"]:
            return _Result(stdout="src/app.py\n")
        if args == ["git", "rebase", "--abort"]:
            return _Result()
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("rebase", apply=True)

    assert code == 1
    assert payload["status"] == "conflict"
    assert payload["applied"] is False
    assert payload["conflict_files"] == ["src/app.py"]
    assert ["git", "rebase", "--abort"] in calls
    flattened = " ".join(part for call in calls for part in call)
    assert "-X theirs" not in flattened
    assert "-X ours" not in flattened


def test_apply_time_merge_conflict_aborts_and_reports_conflict(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "merge", "--no-edit", "origin/main"]:
            return _Result(
                returncode=1,
                stderr="CONFLICT (content): Merge conflict in src/app.py\n",
            )
        if args == ["git", "diff", "--name-only", "--diff-filter=U"]:
            return _Result(stdout="src/app.py\n")
        if args == ["git", "merge", "--abort"]:
            return _Result()
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("merge", apply=True)

    assert code == 1
    assert payload["status"] == "conflict"
    assert payload["reason"] == "merge_conflict"
    assert payload["conflict_files"] == ["src/app.py"]
    assert ["git", "merge", "--abort"] in calls


def test_rebase_failure_without_conflicted_files_aborts_and_reports_error(
    monkeypatch,
) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "rebase", "origin/main"]:
            return _Result(
                returncode=1, stderr="fatal: unable to auto-detect email address\n"
            )
        if args == ["git", "diff", "--name-only", "--diff-filter=U"]:
            return _Result(stdout="")
        if args == ["git", "rebase", "--abort"]:
            return _Result()
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("rebase", apply=True)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "rebase_failed"
    assert payload["conflict_files"] == []
    assert "auto-detect email" in payload["message"]
    assert ["git", "rebase", "--abort"] in calls


def test_merge_failure_without_conflicted_files_aborts_and_reports_error(
    monkeypatch,
) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "merge", "--no-edit", "origin/main"]:
            return _Result(returncode=1, stderr="fatal: refusing to merge unrelated\n")
        if args == ["git", "diff", "--name-only", "--diff-filter=U"]:
            return _Result(stdout="")
        if args == ["git", "merge", "--abort"]:
            return _Result()
        return _standard_success(args)

    calls = _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync("merge", apply=True)

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "merge_failed"
    assert payload["conflict_files"] == []
    assert "refusing to merge" in payload["message"]
    assert ["git", "merge", "--abort"] in calls


def test_fetch_failure_reports_error(monkeypatch) -> None:
    _install_runner(
        monkeypatch,
        lambda args: (
            _Result(returncode=1, stderr="fetch failed")
            if args == ["git", "fetch", "origin"]
            else _Result()
        ),
    )

    code, payload = quest_pr_sync_default_branch.sync()

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "fetch_failed"


def test_default_branch_undetected_reports_error(monkeypatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args == ["git", "fetch", "origin"]:
            return _Result()
        if args in (
            ["git", "ls-remote", "--symref", "origin", "HEAD"],
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            [
                "gh",
                "repo",
                "view",
                "--json",
                "defaultBranchRef",
                "--jq",
                ".defaultBranchRef.name",
            ],
        ):
            return _Result(returncode=1)
        raise AssertionError(f"unexpected call: {args}")

    _install_runner(monkeypatch, fake_run)
    code, payload = quest_pr_sync_default_branch.sync()

    assert code == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "default_branch_undetected"


def test_conflict_parser_skips_tree_oid_and_message_lines() -> None:
    output = "\n".join(
        [
            "c" * 40,
            "src/app.py",
            "docs/notes.md",
            "",
            "Auto-merging src/app.py",
            "CONFLICT (content): Merge conflict in src/app.py",
        ]
    )

    assert quest_pr_sync_default_branch._parse_conflict_files(output) == [
        "src/app.py",
        "docs/notes.md",
    ]
