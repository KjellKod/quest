# Scripts

Build and utility scripts for the Quest repository.

## Contents

| Script / Package | Purpose |
|------------------|---------|
| `quest_dashboard/` | Python package that generates a static HTML Quest Dashboard from journal entries and active quest state. See `quest_dashboard/README.md` for details. |
| `quest_installer.sh` | Installs and updates Quest in any repository. Handles fresh installs, updates, and checksum-based change detection. |
| `validate-quest-config.sh` | Validates quest configuration files (allowlist JSON schema, role markdown completeness). Used by pre-commit hooks and CI. |
| `validate-handoff-contracts.sh` | Validates that role files use the correct handoff contract format (`---HANDOFF---` with STATUS/ARTIFACTS/NEXT/SUMMARY). |
| `validate-manifest.sh` | Validates the file manifest and checksums for Quest installation integrity. |

## Quick Start

```bash
# Build the Quest Dashboard
python3 scripts/quest_dashboard/build_quest_dashboard.py

# Validate quest configuration
bash scripts/validate-quest-config.sh

# Install/update Quest in a repository
bash scripts/quest_installer.sh
```
