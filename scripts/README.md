# Scripts

Build and utility scripts for the Quest repository.

## Contents

| Script / Package | Purpose |
|------------------|---------|
| `quest_dashboard/` | Python package that generates a static HTML Quest Dashboard from journal entries and active quest state. See `quest_dashboard/README.md` for details. |
| `quest_runtime/` | Python package with Quest orchestration helpers (state updates, Claude transport runner, handoff polling). |
| `quest_runtime/review_intelligence.py` | Canonical review-finding schema validation, dedupe/merge helpers, decision backlog policy, deferred JSONL append, and planner backlog scan matching. |
| `quest_runtime/pr_review_cycle.py` | PR-cycle helpers for canonical intake normalization, actionable batch construction, validation-step selection, loop-stop classification, and cap retagging. |
| `quest_checks/` | Python package that provides the installed `quest-checks` CLI for running Quest validators. |
| `quest_claude_bg_run.py` | Standalone background-agent transport runner for `claude --bg`; returns a structured envelope and keeps Quest-specific policy out of the transport. |
| `quest_claude_bridge.py` | Explicit API-metered bridge transport from the current host into Claude CLI for Codex-led Claude-designated Quest roles. |
| `quest_preflight.sh` | Checks second-model readiness before quest routing. Codex-led Claude probes now retain a recent successful host probe under `.quest/cache/` so later quest starts can reuse it. |
| `quest_claude_probe.py` | Probes a Claude transport by requiring a real artifact write and `handoff.json` under the quest logs directory. |
| `quest_state.py` | Updates `.quest/<id>/state.json` consistently and refreshes `updated_at`. |
| `quest_plan_iteration.py` | Seals immutable plan iterations, guards cleanup, and binds automatic refinement verdicts to the next Planner run. |
| `quest_startup_branch.py` | Creates the startup branch or worktree for a new quest from `.ai/allowlist.json` and returns machine-readable branch context JSON. |
| `quest_claude_runner.py` | Runs Claude-designated Quest roles through the additive Codex-host Claude adapter, using background-agent or explicit bridge transport plus `bypassPermissions`, explicit `--add-dir` access, declared `--artifact-subset findings-only` Arbiter retries, handoff polling, and `context_health.log` updates. Native Claude-led Quest behavior stays on `Task(...)`. |
| `quest_review_intelligence.py` | CLI wrapper around review-intelligence helpers (`validate-findings`, `merge-findings`, `build-backlog`, `append-deferred`, `scan-backlog`, `normalize-pr-intake`, `select-batch-validation`, `build-fix-batches`, `classify-pr-stop`). |
| `quest_pr_shepherd_checkout.py` | Inspection-first PR target helper; reports current/target branch state and only runs `gh pr checkout` with `--apply`. |
| `quest_pr_shepherd_collect_intake.py` | Collects compact records-shaped PR shepherd intake for normalization. |
| `quest_pr_shepherd_annotate_scope.py` | Annotates normalized findings with deterministic `in_diff` or `unknown` changed-line scope. |
| `quest_pr_shepherd_post_reply.py` | Appends shepherd markers and posts or dry-runs thread replies / marker-owned summary comments. |
| `quest_pr_shepherd_fetch_failed_logs.py` | Fetches failed run logs with deterministic head/tail truncation and unavailable diagnostics. |
| `quest_select_tests.py` | Thin CLI that returns ordered `validation_steps` for a single canonical finding (Level 0/1/2 test-selection heuristic). |
| `quest_installer.sh` | Installs and updates Quest in any repository. Handles fresh installs, updates, and checksum-based change detection. |
| `quest_validate-quest-config.sh` | Validates quest configuration files (allowlist JSON schema, role markdown completeness). Used by pre-commit hooks and CI. |
| `quest_validate-handoff-contracts.sh` | Validates that role files use the correct handoff contract format (`---HANDOFF---` with STATUS/ARTIFACTS/NEXT/SUMMARY). |
| `quest_validate-manifest.sh` | Validates the file manifest and checksums for Quest installation integrity. |

## Quick Start

```bash
# Build the Quest Dashboard
python3 scripts/quest_dashboard/build_quest_dashboard.py

# Perform a validated state transition without hand-editing JSON
python3 scripts/quest_state.py --quest-dir .quest/<id> --transition plan_reviewed --status complete --expect-phase plan

# Human-requested replanning before Build, run in this exact order
python3 scripts/quest_plan_iteration.py snapshot --quest-dir .quest/<id> --iteration <N>
python3 scripts/quest_state.py --quest-dir .quest/<id> --record-user-replan-feedback --source <walkthrough|sharpen|build_gate|resume_instruction> --feedback-file <prepared-input-file> --expect-phase <current>
python3 scripts/quest_state.py --quest-dir .quest/<id> --transition plan --status in_progress --expect-phase <current>

# Prepare startup branch/worktree context for a new quest
python3 scripts/quest_startup_branch.py --slug feature-x --mode branch

# Run a Claude-designated role via the configured Claude transport with file polling
python3 scripts/quest_claude_runner.py --quest-dir .quest/<id> --phase plan_review --agent plan-reviewer-a --iter 1 --prompt-file .quest/<id>/phase_01_plan/reviewer_a_prompt.txt --handoff-file .quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json --model claude --transport background-agent

# Retry invalid Arbiter findings into separate scratch files, preserving the rejected findings and valid verdict as inputs
python3 scripts/quest_claude_runner.py --quest-dir .quest/<id> --phase plan_review --agent arbiter --iter <N> --prompt-file <retry-prompt> --handoff-file .quest/<id>/phase_01_plan/handoff_arbiter.retry.json --artifact-subset findings-only --model <model> --transport background-agent

# Probe the Claude background-agent transport with a real artifact + handoff write
python3 scripts/quest_claude_probe.py --quest-dir .quest/<id> --model claude --transport background-agent

# Validate canonical findings JSON
python3 scripts/quest_review_intelligence.py validate-findings --input .quest/<id>/phase_03_review/review_findings.json

# PR review pipeline — order matters: validation selection MUST run
# before batching or build-fix-batches falls back to one-item batches.
#
# 1. Normalize PR intake into canonical findings
python3 scripts/quest_review_intelligence.py normalize-pr-intake --input /tmp/pr_intake.json --output /tmp/review_findings.json

# 2. Build the decision backlog
python3 scripts/quest_review_intelligence.py build-backlog --findings /tmp/review_findings.json --output /tmp/review_backlog.json

# 3. Populate validation_steps on every actionable backlog item IN PLACE
python3 scripts/quest_review_intelligence.py select-batch-validation --backlog /tmp/review_backlog.json --repo-inventory /tmp/repo_inventory.json

# 4. Build actionable non-overlapping batches (now sees real validation signatures)
python3 scripts/quest_review_intelligence.py build-fix-batches --backlog /tmp/review_backlog.json --output /tmp/fix_batches.json

# 5. Classify stop conditions and enforce cap retagging when needed
python3 scripts/quest_review_intelligence.py classify-pr-stop --ci-state failing --actionable 2 --iteration 3 --backlog /tmp/review_backlog.json

# PR shepherd operational intake
python3 scripts/quest_pr_shepherd_checkout.py 123 --json
python3 scripts/quest_pr_shepherd_checkout.py 123 --apply --json
python3 scripts/quest_pr_shepherd_fetch_failed_logs.py --run-id 987654 --check-name unit --raw-log-url https://github.com/OWNER/REPO/actions/runs/987654 --output /tmp/failed_log.json
python3 scripts/quest_pr_shepherd_collect_intake.py --pr 123 --output /tmp/pr_intake.json
python3 scripts/quest_pr_shepherd_collect_intake.py --pr 123 --failed-log-summary /tmp/failed_log.json --output /tmp/pr_intake.json
python3 scripts/quest_review_intelligence.py normalize-pr-intake --input /tmp/pr_intake.json --output /tmp/review_findings.json
python3 scripts/quest_pr_shepherd_annotate_scope.py --pr 123 --findings /tmp/review_findings.json --output /tmp/review_findings_scoped.json
python3 scripts/quest_pr_shepherd_post_reply.py --pr 123 --thread-id 456 --body "Fixed in the latest push."
python3 scripts/quest_review_intelligence.py classify-pr-stop --ci-state green --actionable 0 --iteration 1 --pass-facts /tmp/pass_facts.json

# Debug: select targeted validation steps for a single finding (single-finding preview)
python3 scripts/quest_select_tests.py --finding /tmp/finding.json --repo-inventory /tmp/repo_inventory.json --output /tmp/validation_steps.json

# Run the installed Quest validations and smoke tests
quest-checks

# Validate quest configuration
bash scripts/quest_validate-quest-config.sh

# Install/update Quest in a repository
bash scripts/quest_installer.sh
```
