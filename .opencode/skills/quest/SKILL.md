---
name: quest
description: Multi-agent orchestration with human approval gates - plan, review, build, fix with dual-model verification
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: multi-agent
---
# Quest Orchestration Skill (OpenCode)

This skill orchestrates a multi-agent workflow for planning, reviewing, building, and fixing features with human approval gates.

## Runtime Detection

This skill works in OpenCode. It detects the runtime by checking for OpenCode-specific configuration.

## Unverified Assumptions & Fallback Strategies

The following assumptions may vary by environment. Use fallbacks when needed:

### Agent Path Syntax
- **Primary:** Use `Task` tool with direct `subagent_type` parameter
- **Fallback:** If `subagent_type` not supported, try `agent` parameter or invoke skill directly

### subagent_type Values
- **Assumed values:** `planner`, `plan-reviewer`, `arbiter`, `builder`, `code-reviewer`, `fixer`
- **Fallback:** If specific subagent unavailable, use generic `agent` with custom prompt

### Concurrent Execution
- **Primary:** Invoke two `Task` calls sequentially (OpenCode may not support true parallel)
- **Fallback:** Run sequentially, noting which review came from which model tier

### model_tier
- **Primary:** Request specific tiers via prompt instructions ("use advanced model")
- **Fallback:** Trust OpenCode's model routing, note in state if uncertain

## Quick Reference

- **Quest folder:** `.quest/<quest_id>/`
- **State file:** `.quest/<quest_id>/state.json`
- **Run:** `/quest "your task description"`

## Workflow

Quest follows this phase flow:

```
Intake → Plan → [Dual Review + Arbiter] → [Human Gate] → Build → Code Review → [Fix Loop] → Done
```

### Phase 1: Intake

Evaluate the user's input:
- If input is detailed (has intent, constraints, acceptance criteria): proceed to planning
- If input is thin: ask 1-3 clarifying questions (max 10 total)
- Create quest folder: `.quest/<slug>_YYYY-MM-DD__HHMM/`

### Phase 2: Planning

1. Use `Task` tool to invoke the Planner agent:
   ```
   Task(
     subagent_type="planner",
     description="Create implementation plan",
     prompt="You are the Planner agent for Quest. Create a detailed implementation plan.

## Task
[user task description from intake]

## Context
- Quest ID: <id>
- Runtime: OpenCode
- Review process: Dual-model (per model_routing.opencode in .ai/allowlist.json)
- Human approval required before building

## Output Requirements
Write the plan to: .quest/<id>/phase_01_plan/plan.md
Write handoff to: .quest/<id>/phase_01_plan/handoff.json

## Plan Template
Include these sections:

1. **Overview** - Brief description of the approach (2-3 sentences)

2. **Requirements Analysis** - Break down user requirements into specific items

3. **File Changes** - Specific files to create/modify:
   - Use absolute paths from repo root
   - Note if files are new or existing

4. **Implementation Steps** - Numbered sequence:
   - Step 1: [specific action]
   - Step 2: [specific action]
   - ...

5. **Test Verification** - How to verify the implementation:
   - Which tests to run
   - Manual verification steps
   - Expected outcomes

6. **Risk Assessment** - Potential issues:
   - Technical risks
   - Dependencies
   - Edge cases to handle

7. **Assumptions** - What you're assuming works/exists

Be specific and actionable. Reviewers will evaluate feasibility."
   )
   ```
2. Write plan to: `.quest/<id>/phase_01_plan/plan.md`
3. Write handoff to: `.quest/<id>/phase_01_plan/handoff.json`

### Phase 3: Plan Review (Dual Model)

Invoke TWO reviewers concurrently using separate Task calls:

**Reviewer A (Primary - advanced tier):**
```
Task(
  subagent_type="plan-reviewer",
  description="Review plan - Reviewer A",
  prompt="You are Reviewer A (Advanced Model) for Quest plan review.

## Your Role
Evaluate the implementation plan thoroughly. Your review helps ensure quality before human approval.

## Plan Location
Read: .quest/<id>/phase_01_plan/plan.md

## Review Criteria (evaluate each thoroughly)

### 1. Completeness
- Are all user requirements addressed?
- Any missing functionality?
- Edge cases considered?

### 2. Feasibility
- Can this actually be implemented?
- Are dependencies available?
- Is the timeline realistic?

### 3. Clarity
- Are steps specific and actionable?
- Is it clear what each file change entails?
- Can another developer follow this plan?

### 4. Testing & Verification
- Are test approaches specified?
- Can we verify success?
- Are acceptance criteria clear?

### 5. Risks
- Technical risks?
- Dependency risks?
- What could go wrong?

## Output
Write your detailed review to: .quest/<id>/phase_01_plan/review_reviewer_a.md

## Format
```
# Plan Review - Reviewer A

## Summary
[1-2 sentences on overall quality]

## Completeness
- [issue 1]
- [issue 2]

## Feasibility
- [assessment]

## Clarity
- [issues or positives]

## Testing
- [coverage assessment]

## Risks
- [list risks]

## Decision
APPROVE | ITERATE

## Feedback (if ITERATE)
- [specific, actionable feedback for planner]
```
"
)
```

**Reviewer B (Secondary - standard tier):**
```
Task(
  subagent_type="plan-reviewer",
  description="Review plan - Reviewer B", 
  prompt="You are Reviewer B (Standard Model) for Quest plan review.

## Your Role
Provide an independent evaluation of the implementation plan. Look for gaps and issues Reviewer A might miss.

## Plan Location
Read: .quest/<id>/phase_01_plan/plan.md

## Review Criteria (evaluate each thoroughly)

### 1. Completeness
- Are all user requirements addressed?
- Any missing functionality?
- Edge cases considered?

### 2. Feasibility
- Can this actually be implemented?
- Are dependencies available?
- Is the timeline realistic?

### 3. Clarity
- Are steps specific and actionable?
- Is it clear what each file change entails?
- Can another developer follow this plan?

### 4. Testing & Verification
- Are test approaches specified?
- Can we verify success?
- Are acceptance criteria clear?

### 5. Risks
- Technical risks?
- Dependency risks?
- What could go wrong?

## Output
Write your detailed review to: .quest/<id>/phase_01_plan/review_reviewer_b.md

## Format
```
# Plan Review - Reviewer B

## Summary
[1-2 sentences on overall quality]

## Completeness
- [issue 1]
- [issue 2]

## Feasibility
- [assessment]

## Clarity
- [issues or positives]

## Testing
- [coverage assessment]

## Risks
- [list risks]

## Decision
APPROVE | ITERATE

## Feedback (if ITERATE)
- [specific, actionable feedback for planner]
```
"
)
```

### Phase 4: Arbiter

Invoke Arbiter to synthesize reviews:
```
Task(
  subagent_type="arbiter",
  description="Synthesize plan reviews",
  prompt="You are the Arbiter for Quest. Synthesize the two plan reviews and make a final decision.

## Your Role
Consider both reviews holistically. You may agree with one, both, or neither. Your job is quality control.

## Input Reviews
- .quest/<id>/phase_01_plan/review_reviewer_a.md (Advanced model)
- .quest/<id>/phase_01_plan/review_reviewer_b.md (Standard model)

## Original Plan
Read: .quest/<id>/phase_01_plan/plan.md

## Decision Criteria

### APPROVE if:
- Both reviewers approve
- Or one approves and other's concerns are minor/addressable in build
- Plan is feasible, complete, and actionable

### ITERATE if:
- Both reviewers want iteration
- One reviewer has blocking concerns
- Critical gaps or risks identified

## Output
Write decision to: .quest/<id>/phase_01_plan/arbiter.md

## Format
```
# Arbiter Decision - Plan Review

## Review A Summary
[Key points from Reviewer A]

## Review B Summary
[Key points from Reviewer B]

## Synthesis
[Your analysis of where reviews agree/disagree]

## Decision
APPROVE | ITERATE

## Reasoning
[Explain your decision]

## Feedback to Planner (if ITERATE)
- [specific, actionable items to address]
```
"
)
```

### Phase 5: Human Gate

Present the plan and arbiter verdict to the user. Wait for explicit approval before proceeding to build.

### Phase 6: Build

Invoke Builder to implement:
```
Task(
  subagent_type="builder",
  description="Implement the plan",
  prompt="You are the Builder agent for Quest. Implement the approved plan.

## Approved Plan
Read: .quest/<id>/phase_01_plan/plan.md

## Quest Context
- Quest ID: <id>
- Runtime: OpenCode
- Human already approved this plan
- Output directory: .quest/<id>/phase_02_implementation/

## Implementation Rules

1. **Follow the plan exactly** - Don't add extra features
2. **Write all output** to: .quest/<id>/phase_02_implementation/
3. **Match file paths** exactly as specified in plan
4. **Test your implementation** as specified in plan
5. **Document any deviations** from plan in implementation notes

## Implementation Notes Template
Create: .quest/<id>/phase_02_implementation/implementation_notes.md
```
# Implementation Notes

## Files Created/Modified
- [list files]

## Implementation Summary
[What was implemented]

## Testing Performed
- [tests run]
- [results]

## Any Deviations from Plan
- [if any, explain why]

## Blockers or Issues
- [if any]
```
"
)
```

### Phase 7: Code Review (Dual Model)

Invoke TWO code reviewers concurrently:

**Reviewer A:**
```
Task(
  subagent_type="code-reviewer",
  description="Review code - Reviewer A",
  prompt="You are Reviewer A (Advanced Model) for Quest code review.

## Your Role
Evaluate the implementation for correctness, security, and quality. Your review determines if we're ready to complete.

## Implementation Location
Review: .quest/<id>/phase_02_implementation/

## Original Plan
Read: .quest/<id>/phase_01_plan/plan.md

## Review Criteria

### 1. Correctness
- Does the implementation match the plan?
- Does it solve the original problem?
- Any bugs or logic errors?

### 2. Security
- Any vulnerabilities?
- Input validation?
- Secret handling?

### 3. Performance
- Any performance concerns?
- Efficient algorithms?
- Resource leaks?

### 4. Maintainability
- Is code clean and readable?
- Good variable/function names?
- Appropriate abstractions?

### 5. Testing
- Are tests adequate?
- Edge cases covered?
- Can we verify it works?

## Output
Write review to: .quest/<id>/phase_03_review/review_reviewer_a.md

## Format
```
# Code Review - Reviewer A

## Summary
[Overall assessment]

## Correctness
- [issues]

## Security
- [issues]

## Performance
- [concerns]

## Maintainability
- [feedback]

## Testing
- [assessment]

## Decision
APPROVE | NEEDS_FIX

## Issues to Fix (if NEEDS_FIX)
- [specific, actionable items]
```
"
)
```

**Reviewer B:**
```
Task(
  subagent_type="code-reviewer",
  description="Review code - Reviewer B",
  prompt="You are Reviewer B (Standard Model) for Quest code review.

## Your Role
Provide independent code review. Look for issues Reviewer A might miss.

## Implementation Location
Review: .quest/<id>/phase_02_implementation/

## Original Plan
Read: .quest/<id>/phase_01_plan/plan.md

## Review Criteria

### 1. Correctness
- Does the implementation match the plan?
- Does it solve the original problem?
- Any bugs or logic errors?

### 2. Security
- Any vulnerabilities?
- Input validation?
- Secret handling?

### 3. Performance
- Any performance concerns?
- Efficient algorithms?
- Resource leaks?

### 4. Maintainability
- Is code clean and readable?
- Good variable/function names?
- Appropriate abstractions?

### 5. Testing
- Are tests adequate?
- Edge cases covered?
- Can we verify it works?

## Output
Write review to: .quest/<id>/phase_03_review/review_reviewer_b.md

## Format
```
# Code Review - Reviewer B

## Summary
[Overall assessment]

## Correctness
- [issues]

## Security
- [issues]

## Performance
- [concerns]

## Maintainability
- [feedback]

## Testing
- [assessment]

## Decision
APPROVE | NEEDS_FIX

## Issues to Fix (if NEEDS_FIX)
- [specific, actionable items]
```
"
)
```

### Phase 8: Fix Loop (if needed)

If reviewers find issues:

1. Invoke Arbiter to decide if fixes needed
2. If fixes needed, invoke Fixer:
   ```
   Task(
     subagent_type="fixer",
     description="Fix review issues",
     prompt="You are the Fixer agent for Quest. Address the issues identified in code review.

## Reviews to Address
- .quest/<id>/phase_03_review/review_reviewer_a.md
- .quest/<id>/phase_03_review/review_reviewer_b.md

## Original Plan
Read: .quest/<id>/phase_01_plan/plan.md

## Implementation
The implementation is at: .quest/<id>/phase_02_implementation/

## Your Task

1. **Read both reviews** carefully
2. **Identify all issues** that need fixing
3. **Make the necessary changes** to implementation files
4. **Verify fixes work** - run tests, check functionality
5. **Document fixes** in implementation notes

## Fix Rules
- Address ALL issues raised (unless arbiter says some can be deferred)
- Don't introduce new issues
- Don't change functionality beyond what's needed to fix issues

## Output
After fixing, update: .quest/<id>/phase_02_implementation/implementation_notes.md

Add a section:
```
## Fixes Applied (Iteration N)
- [issue 1]: [what was fixed]
- [issue 2]: [what was fixed]
```
   )
   ```
3. Loop back to Code Review (max 3 iterations)

### Phase 9: Complete

- Update state to complete
- Create journal entry in `docs/quest-journal/`
- Show summary to user

## Tool Usage

When executing Quest in OpenCode:

1. Use `Task` tool for all subagent invocations
2. Use `subagent_type` parameter to specify which agent
3. Track state in `.quest/<id>/state.json`
4. Write artifacts to the quest folder

## Error Handling

### Task Tool Failures
If a subagent Task fails:
1. Check error message for specifics
2. Try again with simplified prompt
3. If persistent, proceed without that subagent and note in state

### Missing Subagent Types
If `subagent_type` not recognized:
1. Try generic `Task` with full prompt context
2. Include agent role description in prompt
3. Note fallback in state file

### Reviewer Disagreements
If reviewers conflict significantly:
1. Let arbiter decide
2. If arbiter also uncertain, defer to human gate
3. Present both views to user for input

### Implementation Failures
If build fails:
1. Document failure in implementation_notes.md
2. Report to user immediately
3. Don't proceed to code review until fixed

### Quest State Recovery
If interrupted:
1. Read `.quest/<id>/state.json` to find current phase
2. Resume from last complete phase
3. Verify artifacts exist before proceeding

## State Management

State file format (`.quest/<id>/state.json`):
```json
{
  "quest_id": "feature-x_2026-02-27__1200",
  "phase": "intake|planning|plan_review|arbiter|human_gate|building|code_review|fixing|complete",
  "status": "pending|in_progress|complete|blocked",
  "plan_iteration": 1,
  "fix_iteration": 0,
  "runtime": "opencode"
}
```

## Configuration

Edit `.ai/allowlist.json` to configure:
- `role_permissions` - file and bash access per role (shared across all runtimes)
- `model_routing.opencode` - which tool, subagent, and model tier to use for each slot
- `model_tiers.opencode` - map tier names (quick, standard, advanced) to concrete model IDs

Reviewer A/B models are determined by `model_routing.opencode.reviewer_a` / `model_routing.opencode.reviewer_b` in `.ai/allowlist.json`.

## Notes

- This skill is designed for OpenCode and uses OpenCode-native patterns
- Model routing and permissions are shared via the unified `.ai/allowlist.json` (v3)
- Dual-model review works by invoking two separate subagents with different model tiers as configured in `model_routing.opencode`
