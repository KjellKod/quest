# Quest Agent Wiring

These files are **Quest pipeline plumbing** — they define how each agent plugs into the orchestration workflow: which tool runs it, artifact paths, handoff contracts, and slot configuration.

They are **not** the skills themselves. The portable review/build/fix methodologies live in `.skills/*/SKILL.md`. Agent wiring files reference those skills but add Quest-specific concerns:

| Concern | Lives in skill (`SKILL.md`) | Lives in agent wiring (here) |
|---------|----------------------------|------------------------------|
| Review methodology | Yes | No |
| Artifact output paths | No | Yes |
| Handoff JSON/text contract | No | Yes |
| Tool and model selection | No | Yes |
| Parallel slot config | No | Yes |

This separation keeps skills portable across repos while letting Quest define its own orchestration layer on top.

For background on why these files were split from `.ai/roles/`, see `docs/quest-journal/phase4-role-wiring_2026-02-18.md`.
