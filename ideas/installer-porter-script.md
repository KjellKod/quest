# Quest Installer

## What
A single script (`quest_installer.sh`) that installs and updates Quest in any repository.

## Source Repository

**This repo (`quest`) is the source of truth.** The installer fetches Quest files from `KjellKod/quest` main branch.

Historical note: Quest was born in `candid_talent_edge`, but that repo's Quest files are now outdated. `candid_talent_edge` is now just another adopter repo that can use this installer to update its legacy Quest files.

## Why
Currently, adopting Quest requires manually copying folders and editing configuration. A single installer script would:
- Reduce onboarding friction
- Handle both fresh installs AND updates (one tool, idempotent)
- Guide users through customization (allowlist, project-specific settings)
- Be vocal about changes and warn about overwrites
- Tell user to start in a new branch and evaluate before committing

## How It Works

```bash
# Copy script to your repo (one time)
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh -o scripts/quest_installer.sh
chmod +x scripts/quest_installer.sh

# Run anytime — it figures out what to do
./scripts/quest_installer.sh
```

**The script is idempotent.** Running it determines the current state and does the right thing:

| Scenario | Script behavior |
|----------|-----------------|
| Fresh repo, no Quest | Install everything |
| Has Quest, outdated | Update changed files |
| Has Quest, current | "Already up to date" — no-op |

## Version Tracking

The script stores installed version in a marker file:
```
.quest-version   # Contains: "v1.2.0" or commit SHA
```

On each run, compares local `.quest-version` against upstream (KjellKod/quest main or tagged release).

## Self-Updating

The script checks for a newer version of **itself** first:
1. Fetch checksum of upstream `quest_installer.sh`
2. Compare to local script checksum
3. If different, prompt: "A newer installer is available. Update? [Y/n]"
4. Then proceed with Quest file updates

## File Manifest

### Copy as-is (no customization needed)
```
.ai/quest.md
.ai/roles/*.md
.ai/schemas/*.json
.ai/templates/*.md
.claude/agents/*.md
.claude/hooks/enforce-allowlist.sh
.claude/skills/quest/SKILL.md
.claude/AGENTS.md
.skills/**/*.md
```

### Require customization (never overwrite)
```
.ai/allowlist.json          # Project-specific permissions, paths, gates
.ai/context_digest.md       # Project description and architecture overview
```

### Merge carefully (may conflict with existing)
```
.claude/settings.json       # May have existing user settings
.claude/settings.local.json # Local overrides
```

### Create if missing
```
.quest/                     # Runtime artifacts (gitignored)
ideas/                      # Optional: idea tracking
docs/quest-journal/         # Optional: completed quest documentation
```

## Flags

```bash
quest_installer.sh              # Interactive install/update
quest_installer.sh --check      # Show what would change (no modifications)
quest_installer.sh --force      # Non-interactive, auto-update safe files
quest_installer.sh --help       # Usage info
```

## Behavior by File Category

| File category | Fresh install | Update |
|---------------|---------------|--------|
| **Copy as-is** | Copy from upstream | Replace with latest |
| **User-customized** | Copy template, prompt to customize | Create `.quest_updated` suffix, prompt to merge |
| **Merge carefully** | Detect existing, offer skip/merge/overwrite | Show diff, let user decide |
| **New upstream files** | Copy | Add automatically |
| **Removed upstream** | N/A | Warn user, do not auto-delete |

## Handling User-Customized Files

For `.ai/allowlist.json` and `.ai/context_digest.md`:

**On fresh install:**
- Copy template version
- Prompt user to customize (or `--force` copies as-is for later customization)

**On update (if upstream changed):**
1. Never overwrite the user's version
2. Copy new version with `.quest_updated` suffix:
   ```
   .ai/allowlist.json.quest_updated
   .ai/context_digest.md.quest_updated
   ```
3. Print instructions:
   ```
   Upstream changes detected in customized files:

   .ai/allowlist.json has updates -> saved as .ai/allowlist.json.quest_updated
   .ai/context_digest.md has updates -> saved as .ai/context_digest.md.quest_updated

   Please diff and merge manually:
     diff .ai/allowlist.json .ai/allowlist.json.quest_updated

   After merging, delete the .quest_updated files.
   ```

## Interactive Flow

1. Check for script self-update; prompt if newer version available
2. Check if in git repo; warn if not
3. Suggest creating a new branch (if changes will be made)
4. Compare `.quest-version` against upstream
5. Show what will be installed/updated, grouped by category
6. For "merge carefully" files: detect existing, offer skip/merge/overwrite
7. For "user-customized" files: handle as described above
8. Copy/update all "as-is" files
9. Update `.quest-version` marker
10. Run `scripts/validate-quest-config.sh` to verify
11. Print next steps

## Acceptance Criteria

1. Fresh repo: `quest_installer.sh` creates all required files
2. Existing Quest repo: `quest_installer.sh` updates only changed files
3. User-customized files are never overwritten (`.quest_updated` pattern)
4. `--check` shows exactly what would change without modifying anything
5. `--force` works non-interactively for CI/automation
6. Script self-updates when a newer version is available
7. Validation passes after install/update
8. Works on macOS and Linux (bash, no exotic dependencies)

## Test Candidate

`candid_talent_edge` — has legacy Quest files, perfect for testing the update flow.

## Status
idea
