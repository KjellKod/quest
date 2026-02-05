# Installer/Porter Script

## What
A script that copies the Quest blueprint into an existing repository, handling conflicts and customization.

## Why
Currently, adopting Quest requires manually copying folders and editing configuration. An installer script would:
- Reduce onboarding friction
- Handle merge conflicts with existing files
- Guide users through customization (allowlist, project-specific settings)
- Ensure all required files are copied correctly
- Be vocal about changes that are happening and warn about overwrites if they are needed
- Tell user to start in a new branch and evaluate before starting the work

## File Manifest

### Copy as-is (no customization needed)
```
.ai/quest.md
.ai/roles/code_review_agent.md
.ai/roles/plan_review_agent.md
.ai/roles/quest_agent.md
.ai/roles/arbiter_agent.md
.ai/roles/builder_agent.md
.ai/roles/planner_agent.md
.ai/roles/fixer_agent.md
.ai/schemas/allowlist.schema.json
.ai/schemas/handoff.schema.json
.ai/templates/pr_description.md
.ai/templates/quest_brief.md
.ai/templates/plan.md
.ai/templates/review.md
.claude/agents/arbiter.md
.claude/agents/code-reviewer.md
.claude/agents/builder.md
.claude/agents/planner.md
.claude/agents/fixer.md
.claude/agents/plan-reviewer.md
.claude/hooks/enforce-allowlist.sh
.claude/skills/quest/SKILL.md
.claude/AGENTS.md
.skills/plan-maker/SKILL.md
.skills/implementer/SKILL.md
.skills/README.md
.skills/plan-reviewer/SKILL.md
.skills/SKILLS.md
.skills/quest/SKILL.md
.skills/BOOTSTRAP.md
.skills/code-reviewer/SKILL.md
```

### Require customization (prompt user)
```
.ai/allowlist.json          # Project-specific permissions, paths, gates
.ai/context_digest.md       # Project description and architecture overview
```

### Merge carefully (may conflict with existing)
```
.claude/settings.json       # May have existing user settings
.claude/settings.local.json # Local overrides
```

### Create if missing (directories)
```
.quest/                     # Runtime artifacts (gitignored)
ideas/                      # Optional: idea tracking
docs/quest-journal/         # Optional: completed quest documentation
```

## Approach

### Implementation: Shell script (recommended for v1)
- Zero dependencies beyond bash
- Portable across macOS/Linux
- Can upgrade to Python/Node later if needed

### Core flags
- `--dry-run` — Preview changes without writing
- `--force` — Overwrite without prompting (for CI/automation)
- `--skip-customization` — Copy templates as-is, customize later

### Interactive flow
1. Check if in git repo; warn if not
2. Suggest creating a new branch
3. Show file manifest, grouped by category
4. For each "merge carefully" file: detect existing, offer skip/merge/overwrite
5. For each "require customization" file: prompt for values or copy template
6. Copy all "as-is" files
7. Run `scripts/validate-quest-config.sh` to verify installation
8. Print next steps (customize allowlist, write context_digest, run first quest)

### Distribution options
1. **Raw script in this repo** (simplest) — `curl -O ... && bash install-quest.sh`
2. **npx package** (friendlier) — `npx @quest/install` (requires publishing)
3. **GitHub release artifact** — Download from releases with checksum verification

Start with option 1; graduate to npx if adoption grows.

## Acceptance Criteria (v1 — Fresh Install)
1. Running installer in a fresh repo creates all required files
2. Running installer in a repo with existing `.claude/` merges safely
3. `--dry-run` shows exactly what would be created/modified
4. Validation script passes after installation
5. User is prompted for `.ai/allowlist.json` customization (or given clear template)

---

## v2 — Update / Fetch Latest

### What
Allow users who have already installed Quest to pull updates when the blueprint evolves.

### Version Tracking
Store installed version in a marker file:
```
.quest-version   # Contains: "v1.2.0" or commit SHA
```

Compare against:
- Git tags (preferred) — semantic versioning
- Or main branch HEAD (for bleeding edge)

### Update Commands
```bash
quest-install.sh --check-updates    # Show what would change (no modifications)
quest-install.sh --update           # Apply updates interactively
quest-install.sh --update --force   # Auto-update safe files, prompt only for conflicts
```

### Update Behavior by File Category

| File category | Update behavior |
|---------------|-----------------|
| **Copy as-is** | Replace with latest version |
| **User-customized** | Copy new version as `.quest_updated` suffix (see below) |
| **Merge carefully** | Show diff, let user decide |
| **New files in release** | Add them automatically |
| **Removed upstream** | Warn user, do not auto-delete |

### Handling User-Customized Files

For `.ai/allowlist.json` and `.ai/context_digest.md`:

1. **Never overwrite** the user's version
2. If upstream has changes, copy the new version with a `.quest_updated` suffix:
   ```
   .ai/allowlist.json.quest_updated
   .ai/context_digest.md.quest_updated
   ```
3. Print clear instructions:
   ```
   ⚠️  Upstream changes detected in customized files:

   .ai/allowlist.json has updates → saved as .ai/allowlist.json.quest_updated
   .ai/context_digest.md has updates → saved as .ai/context_digest.md.quest_updated

   Please diff and merge manually:
     diff .ai/allowlist.json .ai/allowlist.json.quest_updated
     diff .ai/context_digest.md .ai/context_digest.md.quest_updated

   After merging, delete the .quest_updated files.
   ```

### Acceptance Criteria (v2 — Updates)
1. `--check-updates` shows version diff and changed files without modifying anything
2. `--update` replaces "copy as-is" files and creates `.quest_updated` for customized files
3. User is never surprised by overwrites to their customized files
4. `.quest-version` is updated after successful update
5. New files from upstream are added; removed files generate warnings only

## Status
idea
