"""Unit tests for .github/scripts/codex_review.py -- extracted CI review logic."""

import json
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
