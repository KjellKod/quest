# Quest Journal

Permanent record of quest runs. Each entry captures what was attempted, what shipped, and why abandoned quests were shelved.

## Timeline

| Date | Quest | Outcome |
|------|-------|---------|
| 2026-06-04 | [codex-subagent-dispatch-guardrails](codex-subagent-dispatch-guardrails_2026-06-04.md) | Fix Quest Codex-led role dispatch so Codex roles use local subagents, never Codex MCP. Context: In Codex-led Quest ru... |
| 2026-05-31 | [pre-pr-sync](pre-pr-sync_2026-05-31.md) | implement using $quest ideas/2026-05-30-pre-pr-freshness-and-force-push-guard.md |
| 2026-05-31 | [shared-quest-symlink](shared-quest-symlink_2026-05-31.md) | - **Agent:** Planner - **Model:** claude-opus-4-8 - **Date:** 2026-05-31 - **Quest ID:** shared-quest-symlink_2026-05... |
| 2026-05-30 | [code-review-adjudication](code-review-adjudication_2026-05-30.md) | **Completed (PR #124).** Enforce per-slot findings JSON (fail closed) + add an impartial code-review arbiter; brought code review to plan-phase adjudication parity. |
| 2026-05-22 | [sharpen-grounding](sharpen-grounding_2026-05-22.md) | Improve the standalone sharpen skill so its questions are grounded in repo evidence when local implementation facts m... |
| 2026-05-18 | [orchestration-override](orchestration-override_2026-05-18.md) | 1. New per-quest config file `.quest/<id>/orchestration.json` written at quest startup. This file is the single sourc... |
| 2026-05-15 | [pr-shepherd-operational-intake](pr-shepherd-operational-intake_2026-05-15.md) | `$quest implement ideas/2026-05-14-pr-shepherd-operational-intake.md` |
| 2026-05-13 | [ci-supply-chain-hardening](ci-supply-chain-hardening_2026-05-13.md) | Planned YAML for `.github/workflows/security.yml` (`workflow-guard` job): ```yaml workflow-guard: runs-on: ubuntu-lat... |
| 2026-05-03 | [persist-celebrations](persist-celebrations_2026-05-03.md) | Completed successfully. |
| 2026-05-02 | [installer-branch-conflict](installer-branch-conflict_2026-05-02.md) | `$quest https://github.com/KjellKod/quest/issues/110 fix this.` Issue: https://github.com/KjellKod/quest/issues/110 T... |
| 2026-04-29 | [configurable-quest-id-format](configurable-quest-id-format_2026-04-29.md) | Implement issue #106: configurable Quest ID format. Goal: Add a config option that keeps the current slug-first quest... |
| 2026-04-27 | [portable-pre-commit-review](portable-pre-commit-review_2026-04-27.md) | Completed successfully. |
| 2026-04-25 | [review-ergonomics-batch](review-ergonomics-batch_2026-04-25.md) | Completed successfully. |
| 2026-04-24 | [deep-ci-manifest](deep-ci-manifest_2026-04-24.md) | Impact: - Adds one canonical machine-readable artifact (`/tmp/deep_ci_context_manifest.json`) per run so selection/ch... |
| 2026-04-21 | [deep-ci-chunk-fallback](deep-ci-chunk-fallback_2026-04-21.md) | Completed successfully. |
| 2026-04-21 | [deep-ci-file-review](deep-ci-file-review_2026-04-21.md) | Completed successfully. |
| 2026-04-20 | [runner-cwd-path-hygiene](runner-cwd-path-hygiene_2026-04-20.md) | - Problem: CLI wrappers precompute `bridge_script` as `Path(args.cwd) / args.bridge_script` and then call runtime hel... |
| 2026-04-20 | [allowlist-pattern-hygiene](allowlist-pattern-hygiene_2026-04-20.md) | Harden allowlist command matching so role permissions no longer rely on dangerous bare command tokens or shell-prefix... |
| 2026-04-17 | [codex-skill-wrappers](codex-skill-wrappers_2026-04-17.md) | User wants Quest to fix Codex repo-local skill access so project skills such as `pr-shepherd`, `pr-assistant`, and `g... |
| 2026-04-16 | [celebration-review-intel](celebration-review-intel_2026-04-16.md) | Add two narrow, artifact-backed carry-over sections to Quest celebration/journal output so Phase 1 review intelligenc... |
| 2026-04-16 | [review-intelligence-canonical](review-intelligence-canonical_2026-04-16.md) | Implement Phase 1 of review-intelligence-canonical: normalize review findings and add a review-decisions stage betwee... |
| 2026-04-16 | [quest-dashboard-briefs](quest-dashboard-briefs_2026-04-16.md) | Dashboard quest detail pages now include the brief and celebration context, and archived journal pages were backfill... |
| 2026-04-15 | [claude-insights-ideas](claude-insights-ideas_2026-04-15.md) | > review ~/Documents/Evaluations/2026-04-15-claude-insights.html (you can also see the markdown, 2026-04-15-claude-in... |
| 2026-04-13 | [memory-docs-consolidation](memory-docs-consolidation_2026-04-13.md) | Completed successfully. |
| 2026-04-13 | [review-intel-canonical](review-intel-canonical_2026-04-13.md) | Consolidate Quest review hardening docs into one canonical review intelligence proposal. Use `ideas/2026-04-13-review... |
| 2026-04-13 | [feedback-intent-routing](feedback-intent-routing_2026-04-13.md) | Consolidate the Quest routing and feedback-intent ideas into one canonical delegation proposal. Use `ideas/2026-04-13... |
| 2026-04-13 | [prompt-surface-consolidation](prompt-surface-consolidation_2026-04-13.md) | > 3. Prompt Surface / Instruction Architecture > > Consolidate Quest prompt-surface improvement docs into one canonic... |
| 2026-04-12 | [caveman-review](caveman-review_2026-04-12.md) | Review completed. Decision: NO ACTION. |
| 2026-04-11 | [execution-discipline-guardrails](execution-discipline-guardrails_2026-04-11.md) | Completed successfully. |
| 2026-04-11 | [multi-cleanup](multi-cleanup_2026-04-11.md) | Multi-cleanup quest. Continuing on our existing branch. fix/quest-startup-outside-repo. In ideas, we have several thi... |
| 2026-04-08 | [extract-ci-review-python](extract-ci-review-python_2026-04-08.md) | Extract the embedded Python from .github/workflows/codex-ci-review.yml into a standalone script at .github/scripts/co... |
| 2026-04-07 | [ci-review-severity](ci-review-severity_2026-04-07.md) | User selection: full quest. |
| 2026-04-06 | [pdf-formatting](pdf-formatting_2026-04-06.md) | Improve doc2md's PDF converter to better preserve formatting from structured PDFs, using only existing pdfjs-dist pos... |
| 2026-03-31 | [branch-or-worktree-start](branch-or-worktree-start_2026-03-31.md) | **Agent:** Planner \| **Model:** claude-opus-4-6 \| **Date:** 2026-03-31 \| **Quest ID:** branch-or-worktree-start_20... |
| 2026-03-22 | [direct-cli-guidance](direct-cli-guidance_2026-03-22.md) | Claude Code permission prefixes (e.g. `["gh","api"]`, `["gh","pr"]`) only match when the command is the top-level exe... |
| 2026-03-21 | [quest-housekeeping-blitz](quest-housekeeping-blitz_2026-03-21.md) | Forensic sweep of stale quests, missing journal entries, broken archive/celebration automation, and a Codex sandbox p... |
| 2026-03-21 | [installer-codex-and-bridge-timeout](installer-codex-and-bridge-timeout_2026-03-21.md) | Installer handles Codex MCP setup; bridge timeout raised from 90s to 30 minutes. (PRs #78, #80) |
| 2026-03-20 | [atomic-state-transitions](atomic-state-transitions_2026-03-20.md) | Atomic state transitions close the validate+mutate footgun; mandatory presentation gate enforced. (PR #77) |
| 2026-03-20 | [readme-rewrite](readme-rewrite_2026-03-20.md) | README cut from 594 to ~150 lines; philosophy extracted to own doc; bridge architecture documented. (PR #76) |
| 2026-03-19 | [artifact-staging](artifact-staging_2026-03-19.md) | Explicit artifact staging before role execution; tighter runtime fallback; workspace-local artifacts. (PR #74) |
| 2026-03-17 | [codex-mcp-docs-cleanup](codex-mcp-docs-cleanup_2026-03-17.md) | Codex MCP docs overhauled, allowlist cleaned up, model dispatch reads from config. (PRs #70, #72, #73) |
| 2026-03-16 | [gpt-skill](gpt-skill_2026-03-16.md) | New /gpt skill for delegating tasks to Codex via MCP; co-author trailer labels updated. (PR #71) |
| 2026-03-13 | [codex-led-claude-runtime](codex-led-claude-runtime_2026-03-13.md) | First-class Codex-led Claude runtime path with bridge helpers and trust boundary preservation. (PR #68) |
| 2026-03-06 | [celebration-from-journal](celebration-from-journal_2026-03-06.md) | Quality tiers (Diamond→Cardboard), embedded celebration_data JSON in journals, dashboard tier badges with tooltips, agent model credits, test counts. Solo adventure. |
| 2026-03-05 | [celebrate-v2](celebrate-v2_2026-03-05.md) | Reworked celebration system with deep artifact reading, block-letter titles, achievements, quality scores, and cinematic movie credits. |
| 2026-03-05 | [pr-inline-commenting-playbook](pr-inline-commenting-playbook_2026-03-05.md) | Added a practical inline-commenting playbook to PR shepherd guidance, including tone, severity, and signature conventions. |
| 2026-03-04 | [quest-completion-animations](quest-completion-animations_2026-03-04.md) | Quest Completion Animation System with 4 animation styles, 38 passing tests, and integration into quest workflow. |
| 2026-02-28 | [opencode-model-suitability](opencode-model-suitability_2026-02-28.md) | Comprehensive model selection guide — 32 OpenCode models mapped to 6 Quest roles with evidence tags, benchmarks, and default/budget configs. |
| 2026-02-22 | [pr-body-gate](pr-body-gate_2026-02-22.md) | PR body structure CI gate — validates required headings on PRs. Phase 1 (warn-only) shipped; branch protection enforcement is a follow-up. |
| 2026-02-18 | [phase4-role-wiring](phase4-role-wiring_2026-02-18.md) | Relocated Quest role wiring to .skills/quest/agents with updated validators, docs, and clean dual-review completion. |
| 2026-02-15 | [state-validation-script](state-validation-script_2026-02-15.md) | Implemented quest_validate-quest-state.sh with 28-test harness, 10 workflow gates, and semantic handoff checks. Completes Phase 3 of architecture evolution. |
| 2026-02-15 | [context-leak-closure](context-leak-closure_2026-02-15.md) | Implemented handoff.json structured file pattern for all agents, context health logging, and completion compliance report. Completes Phase 2b of the architecture evolution. |
| 2026-02-13 | [dashboard-layout-redesign](dashboard-layout-redesign_2026-02-13.md) | Restructured dashboard to match target executive "Quest Intelligence" design — hero branding, 5 KPI cards, side-by-side charts, unified portfolio section, card content redesign. |
| 2026-02-12 | [dashboard-visual-polish](dashboard-visual-polish_2026-02-12.md) | Added ambient CSS glows, Chart.js doughnut and stacked area charts, gradient enhancements — dashboard goes from "works" to "looks great." |
| 2026-02-12 | [ci-python-quest](ci-python-quest_2026-02-12.md) | Added pytest CI workflow to run 36 Python tests on push/PR to main. |
| 2026-02-12 | [harden-url-rendering](harden-url-rendering_2026-02-12.md) | Fixed XSS vulnerability in dashboard URL rendering — added `_sanitize_url()` with scheme/pattern validation and HTML attribute escaping, 7 new tests. |
| 2026-02-11 | [codex-ci-review](codex-ci-review_2026-02-11.md) | Automated Codex CI code review workflow for PRs transitioning to ready-for-review. |
| 2026-02-09 | [thin-orchestrator](thin-orchestrator_2026-02-09.md) | Phase 2 of architecture evolution. Orchestrator passes paths, not content. Context stays lean. |
| 2026-02-12 | [dashboard-final-implementation](dashboard-final-implementation_2026-02-12.md) | **Abandoned.** First dashboard attempt — plan approved, build interrupted by model switch. Superseded by dashboard-v2. |
| 2026-02-12 | [dashboard-v2](dashboard-v2_2026-02-12.md) | Quest Dashboard: self-contained Python package generating static HTML dashboard with dark navy theme, three status sections, 29 tests. |
| 2026-02-09 | [handoff-contract-fix](handoff-contract-fix_2026-02-09.md) | Standardized `---HANDOFF---` contracts across all 6 role files and workflow prompts. |
| 2026-02-09 | [skill-strategy](skill-strategy_2026-02-09.md) | Research-only. Analyzed skill organization, distribution, and community patterns. |
| 2026-02-06 | [caching-strategy-exploration](caching-strategy-exploration_2026-02-06.md) | Research-only. Mapped 11 caching strategies for Quest. No code changes. |
| 2026-02-06 | [quest-delegation-gate](quest-delegation-gate_2026-02-06.md) | Decomposed monolithic SKILL.md into routing + delegation files. Intake gate enforces question-first for vague input. |
| 2026-02-05 | [quest-council-mode](quest-council-mode_2026-02-05.md) | **Abandoned.** Dual-plan council mode — plan approved but never built. Deferred for thin-orchestrator work. |
| 2026-02-05 | [weekly-update-check](weekly-update-check_2026-02-05.md) | Auto-check for Quest updates after quest completion. |
| 2026-02-04 | [interactive-plan-presentation](interactive-plan-presentation_2026-02-04.md) | Interactive plan walkthrough — users review phase-by-phase before build. |
| 2026-02-04 | [installer-script](installer-script_2026-02-04.md) | Unified installer script (`scripts/quest_installer.sh`) for any repo. |
| 2026-02-04 | [ci-quest-validation](ci-quest-validation_2026-02-04.md) | GitHub Actions CI and pre-commit hooks for quest artifact validation. |
| 2026-02-04 | [validate-and-launch](validate-and-launch_2026-02-04.md) | First-ever quest. Validated the extracted blueprint works, seeded `ideas/` directory. |
