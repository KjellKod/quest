# Idea: Document Solo Quest Mode and Complexity Routing

## Problem

The quest system now supports three routes (manual, solo, workflow) selected via a complexity x risk matrix, but the user-facing documentation (`docs/guides/quest_input_routing.md`) still describes the old two-path model (questioning vs. straight-to-planning). Users have no guide explaining:

- What solo mode is and how it differs from full workflow
- When the router recommends each route
- The complexity x risk matrix
- How to override the recommendation
- Solo mode's constraints (Gold tier ceiling, single reviewer, capped fix iterations)

## Deliverable

Update `docs/guides/quest_input_routing.md` to cover the full routing model:

1. **Update the ASCII flow diagram** (lines 7-19) to show four paths: resume, manual, solo, workflow (with questioner as a gate, not a path)
2. **Add a "Complexity Routing" section** after "How Quest Evaluates Your Input" explaining:
   - The three complexity levels (trivial, moderate, substantial) with examples
   - The complexity x risk matrix table showing which combination leads to which route
   - What each route means in practice
3. **Add a "Solo Mode" section** explaining:
   - Single plan reviewer (A only), no arbiter, single code reviewer (A only)
   - Fix iterations capped at min(2, allowlist max)
   - Quality tier ceiling at Gold (Diamond and Platinum not achievable)
   - "Solo Adventurer" achievement badge
4. **Add an "Override" section** explaining:
   - The router recommends, the human chooses
   - Every route presents alternatives (e.g., solo recommended but user can pick full workflow or manual)
   - Show the override prompt format users will see
5. **Update the examples section** with solo-specific examples:
   - A moderate/low task that routes to solo
   - A user overriding solo to full workflow
   - A trivial/low task that routes to manual
6. **Update the file structure section** to note the router now includes complexity assessment

## Scope

- Primary file: `docs/guides/quest_input_routing.md`
- Reference (read-only): `.skills/quest/SKILL.md` (route presentation format), `.skills/quest/delegation/router.md` (matrix, complexity levels), `.skills/quest/delegation/workflow.md` (solo conditionals), `.ai/allowlist.json` (solo config)

## Success Criteria

- A user reading the guide understands all three routes without reading the skill internals
- The complexity x risk matrix is clearly presented
- Solo mode constraints are documented with rationale (lighter process = lower ceiling)
- Override mechanism is clear with concrete examples
- Existing content about questioning phase and 7 dimensions is preserved (still accurate)

## Constraints

- Keep the guide user-facing and conversational (match existing tone)
- No code changes — documentation only
- Preserve backward compatibility of the guide structure (existing section anchors)
