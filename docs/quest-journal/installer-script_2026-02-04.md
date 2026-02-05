# Quest Journal: Installer Script

**Quest ID:** `installer-script_2026-02-04__1841`
**Completed:** 2026-02-04
**Branch:** choices

---

## Summary

Created a single unified installer script (`scripts/quest_installer.sh`) that installs and updates Quest in any repository.

### Key Features
- **Idempotent**: Handles fresh installs AND updates
- **Checksum tracking**: Detects user modifications via `.quest-checksums`
- **Self-update**: Script updates itself when newer version available
- **Three file categories**: copy-as-is (auto-update), user-customized (never overwrite), merge-carefully (prompt)
- **Cross-platform**: Works on macOS (bash 3.2+) and Linux

### Flags
- `--check`: Dry-run mode (shows what would change)
- `--force`: Non-interactive CI mode
- `--help`: Usage information

---

## Files Changed

### Created
- `scripts/quest_installer.sh` - Main installer (1174 lines, bash)
- `checksums.txt` - Source manifest of all Quest file checksums

### Modified
- `.ai/allowlist.json` - Added `shasum`, `sha256sum` to builder/fixer bash permissions

---

## Iterations

| Phase | Iterations | Notes |
|-------|------------|-------|
| Planning | 2 | Added checksum tracking per user request |
| Fixing | 1 | Fixed self-update bugs, file write safety, validation |

---

## Reviews

- **Claude Plan Review**: Ready to implement
- **Codex Plan Review**: Ready after fixes (5 items)
- **Claude Code Review**: 3 must-fix, 4 should-fix
- **Codex Code Review**: 3 blockers identified
- **Security Review**: PASSED (LOW severity notes only)

---

## This is where it all began...

> **ideas/installer-porter-script.md**
>
> A single script (`quest_installer.sh`) that installs and updates Quest in any repository.
>
> Currently, adopting Quest requires manually copying folders and editing configuration. A single installer script would:
> - Reduce onboarding friction
> - Handle both fresh installs AND updates (one tool, idempotent)
> - Guide users through customization
> - Be vocal about changes and warn about overwrites
> - Tell user to start in a new branch and evaluate before committing

---

## Artifacts

- Quest folder: `.quest/installer-script_2026-02-04__1841/`
- Plan: `.quest/installer-script_2026-02-04__1841/phase_01_plan/plan.md`
- Reviews: `.quest/installer-script_2026-02-04__1841/phase_03_review/`
