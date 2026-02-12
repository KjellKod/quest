# Quest Dashboard - Comprehensive Analysis & Implementation Plan

**Created:** 2026-02-12
**Purpose:** Technical analysis of three dashboard implementations (PRs #24, #22, #21) with detailed architectural recommendations for building the final Quest Dashboard.

---

## Executive Summary

### User Feedback Synthesis

**Clear Requirements Emerged:**
1. **Grouping/Sorting Priority:** Status-based grouping > Chronological
   - Order: ① Completed → ② In Progress → ③ Abandoned
   - Clear visual separation is critical (not mixed chronologically)

2. **Content Strategy:**
   - Display **elevator pitch** (not original user request)
   - Truncate if too long; avoid exposing private user notes
   - Source elevator pitch from quest journal debrief when available

3. **Information Hierarchy:**
   - Mute metadata (timestamps, Quest IDs, iterations)
   - Avoid redundant labels ("executive summary", "board-level visibility")
   - Make actionable content prominent

4. **Missing Critical Elements:**
   - Link to Quest Journal (formatted/rendered view, not raw markdown)
   - Link to merged PR (when available)
   - Both should be present but visually muted

5. **Visual Design:**
   - PR #21's cohesive dark navy palette wins
   - Avoid stark dark/light contrast (PR #24's issue)
   - Smooth gradients work well

6. **Charts:**
   - Started vs Completed bars: when equal, not insightful
   - Prefer graphs showing delta or trends over time
   - Status over time needs sufficient data points to be meaningful

### Architectural Decision: Source of Truth

**User's Proposed Architecture (APPROVED):**
- **Completed quests** = source of truth from `docs/quest-journal/*.md` in main branch
- **In-progress quests** = ephemeral snapshot from `.quest/*/state.json` in current worktree
- **Generation context:** Can generate from any git worktree branch
- **Publishing:** Push to GitHub Pages as part of merge/PR workflow
- **Race conditions:** Acceptable; next update self-corrects from main branch

**Implications:**
- Dashboard reads from **two sources** with different lifecycles
- Completed quests are stable and authoritative
- Active quests are transient and may disappear between updates
- This aligns with prioritizing completed > in-progress > abandoned

---

## PR #24: rommel-demonstration (Most Professional)

**Branch:** `rommel-demonstration` (worktree at `/Users/kjell/ws/quest-rommel-demonstration`)
**Status:** Open PR to main
**Visual:** Dark hero with gold accent, slate color system

### Architecture

**Structure:**
- **Modular Python package** (`scripts/quest_dashboard/`)
- **Single-file HTML output** with embedded CSS
- **Server-side rendering** (SSR) - fully static HTML

**Files:**
```
scripts/
  build_quest_dashboard.py         # CLI entry point
  quest_dashboard/
    __init__.py
    models.py                       # Dataclasses for type safety
    loaders.py                      # Data extraction from quest artifacts
    render.py                       # HTML generation with inline CSS
tests/
  unit/test_quest_dashboard_loaders.py
  unit/test_quest_dashboard_render.py
  integration/test_build_quest_dashboard.py
docs/dashboard/index.html          # Generated output
```

### Data Model

**Python Dataclasses:**
```python
@dataclass(frozen=True, slots=True)
class ActiveQuestRecord:
    quest_id: str
    slug: str
    name: str
    status: str                    # e.g., "In Progress", "Blocked"
    phase: str                     # e.g., "Building", "Plan"
    updated_at: datetime
    elevator_pitch: str
    state_path: Path
    brief_path: Path | None

@dataclass(frozen=True, slots=True)
class CompletedQuestRecord:
    quest_id: str
    name: str
    status: str                    # "Completed" or "Abandoned"
    updated_on: date
    elevator_pitch: str
    journal_path: Path             # Relative to repo root
    source_path: Path

@dataclass(frozen=True, slots=True)
class DashboardData:
    active_quests: list[ActiveQuestRecord]
    completed_quests: list[CompletedQuestRecord]
    warnings: list[str]
    generated_at: datetime
```

### Data Sources & Extraction Logic

**Active Quests:**
- Source: `.quest/*/state.json` (excludes archived)
- Brief: `.quest/*/quest_brief.md`
- Extraction logic (`loaders.py:load_active_quests()`):
  1. Glob for `state.json` files
  2. Skip if path contains "archive"
  3. Parse JSON for `quest_id`, `slug`, `status`, `phase`, `updated_at`
  4. Extract name from quest_brief heading: `# Quest Brief: <name>`
  5. Extract elevator pitch priority:
     - First: "Original Prompt" section first paragraph
     - Fallback: "Requirements" section first bullet/paragraph
     - Fallback: First paragraph of entire brief
  6. Generate warnings if brief missing

**Completed Quests:**
- Source: `docs/quest-journal/*.md`
- Extraction logic (`loaders.py:load_completed_quests()`):
  1. Glob for `*.md` files
  2. Extract quest_id from metadata `**Quest ID:** <value>`
  3. Extract status from `**Status:** <value>` (default: "Completed")
  4. Extract date from `**Completed:** <date>` or filename pattern `_YYYY-MM-DD`
  5. Extract name from heading: `# Quest Journal: <name>` or first `# <name>`
  6. Extract elevator pitch from "Summary" section first paragraph
  7. Fallback to first paragraph of entire journal

**Sorting:**
- Active: By `updated_at` descending (most recent first)
- Completed: By `updated_on` descending (most recent first)

### Rendering

**HTML Generation (`render.py`):**
- Single function `render_dashboard()` returns complete HTML string
- Inline CSS (440 lines) in `<style>` tag
- Uses Python f-strings for templating
- HTML escaping via `html.escape()`

**CSS Architecture:**
- CSS custom properties (design tokens)
- Slate color palette (950→50)
- Hero gradient: `radial-gradient` + `linear-gradient`
- Card-based layout with hover effects
- Responsive: breakpoints at 780px, 480px

**Activity Chart:**
- Inline SVG generated in Python
- Weekly buckets (ISO week)
- Side-by-side bars (Started vs Completed)
- Parses quest_id timestamp: `_YYYY-MM-DD__HHMM`
- Falls back to `updated_on` for completed dates

**Journal Links:**
- GitHub mode: `{github_base_url}/blob/main/{journal_path}`
- Relative mode: Computes `os.path.relpath()` from output to journal

### Strengths

1. **Type safety**: Frozen dataclasses with slots
2. **Modularity**: Separate concerns (load, model, render)
3. **Testability**: Pure functions, comprehensive unit tests
4. **Error handling**: Resilient parsing with warnings list
5. **Single artifact**: Self-contained HTML (no network dependencies)
6. **Professional design**: Cohesive slate palette, subtle accents
7. **Accessibility**: ARIA labels, semantic HTML
8. **GitHub integration**: Auto-detects remote URL, generates proper links

### Weaknesses

1. **No status separation**: Mixes completed/abandoned chronologically (user's #1 complaint)
2. **Timestamp too prominent**: "Generated" metric has same visual weight as quest counts
3. **Redundant subtitle**: "Executive summary..." states the obvious
4. **Missing Journal link**: No "Open Journal →" link on cards
5. **Chart noise**: When started=completed, bars overlap → no insight
6. **Elevator pitch source**: Uses "Original Prompt" which may contain private user details

### Technical Debt

- `render.py` is 732 lines (monolithic)
- Inline CSS makes styling changes require Python edits
- Chart SVG generation in render logic (mixed concerns)
- No separation of data generation from HTML rendering

---

## PR #22: demo/skills-quest-engineering-discipline (Better UX)

**Branch:** `demo/skills-quest-engineering-discipline`
**Status:** Open PR to main
**Visual:** Gradient header (tan→blue), warmer color palette

### Architecture

**Structure:**
- **Single monolithic Python file** (927 lines)
- **Embedded HTML/CSS** as Python f-string
- **Server-side rendering** (SSR)

**Files:**
```
scripts/generate_quest_status_page.py   # Everything in one file
tests/unit/test_generate_quest_status_page.py
docs/quest-status/index.html            # Generated output
```

### Data Model

**Python Dicts (no dataclasses):**
```python
Quest = {
    "quest_id": str,
    "phase": str,                   # e.g., "building", "plan"
    "status": str,                  # e.g., "complete", "in_progress"
    "plan_iteration": int | None,
    "fix_iteration": int | None,
    "last_role": str,
    "last_verdict": str,
    "created_at": str,              # ISO timestamp
    "updated_at": str,
    "title": str,
    "elevator_pitch": str,
    "description": str,
    "original_request": str,
    "anchor": str,                  # HTML id for <details>
    "artifact_path": str,           # .quest/<quest_id>
    "journal_filename": str,
    "warnings": list[str]
}

DashboardModel = {
    "ongoing": list[Quest],         # Sorted by phase rank, then date
    "finished": list[Quest],        # status == "complete"
    "counts": {
        "ongoing": int,
        "finished": int,
        "blocked": int
    },
    "warnings": list[str]
}
```

### Data Sources & Extraction Logic

**Quest Discovery:**
- Function: `discover_quest_dirs()`
- Roots: `.quest/` and `.quest/archive/`
- Validation: Directory must contain both `state.json` and `quest_brief.md`
- Returns sorted list of quest directories

**State Loading:**
- Function: `load_state()`
- Resilient: Returns default dict if JSON invalid
- Collects warnings in `state["warnings"]`

**Brief Parsing:**
- Function: `parse_quest_brief()`
- Title: First heading, strips "Quest Brief:" prefix
- Elevator pitch priority:
  1. "User Input (Original Prompt)" section
  2. "User Input" section
  3. "Original Prompt" section
  4. "User Request" section
- Description priority: "Goal", "Objective", "Problem", "Context"
- Fallback: First paragraph after title

**Journal Integration:**
- Function: `find_journal_entry()` - matches slug prefix
- Function: `parse_journal_summary()` - extracts `## Summary` section
- **For completed quests:** Elevator pitch = journal summary (if exists)

**Phase-Based Sorting:**
```python
_PHASE_ORDER = {
    "complete": 0,
    "reviewing": 1, "code_review": 1,
    "fixing": 2,
    "building": 3, "implementing": 3,
    "presenting": 4,
    "plan": 5, "pending": 5
}
```
- Primary sort: Phase rank (lower = earlier in pipeline)
- Secondary sort: `updated_at` descending (most recent first within phase)
- Result: **Building quests appear before Plan quests** (active work > planning)

### Rendering

**HTML Structure:**
- Embedded in f-string (lines 589-869)
- Inline CSS in `<style>` tag (lines 596-814)
- Hero with gradient background
- 3 metrics: Ongoing, Completed, Blocked

**Key Sections:**
1. **Ongoing** - Card grid with phase badges
2. **Completed** - Card grid with "View Details" links
3. **Details** - `<details>` elements for expandable info

**Color Palette:**
```css
--bg: #f4f4ef              /* Warm off-white */
--ink: #121619              /* Near-black */
--surface: rgba(255,255,255,0.86)
--accent: #4338ca           /* Indigo */
--green: #0b8f53
--amber: #b45309
--red: #dc2626
```

**Phase Badges:**
- PLAN: Blue background
- BUILDING: Amber background
- UNDER REVIEW: Purple background
- FIXING: Red background
- COMPLETE: Green background

**Chart:**
- Weekly bar chart (started vs completed)
- Parses `created_at` for started
- Parses `updated_at` for completed (if status == "complete")
- Colors: Orange (started), Teal (completed)

### Strengths

1. **Clear separation**: "Ongoing" and "Completed" sections (user's top request)
2. **Phase-aware sorting**: Active work prioritized over planning
3. **Expandable details**: `<details>` for completed quests (optional deep dive)
4. **Journal integration**: Uses journal summary for completed quest elevator pitch
5. **Better elevator pitch**: Pulls from "Original Prompt" section (more structured)
6. **Resilient parsing**: Default values + warnings (doesn't crash on bad data)
7. **Gradient header**: Warmer, less stark than PR #24

### Weaknesses

1. **Monolithic file**: 927 lines, hard to maintain
2. **No type safety**: Plain dicts, easy to typo keys
3. **Shows original request**: Card displays user's raw input (privacy concern)
4. **Slug displayed**: Quest ID slug shown but not actionable
5. **"Executive overview..." label**: Still redundant
6. **Mixes completed/abandoned**: Both in "Completed" section without sub-grouping
7. **No PR link**: Missing link to merged PR

### Technical Debt

- No separation of concerns (data + rendering in one file)
- Hard to test individual functions
- CSS changes require editing Python file
- Chart generation mixed with HTML rendering

---

## PR #21: test_with_dashboard_a_demo (Most Polished)

**Branch:** `test_with_dashboard_a_demo` (remote: `origin/test_with_dashboard_a_demo`)
**Status:** Open PR to main
**Visual:** Dark navy theme, professional data-driven design

### Architecture

**Structure:**
- **Client-server separation**
- **Python data generator** → JSON
- **Static HTML + JS + CSS** → Consumes JSON
- **Chart.js from CDN** for interactive charts

**Files:**
```
scripts/generate_quest_dashboard_data.py   # Data extraction → JSON
docs/dashboard/
  dashboard-data.json                      # Generated data file
  index.html                               # Static template
  styles.css                               # Separate stylesheet
  app.js                                   # Client-side rendering
```

### Data Model

**JSON Structure:**
```json
{
  "generated_at": "2026-02-12T08:54:00Z",
  "summary": {
    "total": 12,
    "by_status": {
      "in_progress": 0,
      "blocked": 0,
      "abandoned": 1,
      "finished": 11,
      "unknown": 0
    }
  },
  "trends": {
    "granularity": "month",
    "points": [
      {
        "period": "2026-02",
        "in_progress": 0,
        "blocked": 0,
        "abandoned": 1,
        "finished": 11,
        "unknown": 0
      }
    ]
  },
  "quests": [
    {
      "quest_id": "quest-dashboard_2026-02-11__0936",
      "slug": "quest-dashboard",
      "title": "Quest Dashboard",
      "elevator_pitch": "Built a static executive dashboard...",
      "status": "finished",
      "completed_date": "2026-02-11",
      "created_at": "2026-02-11T...",
      "updated_at": "2026-02-11T...",
      "plan_iteration": 2,
      "fix_iteration": 0,
      "journal_path": "docs/quest-journal/quest-dashboard_2026-02-10.md",
      "state_path": ".quest/archive/quest-dashboard_2026-02-11__0936/state.json"
    }
  ]
}
```

### Data Sources & Merging Logic

**Three Data Sources:**
1. **Journal entries** (`docs/quest-journal/*.md`)
2. **Active states** (`.quest/*/state.json`, excluding archive)
3. **Archive states** (`.quest/archive/*/state.json`)

**Merging Strategy (`_merge_records()`):**
1. Build indexes: `state_by_id` and `state_by_slug`
2. For each journal entry:
   - Match by `quest_id` (exact)
   - Fallback: Match by `slug` (prefix match)
   - Merge: journal data + state data → unified quest record
3. For unmatched states (no journal):
   - Create quest record from state alone
   - Elevator pitch = empty string
4. Deduplicate: Archive state overwrites active state (same quest_id)

**Status Normalization:**
```python
def normalize_status(journal_record, state_record):
    # Priority:
    # 1. state["status"] or state["phase"]
    # 2. journal["status"]
    # 3. If completed_date exists → "finished"
    # 4. Default: "unknown"

    # Mappings:
    # "completed", "complete" → "finished"
    # "in_progress" → "in_progress"
    # "blocked" → "blocked"
    # "abandoned" → "abandoned"
```

**Trend Calculation:**
- Buckets by month: `YYYY-MM`
- For each quest:
  - Event date = `completed_date` or `updated_at` or `created_at`
  - Increment bucket for quest's **current status**
- Result: Monthly snapshots of status distribution

### Rendering

**Client-Side (app.js):**
1. Fetch `dashboard-data.json`
2. Populate KPIs from `summary.by_status`
3. Render charts using Chart.js:
   - **Doughnut chart**: Status distribution (current snapshot)
   - **Stacked area chart**: Trends over time (monthly)
4. Render quest cards dynamically:
   - Sort by `completed_date` (or `updated_at`) descending
   - Build DOM elements via `document.createElement()`

**CSS Design System (styles.css):**
```css
:root {
  --bg-0: #05070f;                 /* Deep space */
  --bg-1: #0a0f1d;
  --surface-0: rgba(17, 24, 39, 0.78);
  --text-0: #f8fafc;               /* Pure white */
  --text-1: #cbd5e1;               /* Light slate */
  --text-2: #94a3b8;               /* Muted slate */

  --status-finished: #34d399;      /* Green */
  --status-in-progress: #60a5fa;   /* Blue */
  --status-blocked: #f59e0b;       /* Amber */
  --status-abandoned: #f87171;     /* Red */
  --status-unknown: #a78bfa;       /* Purple */
}
```

**Visual Effects:**
- Animated page glows (fixed position blurred circles)
- Glassmorphism on hero (`backdrop-filter: blur()`)
- Subtle gradients everywhere
- Card hover effects (`transform: translateY(-1px)`)

**Chart Features:**
- Interactive legends (click to toggle)
- Tooltips on hover
- Responsive canvas sizing
- Fallback if Chart.js CDN fails

### Strengths

1. **Data/presentation separation**: JSON can be consumed by other tools
2. **Interactive charts**: Chart.js provides rich visualization
3. **Most polished design**: Professional dark theme, cohesive palette
4. **Shows iterations**: Displays `plan X / fix Y` (unique insight)
5. **Proper status normalization**: Canonical status mapping
6. **Trend analysis**: Monthly time-series data
7. **Flexible rendering**: Can rebuild UI without regenerating data
8. **Archive handling**: Merges active + archived states intelligently

### Weaknesses

1. **Network dependency**: Requires Chart.js CDN (fails offline)
2. **Client-side rendering**: Blank page if JS disabled
3. **Timestamp too bright**: Generated date is sharp white (should be muted)
4. **Slug prominence**: Quest ID in white (should be muted/bottom)
5. **"Board-level visibility" text**: Redundant label
6. **No status sub-grouping**: Mixes finished/abandoned in single list
7. **No Journal link**: Missing "View Journal" action
8. **No PR link**: Missing link to merged PR
9. **Iterations not muted**: Shown in white despite being non-critical

### Technical Debt

- Two-step build: Python → JSON, then manual file placement
- No build script to coordinate data generation + deployment
- Chart.js version pinned in HTML (CDN URL)

---

## Comparison Matrix

| Aspect | PR #24 (rommel) | PR #22 (skills) | PR #21 (dashboard_a) |
|--------|-----------------|-----------------|----------------------|
| **Architecture** | Modular Python + SSR | Monolithic Python + SSR | Data gen → JSON + Client render |
| **Type Safety** | ✅ Dataclasses | ❌ Dicts | ⚠️ JSON schema |
| **Testability** | ✅ Excellent | ⚠️ Limited | ✅ Good (data gen) |
| **Separation of Concerns** | ✅ Good | ❌ Poor | ✅ Excellent |
| **Status Grouping** | ❌ Mixed chronologically | ✅ Ongoing/Completed split | ❌ Mixed chronologically |
| **Elevator Pitch Source** | ⚠️ "Original Prompt" (privacy risk) | ✅ Journal summary for completed | ✅ Journal summary |
| **Journal Link** | ❌ Missing | ⚠️ "View Details" (not journal) | ❌ Missing |
| **Quest ID Prominence** | ⚠️ Shown but muted | ❌ Shown prominently | ❌ Shown in white |
| **Iterations Shown** | ❌ No | ❌ No | ✅ Yes |
| **Charts** | ⚠️ Static SVG, basic | ⚠️ Static SVG, basic | ✅ Interactive (Chart.js) |
| **Visual Design** | ✅ Professional slate | ✅ Warm gradient | ✅✅ **Best: Dark navy** |
| **Timestamp Muting** | ❌ Same weight as metrics | ⚠️ Embedded in subtitle | ❌ Bright white |
| **Offline Support** | ✅ Full | ✅ Full | ❌ Requires CDN |
| **Build Complexity** | Medium | Low | Medium-High |
| **Maintainability** | ✅ Good | ❌ Poor | ✅ Good |

---

## Recommended Architecture

### Hybrid Approach

**Take the best from each PR:**

1. **From PR #24 (rommel):**
   - Modular Python structure (models, loaders, render)
   - Type-safe dataclasses
   - Comprehensive error handling + warnings
   - Auto-detect GitHub remote URL

2. **From PR #22 (skills):**
   - Status-based grouping (Ongoing vs Completed sections)
   - Phase-aware sorting (building > plan)
   - Journal summary integration for elevator pitch
   - Expandable details for completed quests

3. **From PR #21 (dashboard_a):**
   - Visual design (dark navy palette, glassmorphism)
   - Iterations display (plan X / fix Y)
   - Status normalization logic
   - Archive state merging

**Don't take:**
- Client-side rendering (adds deployment complexity)
- Chart.js dependency (use inline SVG instead)
- Monolithic file structure
- Redundant labels ("executive summary", "board-level visibility")

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT SOURCES (Read-only)                                   │
├─────────────────────────────────────────────────────────────┤
│ 1. docs/quest-journal/*.md  ← SOURCE OF TRUTH (main branch)│
│    - Completed quests (stable)                              │
│    - Status: "completed" or "abandoned"                     │
│    - Elevator pitch from "## Summary"                       │
│                                                              │
│ 2. .quest/*/state.json      ← EPHEMERAL (current worktree) │
│    - Active quests                                          │
│    - Status: "in_progress", "blocked"                       │
│                                                              │
│ 3. .quest/archive/*/state.json ← OPTIONAL (if archived)    │
│    - Recently completed (before journal merge)              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ DATA EXTRACTION & MERGING                                   │
├─────────────────────────────────────────────────────────────┤
│ loaders.py:                                                 │
│  - load_journal_entries()    → CompletedQuestRecord[]      │
│  - load_active_states()      → ActiveQuestRecord[]         │
│  - load_archive_states()     → ArchiveQuestRecord[]        │
│  - merge_quest_data()        → DashboardData               │
│                                                              │
│ models.py:                                                  │
│  - Dataclasses with frozen=True, slots=True                │
│  - Type hints everywhere                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ RENDERING                                                   │
├─────────────────────────────────────────────────────────────┤
│ render.py:                                                  │
│  - render_dashboard() → HTML string                         │
│  - Inline CSS (design tokens)                               │
│  - Inline SVG charts                                        │
│  - Journal links (GitHub or relative)                       │
│  - PR links (via GitHub API or git log parsing)            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT                                                      │
├─────────────────────────────────────────────────────────────┤
│ docs/dashboard/index.html                                   │
│  - Self-contained static HTML                               │
│  - No external dependencies                                 │
│  - Works offline                                            │
│  - Can be pushed to GitHub Pages                            │
└─────────────────────────────────────────────────────────────┘
```

### Grouping Strategy

**Three Status Groups (user requirement):**

1. **Finished** (green badge)
   - Status: "completed" (from journal or state)
   - Sort: `completed_date` descending (most recent first)
   - Content: Elevator pitch from journal summary
   - Actions: "View Journal →" (primary), PR link (secondary, muted)

2. **In Progress** (blue/amber badge)
   - Status: "in_progress", "building", "reviewing", "fixing", etc.
   - Sort: Phase rank (building > plan), then `updated_at` descending
   - Content: Elevator pitch from quest brief "Original Prompt" section
   - Actions: None (ephemeral, no journal yet)

3. **Abandoned** (red badge)
   - Status: "abandoned" (from journal)
   - Sort: `updated_at` or `completed_date` descending
   - Content: Elevator pitch from journal summary
   - Actions: "View Journal →" (shows why abandoned)

**Layout:**
```html
<section id="finished-quests">
  <h2>Finished Quests</h2>
  <small>11 quests completed</small>
  <div class="quest-grid">
    <!-- Cards sorted by completion date -->
  </div>
</section>

<section id="in-progress-quests">
  <h2>In Progress</h2>
  <small>5 quests actively being worked</small>
  <div class="quest-grid">
    <!-- Cards sorted by phase, then updated_at -->
  </div>
</section>

<section id="abandoned-quests">
  <h2>Abandoned</h2>
  <small>1 quest archived</small>
  <div class="quest-grid">
    <!-- Cards sorted by abandonment date -->
  </div>
</section>
```

### Visual Hierarchy

**Prominent (what matters):**
- Quest title (large, bold)
- Status badge (color-coded)
- Elevator pitch (readable font size)
- "View Journal →" link (blue, underlined)

**Muted (metadata):**
- Quest ID slug (small, gray, at bottom)
- Completed date (small, gray)
- Iterations count (small, gray)
- PR link (small, gray, "PR #123")
- Generated timestamp (tiny, gray, in footer only)

**Hidden (don't show):**
- Original user request (privacy)
- State file paths (.quest/... paths)
- Internal phase names (unless in debug mode)

### Design Tokens (PR #21 palette)

```css
:root {
  /* ── Color Palette ── */
  --navy-950: #05070f;
  --navy-900: #0a0f1d;
  --navy-800: #111827;
  --navy-700: #1e293b;
  --slate-600: #475569;
  --slate-400: #94a3b8;
  --slate-200: #cbd5e1;
  --slate-100: #f8fafc;

  /* ── Status Colors ── */
  --status-finished: #34d399;      /* Green */
  --status-in-progress: #60a5fa;   /* Blue */
  --status-blocked: #f59e0b;       /* Amber */
  --status-abandoned: #f87171;     /* Red */

  /* ── Semantic Tokens ── */
  --bg-primary: var(--navy-950);
  --bg-surface: var(--navy-800);
  --text-primary: var(--slate-100);
  --text-secondary: var(--slate-400);
  --text-muted: var(--slate-600);

  /* ── Spacing ── */
  --radius-lg: 22px;
  --radius-md: 16px;
  --shadow-lg: 0 25px 60px rgba(2, 6, 23, 0.45);
}
```

### Hero Section (simplified)

**Remove redundant text:**
```html
<!-- ❌ OLD -->
<h1>Quest Portfolio Dashboard</h1>
<p>Board-level visibility into quest outcomes, execution momentum, and strategic throughput.</p>

<!-- ✅ NEW -->
<h1>Quest Dashboard</h1>
<p>Engineering quest portfolio tracking and historical analysis.</p>
```

**Mute timestamp:**
```css
.meta-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);  /* Gray, not white */
}

.meta-value {
  font-size: 0.82rem;
  color: var(--text-muted);  /* Gray, not white */
}
```

### Quest Card Design

```html
<article class="quest-card quest-card--finished">
  <header>
    <h3>Quest Dashboard</h3>
    <span class="badge badge--finished">Finished</span>
  </header>

  <p class="pitch">
    Built a static executive dashboard for GitHub Pages that tracks all quest
    statuses. The dashboard displays quest cards with elevator pitches...
  </p>

  <!-- Primary action (prominent) -->
  <a href="/docs/quest-journal/quest-dashboard_2026-02-10.md" class="journal-link">
    View Journal →
  </a>

  <!-- Metadata (muted, bottom) -->
  <footer class="quest-meta">
    <span class="meta-item">quest-dashboard</span>
    <span class="meta-item">Feb 11, 2026</span>
    <span class="meta-item">plan 2 / fix 0</span>
    <a href="https://github.com/org/repo/pull/24" class="meta-link">PR #24</a>
  </footer>
</article>
```

**CSS:**
```css
.pitch {
  font-size: 0.92rem;
  line-height: 1.52;
  color: var(--text-primary);
  flex: 1;
  /* Clamp to 3 lines */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.journal-link {
  color: #60a5fa;  /* Blue */
  font-weight: 600;
  font-size: 0.92rem;
  text-decoration: none;
  border-bottom: 1px solid rgba(96, 165, 250, 0.3);
  margin-top: auto;
}

.quest-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.15);
  font-size: 0.78rem;
  color: var(--text-muted);  /* Muted gray */
}

.meta-link {
  color: var(--text-muted);
  text-decoration: none;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
}
```

---

## Implementation Plan

### Phase 1: Data Model & Loaders

**Files to create:**
```
scripts/quest_dashboard/
  __init__.py
  models.py
  loaders.py
  render.py
scripts/build_quest_dashboard.py
```

**models.py:**
```python
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

StatusType = Literal["completed", "abandoned", "in_progress", "blocked"]
PhaseType = Literal["plan", "building", "reviewing", "fixing", "presenting"]

@dataclass(frozen=True, slots=True)
class JournalEntry:
    """Completed quest from docs/quest-journal/*.md"""
    quest_id: str
    slug: str
    title: str
    elevator_pitch: str
    status: Literal["completed", "abandoned"]
    completed_date: date
    journal_path: Path           # Relative to repo root
    pr_number: int | None        # Extracted from journal or git
    pr_url: str | None           # Computed from pr_number + repo URL

@dataclass(frozen=True, slots=True)
class ActiveQuest:
    """In-progress quest from .quest/*/state.json"""
    quest_id: str
    slug: str
    title: str
    elevator_pitch: str
    status: StatusType
    phase: PhaseType
    updated_at: datetime
    plan_iteration: int | None
    fix_iteration: int | None

@dataclass(frozen=True, slots=True)
class DashboardData:
    finished_quests: list[JournalEntry]      # Completed successfully
    abandoned_quests: list[JournalEntry]     # Completed but abandoned
    active_quests: list[ActiveQuest]         # Still in progress
    warnings: list[str]
    generated_at: datetime
    github_repo_url: str | None
```

**loaders.py functions:**
```python
def load_journal_entries(journal_dir: Path, repo_root: Path) -> list[JournalEntry]:
    """Load completed/abandoned quests from docs/quest-journal/*.md"""
    # Parse markdown files
    # Extract quest_id, status, completed date, summary
    # Determine if completed or abandoned
    # Extract PR number from journal metadata or git log
    # Return sorted by completed_date descending

def load_active_quests(quest_dir: Path) -> list[ActiveQuest]:
    """Load in-progress quests from .quest/*/state.json (exclude archive)"""
    # Glob for state.json files
    # Skip if "archive" in path
    # Parse quest_brief.md for title and elevator pitch
    # Extract iterations from state
    # Return sorted by phase rank, then updated_at descending

def load_dashboard_data(repo_root: Path) -> DashboardData:
    """Load all quest data and merge into dashboard model"""
    journal_entries = load_journal_entries(...)
    active_quests = load_active_quests(...)

    # Separate completed vs abandoned
    finished = [e for e in journal_entries if e.status == "completed"]
    abandoned = [e for e in journal_entries if e.status == "abandoned"]

    # Detect GitHub repo URL
    github_url = detect_github_url(repo_root)

    return DashboardData(
        finished_quests=finished,
        abandoned_quests=abandoned,
        active_quests=active,
        warnings=warnings,
        generated_at=datetime.now(timezone.utc),
        github_repo_url=github_url
    )
```

### Phase 2: HTML Rendering

**render.py structure:**
```python
def render_dashboard(data: DashboardData, output_path: Path, repo_root: Path) -> str:
    """Generate complete HTML document"""

    # Compute summary metrics
    total = len(data.finished_quests) + len(data.abandoned_quests) + len(data.active_quests)

    # Render sections
    hero_html = _render_hero(data, total)
    finished_html = _render_finished_section(data.finished_quests, ...)
    active_html = _render_active_section(data.active_quests)
    abandoned_html = _render_abandoned_section(data.abandoned_quests, ...)

    # Assemble full HTML
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Quest Dashboard</title>
  {_render_css()}
</head>
<body>
  {hero_html}
  {finished_html}
  {active_html}
  {abandoned_html}
</body>
</html>
"""

def _render_finished_section(quests: list[JournalEntry], ...) -> str:
    """Render finished quests section with cards"""
    cards = [_render_finished_card(q, ...) for q in quests]
    return f"""
<section id="finished-quests">
  <h2>Finished Quests</h2>
  <small>{len(quests)} quests completed</small>
  <div class="quest-grid">
    {"".join(cards)}
  </div>
</section>
"""

def _render_finished_card(quest: JournalEntry, ...) -> str:
    """Render a single finished quest card"""
    journal_link = _compute_journal_link(quest.journal_path, ...)
    pr_link_html = ""
    if quest.pr_url:
        pr_link_html = f'<a href="{quest.pr_url}" class="meta-link">PR #{quest.pr_number}</a>'

    return f"""
<article class="quest-card quest-card--finished">
  <header>
    <h3>{escape(quest.title)}</h3>
    <span class="badge badge--finished">Finished</span>
  </header>
  <p class="pitch">{escape(quest.elevator_pitch)}</p>
  <a href="{journal_link}" class="journal-link">View Journal →</a>
  <footer class="quest-meta">
    <span class="meta-item">{escape(quest.slug)}</span>
    <span class="meta-item">{quest.completed_date.isoformat()}</span>
    {pr_link_html}
  </footer>
</article>
"""
```

### Phase 3: CLI & Integration

**build_quest_dashboard.py:**
```python
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = resolve_repo_root(args.repo_root)
    output_path = resolve_output_path(repo_root, args.output)

    data = load_dashboard_data(repo_root)
    html = render_dashboard(data, output_path, repo_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    # Print summary
    print(f"Dashboard built: {output_path}")
    print(f"  Finished: {len(data.finished_quests)}")
    print(f"  In Progress: {len(data.active_quests)}")
    print(f"  Abandoned: {len(data.abandoned_quests)}")

    # Print warnings
    for warning in data.warnings:
        print(f"  Warning: {warning}", file=sys.stderr)

    return 0
```

**GitHub Pages Deployment:**
```bash
# In .github/workflows/dashboard.yml
name: Update Quest Dashboard
on:
  push:
    branches: [main]
    paths:
      - 'docs/quest-journal/*.md'
      - '.quest/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate dashboard
        run: python scripts/build_quest_dashboard.py
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs/dashboard
```

**Local Development:**
```bash
# Generate dashboard from any worktree
python scripts/build_quest_dashboard.py

# View locally
open docs/dashboard/index.html

# Or serve via Python
cd docs/dashboard
python -m http.server 8000
open http://localhost:8000
```

### Phase 4: Testing

**Unit tests:**
```python
# tests/unit/test_loaders.py
def test_load_journal_entry_extracts_elevator_pitch():
    """Verify elevator pitch extracted from ## Summary section"""
    ...

def test_load_active_quest_skips_archived():
    """Verify .quest/archive/* is excluded from active quests"""
    ...

def test_journal_entry_determines_status():
    """Verify abandoned vs completed status detection"""
    ...

# tests/unit/test_render.py
def test_render_finished_card_includes_journal_link():
    ...

def test_render_active_card_excludes_journal_link():
    ...

def test_quest_meta_is_muted():
    """Verify quest ID and iterations use muted CSS class"""
    ...

# tests/integration/test_build_dashboard.py
def test_build_dashboard_from_real_repo():
    """Integration test using actual repo structure"""
    ...
```

---

## PR Link Extraction Strategy

### Problem
Quest journals may or may not contain PR metadata. We need a fallback strategy.

### Solution Hierarchy

**1. Journal Metadata (Primary)**
```markdown
**PR:** #24
**PR:** https://github.com/org/repo/pull/24
```
Parse with regex: `\*\*PR\*\*:\s*#?(\d+)` or `\*\*PR\*\*:\s*(https://github\.com/[^/]+/[^/]+/pull/\d+)`

**2. Git Log (Fallback)**
```bash
# Find merge commit that added this journal file
git log --follow --format='%H %s' -- docs/quest-journal/<filename>

# Check if commit message contains "Merge pull request #123"
# Or check if commit is a merge commit and look for PR number
```

**3. GitHub API (Advanced)**
```bash
# If we have GitHub token
gh api repos/{owner}/{repo}/commits/{sha}/pulls
# Returns PR associated with commit
```

**Implementation:**
```python
def extract_pr_number(journal_path: Path, repo_root: Path) -> int | None:
    """Extract PR number from journal or git history"""

    # 1. Try journal metadata
    text = journal_path.read_text()
    pr_match = re.search(r'\*\*PR\*\*:\s*#?(\d+)', text)
    if pr_match:
        return int(pr_match.group(1))

    # 2. Try git log
    result = subprocess.run(
        ['git', 'log', '--follow', '--format=%s', '-1', '--', journal_path],
        cwd=repo_root,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        # Match "Merge pull request #123" or similar
        merge_match = re.search(r'#(\d+)', result.stdout)
        if merge_match:
            return int(merge_match.group(1))

    return None
```

---

## Journal Link Strategy

### Rendered vs Raw

**User requirement:** Link to **formatted/rendered view**, not raw markdown.

**Options:**

1. **GitHub blob URL** (if dashboard hosted on GitHub Pages):
   ```
   https://github.com/org/repo/blob/main/docs/quest-journal/quest-dashboard_2026-02-10.md
   ```
   - ✅ GitHub renders markdown beautifully
   - ✅ Syntax highlighting, TOC, etc.
   - ❌ Requires internet connection

2. **Relative link to markdown file** (if dashboard is local):
   ```
   ../../quest-journal/quest-dashboard_2026-02-10.md
   ```
   - ❌ Browser shows raw markdown (unrendered)
   - ❌ Bad UX

3. **Convert markdown to HTML** (build-time):
   ```python
   import markdown
   html = markdown.markdown(journal_text)
   output_path.write_text(html)
   ```
   - ✅ Rendered locally
   - ✅ Works offline
   - ❌ Increases build complexity
   - ❌ Need CSS for markdown styling

**Recommendation: Option 1 (GitHub blob URL)**
- Most dashboards will be hosted on GitHub Pages
- Best UX (GitHub's markdown renderer is excellent)
- Fallback: If no GitHub URL detected, link to raw file with warning

**Implementation:**
```python
def compute_journal_link(journal_path: Path, github_base_url: str | None, output_path: Path, repo_root: Path) -> str:
    """Compute link to journal (rendered if possible)"""

    if github_base_url:
        # GitHub blob URL
        posix_path = journal_path.as_posix()
        return f"{github_base_url.rstrip('/')}/blob/main/{posix_path}"

    # Fallback: relative path
    # (This will show raw markdown in browser)
    output_dir = output_path.parent
    journal_full = (repo_root / journal_path).resolve()
    rel_path = os.path.relpath(journal_full, output_dir)
    return rel_path.replace(os.sep, '/')
```

---

## Chart Improvements

### Problem (from user feedback)
- When started = completed, bars overlap → no insight
- Need to show **delta** or **trends** to be meaningful

### Solution: Stacked Area Chart (Status Over Time)

**Instead of:**
- Started vs Completed (often equal)

**Show:**
- Status distribution over time (stacked)
- Monthly buckets: `{ "2026-01": { finished: 8, in_progress: 3, ... } }`
- Visualize: Stacked area or line chart

**SVG Structure:**
```python
def render_trend_chart(data: DashboardData) -> str:
    """Render monthly status trend as stacked area chart"""

    # Bucket quests by month
    buckets = defaultdict(lambda: {
        "finished": 0,
        "in_progress": 0,
        "blocked": 0,
        "abandoned": 0
    })

    for quest in data.finished_quests:
        month = quest.completed_date.strftime("%Y-%m")
        buckets[month]["finished"] += 1

    for quest in data.abandoned_quests:
        month = quest.completed_date.strftime("%Y-%m")
        buckets[month]["abandoned"] += 1

    # For active quests, use updated_at month
    for quest in data.active_quests:
        month = quest.updated_at.strftime("%Y-%m")
        if quest.status == "blocked":
            buckets[month]["blocked"] += 1
        else:
            buckets[month]["in_progress"] += 1

    # Render as stacked area chart
    # ...
```

**Alternative: Velocity Chart**
- Show: Completed per week/month (trend line)
- Show: Started per week/month (trend line)
- Delta: Started - Completed (backlog growth/shrinkage)

---

## File Structure (Final)

```
quest-repo/
  scripts/
    build_quest_dashboard.py         # CLI entry point
    quest_dashboard/
      __init__.py
      models.py                       # Dataclasses
      loaders.py                      # Data extraction
      render.py                       # HTML generation

  tests/
    unit/
      test_quest_dashboard_loaders.py
      test_quest_dashboard_render.py
    integration/
      test_build_quest_dashboard.py

  docs/
    dashboard/
      index.html                      # Generated output
    quest-journal/
      quest-dashboard_2026-02-10.md
      skill-strategy_2026-02-09.md
      ...

  .quest/
    quest-123_2026-02-11__1234/
      state.json
      quest_brief.md
    archive/
      old-quest_2026-01-15__0900/
        state.json
        quest_brief.md

  .github/
    workflows/
      dashboard.yml                   # Auto-deploy on push
```

---

## Success Metrics

**User Acceptance Criteria:**
- ✅ Finished quests shown first, then in-progress, then abandoned
- ✅ Clear visual separation between groups
- ✅ Elevator pitch from journal summary (not user's private request)
- ✅ Timestamp muted (gray, small)
- ✅ Quest ID muted and at bottom
- ✅ "View Journal →" link present and prominent
- ✅ PR link present but muted
- ✅ Iterations shown but muted
- ✅ Professional dark navy design (PR #21 style)
- ✅ Charts show meaningful trends (not just started=completed overlap)
- ✅ Works offline (no CDN dependencies)
- ✅ Can generate from any worktree branch
- ✅ Reads completed quests from main branch journal (source of truth)

**Technical Criteria:**
- ✅ Type-safe dataclasses
- ✅ Comprehensive unit tests (>80% coverage)
- ✅ Modular architecture (models, loaders, render separated)
- ✅ Error handling with warnings (doesn't crash on bad data)
- ✅ Single-file HTML output (self-contained)
- ✅ GitHub Pages deployable
- ✅ CLI with --repo-root and --output flags
- ✅ Auto-detects GitHub remote URL

---

## Branch References for Implementation

**PR #24 (rommel-demonstration):**
- Worktree: `/Users/kjell/ws/quest-rommel-demonstration`
- Files to study:
  - `scripts/quest_dashboard/models.py` - Dataclass patterns
  - `scripts/quest_dashboard/loaders.py` - Journal parsing logic
  - `scripts/build_quest_dashboard.py` - CLI structure

**PR #22 (demo/skills-quest-engineering-discipline):**
- Branch: `demo/skills-quest-engineering-discipline`
- Files to study:
  - `scripts/generate_quest_status_page.py:_PHASE_ORDER` - Phase ranking
  - `scripts/generate_quest_status_page.py:build_dashboard_model()` - Ongoing/Finished split
  - `scripts/generate_quest_status_page.py:parse_journal_summary()` - Summary extraction

**PR #21 (test_with_dashboard_a_demo):**
- Branch: `origin/test_with_dashboard_a_demo`
- Files to study:
  - `docs/dashboard/styles.css` - Design tokens, color palette
  - `docs/dashboard/index.html` - Hero structure, KPI layout
  - `scripts/generate_quest_dashboard_data.py:normalize_status()` - Status mapping

---

## Open Questions for Quest

1. **Chart preference:**
   - Stacked area chart (status distribution over time)?
   - Velocity chart (completed per month trend)?
   - Both?

2. **Empty state messaging:**
   - If no finished quests: "No completed quests yet. Start your first quest!"
   - If no active quests: "No active quests. All work completed!"

3. **Iterations display:**
   - Show for all quests or only finished?
   - Format: "plan 2 / fix 0" or "2 plans, 0 fixes"?

4. **PR link text:**
   - "PR #24"
   - "View PR"
   - Just the PR number in muted text?

5. **Archive handling:**
   - Should archived quests (in `.quest/archive/`) appear in dashboard?
   - If journal exists, prefer journal over archive state?
   - **Recommendation:** Ignore archive; journal is source of truth for completed quests

6. **Sorting tie-breakers:**
   - If two quests have same completion date, sort by title alphabetically?
   - Or by quest_id?

7. **Status badge colors:**
   - Use PR #21's exact colors (finished=#34d399, etc.)?
   - Or adjust for accessibility (WCAG contrast ratios)?

---

## Next Steps

**For Quest Implementation:**

1. **Create skeleton:**
   - `scripts/quest_dashboard/models.py` with dataclasses
   - `scripts/quest_dashboard/loaders.py` with stub functions
   - `scripts/quest_dashboard/render.py` with stub functions
   - `scripts/build_quest_dashboard.py` with CLI

2. **Implement loaders (TDD):**
   - Write tests for journal parsing
   - Write tests for state parsing
   - Implement journal loader
   - Implement active quest loader
   - Implement merge logic

3. **Implement renderer:**
   - Write tests for HTML structure
   - Implement CSS (copy from PR #21, adjust)
   - Implement hero section
   - Implement finished section
   - Implement active section
   - Implement abandoned section
   - Implement chart SVG

4. **Integration & Testing:**
   - Test on real repository data
   - Verify GitHub Pages deployment
   - Get user feedback on visual design
   - Iterate

5. **Documentation:**
   - README in `docs/dashboard/`
   - CLI --help text
   - Comment complex parsing logic

---

**End of Analysis Document**
