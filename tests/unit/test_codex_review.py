"""Unit tests for .github/scripts/codex_review.py -- extracted CI review logic."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Make the script importable
_scripts_dir = str(Path(__file__).resolve().parent.parent.parent / ".github" / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import codex_review  # noqa: E402


# ---------------------------------------------------------------------------
# normalize_severity
# ---------------------------------------------------------------------------

class TestNormalizeSeverity:
    def test_valid_values(self):
        assert codex_review.normalize_severity("blocker") == "blocker"
        assert codex_review.normalize_severity("must-fix") == "must-fix"
        assert codex_review.normalize_severity("should-fix") == "should-fix"

    def test_case_insensitive(self):
        assert codex_review.normalize_severity("BLOCKER") == "blocker"
        assert codex_review.normalize_severity("Must-Fix") == "must-fix"
        assert codex_review.normalize_severity("SHOULD-FIX") == "should-fix"

    def test_strips_whitespace(self):
        assert codex_review.normalize_severity("  blocker  ") == "blocker"
        assert codex_review.normalize_severity("\tmust-fix\n") == "must-fix"

    def test_invalid_returns_none(self):
        assert codex_review.normalize_severity("nit") is None
        assert codex_review.normalize_severity("info") is None
        assert codex_review.normalize_severity("") is None
        assert codex_review.normalize_severity("critical") is None

    def test_non_string_returns_none(self):
        assert codex_review.normalize_severity(None) is None
        assert codex_review.normalize_severity(42) is None
        assert codex_review.normalize_severity(["blocker"]) is None


# ---------------------------------------------------------------------------
# escape_github_command_field
# ---------------------------------------------------------------------------

class TestEscapeGithubCommandField:
    def test_escape_percent(self):
        assert codex_review.escape_github_command_field("100%") == "100%25"

    def test_escape_newlines(self):
        assert codex_review.escape_github_command_field("a\rb") == "a%0Db"
        assert codex_review.escape_github_command_field("a\nb") == "a%0Ab"
        assert codex_review.escape_github_command_field("a\r\nb") == "a%0D%0Ab"

    def test_escape_colon_comma(self):
        assert codex_review.escape_github_command_field("key:val") == "key%3Aval"
        assert codex_review.escape_github_command_field("a,b") == "a%2Cb"

    def test_none_returns_empty(self):
        assert codex_review.escape_github_command_field(None) == ""

    def test_non_string_coerced(self):
        assert codex_review.escape_github_command_field(42) == "42"


# ---------------------------------------------------------------------------
# is_valid_comment
# ---------------------------------------------------------------------------

class TestIsValidComment:
    def _make_comment(self, **overrides):
        base = {"path": "src/main.py", "body": "Fix this", "line": 10}
        base.update(overrides)
        return base

    def test_valid_comment_minimal(self):
        stats = {"stripped": 0}
        c = self._make_comment()
        assert codex_review.is_valid_comment(c, stats) is True

    def test_missing_path_rejected(self):
        stats = {"stripped": 0}
        c = self._make_comment(path="")
        assert codex_review.is_valid_comment(c, stats) is False

    def test_missing_body_rejected(self):
        stats = {"stripped": 0}
        c = self._make_comment(body="")
        assert codex_review.is_valid_comment(c, stats) is False

    def test_invalid_line_rejected(self):
        stats = {"stripped": 0}
        c = self._make_comment(line="not-a-number")
        assert codex_review.is_valid_comment(c, stats) is False

    def test_negative_line_rejected(self):
        stats = {"stripped": 0}
        c = self._make_comment(line=-1)
        assert codex_review.is_valid_comment(c, stats) is False

    def test_zero_line_rejected(self):
        stats = {"stripped": 0}
        c = self._make_comment(line=0)
        assert codex_review.is_valid_comment(c, stats) is False

    def test_missing_severity_accepted(self):
        stats = {"stripped": 0}
        c = self._make_comment()
        # no severity key at all
        assert codex_review.is_valid_comment(c, stats) is True
        assert stats["stripped"] == 0

    def test_invalid_severity_stripped_and_counter_increments(self):
        stats = {"stripped": 0}
        c = self._make_comment(severity="nit")
        assert codex_review.is_valid_comment(c, stats) is True
        assert "severity" not in c
        assert stats["stripped"] == 1

    def test_valid_severity_normalized(self):
        stats = {"stripped": 0}
        c = self._make_comment(severity="BLOCKER")
        assert codex_review.is_valid_comment(c, stats) is True
        assert c["severity"] == "blocker"
        assert stats["stripped"] == 0

    def test_side_defaults_to_right(self):
        stats = {"stripped": 0}
        c = self._make_comment()
        assert codex_review.is_valid_comment(c, stats) is True
        assert c["side"] == "RIGHT"

    def test_side_left_preserved(self):
        stats = {"stripped": 0}
        c = self._make_comment(side="LEFT")
        assert codex_review.is_valid_comment(c, stats) is True
        assert c["side"] == "LEFT"

    def test_not_a_dict_rejected(self):
        stats = {"stripped": 0}
        assert codex_review.is_valid_comment("string", stats) is False

    def test_line_coerced_from_string(self):
        stats = {"stripped": 0}
        c = self._make_comment(line="42")
        assert codex_review.is_valid_comment(c, stats) is True
        assert c["line"] == 42


# ---------------------------------------------------------------------------
# parse_review_output
# ---------------------------------------------------------------------------

class TestParseReviewOutput:
    def test_parse_direct_json_array(self):
        data = [{"path": "a.py", "body": "fix", "line": 1}]
        result = codex_review.parse_review_output(json.dumps(data))
        assert result == data

    def test_parse_markdown_fenced(self):
        raw = "Here is the review:\n```json\n" + json.dumps([{"x": 1}]) + "\n```\n"
        result = codex_review.parse_review_output(raw)
        assert result == [{"x": 1}]

    def test_parse_individual_fenced_blocks(self):
        """Strategy 3: extract from individual fenced code blocks amid prose."""
        raw = (
            "Some explanation text.\n"
            "```json\n"
            '[{"path": "b.py", "body": "check", "line": 5}]\n'
            "```\n"
            "More prose here.\n"
        )
        result = codex_review.parse_review_output(raw)
        assert result == [{"path": "b.py", "body": "check", "line": 5}]

    def test_parse_regex_fallback_on_stripped_text(self):
        """Strategy 4: regex for JSON array after fences are stripped."""
        raw = (
            "Some text ```ignored\ngarbage``` and then "
            '[{"path": "c.py", "body": "msg", "line": 3}] trailing'
        )
        result = codex_review.parse_review_output(raw)
        assert result == [{"path": "c.py", "body": "msg", "line": 3}]

    def test_parse_empty_string_returns_none(self):
        assert codex_review.parse_review_output("") is None

    def test_parse_unparseable_returns_none(self):
        assert codex_review.parse_review_output("just some random text") is None

    def test_parse_object_not_array_returns_none(self):
        """A JSON object (not array) should not be returned."""
        assert codex_review.parse_review_output('{"key": "value"}') is None


# ---------------------------------------------------------------------------
# extract_keywords
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    def test_filters_short_words(self):
        result = codex_review.extract_keywords("do it now and fix the bug")
        # "do", "it", "now", "and", "fix", "the", "bug" are all < 4 chars
        assert result == set()

    def test_removes_filler_words(self):
        result = codex_review.extract_keywords(
            "this should have been review because automated comment"
        )
        # "this", "should", "have", "been", "review", "because", "automated", "comment"
        # are all filler words (short or in the exclusion set)
        assert result == set()

    def test_keeps_meaningful_words(self):
        result = codex_review.extract_keywords("buffer overflow vulnerability detected here")
        assert "buffer" in result
        assert "overflow" in result
        assert "vulnerability" in result
        assert "detected" in result
        # "here" is 4 chars but doesn't start with lowercase letter pattern requirement
        # Actually "here" matches [a-z][a-z0-9_.-]{3,} -- 4 chars total
        # h + ere = 1+3 = {3,} means 3 or more after first, so "here" = h + "ere" (3 chars) matches {3,}
        assert "here" in result


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------

class TestIsDuplicate:
    def test_duplicate_resolved(self):
        resolved = {("src/main.py", 10)}
        result = codex_review.is_duplicate(
            {"path": "src/main.py", "line": 10, "body": "anything"},
            resolved, set(), []
        )
        assert result == "resolved"

    def test_duplicate_already_commented(self):
        bot_locs = {("src/main.py", 10)}
        result = codex_review.is_duplicate(
            {"path": "src/main.py", "line": 10, "body": "anything"},
            set(), bot_locs, []
        )
        assert result == "already-commented"

    def test_duplicate_similar_concern(self):
        concerns = [{
            "path": "src/main.py",
            "line": 10,
            "keywords": {"buffer", "overflow", "vulnerability", "detected"},
        }]
        result = codex_review.is_duplicate(
            {"path": "src/main.py", "line": 20, "body": "buffer overflow vulnerability detected here"},
            set(), set(), concerns
        )
        assert result == "similar-concern"

    def test_not_duplicate(self):
        result = codex_review.is_duplicate(
            {"path": "src/other.py", "line": 5, "body": "completely different concern"},
            set(), set(), []
        )
        assert result is None


# ---------------------------------------------------------------------------
# build_dedup_state
# ---------------------------------------------------------------------------

class TestBuildDedupState:
    def test_empty_input(self):
        resolved, bot_locs, concerns = codex_review.build_dedup_state([])
        assert resolved == set()
        assert bot_locs == set()
        assert concerns == []

    def test_with_bot_comments_and_human_replies(self):
        existing = [
            # Bot comment
            {"id": 100, "user": "github-actions[bot]", "path": "a.py", "line": 5,
             "body": "potential buffer overflow here", "in_reply_to_id": None},
            # Human reply to bot
            {"id": 101, "user": "developer", "path": "a.py", "line": 5,
             "body": "fixed", "in_reply_to_id": 100},
            # Another bot comment with no reply
            {"id": 200, "user": "github-actions[bot]", "path": "b.py", "line": 10,
             "body": "missing error handling check", "in_reply_to_id": None},
        ]
        resolved, bot_locs, concerns = codex_review.build_dedup_state(existing)

        # Human replied to bot comment at (a.py, 5) so it's resolved
        assert ("a.py", 5) in resolved
        # b.py, 10 is not resolved (no human reply)
        assert ("b.py", 10) not in resolved

        # Both bot locations present
        assert ("a.py", 5) in bot_locs
        assert ("b.py", 10) in bot_locs

        # Two bot concerns
        assert len(concerns) == 2
        assert concerns[0]["path"] == "a.py"
        assert concerns[1]["path"] == "b.py"
        assert "buffer" in concerns[0]["keywords"]


# ---------------------------------------------------------------------------
# Deep CI filtering, diff parsing, and chunking
# ---------------------------------------------------------------------------

class TestDeepCiCandidateFiltering:
    def test_deep_ci_candidate_accepts_supported_code_extensions(self):
        assert codex_review.is_deep_ci_candidate("scripts/review.py")
        assert codex_review.is_deep_ci_candidate("bin/install.sh")
        assert codex_review.is_deep_ci_candidate("src/review.js")
        assert codex_review.is_deep_ci_candidate("src/review.ts")

    def test_deep_ci_candidate_rejects_markdown_docs_and_prose(self):
        assert not codex_review.is_deep_ci_candidate("README.md")
        assert not codex_review.is_deep_ci_candidate("docs/example.py")
        assert not codex_review.is_deep_ci_candidate("ideas/sketch.ts")
        assert not codex_review.is_deep_ci_candidate("notes/review.txt")

    def test_deep_ci_candidate_rejects_generated_vendor_minified_and_lock_paths(self):
        assert not codex_review.is_deep_ci_candidate("generated/client.ts")
        assert not codex_review.is_deep_ci_candidate("vendor/tool.py")
        assert not codex_review.is_deep_ci_candidate("build/bundle.js")
        assert not codex_review.is_deep_ci_candidate("dist/app.js")
        assert not codex_review.is_deep_ci_candidate("src/app.min.js")
        assert not codex_review.is_deep_ci_candidate("src/runtime.lock.ts")

    def test_deep_ci_candidate_rejects_deleted_and_noisy_change_files(self):
        assert not codex_review.is_deep_ci_candidate(
            "src/deleted.py",
            {"path": "src/deleted.py", "status": "removed"},
        )
        assert codex_review.is_deep_ci_candidate(
            "src/large.py",
            {"path": "src/large.py", "size": codex_review.DEEP_CI_MAX_FILE_CHARS + 1},
        )
        assert not codex_review.is_deep_ci_candidate(
            "src/noisy.ts",
            {
                "path": "src/noisy.ts",
                "additions": 1500,
                "deletions": 600,
            },
        )


class TestSelectDeepCiFiles:
    def test_select_deep_ci_files_is_deterministic_and_bounded(self):
        changed = [
            {"path": "zeta.ts"},
            {"path": "docs/not_selected.py"},
            {"path": "alpha.py"},
            {"path": "beta.js"},
            {"path": "gamma.sh"},
        ]

        assert codex_review.select_deep_ci_files(changed) == [
            "alpha.py",
            "beta.js",
            "gamma.sh",
        ]
        assert codex_review.select_deep_ci_files(list(reversed(changed))) == [
            "alpha.py",
            "beta.js",
            "gamma.sh",
        ]

    def test_select_deep_ci_files_preserves_supported_paths_after_filtering(self):
        changed = [
            "README.md",
            "src/app.py",
            {"path": "ideas/example.ts"},
            {"path": "src/app.py"},
            {"path": "src/client.ts", "changeType": "MODIFIED"},
            {"path": "src/old.js", "status": "deleted"},
        ]

        assert codex_review.select_deep_ci_files(changed) == [
            "src/app.py",
            "src/client.ts",
        ]


# ---------------------------------------------------------------------------
# Deep CI diff parsing and window helpers
# ---------------------------------------------------------------------------

class TestDeepCiDiffParsing:
    def test_parse_changed_line_ranges_records_right_side_additions(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -10,2 +10,3 @@\n"
            " context\n"
            "+added one\n"
            "+added two\n"
            " tail\n"
        )
        assert codex_review.parse_changed_line_ranges(diff) == {"src/app.py": [(11, 12)]}

    def test_parse_changed_line_ranges_ignores_deletions_and_metadata(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -2,2 +2,2 @@\n"
            "-old\n"
            "+new\n"
            " context\n"
        )
        assert codex_review.parse_changed_line_ranges(diff) == {"src/app.py": [(2, 2)]}

    def test_parse_changed_line_ranges_handles_multiple_hunks_and_files(self):
        diff = (
            "diff --git a/src/a.py b/src/a.py\n"
            "+++ b/src/a.py\n"
            "@@ -1,1 +1,1 @@\n"
            "+a\n"
            "@@ -10,1 +10,2 @@\n"
            "+b\n"
            "+c\n"
            "diff --git a/src/b.py b/src/b.py\n"
            "+++ b/src/b.py\n"
            "@@ -4,1 +4,1 @@\n"
            "+d\n"
        )
        assert codex_review.parse_changed_line_ranges(diff) == {
            "src/a.py": [(1, 1), (10, 11)],
            "src/b.py": [(4, 4)],
        }

    def test_parse_changed_line_ranges_handles_new_file_from_dev_null(self):
        diff = (
            "diff --git a/dev/null b/src/new.py\n"
            "--- /dev/null\n"
            "+++ b/src/new.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+hello\n"
            "+world\n"
        )
        assert codex_review.parse_changed_line_ranges(diff) == {"src/new.py": [(1, 2)]}

    def test_parse_changed_line_ranges_handles_paths_with_spaces_and_rename_new_paths(self):
        diff = (
            "diff --git a/src/old name.py b/src/new name.py\n"
            "similarity index 90%\n"
            "rename from src/old name.py\n"
            "rename to src/new name.py\n"
            "--- a/src/old name.py\n"
            "+++ b/src/new name.py\n"
            "@@ -1,1 +1,2 @@\n"
            "+x\n"
            "+y\n"
        )
        parsed = codex_review.parse_changed_line_ranges(diff)
        assert "src/new name.py" in parsed
        assert "src/old name.py" not in parsed
        assert parsed["src/new name.py"] == [(1, 2)]

    def test_parse_changed_line_ranges_handles_omitted_count_hunk_header(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -5 +5 @@\n"
            "+replacement\n"
        )
        assert codex_review.parse_changed_line_ranges(diff) == {"src/app.py": [(5, 5)]}

    def test_parse_changed_line_ranges_does_not_treat_in_hunk_plus_plus_space_as_header(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -5,0 +6,2 @@\n"
            "+++ suspicious\n"
            "+normal\n"
        )
        assert codex_review.parse_changed_line_ranges(diff) == {"src/app.py": [(6, 7)]}


class TestDeepCiChunkHelpers:
    def test_build_line_windows_expands_merges_and_bounds_to_file(self):
        windows = codex_review.build_line_windows(
            [(3, 3), (5, 5), (40, 40)],
            line_count=45,
            context_lines=2,
            max_chunks=4,
        )
        assert windows[0]["start_line"] == 1
        assert windows[0]["end_line"] == 7
        assert windows[1]["start_line"] == 38
        assert windows[1]["end_line"] == 42

    def test_build_line_windows_caps_deterministically_and_restores_file_order(self):
        windows = codex_review.build_line_windows(
            [(1, 1), (20, 22), (40, 44)],
            line_count=100,
            context_lines=0,
            max_chunks=2,
        )
        # keep ranges with highest changed-line counts, rendered in file order
        assert [(w["start_line"], w["end_line"]) for w in windows] == [(20, 22), (40, 44)]

    def test_build_line_windows_can_report_chunk_cap_omissions(self):
        plan = codex_review.build_line_windows(
            [(1, 1), (20, 22), (40, 44)],
            line_count=100,
            context_lines=0,
            max_chunks=2,
            include_omitted=True,
        )
        assert [(w["start_line"], w["end_line"]) for w in plan["included"]] == [
            (20, 22),
            (40, 44),
        ]
        assert [(w["start_line"], w["end_line"]) for w in plan["omitted"]] == [
            (1, 1)
        ]

    def test_extract_line_chunk_and_fit_chunk_to_char_cap_respect_line_boundaries(self):
        content = "line1\nline2\nline3\nline4\nline5\n"
        chunk = codex_review.extract_line_chunk(content, 2, 4)
        assert chunk == "line2\nline3\nline4"

        fitted = codex_review.fit_chunk_to_char_cap(
            {"start_line": 2, "end_line": 4, "content": chunk},
            [2, 3, 4],
            cap=11,
        )
        assert fitted["start_line"] >= 2
        assert fitted["end_line"] <= 4
        assert len(fitted["content"]) <= 11
        assert set(fitted["changed_lines_included"]).issubset({2, 3, 4})


class TestFetchDeepCiFiles:
    def test_fetch_deep_ci_files_keeps_small_file_as_full_snapshot(self, monkeypatch):
        def fake_run(cmd, check, capture_output, text):
            return subprocess.CompletedProcess(cmd, 0, stdout="print('ok')\n", stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)

        snapshots = codex_review.fetch_deep_ci_files("owner/repo", "abc123", ["src/app.py"])
        assert snapshots[0]["mode"] == "full"
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/app.py"])
        assert "Mode: full-file" in rendered
        assert "print('ok')" in rendered

    def test_deep_ci_hard_cap_file_renders_mode_skipped_with_reason(self, monkeypatch):
        # Backstop path: metadata is unknown (no size field), so the gh api
        # call runs and the post-fetch safeguard rejects the oversized body.
        def fake_run(cmd, check, capture_output, text):
            return subprocess.CompletedProcess(cmd, 0, stdout="x" * 50, stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/huge.py"],
            changed_line_ranges={"src/huge.py": [(1, 2)]},
            max_fetch_chars=20,
        )
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/huge.py"])
        assert snapshots[0]["mode"] == "skipped"
        assert "Mode: skipped" in rendered
        assert "hard fetch cap of 20 chars" in rendered

    def test_fetch_deep_ci_files_skips_pre_fetch_when_metadata_size_exceeds_hard_cap(
        self, monkeypatch
    ):
        # Pre-fetch path: metadata reports size > cap, so the gh api call
        # must NEVER run. The snapshot still renders as Mode: skipped with
        # the same hard-cap reason string to preserve F1 visibility.
        calls = []

        def fake_run(cmd, check, capture_output, text):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="should-not-be-read", stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/huge.py"],
            changed_line_ranges={"src/huge.py": [(1, 2)]},
            max_fetch_chars=20,
            file_metadata=[{"path": "src/huge.py", "size": 500}],
        )
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/huge.py"])

        assert calls == []  # hard-cap candidate never reached gh api
        assert len(snapshots) == 1
        assert snapshots[0]["mode"] == "skipped"
        assert "hard fetch cap of 20 chars" in snapshots[0]["reason"]
        assert "Mode: skipped" in rendered
        assert "hard fetch cap of 20 chars" in rendered

    def test_fetch_deep_ci_files_still_fetches_when_metadata_size_under_cap(
        self, monkeypatch
    ):
        # Metadata-under-cap path: fetch proceeds and small body is kept.
        calls = []

        def fake_run(cmd, check, capture_output, text):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="print('ok')\n", stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/small.py"],
            file_metadata=[{"path": "src/small.py", "size": 10}],
        )

        assert len(calls) == 1
        assert snapshots[0]["mode"] == "full"

    def test_fetch_deep_ci_files_chunks_oversized_file_with_changed_ranges(self, monkeypatch):
        content = "\n".join(f"line {i}" for i in range(1, 30)) + "\n"

        def fake_run(cmd, check, capture_output, text):
            return subprocess.CompletedProcess(cmd, 0, stdout=content, stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/large.py"],
            changed_line_ranges={"src/large.py": [(10, 10)]},
            max_chars_per_file=20,
            context_lines=1,
            max_chunks_per_file=2,
            max_chunk_chars=500,
        )
        assert snapshots[0]["mode"] == "chunked"
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/large.py"])
        assert "Mode: chunked-large-file" in rendered
        assert "Included chunks:" in rendered

    def test_fetch_deep_ci_files_skips_oversized_file_without_changed_ranges(self, monkeypatch):
        def fake_run(cmd, check, capture_output, text):
            return subprocess.CompletedProcess(cmd, 0, stdout=("line\n" * 30), stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/large.py"],
            changed_line_ranges={},
            max_chars_per_file=20,
        )
        assert snapshots[0]["mode"] == "skipped"
        assert "no changed-line ranges" in snapshots[0]["reason"]

    def test_chunk_metadata_reports_included_and_omitted_changed_lines_under_cap_pressure(
        self, monkeypatch
    ):
        content = "\n".join(f"{i}-" + ("x" * 20) for i in range(1, 40)) + "\n"

        def fake_run(cmd, check, capture_output, text):
            return subprocess.CompletedProcess(cmd, 0, stdout=content, stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/large.py"],
            changed_line_ranges={"src/large.py": [(10, 15)]},
            max_chars_per_file=20,
            context_lines=0,
            max_chunk_chars=45,
        )
        chunk = snapshots[0]["chunks"][0]
        assert chunk["changed_lines_omitted"]
        assert chunk["changed_lines_included"]
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/large.py"])
        assert "changed_lines_included:" in rendered
        assert "changed_lines_omitted:" in rendered

    def test_fetch_deep_ci_files_respects_total_cap_across_full_files_and_chunks(self, monkeypatch):
        contents = {
            "src/a.py": "aaaaaa",
            "src/b.py": "\n".join(["line"] * 40) + "\n",
        }

        def fake_run(cmd, check, capture_output, text):
            path_part = cmd[-1].split("/contents/", 1)[1].split("?ref=", 1)[0]
            return subprocess.CompletedProcess(cmd, 0, stdout=contents[path_part], stderr="")

        monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
        snapshots = codex_review.fetch_deep_ci_files(
            "owner/repo",
            "abc123",
            ["src/a.py", "src/b.py"],
            changed_line_ranges={"src/b.py": [(10, 10)]},
            max_chars_per_file=5,
            max_total_chars=3,
            context_lines=0,
            max_chunk_chars=50,
        )
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/a.py", "src/b.py"])
        assert snapshots[0]["mode"] == "skipped"
        assert snapshots[1]["mode"] == "skipped"
        assert "total-cap-exhausted" in rendered

    def test_render_deep_ci_context_surfaces_partial_total_cap_omitted_windows(self):
        # Manually construct a chunked snapshot with the total-cap omission
        # metadata populated. The renderer must surface those dropped windows
        # in the output so reviewers see them as explicitly omitted rather
        # than silently absent.
        snapshots = [
            {
                "path": "src/big.py",
                "mode": "chunked",
                "content": "",
                "chunks": [
                    {
                        "start_line": 10,
                        "end_line": 12,
                        "changed_lines": [11],
                        "changed_lines_included": [11],
                        "changed_lines_omitted": [],
                        "content": "row1\nrow2\nrow3",
                    }
                ],
                "char_count": 9999,
                "line_count": 500,
                "changed_line_ranges": [(11, 11), (200, 205), (450, 452)],
                "total_cap_omitted_windows": [
                    {"start_line": 180, "end_line": 220},
                    {"start_line": 430, "end_line": 470},
                ],
                "omitted": False,
                "reason": "full file exceeded cap",
            }
        ]
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/big.py"])
        assert "Total-cap omitted: 2 changed-line window(s)" in rendered
        assert "180-220" in rendered
        assert "430-470" in rendered

    def test_render_deep_ci_context_surfaces_chunk_cap_omitted_windows(self):
        snapshots = [
            {
                "path": "src/big.py",
                "mode": "chunked",
                "content": "",
                "chunks": [
                    {
                        "start_line": 20,
                        "end_line": 25,
                        "changed_lines": [22],
                        "changed_lines_included": [22],
                        "changed_lines_omitted": [],
                        "content": "row1\nrow2",
                    }
                ],
                "char_count": 9999,
                "line_count": 500,
                "changed_line_ranges": [(10, 10), (22, 22), (300, 300)],
                "chunk_cap_omitted_windows": [
                    {"start_line": 300, "end_line": 305},
                ],
                "omitted": False,
                "reason": "full file exceeded cap",
            }
        ]
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/big.py"])
        assert "Chunk-cap omitted: 1 changed-line window(s)" in rendered
        assert "300-305" in rendered

    def test_render_deep_ci_context_uses_longer_fence_for_chunk_backticks(self):
        snapshots = [
            {
                "path": "src/app.py",
                "mode": "chunked",
                "content": "",
                "chunks": [
                    {
                        "start_line": 10,
                        "end_line": 12,
                        "changed_lines": [11],
                        "changed_lines_included": [11],
                        "changed_lines_omitted": [],
                        "content": "return ```payload```",
                    }
                ],
                "char_count": 100,
                "line_count": 20,
                "changed_line_ranges": [(11, 11)],
                "omitted": False,
                "reason": "full file exceeded 20 chars; only changed-line windows are included",
            }
        ]
        rendered = codex_review.render_deep_ci_context(snapshots, ["src/app.py"])
        assert "Mode: chunked-large-file" in rendered
        assert "````\nreturn ```payload```\n````" in rendered


# ---------------------------------------------------------------------------
# Workflow context contract
# ---------------------------------------------------------------------------

class TestWorkflowContextContract:
    def test_workflow_keeps_trusted_base_checkout_for_secret_review(self):
        workflow = Path(".github/workflows/codex-ci-review.yml").read_text(encoding="utf-8")

        assert "ref: ${{ github.event.pull_request.base.sha }}" in workflow
        assert "ref: ${{ github.event.pull_request.head.sha }}" not in workflow

    def test_workflow_writes_raw_changed_file_paths_for_gather_context(self):
        workflow = Path(".github/workflows/codex-ci-review.yml").read_text(encoding="utf-8")

        raw_paths_command = (
            "jq -r '.files[].path' /tmp/changed_files_payload.json > /tmp/changed_files.txt"
        )
        quoted_paths_command = (
            "jq '.files[].path' /tmp/changed_files_payload.json > /tmp/changed_files.txt"
        )

        assert raw_paths_command in workflow
        assert quoted_paths_command not in workflow

    def test_workflow_has_legacy_build_prompt_fallback_for_base_checkout(self):
        workflow = Path(".github/workflows/codex-ci-review.yml").read_text(encoding="utf-8")

        assert (
            "if python3 .github/scripts/codex_review.py build-prompt "
            "2>/tmp/build_prompt_err.log; then"
        ) in workflow
        assert "grep -Eq \"Unknown subcommand: build-prompt|invalid choice: 'build-prompt'\"" in workflow
        assert "exit 1" in workflow
        assert "legacy prompt assembly" in workflow
        assert "touch /tmp/deep_ci_files.md" in workflow
        assert "/{PLACEHOLDER_DEEP_CI_FILES}/r /tmp/deep_ci_files.md" in workflow

    def test_gather_context_reads_workflow_raw_changed_file_paths(self, monkeypatch):
        tmp_paths = [
            Path("/tmp/pr_head_sha.txt"),
            Path("/tmp/changed_files.txt"),
            Path("/tmp/pr_head_files.md"),
            Path("/tmp/deep_ci_files.md"),
            Path("/tmp/pr.diff"),
        ]
        originals = {
            path: path.read_bytes() if path.exists() else None
            for path in tmp_paths
        }

        captured = {}

        def fake_fetch_head_files(repo, head_sha, changed_files):
            captured["repo"] = repo
            captured["head_sha"] = head_sha
            captured["changed_files"] = changed_files
            return [f"## {path}\n```\ncontent\n```" for path in changed_files]

        monkeypatch.setenv("REPO", "owner/repo")
        monkeypatch.setattr(codex_review, "fetch_head_files", fake_fetch_head_files)
        monkeypatch.setattr(
            codex_review,
            "load_changed_file_metadata",
            lambda: [{"path": "src/app.py"}, {"path": "lib/space name.py"}],
        )

        def fake_fetch_deep_ci_files(repo, head_sha, selected_files, **kwargs):
            captured["deep_ci_repo"] = repo
            captured["deep_ci_head_sha"] = head_sha
            captured["selected_files"] = selected_files
            captured["changed_line_ranges"] = kwargs.get("changed_line_ranges")
            return []

        monkeypatch.setattr(codex_review, "fetch_deep_ci_files", fake_fetch_deep_ci_files)

        try:
            Path("/tmp/pr_head_sha.txt").write_text("abc123\n", encoding="utf-8")
            Path("/tmp/changed_files.txt").write_text(
                "src/app.py\nlib/space name.py\n",
                encoding="utf-8",
            )
            Path("/tmp/pr.diff").write_text(
                "diff --git a/src/app.py b/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1 +1 @@\n"
                "+added\n",
                encoding="utf-8",
            )

            codex_review.gather_context()

            assert captured["repo"] == "owner/repo"
            assert captured["head_sha"] == "abc123"
            assert captured["changed_files"] == ["src/app.py", "lib/space name.py"]
            assert captured["deep_ci_repo"] == "owner/repo"
            assert captured["deep_ci_head_sha"] == "abc123"
            assert captured["selected_files"] == ["lib/space name.py", "src/app.py"]
            assert captured["changed_line_ranges"] == {"src/app.py": [(1, 1)]}
        finally:
            for path, content in originals.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

class TestBuildReviewPrompt:
    def test_build_review_prompt_includes_deep_ci_section(self):
        template = (
            "PR {PLACEHOLDER_PR_DESCRIPTION}\n"
            "Existing {PLACEHOLDER_EXISTING_COMMENTS}\n"
            "Head {PLACEHOLDER_PR_HEAD_FILES}\n"
            "Deep {PLACEHOLDER_DEEP_CI_FILES}\n"
            "Diff {PLACEHOLDER_DIFF}\n"
        )

        prompt = codex_review.build_review_prompt(
            template,
            {
                "PLACEHOLDER_PR_DESCRIPTION": "description",
                "PLACEHOLDER_EXISTING_COMMENTS": "[]",
                "PLACEHOLDER_PR_HEAD_FILES": "normal snapshot",
                "PLACEHOLDER_DEEP_CI_FILES": "deep snapshot",
                "PLACEHOLDER_DIFF": "diff text",
            },
        )

        assert "deep snapshot" in prompt
        assert "normal snapshot" in prompt
        assert "diff text" in prompt

    def test_build_review_prompt_replaces_all_placeholders(self):
        template = Path(".github/codex-review-prompt.md").read_text(encoding="utf-8")
        prompt = codex_review.build_review_prompt(
            template,
            {
                "PLACEHOLDER_PR_DESCRIPTION": "description",
                "PLACEHOLDER_EXISTING_COMMENTS": "[]",
                "PLACEHOLDER_PR_HEAD_FILES": "normal snapshot",
                "PLACEHOLDER_DEEP_CI_FILES": "deep snapshot",
                "PLACEHOLDER_DIFF": "diff text",
            },
        )

        assert "PLACEHOLDER_" not in prompt
        assert "## Deep CI Whole-File / Chunked Logic Pass" in prompt
        assert "deep snapshot" in prompt

    def test_build_review_prompt_does_not_reprocess_inserted_placeholders(self):
        template = (
            "Head {PLACEHOLDER_PR_HEAD_FILES}\n"
            "Diff {PLACEHOLDER_DIFF}\n"
        )

        prompt = codex_review.build_review_prompt(
            template,
            {
                "PLACEHOLDER_PR_HEAD_FILES": "snapshot has literal {PLACEHOLDER_DIFF}",
                "PLACEHOLDER_DIFF": "diff body",
            },
        )

        assert "snapshot has literal {PLACEHOLDER_DIFF}" in prompt
        assert prompt.count("diff body") == 1


class TestDeepCiDedupeReuse:
    def test_deep_ci_comment_uses_existing_duplicate_filter(self):
        existing = [
            {
                "id": 1,
                "user": "github-actions[bot]",
                "path": "src/app.py",
                "line": 42,
                "body": "**Must fix** - Deep CI: initializer fallback leaves cached state stale.",
                "in_reply_to_id": None,
            }
        ]
        resolved, bot_locs, concerns = codex_review.build_dedup_state(existing)

        reason = codex_review.is_duplicate(
            {
                "path": "src/app.py",
                "line": 42,
                "body": "**Must fix** - Deep CI: initializer fallback leaves cached state stale.",
            },
            resolved,
            bot_locs,
            concerns,
        )

        assert reason == "already-commented"
