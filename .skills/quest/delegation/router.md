# Input Router

Classify user input to determine whether it has enough substance for planning or needs a questioning phase first.

## Substance Evaluation Dimensions

Evaluate the user's input against these 7 dimensions. For each, assess as **present**, **partial**, or **missing**.

### 1. Deliverable
What concrete thing is being built or changed? Is there a clear output (feature, fix, refactor, integration)?

- **Present:** "Add email validation to the registration form"
- **Partial:** "Improve the registration flow"
- **Missing:** "Make things better"

### 2. Scope
What parts of the system are affected? What is explicitly out of scope?

- **Present:** "Changes to src/components/Form.tsx and src/services/validation.ts only"
- **Partial:** "Something in the frontend"
- **Missing:** No indication of where changes should happen

### 3. Success Criteria
How will we know it is done? What should a reviewer check?

- **Present:** "Email validated on blur, password requires 8+ chars with uppercase, errors shown inline"
- **Partial:** "It should work correctly"
- **Missing:** No definition of done

### 4. Constraints
Technical limitations, dependencies, performance targets, compatibility requirements?

- **Present:** "No new dependencies, must support IE11, response time under 200ms"
- **Partial:** "Keep it simple"
- **Missing:** No constraints mentioned

### 5. Input Artifacts
Referenced specs, docs, tickets, URLs, files, or existing code?

- **Present:** "See spec in docs/design/auth-flow.md" or "Per ticket PROJ-1234"
- **Partial:** "Based on the discussion we had"
- **Missing:** No references

### 6. Testing Expectations
How should this be tested? What coverage is expected?

- **Present:** "Unit tests for validation logic, integration test for form submission"
- **Partial:** "Should have tests"
- **Missing:** No mention of testing

### 7. Deployment Expectations
Any rollout, migration, or compatibility concerns?

- **Present:** "Needs database migration, feature flag for gradual rollout"
- **Partial:** "Should be backward compatible"
- **Missing:** No deployment considerations

## Complexity Assessment

After evaluating the 7 substance dimensions, assess the **complexity** of the task:

| Level | Signal | Examples |
|-------|--------|----------|
| **trivial** | Single file, documentation, config change, idea doc, small bug fix, adding a test | "Fix typo in README", "Add env var to config", "Write idea doc for feature X" |
| **moderate** | Multi-file change within one module, new function/endpoint, focused refactor | "Add validation to registration form", "Refactor logger to use structured output" |
| **substantial** | Cross-cutting changes, new module, architecture change, security-sensitive, multi-system integration | "Add OAuth2 flow", "Migrate database schema", "Implement plugin system" |

## Decision Logic

### Step 1: Questioner Gate (unchanged)

Route to `questioner` first if the input lacks substance for planning. This gate runs before complexity routing.

Routing rule: route `questioner` if confidence < 0.70, else proceed to Step 2.

Confidence drivers (not strict math, but a clear rule):
- Confidence >= 0.70 if no more than 2 dimensions are missing, AND deliverable is present, AND scope is at least partial
- Otherwise confidence < 0.70 → `questioner`

Risk adjustment: high `risk_level` should bias toward `questioner` even if the dimension count suggests proceeding. When the task domain is inherently high-risk (migrations, security, payments, data loss scenarios), lower the confidence score or route to `questioner` to ensure thorough information gathering.

Questioner signals:
- Deliverable is vague or missing
- Both scope and success criteria are missing
- Input has no artifacts or references that might contain detail
- The planner would need to guess fundamental aspects of what to build

### Step 2: Complexity Routing

Once confidence >= 0.70 (questioner gate passed), use the complexity × risk matrix to determine the route:

| Risk \ Complexity | trivial  | moderate | substantial |
|-------------------|----------|----------|-------------|
| low               | manual   | solo     | workflow    |
| medium            | solo     | solo     | workflow    |
| high              | workflow | workflow | workflow    |

- **`workflow`** (full quest): Dual plan review, arbiter, dual code review, full fix loop
- **`solo`** (lightweight quest): Single plan reviewer, no arbiter, single code reviewer, capped fix iterations
- **`manual`** (no pipeline): User works directly, no quest folder created

The router **recommends** a route. The human always chooses (override happens in SKILL.md).

**Critical rule: Prompt length is NOT a valid routing signal.** A 10-word prompt referencing a detailed spec file is rich input. A 200-word prompt with no scope, deliverables, or acceptance criteria is thin input. Length and word count must not influence the routing decision. Evaluate substance, not size.

**Keyword heuristics are secondary signals only.** The presence or absence of specific keywords (like "spec", "test", "deploy") should inform the dimension assessment but never override the substance evaluation.

## Output Contract

Produce this JSON structure as your routing decision:

```json
{
  "route": "questioner | workflow | solo | manual",
  "confidence": 0.0,
  "risk_level": "low | medium | high",
  "complexity": "trivial | moderate | substantial",
  "reason": "One sentence explaining the decision",
  "missing_information": []
}
```

- `route` is determined by the two-step decision logic: questioner gate first, then complexity × risk matrix.
- `confidence` is a numeric float from 0.0 to 1.0. If confidence < 0.70, route is always `questioner` regardless of complexity.
- `risk_level` assesses inherent task risk independent of information completeness. Domains like migrations, security, payments, and data loss scenarios are typically `high`. High risk should bias toward `questioner`.
- `complexity` assesses the scope and breadth of the change. Always populated, even for `questioner` routes (use best estimate).
- `missing_information` is ALWAYS an array. Use an empty array `[]` when routing with no gaps. Never omit this field or set it to null.

The classification MUST be recorded in the quest brief during Quest Folder Creation (see SKILL.md). The brief must contain the full JSON block — not a summary, not a paraphrase, the actual JSON. This is how risk visibility is preserved for the user and for downstream agents (planner, reviewers).

## Re-run Behavior

After the questioner completes, the router is invoked again with enriched input (original user prompt + questioner summary). Evaluate the combined input against the same 7 dimensions.

- If the re-run routes to `workflow`: proceed to quest folder creation and workflow.
- If the re-run still routes to `questioner`: allow a second short questioning pass. The 10-question total cap from questioner.md is still enforced -- the second pass uses whatever question budget remains. After the second pass, proceed to workflow regardless of the re-run result.
