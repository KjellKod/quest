"""Tests for scripts/quest_artifact_postflight.py.

Plan reference: ``.quest/wrong-location-guardrails_2026-05-18__0003/phase_01_plan/plan.md``
§7.2.

Tests in this file:

* Slice B (happy path): #1, #7, #10.
* Slice C (failure branches): #2, #3, #4, #5, #6, #8, #9.
* Slice D (latency, perf-marker-gated): #11, #12.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pytest

# Ensure ``scripts/`` is on sys.path before importing the validator module.
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import quest_artifact_postflight as postflight  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Return a temp repo root that contains a ``.quest/<id>/`` tree."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def _make_planner_handoff(
    *,
    repo_root: Path,
    quest_id: str = "test-quest_2026-05-18__0001",
    artifacts: list[str] | None = None,
    create_artifact_files: bool = True,
) -> tuple[Path, Path, Path]:
    """Create a planner-phase quest dir, optional artifact files, and the
    handoff.json. Returns ``(quest_dir, handoff_path, log_path)``."""

    quest_dir = repo_root / ".quest" / quest_id
    phase_dir = quest_dir / "phase_01_plan"
    phase_dir.mkdir(parents=True, exist_ok=True)
    log_path = quest_dir / "logs" / "path_compliance.log"

    if artifacts is None:
        artifacts = [
            str(phase_dir / "plan.md"),
            str(phase_dir / "handoff.json"),
        ]

    if create_artifact_files:
        for entry in artifacts:
            p = Path(entry)
            if not p.is_absolute():
                p = repo_root / entry
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("seed", encoding="utf-8")

    handoff_path = phase_dir / "handoff.json"
    handoff_payload = {
        "status": "complete",
        "artifacts": artifacts,
        "next": "plan-reviewer-a",
        "summary": "test handoff",
    }
    handoff_path.write_text(json.dumps(handoff_payload), encoding="utf-8")
    return quest_dir, handoff_path, log_path


# ---------------------------------------------------------------------------
# Slice B — Happy-path tests (#1, #7, #10)
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Plan §7.2 #1, #7, #10."""

    def test_all_declared_artifacts_present_and_inside_boundary_passes(
        self, workspace: Path
    ) -> None:
        """#1: exit 0; log file absent or empty."""

        quest_dir, handoff_path, log_path = _make_planner_handoff(repo_root=workspace)
        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        # Log file MUST be absent or empty on a clean pass.
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_no_expected_artifacts_role_passes_with_no_log(self, workspace: Path) -> None:
        """#7: role whose expected_artifacts_for_role(...) returns empty
        → exit 0 and the log file is left untouched."""

        # plan-reviewer-b is solo-disabled; in ``quest_mode='solo'`` the
        # helper returns an empty list and the validator passes through.
        quest_id = "test-quest_2026-05-18__0001"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        handoff_path = phase_dir / "handoff_plan-reviewer-b.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [],
                    "next": "arbiter",
                    "summary": "n/a",
                }
            ),
            encoding="utf-8",
        )

        # Seed an existing log line to prove the validator does NOT touch it
        # on a pass-through role.
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel = '{"sentinel":"preserved"}\n'
        log_path.write_text(sentinel, encoding="utf-8")

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="plan-reviewer-b",
            handoff=handoff_path,
            quest_mode="solo",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        assert log_path.read_text(encoding="utf-8") == sentinel

    def test_run_returns_nonzero_int_on_any_mismatch(self, workspace: Path) -> None:
        """#10: pin the ``run(...)`` Python contract directly.

        Pass case returns ``0``; mismatch case returns ``1``.
        """

        # Pass case.
        quest_dir, handoff_path, log_path = _make_planner_handoff(repo_root=workspace)
        assert (
            postflight.run(
                quest_dir=quest_dir,
                phase="phase_01_plan",
                role="planner",
                handoff=handoff_path,
                quest_mode="workflow",
                log=log_path,
                repo_root=workspace,
            )
            == 0
        )

        # Mismatch case: declared path missing on disk.
        quest_id = "test-quest_2026-05-18__0002"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path_b = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"
        handoff_path_b = phase_dir / "handoff.json"
        handoff_payload = {
            "status": "complete",
            "artifacts": [
                str(phase_dir / "plan.md"),  # never written to disk
                str(phase_dir / "handoff.json"),
            ],
            "next": "plan-reviewer-a",
            "summary": "missing-plan case",
        }
        handoff_path_b.write_text(json.dumps(handoff_payload), encoding="utf-8")

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path_b,
            quest_mode="workflow",
            log=log_path_b,
            repo_root=workspace,
        )
        assert isinstance(rc, int)
        assert rc == 1


# ---------------------------------------------------------------------------
# Slice C — Failure branches + mismatch records (#2 – #6, #8, #9)
# ---------------------------------------------------------------------------


def _read_log_lines(log_path: Path) -> list[dict[str, str]]:
    """Return the JSON-decoded mismatch records from ``log_path``."""

    if not log_path.exists():
        return []
    raw = log_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


class TestFailureBranches:
    """Plan §7.2 #2 – #6, #8, #9."""

    def test_missing_artifact_records_missing_mismatch(self, workspace: Path) -> None:
        """#2: declared artifact does not exist on disk → reason=missing."""

        # plan.md is declared but not written; handoff.json is written.
        quest_id = "test-quest_missing"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "plan.md"),  # NOT written
                        str(phase_dir / "handoff.json"),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "missing plan.md",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert len(records) == 1
        assert records[0]["reason"] == "missing"
        assert records[0]["declared"].endswith("plan.md")

    def test_outside_boundary_records_outside_boundary(self, workspace: Path) -> None:
        """#3: declared artifact resolves inside repo but outside the role
        boundary → reason=outside_boundary."""

        quest_id = "test-quest_outside"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Declared path is in src/, which is repo-local but outside the
        # phase_01_plan boundary.
        rogue = workspace / "src" / "plan.md"
        rogue.parent.mkdir(parents=True, exist_ok=True)
        rogue.write_text("rogue", encoding="utf-8")
        good_handoff = phase_dir / "handoff.json"
        good_handoff.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(rogue), str(good_handoff)],
                    "next": "plan-reviewer-a",
                    "summary": "outside boundary",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "outside_boundary" for r in records)

    def test_nested_quest_path_records_nested_quest(self, workspace: Path) -> None:
        """#4: path contains .quest/<id>/.quest/ → reason=nested_quest."""

        quest_id = "test-quest_nested"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Pathologic nested .quest/<id>/.quest/<id>/phase_01_plan/plan.md
        nested = (
            workspace
            / ".quest"
            / quest_id
            / ".quest"
            / quest_id
            / "phase_01_plan"
            / "plan.md"
        )
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text("nested", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(nested), str(phase_dir / "handoff.json")],
                    "next": "plan-reviewer-a",
                    "summary": "nested .quest",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "nested_quest" for r in records)

    def test_path_traversal_records_traversal_outside_repo(
        self, workspace: Path
    ) -> None:
        """#5: declared path with ``..`` resolves outside repo_root →
        reason=traversal_outside_repo."""

        quest_id = "test-quest_traversal"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Resolve outside the repo by walking up via ``..``. We construct an
        # absolute path so the resolve() escapes ``workspace``.
        outside = workspace.parent / "elsewhere" / "plan.md"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("rogue", encoding="utf-8")

        # Reference outside via a relative-with-``..`` form so the validator
        # has to resolve it.
        traversal_relative = "../elsewhere/plan.md"

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [traversal_relative, str(phase_dir / "handoff.json")],
                    "next": "plan-reviewer-a",
                    "summary": "traversal",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "traversal_outside_repo" for r in records)

    def test_noncanonical_filename_records_noncanonical_name(
        self, workspace: Path
    ) -> None:
        """#6: declared filename is not in the canonical set →
        reason=noncanonical_name."""

        quest_id = "test-quest_noncanon"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # ``rogue.md`` is inside the boundary (the phase directory) but the
        # name is not one of {plan.md, handoff.json}.
        rogue = phase_dir / "rogue.md"
        rogue.write_text("rogue", encoding="utf-8")
        good_handoff = phase_dir / "handoff.json"
        good_handoff.write_text("seed", encoding="utf-8")
        good_plan = phase_dir / "plan.md"
        good_plan.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(rogue),
                        str(good_plan),
                        str(good_handoff),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "noncanonical name",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "noncanonical_name" for r in records)
        # The other declared paths (plan.md, handoff.json) should pass and
        # NOT add records.
        canonical_failures = [
            r for r in records if r["declared"].endswith(("plan.md", "handoff.json"))
        ]
        assert canonical_failures == []

    def test_multiple_mismatches_append_one_line_per_mismatch(
        self, workspace: Path
    ) -> None:
        """#8: two declared bad paths → two JSON lines; exit non-zero."""

        quest_id = "test-quest_multi"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Two missing artifacts.
        plan_missing = phase_dir / "plan.md"
        handoff_missing = phase_dir / "handoff.json"
        # NOTE: handoff.json is written for the validator to read, but plan.md
        # stays missing. We write handoff.json then list a DIFFERENT path
        # also (with a noncanonical name) so we get two mismatches.
        handoff_missing.write_text("seed", encoding="utf-8")
        rogue = phase_dir / "rogue.md"
        # rogue path: exists but noncanonical name.
        rogue.write_text("rogue", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(plan_missing),  # missing -> reason=missing
                        str(rogue),  # noncanonical name
                        str(handoff_missing),  # OK
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "two mismatches",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        # Exactly TWO mismatches recorded.
        assert len(records) == 2
        reasons = {r["reason"] for r in records}
        assert reasons == {"missing", "noncanonical_name"}

    def test_log_lines_are_valid_json_with_required_fields(
        self, workspace: Path
    ) -> None:
        """#9: each log line parses; required fields present."""

        quest_id = "test-quest_json_fields"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # One missing artifact -> exactly one log line.
        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "plan.md"),  # missing
                        str(phase_dir / "handoff.json"),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "single missing",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1

        # The file contains valid JSON lines with required fields.
        required = {"timestamp", "phase", "role", "declared", "actual", "reason"}
        raw = log_path.read_text(encoding="utf-8").splitlines()
        assert raw, "log should contain at least one line"
        for line in raw:
            assert line.strip(), "no blank lines"
            record = json.loads(line)
            assert required.issubset(record.keys()), record
            assert record["phase"] == "phase_01_plan"
            assert record["role"] == "planner"
            assert isinstance(record["timestamp"], str) and record["timestamp"]
            assert record["reason"] in {
                "missing",
                "outside_boundary",
                "noncanonical_name",
                "nested_quest",
                "traversal_outside_repo",
                "unsupported_role_or_phase",
            }


# ---------------------------------------------------------------------------
# Slice D — Latency tests (#11, #12), perf-marker-gated
# ---------------------------------------------------------------------------


def _median_run_ms(
    *,
    quest_dir: Path,
    handoff_path: Path,
    log_path: Path,
    workspace: Path,
    iterations: int = 5,
    role: str = "planner",
    phase: str = "phase_01_plan",
    quest_mode: str = "workflow",
) -> float:
    """Run ``postflight.run(...)`` ``iterations`` times and return median ms."""

    timings: list[float] = []
    for _ in range(iterations):
        # Truncate the log between runs so the latency picture isn't biased
        # by append-only growth.
        if log_path.exists():
            log_path.unlink()
        t0 = time.perf_counter()
        postflight.run(
            quest_dir=quest_dir,
            phase=phase,
            role=role,
            handoff=handoff_path,
            quest_mode=quest_mode,
            log=log_path,
            repo_root=workspace,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        timings.append(elapsed_ms)
    return statistics.median(timings)


class TestLatency:
    """Plan §7.2 #11, #12 — perf-marker-gated."""

    @pytest.mark.perf
    def test_latency_under_target_for_typical_role(self, workspace: Path) -> None:
        """#11: typical 3-artifact happy path. Median of 5 runs < 50 ms."""

        # The planner expected_artifacts_for_role returns 2 entries; declare
        # 3 paths (the 2 canonical + 1 sibling) so the workload matches the
        # plan's 3-artifact figure. Sibling has noncanonical name, so we
        # only use canonical-named files.
        quest_id = "test-quest_perf_3"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # All canonical names so the run passes (latency = pass-path cost).
        plan_md = phase_dir / "plan.md"
        handoff_json = phase_dir / "handoff.json"
        plan_md.write_text("seed", encoding="utf-8")
        handoff_json.write_text("seed", encoding="utf-8")

        # Use the builder role to bump up to 3 artifacts in one phase.
        # Builder canonical: pr_description.md, builder_feedback_discussion.md, handoff.json.
        builder_phase_dir = workspace / ".quest" / quest_id / "phase_02_implementation"
        builder_phase_dir.mkdir(parents=True, exist_ok=True)
        pr_md = builder_phase_dir / "pr_description.md"
        fb_md = builder_phase_dir / "builder_feedback_discussion.md"
        b_handoff = builder_phase_dir / "handoff.json"
        for p in (pr_md, fb_md, b_handoff):
            p.write_text("seed", encoding="utf-8")

        b_handoff.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(pr_md), str(fb_md), str(b_handoff)],
                    "next": "code-reviewer-a",
                    "summary": "perf-3",
                }
            ),
            encoding="utf-8",
        )

        median_ms = _median_run_ms(
            quest_dir=workspace / ".quest" / quest_id,
            handoff_path=b_handoff,
            log_path=log_path,
            workspace=workspace,
            role="builder",
            phase="phase_02_implementation",
        )
        assert median_ms < 50.0, f"median latency {median_ms:.2f} ms >= 50 ms target"

    @pytest.mark.perf
    def test_latency_under_regression_cap_for_stress_case(
        self, workspace: Path
    ) -> None:
        """#12: 20-declared-artifact stress case. Median of 5 runs < 200 ms."""

        # Use the builder role: 3 canonical names. Declare 20 paths (each
        # one of the 3 canonical names, all inside the phase directory).
        quest_id = "test-quest_perf_20"
        phase_dir = workspace / ".quest" / quest_id / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        canonical = ["pr_description.md", "builder_feedback_discussion.md", "handoff.json"]
        for name in canonical:
            (phase_dir / name).write_text("seed", encoding="utf-8")

        # 20 declared paths cycling through canonical files (all valid).
        declared = [str(phase_dir / canonical[i % 3]) for i in range(20)]

        b_handoff = phase_dir / "handoff.json"
        b_handoff.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": declared,
                    "next": "code-reviewer-a",
                    "summary": "perf-20",
                }
            ),
            encoding="utf-8",
        )

        median_ms = _median_run_ms(
            quest_dir=workspace / ".quest" / quest_id,
            handoff_path=b_handoff,
            log_path=log_path,
            workspace=workspace,
            role="builder",
            phase="phase_02_implementation",
        )
        assert median_ms < 200.0, (
            f"median latency {median_ms:.2f} ms >= 200 ms regression cap"
        )
