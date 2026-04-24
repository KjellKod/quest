"""Quest artifact path helpers for runtime-neutral orchestration."""

from __future__ import annotations

from pathlib import Path

ROLE_ARTIFACTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "planner": ("phase_01_plan", ("plan.md", "handoff.json")),
    "plan-reviewer-a": (
        "phase_01_plan",
        ("review_plan-reviewer-a.md", "handoff_plan-reviewer-a.json"),
    ),
    "plan-reviewer-b": (
        "phase_01_plan",
        ("review_plan-reviewer-b.md", "handoff_plan-reviewer-b.json"),
    ),
    "arbiter": (
        "phase_01_plan",
        (
            "arbiter_verdict.md.next",
            "review_findings.json.next",
            "handoff_arbiter.json",
        ),
    ),
    "builder": (
        "phase_02_implementation",
        ("pr_description.md", "builder_feedback_discussion.md", "handoff.json"),
    ),
    "code-reviewer-a": (
        "phase_03_review",
        (
            "review_code-reviewer-a.md",
            "review_findings_code-reviewer-a.json",
            "handoff_code-reviewer-a.json",
        ),
    ),
    "code-reviewer-b": (
        "phase_03_review",
        (
            "review_code-reviewer-b.md",
            "review_findings_code-reviewer-b.json",
            "handoff_code-reviewer-b.json",
        ),
    ),
    "fixer": (
        "phase_03_review",
        ("review_fix_feedback_discussion.md", "handoff_fixer.json"),
    ),
}

SOLO_DISABLED_AGENTS = frozenset({"plan-reviewer-b", "code-reviewer-b", "arbiter"})

ROLE_PHASE_ALIASES: dict[str, frozenset[str]] = {
    "planner": frozenset({"plan"}),
    "plan-reviewer-a": frozenset({"plan_review"}),
    "plan-reviewer-b": frozenset({"plan_review"}),
    "arbiter": frozenset({"plan_review"}),
    "builder": frozenset({"build", "building", "implementation"}),
    "code-reviewer-a": frozenset({"code_review", "review", "reviewing"}),
    "code-reviewer-b": frozenset({"code_review", "review", "reviewing"}),
    "fixer": frozenset({"fix", "fixing"}),
}


def default_quest_dir(workspace_root: str | Path, quest_id: str) -> Path:
    """Return the default repo-local quest directory for a run."""

    return Path(workspace_root).resolve() / ".quest" / quest_id


def expected_artifacts_for_role(
    quest_dir: str | Path,
    phase: str,
    agent: str,
    quest_mode: str = "workflow",
) -> list[Path]:
    """Return absolute artifact paths for the requested role invocation."""

    normalized_agent = agent.strip()
    if quest_mode == "solo" and normalized_agent in SOLO_DISABLED_AGENTS:
        return []

    try:
        phase_dir, filenames = ROLE_ARTIFACTS[normalized_agent]
    except KeyError as exc:
        raise ValueError(f"Unsupported quest role: {agent}") from exc

    normalized_phase = phase.strip().lower().replace("-", "_")
    allowed_phases = ROLE_PHASE_ALIASES[normalized_agent]
    if normalized_phase not in allowed_phases:
        allowed = ", ".join(sorted(allowed_phases))
        raise ValueError(
            f"Quest role {agent} is not valid for phase {phase!r}. Allowed: {allowed}"
        )

    base_dir = Path(quest_dir).resolve() / phase_dir
    return [base_dir / filename for filename in filenames]


def prepare_artifact_files(paths: list[Path]) -> list[Path]:
    """Create or truncate the provided artifact files."""

    prepared: list[Path] = []
    for path in paths:
        resolved = Path(path).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text("", encoding="utf-8")
        prepared.append(resolved)
    return prepared


def is_workspace_local(path: Path, workspace_root: Path) -> bool:
    """Return True when the path resolves under the workspace root."""

    try:
        Path(path).resolve().relative_to(Path(workspace_root).resolve())
    except ValueError:
        return False
    return True


def check_artifact_paths(
    paths: list[Path],
    workspace_root: Path,
) -> tuple[list[Path], list[Path]]:
    """Partition artifact paths into workspace-local and external buckets."""

    local_paths: list[Path] = []
    external_paths: list[Path] = []
    for path in paths:
        resolved = Path(path).resolve()
        if is_workspace_local(resolved, workspace_root):
            local_paths.append(resolved)
        else:
            external_paths.append(resolved)
    return local_paths, external_paths


def any_artifact_missing_or_empty(paths: list[Path]) -> bool:
    """Return True when any expected artifact is missing or still empty."""

    for path in paths:
        resolved = Path(path).resolve()
        if not resolved.exists():
            return True
        if resolved.stat().st_size == 0:
            return True
    return False
