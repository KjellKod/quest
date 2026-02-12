"""Unit tests for quest_dashboard.render module."""

from datetime import date, datetime, timezone
from pathlib import Path

from quest_dashboard.models import ActiveQuest, DashboardData, JournalEntry
from quest_dashboard.render import render_dashboard

UTC = timezone.utc


def test_finished_card_has_journal_link(tmp_path):
    """Test that finished quest cards contain a View Journal link."""
    entry = JournalEntry(
        quest_id="test-001",
        slug="test-quest",
        title="Test Quest",
        elevator_pitch="This is a test quest.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/test-quest.md"),
        pr_number=24,
        plan_iterations=2,
        fix_iterations=1,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="https://github.com/owner/repo",
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Check for View Journal link
    assert "View Journal &rarr;" in html
    assert (
        "https://github.com/owner/repo/blob/main/docs/quest-journal/test-quest.md"
        in html
    )


def test_active_card_has_no_journal_link(tmp_path):
    """Test that active quest cards do not contain View Journal link."""
    quest = ActiveQuest(
        quest_id="active-001",
        slug="active-quest",
        title="Active Quest",
        elevator_pitch="This is an active quest.",
        status="In Progress",
        phase="Building",
        updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        plan_iterations=1,
        fix_iterations=0,
    )

    data = DashboardData(
        finished_quests=[],
        active_quests=[quest],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Active section should not have View Journal link
    # Extract just the in-progress section
    in_progress_start = html.find('id="in-progress-quests"')
    in_progress_end = html.find("</section>", in_progress_start)
    in_progress_section = html[in_progress_start:in_progress_end]

    assert "View Journal" not in in_progress_section


def test_card_metadata_uses_muted_class(tmp_path):
    """Test that quest metadata is wrapped in quest-meta class."""
    entry = JournalEntry(
        quest_id="test-001",
        slug="test-quest",
        title="Test Quest",
        elevator_pitch="Test pitch.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/test-quest.md"),
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Check for quest-meta class
    assert 'class="quest-meta"' in html


def test_sections_rendered_in_order(tmp_path):
    """Test that sections appear in order: Finished, In Progress, Abandoned."""
    finished_entry = JournalEntry(
        quest_id="finished-001",
        slug="finished-quest",
        title="Finished Quest",
        elevator_pitch="Finished.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/finished.md"),
    )

    active_quest = ActiveQuest(
        quest_id="active-001",
        slug="active-quest",
        title="Active Quest",
        elevator_pitch="Active.",
        status="In Progress",
        phase="Building",
        updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
    )

    abandoned_entry = JournalEntry(
        quest_id="abandoned-001",
        slug="abandoned-quest",
        title="Abandoned Quest",
        elevator_pitch="Abandoned.",
        status="Abandoned",
        completed_date=date(2026, 1, 15),
        journal_path=Path("docs/quest-journal/abandoned.md"),
    )

    data = DashboardData(
        finished_quests=[finished_entry],
        active_quests=[active_quest],
        abandoned_quests=[abandoned_entry],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Find positions of section IDs
    finished_pos = html.index('id="finished-quests"')
    in_progress_pos = html.index('id="in-progress-quests"')
    abandoned_pos = html.index('id="abandoned-quests"')

    # Verify order
    assert finished_pos < in_progress_pos < abandoned_pos


def test_pr_link_rendered_when_present(tmp_path):
    """Test that PR link is rendered when pr_number is present."""
    entry = JournalEntry(
        quest_id="test-001",
        slug="test-quest",
        title="Test Quest",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/test.md"),
        pr_number=24,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="https://github.com/owner/repo",
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Check for PR link
    assert "PR #24" in html
    assert "https://github.com/owner/repo/pull/24" in html


def test_html_is_self_contained(tmp_path):
    """Test that HTML has no external stylesheet, script, or HTTP URL references."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Check for external references
    assert '<link rel="stylesheet"' not in html
    assert "<script src=" not in html
    assert "url(http" not in html.lower()

    # Should have inline style tag
    assert "<style>" in html


def test_empty_sections_show_message(tmp_path):
    """Test that empty sections show 'No quests in this category' message."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Check for empty state messages
    assert html.count("No quests in this category") == 3


def test_warnings_section_rendered(tmp_path):
    """Test that warnings are rendered when present."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
        warnings=["Warning 1: Something went wrong", "Warning 2: Another issue"],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    assert "Build Warnings" in html
    assert "Warning 1: Something went wrong" in html
    assert "Warning 2: Another issue" in html


def test_kpi_counts_correct(tmp_path):
    """Test that KPI counts in hero section are correct."""
    finished_entries = [
        JournalEntry(
            quest_id=f"finished-{i}",
            slug=f"finished-{i}",
            title=f"Finished {i}",
            elevator_pitch="Test.",
            status="Completed",
            completed_date=date(2026, 2, 10),
            journal_path=Path(f"docs/quest-journal/finished-{i}.md"),
        )
        for i in range(5)
    ]

    active_quests = [
        ActiveQuest(
            quest_id=f"active-{i}",
            slug=f"active-{i}",
            title=f"Active {i}",
            elevator_pitch="Test.",
            status="In Progress",
            phase="Building",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        )
        for i in range(3)
    ]

    abandoned_entries = [
        JournalEntry(
            quest_id=f"abandoned-{i}",
            slug=f"abandoned-{i}",
            title=f"Abandoned {i}",
            elevator_pitch="Test.",
            status="Abandoned",
            completed_date=date(2026, 1, 15),
            journal_path=Path(f"docs/quest-journal/abandoned-{i}.md"),
        )
        for i in range(2)
    ]

    data = DashboardData(
        finished_quests=finished_entries,
        active_quests=active_quests,
        abandoned_quests=abandoned_entries,
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Extract hero section
    hero_start = html.find('<div class="hero">')
    hero_end = html.find("</div>", hero_start) + 6
    hero_section = html[hero_start:hero_end]

    # Check KPI values (they appear in specific order with specific classes)
    assert 'kpi-value kpi-value--finished">5<' in html
    assert 'kpi-value kpi-value--in-progress">3<' in html
    assert 'kpi-value kpi-value--abandoned">2<' in html


def test_fallback_journal_link_relative_to_output(tmp_path):
    """Test that fallback journal links compute correct relative path from output location."""
    entry = JournalEntry(
        quest_id="test-001",
        slug="test-quest",
        title="Test Quest",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/test-quest.md"),
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="",  # No GitHub URL -- triggers fallback
    )

    # Default output location: docs/dashboard/index.html
    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # The relative path from docs/dashboard/ to docs/quest-journal/test-quest.md
    # should be ../../docs/quest-journal/test-quest.md (go up to repo root, then down)
    assert "../../docs/quest-journal/test-quest.md" in html

    # Now test with a custom output location
    custom_output = tmp_path / "build" / "output" / "dashboard.html"
    html_custom = render_dashboard(data, custom_output, repo_root)

    # The relative path from build/output/ to docs/quest-journal/test-quest.md
    # should be ../../docs/quest-journal/test-quest.md
    assert "../../docs/quest-journal/test-quest.md" in html_custom


def test_quest_id_displayed_in_metadata(tmp_path):
    """Test that quest_id (not slug) is displayed in card metadata (AC #6)."""
    entry = JournalEntry(
        quest_id="my-quest-id-001",
        slug="my-quest-slug",
        title="Test Quest",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/test.md"),
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # quest_id should appear in metadata, not slug
    assert "my-quest-id-001" in html
    # slug should NOT appear in metadata (it may appear elsewhere, but not in meta-item)
    assert 'class="meta-item">my-quest-slug<' not in html


def test_github_url_with_double_quote_injection(tmp_path):
    """XSS regression: github_url with double-quote injection must not break href attribute."""
    entry = JournalEntry(
        quest_id="xss-001",
        slug="xss-test",
        title="XSS Test",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/xss-test.md"),
        pr_number=42,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url='" onmouseover="alert(1)',
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # The malicious URL is not a valid GitHub URL, so it should be rejected.
    # The raw injected string must not appear in any href attribute.
    assert '" onmouseover="alert(1)' not in html


def test_github_url_with_javascript_scheme(tmp_path):
    """XSS regression: javascript: scheme github_url must be rejected."""
    entry = JournalEntry(
        quest_id="xss-002",
        slug="xss-js",
        title="XSS JS Test",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/xss-js.md"),
        pr_number=43,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="javascript:alert(1)",
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # javascript: must never appear in any href
    assert "javascript:" not in html
    # Journal link should fall back to relative path
    assert "../../docs/quest-journal/xss-js.md" in html
    # PR link should fall back to #
    assert 'href="#"' in html


def test_github_url_with_single_quote_injection(tmp_path):
    """XSS regression: github_url with single-quote injection must not break href attribute."""
    entry = JournalEntry(
        quest_id="xss-003",
        slug="xss-sq",
        title="XSS SQ Test",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/xss-sq.md"),
        pr_number=44,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="' onmouseover='alert(1)",
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # The malicious URL is not a valid GitHub URL, so it should be rejected.
    assert "' onmouseover='alert(1)" not in html


def test_valid_github_url_renders_correctly(tmp_path):
    """Test that a valid github_url produces correct journal and PR links."""
    entry = JournalEntry(
        quest_id="valid-001",
        slug="valid-quest",
        title="Valid Quest",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/valid-quest.md"),
        pr_number=50,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="https://github.com/owner/repo",
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # Valid URLs should be preserved
    assert (
        "https://github.com/owner/repo/blob/main/docs/quest-journal/valid-quest.md"
        in html
    )
    assert "https://github.com/owner/repo/pull/50" in html


def test_fallback_journal_link_with_malicious_filename(tmp_path):
    """XSS regression: journal filename with quotes must be escaped in fallback relative link."""
    entry = JournalEntry(
        quest_id="xss-fallback-001",
        slug="xss-fallback",
        title="XSS Fallback Test",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path('docs/quest-journal/evil" onclick="alert(1).md'),
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
        github_repo_url="",  # Empty URL triggers fallback to relative path
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    html = render_dashboard(data, output_path, repo_root)

    # The raw double-quote must NOT appear unescaped in the href attribute.
    # It should be escaped to &quot; so it cannot break out of href="...".
    assert 'evil" onclick="alert(1)' not in html
    # The escaped version should be present instead
    assert "evil&quot; onclick=&quot;alert(1).md" in html
