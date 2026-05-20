---
title: Sharpen Context Grounding
purpose: Improve sharpening so each challenge question is grounded in the target repo's real code, tests, and workflow conventions.
audience:
  - quest-maintainers
  - skill-authors
  - quest-users
status: proposed
date: 2026-05-19
related:
  - .skills/sharpen/SKILL.md
  - .skills/quest/delegation/workflow.md
  - ideas/2026-04-29-research-fanout-skill.md
---

# Summary

The `sharpen` skill is valuable because it pressures a plan before build, but
its current execution posture can ask questions before it has enough local
context. That creates low-signal or misleading challenges: the question sounds
adversarial, but it is not grounded in what the repo already does.

One concrete failure mode came up during a Quest plan presentation. The user
asked to sharpen a feature plan and specifically wanted strong smoke tests. The
first sharpening pass questioned smoke-test strength without first inspecting
the repo's existing smoke runner. After a quick repo check, it was clear that
the project already had an executable live smoke suite with real spreadsheet
creation, focused scenario routing, artifact retention, cleanup behavior, and
coverage meta-tests. The better sharpening question was not "should we add real
smoke tests?" but "how should the new scenario extend the existing smoke suite
and scenario taxonomy?"

# Problem

Sharpening should not be a generic interview over the text of a plan. It should
challenge the plan against the actual implementation environment.

Today the skill says to skip questions that can be answered by reading the file
or another source, but it does not require enough repo-local discovery before
asking. In practice, the agent may:

- ask about facts that are discoverable in the codebase,
- miss established test or smoke conventions,
- frame repo-specific work as an open product decision,
- waste the user's attention correcting basic context,
- accidentally weaken trust in the plan review process.

# Proposal

Update `sharpen` so every question must pass a lightweight grounding check
before it is asked.

## Grounding Rule

Before asking a sharpening question, the agent should ask itself:

1. Is this question about a repo convention, existing test harness, command,
   API boundary, workflow, or current implementation behavior?
2. If yes, have I checked the relevant local files or commands?
3. Can I phrase the question with evidence from that check?

If the answer to question 2 is no, the agent should pause and inspect the repo
first. It should then ask a better question or skip the question entirely if the
repo already answers it.

## Minimum Prep For Quest Plan Sharpening

For a Quest plan, sharpening should do a short preparation pass before Q1:

- read the plan,
- identify the plan's main implementation surfaces,
- run targeted `rg` searches for named tools, scripts, tests, or workflows,
- inspect the most relevant existing files, not the whole repo,
- record 3-5 grounding facts in working notes,
- only then ask Q1.

This should stay lightweight. The point is not to redo planning. The point is
to avoid questions whose premise is already contradicted by local evidence.

## Question Quality Bar

Each sharpening question should include one of:

- a cited repo fact, such as "the repo already has `scripts/smoke_test.py` and
  `GS_SMOKE_ONLY`; should this feature add a focused scenario there?",
- an explicit uncertainty after a bounded check, such as "I found unit coverage
  but no live smoke path for this API; should build add one?",
- a clear design tradeoff that cannot be resolved from repo inspection.

Questions should avoid:

- asking whether something exists before checking,
- treating "optional but recommended" test language as acceptable when the repo
  has stronger established conventions,
- asking the user to supply facts the agent can cheaply discover,
- generic best-practice questions detached from the local implementation.

# Candidate Skill Changes

Add this section to `.skills/sharpen/SKILL.md`:

```markdown
## Context Grounding Before Questions

Before Q1, perform a bounded grounding pass when the artifact references a
repo, codebase, tests, scripts, workflows, tools, or implementation conventions.

1. Read the artifact.
2. Extract likely local anchors: file paths, commands, tool names, test names,
   modules, scripts, and acceptance criteria.
3. Use targeted searches or file reads to verify the highest-impact anchors.
4. Write down 3-5 grounding facts in working notes.
5. Ask only questions that remain unresolved after that check.

For each question, prefer phrasing that names the grounding fact or bounded
uncertainty. If a question can be answered by cheap repo inspection, inspect
first or skip it.
```

# Acceptance Criteria

- Sharpening a Quest plan that mentions tests inspects the relevant test or
  smoke harness before asking test-strategy questions.
- The first sharpening question is allowed to take longer when repo grounding is
  needed.
- At least one question in a grounded sharpening session references a concrete
  local file, command, or observed convention when that context materially
  affects the answer.
- The skill still asks one question at a time after the grounding pass.
- The grounding pass is bounded and targeted, not a broad repo inventory.

# Non-Goals

- Do not turn `sharpen` into a full planner or code reviewer.
- Do not require exhaustive repository analysis before every question.
- Do not spawn research agents by default.
- Do not ask the user to approve the grounding pass; it is part of asking a good
  question.

# Open Design Questions

- Should grounded facts be written to a temporary artifact during Quest runs, or
  kept only in the orchestrator's working context?
- Should `sharpen` have a hard prep budget, such as at most five targeted reads,
  before it asks Q1?
- Should Quest's plan-presentation path pass known implementation surfaces from
  `plan.md` into `sharpen`, so the skill has better starting anchors?
