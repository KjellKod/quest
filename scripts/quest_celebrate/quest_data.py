"""Deep artifact reader for quest directories.

Extracts rich structured data from quest artifacts: state.json, handoff*.json,
quest_brief.md, plan.md, and review*.md files. All reads are wrapped in
try/except for graceful degradation -- missing or malformed files produce
empty defaults, never crashes.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class AgentInfo:
    """Information about an agent that participated in the quest."""

    name: str  # e.g. "plan-reviewer-a"
    model: str  # e.g. "opencode/gpt-5.3-codex"
    role_title: str  # e.g. "The Plan Reviewer"
    summary: str  # from handoff summary field
    phase: str  # e.g. "Planning"


@dataclass
class Achievement:
    """A dynamically generated achievement badge."""

    icon: str  # emoji or safe-mode text
    title: str  # e.g. "Gremlin Slayer"
    description: str  # e.g. "Fixed 3 review issues"
    attribution: str = ""  # e.g. "Codex" or "KiMi K2.5"


@dataclass
class QuestData:
    """Rich structured data extracted from a quest directory."""

    # Metadata from state.json
    quest_id: str = ""
    slug: str = ""
    name: str = "Unknown Quest"
    phase: str = ""
    status: str = ""
    quest_mode: str = ""  # "workflow", "solo", or "" (legacy/unknown)
    plan_iterations: int = 0
    fix_iterations: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # From quest_brief.md
    brief_summary: str = ""

    # From plan.md
    plan_summary: str = ""

    # From handoff*.json files
    agents: List[AgentInfo] = field(default_factory=list)

    # From review*.md files
    review_findings: List[str] = field(default_factory=list)
    review_count: int = 0

    # Computed
    files_changed: List[str] = field(default_factory=list)
    pr_number: Optional[int] = None
    achievements: List[Achievement] = field(default_factory=list)
    quality_score: int = 0
    quality_tier: str = (
        ""  # Diamond/Platinum/Gold/Silver/Bronze/Tin/Cardboard/Abandoned
    )
    test_count: Optional[int] = None
    tests_added: Optional[int] = None


# Mapping from agent name patterns to cinematic role titles
_ROLE_TITLE_MAP = {
    "plan-reviewer-a": "The A Plan Critic",
    "plan-reviewer-b": "The B Plan Critic",
    "code-reviewer-a": "The A Code Critic",
    "code-reviewer-b": "The B Code Critic",
    "planner": "The Architect",
    "plan-reviewer": "The Plan Critic",
    "builder": "The Implementer",
    "code-reviewer": "The Code Critic",
    "fixer": "The Bug Slayer",
    "arbiter": "The Judge",
}


def _load_allowlist_quality_defaults() -> Tuple[int, int, int]:
    """Read live allowlist overrides for active quests.

    Historical journal replay should not depend on the current repo config.
    Callers that need reproducible replay should use the static module defaults
    or persisted quest-local values instead of this helper.
    """
    repo_root = Path(__file__).resolve().parents[2]
    allowlist_path = repo_root / ".ai" / "allowlist.json"
    max_plan_iterations = 4
    max_fix_iterations = 3
    solo_max_fix_iterations = 2
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (
            max_plan_iterations,
            max_fix_iterations,
            solo_max_fix_iterations,
        )

    gates = data.get("gates", {})
    if (
        type(gates.get("max_plan_iterations")) is int
        and gates["max_plan_iterations"] >= 1
    ):
        max_plan_iterations = gates["max_plan_iterations"]
    if (
        type(gates.get("max_fix_iterations")) is int
        and gates["max_fix_iterations"] >= 1
    ):
        max_fix_iterations = gates["max_fix_iterations"]

    solo = data.get("solo", {})
    if type(solo.get("max_fix_iterations")) is int and solo["max_fix_iterations"] >= 1:
        solo_max_fix_iterations = solo["max_fix_iterations"]

    return (
        max_plan_iterations,
        max_fix_iterations,
        solo_max_fix_iterations,
    )


def _map_agent_role_title(agent_name: str) -> str:
    """Map an agent name to a cinematic role title."""
    lower = agent_name.lower()

    # Exact matches first (handles A/B critic labels)
    if lower in _ROLE_TITLE_MAP:
        return _ROLE_TITLE_MAP[lower]

    for pattern, title in _ROLE_TITLE_MAP.items():
        if pattern in lower:
            return title
    return agent_name.replace("-", " ").title()


def _phase_from_path(rel_path: str) -> str:
    """Infer a phase label from a relative path within the quest directory."""
    lower = rel_path.lower()
    if "phase_01" in lower or "plan" in lower:
        return "Planning"
    if "phase_02" in lower or "implement" in lower or "build" in lower:
        return "Building"
    if "phase_03" in lower or "review" in lower:
        return "Review"
    return "Unknown"


def _read_state_json(quest_dir: Path) -> dict:
    """Parse state.json, returning empty dict on failure."""
    state_path = quest_dir / "state.json"
    if not state_path.exists():
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _read_quest_brief(quest_dir: Path) -> Tuple[str, str]:
    """Extract name and summary from quest_brief.md.

    Returns (name, summary). Falls back to empty strings.
    """
    brief_path = quest_dir / "quest_brief.md"
    if not brief_path.exists():
        return "", ""
    try:
        text = brief_path.read_text(encoding="utf-8")
    except IOError:
        return "", ""

    name = ""
    # Try "# Quest Brief: <title>"
    title_match = re.search(r"^#\s+Quest Brief:\s*(.+)$", text, re.MULTILINE)
    if title_match:
        name = title_match.group(1).strip()
    else:
        # Fall back to first heading
        heading_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if heading_match:
            name = heading_match.group(1).strip()

    # Extract summary: look for "## User Input" section, or first paragraph
    summary = ""
    user_input_match = re.search(
        r"## User Input\s*\n+(.+?)(?:\n\n|\n##|\Z)", text, re.DOTALL
    )
    if user_input_match:
        summary = user_input_match.group(1).strip()
    else:
        # First non-heading paragraph
        para_match = re.search(r"\n\n([^#\n].+?)(?:\n\n|\Z)", text, re.DOTALL)
        if para_match:
            summary = para_match.group(1).strip()

    # Truncate summary to first ~200 chars for display
    if len(summary) > 200:
        summary = summary[:197] + "..."

    return name, summary


def _read_plan_summary(quest_dir: Path) -> str:
    """Extract overview from phase_01_plan/plan.md."""
    plan_path = quest_dir / "phase_01_plan" / "plan.md"
    if not plan_path.exists():
        return ""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except IOError:
        return ""

    # Look for ## Overview section
    overview_match = re.search(r"## Overview\s*\n+(.+?)(?:\n##|\Z)", text, re.DOTALL)
    if overview_match:
        summary = overview_match.group(1).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."
        return summary

    # Fall back to first paragraph after the title
    para_match = re.search(r"\n\n([^#\n].+?)(?:\n\n|\Z)", text, re.DOTALL)
    if para_match:
        summary = para_match.group(1).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."
        return summary

    return ""


def _collect_handoff_data(quest_dir: Path) -> Tuple[List[AgentInfo], List[str]]:
    """Glob all handoff*.json, extract agent info and artifact paths.

    Returns (agents, files_changed).
    """
    agents: List[AgentInfo] = []
    files_changed: List[str] = []

    handoff_files = sorted(quest_dir.glob("**/handoff*.json"))
    for handoff_path in handoff_files:
        try:
            with open(handoff_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        agent_name = data.get("agent", "")
        model = data.get("model", "")
        summary = data.get("summary", "")

        # Determine phase from file path
        try:
            rel = str(handoff_path.relative_to(quest_dir))
        except ValueError:
            rel = str(handoff_path)
        phase = _phase_from_path(rel)

        if agent_name:
            agents.append(
                AgentInfo(
                    name=agent_name,
                    model=model,
                    role_title=_map_agent_role_title(agent_name),
                    summary=summary,
                    phase=phase,
                )
            )

        # Collect artifact paths
        for artifact in data.get("artifacts", []):
            if artifact not in files_changed:
                files_changed.append(artifact)

    if agents:
        return agents, files_changed

    # Legacy fallback for older quests without handoff JSON artifacts.
    # Infer participant models/roles from markdown artifact filenames.
    def infer_model_from_name(name: str) -> str:
        lower = name.lower()
        if "kimi" in lower:
            return "moonshotai/kimi-k2.5"
        if "codex" in lower or "gpt" in lower:
            return "openai/gpt-5.3-codex"
        if "claude" in lower or "opus" in lower:
            return "anthropic/claude-opus"
        return ""

    def add_legacy_agent(name: str, model: str, phase: str, summary: str = "") -> None:
        if not name:
            return

        for existing in agents:
            if existing.name != name:
                continue

            # Same role already captured with same model -> skip duplicate.
            if existing.model == model:
                return

            # Prefer model-bearing entries over empty-model placeholders.
            if not existing.model and model:
                existing.model = model
                return

            # If existing already has a model and new one doesn't, skip.
            if existing.model and not model:
                return

        agents.append(
            AgentInfo(
                name=name,
                model=model,
                role_title=_map_agent_role_title(name),
                summary=summary,
                phase=phase,
            )
        )

    legacy_markdown = sorted(quest_dir.glob("**/*.md"))
    for md_path in legacy_markdown:
        rel = str(md_path.relative_to(quest_dir)).lower()
        file_name = md_path.name.lower()
        model = infer_model_from_name(file_name)
        phase = _phase_from_path(rel)

        if "phase_01_plan" in rel and "review_" in file_name:
            if "claude" in file_name:
                role = "plan-reviewer-a"
            elif "codex" in file_name or "gpt" in file_name:
                role = "plan-reviewer-b"
            else:
                continue
            add_legacy_agent(role, model, phase)
        elif "phase_01_plan" in rel and "arbiter" in file_name:
            add_legacy_agent("arbiter", model, phase)
        elif "phase_02_implementation" in rel and "builder" in file_name:
            add_legacy_agent("builder", model, phase)
        elif "phase_03_review" in rel and "review_" in file_name:
            if "claude" in file_name:
                role = "code-reviewer-a"
            elif "codex" in file_name or "gpt" in file_name:
                role = "code-reviewer-b"
            else:
                continue
            add_legacy_agent(role, model, phase)
        elif "phase_03_review" in rel and "fix" in file_name:
            add_legacy_agent("fixer", model, phase)

    return agents, files_changed


def _collect_review_findings(quest_dir: Path) -> Tuple[List[str], int]:
    """Glob review*.md files, extract key findings.

    Returns (findings, review_count).
    """
    findings: List[str] = []
    review_files = sorted(quest_dir.glob("**/review*.md"))
    review_count = len(review_files)

    for review_path in review_files:
        try:
            text = review_path.read_text(encoding="utf-8")
        except IOError:
            continue

        # Look for bullet points that mention issues, findings, or fixes
        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith(("- ", "* ")):
                continue
            lower = line.lower()
            if any(
                keyword in lower
                for keyword in ("issue", "finding", "fix", "bug", "problem", "concern")
            ):
                # Clean up the bullet
                finding = line.lstrip("-* ").strip()
                if finding and finding not in findings:
                    findings.append(finding)

    return findings, review_count


def _find_pr_number(
    quest_dir: Path, state: dict, agents: List[AgentInfo]
) -> Optional[int]:
    """Search for PR number across multiple sources."""
    # 1. state.json
    pr = state.get("pr_number")
    if pr is not None:
        try:
            return int(pr)
        except (ValueError, TypeError):
            pass

    # 2. pr_description.md -- look for PR URL or number
    pr_desc_path = quest_dir / "phase_02_implementation" / "pr_description.md"
    if pr_desc_path.exists():
        try:
            text = pr_desc_path.read_text(encoding="utf-8")
            # Most specific: GitHub pull URL
            url_match = re.search(r"/pull/(\d+)", text)
            if url_match:
                return int(url_match.group(1))
            # Next: explicit PR reference (avoids matching markdown headings)
            pr_match = re.search(r"(?:PR|pull request)\s*#(\d+)", text, re.IGNORECASE)
            if pr_match:
                return int(pr_match.group(1))
            # Fallback: bare #N only on lines that don't start with markdown heading markers
            for line in text.split("\n"):
                if line.lstrip().startswith("#"):
                    continue  # skip markdown headings
                bare_match = re.search(r"#(\d+)", line)
                if bare_match:
                    return int(bare_match.group(1))
        except IOError:
            pass

    # 3. Handoff artifacts mentioning PR
    for agent in agents:
        pr_match = re.search(r"PR\s*#?(\d+)", agent.summary)
        if pr_match:
            return int(pr_match.group(1))

    return None


def _compute_achievements(data: QuestData) -> List[Achievement]:
    """Generate achievements based on quest stats."""
    achievements: List[Achievement] = []

    def models_for_role(*role_keywords: str) -> str:
        """Get unique friendly model labels for agents matching role keywords."""
        labels: List[str] = []
        seen = set()
        for agent in data.agents:
            name = agent.name.lower()
            if not any(keyword in name for keyword in role_keywords):
                continue
            label = friendly_model_name(agent.model)
            if label and label not in seen:
                seen.add(label)
                labels.append(label)
        return " + ".join(labels)

    def models_for_all() -> str:
        labels: List[str] = []
        seen = set()
        for agent in data.agents:
            label = friendly_model_name(agent.model)
            if label and label not in seen:
                seen.add(label)
                labels.append(label)
        return " + ".join(labels)

    if data.review_count > 0 and len(data.review_findings) > 0:
        achievements.append(
            Achievement(
                icon="[BUG]",
                title="Gremlin Slayer",
                description=f"Tackled {len(data.review_findings)} review findings",
                attribution=(
                    models_for_role("fixer")
                    or models_for_role("builder")
                    or models_for_role("reviewer")
                ),
            )
        )

    if data.review_count > 0:
        achievements.append(
            Achievement(
                icon="[TEST]",
                title="Battle Tested",
                description=f"Survived {data.review_count} reviews",
                attribution=models_for_role("reviewer"),
            )
        )

    if data.pr_number is not None:
        achievements.append(
            Achievement(
                icon="[SHIP]",
                title="Ship It",
                description=f"PR #{data.pr_number} created",
                attribution=models_for_role("builder"),
            )
        )

    if data.plan_iterations > 1:
        achievements.append(
            Achievement(
                icon="[PLAN]",
                title="Plan Perfectionist",
                description=f"Iterated plan {data.plan_iterations} times",
                attribution=models_for_role("planner", "plan-reviewer"),
            )
        )

    if len(data.agents) >= 4:
        achievements.append(
            Achievement(
                icon="[TEAM]",
                title="Full Squad",
                description=f"{len(data.agents)} agents collaborated",
                attribution=models_for_all(),
            )
        )

    if data.quest_mode == "solo":
        achievements.append(
            Achievement(
                icon="[SOLO]",
                title="Solo Adventurer",
                description="Completed quest with a single companion",
                attribution=models_for_role("reviewer", "plan-reviewer"),
            )
        )

    if data.status == "complete":
        achievements.append(
            Achievement(
                icon="[WIN]",
                title="Quest Complete",
                description="All phases finished successfully",
                attribution=models_for_all(),
            )
        )

    return achievements


def _compute_quality_score(data: QuestData) -> int:
    """Compute quality score (0-100) from review data.

    Scoring:
    - Base 50 for a complete quest
    - +20 if reviews exist (shows rigor)
    - +15 if findings were addressed (review_findings > 0 means issues were found and tracked)
    - +10 if plan_iterations <= 1 (efficient planning)
    - +5 if fix_iterations <= 1 (clean implementation)
    - -10 per extra plan iteration beyond 2
    - -5 per extra fix iteration beyond 2
    """
    score = 0

    if data.status == "complete":
        score += 50

    if data.review_count > 0:
        score += 20

    if len(data.review_findings) > 0:
        score += 15

    if data.plan_iterations <= 1:
        score += 10
    elif data.plan_iterations > 2:
        score -= 10 * (data.plan_iterations - 2)

    if data.fix_iterations <= 1:
        score += 5
    elif data.fix_iterations > 2:
        score -= 5 * (data.fix_iterations - 2)

    return max(0, min(100, score))


# Quality tier definitions: name, icon, grade, tooltip
QUALITY_TIERS = {
    "Diamond": ("💎", "A+", "Flawless — zero issues, shipped clean"),
    "Platinum": ("🏆", "A", "Near-perfect — minor issues, one-pass fix"),
    "Gold": ("🥇", "B", "Solid — issues caught, fixed cleanly"),
    "Silver": ("🥈", "C", "Workable — multiple iterations but landed"),
    "Bronze": ("🥉", "D", "Rough ride — got through, bruised"),
    "Tin": ("🥫", "D-", "Dented — 3+ iterations, plan revisions"),
    "Cardboard": ("📦", "F", "Held together with tape. Still shipped."),
    "Abandoned": ("💀", "Inc", "Never shipped — lessons learned"),
}

# Static defaults used for replay and as fallbacks when quest-local settings
# are unavailable.
_DEFAULT_MAX_PLAN_ITERATIONS = 4
_DEFAULT_MAX_FIX_ITERATIONS = 3
_DEFAULT_SOLO_MAX_FIX_ITERATIONS = 2


def _validated_quality_tier(value: object) -> str:
    """Return a known tier string or empty string for invalid input."""
    return value if isinstance(value, str) and value in QUALITY_TIERS else ""


def compute_quality_tier(
    plan_iterations: int,
    fix_iterations: int,
    review_findings_count: int,
    status: str,
    max_plan_iterations: int = _DEFAULT_MAX_PLAN_ITERATIONS,
    max_fix_iterations: int = _DEFAULT_MAX_FIX_ITERATIONS,
    quest_mode: str = "",
    solo_max_fix_iterations: int = _DEFAULT_SOLO_MAX_FIX_ITERATIONS,
) -> str:
    """Compute a named quality tier from quest iteration data.

    The tier is candid: smooth quests get top tiers, rough quests get
    honest lower tiers. Every tier that isn't Abandoned still shipped.

    Returns one of: Diamond, Platinum, Gold, Silver, Bronze, Tin,
    Cardboard, Abandoned.
    """
    if status == "abandoned":
        return "Abandoned"

    effective_max_fix_iterations = max_fix_iterations
    if quest_mode == "solo":
        effective_max_fix_iterations = min(max_fix_iterations, solo_max_fix_iterations)

    # Check from worst to best so max-gate check uses strict equality

    # Cardboard: hit or exceeded max iteration gates
    at_plan_max = plan_iterations >= max_plan_iterations
    at_fix_max = fix_iterations >= effective_max_fix_iterations
    if at_plan_max and at_fix_max:
        return "Cardboard"

    # Tin: high iterations (approaching gates but not both maxed)
    if (
        plan_iterations >= max_plan_iterations
        or fix_iterations >= effective_max_fix_iterations
    ):
        return "Tin"

    # Bronze: 3+ on either axis (below gate thresholds)
    if plan_iterations >= 3 or fix_iterations >= 3:
        return "Bronze"

    # Silver: fix_iterations == 2
    if fix_iterations == 2:
        return "Silver"

    # Gold: plan > 1 but fix == 1 (needed replanning but fixed cleanly)
    if fix_iterations == 1 and plan_iterations > 1:
        return "Gold"

    # Diamond: plan <= 1, fix == 0, zero review issues — flawless
    if plan_iterations <= 1 and fix_iterations == 0 and review_findings_count == 0:
        tier = "Diamond"
    # Platinum: plan <= 1, fix <= 1 — near-perfect (issues found or one fix pass)
    elif plan_iterations <= 1 and fix_iterations <= 1:
        tier = "Platinum"
    else:
        tier = "Gold"

    return tier


def friendly_model_name(model: str) -> str:
    """Normalize raw model IDs to readable display names.

    Shared utility used by celebrate, dashboard, and ascii_art modules.

    Examples:
        "claude-opus-4-6" -> "Claude Opus"
        "gpt-5.3-codex" -> "Codex"
        "kimi-k2.5" -> "KiMi K2.5"
    """
    if not model:
        return ""
    lower = model.lower()
    if "kimi" in lower:
        return "KiMi K2.5"
    if "opus" in lower or "claude" in lower:
        return "Claude Opus"
    if "codex" in lower or "gpt-" in lower:
        return "Codex"
    return model.split("/")[-1]


def extract_celebration_data_from_journal(content: str) -> Optional[dict]:
    """Extract celebration_data JSON block from a journal markdown file.

    Looks for content between <!-- celebration-data-start --> and
    <!-- celebration-data-end --> markers, then parses the JSON code
    block within.

    Returns parsed dict or None if not found/malformed.
    """
    match = re.search(
        r"<!--\s*celebration-data-start\s*-->\s*```json\s*\n(.*?)\n\s*```\s*\n\s*<!--\s*celebration-data-end\s*-->",
        content,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_metadata(content: str, key: str) -> str:
    """Extract journal metadata from bold, list-item, or plain formats."""
    patterns = [
        rf"\*\*{re.escape(key)}:\s*\*\*\s*(.+?)(?:\n|$)",
        rf"\*\*{re.escape(key)}\*\*\s*:\s*(.+?)(?:\n|$)",
        rf"^\s*[-*]\s*{re.escape(key)}:\s*`?(.+?)`?\s*$",
        rf"^\s*{re.escape(key)}:\s*`?(.+?)`?\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip().strip("`")
    return ""


def _extract_journal_title(content: str) -> str:
    """Extract a journal title from supported heading formats."""
    for pattern in (
        r"^#\s+Quest Journal:\s*(.+?)$",
        r"^#\s+Quest:\s*(.+?)$",
        r"^#\s+(.+?)$",
    ):
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_dict_items(value: object) -> list[dict]:
    """Return only dict entries from a list-like JSON field."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def load_quest_data_from_journal(journal_path: Path) -> QuestData:
    """Load quest data from a journal markdown file.

    Extracts the embedded celebration_data JSON block if present.
    Falls back to parsing the markdown text for basic metadata.
    """
    data = QuestData()

    if not journal_path.exists():
        return data

    try:
        content = journal_path.read_text(encoding="utf-8")
    except IOError:
        return data

    # Try to extract structured celebration data
    celebration = extract_celebration_data_from_journal(content)
    if celebration:
        # Populate from structured JSON
        data.quest_mode = celebration.get("quest_mode", "")
        quality = celebration.get("quality", {})
        if isinstance(quality, dict):
            data.quality_tier = _validated_quality_tier(quality.get("tier"))
        data.test_count = celebration.get("test_count")
        data.tests_added = celebration.get("tests_added")

        for agent_dict in _extract_dict_items(celebration.get("agents")):
            data.agents.append(
                AgentInfo(
                    name=agent_dict.get("name", ""),
                    model=agent_dict.get("model", ""),
                    role_title=agent_dict.get("role", ""),
                    summary="",
                    phase="",
                )
            )

        for ach_dict in _extract_dict_items(celebration.get("achievements")):
            data.achievements.append(
                Achievement(
                    icon=ach_dict.get("icon", "⭐️"),
                    title=ach_dict.get("title", ""),
                    description=ach_dict.get("desc", ""),
                )
            )

        quote = celebration.get("quote", {})
        if isinstance(quote, dict) and quote:
            data.brief_summary = (
                f'{quote.get("text", "")} — {quote.get("attribution", "")}'
            )

        victory_narrative = celebration.get("victory_narrative")
        if isinstance(victory_narrative, str):
            data.plan_summary = victory_narrative

    # Extract basic metadata from markdown (always, for fields not in JSON)
    if not data.quest_mode:
        raw_mode = _extract_metadata(content, "quest mode")
        if raw_mode:
            data.quest_mode = raw_mode.lower()

    data.quest_id = _extract_metadata(content, "quest id")
    if data.quest_id:
        parts = data.quest_id.split("_")
        if parts:
            data.slug = parts[0]

    # Title from heading
    title = _extract_journal_title(content)
    if title:
        data.name = title

    # Iterations
    plan_match = re.search(
        r"(?:\*\*)?[Pp]lan\s+iterations:\s*(?:\*\*)?\s*(\d+)", content
    )
    parsed_plan_iterations = False
    if plan_match:
        data.plan_iterations = int(plan_match.group(1))
        parsed_plan_iterations = True

    fix_match = re.search(r"(?:\*\*)?[Ff]ix\s+iterations:\s*(?:\*\*)?\s*(\d+)", content)
    parsed_fix_iterations = False
    if fix_match:
        data.fix_iterations = int(fix_match.group(1))
        parsed_fix_iterations = True

    # Status
    raw_status = _extract_metadata(content, "status")
    if raw_status:
        raw = raw_status.lower()
        if raw.startswith("abandon"):
            data.status = "abandoned"
        else:
            data.status = "complete"
    else:
        data.status = "complete"

    # Compute quality tier if not already set from celebration data
    if not data.quality_tier and parsed_plan_iterations and parsed_fix_iterations:
        data.quality_tier = compute_quality_tier(
            data.plan_iterations,
            data.fix_iterations,
            len(data.review_findings),
            data.status,
            quest_mode=data.quest_mode,
        )

    # Compute quality score for backward compatibility
    data.quality_score = _compute_quality_score(data)

    return data


def load_quest_data(quest_dir: Path) -> QuestData:
    """Load rich quest data from a quest directory.

    Main entry point. Reads all artifacts and computes derived fields.
    Handles missing/malformed files gracefully.
    """
    data = QuestData()

    if not quest_dir.exists():
        return data

    # 1. state.json
    state = _read_state_json(quest_dir)
    data.quest_id = state.get("quest_id", "")
    data.slug = state.get("slug", "")
    data.phase = state.get("phase", "")
    data.status = state.get("status", "")
    data.quest_mode = state.get("quest_mode", "")
    data.plan_iterations = state.get("plan_iteration", 0)
    data.fix_iterations = state.get("fix_iteration", 0)
    data.created_at = state.get("created_at")
    data.updated_at = state.get("updated_at")

    # Derive name from quest_id if needed
    if data.quest_id:
        parts = data.quest_id.split("_")
        if parts:
            data.name = parts[0].replace("-", " ").title()

    # 2. quest_brief.md
    brief_name, brief_summary = _read_quest_brief(quest_dir)
    if brief_name:
        data.name = brief_name
    data.brief_summary = brief_summary

    # 3. plan.md
    data.plan_summary = _read_plan_summary(quest_dir)

    # 4. handoff*.json
    data.agents, data.files_changed = _collect_handoff_data(quest_dir)

    # 5. review*.md
    data.review_findings, data.review_count = _collect_review_findings(quest_dir)

    # 6. PR number
    data.pr_number = _find_pr_number(quest_dir, state, data.agents)

    # 7. Computed fields
    data.achievements = _compute_achievements(data)
    data.quality_score = _compute_quality_score(data)
    (
        max_plan_iterations,
        max_fix_iterations,
        solo_max_fix_iterations,
    ) = _load_allowlist_quality_defaults()
    data.quality_tier = compute_quality_tier(
        data.plan_iterations,
        data.fix_iterations,
        len(data.review_findings),
        data.status,
        max_plan_iterations=max_plan_iterations,
        max_fix_iterations=max_fix_iterations,
        quest_mode=data.quest_mode,
        solo_max_fix_iterations=solo_max_fix_iterations,
    )

    return data
