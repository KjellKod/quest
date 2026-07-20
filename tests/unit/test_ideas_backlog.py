import re
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[2]
IDEAS_DIR = REPO_ROOT / "ideas"
INDEX_PATH = IDEAS_DIR / "README.md"
DIAMOND_PATH = (
    REPO_ROOT / "docs/implementation/backlog/quest-diamond-efficiency-roadmap.md"
)
OLD_DIAMOND_PATH = REPO_ROOT / "docs/implementation/quest-diamond-efficiency-roadmap.md"
OLD_IDEAS_DIAMOND_PATH = IDEAS_DIR / "quest-diamond-efficiency-roadmap.md"
CI_ROADMAP_PATH = IDEAS_DIR / "2026-05-04-ci-review-allowlist-quality-roadmap.md"
CELEBRATION_PATH = (
    IDEAS_DIR / "2026-04-17-persisted-celebrations-and-brief-in-cheers.md"
)
ORCHESTRATION_ARCHIVE_PATH = (
    IDEAS_DIR / "archive/2026-05-18-per-quest-orchestration-override.md"
)
CODE_REVIEW_ARCHIVE_PATH = IDEAS_DIR / "archive/2026-05-30-code-review-adjudication.md"
ORCHESTRATION_JOURNAL_PATH = (
    REPO_ROOT / "docs/quest-journal/orchestration-override_2026-05-18.md"
)
NATIVE_RUNTIME_ARCHIVE_PATH = (
    IDEAS_DIR / "archive/2026-05-26-native-runtime-dispatch.md"
)

CHANGED_PLANNING_PATHS = (
    INDEX_PATH,
    DIAMOND_PATH,
    IDEAS_DIR / "quest-policy-canonicalization-and-enforcement-roadmap.md",
    IDEAS_DIR / "2026-04-13-instruction-architecture.md",
    CI_ROADMAP_PATH,
    IDEAS_DIR / "quest-multi-phase-execution.md",
    CELEBRATION_PATH,
    ORCHESTRATION_ARCHIVE_PATH,
    CODE_REVIEW_ARCHIVE_PATH,
    ORCHESTRATION_JOURNAL_PATH,
    NATIVE_RUNTIME_ARCHIVE_PATH,
)

PERMITTED_DIAMOND_STATUSES = {
    "done",
    "partial",
    "proposed",
    "blocked",
    "superseded",
}


def _section(text: str, start: str, end: str | None = None) -> str:
    section = text.split(start, 1)[1]
    if end:
        parts = section.split(end, 1)
        assert len(parts) > 1, f"end delimiter {end!r} not found after {start!r}"
        section = parts[0]
    return section


def _table_target(cell: str) -> str | None:
    link = re.search(r"\[[^]]+\]\(([^)]+)\)", cell)
    if link:
        return link.group(1)
    code = re.search(r"`([^`]+)`", cell)
    return code.group(1) if code else None


def _active_rows(index_text: str) -> list[tuple[str, str]]:
    active = _section(index_text, "## Active Index", "### Graduated")
    rows: list[tuple[str, str]] = []
    for line in active.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"File", "---"}:
            continue
        target = _table_target(cells[0])
        if target:
            rows.append((target, cells[1]))
    return rows


def _done_identifiers(index_text: str) -> set[str]:
    done = _section(index_text, "### Done Index", "## Hygiene Rules")
    return {
        match.group(1).removesuffix(".md")
        for match in re.finditer(r"~~([^~]+)~~", done)
    }


def _identifier(target: str) -> str:
    return Path(target).stem


def _relative_markdown_links(path: Path) -> list[str]:
    links = re.findall(r"(?<!!)\[[^]]*\]\(([^)]+)\)", path.read_text())
    return [
        unquote(link.split("#", 1)[0])
        for link in links
        if link
        and not link.startswith(("#", "http://", "https://", "mailto:"))
        and "<" not in link
        and ">" not in link
    ]


def test_active_ideas_exist_do_not_duplicate_done_and_record_status_evidence():
    index = INDEX_PATH.read_text()
    active_rows = _active_rows(index)
    active_ids = [_identifier(target) for target, _ in active_rows]
    done_ids = _done_identifiers(index)

    assert len(active_ids) == len(set(active_ids))
    assert not set(active_ids) & done_ids
    assert all((IDEAS_DIR / target).is_file() for target, _ in active_rows)

    celebration_rows = [
        status
        for target, status in active_rows
        if _identifier(target)
        == "2026-04-17-persisted-celebrations-and-brief-in-cheers"
    ]
    assert celebration_rows == ["partial"]
    celebration = CELEBRATION_PATH.read_text()
    assert "## Status: partial" in celebration
    assert "PR [#112]" in celebration
    assert "### Unshipped Or Unresolved" in celebration
    assert "overwrite/regeneration" in celebration
    assert "origin` and revision metadata" in celebration
    assert "Allowlist and ownership-list completion" in celebration

    orchestration = ORCHESTRATION_ARCHIVE_PATH.read_text()
    assert "status: done" in orchestration
    assert "PR\n[#119]" in orchestration
    assert "[#144]" in orchestration
    assert "requires a new evidence-backed proposal" in orchestration
    assert (
        "../../docs/quest-journal/orchestration-override_2026-05-18.md" in orchestration
    )
    assert "2026-05-18-per-quest-orchestration-override" in done_ids

    code_review = CODE_REVIEW_ARCHIVE_PATH.read_text()
    assert (
        "../../docs/quest-journal/code-review-adjudication_2026-05-30.md" in code_review
    )


def test_ci_quality_superseded_ideas_are_not_active():
    index = INDEX_PATH.read_text()
    active_ids = {_identifier(target) for target, _ in _active_rows(index)}
    superseded_section = _section(
        CI_ROADMAP_PATH.read_text(),
        "## Superseded Idea Docs",
        "Keep these archived docs",
    )
    superseded_ids = {
        Path(path).stem
        for path in re.findall(r"`ideas/archive/([^`]+)`", superseded_section)
    }

    assert superseded_ids
    assert not active_ids & superseded_ids


def test_changed_idea_document_links_resolve():
    missing: list[str] = []
    for path in CHANGED_PLANNING_PATHS:
        for target in _relative_markdown_links(path):
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {target}")

    assert missing == []

    stale_path = "ideas/2026-05-18-per-quest-orchestration-override.md"
    stale_references = [
        path.relative_to(REPO_ROOT).as_posix()
        for directory in (REPO_ROOT / "docs", IDEAS_DIR)
        for path in directory.rglob("*.md")
        if stale_path in path.read_text()
    ]
    assert stale_references == []


def test_diamond_roadmap_records_current_state_safe_topology_and_location():
    assert DIAMOND_PATH.is_file()
    assert not OLD_DIAMOND_PATH.exists()
    assert not OLD_IDEAS_DIAMOND_PATH.exists()
    diamond = DIAMOND_PATH.read_text()

    assert "Refreshed: 2026-07-20" in diamond
    for status in PERMITTED_DIAMOND_STATUSES:
        assert f"- `{status}`:" in diamond

    rows = {}
    for line in diamond.splitlines():
        match = re.match(r"\| (WP\d+) [^|]*\| ([^|]+) \|", line)
        if match:
            package, status_cell = match.groups()
            status_tokens = PERMITTED_DIAMOND_STATUSES & set(status_cell.split())
            assert len(status_tokens) == 1, f"{package} has statuses {status_tokens}"
            assert package not in rows
            rows[package] = status_tokens.pop()

    assert rows == {
        "WP0": "proposed",
        "WP1": "partial",
        "WP2": "proposed",
        "WP3": "partial",
        "WP4": "partial",
        "WP5": "proposed",
        "WP6": "proposed",
        "WP7": "done",
        "WP8": "partial",
        "WP9": "blocked",
    }
    assert "WP0 is the" in diamond
    assert "only recommended next implementation slice" in diamond
    wp9 = _section(diamond, "## WP9: Benchmark Comparison", "## Integration")
    for heading in (
        "### Unblock Conditions",
        "### Acceptance Criteria",
        "### Automated Validation",
        "### Manual Validation",
    ):
        assert heading in wp9

    prohibited = (
        "Fable 5",
        "claude-fable-5",
        "GPT-5.5",
        "1,476",
        "auto_pr",
        "standing approval",
        "WP PR-to-integration-branch",
    )
    assert all(term not in diamond for term in prohibited)
    assert "ideas/2026-05-31-quest-model-capability-improvements.md" not in diamond
    assert "one bounded Quest and PR" in diamond
    assert "No persistent integration branch is required" in diamond

    wp5 = _section(diamond, "## WP5: Planning Lessons", "## WP6")
    assert (
        "[Memory architecture](../../../ideas/2026-04-13-quest-memory-architecture.md)"
        in wp5
    )
    assert (
        "[Memory evaluation loop](../../../ideas/2026-04-13-quest-memory-evaluation-loop.md)"
        in wp5
    )
    assert "canonical owners" in wp5
    assert "Diamond owns only package sequencing and efficiency measurement" in wp5


def test_source_only_backlog_surfaces_are_not_consumer_owned():
    manifest = (REPO_ROOT / ".quest-manifest").read_text()
    checksums = (REPO_ROOT / ".quest-checksums").read_text()
    source_only_paths = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (*CHANGED_PLANNING_PATHS, Path(__file__).resolve())
    }
    source_only_paths.add("docs/implementation/quest-diamond-efficiency-roadmap.md")

    for path in source_only_paths:
        assert path not in manifest
        assert path not in checksums
