# Quest Journal: Wrong-Location Guardrails

- Quest ID: `wrong-location-guardrails_2026-05-18__0003`
- Completed: 2026-05-18
- Mode: workflow
- Quality: Platinum
- Outcome: Ships two additive guardrails to every Quest user via the installer — a `PreToolUse Edit|Write` hook that prints branch + working directory before edits, and a post-invocation sub-agent artifact-path validator (`scripts/quest_artifact_postflight.py`) wired into the orchestrator workflow at the END of the Handoff File Polling pattern. Targets the top friction class in the eval data (wrong-branch / wrong-directory / wrong nested `.quest/` edits).

## What Shipped

**Hook (Slice A)** — `.claude/hooks/branch-dir-context.sh`: prints `[quest-context] branch=<name|no-git> dir=<path>`, exits 0 in git / non-git / detached-HEAD contexts, never blocks the wrapped tool call. Additive `PreToolUse Edit|Write` wiring in `.claude/settings.json` preserves existing `SessionStart` and `PostToolUse` hooks verbatim.

**Validator (Slices B–D)** — `scripts/quest_artifact_postflight.py`: filesystem-only checks against `expected_artifacts_for_role(...)`. Five mismatch reasons (`missing`, `outside_boundary`, `noncanonical_filename`, `nested_quest_path`, `path_traversal`) plus a defensive `unsupported_role_or_phase`. CLI exits non-zero on mismatch; orchestrator policy is `accepted_with_warnings` (non-halting per kill criterion). Latency: `<50 ms` median on happy path, `<200 ms` regression cap on 20-artifact stress case, gated behind `pytest.mark.perf`.

**Workflow wire-in (Slice E)** — doc-only edit to `.skills/quest/delegation/workflow.md`. New postflight step appended at the END of the Handoff File Polling pattern; existing items 1–6 (and their numbering) preserved. Cross-reference counts in workflow.md unchanged: `Handoff File Polling §5` × 6, `Handoff File Polling** §6` × 4. Two contract tests lock the placement and the counts against future drift.

**Manifest + AGENTS.md (Slice F)** — `.quest-manifest` adds the hook and validator under `[copy-as-is]`. `AGENTS.md` gets a "Wrong-location guardrails" section that names both guardrails, documents how to disable them, and surfaces the installer's `merge-carefully` caveat: users with customized `.claude/settings.json` get a `.quest_updated` sidecar and must merge manually.

**Archival (Slice G)** — three idea docs moved to `ideas/archive/` via `git mv`; `ideas/README.md` Done Index gains a `done` row pointing at this journal.

## Files Changed

- `.claude/hooks/branch-dir-context.sh` (new)
- `.claude/settings.json` (additive PreToolUse hook)
- `.quest-manifest` (two new `[copy-as-is]` entries)
- `.skills/quest/delegation/workflow.md` (new postflight step at end of Handoff File Polling pattern)
- `AGENTS.md` (Wrong-location guardrails section)
- `ideas/README.md` (active rows removed, Done Index row added)
- `ideas/archive/2026-05-17-wrong-location-guardrails.md` (moved from `ideas/`)
- `ideas/archive/2026-04-15-pretooluse-branch-dir-verification-hook.md` (moved from `ideas/`)
- `ideas/archive/2026-04-15-subagent-path-constraints-hardening.md` (moved from `ideas/`)
- `pyproject.toml` (registers `perf` marker)
- `scripts/quest_artifact_postflight.py` (new validator)
- `tests/unit/test_branch_dir_context_hook.sh` (new — hook contexts)
- `tests/unit/test_quest_artifact_postflight.py` (new — 12 cases incl. perf)
- `tests/unit/test_workflow_postflight_wireup.py` (new — placement + cross-ref counts)
- `tests/unit/test_manifest_guardrails_entries.py` (new — manifest + AGENTS.md literals)
- `tests/unit/test_ideas_archive_guardrails_housekeeping.py` (new — archival assertions)

## Iterations

- Plan iterations: 3
- Fix iterations: 0

### Plan-phase review history

- **Iteration 1.** Reviewer A approved with 1 must-fix + 3 should-fixes + 3 nits. Reviewer B caught **1 blocker** (installer `merge-carefully` is wholesale-replace, not JSON merge — confirmed at `scripts/quest_installer.sh:1309-1405`) plus 2 must-fix and 11 should-fix/nit. Arbiter merged to 4 `fix_now` items (A1–A4), 4 defer, 1 drop.
- **Iteration 2.** Resolved A1/A3/A4 cleanly. A2's chosen placement introduced regression **B1**: silently renumbered Handoff File Polling steps, breaking 10 numeric cross-references at workflow.md:318/355/483/716/787/992 (§5) and 457/733/923/1005 (§6). Reviewer B caught it. Arbiter cross-verified line numbers; one `fix_now`.
- **Iteration 3.** Adopted Option (a): append the new step at the END of the pattern. New tests lock placement (end-of-section negative assertion) and cross-reference counts (§5 × 6, §6 × 4). Both reviewers approve with **0 findings**; arbiter approves; route to builder.

### Code-review history

- Builder ran 7 slices, 584 unit tests pass, 2 perf tests pass.
- Reviewer A: 5 low/info findings, no blockers.
- Reviewer B: empirically verified §5 × 6, §6 × 4, postflight placement after line 143 — 0 findings.
- Arbiter: 0 fix_now, 2 defer, 3 drop → **APPROVED → complete** (no fixer needed).

## Decisions

1. **Installer merge approach.** Option 2 (KISS): document the limitation in `AGENTS.md` rather than extend the installer with `jq`-aware merge. Plan §11.
2. **Validator wire-in.** Doc-only / orchestrator-instruction. No new Python module auto-invokes `run(...)`. Runtime auto-invocation logged as backlog for a follow-up quest. Plan §11.
3. **Validator failure policy.** `accepted_with_warnings` (non-halting). CLI exits non-zero, structured log records persist, orchestrator surfaces a warning but does not block the handoff. Tighten to halting only once false-positive rate is empirically zero in the field. Plan §11.
4. **Workflow placement.** End of Handoff File Polling pattern (preserves §5/§6 numbering). Mid-list placement rejected — silently breaks 10 hard-coded numeric cross-references in workflow.md. Plan §11.

## Carry-Over Findings

- No carry-over findings inherited (deferred-backlog scan returned 0 matches at planner startup).
- 3 code-review polish findings appended to `.quest/backlog/deferred_findings.jsonl` for re-surfacing on the next quest touching the postflight validator or workflow doc: docstring drift on validator mismatch reasons (`cra-002` polish for the test heuristic, `cra-003` validator docstring polish, `cra-004` `--quest-mode` help text polish).

## Acceptance Criteria

All 8 ACs covered with green tests:

- AC1 ✓ Additive `PreToolUse Edit|Write` in `.claude/settings.json`; existing hooks preserved.
- AC2 ✓ Hook stdout format + non-blocking exit verified across git / non-git / detached-HEAD.
- AC3 ✓ Validator wired in workflow.md at handoff acceptance.
- AC4 ✓ Validator exits non-zero on mismatch; structured log records to `.quest/<id>/logs/path_compliance.log`.
- AC5 ✓ Both new files under `[copy-as-is]` in `.quest-manifest`.
- AC6 ✓ All focused tests pass (`pytest tests/unit/ -q`: 584 pass; perf: 2 pass; existing handoff-contract shell tests still green).
- AC7 ✓ `AGENTS.md` gains "Wrong-location guardrails" section.
- AC8 ✓ Three idea docs archived; Done Index row added; active rows removed.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/wrong-location-guardrails_2026-05-18.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "planner",
      "model": "claude",
      "role": "The Architect"
    },
    {
      "name": "plan-reviewer-a",
      "model": "claude",
      "role": "The First Reader"
    },
    {
      "name": "plan-reviewer-b",
      "model": "claude",
      "role": "The Second Reader"
    },
    {
      "name": "arbiter",
      "model": "claude",
      "role": "The Judge"
    },
    {
      "name": "builder",
      "model": "claude",
      "role": "The Implementer"
    },
    {
      "name": "code-reviewer-a",
      "model": "claude",
      "role": "The Code Inspector A"
    },
    {
      "name": "code-reviewer-b",
      "model": "claude",
      "role": "The Code Inspector B"
    }
  ],
  "achievements": [
    {
      "icon": "[HOOK]",
      "title": "Wrong-Location Slayer",
      "desc": "Hook + validator address the top friction class (55 'wrong approach' events)"
    },
    {
      "icon": "[CATCH]",
      "title": "Cross-Reference Watchdog",
      "desc": "Reviewer B caught two real regressions — installer merge gap and 10 silent §5/§6 cross-reference breaks"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "584 unit tests + 2 perf tests green; new contract tests lock placement and counts"
    },
    {
      "icon": "[SHIP]",
      "title": "Ships Everywhere",
      "desc": "Both guardrails ride out through the installer to every downstream Quest user"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All 8 ACs covered, no fix iterations needed"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 3"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 0"
    },
    {
      "icon": "🧪",
      "label": "Unit tests: 584 pass"
    },
    {
      "icon": "⏱️",
      "label": "Perf tests: 2 pass"
    },
    {
      "icon": "📝",
      "label": "Files changed: 16"
    }
  ],
  "quality": {
    "tier": "Platinum",
    "grade": "P"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 3,
    "summaries": [
      "Validator module docstring drift (mismatch reasons enumeration)",
      "Workflow test #5 fragile end-of-bullet heuristic",
      "--quest-mode help text lists values that have no effect"
    ]
  },
  "test_count": 586,
  "tests_added": 7,
  "files_changed": 16
}
```
<!-- celebration-data-end -->
