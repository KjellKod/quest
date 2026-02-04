# Installer/Porter Script

## What
A script that copies the Quest blueprint into an existing repository, handling conflicts and customization.

## Why
Currently, adopting Quest requires manually copying folders and editing configuration. An installer script would:
- Reduce onboarding friction
- Handle merge conflicts with existing files
- Guide users through customization (allowlist, project-specific settings)
- Ensure all required files are copied correctly

## Approach
- Shell script or Python script
- Interactive prompts for customization
- Detect existing files and offer merge/skip/overwrite options
- Validate installation after completion
- Could be run via `npx` or `curl | bash`

## Status
idea
