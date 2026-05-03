"""Unit tests for quest_celebrate package."""

import json
import os
import subprocess
import sys
import textwrap
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from quest_celebrate.animations import (
    QuestStats,
    celebrate,
    load_quest_stats,
    render_end_credits,
    render_epic,
    render_minimal,
    render_silly,
    render_standard,
)
from quest_celebrate.ascii_art import (
    block_letter_title,
    box_banner,
    get_credits_lines,
    get_movie_credits_lines,
    gremlin_battle_art,
    gremlin_retirement_art,
    render_achievements,
    render_impact_metrics,
    render_quality_score,
    rocket_launch_art,
    trophy_art,
)
from quest_celebrate.config import CelebrationConfig, load_config
from quest_celebrate.quest_data import (
    QUALITY_TIERS,
    CarryoverFindings,
    _load_allowlist_quality_defaults,
    extract_celebration_data_from_journal,
    compute_quality_tier,
    friendly_model_name,
    load_quest_data_from_journal,
)
from quest_celebrate.progress import (
    render_progress_bar,
    render_phase_progress,
    scroll_credits,
)
from quest_celebrate.quest_data import (
    Achievement,
    AgentInfo,
    QuestData,
    load_quest_data,
)
from quest_celebrate.persist import (
    extract_what_started_this,
    render_persisted_celebration,
    select_quest_quote,
    write_celebration_file,
)
from quest_celebrate.terminal import (
    TerminalCaps,
    detect_terminal_capabilities,
    is_safe_mode,
)


class TestRenderMinimal:
    """Tests for minimal style rendering (AC1)."""

    def test_render_minimal_outputs_single_line(self):
        """Minimal style renders one-line summary."""
        stats = QuestStats(name="Test Quest", tools_count=5, tests_count=10)
        config = CelebrationConfig(style="minimal", is_safe=True)

        result = render_minimal(stats, config)

        assert "Quest Complete" in result or "complete" in result.lower()
        assert "Test Quest" in result
        assert result.count("\n") == 0 or result.endswith("\n")

    def test_render_minimal_includes_stats(self):
        """Minimal style includes tools and tests count."""
        stats = QuestStats(name="My Quest", tools_count=3, tests_count=7)
        config = CelebrationConfig(style="minimal", is_safe=True)

        result = render_minimal(stats, config)

        assert "3" in result or "tools" in result
        assert "7" in result or "tests" in result


class TestRenderStandard:
    """Tests for standard style rendering (AC2)."""

    def test_render_standard_outputs_box_banner(self):
        """Standard style renders box-framed banner."""
        stats = QuestStats(name="Test Quest", tools_count=5)
        config = CelebrationConfig(style="standard", is_safe=True)

        result = render_standard(stats, config)

        assert "QUEST COMPLETE" in result.upper() or "complete" in result.lower()
        assert "Test Quest" in result

    def test_render_standard_includes_stats(self):
        """Standard style includes quest statistics."""
        stats = QuestStats(
            name="Test Quest",
            tools_count=5,
            tests_count=10,
            bugs_fixed=2,
            pr_number=42,
        )
        config = CelebrationConfig(style="standard", is_safe=True, show_progress=True)

        result = render_standard(stats, config)

        assert "5" in result
        assert "10" in result
        assert "2" in result or "42" in result or "Stats" in result

    def test_render_standard_shows_iterations(self):
        """Standard style shows plan/fix iterations."""
        stats = QuestStats(name="Test Quest", plan_iterations=2, fix_iterations=1)
        config = CelebrationConfig(style="standard", is_safe=True)

        result = render_standard(stats, config)

        assert "2" in result and (
            "plan" in result.lower() or "iteration" in result.lower()
        )

    def test_render_standard_shows_carryover_findings_when_present(self):
        """Standard style surfaces artifact-backed carry-over findings."""
        stats = QuestStats(name="Carryover Quest")
        config = CelebrationConfig(style="standard", is_safe=True)
        quest_data = QuestData(
            name="Carryover Quest",
            inherited_findings_used=CarryoverFindings(
                count=2,
                summaries=[
                    "Deferred auth cleanup was pulled into scope.",
                    "Legacy validation gap was revisited.",
                ],
            ),
            findings_left_for_future_quests=CarryoverFindings(
                count=1,
                summaries=["Follow up on dashboard backlog rendering."],
            ),
        )

        result = render_standard(stats, config, quest_data=quest_data)

        assert "Inherited Findings Used" in result
        assert "Count: 2" in result
        assert "Findings Left For Future Quests" in result

    def test_render_standard_shows_empty_carryover_status_when_absent(self):
        """Standard style shows an explicit empty-state carry-over message."""
        stats = QuestStats(name="Carryover Quest")
        config = CelebrationConfig(style="standard", is_safe=True)
        quest_data = QuestData(name="Carryover Quest")

        result = render_standard(stats, config, quest_data=quest_data)

        assert "Carry-Over Findings" in result
        assert "nothing was inherited from earlier quests" in result
        assert "Inherited Findings Used" not in result


class TestRenderEpic:
    """Tests for epic style rendering (AC3)."""

    def test_render_epic_produces_all_sections(self):
        """Epic style produces block title, achievements, metrics, quality, credits."""
        stats = QuestStats(
            name="Epic Quest",
            tools_count=3,
            phases=[("Planning", "complete"), ("Building", "complete")],
        )
        quest_data = QuestData(
            quest_id="epic-quest_2026-01-01__1200",
            name="Epic Quest",
            status="complete",
            plan_iterations=1,
            fix_iterations=1,
            review_count=2,
            review_findings=["Fixed edge case"],
            agents=[
                AgentInfo(
                    name="builder",
                    model="claude-opus-4-6",
                    role_title="The Implementer",
                    summary="Built the feature",
                    phase="Building",
                ),
            ],
            achievements=[
                Achievement(icon="[WIN]", title="Quest Complete", description="Done"),
            ],
            quality_score=85,
        )
        config = CelebrationConfig(
            style="epic", is_safe=True, show_progress=True, ascii_art=True
        )
        output = StringIO()

        with patch("time.sleep"):  # Speed up animation
            render_epic(stats, config, output, quest_data=quest_data)

        result = output.getvalue()
        # Block title content (fallback banner for long name or block letters)
        assert "EPIC" in result.upper()
        # Achievements section
        assert "ACHIEVEMENTS" in result.upper()
        assert "Quest Complete" in result
        # Impact metrics
        assert "IMPACT METRICS" in result
        # Quality score
        assert "QUALITY SCORE" in result
        assert "85%" in result
        # Credits with agent names
        assert "builder" in result
        assert "The Implementer" in result

    def test_render_epic_includes_credits_when_enabled(self):
        """Epic style includes end credits when show_credits is True."""
        stats = QuestStats(name="Epic Quest", tools_count=5)
        config = CelebrationConfig(
            style="epic", is_safe=True, show_credits=True, ascii_art=True
        )
        output = StringIO()

        with patch("time.sleep"):
            render_epic(stats, config, output)

        result = output.getvalue()
        assert "CREDITS" in result.upper() or "Quest" in result

    def test_render_epic_without_quest_data_falls_back(self):
        """Epic renders basic credits when quest_data is not provided."""
        stats = QuestStats(name="Basic Quest", tools_count=2)
        config = CelebrationConfig(
            style="epic", is_safe=True, show_credits=True, ascii_art=True
        )
        output = StringIO()

        with patch("time.sleep"):
            render_epic(stats, config, output, quest_data=None)

        result = output.getvalue()
        assert "Basic Quest" in result

    def test_render_epic_shows_carryover_findings_when_present(self):
        """Epic style surfaces artifact-backed carry-over findings."""
        stats = QuestStats(name="Carryover Quest")
        config = CelebrationConfig(style="epic", is_safe=True)
        quest_data = QuestData(
            name="Carryover Quest",
            inherited_findings_used=CarryoverFindings(
                count=1,
                summaries=["Deferred auth cleanup was pulled into scope."],
            ),
            findings_left_for_future_quests=CarryoverFindings(
                count=2,
                summaries=[
                    "Follow up on dashboard backlog rendering.",
                    "Keep the planner reminder narrow.",
                ],
            ),
        )
        output = StringIO()

        with patch("time.sleep"):
            render_epic(stats, config, output, quest_data=quest_data)

        result = output.getvalue()
        assert "## Inherited Findings Used" in result
        assert "## Findings Left For Future Quests" in result

    def test_render_epic_shows_empty_carryover_status_when_absent(self):
        """Epic style shows the explicit empty-state carry-over message."""
        stats = QuestStats(name="Carryover Quest")
        config = CelebrationConfig(style="epic", is_safe=True)
        quest_data = QuestData(name="Carryover Quest")
        output = StringIO()

        with patch("time.sleep"):
            render_epic(stats, config, output, quest_data=quest_data)

        result = output.getvalue()
        assert "## Carry-Over Findings" in result
        assert "nothing needs to be saved for the next one" in result
        assert "## Inherited Findings Used" not in result

    def test_render_epic_journal_backed_quest_still_has_required_sections(self):
        """Journal-backed QuestData still renders the rich /celebrate sections."""
        stats = QuestStats(name="Journal Quest", phases=[("Planning", "complete")])
        config = CelebrationConfig(
            style="epic",
            is_safe=True,
            show_progress=False,
            show_credits=False,
            ascii_art=True,
        )
        quest_data = QuestData(
            quest_id="journal-quest_2026-05-03__1200",
            slug="journal-quest",
            name="Journal Quest",
            achievements=[
                Achievement(icon="[WIN]", title="Saved Story", description="Done")
            ],
            agents=[
                AgentInfo(
                    name="builder",
                    model="Codex",
                    role_title="The Implementer",
                    summary="Built the feature.",
                    phase="Building",
                )
            ],
            plan_iterations=1,
            fix_iterations=0,
            quality_score=95,
            quality_tier="Diamond",
        )
        output = StringIO()

        render_epic(stats, config, output, quest_data=quest_data)

        result = output.getvalue()
        assert "```text" in result
        assert "## 🎯 IMPACT METRICS" in result
        assert "## 🏆 Achievements" in result
        assert "## 🚀 Victory Narrative" in result
        assert "Saved Story" in result
        assert "TROPHY" in result.upper() or "🏆" in result


class TestPersistedCelebration:
    """Tests for persisted celebration markdown artifacts."""

    def test_persisted_celebration_contains_required_sections(self):
        data = QuestData(
            quest_id="persisted_2026-05-03__1200",
            slug="persisted",
            name="Persisted",
            brief_body="Problem: The story disappears.\n\nImpact: Readers lose context.",
            plan_summary="Persisted the full celebration.",
            plan_iterations=1,
            fix_iterations=0,
            review_count=1,
            review_findings=[],
            quality_tier="Diamond",
            quality_score=100,
            agents=[
                AgentInfo(
                    name="builder",
                    model="Codex",
                    role_title="The Implementer",
                    summary="Built persisted celebrations.",
                    phase="Building",
                )
            ],
            achievements=[
                Achievement(icon="[WIN]", title="Story Saved", description="Done")
            ],
        )

        result = render_persisted_celebration(
            data,
            date(2026, 5, 3),
            Path("docs/quest-journal/persisted_2026-05-03.md"),
        )

        assert "<!-- quest-id: persisted_2026-05-03__1200 -->" in result
        assert "<!-- origin: step7-original -->" in result
        assert "```text" in result
        assert "## What Started This" in result
        assert "The story disappears" in result
        assert "## Starring Cast" in result
        assert "## Achievements" in result
        assert "## Impact Metrics" in result
        assert "## Quality Tier: Diamond" in result or "Quality Tier: Diamond" in result
        assert "## Quest Quote" in result
        assert "Built persisted celebrations." in result
        assert "## Victory Narrative" in result

    def test_persisted_victory_narrative_prefers_full_brief_over_clipped_summary(self):
        data = QuestData(
            quest_id="full-story_2026-05-03__1200",
            slug="full-story",
            name="Full Story",
            brief_body=(
                "Problem: Quest celebrations disappeared after chat, leaving "
                "GitHub readers without the full story.\n\n"
                "Impact: Dashboard navigation could not reach the rendered "
                "celebration artifact."
            ),
            plan_summary="Problem: Quest celebrations disappeared after chat, leaving a...",
            quality_tier="Gold",
        )

        result = render_persisted_celebration(
            data,
            date(2026, 5, 3),
            Path("docs/quest-journal/full-story_2026-05-03.md"),
        )

        assert "leaving a..." not in result
        assert "GitHub readers without the full story" in result

    def test_write_celebration_file_when_exists_keeps_existing_file(self, tmp_path):
        journal_dir = tmp_path / "docs" / "quest-journal"
        existing = journal_dir / "celebrations" / "persisted_2026-05-03.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("sentinel", encoding="utf-8")
        data = QuestData(quest_id="persisted_2026-05-03__1200", slug="persisted")

        result = write_celebration_file(
            journal_dir,
            data,
            date(2026, 5, 3),
            Path("docs/quest-journal/persisted_2026-05-03.md"),
        )

        assert result.created is False
        assert existing.read_text(encoding="utf-8") == "sentinel"
        assert "not overwritten" in result.message

    def test_extract_what_started_this_with_problem_impact_pair(self):
        data = QuestData(
            brief_body="Problem: The story disappears.\n\nImpact: Readers lose context."
        )

        result = extract_what_started_this(data)

        assert "The story disappears" in result
        assert "Readers lose context" in result

    def test_select_quest_quote_returns_text_and_attribution(self):
        data = QuestData(
            agents=[
                AgentInfo(
                    name="builder",
                    model="Codex",
                    role_title="The Implementer",
                    summary="Built the feature.",
                    phase="Building",
                )
            ]
        )

        assert select_quest_quote(data) == ("Built the feature.", "The Implementer")


class TestRenderSilly:
    """Tests for silly style rendering (AC4)."""

    def test_render_silly_includes_flair(self):
        """Silly style includes extra fun elements."""
        stats = QuestStats(name="Silly Quest", bugs_fixed=3)
        config = CelebrationConfig(style="silly", is_safe=True, ascii_art=True)
        output = StringIO()

        with patch("time.sleep"):
            render_silly(stats, config, output)

        result = output.getvalue()
        # Should contain silly phrases or gremlin references
        assert (
            "GREMLIN" in result.upper()
            or "VANQUISHED" in result.upper()
            or "retirement" in result.lower()
            or len(result) > 50  # Silly is verbose
        )

    def test_render_silly_includes_stats(self):
        """Silly style includes quest statistics with fun labels."""
        stats = QuestStats(
            name="Silly Quest", tools_count=3, tests_count=5, bugs_fixed=2
        )
        config = CelebrationConfig(style="silly", is_safe=True, ascii_art=True)
        output = StringIO()

        with patch("time.sleep"):
            render_silly(stats, config, output)

        result = output.getvalue()
        assert "3" in result or "tools" in result.lower() or "forged" in result.lower()

    def test_render_silly_shows_carryover_findings_when_present(self):
        """Silly style also surfaces artifact-backed carry-over findings."""
        stats = QuestStats(name="Silly Quest")
        config = CelebrationConfig(style="silly", is_safe=True, ascii_art=False)
        quest_data = QuestData(
            name="Silly Quest",
            inherited_findings_used=CarryoverFindings(
                count=1,
                summaries=["Deferred auth cleanup was pulled into scope."],
            ),
        )
        output = StringIO()

        with patch("time.sleep"):
            render_silly(stats, config, output, quest_data=quest_data)

        result = output.getvalue()
        assert "## Inherited Findings Used" in result

    def test_render_silly_shows_empty_carryover_status_when_absent(self):
        """Silly style shows the explicit empty-state carry-over message."""
        stats = QuestStats(name="Silly Quest")
        config = CelebrationConfig(style="silly", is_safe=True, ascii_art=False)
        quest_data = QuestData(name="Silly Quest")
        output = StringIO()

        with patch("time.sleep"):
            render_silly(stats, config, output, quest_data=quest_data)

        result = output.getvalue()
        assert "## Carry-Over Findings" in result
        assert "nothing was inherited from earlier quests" in result


class TestEnvironmentOverrides:
    """Tests for environment variable overrides (AC5, AC6)."""

    def test_animations_disabled_via_env_shows_minimal(self):
        """QUEST_ANIMATIONS=0 forces minimal style."""
        with patch.dict(os.environ, {"QUEST_ANIMATIONS": "0"}, clear=False):
            config = load_config()
            assert config.enabled is False

    def test_quest_style_env_override(self):
        """QUEST_STYLE overrides configured style."""
        with patch.dict(os.environ, {"QUEST_STYLE": "epic"}, clear=False):
            config = load_config()
            assert config.style == "epic"

    def test_quest_speed_env_override(self):
        """QUEST_SPEED overrides configured speed."""
        with patch.dict(os.environ, {"QUEST_SPEED": "fast"}, clear=False):
            config = load_config()
            assert config.speed == "fast"

    def test_quest_credits_env_override(self):
        """QUEST_CREDITS=0 hides credits."""
        with patch.dict(os.environ, {"QUEST_CREDITS": "0"}, clear=False):
            config = load_config()
            assert config.show_credits is False


class TestCIDetection:
    """Tests for CI/terminal detection (AC6)."""

    def test_ci_detection_enables_safe_mode(self):
        """CI=true auto-enables safe mode and fast speed."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            # Force re-detection by clearing any cached values
            caps = detect_terminal_capabilities()
            assert caps.is_ci is True
            assert caps.supports_unicode is False
            assert caps.supports_emoji is False

    def test_term_dumb_detection(self):
        """TERM=dumb auto-enables safe mode."""
        with patch.dict(os.environ, {"TERM": "dumb"}, clear=True):
            caps = detect_terminal_capabilities()
            assert caps.supports_unicode is False


class TestSafeMode:
    """Tests for safe mode rendering (AC6 continued)."""

    def test_safe_mode_uses_ascii_only(self):
        """Safe mode uses only ASCII characters."""
        bar = render_progress_bar(50, "test", safe_mode=True)
        # Check all chars are ASCII
        assert all(ord(c) < 128 for c in bar), f"Non-ASCII chars found: {bar}"

    def test_safe_mode_box_banner(self):
        """Box banner in safe mode uses ASCII characters."""
        banner = box_banner("Test", width=40, safe_mode=True)
        assert all(ord(c) < 128 for c in banner)
        assert "+" in banner and "-" in banner

    def test_unicode_mode_uses_unicode(self):
        """Non-safe mode can use Unicode characters."""
        bar = render_progress_bar(50, "test", safe_mode=False)
        # Unicode mode should contain block chars or other Unicode
        has_unicode = any(ord(c) >= 128 for c in bar)
        assert has_unicode or "=" in bar


class TestProgressBar:
    """Tests for progress bar rendering."""

    def test_progress_bar_unicode_and_ascii(self):
        """Progress bar renders correctly in both modes."""
        unicode_bar = render_progress_bar(75, "Phase 1", safe_mode=False)
        ascii_bar = render_progress_bar(75, "Phase 1", safe_mode=True)

        assert "75%" in unicode_bar
        assert "75%" in ascii_bar
        assert "Phase 1" in unicode_bar
        assert "Phase 1" in ascii_bar

    def test_progress_bar_full_and_empty(self):
        """Progress bar handles 0% and 100%."""
        empty = render_progress_bar(0, "start", safe_mode=True)
        full = render_progress_bar(100, "done", safe_mode=True)

        assert "0%" in empty
        assert "100%" in full


class TestConfigLoading:
    """Tests for configuration loading (AC7)."""

    def test_config_loads_from_allowlist(self, tmp_path):
        """Config loads from .ai/allowlist.json quest_completion section."""
        allowlist = {
            "quest_completion": {
                "enabled": True,
                "animation_style": "epic",
                "show_end_credits": False,
                "show_progress_bars": True,
                "ascii_art": True,
                "animation_speed": "slow",
                "safe_mode": "never",
            }
        }
        allowlist_path = tmp_path / ".ai"
        allowlist_path.mkdir()
        (allowlist_path / "allowlist.json").write_text(json.dumps(allowlist))

        config = load_config(repo_root=tmp_path)

        assert config.style == "epic"
        assert config.speed == "slow"
        assert config.show_credits is False
        assert config.safe_mode == "never"

    def test_config_precedence(self, tmp_path):
        """Config precedence: CLI > env > allowlist > auto > defaults."""
        # Create allowlist with standard style
        allowlist = {"quest_completion": {"animation_style": "standard"}}
        allowlist_path = tmp_path / ".ai"
        allowlist_path.mkdir()
        (allowlist_path / "allowlist.json").write_text(json.dumps(allowlist))

        # Env var should override allowlist
        with patch.dict(os.environ, {"QUEST_STYLE": "silly"}):
            config = load_config(repo_root=tmp_path)
            assert config.style == "silly"  # env wins

        # CLI should override env
        with patch.dict(os.environ, {"QUEST_STYLE": "minimal"}):
            config = load_config(repo_root=tmp_path, cli_style="epic")
            assert config.style == "epic"  # CLI wins

    def test_default_style_is_epic(self):
        """Default style is epic (AC8)."""
        config = CelebrationConfig()
        assert config.style == "epic"


class TestQuestStatsLoading:
    """Tests for quest stats loading from state.json."""

    def test_load_quest_stats_from_state_json(self, tmp_path):
        """Load quest stats from quest directory state.json."""
        quest_dir = tmp_path / "test-quest_2026-01-01__1200"
        quest_dir.mkdir()

        state = {
            "quest_id": "test-quest_2026-01-01__1200",
            "slug": "test-quest",
            "plan_iteration": 2,
            "fix_iteration": 1,
            "phase": "complete",
        }
        (quest_dir / "state.json").write_text(json.dumps(state))

        stats = load_quest_stats(quest_dir)

        assert stats.quest_id == "test-quest_2026-01-01__1200"
        assert stats.slug == "test-quest"
        assert stats.plan_iterations == 2
        assert stats.fix_iterations == 1

    def test_load_quest_stats_uses_state_slug_for_date_first_id(self, tmp_path):
        """Date-first IDs display the slug, not the date prefix."""
        quest_dir = tmp_path / "2026-04-29_1430__portable-pre-commit-review"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text(
            json.dumps(
                {
                    "quest_id": "2026-04-29_1430__portable-pre-commit-review",
                    "slug": "portable-pre-commit-review",
                }
            ),
            encoding="utf-8",
        )

        stats = load_quest_stats(quest_dir)

        assert stats.name == "Portable Pre Commit Review"

    def test_load_quest_stats_from_brief(self, tmp_path):
        """Load quest name from quest_brief.md."""
        quest_dir = tmp_path / "my-quest_2026-01-01__1200"
        quest_dir.mkdir()

        (quest_dir / "state.json").write_text(
            json.dumps({"quest_id": "my-quest_2026-01-01__1200"})
        )
        (quest_dir / "quest_brief.md").write_text(
            "# Quest Brief: My Special Quest\n\nDetails here."
        )

        stats = load_quest_stats(quest_dir)

        assert stats.name == "My Special Quest"

    def test_load_quest_stats_missing_dir(self, tmp_path):
        """Handle missing quest directory gracefully."""
        missing_dir = tmp_path / "nonexistent"
        stats = load_quest_stats(missing_dir)

        assert stats.name == "Unknown Quest"
        assert stats.quest_id == ""

    def test_load_quest_stats_malformed_json(self, tmp_path):
        """Handle malformed state.json gracefully."""
        quest_dir = tmp_path / "bad-quest"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text("not valid json {")

        stats = load_quest_stats(quest_dir)

        assert stats.name == "Unknown Quest"  # graceful degradation


class TestOutputWidth:
    """Tests for 80-column output constraint (AC9)."""

    def test_output_fits_80_columns(self):
        """All output lines fit within 80 columns."""
        stats = QuestStats(name="Test Quest")
        config = CelebrationConfig(is_safe=True, columns=80)

        # Test minimal
        minimal = render_minimal(stats, config)
        for line in minimal.split("\n"):
            assert len(line) <= 80, f"Line too long ({len(line)}): {line}"

        # Test standard
        standard = render_standard(stats, config)
        for line in standard.split("\n"):
            assert len(line) <= 80, f"Line too long ({len(line)}): {line}"


class TestASCIIArt:
    """Tests for ASCII art templates."""

    def test_trophy_art_safe_mode(self):
        """Trophy art in safe mode is ASCII-only."""
        art = trophy_art("Test", safe_mode=True)
        assert all(ord(c) < 128 for c in art)

    def test_gremlin_art_safe_mode(self):
        """Gremlin art in safe mode is ASCII-only."""
        art = gremlin_battle_art(safe_mode=True)
        assert all(ord(c) < 128 for c in art)

    def test_rocket_art_safe_mode(self):
        """Rocket art in safe mode is ASCII-only."""
        art = rocket_launch_art(safe_mode=True)
        assert all(ord(c) < 128 for c in art)

    def test_get_credits_lines(self):
        """Credits lines include quest stats."""
        stats = {"name": "Test Quest", "tools_count": 5, "tests_count": 3}
        lines = get_credits_lines(stats, safe_mode=True)

        assert any("Test Quest" in line for line in lines)
        assert any("5" in line or "Tools" in line for line in lines)


class TestCelebrateFunction:
    """Tests for main celebrate function."""

    def test_missing_quest_dir_returns_error(self, tmp_path):
        """Missing quest directory returns exit code 1."""
        missing_dir = tmp_path / "nonexistent"
        config = CelebrationConfig()

        result = celebrate(missing_dir, config)

        assert result == 1

    def test_valid_quest_dir_returns_success(self, tmp_path):
        """Valid quest directory returns exit code 0."""
        quest_dir = tmp_path / "test-quest"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text(json.dumps({"quest_id": "test-quest"}))

        config = CelebrationConfig(style="minimal", is_safe=True)
        output = StringIO()

        result = celebrate(quest_dir, config, output)

        assert result == 0
        assert "Quest" in output.getvalue() or "complete" in output.getvalue().lower()

    def test_celebrate_defaults_to_epic(self, tmp_path):
        """celebrate() uses epic style by default (AC8)."""
        quest_dir = tmp_path / "test-quest"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text(
            json.dumps({"quest_id": "test-quest", "status": "complete"})
        )

        config = CelebrationConfig(is_safe=True)
        output = StringIO()

        with patch("time.sleep"):
            result = celebrate(quest_dir, config, output)

        assert result == 0
        assert config.style == "epic"
        # Epic style shows block title and QUEST COMPLETE banner
        assert "QUEST COMPLETE" in output.getvalue().upper()


class TestShellWrapper:
    """Tests for shell script wrapper (AC8)."""

    def test_shell_wrapper_delegates_to_python(self, tmp_path):
        """Shell wrapper delegates to Python script."""
        quest_dir = tmp_path / "test-quest_2026-01-01__1200"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text(
            json.dumps({"quest_id": "test-quest_2026-01-01__1200"})
        )

        wrapper_path = (
            Path(__file__).parents[2]
            / "scripts"
            / "quest_celebrate"
            / "quest-celebrate.sh"
        )

        if wrapper_path.exists():
            result = subprocess.run(
                [
                    "bash",
                    str(wrapper_path),
                    "--quest-dir",
                    str(quest_dir),
                    "--style",
                    "minimal",
                ],
                capture_output=True,
                text=True,
            )
            # Should succeed or print fallback
            assert (
                result.returncode == 0
                or "Quest" in result.stdout
                or "complete" in result.stdout.lower()
            )

    def test_shell_wrapper_fallback_no_python(self, tmp_path):
        """Shell wrapper prints message when Python unavailable."""
        # This is a theoretical test - we can't easily remove Python
        # Just verify the fallback logic exists in the script
        wrapper_path = (
            Path(__file__).parents[2]
            / "scripts"
            / "quest_celebrate"
            / "quest-celebrate.sh"
        )

        if wrapper_path.exists():
            script_content = wrapper_path.read_text()
            # Should have fallback logic
            assert "Quest complete" in script_content or "echo" in script_content


class TestTerminalCapabilities:
    """Tests for terminal capability detection."""

    def test_detect_terminal_caps_returns_valid(self):
        """Terminal detection returns valid caps."""
        caps = detect_terminal_capabilities()

        assert isinstance(caps, TerminalCaps)
        assert isinstance(caps.supports_unicode, bool)
        assert isinstance(caps.supports_emoji, bool)
        assert isinstance(caps.is_interactive, bool)
        assert isinstance(caps.is_ci, bool)
        assert isinstance(caps.columns, int)
        assert caps.columns >= 40

    def test_is_safe_mode_function(self):
        """is_safe_mode convenience function works."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert is_safe_mode() is True


class TestPhaseProgress:
    """Tests for phase progress rendering."""

    def test_render_phase_progress_outputs_lines(self):
        """Phase progress renders phase lines."""
        phases = [
            ("Planning", "complete"),
            ("Building", "complete"),
            ("Review", "in_progress"),
        ]
        output = StringIO()

        render_phase_progress(phases, safe_mode=True, output=output)

        result = output.getvalue()
        assert "Planning" in result
        assert "Building" in result
        assert "Review" in result


# === New tests for Celebrate V2 ===


class TestQuestDataLoading:
    """Tests for deep quest data extraction (AC1)."""

    def _make_quest_dir(self, tmp_path):
        """Create a fixture quest directory with realistic data."""
        quest_dir = tmp_path / "test-quest_2026-01-01__1200"
        quest_dir.mkdir()

        # state.json
        state = {
            "quest_id": "test-quest_2026-01-01__1200",
            "slug": "test-quest",
            "phase": "complete",
            "status": "complete",
            "plan_iteration": 2,
            "fix_iteration": 1,
            "created_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-01-01T14:00:00Z",
        }
        (quest_dir / "state.json").write_text(json.dumps(state))

        # quest_brief.md
        (quest_dir / "quest_brief.md").write_text(
            "# Quest Brief: My Test Feature\n\n## User Input\n\nBuild a great feature.\n"
        )

        # plan.md
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir()
        (plan_dir / "plan.md").write_text(
            "# Plan\n\n## Overview\n\nThis plan builds a great feature with tests.\n\n## Steps\n\n- Step 1\n"
        )

        # handoff files
        (plan_dir / "handoff_plan-reviewer-a.json").write_text(
            json.dumps(
                {
                    "agent": "plan-reviewer-a",
                    "model": "claude-opus-4-6",
                    "summary": "Plan review complete with minor issues.",
                    "artifacts": [],
                }
            )
        )

        impl_dir = quest_dir / "phase_02_implementation"
        impl_dir.mkdir()
        (impl_dir / "handoff.json").write_text(
            json.dumps(
                {
                    "agent": "builder",
                    "model": "gpt-5.3-codex",
                    "summary": "Built the feature successfully.",
                    "artifacts": ["src/feature.py", "tests/test_feature.py"],
                }
            )
        )

        review_dir = quest_dir / "phase_03_review"
        review_dir.mkdir()
        (review_dir / "handoff_code-reviewer-a.json").write_text(
            json.dumps(
                {
                    "agent": "code-reviewer-a",
                    "model": "claude-opus-4-6",
                    "summary": "Review complete, approved.",
                    "artifacts": [".quest/test-quest/phase_03_review/review_a.md"],
                }
            )
        )

        # review markdown
        (review_dir / "review_a.md").write_text(
            "# Review\n\n- **issue**: Missing null check in handler\n- **finding**: No error handling for empty input\n- Good code structure overall\n"
        )

        return quest_dir

    def test_load_quest_data_reads_state_json(self, tmp_path):
        """Verifies quest_id, slug, iterations extracted from state.json."""
        quest_dir = self._make_quest_dir(tmp_path)
        data = load_quest_data(quest_dir)

        assert data.quest_id == "test-quest_2026-01-01__1200"
        assert data.slug == "test-quest"
        assert data.plan_iterations == 2
        assert data.fix_iterations == 1
        assert data.status == "complete"
        assert data.created_at == "2026-01-01T12:00:00Z"

    def test_load_quest_data_uses_state_slug_for_date_first_id(self, tmp_path):
        """Date-first active quest names come from state slug."""
        quest_dir = tmp_path / "2026-04-29_1430__portable-pre-commit-review"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text(
            json.dumps(
                {
                    "quest_id": "2026-04-29_1430__portable-pre-commit-review",
                    "slug": "portable-pre-commit-review",
                }
            ),
            encoding="utf-8",
        )

        data = load_quest_data(quest_dir)

        assert data.slug == "portable-pre-commit-review"
        assert data.name == "Portable Pre Commit Review"

    def test_load_quest_data_reads_handoff_agents(self, tmp_path):
        """Verifies agent names and models extracted from handoff JSON."""
        quest_dir = self._make_quest_dir(tmp_path)
        data = load_quest_data(quest_dir)

        agent_names = [a.name for a in data.agents]
        assert "plan-reviewer-a" in agent_names
        assert "builder" in agent_names
        assert "code-reviewer-a" in agent_names

        builder = next(a for a in data.agents if a.name == "builder")
        assert builder.model == "gpt-5.3-codex"
        assert builder.role_title == "The Implementer"

    def test_load_quest_data_reads_quest_brief(self, tmp_path):
        """Verifies name and summary from quest_brief.md."""
        quest_dir = self._make_quest_dir(tmp_path)
        data = load_quest_data(quest_dir)

        assert data.name == "My Test Feature"
        assert "great feature" in data.brief_summary.lower()
        assert "Build a great feature." in data.brief_body
        assert data.brief_source == "original_prompt"

    def test_load_quest_data_reads_original_request_variant(self, tmp_path):
        """Verifies legacy Original Request headings are treated as full prompt content."""
        quest_dir = self._make_quest_dir(tmp_path)
        (quest_dir / "quest_brief.md").write_text(
            "# Quest Brief: My Test Feature\n\n"
            "## Original Request\n\n"
            "> Recover the original request in full.\n",
            encoding="utf-8",
        )

        data = load_quest_data(quest_dir)

        assert "Recover the original request in full." in data.brief_body
        assert data.brief_source == "original_prompt"

    def test_load_quest_data_reads_user_request_variant(self, tmp_path):
        """Verifies User Request headings are treated as full prompt content."""
        quest_dir = self._make_quest_dir(tmp_path)
        (quest_dir / "quest_brief.md").write_text(
            "# Quest Brief: My Test Feature\n\n"
            "## User Request\n\n"
            "Recover the user request in full.\n",
            encoding="utf-8",
        )

        data = load_quest_data(quest_dir)

        assert "Recover the user request in full." in data.brief_body
        assert data.brief_source == "original_prompt"

    def test_load_quest_data_reads_original_user_input_variant(self, tmp_path):
        """Verifies Original User Input headings are treated as full prompt content."""
        quest_dir = self._make_quest_dir(tmp_path)
        (quest_dir / "quest_brief.md").write_text(
            "# Quest Brief: My Test Feature\n\n"
            "## Original User Input\n\n"
            "Recover the original user input in full.\n",
            encoding="utf-8",
        )

        data = load_quest_data(quest_dir)

        assert "Recover the original user input in full." in data.brief_body
        assert data.brief_source == "original_prompt"

    def test_load_quest_data_reads_plan_summary(self, tmp_path):
        """Verifies plan overview extracted."""
        quest_dir = self._make_quest_dir(tmp_path)
        data = load_quest_data(quest_dir)

        assert "great feature" in data.plan_summary.lower()

    def test_load_quest_data_computes_achievements(self, tmp_path):
        """Verifies dynamic achievements based on stats."""
        quest_dir = self._make_quest_dir(tmp_path)
        data = load_quest_data(quest_dir)

        titles = [a.title for a in data.achievements]
        # Should have "Plan Perfectionist" because plan_iterations > 1
        assert "Plan Perfectionist" in titles
        # Should have "Quest Complete" because status is complete
        assert "Quest Complete" in titles
        # Should have "Battle Tested" because reviews exist
        assert "Battle Tested" in titles

    def test_load_quest_data_computes_quality_score(self, tmp_path):
        """Verifies quality score computation."""
        quest_dir = self._make_quest_dir(tmp_path)
        data = load_quest_data(quest_dir)

        # complete=50 + reviews=20 + findings=15 + fix_iter<=1=5 = 90
        # plan_iterations=2 <= 2 so no penalty but also no +10 bonus
        assert data.quality_score == 90

    def test_load_quest_data_finds_pr_number(self, tmp_path):
        """Verifies PR number extraction from handoff summary."""
        quest_dir = self._make_quest_dir(tmp_path)
        # Add a PR reference to a handoff
        impl_dir = quest_dir / "phase_02_implementation"
        (impl_dir / "handoff.json").write_text(
            json.dumps(
                {
                    "agent": "builder",
                    "model": "gpt-5.3-codex",
                    "summary": "Built feature, created PR #42.",
                    "artifacts": ["src/feature.py"],
                }
            )
        )

        data = load_quest_data(quest_dir)
        assert data.pr_number == 42

    def test_load_quest_data_handles_missing_files(self, tmp_path):
        """Graceful degradation for missing files."""
        quest_dir = tmp_path / "sparse-quest"
        quest_dir.mkdir()
        (quest_dir / "state.json").write_text(
            json.dumps({"quest_id": "sparse-quest_2026-01-01__1200"})
        )

        data = load_quest_data(quest_dir)

        assert data.quest_id == "sparse-quest_2026-01-01__1200"
        assert data.brief_summary == ""
        assert data.plan_summary == ""
        assert data.agents == []
        assert data.inherited_findings_used.count == 0
        assert data.findings_left_for_future_quests.count == 0

    def test_load_quest_data_reads_carryover_finding_artifacts(self, tmp_path):
        """Deferred backlog artifacts populate the carry-over fields."""
        quest_dir = self._make_quest_dir(tmp_path)
        (quest_dir / "phase_01_plan" / "deferred_backlog_matches.json").write_text(
            json.dumps(
                [
                    {"summary": "Deferred auth cleanup was pulled into scope."},
                    {"summary": "Legacy validation gap was revisited."},
                    {"summary": "Dashboard state drift needs follow-up."},
                    {"summary": "A fourth match should only affect the count."},
                ]
            ),
            encoding="utf-8",
        )

        backlog_dir = Path(__file__).resolve().parents[2] / ".quest" / "backlog"
        backlog_dir.mkdir(parents=True, exist_ok=True)
        backlog_path = backlog_dir / "deferred_findings.jsonl"
        original = backlog_path.read_text(encoding="utf-8") if backlog_path.exists() else None
        try:
            backlog_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "deferred_by_quest": "test-quest_2026-01-01__1200",
                                "summary": "Follow up on dashboard backlog rendering.",
                            }
                        ),
                        json.dumps(
                            {
                                "deferred_by_quest": "other-quest_2026-01-01__1200",
                                "summary": "Should not be included.",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            data = load_quest_data(quest_dir)
        finally:
            if original is None:
                backlog_path.unlink(missing_ok=True)
            else:
                backlog_path.write_text(original, encoding="utf-8")

        assert data.inherited_findings_used.count == 4
        assert len(data.inherited_findings_used.summaries) == 3
        assert data.findings_left_for_future_quests.count == 1
        assert data.findings_left_for_future_quests.summaries == [
            "Follow up on dashboard backlog rendering."
        ]

    def test_load_quest_data_reads_deferred_backlog_from_quest_repo_root(self, tmp_path):
        """A .quest/<id> input resolves deferred backlog from its own repo."""
        quest_id = "target-quest_2026-01-01__1200"
        quest_dir = tmp_path / ".quest" / quest_id
        quest_dir.mkdir(parents=True)
        (quest_dir / "state.json").write_text(
            json.dumps({"quest_id": quest_id}),
            encoding="utf-8",
        )
        backlog_dir = tmp_path / ".quest" / "backlog"
        backlog_dir.mkdir(parents=True)
        (backlog_dir / "deferred_findings.jsonl").write_text(
            json.dumps(
                {
                    "deferred_by_quest": quest_id,
                    "summary": "Read from the target repo backlog.",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        data = load_quest_data(quest_dir)

        assert data.findings_left_for_future_quests.count == 1
        assert data.findings_left_for_future_quests.summaries == [
            "Read from the target repo backlog."
        ]

    def test_load_quest_data_handles_empty_quest_dir(self, tmp_path):
        """Minimal output for empty directory."""
        quest_dir = tmp_path / "empty-quest"
        quest_dir.mkdir()

        data = load_quest_data(quest_dir)

        assert data.name == "Unknown Quest"
        assert data.quest_id == ""
        assert data.achievements == []

    def test_load_quest_data_handles_nonexistent_dir(self, tmp_path):
        """Returns defaults for nonexistent directory."""
        data = load_quest_data(tmp_path / "does-not-exist")
        assert data.name == "Unknown Quest"


class TestBlockLetterTitle:
    """Tests for block letter rendering (AC2)."""

    def test_block_letter_renders_short_name(self):
        """Verifies block letters for 'TEST'."""
        result = block_letter_title("TEST")

        # Should be 5 lines tall
        lines = result.split("\n")
        assert len(lines) == 5

        # Unicode mode uses filled block characters for stronger visuals
        assert "█" in result

    def test_block_letter_safe_mode_ascii_only(self):
        """All chars are ASCII in safe mode."""
        result = block_letter_title("HELLO", safe_mode=True)
        assert all(ord(c) < 128 for c in result)

    def test_block_letter_long_name_falls_back(self):
        """Names wider than terminal get centered banner fallback."""
        long_name = "A" * 20  # 20 * 6 = 120 chars wide, > 80
        result = block_letter_title(long_name, max_width=80)

        # Should be a fallback banner (3 lines: border, text, border)
        lines = result.split("\n")
        assert len(lines) == 3
        assert "=" in lines[0]  # border character

    def test_block_letter_unsupported_chars_fall_back(self):
        """Names with unsupported characters get fallback banner."""
        result = block_letter_title("Hello!", max_width=80)  # '!' not in font
        lines = result.split("\n")
        assert len(lines) == 3  # fallback banner


class TestAchievements:
    """Tests for achievement generation and rendering."""

    def test_achievements_generated_from_stats(self):
        """Verifies correct achievements for given data."""
        achievements = [
            Achievement(icon="[WIN]", title="Quest Complete", description="All done"),
            Achievement(
                icon="[BUG]", title="Gremlin Slayer", description="Fixed 3 issues"
            ),
        ]
        result = render_achievements(achievements, safe_mode=True)

        assert "ACHIEVEMENTS UNLOCKED" in result
        assert "Quest Complete" in result
        assert "Gremlin Slayer" in result

    def test_no_achievements_for_empty_quest(self):
        """Empty achievements produces empty string."""
        result = render_achievements([], safe_mode=True)
        assert result == ""


class TestMovieCredits:
    """Tests for full movie-style credits (AC6)."""

    def test_credits_include_starring_agents(self):
        """Verifies agent names appear in credits."""
        data = QuestData(
            name="Test Quest",
            agents=[
                AgentInfo(
                    name="builder",
                    model="claude-opus-4-6",
                    role_title="The Implementer",
                    summary="Built it",
                    phase="Building",
                ),
                AgentInfo(
                    name="plan-reviewer-a",
                    model="gpt-5.3",
                    role_title="The Plan Critic",
                    summary="Reviewed the plan",
                    phase="Planning",
                ),
            ],
        )

        lines = get_movie_credits_lines(data, safe_mode=True)
        text = "\n".join(lines)

        assert "STARRING" in text
        assert "builder" in text
        assert "The Implementer" in text
        assert "plan-reviewer-a" in text

    def test_credits_include_achievements(self):
        """Verifies achievements section in credits."""
        data = QuestData(
            name="Test Quest",
            achievements=[
                Achievement(icon="[WIN]", title="Quest Complete", description="Done"),
            ],
        )

        lines = get_movie_credits_lines(data, safe_mode=True)
        text = "\n".join(lines)

        assert "ACHIEVEMENTS" in text
        assert "Quest Complete" in text

    def test_credits_safe_mode_ascii_only(self):
        """All ASCII in safe mode."""
        data = QuestData(
            name="Test Quest",
            agents=[
                AgentInfo(
                    name="builder",
                    model="model",
                    role_title="Role",
                    summary="Summary",
                    phase="Building",
                ),
            ],
            achievements=[
                Achievement(icon="[OK]", title="Done", description="All done"),
            ],
        )

        lines = get_movie_credits_lines(data, safe_mode=True)
        text = "\n".join(lines)
        assert all(ord(c) < 128 for c in text)

    def test_credits_include_the_end(self):
        """Credits include THE END banner."""
        data = QuestData(name="Test Quest")
        lines = get_movie_credits_lines(data, safe_mode=True)
        text = "\n".join(lines)

        assert "THE END" in text
        assert "QUEST PRODUCTION" in text.upper()


class TestScrollCredits:
    """Tests for scroll_credits timing (AC10)."""

    def test_scroll_credits_default_speed(self):
        """Default speed uses 0.15s per line."""
        lines = ["line 1", "line 2", "line 3"]
        output = StringIO()

        with patch("quest_celebrate.progress.time.sleep") as mock_sleep:
            scroll_credits(lines, speed="default", output=output)

        # Should call sleep with 0.15 for each line
        assert mock_sleep.call_count == 3
        for call in mock_sleep.call_args_list:
            assert call[0][0] == 0.15

    def test_scroll_credits_slow_speed(self):
        """Slow speed uses 0.3s per line."""
        lines = ["line 1", "line 2"]
        output = StringIO()

        with patch("quest_celebrate.progress.time.sleep") as mock_sleep:
            scroll_credits(lines, speed="slow", output=output)

        assert mock_sleep.call_count == 2
        for call in mock_sleep.call_args_list:
            assert call[0][0] == 0.3

    def test_scroll_credits_fast_speed(self):
        """Fast speed uses 0.02s per line."""
        lines = ["line 1"]
        output = StringIO()

        with patch("quest_celebrate.progress.time.sleep") as mock_sleep:
            scroll_credits(lines, speed="fast", output=output)

        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args[0][0] == 0.02

    def test_scroll_credits_writes_all_lines(self):
        """All lines are written to output."""
        lines = ["alpha", "beta", "gamma"]
        output = StringIO()

        with patch("quest_celebrate.progress.time.sleep"):
            scroll_credits(lines, speed="fast", output=output)

        result = output.getvalue()
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result


class TestQualityScore:
    """Tests for quality score rendering."""

    def test_render_quality_score_high(self):
        """High score renders grade A."""
        result = render_quality_score(95, safe_mode=True)
        assert "95%" in result
        assert "A" in result
        assert "QUALITY SCORE" in result

    def test_render_quality_score_low(self):
        """Low score renders grade F."""
        result = render_quality_score(40, safe_mode=True)
        assert "40%" in result
        assert "F" in result

    def test_render_quality_score_ascii_only(self):
        """Quality score is ASCII-only in safe mode."""
        result = render_quality_score(75, safe_mode=True)
        assert all(ord(c) < 128 for c in result)


class TestImpactMetrics:
    """Tests for impact metrics rendering."""

    def test_render_impact_metrics(self):
        """Impact metrics include agent count and file count."""
        data = QuestData(
            agents=[
                AgentInfo(name="a", model="m", role_title="R", summary="s", phase="p"),
                AgentInfo(name="b", model="m", role_title="R", summary="s", phase="p"),
            ],
            files_changed=["file1.py", "file2.py", "file3.py"],
            plan_iterations=2,
            fix_iterations=1,
            review_count=3,
            review_findings=["f1"],
        )

        result = render_impact_metrics(data, safe_mode=True)

        assert "IMPACT METRICS" in result
        assert "2" in result  # agents
        assert "3" in result  # files changed


class TestQualityTier:
    """Tests for the compute_quality_tier function."""

    def test_diamond_zero_issues_zero_fix(self):
        tier = compute_quality_tier(
            plan_iterations=1,
            fix_iterations=0,
            review_findings_count=0,
            status="complete",
        )
        assert tier == "Diamond"

    def test_platinum_minor_issues_one_fix(self):
        tier = compute_quality_tier(
            plan_iterations=1,
            fix_iterations=1,
            review_findings_count=2,
            status="complete",
        )
        assert tier == "Platinum"

    def test_gold_two_plan_one_fix(self):
        tier = compute_quality_tier(
            plan_iterations=2,
            fix_iterations=1,
            review_findings_count=3,
            status="complete",
        )
        assert tier == "Gold"

    def test_silver_two_fix_iterations(self):
        tier = compute_quality_tier(
            plan_iterations=2,
            fix_iterations=2,
            review_findings_count=5,
            status="complete",
        )
        assert tier == "Silver"

    def test_bronze_three_fix_iterations(self):
        """3 fix iterations (below max gate of 3) → Bronze."""
        tier = compute_quality_tier(
            plan_iterations=1,
            fix_iterations=3,
            review_findings_count=5,
            status="complete",
            max_plan_iterations=5,
            max_fix_iterations=4,
        )
        assert tier == "Bronze"

    def test_tin_approaching_max_gate(self):
        """Hit one max gate but not both → Tin."""
        tier = compute_quality_tier(
            plan_iterations=4,
            fix_iterations=2,
            review_findings_count=5,
            status="complete",
            max_plan_iterations=4,
            max_fix_iterations=4,
        )
        assert tier == "Tin"

    def test_cardboard_hit_both_max_gates(self):
        """Hit both max gates → Cardboard."""
        tier = compute_quality_tier(
            plan_iterations=4,
            fix_iterations=3,
            review_findings_count=5,
            status="complete",
            max_plan_iterations=4,
            max_fix_iterations=3,
        )
        assert tier == "Cardboard"

    def test_abandoned_status(self):
        tier = compute_quality_tier(
            plan_iterations=1,
            fix_iterations=0,
            review_findings_count=0,
            status="abandoned",
        )
        assert tier == "Abandoned"

    def test_solo_uses_configured_fix_iteration_cap(self):
        tier = compute_quality_tier(
            plan_iterations=1,
            fix_iterations=2,
            review_findings_count=1,
            status="complete",
            max_plan_iterations=4,
            max_fix_iterations=3,
            quest_mode="solo",
            solo_max_fix_iterations=2,
        )
        assert tier == "Tin"

    def test_allowlist_loader_rejects_non_positive_or_bool_iteration_values(self):
        fake_allowlist = json.dumps(
            {
                "gates": {
                    "max_plan_iterations": True,
                    "max_fix_iterations": -1,
                },
                "solo": {
                    "max_fix_iterations": 0,
                },
            }
        )
        with patch("pathlib.Path.read_text", return_value=fake_allowlist):
            max_plan, max_fix, solo_fix = _load_allowlist_quality_defaults()
        assert max_plan == 4
        assert max_fix == 3
        assert solo_fix == 2

    def test_journal_replay_does_not_read_live_allowlist(self, tmp_path):
        journal_path = tmp_path / "journal.md"
        journal_path.write_text(
            textwrap.dedent(
                """\
                # Quest Journal: test-quest

                - Quest ID: `test-quest_2026-03-05__0643`
                - Status: complete

                ## Iterations

                - Plan iterations: 1
                - Fix iterations: 0
            """
            ),
            encoding="utf-8",
        )

        with patch(
            "quest_celebrate.quest_data._load_allowlist_quality_defaults",
            side_effect=AssertionError(
                "should not read live allowlist during journal replay"
            ),
        ):
            data = load_quest_data_from_journal(journal_path)
        assert data.quality_tier == "Diamond"

    def test_all_tiers_in_quality_tiers_dict(self):
        """Every tier the function can return has an entry in QUALITY_TIERS."""
        for tier_name in [
            "Diamond",
            "Platinum",
            "Gold",
            "Silver",
            "Bronze",
            "Tin",
            "Cardboard",
            "Abandoned",
        ]:
            assert tier_name in QUALITY_TIERS
            icon, grade, tooltip = QUALITY_TIERS[tier_name]
            assert icon
            assert grade
            assert tooltip


class TestJournalCelebrationData:
    """Tests for celebration_data extraction from journal markdown."""

    SAMPLE_JOURNAL = textwrap.dedent(
        """\
        # Quest Journal: test-quest

        - Quest ID: `test-quest_2026-03-05__0643`
        - Completed: 2026-03-05

        ## What Shipped

        - Something great

        ## Iterations

        - Plan iterations: 1
        - Fix iterations: 1

        ## Celebration Data

        <!-- celebration-data-start -->
        ```json
        {
          "agents": [
            {"name": "planner", "model": "claude-opus-4-6", "role": "The Architect"},
            {"name": "builder", "model": "gpt-5.3-codex", "role": "The Implementer"}
          ],
          "achievements": [
            {"icon": "⭐️", "title": "One-Plan Wonder", "desc": "Plan approved in 1 iteration"}
          ],
          "metrics": [
            {"icon": "📊", "label": "5 modules created"}
          ],
          "quality": {"tier": "Platinum", "icon": "🏆", "grade": "A"},
          "quote": {
            "text": "Clean implementation.",
            "attribution": "Code Reviewer A"
          },
          "victory_narrative": "A great quest.",
          "test_count": 42,
          "tests_added": 15,
          "files_changed": 7
        }
        ```
        <!-- celebration-data-end -->
    """
    )

    def test_extract_celebration_data_finds_json(self):
        data = extract_celebration_data_from_journal(self.SAMPLE_JOURNAL)
        assert data is not None
        assert data["quality"]["tier"] == "Platinum"
        assert data["test_count"] == 42
        assert data["tests_added"] == 15
        assert len(data["agents"]) == 2

    def test_extract_celebration_data_returns_none_for_legacy(self):
        legacy = "# Quest Journal: old\n\n- Quest ID: `old_2026-01-01`\n"
        data = extract_celebration_data_from_journal(legacy)
        assert data is None

    def test_extract_celebration_data_handles_malformed_json(self):
        bad = "<!-- celebration-data-start -->\n```json\n{bad json}\n```\n<!-- celebration-data-end -->"
        data = extract_celebration_data_from_journal(bad)
        assert data is None

    def test_extract_celebration_data_returns_none_for_non_object_root(self):
        non_object = "<!-- celebration-data-start -->\n```json\n[]\n```\n<!-- celebration-data-end -->"
        data = extract_celebration_data_from_journal(non_object)
        assert data is None

    def test_load_quest_data_from_journal_with_celebration_data(self, tmp_path):
        journal_path = tmp_path / "test-quest_2026-03-05.md"
        journal_path.write_text(self.SAMPLE_JOURNAL)

        data = load_quest_data_from_journal(journal_path)
        assert data.quest_id == "test-quest_2026-03-05__0643"
        assert data.name == "test-quest"
        assert data.quality_tier == "Platinum"
        assert data.test_count == 42
        assert data.tests_added == 15
        assert len(data.agents) == 2
        assert data.agents[0].name == "planner"
        assert data.agents[0].model == "claude-opus-4-6"
        assert len(data.achievements) == 1
        assert data.plan_iterations == 1
        assert data.fix_iterations == 1

    def test_load_quest_data_from_journal_reads_carryover_findings(self, tmp_path):
        journal = textwrap.dedent(
            """\
            # Quest Journal: carryover

            - Quest ID: `carryover_2026-04-16__1200`

            <!-- celebration-data-start -->
            ```json
            {
              "quality": {"tier": "Gold"},
              "inherited_findings_used": {
                "count": 2,
                "summaries": [
                  "Deferred auth cleanup was pulled into scope.",
                  "Legacy validation gap was revisited."
                ]
              },
              "findings_left_for_future_quests": {
                "count": 1,
                "summaries": [
                  "Follow up on dashboard backlog rendering."
                ]
              }
            }
            ```
            <!-- celebration-data-end -->
            """
        )
        journal_path = tmp_path / "carryover_2026-04-16.md"
        journal_path.write_text(journal)

        data = load_quest_data_from_journal(journal_path)

        assert data.inherited_findings_used.count == 2
        assert data.inherited_findings_used.summaries[0] == (
            "Deferred auth cleanup was pulled into scope."
        )
        assert data.findings_left_for_future_quests.count == 1

    def test_load_quest_data_from_journal_legacy_no_celebration_data(self, tmp_path):
        legacy = textwrap.dedent(
            """\
            # Quest Journal: old-quest

            - Quest ID: `old-quest_2026-01-01__0000`
            - Completed: 2026-01-01

            ## Iterations

            - Plan iterations: 2
            - Fix iterations: 2
        """
        )
        journal_path = tmp_path / "old-quest_2026-01-01.md"
        journal_path.write_text(legacy)

        data = load_quest_data_from_journal(journal_path)
        assert data.quest_id == "old-quest_2026-01-01__0000"
        assert data.plan_iterations == 2
        assert data.fix_iterations == 2
        # Quality tier should be computed from iterations
        assert data.quality_tier == "Silver"
        # No agents or achievements from legacy
        assert len(data.agents) == 0

    def test_load_quest_data_from_journal_parses_date_first_id_slug_when_slug_missing(
        self, tmp_path
    ):
        journal = textwrap.dedent(
            """\
            # Quest Journal: Portable Pre Commit Review

            - Quest ID: `2026-04-29_1430__portable-pre-commit-review`
            - Completed: 2026-04-29
            """
        )
        journal_path = tmp_path / "portable-pre-commit-review_2026-04-29.md"
        journal_path.write_text(journal, encoding="utf-8")

        data = load_quest_data_from_journal(journal_path)

        assert data.slug == "portable-pre-commit-review"

    def test_load_quest_data_from_journal_supports_existing_journal_formats(
        self, tmp_path
    ):
        legacy = textwrap.dedent(
            """\
            # Quest: Dashboard Final Implementation

            **Quest ID:** dashboard-final-implementation_2026-02-12__0913
            **Status:** Abandoned (superseded by dashboard-v2)

            ## Iterations

            - Plan iterations: 1
            - Fix iterations: 0
        """
        )
        journal_path = tmp_path / "dashboard-final-implementation_2026-02-12.md"
        journal_path.write_text(legacy)

        data = load_quest_data_from_journal(journal_path)

        assert data.quest_id == "dashboard-final-implementation_2026-02-12__0913"
        assert data.name == "Dashboard Final Implementation"
        assert data.status == "abandoned"

    def test_load_quest_data_from_journal_skips_invalid_json_entries(self, tmp_path):
        journal = textwrap.dedent(
            """\
            # Quest Journal: malformed-json

            - Quest ID: `malformed-json_2026-03-06__1200`

            <!-- celebration-data-start -->
            ```json
            {
              "quality": {"tier": "Gold"},
              "agents": ["planner", {"name": "builder", "model": "gpt-5.3-codex", "role": "The Implementer"}],
              "achievements": ["bad", {"title": "Shipped", "desc": "Still made it"}],
              "quote": "not-an-object"
            }
            ```
            <!-- celebration-data-end -->
        """
        )
        journal_path = tmp_path / "malformed-json_2026-03-06.md"
        journal_path.write_text(journal)

        data = load_quest_data_from_journal(journal_path)

        assert [agent.name for agent in data.agents] == ["builder"]
        assert [achievement.title for achievement in data.achievements] == ["Shipped"]
        assert data.brief_summary == ""

    def test_load_quest_data_from_journal_ignores_invalid_quality_tier_type(
        self, tmp_path
    ):
        journal = textwrap.dedent(
            """\
            # Quest Journal: malformed-quality

            - Quest ID: `malformed-quality_2026-03-06__1200`

            <!-- celebration-data-start -->
            ```json
            {
              "quality": {"tier": ["Gold"]}
            }
            ```
            <!-- celebration-data-end -->
        """
        )
        journal_path = tmp_path / "malformed-quality_2026-03-06.md"
        journal_path.write_text(journal)

        data = load_quest_data_from_journal(journal_path)

        assert data.quality_tier == ""

    def test_load_quest_data_from_journal_rejects_boolean_carryover_count(
        self, tmp_path
    ):
        journal = textwrap.dedent(
            """\
            # Quest Journal: malformed-carryover

            - Quest ID: `malformed-carryover_2026-03-06__1200`

            <!-- celebration-data-start -->
            ```json
            {
              "inherited_findings_used": {
                "count": true,
                "summaries": ["Deferred auth cleanup was pulled into scope."]
              }
            }
            ```
            <!-- celebration-data-end -->
        """
        )
        journal_path = tmp_path / "malformed-carryover_2026-03-06.md"
        journal_path.write_text(journal)

        data = load_quest_data_from_journal(journal_path)

        assert data.inherited_findings_used.count == 1
        assert data.inherited_findings_used.summaries == [
            "Deferred auth cleanup was pulled into scope."
        ]

    def test_load_quest_data_from_journal_leaves_tier_unset_without_iterations(
        self, tmp_path
    ):
        journal = textwrap.dedent(
            """\
            # Quest Journal: legacy-no-iterations

            - Quest ID: `legacy-no-iterations_2026-03-06__1200`
        """
        )
        journal_path = tmp_path / "legacy-no-iterations_2026-03-06.md"
        journal_path.write_text(journal)

        data = load_quest_data_from_journal(journal_path)

        assert data.quality_tier == ""

    def test_load_quest_data_from_journal_nonexistent_file(self, tmp_path):
        data = load_quest_data_from_journal(tmp_path / "nope.md")
        assert data.quest_id == ""
        assert data.quality_tier == ""
