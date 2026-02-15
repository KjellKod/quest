"""Unit tests for quest_dashboard.render module."""

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from quest_dashboard.models import ActiveQuest, DashboardData, JournalEntry
from quest_dashboard.render import _compute_monthly_buckets, render_dashboard

UTC = timezone.utc


def test_card_shows_full_pitch_and_labeled_metadata(tmp_path):
    """Test that quest cards show full pitch text and labeled metadata (no journal link)."""
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

    result = render_dashboard(data, output_path, repo_root)

    # Full pitch text present (no truncation)
    assert "This is a test quest." in result

    # No "View Journal" link
    assert "View Journal" not in result

    # Labeled metadata present
    assert "<b>Quest ID:</b>" in result
    assert "<b>Completion Date:</b>" in result
    assert "<b>Iterations:</b>" in result
    assert "<b>PR:</b>" in result


def test_active_card_shows_updated_date_label(tmp_path):
    """Test that active quest cards show Updated: label (not Completion Date)."""
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

    result = render_dashboard(data, output_path, repo_root)

    # No "View Journal" link
    assert "View Journal" not in result

    # Active cards show "Updated:" label
    assert "<b>Updated:</b>" in result


def test_card_metadata_uses_muted_class(tmp_path):
    """Test that quest metadata is wrapped in quest-meta class with bold labels."""
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

    result = render_dashboard(data, output_path, repo_root)

    # Check for quest-meta class with bold labels
    assert 'class="quest-meta"' in result
    assert "<b>Quest ID:</b>" in result


def test_portfolio_section_contains_all_quests(tmp_path):
    """Test that all quests appear in a single Quest Portfolio section, sorted by date."""
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

    result = render_dashboard(data, output_path, repo_root)

    # Single Quest Portfolio section contains all quests
    assert 'id="quest-portfolio"' in result
    assert "Finished Quest" in result
    assert "Active Quest" in result
    assert "Abandoned Quest" in result

    # No separate section IDs
    assert 'id="finished-quests"' not in result
    assert 'id="in-progress-quests"' not in result
    assert 'id="abandoned-quests"' not in result

    # Sorted by date descending: Active (Feb 12) > Finished (Feb 10) > Abandoned (Jan 15)
    active_pos = result.index("Active Quest")
    finished_pos = result.index("Finished Quest")
    abandoned_pos = result.index("Abandoned Quest")
    assert active_pos < finished_pos < abandoned_pos


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

    result = render_dashboard(data, output_path, repo_root)

    # Check for PR link in labeled metadata
    assert "<b>PR:</b>" in result
    assert "#24" in result
    assert "https://github.com/owner/repo/pull/24" in result


def test_html_is_self_contained(tmp_path):
    """Test that HTML has no external stylesheet, script, or HTTP URL references."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Check for external references
    assert '<link rel="stylesheet"' not in result
    assert "<script src=" not in result
    assert "url(http" not in result.lower()

    # Should have inline style tag
    assert "<style>" in result


def test_empty_sections_show_message(tmp_path):
    """Test that empty portfolio shows 'No quests in this category' message."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Single portfolio section with empty state
    assert result.count("No quests in this category") == 1


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

    result = render_dashboard(data, output_path, repo_root)

    assert "Build Warnings" in result
    assert "Warning 1: Something went wrong" in result
    assert "Warning 2: Another issue" in result


def test_kpi_counts_correct(tmp_path):
    """Test that 5 KPI cards show correct counts including blocked separation."""
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

    result = render_dashboard(data, output_path, repo_root)

    # 5 KPI cards present
    assert result.count('class="kpi-card"') == 5

    # Correct counts: Total=10, Finished=5, In Progress=3, Blocked=0, Abandoned=2
    assert 'kpi-value">10<' in result  # Total (no color class)
    assert 'kpi-value kpi-value--finished">5<' in result
    assert 'kpi-value kpi-value--in-progress">3<' in result
    assert 'kpi-value kpi-value--blocked">0<' in result
    assert 'kpi-value kpi-value--abandoned">2<' in result


def test_labeled_metadata_format(tmp_path):
    """Test that card metadata uses labeled key-value format (replaces journal link test)."""
    entry = JournalEntry(
        quest_id="test-001",
        slug="test-quest",
        title="Test Quest",
        elevator_pitch="Test.",
        status="Completed",
        completed_date=date(2026, 2, 10),
        journal_path=Path("docs/quest-journal/test-quest.md"),
        plan_iterations=2,
        fix_iterations=1,
    )

    data = DashboardData(
        finished_quests=[entry],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Labeled metadata format
    assert "<b>Quest ID:</b> test-001" in result
    assert "<b>Completion Date:</b> Feb 10, 2026" in result
    assert "<b>Iterations:</b> plan 2 / fix 1" in result


def test_quest_id_displayed_in_metadata(tmp_path):
    """Test that quest_id (not slug) is displayed in labeled card metadata."""
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

    result = render_dashboard(data, output_path, repo_root)

    # quest_id should appear in labeled metadata
    assert "<b>Quest ID:</b> my-quest-id-001" in result
    # slug should NOT appear in metadata
    assert "my-quest-slug" not in result


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

    result = render_dashboard(data, output_path, repo_root)

    # The malicious URL is not a valid GitHub URL, so it should be rejected.
    assert '" onmouseover="alert(1)' not in result


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

    result = render_dashboard(data, output_path, repo_root)

    # javascript: must never appear in any href
    assert "javascript:" not in result
    # PR link should fall back to #
    assert 'href="#"' in result


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

    result = render_dashboard(data, output_path, repo_root)

    # The malicious URL is not a valid GitHub URL, so it should be rejected.
    assert "' onmouseover='alert(1)" not in result


def test_valid_github_url_renders_correctly(tmp_path):
    """Test that a valid github_url produces correct PR links."""
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

    result = render_dashboard(data, output_path, repo_root)

    # PR link present
    assert "https://github.com/owner/repo/pull/50" in result


# ---------------------------------------------------------------------------
# Tests: Glows, Charts, Gradients, Self-containment, Portfolio
# ---------------------------------------------------------------------------


def test_glow_elements_rendered(tmp_path):
    """Glow divs with page-glow classes (2 orbs) are present outside .container."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # 2 page-glow elements with correct classes
    assert 'class="page-glow page-glow-left"' in result
    assert 'class="page-glow page-glow-right"' in result

    # Only 2 glow orbs (not 3)
    assert result.count("page-glow page-glow-") == 2

    # Glow divs must appear OUTSIDE .container (before it in <body>)
    container_pos = result.index('class="container"')
    left_pos = result.index('class="page-glow page-glow-left"')
    right_pos = result.index('class="page-glow page-glow-right"')
    assert left_pos < container_pos
    assert right_pos < container_pos

    # CSS must define pointer-events: none for .page-glow
    assert "pointer-events: none" in result

    # Glow z-index must be below content (z-index: -1)
    glow_css_pos = result.index(".page-glow {")
    glow_css_end = result.index("}", glow_css_pos)
    glow_css = result[glow_css_pos:glow_css_end]
    assert "z-index: -1" in glow_css

    # Container must establish a stacking context above glows
    container_css_pos = result.index(".container {")
    container_css_end = result.index("}", container_css_pos)
    container_css = result[container_css_pos:container_css_end]
    assert "position: relative" in container_css
    assert "z-index: 1" in container_css


def test_doughnut_chart_not_in_hero(tmp_path):
    """Doughnut chart canvas is NOT in the hero; it IS in the panel-grid."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Find the hero section boundaries
    hero_start = result.index('class="hero"')
    hero_end = result.index("</div>", hero_start)
    # Find the end more precisely by looking for the kpi-grid that follows
    kpi_grid_pos = result.index('class="kpi-grid"')
    hero_section = result[hero_start:kpi_grid_pos]

    # Doughnut canvas must NOT be inside the hero
    assert 'id="chart-status-doughnut"' not in hero_section

    # Doughnut canvas must be inside the panel-grid
    panel_grid_start = result.index('class="panel-grid"')
    panel_grid_end = result.index("</div>\n    </div>", panel_grid_start) + 20
    panel_section = result[panel_grid_start:panel_grid_end]
    assert 'id="chart-status-doughnut"' in panel_section


def test_time_progression_chart_present(tmp_path):
    """Canvas element with id chart-time-progression is present."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    assert 'id="chart-time-progression"' in result


def test_chartjs_inlined_not_external(tmp_path):
    """Chart.js is inlined as a <script> block, not loaded via src attribute."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Chart.js content should be inlined (contains "Chart" constructor)
    assert "<script>" in result
    assert "Chart" in result

    # No external script sources
    assert "<script src=" not in result


def test_quest_card_uses_surface_2(tmp_path):
    """Quest cards use --surface-2 background (not linear-gradient)."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # CSS should contain --surface-2 in the .quest-card rule
    quest_card_pos = result.index(".quest-card {")
    quest_card_end = result.index("}", quest_card_pos)
    quest_card_css = result[quest_card_pos:quest_card_end]

    assert "--surface-2" in quest_card_css
    assert "linear-gradient" not in quest_card_css


def test_quests_header_flex_layout(tmp_path):
    """Portfolio section uses quests-header with flex layout."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # quests-header with flex layout in CSS
    header_pos = result.index(".quests-header {")
    header_end = result.index("}", header_pos)
    header_css = result[header_pos:header_end]
    assert "display: flex" in header_css
    assert "justify-content: space-between" in header_css

    # quests-header in HTML
    assert 'class="quests-header"' in result


def test_decorative_elements_accessible(tmp_path):
    """Glow elements have aria-hidden; charts have noscript fallback."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Page-glow divs have aria-hidden="true"
    assert 'class="page-glow page-glow-left" aria-hidden="true"' in result
    assert 'class="page-glow page-glow-right" aria-hidden="true"' in result

    # Charts have noscript fallback
    assert "<noscript>Chart requires JavaScript</noscript>" in result


def test_compute_monthly_buckets(tmp_path):
    """Monthly bucket computation groups quests correctly with all 5 statuses."""
    finished_quests = [
        JournalEntry(
            quest_id="f1",
            slug="f1",
            title="F1",
            elevator_pitch="T",
            status="Completed",
            completed_date=date(2026, 1, 10),
            journal_path=Path("docs/quest-journal/f1.md"),
        ),
        JournalEntry(
            quest_id="f2",
            slug="f2",
            title="F2",
            elevator_pitch="T",
            status="Completed",
            completed_date=date(2026, 1, 20),
            journal_path=Path("docs/quest-journal/f2.md"),
        ),
        JournalEntry(
            quest_id="f3",
            slug="f3",
            title="F3",
            elevator_pitch="T",
            status="Completed",
            completed_date=date(2026, 3, 5),
            journal_path=Path("docs/quest-journal/f3.md"),
        ),
    ]

    abandoned_quests = [
        JournalEntry(
            quest_id="a1",
            slug="a1",
            title="A1",
            elevator_pitch="T",
            status="Abandoned",
            completed_date=date(2026, 2, 15),
            journal_path=Path("docs/quest-journal/a1.md"),
        ),
    ]

    active_quests = [
        ActiveQuest(
            quest_id="active-1",
            slug="active-1",
            title="Active 1",
            elevator_pitch="T",
            status="In Progress",
            phase="Building",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    data = DashboardData(
        finished_quests=finished_quests,
        active_quests=active_quests,
        abandoned_quests=abandoned_quests,
    )

    buckets = _compute_monthly_buckets(data)

    # Should have 3 months: 2026-01, 2026-02, 2026-03
    assert list(buckets.keys()) == ["2026-01", "2026-02", "2026-03"]

    # All buckets have 5 status keys
    for month_data in buckets.values():
        assert set(month_data.keys()) == {
            "finished",
            "abandoned",
            "in_progress",
            "blocked",
            "unknown",
        }

    # January: 2 finished
    assert buckets["2026-01"]["finished"] == 2
    assert buckets["2026-01"]["abandoned"] == 0

    # February: 0 finished, 1 abandoned, 1 in_progress (active quest)
    assert buckets["2026-02"]["finished"] == 0
    assert buckets["2026-02"]["abandoned"] == 1
    assert buckets["2026-02"]["in_progress"] == 1

    # March: 1 finished
    assert buckets["2026-03"]["finished"] == 1
    assert buckets["2026-03"]["abandoned"] == 0


def test_compute_monthly_buckets_empty():
    """Monthly bucket computation returns empty dict when no quests."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    buckets = _compute_monthly_buckets(data)
    assert buckets == {}


def test_chartjs_missing_vendor_graceful(tmp_path):
    """Graceful degradation: dashboard renders without Chart.js when vendor file is missing."""
    data = DashboardData(
        finished_quests=[
            JournalEntry(
                quest_id="f1",
                slug="f1",
                title="F1",
                elevator_pitch="Test.",
                status="Completed",
                completed_date=date(2026, 2, 10),
                journal_path=Path("docs/quest-journal/f1.md"),
            )
        ],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    # Patch the vendor file path to a nonexistent location
    fake_path = tmp_path / "nonexistent" / "chart.min.js"
    with patch("quest_dashboard.render._CHARTJS_PATH", fake_path):
        result = render_dashboard(data, output_path, repo_root)

    # No exception raised -- dashboard rendered successfully

    # No Chart.js library code in output
    assert "chart.umd" not in result.lower()

    # No chart initialization code (no `new Chart`)
    assert "new Chart" not in result

    # KPI cards still present
    assert 'class="kpi-card"' in result

    # Glow divs still present
    assert 'class="page-glow page-glow-left"' in result

    # Canvas elements may still exist (with noscript fallback)
    assert 'id="chart-status-doughnut"' in result


# ---------------------------------------------------------------------------
# New tests for the redesigned dashboard
# ---------------------------------------------------------------------------


def test_hero_has_quest_intelligence_branding(tmp_path):
    """Hero section has QUEST INTELLIGENCE eyebrow and Quest Portfolio Dashboard title."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    assert "QUEST INTELLIGENCE" in result
    assert "Quest Portfolio Dashboard" in result
    assert 'class="eyebrow"' in result


def test_hero_has_timestamp(tmp_path):
    """Hero section has a monospace timestamp line with meta-row class."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
        generated_at=datetime(2026, 2, 12, 8, 54, 0, tzinfo=UTC),
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    assert 'class="meta-row"' in result
    assert "DATA GENERATED:" in result
    assert 'class="meta-value"' in result
    # Monospace font in CSS
    assert "ui-monospace" in result


def test_kpi_row_blocked_count(tmp_path):
    """Blocked KPI shows correct count; unknown-status quests excluded from In Progress."""
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
    ] + [
        ActiveQuest(
            quest_id=f"blocked-{i}",
            slug=f"blocked-{i}",
            title=f"Blocked {i}",
            elevator_pitch="Test.",
            status="Blocked",
            phase="Building",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        )
        for i in range(2)
    ] + [
        ActiveQuest(
            quest_id="mystery-001",
            slug="mystery",
            title="Mystery Quest",
            elevator_pitch="Unknown status.",
            status="SomethingWeird",
            phase="Unknown",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    data = DashboardData(
        finished_quests=[],
        active_quests=active_quests,
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Blocked KPI shows 2
    assert 'kpi-value kpi-value--blocked">2<' in result
    # In Progress KPI shows 3 (not 4) -- unknown-status quest excluded
    assert 'kpi-value kpi-value--in-progress">3<' in result
    # Total includes all 6 active quests (including the unknown one)
    assert 'kpi-value">6<' in result


def test_charts_side_by_side_in_panel_grid(tmp_path):
    """Both chart canvases are inside a panel-grid section."""
    data = DashboardData(
        finished_quests=[],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    assert 'class="panel-grid"' in result

    # Both canvases inside panel-grid
    panel_grid_start = result.index('class="panel-grid"')
    panel_grid_section = result[panel_grid_start:]
    assert 'id="chart-status-doughnut"' in panel_grid_section
    assert 'id="chart-time-progression"' in panel_grid_section


def test_doughnut_chart_has_five_statuses(tmp_path):
    """Chart config JS contains all 5 status labels for doughnut."""
    data = DashboardData(
        finished_quests=[
            JournalEntry(
                quest_id="f1",
                slug="f1",
                title="F1",
                elevator_pitch="Test.",
                status="Completed",
                completed_date=date(2026, 2, 10),
                journal_path=Path("docs/quest-journal/f1.md"),
            )
        ],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # All 5 labels in chart config
    assert "'In Progress'" in result
    assert "'Blocked'" in result
    assert "'Abandoned'" in result
    assert "'Finished'" in result
    assert "'Unknown'" in result


def test_portfolio_sorted_by_date(tmp_path):
    """Quest cards appear in descending date order in portfolio."""
    old_entry = JournalEntry(
        quest_id="old-001",
        slug="old-quest",
        title="Old Quest",
        elevator_pitch="Old.",
        status="Completed",
        completed_date=date(2026, 1, 1),
        journal_path=Path("docs/quest-journal/old.md"),
    )

    recent_entry = JournalEntry(
        quest_id="recent-001",
        slug="recent-quest",
        title="Recent Quest",
        elevator_pitch="Recent.",
        status="Completed",
        completed_date=date(2026, 2, 15),
        journal_path=Path("docs/quest-journal/recent.md"),
    )

    data = DashboardData(
        finished_quests=[old_entry, recent_entry],
        active_quests=[],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Recent quest should appear before old quest
    recent_pos = result.index("Recent Quest")
    old_pos = result.index("Old Quest")
    assert recent_pos < old_pos


def test_card_badge_text_finished(tmp_path):
    """Completed quests show FINISHED badge text."""
    entry = JournalEntry(
        quest_id="test-001",
        slug="test-quest",
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

    result = render_dashboard(data, output_path, repo_root)

    assert "FINISHED" in result
    # Should not show raw "Completed" in badge
    assert 'badge--finished">Completed<' not in result


def test_unknown_status_badge(tmp_path):
    """Quest with unrecognized status gets badge--unknown class."""
    quest = ActiveQuest(
        quest_id="mystery-001",
        slug="mystery-quest",
        title="Mystery Quest",
        elevator_pitch="Mystery.",
        status="SomethingWeird",
        phase="Unknown",
        updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
    )

    data = DashboardData(
        finished_quests=[],
        active_quests=[quest],
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    assert "badge--unknown" in result
    assert "UNKNOWN" in result


def test_doughnut_chart_counts_unknown_separately(tmp_path):
    """Doughnut chart counts unknown-status quests in Unknown, not In Progress.

    Regression test for bug where unknown_count was hardcoded to 0 and
    unknowns were silently merged into in_progress_count.
    """
    active_quests = [
        ActiveQuest(
            quest_id="normal-001",
            slug="normal",
            title="Normal Quest",
            elevator_pitch="Normal.",
            status="In Progress",
            phase="Building",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        ),
        ActiveQuest(
            quest_id="blocked-001",
            slug="blocked",
            title="Blocked Quest",
            elevator_pitch="Blocked.",
            status="Blocked",
            phase="Building",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        ),
        ActiveQuest(
            quest_id="mystery-001",
            slug="mystery",
            title="Mystery Quest",
            elevator_pitch="Mystery.",
            status="SomethingWeird",
            phase="Unknown",
            updated_at=datetime(2026, 2, 12, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    data = DashboardData(
        finished_quests=[],
        active_quests=active_quests,
        abandoned_quests=[],
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    repo_root = tmp_path

    result = render_dashboard(data, output_path, repo_root)

    # Doughnut data array: [in_progress, blocked, abandoned, finished, unknown]
    # Expected: [1, 1, 0, 0, 1] -- not [2, 1, 0, 0, 0]
    assert "data: [1, 1, 0, 0, 1]" in result
