# Quest Dashboard

A self-contained Python package that generates a static HTML dashboard from Quest artifacts.

## Package Structure

```
quest_dashboard/
  __init__.py                  # Package marker
  build_quest_dashboard.py     # CLI entry point
  models.py                    # Frozen dataclasses (JournalEntry, ActiveQuest, DashboardData)
  loaders.py                   # Data extraction from quest journals and state files
  render.py                    # HTML generation with inline dark navy CSS
  README.md                    # This file
```

## Usage

```bash
# Default: reads repo data and writes docs/dashboard/index.html
python3 scripts/quest_dashboard/build_quest_dashboard.py

# Custom output path
python3 scripts/quest_dashboard/build_quest_dashboard.py --output docs/custom.html

# Explicit GitHub URL (overrides auto-detection from git remote)
python3 scripts/quest_dashboard/build_quest_dashboard.py --github-url https://github.com/owner/repo

# Explicit repo root
python3 scripts/quest_dashboard/build_quest_dashboard.py --repo-root /path/to/repo
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--repo-root` | Auto-detect from script location | Repository root directory |
| `--output` | `docs/dashboard/index.html` | Output HTML path (relative to repo root or absolute) |
| `--github-url` | Auto-detect from `git remote` | GitHub repo URL for journal and PR links |

## Data Sources

The dashboard reads from two data sources:

1. **Journal entries** (`docs/quest-journal/*.md`): Completed and abandoned quests. These are the source of truth for finished work. The loader extracts title, status, completion date, elevator pitch (from `## Summary`), PR number, and iteration counts.

2. **Active quests** (`.quest/*/state.json` + `quest_brief.md`): In-progress quests from the current worktree. These are ephemeral and reflect the live state of ongoing work.

## Output

A single self-contained HTML file with:
- No external CSS, fonts, or JavaScript
- Dark navy theme with glassmorphism effects
- Three sections: Finished, In Progress, Abandoned
- Quest cards with elevator pitch, journal links, PR links, and metadata
- Responsive card grid layout

## Architecture

- **models.py**: Immutable dataclasses with `frozen=True, slots=True`. `DashboardData` pre-groups quests into three lists so the renderer has no grouping logic.
- **loaders.py**: Parses markdown and JSON files. Handles format variations (bold metadata, list items, colon placement). Uses prefix matching for status normalization. Deduplicates active quests against journal entries.
- **render.py**: Pure HTML generation with inline CSS. Each section and card type has its own render function. All user text is HTML-escaped.
