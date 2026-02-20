# Idea: Add Quest Attribution Line to Files

## What
Add a single commented attribution line to Quest-managed files stating that the file is part of Quest, includes the Candid Talent Edge public domain dedication note, and links to the repository license.

Example target text (comment syntax adapted per file type):

`Part of Quest (Candid Talent Edge public domain dedication). See LICENSE: https://github.com/KjellKod/quest/blob/main/LICENSE`

## Why
- Make provenance and licensing intent obvious in copied files.
- Preserve attribution context when files are copied between repositories.
- Reduce ambiguity about origin and license for downstream users.

## Approach
- Define a small mapping of comment styles by file type:
  - Markdown: `<!-- ... -->`
  - Shell/YAML/Python: `# ...`
  - JSON: skip (no comments) or use adjacent docs instead
- Apply only to Quest-owned source files (not generated artifacts).
- Add a validator/lint rule to keep the line consistent and avoid drift.

## Status
idea
