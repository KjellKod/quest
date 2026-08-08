"""Drift guard: every phase name ``workflow.md`` teaches must be a phase name
``expected_artifacts_for_role`` accepts.

Quest's control flow is markdown an orchestrator reads, so ``workflow.md`` is
not documentation *about* the dispatch contract -- it is the copy the
orchestrator learns the contract from. The accepted spellings live in
``ROLE_PHASE_ALIASES``. Nothing currently connects the two, so an edit to
either side can teach an orchestrator a value the code rejects, and the suite
stays green.

That failure mode is worse than an off-path mistake: the orchestrator follows
the documented path faithfully and still fails, on every quest, for every user.
These tests fail by name the moment the doc and the gate disagree.

Scope: phase *values*. The role *slot* dimension is guarded by
``test_canonical_role_lockstep.py``, and the agent-contract-file dimension by
``test_runtime_agent_role_files_reference_canonical.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from quest_runtime.artifacts import expected_artifacts_for_role
from quest_runtime.orchestration import CANONICAL_ROLES

WORKFLOW_DOC = (
    Path(__file__).resolve().parents[2]
    / ".skills"
    / "quest"
    / "delegation"
    / "workflow.md"
)

# Matches phase/agent examples in both forms the doc uses:
#   context_health.log style  -- "phase=plan_review | agent=plan-reviewer-a"
#   role-instance-list style  -- "(phase=plan, agent=planner)"
# The second form is the doc's own authoritative per-role dispatch list (the
# "Split by role instance" block), so missing it would have left the exact
# pairing this PR claims to pin unchecked -- caught in review, not written
# blind: an earlier version of this pattern matched only the first form.
_PHASE_PATTERN = re.compile(r"phase=([a-z_0-9]+)")
_PAIR_PATTERN = re.compile(r"phase=([a-z_0-9]+)[ |,]+agent=([a-z0-9-]+)")


def _doc_text() -> str:
    return WORKFLOW_DOC.read_text(encoding="utf-8")


def _documented_phases() -> set[str]:
    return set(_PHASE_PATTERN.findall(_doc_text()))


def _documented_pairs() -> set[tuple[str, str]]:
    """Return (phase, agent) pairs whose agent is a real role slot.

    The doc also contains templated agent names (for example a truncated
    ``agent=code-reviewer-`` standing in for either slot). Those are prose, not
    a claim about a specific role, so they are filtered out rather than
    asserted on.
    """

    return {
        (phase, agent)
        for phase, agent in _PAIR_PATTERN.findall(_doc_text())
        if agent in CANONICAL_ROLES
    }


def test_the_extraction_actually_finds_examples() -> None:
    """Guard the guard.

    Both tests below pass vacuously if the doc stops using the ``phase=``
    convention or the regex drifts. A lockstep test that silently matches
    nothing is worse than no test, so pin that examples exist at all.
    """

    assert WORKFLOW_DOC.exists(), f"missing dispatch doc: {WORKFLOW_DOC}"
    assert len(_documented_phases()) >= 5, "workflow.md phase= examples disappeared"
    assert len(_documented_pairs()) >= 3, "workflow.md phase/agent pairs disappeared"


def test_every_documented_phase_is_accepted_by_some_role(tmp_path: Path) -> None:
    """No phase name in the doc may be rejected by every role."""

    for phase in sorted(_documented_phases()):
        accepted_by = []
        for agent in CANONICAL_ROLES:
            try:
                expected_artifacts_for_role(tmp_path, phase, agent)
            except ValueError:
                continue
            accepted_by.append(agent)

        assert accepted_by, (
            f"workflow.md teaches phase={phase!r}, but no canonical role accepts "
            "it. Either the doc example or ROLE_PHASE_ALIASES is wrong; an "
            "orchestrator following the doc would fail here."
        )


def test_documented_phase_and_agent_pairs_resolve(tmp_path: Path) -> None:
    """Each worked example in the doc must resolve for the role it names."""

    for phase, agent in sorted(_documented_pairs()):
        try:
            paths = expected_artifacts_for_role(tmp_path, phase, agent)
        except ValueError as exc:  # pragma: no cover - failure path is the point
            pytest.fail(
                f"workflow.md shows 'phase={phase} | agent={agent}', but that "
                f"pairing is rejected: {exc}"
            )
        assert paths, f"phase={phase} agent={agent} resolved no artifacts"
