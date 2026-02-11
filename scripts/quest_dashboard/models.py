from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path


UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class ActiveQuestRecord:
    quest_id: str
    slug: str
    name: str
    status: str
    phase: str
    updated_at: datetime
    elevator_pitch: str
    state_path: Path = field(repr=False)
    brief_path: Path | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class CompletedQuestRecord:
    quest_id: str
    name: str
    status: str
    updated_on: date
    elevator_pitch: str
    journal_path: Path
    source_path: Path = field(repr=False)


@dataclass(frozen=True, slots=True)
class DashboardData:
    active_quests: list[ActiveQuestRecord]
    completed_quests: list[CompletedQuestRecord]
    warnings: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
