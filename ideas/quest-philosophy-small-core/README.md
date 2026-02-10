# Quest Philosophy: A Small Principled “Core” (Drop-in)

This note proposes a *small, drop-in* set of additions to Quest that makes the system more “process-trusting” than “model-trusting”, aligned with the philosophy in the prompt:

- Humans set direction, constraints, and intent
- Models generate artifacts
- Pipelines validate artifacts and decide what’s acceptable
- Autonomy is earned through constraints
- Clean context and focus are mandatory
- Artifacts must be explicit, reviewable, traceable, reproducible
- Verification must be continuous and automated wherever possible

The goal is *not* more agents or a larger workflow. The goal is to make correct behavior easy and incorrect behavior hard, with the smallest surface-area increase.

## What Quest Already Gets Right (and we should keep)

Quest already contains a strong “small core”:

- **Explicit phases + state**: `.quest/<id>/state.json` acts as a resumable state machine.
- **Role isolation**: planner/reviewer/builder/fixer run with clean contexts (artifact-based handoffs).
- **Constraints as configuration**: `.ai/allowlist.json` + `.claude/hooks/enforce-allowlist.sh` enforce write/command limits.
- **Dual independent review**: parallel Claude+Codex reviews reduce single-model blind spots.
- **Anti-spin arbiter**: KISS/YAGNI/SRP filter + iteration caps.
- **Portability**: `.ai/` source-of-truth + thin wrappers in tool-specific dirs.
- **Basic validation plumbing**: allowlist schema + config validation scripts exist.

These are the *right primitives*. The remaining gaps are mostly “evidence + enforcement”.

## The Two Gaps That Block the Philosophy

### Gap 1 — Artifact handling is mostly human-readable, not machine-checkable

The workflow is described procedurally, and there *is* a JSON schema for handoffs, but the system still tends to rely on:

- unstructured model output,
- “did the file appear?” checks,
- and human reading to decide if something is acceptable.

That undermines “pipelines validate artifacts” and makes correctness brittle.

### Gap 2 — Verification evidence is optional and hard to audit

“Builder runs tests after changes” is a good instruction, but it’s not a pipeline-backed acceptance decision unless:
- we record what was run,
- we record results in durable artifacts,
- and we can rerun/verify automatically.

## The Small Principled Additions (Drop-in)

The smallest set of changes that meaningfully closes both gaps:

1) **Make handoffs first-class artifacts (machine-checkable)**  
   Every role writes a `handoff.json` artifact (validated against `.ai/schemas/handoff.schema.json`).  
   The orchestrator routes based on `next_role` in the JSON, not on freeform text.

2) **Add a “verification evidence bundle” for build/fix**  
   Capture *what was verified* and *what passed* as explicit artifacts (logs + a small manifest).  
   This enables “trust evidence, not narrative”.

3) **Add lightweight validators (local + CI friendly)**  
   Validators should be boring and fast:
   - schema checks (`allowlist.json`, `handoff.json`)
   - “plan lint” (required sections exist; ACs present; test strategy exists)
   - “diff ↔ plan” sanity check (changed files appear in plan summary; flags drift)

4) **Risk-based gates (still configured in allowlist)**  
   Use a simple, repo-configurable risk rubric to decide when to demand human approval even if auto-approve is on:
   - “touches auth/payments/infra” => require approval
   - “large diff / many files” => require full review mode + approval before build/fix

5) **Keep extension points explicit**  
   Everything above should live as:
   - additive files (scripts / schemas),
   - optional allowlist fields (with safe defaults),
   - and minimal SKILL.md wording changes.
   This keeps the Claude `/quest` path intact and lets Codex-only runners reuse the same contracts.

## Autonomy Ladder (Earned, not assumed)

Keep autonomy as a configuration outcome, not “agent personality”.

- **Tier 0 (manual)**: no auto-approve; humans gate every phase.
- **Tier 1 (safe default)**: auto plan + plan review; human gate implementation + fix loop.
- **Tier 2 (low-risk auto)**: auto-implement only for low-risk paths (docs, tests); require evidence bundle.
- **Tier 3 (high trust)**: broader auto-approve only after the repo has stable validators + CI enforcement and the team has calibrated risk rules.

The key is that raising autonomy requires adding *validators and evidence*, not adding “smarter prompts”.

## Why this stays “small”

This proposal avoids:
- more roles,
- agent swarms,
- large new orchestration engines,
- or “magical autonomy”.

It focuses on a minimal contract + minimal validators that can run anywhere.

## Next Implementation Steps (incremental)

1. Add `handoff.json` as a required artifact per role (and validate it).
2. Add evidence bundle structure for build/fix (logs + manifest).
3. Add plan lint + diff-vs-plan validator script.
4. Wire validators into local dev (pre-commit) and CI for PRs.
5. Add optional risk rules + gate escalation logic (still allowlist-driven).

See `contracts_and_verification.md` for concrete artifact shapes and validator behaviors.
