# Atomic State Transitions and Presentation Gate

- PR: #77
- Merged: 2026-03-20
- Outcome: Closed the state-transition footgun and enforced the mandatory presentation gate.

## What Shipped

- **Atomic state transitions**: Replaced the two-step validate-then-mutate pattern with a single atomic call. Invalid transitions like `building->building` are now rejected at the API level.
- **Mandatory presentation gate**: The plan presentation step can no longer be skipped. Attempting to transition from planning to building without presenting raises an error.
- Updated `scripts/quest_state.py` with the new transition logic and validation.

## Why It Matters

The old pattern allowed a race where validation passed but the state had already changed before the mutation landed. Atomic transitions make invalid states unrepresentable. The presentation gate ensures humans always see the plan before a build starts -- a core Quest principle.
