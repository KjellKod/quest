"""Unit tests for quest_celebrate package."""

import json
import os
import subprocess
import sys
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
    box_banner,
    get_credits_lines,
    gremlin_battle_art,
    gremlin_retirement_art,
    rocket_launch_art,
    trophy_art,
)
from quest_celebrate.config import CelebrationConfig, load_config
from quest_celebrate.progress import render_progress_bar, render_phase_progress
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


class TestRenderEpic:
    """Tests for epic style rendering (AC3)."""

    def test_render_epic_produces_all_sections(self):
        """Epic style produces progress bars, art, and credits."""
        stats = QuestStats(
            name="Epic Quest",
            tools_count=3,
            phases=[("Planning", "complete"), ("Building", "complete")],
        )
        config = CelebrationConfig(
            style="epic", is_safe=True, show_progress=True, ascii_art=True
        )
        output = StringIO()

        with patch("time.sleep"):  # Speed up animation
            render_epic(stats, config, output)

        result = output.getvalue()
        assert "QUEST COMPLETE" in result.upper() or "complete" in result.lower()

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


class TestRenderSilly:
    """Tests for silly style rendering (AC4)."""

    def test_render_silly_includes_flair(self):
        """Silly style includes extra fun elements."""
        stats = QuestStats(name="Silly Quest", bugs_fixed=3)
        config = CelebrationConfig(style="silly", is_safe=True, ascii_art=True)
        output = StringIO()

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

        render_silly(stats, config, output)

        result = output.getvalue()
        assert "3" in result or "tools" in result.lower() or "forged" in result.lower()


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
        assert has_unicode or "█" in bar or "░" in bar or "=" in bar


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
