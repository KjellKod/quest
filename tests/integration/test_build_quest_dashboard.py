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

    # Required sections
    assert "Quest Dashboard" in html
    assert 'id="finished-quests"' in html
    assert 'id="in-progress-quests"' in html
    assert 'id="abandoned-quests"' in html

    # Check for inline CSS (self-contained)
    assert "<style>" in html
    assert "--bg-0:" in html  # Design tokens present

    # No external dependencies
    assert '<link rel="stylesheet"' not in html
    assert '<script src=' not in html

    # KPI section present
    assert "Finished" in html
    assert "In Progress" in html
    assert "Abandoned" in html

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

    # Verify it's valid HTML
    html = custom_output.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()
    assert "Quest Dashboard" in html


def test_build_with_github_url_flag(tmp_path):
    """Test building dashboard with explicit GitHub URL."""
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "quest_dashboard" / "build_quest_dashboard.py"

    # Use custom output
    output_path = tmp_path / "dashboard.html"

    # Run build with GitHub URL
    custom_url = "https://github.com/test-owner/test-repo"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--output",
            str(output_path),
            "--github-url",
            custom_url,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Check success
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    assert output_path.exists()

    # Verify custom GitHub URL is used in links (unconditional: repo has journal entries)
    html = output_path.read_text(encoding="utf-8")
    assert f"{custom_url}/blob/main/" in html
