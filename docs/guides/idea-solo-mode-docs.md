# Idea: Document Solo Quest Mode and Complexity Routing

## Problem

The quest system now supports three routes (manual, solo, workflow) selected via a complexity x risk matrix, but the user-facing documentation still describes only the full dual-review workflow. Two files need updates:

1. **`docs/guides/quest_input_routing.md`** — still describes the old two-path model (questioning vs. straight-to-planning), no mention of complexity routing or solo/manual
2. **`README.md`** — ASCII diagram, feature list, agent roles, and orchestrator description all assume full workflow only

Users have no documentation explaining:
- What solo mode is and how it differs from full workflow
- When the router recommends each route
- The complexity x risk matrix
- How to override the recommendation
- Solo mode's constraints (Gold tier ceiling, single reviewer, capped fix iterations)

## Deliverable

### File 1: `docs/guides/quest_input_routing.md`

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

### File 2: `README.md`

1. **"What Quest delivers today" section** (~line 47): Add bullet for complexity routing and solo mode
2. **ASCII diagram** (~lines 91-104): Add a solo variant or note that solo skips the second reviewer and arbiter. Consider a side-by-side or stacked diagram showing both flows
3. **"What is Quest?" paragraph** (~line 87): Currently says "Two different models review independently, an arbiter filters nitpicks" — add that solo mode uses a single reviewer for lighter tasks
4. **"Key Features" section** (~lines 425-433): Add bullet for smart complexity routing (manual/solo/workflow based on task size and risk)
5. **"The Quest Party: Agent Roles" section** (~lines 519-549): Note which roles are skipped in solo mode (Reviewer B, Arbiter). Could add a small table: role × mode showing active/skipped
6. **"How the Orchestrator Works" section** (~lines 435-478): The parallel dual-review diagram only shows full workflow. Add a note or second diagram showing solo's simpler single-reviewer dispatch
7. **"Quest scales from simple to complex" examples** (~lines 244-261): The examples don't show route selection. Add a solo example showing the route recommendation prompt

## Scope

- Primary files: `docs/guides/quest_input_routing.md`, `README.md`
- Reference (read-only): `.skills/quest/SKILL.md` (route presentation format), `.skills/quest/delegation/router.md` (matrix, complexity levels), `.skills/quest/delegation/workflow.md` (solo conditionals), `.ai/allowlist.json` (solo config)

## Success Criteria

- A user reading either the README or the routing guide understands all three routes without reading the skill internals
- The complexity x risk matrix is clearly presented in the routing guide
- Solo mode constraints are documented with rationale (lighter process = lower ceiling)
- Override mechanism is clear with concrete examples
- README accurately describes both full and solo workflows
- Existing content about questioning phase and 7 dimensions is preserved (still accurate)
- Existing README tone and structure is preserved

## Constraints

- Keep both files user-facing and conversational (match existing tone)
- No code changes — documentation only
- Preserve backward compatibility of section anchors and structure
- Don't over-document solo — it's a lighter version of the same pipeline, not a separate system
