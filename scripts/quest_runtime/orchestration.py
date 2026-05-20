"""Per-quest orchestration config helpers.

The chooser in `.skills/quest/SKILL.md` Step 3 sub-step 8.5 produces a
`.quest/<id>/orchestration.json` file that pins each role to a specific model
for the active quest. This module owns the small bits of logic that benefit
from being concrete (parsing the override line, writing the JSON file, the
resume migration) so they can be unit-tested.

The chooser itself remains markdown prose for an orchestrator LLM; this helper
just encodes the contract that prose describes. Keep this file and SKILL.md
§8.5 in sync.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Canonical role list. Order matters for display; the validator/parser uses
# membership only. Keep in sync with workflow.md dispatch sites and the
# validate_orchestration_json helper in scripts/quest_validate-quest-state.sh.
CANONICAL_ROLES: tuple[str, ...] = (
    "planner",
    "plan-reviewer-a",
    "plan-reviewer-b",
    "arbiter",
    "builder",
    "code-reviewer-a",
    "code-reviewer-b",
    "fixer",
)

# Roles that may legitimately be unused (and therefore null) in solo mode.
SOLO_UNUSED_ROLES: frozenset[str] = frozenset(
    {"plan-reviewer-b", "code-reviewer-b", "arbiter"}
)

ORCHESTRATION_VERSION = 1


class OverrideParseError(ValueError):
    """Raised when an override-line submission is malformed."""


@dataclass(frozen=True)
class Override:
    """A single validated role=model override entry."""

    role: str
    model: str


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with second precision and trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_override_line(line: str) -> list[Override]:
    """Parse a comma-separated `role=model` line.

    Contract (mirrors SKILL.md §8.5):
    - Split on commas, trim each piece. Empty pieces are silently skipped
      (a trailing comma is fine).
    - Each non-empty piece must contain exactly one `=`. Zero or two-or-more
      `=` characters raise OverrideParseError.
    - Role names are trimmed, lowercased, and matched against CANONICAL_ROLES.
      Unknown roles raise OverrideParseError.
    - Model names are trimmed. Lexeme is `[^,=]+` non-empty. No further
      character constraints (so `gpt-5.5`, `claude-opus-4.7`, `o1-mini`
      all pass parsing).
    """
    pieces = [piece.strip() for piece in line.split(",")]
    parsed: list[Override] = []
    for piece in pieces:
        if not piece:
            # Empty piece — silently skip (trailing comma case).
            continue
        equals_count = piece.count("=")
        if equals_count != 1:
            raise OverrideParseError(
                f"Override syntax error: {piece!r} (expected role=model). "
                "Re-enter overrides."
            )
        raw_role, raw_model = piece.split("=", 1)
        role = raw_role.strip().lower()
        model = raw_model.strip()
        if role not in CANONICAL_ROLES:
            valid_list = ", ".join(CANONICAL_ROLES)
            raise OverrideParseError(
                f"Unknown role: {raw_role.strip()} (valid: {valid_list})"
            )
        if not model:
            raise OverrideParseError(
                f"Override syntax error: {piece!r} (expected role=model). "
                "Re-enter overrides."
            )
        parsed.append(Override(role=role, model=model))
    return parsed


def is_model_available(model: str, *, codex_available: bool) -> bool:
    """Return True if the requested model can run with the current preflight.

    `claude` is always allowed. Any other model name requires Codex MCP to be
    available per the preflight cache. This is the contract from SKILL.md
    §8.5 step 6.
    """
    if model == "claude":
        return True
    return codex_available


def load_codex_available_from_cache(cache_path: Path) -> bool:
    """Read a Codex-availability preflight cache.

    Claude-led preflight writes top-level `available`; Codex-led bridge probing
    may write `payload.available`. Only a literal JSON boolean true is accepted.
    Callers may want to also enforce the preflight TTL — that is left to the
    orchestrator since it knows when the quest started.
    """
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("available") is True:
        return True
    payload = data.get("payload")
    if isinstance(payload, dict):
        return payload.get("available") is True
    return False


def build_default_models(allowlist_models: dict[str, str | None]) -> dict[str, str | None]:
    """Return a fresh copy of an allowlist `models` block with all 8 keys.

    Missing keys are filled with None so the schema stays shape-stable. This
    matches the validator's expectation that all 8 keys are always present.
    """
    return {role: allowlist_models.get(role) for role in CANONICAL_ROLES}


def apply_overrides(
    defaults: dict[str, str | None],
    overrides: Iterable[Override],
    *,
    quest_mode: str,
) -> tuple[dict[str, str | None], list[str], list[str]]:
    """Overlay validated overrides on top of the defaults.

    Returns (merged_models, overridden_roles, ignored_unused_roles).
    Overrides on roles that are unused in the active mode are skipped and
    surfaced separately so the orchestrator can warn the user.
    """
    merged = dict(defaults)
    overridden: list[str] = []
    ignored_unused: list[str] = []
    for override in overrides:
        if quest_mode == "solo" and override.role in SOLO_UNUSED_ROLES:
            ignored_unused.append(override.role)
            continue
        merged[override.role] = override.model
        if override.role not in overridden:
            overridden.append(override.role)
    return merged, overridden, ignored_unused


def write_orchestration_json(
    path: Path,
    *,
    models: dict[str, str | None],
    source: str,
    overridden_roles: list[str],
    preflight_validated_at: str | None = None,
) -> None:
    """Write the orchestration.json artifact with canonical key order."""
    if source not in {"default", "overridden"}:
        raise ValueError(
            f"source must be 'default' or 'overridden' (got {source!r})"
        )
    payload = {
        "version": ORCHESTRATION_VERSION,
        "models": {role: models.get(role) for role in CANONICAL_ROLES},
        "source": source,
        "overridden_roles": list(overridden_roles),
        "preflight_validated_at": preflight_validated_at or _now_iso(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_default_from_allowlist(
    orchestration_path: Path,
    allowlist_models: dict[str, str | None],
    *,
    preflight_validated_at: str | None = None,
) -> None:
    """Default-path writer: copy allowlist models into orchestration.json."""
    defaults = build_default_models(allowlist_models)
    write_orchestration_json(
        orchestration_path,
        models=defaults,
        source="default",
        overridden_roles=[],
        preflight_validated_at=preflight_validated_at,
    )


def migrate_from_snapshot(
    quest_dir: Path,
    *,
    preflight_validated_at: str | None = None,
) -> bool:
    """Resume migration: copy snapshot models into orchestration.json.

    Returns True if a new orchestration.json was written, False if the file
    already existed (in which case it is left untouched per SKILL.md Step 1
    sub-step 1a — `Never prompt the chooser on resume`).
    """
    orch_path = quest_dir / "orchestration.json"
    if orch_path.exists():
        return False
    snapshot_path = quest_dir / "logs" / "allowlist_snapshot.json"
    try:
        with snapshot_path.open("r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except OSError as exc:
        raise ValueError(f"Snapshot not readable at {snapshot_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Snapshot at {snapshot_path} is not valid JSON") from exc
    if not isinstance(snapshot, dict):
        raise ValueError(f"Snapshot at {snapshot_path} must be a JSON object")
    models = snapshot.get("models")
    if not isinstance(models, dict):
        raise ValueError(
            f"Snapshot at {snapshot_path} does not contain a 'models' object"
        )
    write_orchestration_json(
        orch_path,
        models=build_default_models(models),
        source="default",
        overridden_roles=[],
        preflight_validated_at=preflight_validated_at,
    )
    return True
