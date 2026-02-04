# GitHub CI for PR Plan Validation

## What
A GitHub Actions workflow that validates quest plans on pull requests.

## Why
Before merging changes made by the quest system, it would be valuable to have automated validation that:
- Plan structure is correct
- Required sections are present
- Acceptance criteria are testable
- File changes match the plan scope

## Approach
- GitHub Actions workflow triggered on PR
- JSON schema validation for plan structure
- Markdown linting for required sections
- Optional: AI-assisted review of plan quality
- Status check that must pass before merge

## Status
idea
