# Dashboard Layout Redesign: Match the Target Executive Design

## Context

The Quest Dashboard was rebuilt (dashboard-v2 quest) and then visually polished (dashboard-visual-polish quest), but the final layout diverges significantly from the target design that was originally envisioned. The target design (captured in `dashboard_great.png`) has a cleaner, more executive look with better information hierarchy.

This quest brings the dashboard layout in line with the target design. The rendering logic lives entirely in `scripts/quest_dashboard/render.py`. The dark navy theme, Chart.js integration, and glow effects are already in place — this is about restructuring the HTML layout and card content, not starting from scratch.

## Current State vs Target

### References
- **Current:** The live dashboard at `docs/dashboard/index.html` (rebuilt from `next-steps` branch)
- **Target design:** PR #21 on branch `test_with_dashboard_a_demo` (remote: `origin/test_with_dashboard_a_demo`)
  - The original prototype HTML can be inspected with: `git show origin/test_with_dashboard_a_demo:docs/dashboard/index.html`
  - PR #21 was closed (not merged) but contains the target layout and styling

## What Needs to Change

### 0. Background, Glows, and Surface Styling

**Current:** Simple single-layer `radial-gradient(ellipse at top, var(--bg-1), var(--bg-0))` body background. Three glow orbs (green, blue, amber) at 15% opacity with 120px blur.

**Target:** Triple-layer body background with colored light bleeding from corners:
```css
body {
  background:
    radial-gradient(1200px circle at 8% -5%, rgba(56, 189, 248, 0.18), transparent 42%),
    radial-gradient(1000px circle at 92% 12%, rgba(45, 212, 191, 0.12), transparent 38%),
    linear-gradient(155deg, var(--bg-0) 0%, var(--bg-1) 68%, #0f172a 100%);
}
```

Two floating glow orbs (not three), bigger and more visible:
```css
.page-glow { width: 480px; height: 480px; filter: blur(95px); opacity: 0.38; }
.page-glow-left  { top: -220px; left: -160px;  background: #0ea5e9; }  /* sky-blue */
.page-glow-right { top: 120px;  right: -180px; background: #14b8a6; }  /* teal */
```

New design token needed: `--status-unknown: #a78bfa` (purple) for the "Unknown" status.
Additional surface variable: `--surface-2: rgba(30, 41, 59, 0.75)` used for quest cards.

Hero uses a gradient surface: `linear-gradient(140deg, rgba(15,23,42,0.9), rgba(30,41,59,0.74))` instead of flat `var(--surface-0)`.

**Changes in `render.py`:** Update `_render_css()` body background, glow classes, and design tokens. Update `_render_glows()` to emit 2 orbs with the new classes.

### 1. Hero Section Redesign

**Current:** Title "Quest Dashboard", simple subtitle, 3 inline KPI numbers (Finished / In Progress / Abandoned) on the left, doughnut chart squeezed into the right side.

**Target:**
- "QUEST INTELLIGENCE" label (small uppercase, accent color) above the title
- Title: "Quest Portfolio Dashboard"
- Subtitle: "Board-level visibility into quest outcomes, execution momentum, and strategic throughput."
- "DATA GENERATED: Feb 12, 2026, 08:54 AM MST" timestamp line (monospace font)
- **No chart in the hero** — the doughnut moves to the charts section

**Changes in `render.py`:** Modify `_render_hero()` to emit the new structure. Remove the `hero-chart` div and doughnut canvas from the hero. Add the intelligence label and timestamp.

### 2. KPI Cards Row

**Current:** 3 KPI values (Finished, In Progress, Abandoned) displayed as plain text items in a flex row inside the hero.

**Target:** 5 separate KPI cards in bordered boxes below the hero:
- **Total Quests** (white text)
- **Finished** (green)
- **In Progress** (blue)
- **Blocked** (amber)
- **Abandoned** (red)

Each card has its own surface background and border, matching the glassmorphism style.

**Changes in `render.py`:** Extract KPIs from the hero into a new `_render_kpi_row()` function. Add a "Total Quests" count. Add "Blocked" as a separate KPI (count quests with blocked status from `data.active_quests`). Each KPI gets its own card wrapper with the surface styling.

**CSS changes:** Add `.kpi-card` class with surface background, border, padding, and border-radius. Update `.kpi-row` to be a 5-column grid.

### 3. Charts Section: Side-by-Side Layout

**Current:** Doughnut chart embedded in the hero section. Time-progression chart in a separate full-width section below with just "Quest Activity Over Time" title.

**Target:** Both charts in a single section, side-by-side in a 2-column grid:
- **Left: "Status Distribution"** — doughnut chart with subtitle "Current normalized state across all quests". Legend below showing all 5 statuses (In Progress, Blocked, Abandoned, Finished, Unknown).
- **Right: "Final Status Over Time"** — stacked area chart with subtitle "Monthly trend using each quest's final/current status". Legend above with all 5 statuses.

**Changes in `render.py`:**
- Modify `_render_charts_section()` to emit a 2-column `.panel-grid` with both chart canvases inside `.panel` containers
- Each panel gets `h2` title and `.panel-subtitle` subtitle
- Chart panels need `min-height: 340px` and chart canvases wrapped in `.chart-wrap` with `height: 255px`
- Move doughnut canvas from hero to left panel
- Update `_render_chart_config()`:
  - **Doughnut:** All 5 statuses (In Progress, Blocked, Abandoned, Finished, Unknown) in that order. `maintainAspectRatio: false`. Legend at bottom with `color: '#cbd5e1'`, `boxWidth: 14`, `padding: 16`. Segments get `borderWidth: 1`, `borderColor: 'rgba(15,23,42,0.85)'`, `hoverOffset: 8`.
  - **Trend:** Change from stacked area to **line chart** with `fill: false`. All 5 statuses. `tension: 0.25`, `borderWidth: 2`, `pointRadius: 3`. `maintainAspectRatio: false`. Legend labels `color: '#cbd5e1'`, `padding: 12`, `boxWidth: 12`.
- Update `_compute_monthly_buckets()` to track all 5 statuses, not just finished/abandoned. Active (in-progress) and blocked quests should be included using their `updated_at` date.

### 4. Single "Quest Portfolio" Section (replaces 3 separate sections)

**Current:** Three separate sections with headers — "Finished" (14 completed quests), "In Progress" (7 active quests), "Abandoned" (2 abandoned quests) — each with its own card grid.

**Target:** One unified "Quest Portfolio" section with:
- Header: "Quest Portfolio" on the left, "N quests represented" count on the right
- All quests in a single 3-column grid, mixed together (not separated by status)
- Sort order: most recently completed/updated first

**Changes in `render.py`:** Replace `_render_finished_section()`, `_render_active_section()`, and `_render_abandoned_section()` with a single `_render_portfolio_section()` that merges all quests, sorts by date, and renders them in one grid.

### 5. Card Content Redesign

**Current cards show:**
- Title + status badge (e.g. "COMPLETED")
- Truncated elevator pitch (3-line clamp with "...")
- "View Journal →" link
- Muted metadata footer: quest_id, date, iterations, PR link

**Target cards show:**
- Title + status badge (e.g. "FINISHED" not "COMPLETED")
- **Full** elevator pitch text (no truncation / line clamping)
- **No** "View Journal" link
- Metadata as labeled key-value pairs:
  - "Quest ID:" quest_id
  - "Completion Date:" date (or "Updated:" for active quests)
  - "Iterations:" plan N / fix N

**Changes in `render.py`:**
- Modify `_render_journal_card()` and `_render_active_card()` (or the unified replacement) to:
  - Remove the `-webkit-line-clamp` truncation from pitch text
  - Remove the journal link
  - Change metadata to a grid of `<span>` elements with `<b>` labels:
    ```html
    <p class="quest-meta">
      <span><b>Quest ID:</b> quest-id-here</span>
      <span><b>Completion Date:</b> Feb 9, 2026</span>
      <span><b>Iterations:</b> plan 1 / fix 0</span>
    </p>
    ```
  - Use "FINISHED" badge text for completed quests (map status values accordingly)
  - Add "Unknown" badge class (`badge-unknown`) with purple color `#a78bfa`

**CSS changes:**
- Quest cards use `--surface-2` background, `border-radius: 14px`, `min-height: 210px`, `display: grid`, `gap: 10px`
- Remove `.quest-pitch` line-clamp styles. Full text with `line-height: 1.58`, `font-size: 0.92rem`
- Remove `.journal-link` styles
- `.quest-meta` becomes a CSS grid with `gap: 5px`, `font-size: 0.83rem`. Bold labels via `.quest-meta b { color: #e2e8f0; font-weight: 600; }`
- Card hover: `translateY(-3px)`, `border-color: rgba(148,163,184, 0.5)` — slightly more lift than current

### 6. Portfolio Section Header

**Current:** Gradient bottom border (green fading to transparent) under section title. Subtitle below the title.

**Target:** The "Quest Portfolio" section wraps everything in a single `.quests-section` panel (surface background + border). Header is flexbox: title left, "N quests represented" count right.

```css
.quests-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; }
.quests-header h2 { font-size: 1.18rem; }
```

### 7. Responsive Breakpoints

**Current:** Single breakpoint at 768px.

**Target:** Three breakpoints:
- **1120px:** KPI grid → 3 columns, quest grid → 2 columns
- **780px:** Layout padding shrinks, hero padding shrinks, KPI grid → 2 columns, chart panels → 1 column, quest grid → 1 column
- **460px:** KPI grid → 1 column, quests header stacks vertically

### 8. Typography

**Current:** System font stack (`-apple-system, BlinkMacSystemFont, ...`).

**Target (PR #21):** Manrope (Google Fonts) + IBM Plex Mono for timestamps. However, since our constraint is **no external dependencies**, we keep the system font stack. The monospace timestamp (`DATA GENERATED:` value) can use the system monospace stack (`ui-monospace, Menlo, Monaco, Consolas, monospace`). KPI numbers should be `font-weight: 800` (extra-bold) instead of current 700.

## Design Direction: "Dark Command Center / Ambient Neon"

The target aesthetic is a full dark-mode "ops dashboard" — the kind of thing you'd see on a wall monitor in a tech company. Key characteristics:

- **Atmospheric:** Ambient colored glows, deep shadows, frosted glass surfaces, translucent layers
- **Colored light bleeding in from corners** via the multi-layer body gradient + glow orbs
- **Vivid status colors** (emerald, blue, amber, red, purple) against near-black backgrounds
- **Bright cyan eyebrow** (#67e8f9) — "QUEST INTELLIGENCE" sets the tone
- **Technical feel:** Monospace timestamps, uppercase labels, tight letter-spacing
- **Large bold KPI numbers** (2rem, weight 800) colored by status
- **Hover effects** with more lift (translateY(-3px)) and border brightening
- **Chart.js canvas charts** in frosted-glass panels — interactive, not decorative

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/quest_dashboard/render.py` | Major restructure: hero, KPI row, charts side-by-side, unified portfolio section, card redesign |
| `tests/unit/test_quest_dashboard_render.py` | Update tests to match new HTML structure |
| `tests/integration/test_build_quest_dashboard.py` | Update integration assertions |

## What NOT to Change

- Chart.js integration approach (vendored, inlined) — keep as-is
- Data loading (`loaders.py`, `models.py`) — no changes needed
- Build script (`build_quest_dashboard.py`) — no changes needed
- URL sanitization logic — keep as-is

## Constraints

- Single self-contained HTML file (no CDN, no external deps)
- All existing tests must be updated, not deleted — test coverage should remain at or above current levels
- Keep the responsive design (mobile-friendly)
- Accessibility: glows and charts are decorative; the data must remain accessible via text

## Priority

High — this is the final step to match the original design vision.

## Status

Implemented — quest `dashboard-layout-redesign_2026-02-13__0103` completed Feb 13, 2026.
