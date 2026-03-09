# Idea: Add Quest Attribution Line to Files

## What
Add a single commented attribution line to Quest-managed files stating that the file is part of the Quest project, credits Candid Talent Edge, and links to the public domain dedication.

Approved attribution text (comment syntax adapted per file type):

`Part of the Quest project by Candid Talent Edge. Public domain dedication: https://github.com/KjellKod/quest/blob/main/LICENSE`

## Why
- Make provenance and licensing intent obvious in copied files.
- Preserve attribution context when files are copied between repositories.
- Reduce ambiguity about origin and license for downstream users.

## Approach
- Do **not** apply this blindly to every file in the repo.
- Apply it only to **human-authored, Quest-owned source and documentation files** where copy/paste or reuse is likely.
- Skip generated files, vendored files, third-party code, lockfiles, and machine-owned artifacts.
- Define a small mapping of comment styles by file type:
  - Markdown: `<!-- ... -->`
  - Shell/YAML/Python: `# ...`
  - JS/TS/CSS: `/* ... */`
  - HTML: `<!-- ... -->`
  - JSON: skip entirely. Standard JSON has no comments, and forcing one in would break parsers. Only consider comments for JSONC-style files or explicitly human-facing generated output.
- Apply only to Quest-owned source files (not generated artifacts).
- Default placement: end of file for docs/source where it does not disrupt existing headers or shebangs.
- Add a validator/lint rule to keep the line consistent and avoid drift.
- The validator should scan all in-scope files and fail if the attribution line is missing, malformed, or inconsistent.
- The validator should explicitly skip standard JSON files, since comments would break parsers.

## Status
idea

## Implementation Note
WHEN THIS IDEA IS TAKEN ON AS A QUEST AND THE PLAN IS APPROVED, THIS IDEA FILE MUST BE RETIRED PER NORMAL QUEST HYGIENE: REMOVE THE IDEA FILE OR OTHERWISE MOVE IT TO THE IMPLEMENTED/JOURNALED PATH USED BY THE REPO.
