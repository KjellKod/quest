# Bug Report: Research/Analysis Quests Fall Through the Cracks

**Date:** 2026-04-13
**Severity:** Medium — workflow completes but degrades to ad-hoc execution
**Discovered during:** Cloudflare embedded function calling analysis quest

## What Happened

Claude was setup to deafult have `auto mode on`, this is fine, but auto mode means also that claude code will NOT ask questions, so this gave it enough incentive to just push forward and ignore the qust process/workflow steps. 

A user invoked `/quest` with a research task: compare Cloudflare's embedded function calling approach against our internal MCP architecture. The quest should have produced a structured analysis document through the planner → reviewer → builder → reviewer pipeline. Instead:

1. Router classified it correctly (confidence 0.85, complexity: substantial, risk: low)
2. Preflight passed
3. Route options were presented — but the orchestrator auto-selected "solo quest" without waiting for the user (auto mode tension, see below)
4. Quest folder was created with proper state.json
5. **The orchestrator then abandoned the workflow entirely** and performed the research inline, bypassing planner, reviewers, and the full agent pipeline
6. The state validator rejected phase transitions because expected artifacts (e.g., `review_plan-reviewer-a.md`) were missing

The user received a good analysis, but through an ad-hoc process with no plan review, no quality gate, and no quest structure.

## Root Causes

### 1. No quest type classification

The router evaluates 7 substance dimensions, all code-oriented:

| Dimension | Code Quest | Research Quest |
|-----------|-----------|----------------|
| Deliverable | Feature, fix, refactor | Analysis document, comparison, recommendation |
| Scope | Files, modules, systems affected | Sources to examine, repos to compare |
| Success Criteria | Tests pass, feature works | Questions answered, insights validated |
| Constraints | Dependencies, performance, compatibility | Time, depth, source availability |
| Input Artifacts | Specs, tickets, existing code | URLs, repos, colleague quotes, prior work |
| Testing | Unit, integration, smoke | Peer review, factual verification |
| Deployment | Rollout, migration, feature flags | Where to publish, who to share with |

The current dimensions *can* score a research quest (the one above got 0.85), but the downstream workflow doesn't know the deliverable is a document rather than code. There's no `quest_type` field to carry this signal forward.

### 2. Workflow language assumes code implementation

The workflow.md uses language that only maps to code quests:

- **"Hard Phase Gate (No Pre-Build Source Edits)"** — For a research quest, there are no source edits at all. The "build" is writing the analysis.
- **"Build Phase"** — Implies writing/modifying code. For research, this is "execute the research plan and write findings."
- **"Code Reviewers"** — The reviewer agents are prompted as code reviewers. They'd need different prompting for reviewing an analysis document.
- **"Fix Phase"** — Implies fixing code based on review feedback. For research, this is "address gaps, verify claims, strengthen weak arguments."

A planner agent receiving a research brief has to independently figure out that "build" means "write document" and "code review" means "analysis review." Some agents might make that leap; others might produce a code-oriented plan for a non-code task.

### 3. State validator has hard-coded artifact expectations

`quest_validate-quest-state.sh` requires `review_plan-reviewer-a.md` before allowing phase transitions. This is correct for code quests but creates a chicken-and-egg problem for research quests where the orchestrator might reasonably want to adapt the artifact set.

### 4. Auto mode creates tension with quest's interactive checkpoints

The system-level auto mode directive says:
> "Execute immediately. Minimize interruptions. Prefer action over planning."

The quest SKILL.md says:
> Present options: [1. Full quest] [2. Solo quest] [3. Cancel]

There's no explicit precedence rule. The orchestrator resolved this tension by auto-selecting, which violated the quest's design intent. This would affect any quest type, not just research.

## What Should Change

### A. Add `quest_type` to router output

Extend the router's output contract:

```json
{
  "route": "workflow",
  "confidence": 0.85,
  "risk_level": "low",
  "complexity": "substantial",
  "quest_type": "research",
  "reason": "...",
  "missing_information": []
}
```

Possible values: `implementation` (default), `research`, `documentation`, `investigation` (debugging/incident analysis).

The router can infer this from the deliverable dimension: if the deliverable is a document, comparison, analysis, or recommendation rather than a code change, set `quest_type` accordingly.

### B. Add workflow adaptation rules per quest type

In workflow.md, after the Quest Mode Check section, add:

```markdown
### Quest Type Adaptation

Read `quest_type` from the quest brief's router classification.
Default to `implementation` if missing.

When `quest_type != "implementation"`, the workflow adapts terminology
and agent prompting but follows the same phase structure:

| Phase | implementation | research / investigation |
|-------|---------------|--------------------------|
| Plan | Implementation plan | Research plan (sources, questions, structure) |
| Plan Review | Feasibility, architecture | Completeness, source coverage, question framing |
| Build | Write/modify code | Execute research, write analysis document |
| Code Review | Correctness, quality, security | Factual accuracy, argument strength, gaps |
| Fix | Fix code issues | Address review gaps, strengthen claims |

Agent prompts MUST include the quest_type so agents can adapt
their evaluation criteria.
```

### C. Differentiate artifact requirements by quest type

The state validator should accept different artifact shapes:

- `implementation` quests: plan.md, review_plan-reviewer-a.md, etc. (current behavior)
- `research` quests: plan.md, review_plan-reviewer-a.md still required, but the *content expectations* differ (the planner knows to produce a research plan, the reviewer knows to evaluate research completeness)

The artifact *file names* can stay the same — what changes is the agent prompting, not the file structure. This minimizes validator changes.

### D. Add explicit auto-mode override for quest decision points

In SKILL.md, after the route presentation blocks, add:

```markdown
**Important:** Quest decision points (route selection, workspace mode,
plan approval) always require user input regardless of auto mode.
These are intentional checkpoints in the quest design.
```

### E. Consider a "research quest" agent prompt variant

The planner, reviewer, and builder agents could receive a `quest_type` parameter that adjusts their behavior:

- **Planner (research):** Structure a research plan with sources, methodology, output format — not an implementation plan with files-to-change and testing strategy
- **Reviewer (research):** Evaluate source coverage, argument quality, factual accuracy — not code correctness and test coverage
- **Builder (research):** Execute the research plan, synthesize findings, write the deliverable — not implement code changes

This could be as simple as a paragraph prepended to the existing agent prompts based on quest_type, rather than entirely separate agent definitions.

## Impact

Without these changes, research quests will keep falling through to ad-hoc execution because:
1. The orchestrator sees code-oriented workflow steps and rationalizes skipping them
2. The agents receive code-oriented prompts and produce awkward plans for non-code work
3. The state validator blocks transitions when non-code artifacts don't match expected shapes

Research and analysis tasks are a legitimate and common use of the quest system (this one was invoked explicitly by the user with `/quest`). They deserve first-class support.

## Related

- The workspace-tools-router skill in internal-mcp-google-spreadsheet is an example of a non-code quest artifact (a routing document) that was built outside the quest system — possibly because quest didn't support non-code deliverables at the time.
- The Gmail roadmap (`docs/roadmaps/gmail-mcp-roadmap.md`) is another document that could have been produced through a research quest if the quest system supported it.
