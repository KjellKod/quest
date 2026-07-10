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
    "review-arbiter",
    "fixer",
)

DEFAULT_MODELS: dict[str, str] = {
    "planner": "claude",
    "plan-reviewer-a": "claude",
    "plan-reviewer-b": "gpt-5.5",
    "arbiter": "claude",
    "builder": "gpt-5.5",
    "code-reviewer-a": "claude",
    "code-reviewer-b": "gpt-5.5",
    "review-arbiter": "claude",
    "fixer": "gpt-5.5",
}

# Roles added after early snapshots/existing orchestration files were already
# written. These keys may be backfilled from DEFAULT_MODELS during resume.
LEGACY_COMPAT_BACKFILL_ROLES: frozenset[str] = frozenset({"review-arbiter"})

# Roles that may legitimately be unused (and therefore null) in solo mode.
SOLO_UNUSED_ROLES: frozenset[str] = frozenset(
    {"plan-reviewer-b", "code-reviewer-b", "arbiter", "review-arbiter"}
)

ORCHESTRATION_VERSION = 1
CODEX_NATIVE_FALLBACK_MODEL = "gpt-5.5"

# Transport for Codex-led Claude roles (.ai/allowlist.json claude_role_transport).
# "auto" resolves to background-agent when the preflight bg probe succeeds.
# If it fails, Quest asks the user; bridge is an explicit API-metered opt-in.
CLAUDE_ROLE_TRANSPORTS: tuple[str, ...] = ("auto", "background-agent", "bridge")
DEFAULT_CLAUDE_ROLE_TRANSPORT = "auto"


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


def is_claude_model(model: str) -> bool:
    """Return True for model names that run on the Claude runtime."""
    return model == "claude" or model.startswith("claude-")


def runtime_for_model(model: str) -> str:
    """Map a persisted `models.<role>` model ID to its runtime family.

    `models.*` stores model IDs (for example `claude`, `claude-opus-4-6`,
    `gpt-5.5`), not runtime names. The Quest contract is binary: Claude-family
    IDs run on the Claude runtime; every other ID runs on Codex tooling.
    Provider-qualified IDs (for example `opencode/claude-opus-4-6`) are
    classified on the segment after the final `/`.
    """
    normalized = model.strip().lower()
    if not normalized:
        raise ValueError("model must be a non-empty string")
    unqualified = normalized.rsplit("/", 1)[-1]
    if not unqualified:
        raise ValueError(f"model ID has no name after provider prefix: {model!r}")
    return "claude" if is_claude_model(unqualified) else "codex"


def is_model_available(model: str, *, codex_available: bool) -> bool:
    """Return True if the requested model can run with the current preflight.

    Backward-compatible wrapper for Claude-led availability checks.
    """
    return is_model_available_for_orchestrator(
        model,
        orchestrator="claude",
        codex_available=codex_available,
        claude_available=True,
    )


def is_model_available_for_orchestrator(
    model: str,
    *,
    orchestrator: str,
    codex_available: bool,
    claude_available: bool,
) -> bool:
    """Return True if the model can run in the active orchestrator session."""
    normalized_orchestrator = orchestrator.strip().lower()
    if normalized_orchestrator not in {"claude", "codex"}:
        raise ValueError(f"Unknown orchestrator: {orchestrator!r}")
    # Classify through the same canonical mapping dispatch uses, so
    # provider-qualified IDs (opencode/claude-*) gate consistently.
    model_runtime = runtime_for_model(model)
    if normalized_orchestrator == "claude":
        return True if model_runtime == "claude" else codex_available
    return claude_available if model_runtime == "claude" else True


def active_roles_for_mode(quest_mode: str) -> tuple[str, ...]:
    """Return roles that are actually dispatched for the selected quest mode."""
    if quest_mode == "solo":
        return tuple(role for role in CANONICAL_ROLES if role not in SOLO_UNUSED_ROLES)
    return CANONICAL_ROLES


def validate_or_remap_models_for_orchestrator(
    models: dict[str, str | None],
    *,
    orchestrator: str,
    codex_available: bool,
    claude_available: bool,
    quest_mode: str,
    remap_unavailable: bool = False,
) -> tuple[dict[str, str | None], list[str]]:
    """Validate active role models against the preflight result.

    When a user explicitly continues with a single-model quest after preflight
    reports the second runtime unavailable, the chooser can remap active
    unavailable roles to the current orchestrator's native model before writing
    orchestration.json. Otherwise, unavailable active role models are rejected.
    """
    normalized_orchestrator = orchestrator.strip().lower()
    if normalized_orchestrator not in {"claude", "codex"}:
        raise ValueError(f"Unknown orchestrator: {orchestrator!r}")

    result = dict(models)
    fallback_model = (
        "claude" if normalized_orchestrator == "claude" else CODEX_NATIVE_FALLBACK_MODEL
    )
    remapped_roles: list[str] = []
    unavailable_roles: list[str] = []

    for role in active_roles_for_mode(quest_mode):
        model = result.get(role)
        if not isinstance(model, str) or not model:
            # An unset/empty model on an ACTIVE role is unavailable by
            # definition — remap or reject now instead of persisting config
            # that can only fail later at dispatch time.
            if remap_unavailable:
                result[role] = fallback_model
                remapped_roles.append(role)
            else:
                unavailable_roles.append(role)
            continue
        if is_model_available_for_orchestrator(
            model,
            orchestrator=normalized_orchestrator,
            codex_available=codex_available,
            claude_available=claude_available,
        ):
            continue
        if remap_unavailable:
            result[role] = fallback_model
            remapped_roles.append(role)
        else:
            unavailable_roles.append(role)

    if unavailable_roles:
        raise ValueError(
            "Unavailable model for active role(s): " + ", ".join(unavailable_roles)
        )

    return result, remapped_roles


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
    """Return a fresh copy of an allowlist `models` block with all 9 keys.

    Missing keys are filled from the documented workflow defaults so older or
    customized allowlists that omit a role do not write unusable null entries.
    Explicit null values are preserved for compatibility with legacy snapshots.
    """
    return {
        role: allowlist_models[role] if role in allowlist_models else DEFAULT_MODELS[role]
        for role in CANONICAL_ROLES
    }


def _backfill_legacy_compatible_roles(
    models: dict[str, str | None],
) -> tuple[dict[str, str | None], list[str]]:
    """Backfill known legacy-compatible missing roles with defaults."""
    merged = dict(models)
    backfilled: list[str] = []
    for role in CANONICAL_ROLES:
        if role in merged:
            continue
        if role in LEGACY_COMPAT_BACKFILL_ROLES:
            merged[role] = DEFAULT_MODELS[role]
            backfilled.append(role)
    return merged, backfilled


def build_snapshot_models(snapshot_models: dict[str, str | None]) -> dict[str, str | None]:
    """Return a shape-stable model block from a saved snapshot.

    Unlike fresh allowlist defaults, resume migration stays fail-closed for
    genuinely missing roles. The only exception is explicitly legacy-compatible
    role introductions listed in LEGACY_COMPAT_BACKFILL_ROLES.
    """
    merged, _ = _backfill_legacy_compatible_roles(snapshot_models)
    missing = [role for role in CANONICAL_ROLES if role not in merged]
    if missing:
        raise ValueError(
            "Snapshot models missing required role(s): " + ", ".join(missing)
        )
    return {role: merged.get(role) for role in CANONICAL_ROLES}


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
    claude_role_transport: str = DEFAULT_CLAUDE_ROLE_TRANSPORT,
    claude_transport_resolved: str | None = None,
) -> None:
    """Write the orchestration.json artifact with canonical key order."""
    if source not in {"default", "overridden"}:
        raise ValueError(
            f"source must be 'default' or 'overridden' (got {source!r})"
        )
    if claude_role_transport not in CLAUDE_ROLE_TRANSPORTS:
        raise ValueError(
            f"claude_role_transport must be one of {CLAUDE_ROLE_TRANSPORTS} "
            f"(got {claude_role_transport!r})"
        )
    payload = {
        "version": ORCHESTRATION_VERSION,
        "models": {role: models.get(role) for role in CANONICAL_ROLES},
        "claude_role_transport": claude_role_transport,
        "claude_transport_resolved": claude_transport_resolved,
        # Compatibility field for consumers created during the downgrade era.
        # New auto runs block for user choice instead of downgrading.
        "claude_transport_downgraded": False,
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
    orchestrator: str | None = None,
    codex_available: bool = True,
    claude_available: bool = True,
    quest_mode: str = "workflow",
    remap_unavailable: bool = False,
    claude_role_transport: str = DEFAULT_CLAUDE_ROLE_TRANSPORT,
    claude_transport_resolved: str | None = None,
) -> None:
    """Default-path writer: copy allowlist models into orchestration.json."""
    defaults = build_default_models(allowlist_models)
    if orchestrator is not None:
        defaults, _ = validate_or_remap_models_for_orchestrator(
            defaults,
            orchestrator=orchestrator,
            codex_available=codex_available,
            claude_available=claude_available,
            quest_mode=quest_mode,
            remap_unavailable=remap_unavailable,
        )
    write_orchestration_json(
        orchestration_path,
        models=defaults,
        source="default",
        overridden_roles=[],
        preflight_validated_at=preflight_validated_at,
        claude_role_transport=claude_role_transport,
        claude_transport_resolved=claude_transport_resolved,
    )


def migrate_from_snapshot(
    quest_dir: Path,
    *,
    preflight_validated_at: str | None = None,
) -> bool:
    """Resume migration: copy snapshot models into orchestration.json.

    Returns True if orchestration.json was written or legacy-backfilled.
    Existing files are preserved unless they are missing known
    legacy-compatible role introductions.
    """
    orch_path = quest_dir / "orchestration.json"
    if orch_path.exists():
        try:
            with orch_path.open("r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(existing, dict):
            return False
        existing_models = existing.get("models")
        if not isinstance(existing_models, dict):
            return False
        merged_models, backfilled = _backfill_legacy_compatible_roles(existing_models)
        # Transport keys were introduced after early quests; backfill in place
        # (same legacy-compat contract as newly-introduced roles).
        transport_backfilled = False
        if "claude_role_transport" not in existing:
            # Absent: legacy file predating the transport key — backfill the default.
            existing["claude_role_transport"] = DEFAULT_CLAUDE_ROLE_TRANSPORT
            transport_backfilled = True
        elif existing["claude_role_transport"] not in CLAUDE_ROLE_TRANSPORTS:
            # Present but invalid: a mistyped/forced transport must fail closed,
            # never be silently coerced to "auto" (that would resume under a
            # different transport than the per-quest config demanded).
            raise ValueError(
                "orchestration.json has an invalid claude_role_transport "
                f"{existing['claude_role_transport']!r}; expected one of "
                f"{CLAUDE_ROLE_TRANSPORTS}. Fix or remove the key — resume will "
                "not coerce a forced transport."
            )
        if "claude_transport_resolved" not in existing:
            existing["claude_transport_resolved"] = None
            transport_backfilled = True
        if "claude_transport_downgraded" not in existing:
            existing["claude_transport_downgraded"] = False
            transport_backfilled = True
        if not backfilled and not transport_backfilled:
            return False
        # Fail closed BEFORE writing: a role missing from the merged models
        # would be written as null and rejected by the very validation this
        # migration feeds — never persist a file we know is invalid.
        missing_roles = [
            role for role in CANONICAL_ROLES if not merged_models.get(role)
        ]
        if missing_roles:
            raise ValueError(
                "orchestration.json migration would write null model(s) for "
                f"role(s) {missing_roles}; the existing file is malformed — "
                "fix models.<role> entries before resuming."
            )
        existing["models"] = {
            role: merged_models.get(role) for role in CANONICAL_ROLES
        }
        if not isinstance(existing.get("preflight_validated_at"), str) or not existing.get(
            "preflight_validated_at"
        ):
            existing["preflight_validated_at"] = preflight_validated_at or _now_iso()
        with orch_path.open("w", encoding="utf-8") as handle:
            json.dump(existing, handle, indent=2)
            handle.write("\n")
        return True
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
        models=build_snapshot_models(models),
        source="default",
        overridden_roles=[],
        preflight_validated_at=preflight_validated_at,
    )
    return True
