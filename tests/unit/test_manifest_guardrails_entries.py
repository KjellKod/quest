"""Contract tests for the manifest + AGENTS.md guardrail entries.

Plan reference: ``.quest/wrong-location-guardrails_2026-05-18__0003/phase_01_plan/plan.md``
§7.4.

Covers:

#1 — ``.claude/hooks/branch-dir-context.sh`` listed under ``[copy-as-is]``.
#2 — ``scripts/quest_artifact_postflight.py`` listed under ``[copy-as-is]``.
#3 — ``.claude/settings.json`` still under ``[merge-carefully]``.
#4 — AGENTS.md contains the verbatim installer-caveat substring.
#5 — AGENTS.md mentions both guardrail file paths as literals.
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / ".quest-manifest"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"

_HOOK_PATH = ".claude/hooks/branch-dir-context.sh"
_VALIDATOR_PATH = "scripts/quest_artifact_postflight.py"
_SETTINGS_PATH = ".claude/settings.json"

# Verbatim substring required by AGENTS.md per plan §6 / §7.4 #4.
_CAVEAT_LITERAL = (
    "the installer writes `.claude/settings.json.quest_updated` and the "
    "user must manually merge the new `PreToolUse` entry"
)


def _section_lines(manifest_text: str, section: str) -> list[str]:
    """Return the file-path lines under a ``[section]`` header in the manifest.

    Lines that are empty or start with ``#`` are skipped. The block ends at
    the next ``[section]`` header.
    """

    lines = manifest_text.splitlines()
    header = f"[{section}]"
    in_section = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == header
            continue
        if not in_section:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped)
    return out


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


def test_manifest_lists_hook_under_copy_as_is() -> None:
    """#1: ``.claude/hooks/branch-dir-context.sh`` lives under
    ``[copy-as-is]``."""

    text = _MANIFEST.read_text(encoding="utf-8")
    copy_as_is = _section_lines(text, "copy-as-is")
    assert _HOOK_PATH in copy_as_is, (
        f"{_HOOK_PATH} must be listed under [copy-as-is]; "
        f"got: {copy_as_is!r}"
    )


def test_manifest_lists_validator_under_copy_as_is() -> None:
    """#2: ``scripts/quest_artifact_postflight.py`` lives under
    ``[copy-as-is]``."""

    text = _MANIFEST.read_text(encoding="utf-8")
    copy_as_is = _section_lines(text, "copy-as-is")
    assert _VALIDATOR_PATH in copy_as_is, (
        f"{_VALIDATOR_PATH} must be listed under [copy-as-is]; "
        f"got: {copy_as_is!r}"
    )


def test_manifest_settings_json_remains_merge_carefully() -> None:
    """#3: ``.claude/settings.json`` is still under ``[merge-carefully]``
    (not silently demoted to ``[copy-as-is]``)."""

    text = _MANIFEST.read_text(encoding="utf-8")
    merge_carefully = _section_lines(text, "merge-carefully")
    copy_as_is = _section_lines(text, "copy-as-is")
    assert _SETTINGS_PATH in merge_carefully, (
        f"{_SETTINGS_PATH} must remain under [merge-carefully]"
    )
    assert _SETTINGS_PATH not in copy_as_is, (
        f"{_SETTINGS_PATH} must NOT be silently moved to [copy-as-is]"
    )


# ---------------------------------------------------------------------------
# AGENTS.md tests
# ---------------------------------------------------------------------------


def test_agents_md_contains_merge_caveat_string() -> None:
    """#4: the verbatim installer-caveat substring appears in AGENTS.md."""

    text = _AGENTS_MD.read_text(encoding="utf-8")
    # Normalize whitespace so a multi-line wrap of the caveat still matches.
    flat = re.sub(r"\s+", " ", text)
    flat_caveat = re.sub(r"\s+", " ", _CAVEAT_LITERAL)
    assert flat_caveat in flat, (
        f"AGENTS.md must contain the installer-caveat substring verbatim: "
        f"{_CAVEAT_LITERAL!r}"
    )


def test_agents_md_names_both_guardrails() -> None:
    """#5: AGENTS.md mentions both guardrail paths as literals."""

    text = _AGENTS_MD.read_text(encoding="utf-8")
    assert _HOOK_PATH in text, f"AGENTS.md must mention {_HOOK_PATH}"
    assert _VALIDATOR_PATH in text, f"AGENTS.md must mention {_VALIDATOR_PATH}"
