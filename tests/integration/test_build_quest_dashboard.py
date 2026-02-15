"""Integration test for the quest dashboard build process."""

import subprocess
import sys
from pathlib import Path

import pytest


def test_build_dashboard_produces_valid_html(tmp_path):
    """Test end-to-end dashboard build from actual repo data.

    Arbiter guidance: write to tmp_path, not the tracked docs/dashboard/ directory.
    """
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "quest_dashboard" / "build_quest_dashboard.py"

    # Write to temp directory to avoid overwriting tracked output
    output_path = tmp_path / "index.html"

    # Run the build script
    result = subprocess.run(
        [sys.executable, str(script_path), "--output", str(output_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Check that build succeeded
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Verify output file exists
    assert output_path.exists(), "Dashboard HTML file not created"

    # Read and validate HTML
    html = output_path.read_text(encoding="utf-8")

    # Basic HTML structure
    assert "<!doctype html>" in html.lower()
    assert "<html" in html
    assert "</html>" in html

    # Updated title and portfolio section
    assert "Quest Portfolio Dashboard" in html
    assert 'id="quest-portfolio"' in html

    # Check for inline CSS (self-contained)
    assert "<style>" in html
    assert "--bg-0:" in html  # Design tokens present

    # No external dependencies
    assert '<link rel="stylesheet"' not in html
    assert "<script src=" not in html

    # KPI section present (5 cards)
    assert "Total Quests" in html
    assert "Finished" in html
    assert "In Progress" in html
    assert "Blocked" in html
    assert "Abandoned" in html

    # Chart.js inlined and chart canvases present
    assert "<script>" in html
    assert 'id="chart-status-doughnut"' in html
    assert 'id="chart-time-progression"' in html

    # Page-glow elements present (2 orbs)
    assert 'class="page-glow page-glow-left"' in html
    assert 'class="page-glow page-glow-right"' in html

    print(f"Dashboard built successfully: {output_path}")
    print(f"HTML size: {len(html)} bytes")


def test_build_with_custom_output_path(tmp_path):
    """Test building dashboard with custom output path."""
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "quest_dashboard" / "build_quest_dashboard.py"

    # Use custom output in temp directory
    custom_output = tmp_path / "custom" / "dashboard.html"

    # Run build with custom output
    result = subprocess.run(
        [sys.executable, str(script_path), "--output", str(custom_output)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Check success
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    assert custom_output.exists(), "Custom output file not created"

    # Verify it's valid HTML with updated title
    html = custom_output.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()
    assert "Quest Portfolio Dashboard" in html


def test_build_with_github_url_flag(tmp_path):
    """Test that --github-url flag produces PR links using the supplied URL base.

    Runs main() in a subprocess with a mocked loader that injects fixture data
    containing a quest with pr_number=99. The mock uses github_repo_url=None so
    the only way the custom URL can appear in the output is if the CLI flag
    --github-url is correctly wired through main() to the renderer.
    """
    custom_url = "https://github.com/test-owner/test-repo"
    output_path = tmp_path / "dashboard.html"
    repo_root = Path(__file__).resolve().parents[2]

    # The mock uses a side_effect that reads the github_url kwarg passed by
    # main() and sets it on the returned DashboardData.  If main() stops
    # forwarding --github-url to load_dashboard_data(), the mock will receive
    # github_url=None, the fixture's github_repo_url will stay empty, no PR
    # link will be rendered, and the assertion below will fail.
    scripts_dir = str(repo_root / "scripts")
    cwd_dir = str(repo_root / "scripts" / "quest_dashboard")
    test_script = tmp_path / "run_test.py"
    test_script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {scripts_dir!r})\n"
        f"sys.path.insert(0, {cwd_dir!r})\n"
        "from unittest.mock import patch\n"
        "from datetime import date\n"
        "from pathlib import Path\n"
        "from quest_dashboard.models import DashboardData, JournalEntry\n"
        "\n"
        "def fake_loader(repo_root, github_url=None):\n"
        "    return DashboardData(\n"
        "        finished_quests=[JournalEntry(\n"
        "            quest_id='pr-test-001', slug='pr-test',\n"
        "            title='PR Test Quest',\n"
        "            elevator_pitch='Quest with PR.',\n"
        "            status='Completed',\n"
        "            completed_date=date(2026, 2, 10),\n"
        "            journal_path=Path('docs/quest-journal/pr-test.md'),\n"
        "            pr_number=99)],\n"
        "        active_quests=[], abandoned_quests=[],\n"
        "        github_repo_url=github_url or '')\n"
        "\n"
        "patcher = patch(\n"
        "    'quest_dashboard.loaders.load_dashboard_data',\n"
        "    side_effect=fake_loader)\n"
        "patcher.start()\n"
        "from build_quest_dashboard import main\n"
        f"main(['--output', {str(output_path)!r},\n"
        f"      '--github-url', {custom_url!r}])\n"
        "patcher.stop()\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(test_script)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, f"Build failed: {result.stderr}"
    assert output_path.exists()

    html = output_path.read_text(encoding="utf-8")
    assert "Quest Portfolio Dashboard" in html
    assert 'id="quest-portfolio"' in html
    # Verify the custom GitHub URL is used in the PR link.
    # The fixture has github_repo_url=None, so this can only pass
    # if --github-url is correctly wired through the CLI to the renderer.
    assert "https://github.com/test-owner/test-repo/pull/99" in html
