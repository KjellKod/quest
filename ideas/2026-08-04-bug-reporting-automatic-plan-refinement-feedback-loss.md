# Automatic Plan Refinement Can Recreate Arbiter Feedback

Date: 2026-08-04
Status: Confirmed trigger fixed, broader reported loss not reproduced

## Summary

A findings-schema retry could truncate an already valid current Arbiter verdict. The retry then required the Arbiter to reconstruct its synthesis from the plan and reviews. That creates a real opportunity for refinement instructions to drift or lose detail before the next Planner invocation.

This change fixes the confirmed trigger and binds exact verdict bytes to the following Planner iteration. It does not claim proof that a completed prior Quest delivered an empty or materially different verdict to its Planner.

## Confirmed Trigger

Arbiter output preparation previously treated these scratch files as one set:

- `arbiter_verdict.md.next`
- `review_findings.json.next`
- `handoff_arbiter.json`

Every fresh role attempt truncated every prepared output. If only `review_findings.json.next` failed validation, the retry still erased `arbiter_verdict.md.next`. A live Quest retry prompt also instructed the Arbiter to recreate both verdict and findings after a findings validation failure.

The focused regression now keeps a sentinel verdict byte-for-byte unchanged while retrying only findings and the handoff.

## Unconfirmed Broader Loss

The observed trigger proves forced reconstruction, but not an end-to-end user-visible loss. The first scratch verdict was not retained in the observed Quest, so it cannot be compared with the recreated verdict. We did not reproduce a completed automatic loop where the next Planner received empty or materially different feedback.

Possible prior failure points included publishing the wrong scratch verdict, cleaning handoffs before consumption was proven, or dispatching Planner with stale canonical feedback. These were plausible from the former lifecycle, not independently confirmed incidents.

## Resolution

- Findings-only retry prepares only invalid findings plus its handoff.
- The exact valid verdict digest must remain unchanged across the retry.
- `publish-refinement` validates findings and binds the exact verdict and Arbiter handoff to iterations `N` and `N+1`.
- Iteration `N` is sealed before cleanup.
- Planner preparation verifies sealed predecessor `N` before truncating current outputs.
- `verify-refinement` rejects absent, stale, or changed verdict bytes before Planner dispatch.

Solo mode remains independent of Arbiter artifacts.
