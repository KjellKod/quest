# Scripts

Build and utility scripts for the Quest repository.

## Contents

| Script / Package | Purpose |
|------------------|---------|
| `quest_dashboard/` | Python package that generates a static HTML Quest Dashboard from journal entries and active quest state. See `quest_dashboard/README.md` for details. |
| `quest_runtime/` | Python package with Quest orchestration helpers (state updates, Claude bridge runner, handoff polling). |
| `quest_checks/` | Python package that provides the installed `quest-checks` CLI for running the standard Quest validation and test suite. |
| `quest_claude_bridge.py` | Thin transport bridge from the current host into Claude CLI for Codex-led Claude-designated Quest roles. |
| `quest_preflight.sh` | Checks second-model readiness before quest routing. Codex-led Claude probes now retain a recent successful host probe under `.quest/cache/` so later quest starts can reuse it. |
| `quest_claude_probe.py` | Probes the Claude bridge by requiring a real artifact write and `handoff.json` under the quest logs directory. |
| `quest_state.py` | Updates `.quest/<id>/state.json` consistently and refreshes `updated_at`. |
| `quest_startup_branch.py` | Creates the startup branch or worktree for a new quest from `.ai/allowlist.json` and returns machine-readable branch context JSON. |
| `quest_claude_runner.py` | Runs Claude-designated Quest roles through the additive Codex-host Claude adapter, using `scripts/quest_claude_bridge.py` as transport plus `bypassPermissions`, explicit `--add-dir` access, handoff polling, and `context_health.log` updates. Native Claude-led Quest behavior stays on `Task(...)`. |
| `quest_installer.sh` | Installs and updates Quest in any repository. Handles fresh installs, updates, and checksum-based change detection. |
| `quest_validate-quest-config.sh` | Validates quest configuration files (allowlist JSON schema, role markdown completeness). Used by pre-commit hooks and CI. |
| `quest_validate-handoff-contracts.sh` | Validates that role files use the correct handoff contract format (`---HANDOFF---` with STATUS/ARTIFACTS/NEXT/SUMMARY). |
| `quest_validate-manifest.sh` | Validates the file manifest and checksums for Quest installation integrity. |

## Quick Start

```bash
# Build the Quest Dashboard
python3 scripts/quest_dashboard/build_quest_dashboard.py

# Update quest state without hand-editing JSON
python3 scripts/quest_state.py --quest-dir .quest/<id> --phase plan_reviewed --status complete

# Prepare startup branch/worktree context for a new quest
python3 scripts/quest_startup_branch.py --slug feature-x --mode branch

# Run a Claude-designated role via the local bridge with file polling
python3 scripts/quest_claude_runner.py --quest-dir .quest/<id> --phase plan_review --agent plan-reviewer-a --iter 1 --prompt-file .quest/<id>/phase_01_plan/reviewer_a_prompt.txt --handoff-file .quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json

# Probe the Claude bridge with a real artifact + handoff write
python3 scripts/quest_claude_probe.py --quest-dir .quest/<id> --model opus

# Run the standard Quest validations and test suite
quest-checks

# Validate quest configuration
bash scripts/quest_validate-quest-config.sh

# Install/update Quest in a repository
bash scripts/quest_installer.sh
```
