"""Data models for the Quest Dashboard.

This module defines frozen dataclasses representing:
- JournalEntry: A completed or abandoned quest from docs/quest-journal/*.md
- ActiveQuest: An in-progress quest from .quest/*/state.json
- DashboardData: The complete dashboard model with all three status groups
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A completed or abandoned quest from docs/quest-journal/*.md."""

    quest_id: str
    slug: str
    title: str
    elevator_pitch: str
    status: str  # "Completed" or "Abandoned"
    completed_date: date
    journal_path: Path  # Relative to repo root
    pr_number: int | None = None
    plan_iterations: int | None = None
    fix_iterations: int | None = None


@dataclass(frozen=True, slots=True)
class ActiveQuest:
    """An in-progress quest from .quest/*/state.json."""

    quest_id: str
    slug: str
    title: str
    elevator_pitch: str
    status: str  # Display label: "In Progress", "Blocked", etc.
    phase: str  # Display label: "Building", "Plan", etc.
    updated_at: datetime
    plan_iterations: int | None = None
    fix_iterations: int | None = None


@dataclass(frozen=True, slots=True)
class DashboardData:
    """Complete dashboard data with pre-grouped quests."""

    finished_quests: list[JournalEntry]  # status == "Completed"
    active_quests: list[ActiveQuest]
    abandoned_quests: list[JournalEntry]  # status == "Abandoned"
    warnings: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    github_repo_url: str = ""
