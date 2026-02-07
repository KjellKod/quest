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

## Decision Logic

**Route to `workflow`** when: The input has enough substance to produce an actionable plan with clear deliverables and success criteria. The planner would not need to make major assumptions likely to be wrong.

Routing rule: route `workflow` if confidence >= 0.70, else route `questioner`.

Confidence drivers (not strict math, but a clear rule):
- `workflow` if no more than 2 dimensions are missing, AND deliverable is present, AND scope is at least partial
- Otherwise `questioner`

Risk adjustment: high `risk_level` should bias toward `questioner` even if the dimension count suggests `workflow`. When the task domain is inherently high-risk (migrations, security, payments, data loss scenarios), lower the confidence score or route to `questioner` to ensure thorough information gathering.

**Route to `questioner`** when: Planning would require major assumptions on critical dimensions likely to produce a wrong plan. Key information gaps exist that the user can fill.

Questioner signals:
- Deliverable is vague or missing
- Both scope and success criteria are missing
- Input has no artifacts or references that might contain detail
- The planner would need to guess fundamental aspects of what to build

**Critical rule: Prompt length is NOT a valid routing signal.** A 10-word prompt referencing a detailed spec file is rich input. A 200-word prompt with no scope, deliverables, or acceptance criteria is thin input. Length and word count must not influence the routing decision. Evaluate substance, not size.

**Keyword heuristics are secondary signals only.** The presence or absence of specific keywords (like "spec", "test", "deploy") should inform the dimension assessment but never override the substance evaluation.

## Output Contract

Produce this JSON structure as your routing decision:

```json
{
  "route": "questioner | workflow",
  "confidence": 0.0,
  "risk_level": "low | medium | high",
  "reason": "One sentence explaining the decision",
  "missing_information": []
}
```

- `confidence` is a numeric float from 0.0 to 1.0. Route `workflow` if confidence >= 0.70, else route `questioner`.
- `risk_level` assesses inherent task risk independent of information completeness. Domains like migrations, security, payments, and data loss scenarios are typically `high`. High risk should bias toward `questioner`.
- `missing_information` is ALWAYS an array. Use an empty array `[]` when routing to `workflow` with no gaps. Never omit this field or set it to null.

The classification MUST be recorded in the quest brief during Quest Folder Creation (see SKILL.md). The brief must contain the full JSON block — not a summary, not a paraphrase, the actual JSON. This is how risk visibility is preserved for the user and for downstream agents (planner, reviewers).

## Re-run Behavior

After the questioner completes, the router is invoked again with enriched input (original user prompt + questioner summary). Evaluate the combined input against the same 7 dimensions.

- If the re-run routes to `workflow`: proceed to quest folder creation and workflow.
- If the re-run still routes to `questioner`: allow a second short questioning pass. The 10-question total cap from questioner.md is still enforced -- the second pass uses whatever question budget remains. After the second pass, proceed to workflow regardless of the re-run result.
