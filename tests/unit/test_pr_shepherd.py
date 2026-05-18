from __future__ import annotations

import json
from pathlib import Path

import pytest

import pr_shepherd_annotate_scope
import pr_shepherd_checkout
import pr_shepherd_collect_intake
import pr_shepherd_fetch_failed_logs
import pr_shepherd_post_reply
from quest_runtime.pr_shepherd import (
    ADDRESSED_MARKER,
    FOLLOWUP_MARKER,
    SUMMARY_MARKER,
    append_marker,
    activity_state,
    classify_operational_state,
    compact_summary_body,
    stable_fingerprint,
)


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_marker_parser_accepts_current_and_older_versions() -> None:
    assert ADDRESSED_MARKER in append_marker("done", ADDRESSED_MARKER)
    assert append_marker("done\n\n<!-- pr-shepherd:addressed v0 -->", ADDRESSED_MARKER).count(
        "pr-shepherd:addressed"
    ) == 1


def test_activity_state_active_when_human_after_marker() -> None:
    assert activity_state(
        [
            {"created_at": "1", "author_kind": "bot", "body": ADDRESSED_MARKER},
            {"created_at": "2", "author_kind": "human", "body": "Still broken"},
        ]
    ) == "active"


def test_activity_state_addressed_when_marker_is_latest() -> None:
    assert activity_state(
        [
            {"created_at": "1", "author_kind": "human", "body": "Please fix"},
            {"created_at": "2", "author_kind": "bot", "body": ADDRESSED_MARKER},
        ]
    ) == "addressed"


def test_activity_state_uncertain_when_automation_after_marker() -> None:
    assert activity_state(
        [
            {"created_at": "1", "author_kind": "bot", "body": ADDRESSED_MARKER},
            {"created_at": "2", "author_kind": "bot", "body": "New automated note"},
        ]
    ) == "uncertain"


def test_fingerprint_is_stable_for_same_source_payload() -> None:
    payload = {"source_kind": "review_thread", "path": "a.py", "line": 4, "body": "Fix it"}
    assert stable_fingerprint(payload) == stable_fingerprint(dict(reversed(payload.items())))


def test_operational_state_clean_requires_success_and_no_active_feedback() -> None:
    result = classify_operational_state(
        {"outcome": "success"},
        {
            "ci_state": "green",
            "pushed_commits_count": 0,
            "posted_replies_count": 0,
            "active_feedback_count": 0,
            "uncertain_feedback_count": 0,
            "unresolved_human_decision_count": 0,
        },
    )
    assert result["operational_state"] == "clean"


def test_operational_state_clean_wins_over_progressing_when_final_state_ready() -> None:
    result = classify_operational_state(
        {"outcome": "success"},
        {
            "ci_state": "green",
            "pushed_commits_count": 1,
            "posted_replies_count": 2,
            "active_feedback_count": 0,
            "uncertain_feedback_count": 0,
            "unresolved_human_decision_count": 0,
        },
    )
    assert result["operational_state"] == "clean"


def test_operational_state_stuck_wins_when_loop_cap_or_blocker_exists() -> None:
    result = classify_operational_state(
        {"outcome": "success"},
        {
            "ci_state": "green",
            "pushed_commits_count": 1,
            "posted_replies_count": 1,
            "active_feedback_count": 0,
            "uncertain_feedback_count": 0,
            "unresolved_human_decision_count": 0,
            "loop_cap_enforced": True,
        },
    )
    assert result["operational_state"] == "stuck"
    assert result["blocker"] == "loop_cap_enforced"


def test_operational_state_stuck_when_ci_green_but_active_feedback_remains() -> None:
    result = classify_operational_state(
        {"outcome": "success"},
        {
            "ci_state": "green",
            "active_feedback_count": 1,
            "uncertain_feedback_count": 0,
            "unresolved_human_decision_count": 0,
        },
    )
    assert result["operational_state"] == "stuck"
    assert result["blocker"] == "feedback_remaining"


def test_operational_state_progressing_when_replies_or_commits_happened() -> None:
    result = classify_operational_state(
        {"outcome": "continue"},
        {
            "ci_state": "pending",
            "pushed_commits_count": 1,
            "posted_replies_count": 0,
            "active_feedback_count": 0,
            "uncertain_feedback_count": 0,
            "unresolved_human_decision_count": 0,
        },
    )
    assert result["operational_state"] == "progressing"


@pytest.mark.parametrize("ci_state", ["failing", "unknown"])
def test_operational_state_stuck_when_terminal_ci_not_green_even_with_progress(ci_state: str) -> None:
    result = classify_operational_state(
        {"outcome": "continue"},
        {
            "ci_state": ci_state,
            "pushed_commits_count": 1,
            "posted_replies_count": 1,
            "active_feedback_count": 0,
            "uncertain_feedback_count": 0,
            "unresolved_human_decision_count": 0,
        },
    )
    assert result["operational_state"] == "stuck"
    assert result["blocker"] == f"ci_{ci_state}"


def test_checkout_inspects_explicit_number_without_apply_even_when_dirty(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> _Result:
        calls.append(args)
        if args[:3] == ["git", "branch", "--show-current"]:
            return _Result(stdout="feature/current\n")
        if args[:3] == ["git", "status", "--short"]:
            return _Result(stdout=" M file.py\n")
        if args[:3] == ["gh", "pr", "view"]:
            return _Result(stdout=json.dumps({"number": 12, "url": "u", "headRefName": "feature/other"}))
        return _Result()

    monkeypatch.setattr(pr_shepherd_checkout, "_run", fake_run)
    code, payload = pr_shepherd_checkout.inspect_checkout("12", apply=False)

    assert code == 0
    assert payload["action"] == "would_checkout"
    assert payload["worktree_clean"] is False
    assert {"ok", "action", "target_pr", "target_branch", "current_branch", "worktree_clean", "reason"} <= set(
        payload
    )
    assert ["gh", "pr", "checkout", "12"] not in calls


def test_checkout_refuses_dirty_worktree_before_apply_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:3] == ["git", "branch", "--show-current"]:
            return _Result(stdout="feature/current\n")
        if args[:3] == ["git", "status", "--short"]:
            return _Result(stdout=" M file.py\n")
        if args[:3] == ["gh", "pr", "view"]:
            return _Result(stdout=json.dumps({"number": 12, "url": "u", "headRefName": "feature/other"}))
        return _Result()

    monkeypatch.setattr(pr_shepherd_checkout, "_run", fake_run)
    code, payload = pr_shepherd_checkout.inspect_checkout("12", apply=True)

    assert code == 1
    assert payload["reason"] == "dirty_worktree"


def test_checkout_noops_when_already_on_target_pr_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:3] == ["git", "branch", "--show-current"]:
            return _Result(stdout="feature/current\n")
        if args[:3] == ["git", "status", "--short"]:
            return _Result(stdout="")
        if args[:3] == ["gh", "pr", "view"]:
            return _Result(stdout=json.dumps({"number": 12, "url": "u", "headRefName": "feature/current"}))
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(pr_shepherd_checkout, "_run", fake_run)
    code, payload = pr_shepherd_checkout.inspect_checkout("12", apply=True)

    assert code == 0
    assert payload["action"] == "none"


def test_checkout_refuses_worktree_branch_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str]) -> _Result:
        if args[:3] == ["git", "branch", "--show-current"]:
            return _Result(stdout="feature/current\n")
        if args[:3] == ["git", "status", "--short"]:
            return _Result(stdout="")
        if args[:3] == ["gh", "pr", "view"]:
            return _Result(stdout=json.dumps({"number": 12, "url": "u", "headRefName": "feature/other"}))
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(pr_shepherd_checkout, "_run", fake_run)
    monkeypatch.setattr(pr_shepherd_checkout, "_is_linked_worktree", lambda: True)

    code, payload = pr_shepherd_checkout.inspect_checkout("12", apply=True)

    assert code == 1
    assert payload["ok"] is False
    assert payload["reason"] == "worktree_mismatch"


def test_checkout_branch_mismatch_uses_git_worktree_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> _Result:
        calls.append(args)
        if args[:3] == ["git", "branch", "--show-current"]:
            return _Result(stdout="feature/current\n")
        if args[:3] == ["git", "status", "--short"]:
            return _Result(stdout="")
        if args[:3] == ["gh", "pr", "view"]:
            return _Result(stdout=json.dumps({"number": 12, "url": "u", "headRefName": "feature/other"}))
        if args == ["git", "rev-parse", "--git-dir"]:
            return _Result(stdout="/repo/.git/worktrees/current\n")
        if args == ["git", "rev-parse", "--git-common-dir"]:
            return _Result(stdout="/repo/.git\n")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(pr_shepherd_checkout, "_run", fake_run)
    code, payload = pr_shepherd_checkout.inspect_checkout("12", apply=True)

    assert code == 1
    assert payload["reason"] == "worktree_mismatch"
    assert ["gh", "pr", "checkout", "12"] not in calls


def test_checkout_supports_target_option_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_inspect(target: str | None, *, apply: bool) -> tuple[int, dict[str, object]]:
        seen["target"] = target
        seen["apply"] = apply
        return 0, {"ok": True}

    monkeypatch.setattr(pr_shepherd_checkout, "inspect_checkout", fake_inspect)
    monkeypatch.setattr("sys.argv", ["pr_shepherd_checkout.py", "--target", "123", "--apply"])

    assert pr_shepherd_checkout.main() == 0
    assert seen == {"target": "123", "apply": True}


def test_scope_in_diff_for_added_line(tmp_path: Path) -> None:
    diff = tmp_path / "diff.patch"
    findings = tmp_path / "findings.json"
    output = tmp_path / "out.json"
    diff.write_text("diff --git a/a.py b/a.py\n+++ b/a.py\n@@ -1,1 +1,2 @@\n old\n+new\n", encoding="utf-8")
    findings.write_text(json.dumps([{"path": "a.py", "line": 2}]), encoding="utf-8")

    annotated = pr_shepherd_annotate_scope.annotate(json.loads(findings.read_text()), diff.read_text())
    output.write_text(json.dumps(annotated), encoding="utf-8")

    assert annotated[0]["scope"] == "in_diff"


def test_scope_unknown_for_removed_old_line() -> None:
    diff_text = "diff --git a/a.py b/a.py\n+++ b/a.py\n@@ -1,2 +1,1 @@\n-old\n keep\n"
    annotated = pr_shepherd_annotate_scope.annotate([{"path": "a.py", "line": 1}], diff_text)
    assert annotated[0]["scope"] == "unknown"


def test_scope_unknown_for_context_line(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.py b/a.py\n+++ b/a.py\n@@ -1,3 +1,4 @@\n one\n two\n+new\n three\n"
    annotated = pr_shepherd_annotate_scope.annotate([{"path": "a.py", "line": 1}], diff_text)
    assert annotated[0]["scope"] == "unknown"


def test_scope_in_diff_for_deleted_file_after_another_file() -> None:
    diff_text = "\n".join(
        [
            "diff --git a/kept.py b/kept.py",
            "--- a/kept.py",
            "+++ b/kept.py",
            "@@ -1,1 +1,2 @@",
            " keep",
            "+added",
            "diff --git a/deleted.py b/deleted.py",
            "--- a/deleted.py",
            "+++ /dev/null",
            "@@ -1,2 +0,0 @@",
            "-gone",
            "-removed",
            "",
        ]
    )

    annotated = pr_shepherd_annotate_scope.annotate(
        [
            {"path": "deleted.py", "line": 1},
            {"path": "kept.py", "line": 1},
        ],
        diff_text,
    )

    assert annotated[0]["scope"] == "unknown"
    assert annotated[1]["scope"] == "unknown"


def test_compact_summary_body_is_metadata_only() -> None:
    body = compact_summary_body([{"state": "defer", "fingerprint": "abcdef1234567890", "url": "https://x"}])
    assert "PR shepherd status" in body
    assert "abcdef1234567890" in body
    assert "pr-shepherd:summary" in body
    assert "because" not in body.lower()


def test_collect_intake_emits_records_without_legacy_typed_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_gh_json(args: list[str]) -> tuple[object | None, str]:
        joined = " ".join(args)
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 12,
                "url": "https://example.test/pull/12",
                "headRefName": "feature",
                "baseRefName": "main",
                "isDraft": True,
                "statusCheckRollup": [
                    {"name": "unit", "conclusion": "FAILURE", "detailsUrl": "https://ci.test/unit"}
                ],
            }, ""
        if "/pulls/12/comments" in joined:
            return [
                {
                    "id": 100,
                    "body": "Please fix this",
                    "user": {"login": "alice", "type": "User"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "path": "scripts/a.py",
                    "line": 4,
                    "html_url": "https://example.test/r100",
                },
                {
                    "id": 101,
                    "in_reply_to_id": 100,
                    "body": "Done\n\n" + ADDRESSED_MARKER,
                    "user": {"login": "bot[bot]", "type": "Bot"},
                    "created_at": "2026-01-01T00:01:00Z",
                },
                {
                    "id": 102,
                    "in_reply_to_id": 100,
                    "body": "Still needs work",
                    "user": {"login": "alice", "type": "User"},
                    "created_at": "2026-01-01T00:02:00Z",
                },
            ], ""
        if "/issues/12/comments" in joined:
            return [
                {
                    "id": 200,
                    "body": "PR shepherd status\n\n" + SUMMARY_MARKER,
                    "user": {"login": "bot[bot]", "type": "Bot"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "html_url": "https://example.test/c200",
                }
            ], ""
        if "/pulls/12/reviews" in joined:
            return [
                {
                    "id": 300,
                    "body": "Review body item",
                    "user": {"login": "carol", "type": "User"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "html_url": "https://example.test/review300",
                }
            ], ""
        return [], ""

    monkeypatch.setattr(pr_shepherd_collect_intake, "_gh_json", fake_gh_json)

    payload = pr_shepherd_collect_intake.collect(12, page_cap=1)

    assert "inline_comments" not in payload
    assert "general_comments" not in payload
    kinds = {record["source_kind"]: record for record in payload["records"]}
    assert {"check_run", "review_thread", "shepherd_summary", "review_body_item"} <= set(kinds)
    assert kinds["review_thread"]["activity_state"] == "active"


def test_collect_intake_skips_successful_legacy_status_contexts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_gh_json(args: list[str]) -> tuple[object | None, str]:
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 12,
                "url": "https://example.test/pull/12",
                "headRefName": "feature",
                "baseRefName": "main",
                "isDraft": True,
                "statusCheckRollup": [
                    {
                        "context": "ci/external",
                        "state": "SUCCESS",
                        "targetUrl": "https://ci.test/external",
                    },
                    {
                        "context": "ci/failing",
                        "state": "FAILURE",
                        "targetUrl": "https://ci.test/failing",
                    },
                ],
            }, ""
        return [], ""

    monkeypatch.setattr(pr_shepherd_collect_intake, "_gh_json", fake_gh_json)

    payload = pr_shepherd_collect_intake.collect(12, page_cap=1)

    check_records = [record for record in payload["records"] if record["source_kind"] == "check_run"]
    assert len(check_records) == 1
    assert check_records[0]["source_label"] == "ci/failing"
    assert check_records[0]["body_excerpt"] == "ci/failing: Check state: failure"
    assert check_records[0]["url"] == "https://ci.test/failing"


def test_collect_intake_reports_pagination_truncated_when_page_cap_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_gh_json(args: list[str]) -> tuple[object | None, str]:
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 12,
                "url": "https://example.test/pull/12",
                "headRefName": "feature",
                "baseRefName": "main",
                "isDraft": True,
                "statusCheckRollup": [],
            }, ""
        return [{"id": index, "body": "x"} for index in range(pr_shepherd_collect_intake.PER_PAGE)], ""

    monkeypatch.setattr(pr_shepherd_collect_intake, "_gh_json", fake_gh_json)

    payload = pr_shepherd_collect_intake.collect(12, page_cap=1)

    assert any(item["unavailable_reason"] == "pagination_truncated" for item in payload["unavailable"])


def test_collect_intake_uses_get_for_paginated_api_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_gh_json(args: list[str]) -> tuple[object | None, str]:
        seen.append(args)
        return [], ""

    monkeypatch.setattr(pr_shepherd_collect_intake, "_gh_json", fake_gh_json)

    pr_shepherd_collect_intake._gh_api_page("repos/{owner}/{repo}/pulls/12/comments", 2)

    assert seen == [
        [
            "gh",
            "api",
            "repos/{owner}/{repo}/pulls/12/comments",
            "--method",
            "GET",
            "-F",
            f"per_page={pr_shepherd_collect_intake.PER_PAGE}",
            "-F",
            "page=2",
        ]
    ]


def test_failed_log_summary_includes_records_with_bounded_lines_and_metadata() -> None:
    result = _Result(stdout="\n".join(f"line-{index}" for index in range(1, 8)))

    payload = pr_shepherd_fetch_failed_logs.build_payload(
        run_id="999",
        result=result,
        head=2,
        tail=2,
        check_name="unit",
        job_name="pytest",
        raw_log_url="https://ci.test/raw",
    )

    assert payload["ok"] is True
    assert payload["lines"] == ["line-1", "line-2", "... truncated 3 lines ...", "line-6", "line-7"]
    record = payload["records"][0]
    assert record["source_kind"] == "failed_log_summary"
    assert record["source_label"] == "unit"
    assert record["run_id"] == "999"
    assert record["check_name"] == "unit"
    assert record["job_name"] == "pytest"
    assert record["raw_log_url"] == "https://ci.test/raw"
    assert "line-1" in record["body_excerpt"]


def test_failed_log_summary_reports_unavailable_with_metadata() -> None:
    result = _Result(returncode=1, stderr="external provider unavailable")

    payload = pr_shepherd_fetch_failed_logs.build_payload(
        run_id="999",
        result=result,
        head=2,
        tail=2,
        check_name="deploy",
        job_name="provider",
        raw_log_url="https://ci.test/raw",
    )

    assert payload["ok"] is False
    assert payload["unavailable_reason"] == "log_unavailable"
    assert payload["unavailable"][0]["check_name"] == "deploy"
    assert payload["unavailable"][0]["raw_log_url"] == "https://ci.test/raw"


def test_collect_intake_merges_failed_log_summary_records(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_gh_json(args: list[str]) -> tuple[object | None, str]:
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 12,
                "url": "https://example.test/pull/12",
                "headRefName": "feature",
                "baseRefName": "main",
                "isDraft": True,
                "statusCheckRollup": [],
            }, ""
        return [], ""

    monkeypatch.setattr(pr_shepherd_collect_intake, "_gh_json", fake_gh_json)
    failed_summary = {
        "records": [
            {
                "source_kind": "failed_log_summary",
                "source_label": "unit",
                "activity_state": "active",
                "path": "ci/log",
                "line": None,
                "body_excerpt": "failed",
                "raw_log_url": "https://ci.test/raw",
            }
        ],
        "unavailable": [{"source_kind": "failed_log_summary", "unavailable_reason": "log_unavailable"}],
    }

    payload = pr_shepherd_collect_intake.collect(12, page_cap=1, failed_log_summaries=[failed_summary])

    assert any(record["source_kind"] == "failed_log_summary" for record in payload["records"])
    assert any(item["unavailable_reason"] == "log_unavailable" for item in payload["unavailable"])


def test_collect_intake_failed_log_summary_parse_failure_becomes_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "failed-log.json"
    path.write_text("{not json", encoding="utf-8")

    summary = pr_shepherd_collect_intake._load_failed_log_summary(str(path))

    assert summary["records"] == []
    assert summary["unavailable"][0]["unavailable_reason"] == "parse_failed"
    assert summary["unavailable"][0]["path"] == str(path)


def test_collect_intake_failed_log_summary_read_failure_becomes_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    summary = pr_shepherd_collect_intake._load_failed_log_summary(str(path))

    assert summary["records"] == []
    assert summary["unavailable"][0]["unavailable_reason"] == "read_failed"
    assert summary["unavailable"][0]["path"] == str(path)


def test_collect_intake_failed_log_summary_decode_failure_becomes_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "bad-encoding.json"
    path.write_bytes(b"\xff\xfe\x00")

    summary = pr_shepherd_collect_intake._load_failed_log_summary(str(path))

    assert summary["records"] == []
    assert summary["unavailable"][0]["unavailable_reason"] == "decode_failed"
    assert summary["unavailable"][0]["path"] == str(path)


def test_post_reply_live_thread_uses_pr_comment_reply_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(args: list[str], *, input_text: str | None = None) -> _Result:
        calls.append((args, input_text))
        return _Result(stdout="{}")

    monkeypatch.setattr(pr_shepherd_post_reply, "_run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["pr_shepherd_post_reply.py", "--pr", "12", "--thread-id", "99", "--body", "@alice fixed"],
    )

    assert pr_shepherd_post_reply.main() == 0
    assert calls == [
        (
            [
                "gh",
                "api",
                "repos/{owner}/{repo}/pulls/12/comments/99/replies",
                "-X",
                "POST",
                "--input",
                "-",
            ],
            json.dumps({"body": f"@alice fixed\n\n{ADDRESSED_MARKER}\n"}, ensure_ascii=True),
        )
    ]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_post_reply_summary_live_updates_existing_marker_comment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(args: list[str], *, input_text: str | None = None) -> _Result:
        calls.append((args, input_text))
        if args[:2] == ["gh", "api"] and args[2].endswith("/issues/12/comments"):
            return _Result(stdout=json.dumps([{"id": 200, "body": SUMMARY_MARKER}]))
        return _Result(stdout="{}")

    monkeypatch.setattr(pr_shepherd_post_reply, "_run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["pr_shepherd_post_reply.py", "--summary", "--pr", "12", "--body", "status"],
    )

    assert pr_shepherd_post_reply.main() == 0
    assert calls[-1] == (
        ["gh", "api", "repos/{owner}/{repo}/issues/comments/200", "-X", "PATCH", "--input", "-"],
        json.dumps({"body": f"status\n\n{SUMMARY_MARKER}\n"}, ensure_ascii=True),
    )
    assert json.loads(capsys.readouterr().out)["action"] == "update_summary"


def test_post_reply_summary_scans_bounded_comment_pages(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(args: list[str], *, input_text: str | None = None) -> _Result:
        calls.append((args, input_text))
        if args[:2] == ["gh", "api"] and args[2].endswith("/issues/12/comments"):
            page_arg = next(item for item in args if item.startswith("page="))
            if page_arg == "page=1":
                return _Result(stdout=json.dumps([{"id": index, "body": "old"} for index in range(100)]))
            return _Result(stdout=json.dumps([{"id": 200, "body": SUMMARY_MARKER}]))
        return _Result(stdout="{}")

    monkeypatch.setattr(pr_shepherd_post_reply, "_run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["pr_shepherd_post_reply.py", "--summary", "--pr", "12", "--body", "status"],
    )

    assert pr_shepherd_post_reply.main() == 0
    assert calls[-1] == (
        ["gh", "api", "repos/{owner}/{repo}/issues/comments/200", "-X", "PATCH", "--input", "-"],
        json.dumps({"body": f"status\n\n{SUMMARY_MARKER}\n"}, ensure_ascii=True),
    )
    assert json.loads(capsys.readouterr().out)["action"] == "update_summary"


def test_post_reply_refuses_missing_target_without_summary_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["pr_shepherd_post_reply.py", "--body", "Fixed"])

    with pytest.raises(ValueError, match="--pr and --thread-id"):
        pr_shepherd_post_reply.main()
