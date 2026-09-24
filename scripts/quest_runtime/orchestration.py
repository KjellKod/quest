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
import re
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

# BEGIN GENERATED MODEL DEFAULTS (edit .ai/allowlist.json, then run scripts/quest_sync_model_defaults.py)
DEFAULT_MODELS: dict[str, str] = {
    "planner": "gpt-6-astra",
    "plan-reviewer-a": "claude-opus-5-5",
    "plan-reviewer-b": "gpt-6-astra",
    "arbiter": "claude-opus-5-5",
    "builder": "gpt-5.6-sol",
    "code-reviewer-a": "claude-opus-5-5",
    "code-reviewer-b": "gpt-6-astra",
    "review-arbiter": "claude-opus-5-5",
    "fixer": "gpt-6-astra",
}
DEFAULT_EFFORT: dict[str, str] = {
    "planner": "medium",
    "plan-reviewer-a": "medium",
    "plan-reviewer-b": "medium",
    "arbiter": "medium",
    "builder": "medium",
    "code-reviewer-a": "medium",
    "code-reviewer-b": "medium",
    "review-arbiter": "medium",
    "fixer": "medium",
}
CODEX_NATIVE_FALLBACK_MODEL = "gpt-6-astra"
# END GENERATED MODEL DEFAULTS

# Roles added after early snapshots/existing orchestration files were already
# written. These keys may be backfilled from DEFAULT_MODELS during resume.
LEGACY_COMPAT_BACKFILL_ROLES: frozenset[str] = frozenset({"review-arbiter"})

# Roles that may legitimately be unused (and therefore null) in solo mode.
SOLO_UNUSED_ROLES: frozenset[str] = frozenset(
    {"plan-reviewer-b", "code-reviewer-b", "arbiter", "review-arbiter"}
)

ORCHESTRATION_VERSION = 1

# Reasoning-effort levels (.ai/allowlist.json effort). The union is the syntax
# vocabulary for the per-role map; `ultra` is Codex-only, so the Claude CLI
# subset excludes it and the Claude runner rejects it at dispatch.
EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max", "ultra")
CLAUDE_EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")

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


class _JsonObjectPairs(list[tuple[str, object]]):
    """Preserve JSON object order and duplicate keys at the input boundary."""


def _validated_override(raw_role: object, raw_model: object) -> Override:
    """Validate one role/model pair shared by both accepted syntaxes."""
    if not isinstance(raw_role, str):
        raise OverrideParseError(
            "Override role names must be strings. Re-enter overrides."
        )
    role = raw_role.strip().lower()
    if role not in CANONICAL_ROLES:
        valid_list = ", ".join(CANONICAL_ROLES)
        raise OverrideParseError(
            f"Unknown role: {raw_role.strip()} (valid: {valid_list})"
        )
    if not isinstance(raw_model, str) or not raw_model.strip():
        raise OverrideParseError(
            f"Override model for {role} must be a non-empty string. "
            "Re-enter overrides."
        )
    model = raw_model.strip()
    if "," in model or "=" in model or "\n" in model or "\r" in model:
        raise OverrideParseError(
            f"Override model for {role} cannot contain ',', '=', or line breaks. "
            "Re-enter overrides."
        )
    return Override(role=role, model=model)


def _append_unique_override(
    parsed: list[Override], seen_roles: set[str], override: Override
) -> None:
    """Append one override, rejecting ambiguous case-normalized duplicates."""
    if override.role in seen_roles:
        raise OverrideParseError(
            f"Duplicate role: {override.role}. Re-enter overrides."
        )
    seen_roles.add(override.role)
    parsed.append(override)


def parse_override_input(text: str) -> list[Override]:
    """Parse JSON or comma- or newline-separated `role=model` overrides.

    Contract (mirrors SKILL.md §8.5):
    - JSON input may be a direct role map, a top-level `models` object, or the
      copied `"models": {...}` fragment without outer braces.
    - JSON role names and model values use the same validation as pairs.
    - Split pair input on commas, LF, or CRLF; trim each piece. Empty pieces
      are silently skipped (trailing separators and blank lines are fine).
    - Each non-empty piece must contain exactly one `=`. Zero or two-or-more
      `=` characters raise OverrideParseError.
    - Role names are trimmed, lowercased, and matched against CANONICAL_ROLES.
      Unknown roles raise OverrideParseError.
    - Model names are trimmed and cannot contain commas, equals signs, or line
      breaks (so `codex-fake-model`, `claude-fake-model`, `gemini-fake-model` all pass parsing).
    """
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith('"models"'):
        candidate = (
            "{" + stripped + "}" if stripped.startswith('"models"') else stripped
        )
        try:
            data = json.loads(candidate, object_pairs_hook=_JsonObjectPairs)
        except json.JSONDecodeError as exc:
            raise OverrideParseError(
                f"Override JSON syntax error: {exc.msg}. Re-enter overrides."
            ) from exc
        if not isinstance(data, _JsonObjectPairs):
            raise OverrideParseError(
                "Override JSON must be an object. Re-enter overrides."
            )
        models_values = [value for key, value in data if key == "models"]
        if models_values:
            if len(data) != 1:
                raise OverrideParseError(
                    "Override JSON with a models block cannot contain other top-level keys. "
                    "Re-enter overrides."
                )
            data = models_values[0]
            if not isinstance(data, _JsonObjectPairs):
                raise OverrideParseError(
                    "Override JSON models value must be an object. Re-enter overrides."
                )

        parsed_json: list[Override] = []
        seen_json_roles: set[str] = set()
        for raw_role, raw_model in data:
            _append_unique_override(
                parsed_json,
                seen_json_roles,
                _validated_override(raw_role, raw_model),
            )
        return parsed_json

    lines = text.replace("\r\n", "\n").split("\n")
    pieces = [piece.strip() for line in lines for piece in line.split(",")]
    parsed: list[Override] = []
    seen_roles: set[str] = set()
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
        _append_unique_override(
            parsed,
            seen_roles,
            _validated_override(raw_role, raw_model),
        )
    return parsed


def parse_override_line(line: str) -> list[Override]:
    """Compatibility wrapper for callers using the original parser name."""
    return parse_override_input(line)


def is_claude_model(model: str) -> bool:
    """Return True for model names that run on the Claude runtime."""
    return model == "claude" or model.startswith("claude-")


def is_antigravity_model(model: str) -> bool:
    """Return True for model names that run on the Antigravity runtime.

    Mirrors `is_claude_model`. The bare `gemini` sentinel means "use the
    Antigravity CLI's own default model" (the runner omits `--model`);
    concrete slugs such as `gemini-3.6-flash-high` pass through verbatim, so
    a newly released slug works without a Quest change.
    """
    return model == "gemini" or model.startswith("gemini-")


def runtime_for_model(model: str) -> str:
    """Map a persisted `models.<role>` model ID to its runtime family.

    `models.*` stores model IDs (for example `claude`, `claude-fake-model`,
    `gemini-fake-model`, `codex-fake-model`), not runtime names. Claude-family IDs
    run on the Claude runtime, Gemini-family IDs run on the Antigravity
    runtime (the `agy` CLI), and every other ID runs on Codex tooling.
    Provider-qualified IDs (for example `opencode/claude-fake-model`) are
    classified on the segment after the final `/`.
    """
    normalized = model.strip().lower()
    if not normalized:
        raise ValueError("model must be a non-empty string")
    unqualified = normalized.rsplit("/", 1)[-1]
    if not unqualified:
        raise ValueError(f"model ID has no name after provider prefix: {model!r}")
    if is_claude_model(unqualified):
        return "claude"
    if is_antigravity_model(unqualified):
        return "antigravity"
    return "codex"


def is_model_available(
    model: str,
    *,
    codex_available: bool,
    antigravity_available: bool = False,
) -> bool:
    """Return True if the requested model can run with the current preflight.

    Backward-compatible wrapper for Claude-led availability checks.
    """
    return is_model_available_for_orchestrator(
        model,
        orchestrator="claude",
        codex_available=codex_available,
        claude_available=True,
        antigravity_available=antigravity_available,
    )


def is_model_available_for_orchestrator(
    model: str,
    *,
    orchestrator: str,
    codex_available: bool,
    claude_available: bool,
    antigravity_available: bool = False,
) -> bool:
    """Return True if the model can run in the active orchestrator session.

    `antigravity_available` defaults to False so that a caller predating the
    Antigravity runtime rejects Gemini-backed roles at chooser time rather
    than persisting config that could only fail later at dispatch.
    """
    normalized_orchestrator = orchestrator.strip().lower()
    if normalized_orchestrator not in {"claude", "codex"}:
        raise ValueError(f"Unknown orchestrator: {orchestrator!r}")
    # Classify through the same canonical mapping dispatch uses, so
    # provider-qualified IDs (opencode/claude-*) gate consistently.
    model_runtime = runtime_for_model(model)
    if model_runtime == "antigravity":
        # Antigravity is never an orchestrator, only ever a dispatched
        # runtime, so the probe result gates it for either orchestrator.
        return antigravity_available
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
    antigravity_available: bool = False,
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
            antigravity_available=antigravity_available,
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


def build_default_models(
    allowlist_models: dict[str, str | None],
) -> dict[str, str | None]:
    """Return a fresh copy of an allowlist `models` block with all 9 keys.

    Missing keys are filled from the documented workflow defaults so older or
    customized allowlists that omit a role do not write unusable null entries.
    Explicit null values are preserved for compatibility with legacy snapshots.
    """
    return {
        role: (
            allowlist_models[role] if role in allowlist_models else DEFAULT_MODELS[role]
        )
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


def build_snapshot_models(
    snapshot_models: dict[str, str | None],
) -> dict[str, str | None]:
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


def validate_codex_reasoning_effort(effort: str) -> None:
    """Validate syntax; the dispatch surface must also support the chosen level."""
    if effort not in EFFORT_LEVELS:
        raise ValueError(
            "codex_reasoning_effort must be low|medium|high|xhigh|max|ultra"
        )


def validate_effort(role: str, effort: object) -> None:
    """Validate one `effort.<role>` entry against the shared level vocabulary.

    Syntax only. Whether a level is reachable depends on the runtime the role's
    model selects: `ultra` is Codex-only, so the Claude runner rejects it at
    dispatch rather than here. One role map serves every runtime.
    """
    if role not in CANONICAL_ROLES:
        raise ValueError(f"effort has unknown role {role!r}")
    if not isinstance(effort, str) or effort not in EFFORT_LEVELS:
        raise ValueError(
            f"effort for {role} must be one of {'|'.join(EFFORT_LEVELS)} "
            f"(got {effort!r})"
        )


def validate_effort_map(effort: object) -> dict[str, str]:
    """Validate a whole `effort` map and return a copy of it."""
    if not isinstance(effort, dict):
        raise ValueError("effort must be an object keyed by role")
    for role, level in effort.items():
        validate_effort(role, level)
    return dict(effort)


def build_default_effort(allowlist_effort: object) -> dict[str, str]:
    """Resolve the per-role effort map, filling gaps from shipped defaults."""
    merged = dict(DEFAULT_EFFORT)
    if allowlist_effort is not None:
        merged.update(validate_effort_map(allowlist_effort))
    return merged


def effort_for_role(saved: dict, role: str) -> str | None:
    """Effort for one role from a saved orchestration.json.

    Resolution order: the per-role `effort` map, then the legacy scalar
    `codex_reasoning_effort`, then None (runtime default).

    Two rules keep legacy quests behaving exactly as they did:

    - A present `effort` map is validated, never silently ignored. A malformed
      map is a configuration error, not a reason to fall back.
    - The legacy scalar is **Codex-scoped**, as its name says. Before the map
      existed, Claude roles ran unpinned and the Claude runner never read this
      key; applying it to them now would both re-tier legacy Claude roles and
      hard-fail any quest that pinned the Codex-only `ultra`.
    """
    effort = saved.get("effort")
    if "effort" in saved:
        level = validate_effort_map(effort).get(role)
        if level:
            return level
    legacy = saved.get("codex_reasoning_effort")
    if not isinstance(legacy, str) or not legacy:
        return None
    model = (saved.get("models") or {}).get(role)
    if not isinstance(model, str) or not model.strip():
        return None
    return legacy if runtime_for_model(model) == "codex" else None


_EFFORT_KEY_ALIAS = re.compile(r"""^\s*(?:"effort"|'effort')\s*:""")
_ANY_EFFORT_KEY = re.compile(r"""^\s*(?:"effort"|'effort'|effort)\s*:""")


def validate_native_claude_effort(saved: dict, role: str, agent_text: str) -> None:
    """Guard native dispatch using the generator's flat frontmatter format.

    Reject other YAML forms rather than guessing at aliases or quoted keys.
    Matching declarations do not prove Claude honors the effort setting.
    """
    model = saved.get("models", {}).get(role)
    if not isinstance(model, str) or runtime_for_model(model) != "claude":
        raise ValueError(f"{role} is not an active Claude role")
    requested = effort_for_role(saved, role)
    if requested is None:
        # The quest pins nothing for this role, so there is no disagreement to
        # find: the agent file simply carries the repo-wide default. Blocking
        # here would wall off every legacy quest on resume, since the generated
        # frontmatter always names a level and an unpinned role never can.
        return
    if requested not in CLAUDE_EFFORT_LEVELS:
        raise ValueError(f"Unsupported native Claude effort: {requested!r}")
    lines = agent_text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("Agent file has no YAML frontmatter")
    fields: dict[str, str] = {}
    for line in lines[1 : lines.index("---", 1)]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace() or line.lstrip().startswith("- "):
            # Part of the previous key's nested block. `hooks:` and
            # `mcpServers:` are valid subagent keys; refusing to dispatch
            # because one is present would be a worse failure than the
            # ambiguity it guards against. An `effort:` nested somewhere
            # unexpected is the one thing we will not skip past.
            if _ANY_EFFORT_KEY.match(line):
                raise ValueError(
                    f"Native effort guard found an ambiguous `effort` key: "
                    f"{line.strip()!r}"
                )
            continue
        match = re.fullmatch(r"([a-zA-Z][a-zA-Z0-9_-]*):[ \t]*(.*)", line)
        if match is None:
            # A quoted or otherwise unusual key spelling. Only `effort` matters
            # here, and an ambiguous one must not be read as agreement.
            if _EFFORT_KEY_ALIAS.match(line):
                raise ValueError(
                    "Native effort guard cannot read an ambiguous `effort` key: "
                    f"{line.strip()!r}"
                )
            continue
        if match[1] in fields:
            raise ValueError(f"Duplicate frontmatter key {match[1]!r} in agent file")
        fields[match[1]] = match[2].strip()
    actual = fields.get("effort")
    if actual != requested:
        raise ValueError(
            f"Native Claude effort mismatch for {role}: saved={requested!r}, "
            f"frontmatter={actual!r}. Stop before Task dispatch."
        )


def validate_codex_auth_mode(mode: str) -> None:
    """Validate an explicit billing choice; absence defaults to cached."""
    if mode not in ("cached", "api-key"):
        raise ValueError("codex_auth_mode must be cached|api-key")


def write_orchestration_json(
    path: Path,
    *,
    models: dict[str, str | None],
    source: str,
    overridden_roles: list[str],
    preflight_validated_at: str | None = None,
    claude_role_transport: str = DEFAULT_CLAUDE_ROLE_TRANSPORT,
    claude_transport_resolved: str | None = None,
    codex_reasoning_effort: str | None = None,
    effort: dict[str, str] | None = None,
    codex_auth_mode: str = "cached",
) -> None:
    """Write the orchestration.json artifact with canonical key order."""
    if source not in {"default", "overridden"}:
        raise ValueError(f"source must be 'default' or 'overridden' (got {source!r})")
    if claude_role_transport not in CLAUDE_ROLE_TRANSPORTS:
        raise ValueError(
            f"claude_role_transport must be one of {CLAUDE_ROLE_TRANSPORTS} "
            f"(got {claude_role_transport!r})"
        )
    if codex_reasoning_effort is not None:
        validate_codex_reasoning_effort(codex_reasoning_effort)
    # `None` means "this caller has no effort policy" — write no key at all, so
    # a migrated legacy quest keeps resolving through whatever it already had.
    # Only the new-quest writers below synthesize DEFAULT_EFFORT.
    resolved_effort = None if effort is None else validate_effort_map(effort)
    validate_codex_auth_mode(codex_auth_mode)
    payload = {
        "version": ORCHESTRATION_VERSION,
        "codex_auth_mode": codex_auth_mode,
        "models": {role: models.get(role) for role in CANONICAL_ROLES},
        **({} if resolved_effort is None else {"effort": resolved_effort}),
        "claude_role_transport": claude_role_transport,
        "claude_transport_resolved": claude_transport_resolved,
        # Compatibility field for consumers created during the downgrade era.
        # New auto runs block for user choice instead of downgrading.
        "claude_transport_downgraded": False,
        "source": source,
        "overridden_roles": list(overridden_roles),
        "preflight_validated_at": preflight_validated_at or _now_iso(),
    }
    if codex_reasoning_effort is not None:
        payload["codex_reasoning_effort"] = codex_reasoning_effort
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
    antigravity_available: bool = False,
    quest_mode: str = "workflow",
    remap_unavailable: bool = False,
    claude_role_transport: str = DEFAULT_CLAUDE_ROLE_TRANSPORT,
    claude_transport_resolved: str | None = None,
    codex_reasoning_effort: str | None = None,
    effort: dict[str, str] | None = None,
    codex_auth_mode: str = "cached",
) -> None:
    """Default-path writer: copy allowlist models into orchestration.json.

    `antigravity_available` must be forwarded from the preflight probe result.
    Without it the validation below rejects every Gemini-backed role, so a
    repo that configured one in its allowlist could never persist it.
    """
    defaults = build_default_models(allowlist_models)
    if orchestrator is not None:
        defaults, _ = validate_or_remap_models_for_orchestrator(
            defaults,
            orchestrator=orchestrator,
            codex_available=codex_available,
            claude_available=claude_available,
            antigravity_available=antigravity_available,
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
        codex_reasoning_effort=codex_reasoning_effort,
        # New quests always get a complete map: an allowlist without an `effort`
        # block still means "use the shipped defaults", not "pin nothing".
        # Migration is the opposite case and passes None through deliberately.
        effort=build_default_effort(effort),
        codex_auth_mode=codex_auth_mode,
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
        if "codex_reasoning_effort" in existing:
            validate_codex_reasoning_effort(existing["codex_reasoning_effort"])
        # A saved effort map is validated but never backfilled: a quest written
        # before the map existed keeps resolving through the legacy scalar, so
        # resume cannot silently re-tier an in-flight quest.
        if "effort" in existing:
            validate_effort_map(existing["effort"])
        validate_codex_auth_mode(existing.get("codex_auth_mode", "cached"))
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
        state_path = quest_dir / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        active_roles = active_roles_for_mode(state.get("quest_mode", "workflow"))
        missing_roles = [
            role
            for role in CANONICAL_ROLES
            if role not in merged_models
            or (
                role in active_roles
                and (
                    not isinstance(merged_models[role], str)
                    or not merged_models[role].strip()
                )
            )
        ]
        if missing_roles:
            raise ValueError(
                "orchestration.json migration would write invalid model(s) for "
                f"role(s) {missing_roles}; the existing file is malformed — "
                "fix models.<role> entries before resuming."
            )
        existing["models"] = {role: merged_models.get(role) for role in CANONICAL_ROLES}
        if not isinstance(
            existing.get("preflight_validated_at"), str
        ) or not existing.get("preflight_validated_at"):
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
    if "codex_reasoning_effort" in snapshot:
        validate_codex_reasoning_effort(snapshot["codex_reasoning_effort"])
    if "effort" in snapshot:
        validate_effort_map(snapshot["effort"])
    write_orchestration_json(
        orch_path,
        models=build_snapshot_models(models),
        codex_reasoning_effort=snapshot.get("codex_reasoning_effort"),
        effort=snapshot.get("effort"),
        codex_auth_mode=snapshot.get("codex_auth_mode", "cached"),
        source="default",
        overridden_roles=[],
        preflight_validated_at=preflight_validated_at,
    )
    return True
