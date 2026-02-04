# Installer/Porter Script

## What
A script that copies the Quest blueprint into an existing repository, handling conflicts and customization.

## Why
Currently, adopting Quest requires manually copying folders and editing configuration. An installer script would:
- Reduce onboarding friction
- Handle merge conflicts with existing files
- Guide users through customization (allowlist, project-specific settings)
- Ensure all required files are copied correctly
- is vocal about changes that are happening and warns about overwrites if they are needed. 
- tells user to start in a new branch and evaluate before starting the work. 

## Approach
- Shell script or Python script
- Interactive prompts for customization
- Detect existing files and offer merge/skip/overwrite options
- Validate installation after completion
- Could be run via `npx` (preferred) or from a pinned/verified release artifact (avoid raw `curl | bash` without hash/signature verification)

## Status
idea
