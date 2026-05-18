# Quest Brief: <QUEST_SLUG>

## Summary
<!-- One paragraph describing what this quest accomplishes -->

## Motivation
<!-- Why is this needed? What problem does it solve? -->

## Acceptance Criteria
<!-- Numbered list of concrete, testable criteria -->
1. ...
2. ...
3. ...

## Constraints
<!-- Any limitations, non-goals, or boundaries -->
- ...

## Relevant Context
<!-- Links to architecture docs, related plans, existing code -->
- ...

## Notes
<!-- Optional: anything the Creator wants the agents to know -->

## Router Classification

<!-- The orchestrator records the full router JSON here at quest creation. Downstream agents read this block to decide which conditional skills to load — e.g. `ux-context` when `ui_work: true`. -->

```json
{
  "route": "workflow",
  "confidence": 0.0,
  "risk_level": "low",
  "complexity": "moderate",
  "ui_work": false,
  "ui_work_evidence": [],
  "reason": "",
  "missing_information": []
}
```
