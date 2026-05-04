"""Persist rendered Quest celebrations as journal artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from quest_celebrate.ascii_art import ansi_shadow_title, render_quality_score
from quest_celebrate.quest_data import QUALITY_TIERS, QuestData, friendly_model_name


@dataclass(frozen=True)
class CelebrationWriteResult:
    """Result of attempting to write a persisted celebration file."""

    path: Path
    rel_path: Path
    created: bool
    message: str


def celebration_filename(slug: str, completion_date: date) -> str:
    """Return the persisted celebration filename for a quest."""
    return f"{slug}_{completion_date.isoformat()}.md"


def celebration_rel_path(slug: str, completion_date: date) -> Path:
    """Return a journal-relative celebration path."""
    return Path("celebrations") / celebration_filename(slug, completion_date)


def extract_what_started_this(data: QuestData) -> str:
    """Extract a concise problem/impact section from the quest brief."""
    source = (data.brief_body or data.brief_summary or "").strip()
    if not source:
        return ""

    problem = _extract_labeled_paragraph(source, "problem")
    impact = _extract_labeled_paragraph(source, "impact")
    if problem:
        parts = [problem]
        if impact:
            parts.append(impact)
        return "\n\n".join(parts)

    return _first_useful_paragraph(source)


def select_quest_quote(data: QuestData) -> tuple[str, str] | None:
    """Return ``(quote_text, attribution)`` from the best available artifact."""
    priority = ("arbiter", "code-reviewer", "fixer", "builder", "planner")
    for role in priority:
        for agent in data.agents:
            summary = agent.summary or ""
            if role in agent.name.lower() and summary.strip():
                attribution = agent.role_title or agent.name
                return _single_line(summary), attribution

    for finding in data.review_findings:
        if finding.strip():
            return _single_line(finding), "Review finding"

    return None


def render_persisted_celebration(
    data: QuestData,
    completion_date: date,
    journal_rel_path: Path,
) -> str:
    """Render a deterministic full celebration markdown artifact."""
    slug = data.slug or data.quest_id or "quest"
    title = data.name or slug.replace("-", " ").title()
    quality_tier = data.quality_tier or "Unknown"
    journal_ref = Path("..") / journal_rel_path.name

    lines: list[str] = [
        f"<!-- quest-id: {data.quest_id} -->",
        "<!-- style: celebration -->",
        f"<!-- quality-tier: {quality_tier} -->",
        f"<!-- date: {completion_date.isoformat()} -->",
        f"<!-- journal: {journal_ref.as_posix()} -->",
        "<!-- origin: step7-original -->",
        "",
        f"# Quest Celebration: {title}",
        "",
        "```text",
    ]

    lines.append(_render_title_art(title))
    lines.extend(["```", "", "---", ""])

    what_started = extract_what_started_this(data)
    if what_started:
        lines.extend(["## What Started This", "", what_started, ""])

    if data.agents:
        lines.extend(["## Starring Cast", ""])
        for agent in data.agents:
            model = friendly_model_name(agent.model)
            label = f" [{model}]" if model else ""
            lines.append(f"- **{agent.name}{label}** ........ {agent.role_title}")
        lines.append("")

    if data.achievements:
        lines.extend(["## Achievements", ""])
        for achievement in data.achievements:
            lines.append(
                f"- {achievement.icon} **{achievement.title}** — {achievement.description}"
            )
        lines.append("")

    lines.extend(
        [
            "## Impact Metrics",
            "",
            f"- Review findings addressed: **{len(data.review_findings)}**",
            f"- Review rounds completed: **{data.review_count}**",
            f"- Plan iterations: **{data.plan_iterations}**",
            f"- Fix iterations: **{data.fix_iterations}**",
        ]
    )
    if data.test_count is not None:
        test_line = f"- Tests: **{data.test_count}**"
        if data.tests_added is not None:
            test_line += f" ({data.tests_added} new)"
        lines.append(test_line)
    if data.pr_number is not None:
        lines.append(f"- PR: **#{data.pr_number}**")
    lines.append("")

    lines.extend(["## Handoff & Reliability", ""])
    lines.extend(f"- {line}" for line in _reliability_lines(data))
    lines.append("")

    lines.extend(_carryover_lines(data))

    tier_icon = QUALITY_TIERS.get(quality_tier, ("", "", ""))[0]
    quality_title = f"{tier_icon} Quality Tier: {quality_tier}".strip()
    lines.extend(["## " + quality_title, "", render_quality_score(data.quality_score)])

    quote = select_quest_quote(data)
    lines.extend(["", "## Quest Quote", ""])
    if quote:
        quote_text, attribution = quote
        lines.extend([f'> "{quote_text}"', ">", f"> — {attribution}", ""])
    else:
        lines.extend(["No artifact-backed quote was available for this quest.", ""])

    lines.extend(
        [
            "## Victory Narrative",
            "",
            _victory_narrative(data),
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def write_celebration_file(
    journal_dir: Path,
    data: QuestData,
    completion_date: date,
    journal_rel_path: Path,
) -> CelebrationWriteResult:
    """Write a celebration file unless the target already exists."""
    rel_path = celebration_rel_path(data.slug or data.quest_id, completion_date)
    target = journal_dir / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        return CelebrationWriteResult(
            path=target,
            rel_path=rel_path,
            created=False,
            message=f"Celebration already exists; not overwritten: {target}",
        )

    target.write_text(
        render_persisted_celebration(data, completion_date, journal_rel_path),
        encoding="utf-8",
    )
    return CelebrationWriteResult(
        path=target,
        rel_path=rel_path,
        created=True,
        message=f"Celebration created: {target}",
    )


def _extract_labeled_paragraph(source: str, label: str) -> str:
    pattern = rf"(?i)^\s*(?:[*_]*{label}[*_]*\s*:|[*_]*{label}[*_]*\s+-)\s*(.*)$"
    source_lines = source.splitlines()
    match_index: int | None = None
    first = ""
    for index, line in enumerate(source_lines):
        match = re.match(pattern, line)
        if match:
            match_index = index
            first = _clean_markdown_line(match.group(1))
            break
    if match_index is None:
        return ""

    extra: list[str] = []
    lines = source_lines[match_index + 1 :]
    for line in lines:
        stripped = line.strip()
        if not stripped and (first or extra):
            break
        if not stripped:
            continue
        if re.match(r"^(?:[*_]*[A-Za-z][A-Za-z -]{1,40}[*_]*\s*:|##+)\s*", stripped):
            break
        extra.append(_clean_markdown_line(stripped))
    return _single_line(" ".join([first, *extra]))


def _render_title_art(title: str) -> str:
    """Render a complete title as readable celebration word blocks."""
    return ansi_shadow_title(title, max_width=70)


def _first_useful_paragraph(source: str) -> str:
    paragraph: list[str] = []
    in_code = False
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped or stripped.startswith("#"):
            if paragraph:
                break
            continue
        if stripped.startswith("<!--"):
            continue
        paragraph.append(_clean_markdown_line(stripped))
    return _single_line(" ".join(paragraph))


def _clean_markdown_line(line: str) -> str:
    cleaned = re.sub(r"^\s*>\s?", "", line.strip())
    cleaned = re.sub(r"^[-*]\s+", "", cleaned)
    cleaned = cleaned.strip("`")
    return cleaned


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _reliability_lines(data: QuestData) -> list[str]:
    reviewer_handoffs = len(
        [agent for agent in data.agents if "reviewer" in agent.name.lower()]
    )
    fixer_handoffs = len(
        [agent for agent in data.agents if "fixer" in agent.name.lower()]
    )
    reliability = "high"
    if data.plan_iterations > 2 or data.fix_iterations > 1:
        reliability = "medium"
    if data.fix_iterations > 2:
        reliability = "recovering"
    return [
        f"Handoffs parsed: {len(data.agents)}",
        f"Reviewer handoffs: {reviewer_handoffs}",
        f"Fixer handoffs: {fixer_handoffs}",
        f"Review findings tracked: {len(data.review_findings)}",
        f"Reliability signal: {reliability}",
    ]


def _carryover_lines(data: QuestData) -> list[str]:
    inherited = data.inherited_findings_used
    future = data.findings_left_for_future_quests
    if inherited.count <= 0 and future.count <= 0:
        return [
            "## Carry-Over Findings",
            "",
            "- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.",
            "",
        ]

    lines: list[str] = []
    for title, carryover in (
        ("Inherited Findings Used", inherited),
        ("Findings Left For Future Quests", future),
    ):
        if carryover.count <= 0:
            continue
        lines.extend([f"## {title}", "", f"- Count: **{carryover.count}**"])
        lines.extend(f"- {summary}" for summary in carryover.summaries[:3])
        lines.append("")
    return lines


def _victory_narrative(data: QuestData) -> str:
    full_brief_summary = extract_what_started_this(data)
    summary = full_brief_summary or data.plan_summary or data.brief_summary
    if summary:
        opening = _single_line(re.sub(r"(?m)^\s*>\s?", "", summary))
        if opening.endswith("...") and full_brief_summary:
            opening = _single_line(full_brief_summary)
        return (
            f"{opening} The quest finished with {data.plan_iterations} plan "
            f"iteration(s), {data.fix_iterations} fix loop(s), and a persisted "
            "celebration artifact that future readers can open directly from the journal."
        )
    return (
        f"This quest completed with {data.plan_iterations} plan iteration(s), "
        f"{data.fix_iterations} fix loop(s), and a persisted celebration artifact "
        "that future readers can open directly from the journal."
    )
