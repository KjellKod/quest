# Dashboard Visual Polish: Glows, Charts, and Shine

## Context

The Quest Dashboard (PR #26, `dashboard-v2` quest) shipped with a functional dark navy theme but dropped several visual features that were present in the original PR #21 prototype (`test_with_dashboard_a_demo`). These features were documented in the comprehensive analysis (`ideas/quest-dashboard-analysis-and-plan.md`, lines 517-527) but were cut during the v2 implementation to prioritize architecture, data correctness, and test coverage.

Ref: [dashboard-v2 quest journal](https://github.com/KjellKod/quest/blob/master-dashboard/docs/quest-journal/dashboard-v2_2026-02-12.md)

## What Was Lost

### 1. Animated Page Glows (the "flare/shine" effect)

PR #21 had fixed-position blurred circles that create ambient lighting behind the dashboard content — a soft, colored glow that gives the dark navy background depth and atmosphere. Think of subtle colored light sources bleeding through a frosted surface.

**Implementation pattern (from PR #21):**
```css
.glow {
  position: fixed;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
  pointer-events: none;
  z-index: 0;
}

.glow--green {
  width: 400px;
  height: 400px;
  background: var(--status-finished);
  top: -100px;
  right: 10%;
}

.glow--blue {
  width: 500px;
  height: 500px;
  background: var(--status-in-progress);
  bottom: -150px;
  left: 5%;
}
```

**Current state:** The hero section has `backdrop-filter: blur(12px)` for basic glassmorphism, but there are no ambient glow elements behind it. The background is a flat `radial-gradient` with no colored light sources.

### 2. Interactive Charts

PR #21 included Chart.js-powered visualizations that gave an at-a-glance picture of quest health:

- **Doughnut chart:** Status distribution (finished vs in-progress vs abandoned as a ring chart)
- **Stacked area chart:** Trends over time — monthly buckets showing how quest statuses evolved

**Key features:**
- Interactive legends (click to toggle status categories)
- Tooltips on hover showing exact counts
- Responsive canvas sizing
- Status colors matched the badge colors (green/blue/amber/red)

**Why it was cut:** Originally assumed Chart.js required a CDN. In fact, Chart.js (~200KB minified) can be inlined directly into the HTML — keeping the dashboard a single self-contained file that works offline with no external dependencies.

**Approach: Inline Chart.js** — `render.py` embeds the minified Chart.js source in a `<script>` tag and generates the chart configuration as inline JS. This gives us the full Chart.js feature set for free:
- Interactive tooltips on hover
- Clickable legends to toggle categories
- Smooth animations on load
- Responsive canvas resizing
- Extensive chart types (doughnut, line, bar, stacked area, etc.)

### 3. Richer Glassmorphism and Gradient Layers

PR #21 had "subtle gradients everywhere" — not just the background, but layered gradient effects on surfaces, cards, and section separators. The current implementation uses flat `rgba()` surfaces with a single border.

## What Already Shipped (Keep)

- Dark navy color palette (PR #21 design tokens)
- Card hover lift effect (`transform: translateY(-2px)`)
- Status badge colors (green/blue/amber/red)
- Glassmorphism on hero (`backdrop-filter: blur(12px)`)
- Responsive grid layout
- Three status sections with card grid

## Constraints

- **Single self-contained HTML file** — no CDN, no external dependencies. Chart.js is inlined directly into the HTML by `render.py` at build time.
- **Accessibility** — glows and gradients are decorative only. Charts include text fallbacks (the existing KPI numbers and card listings remain the primary data source).

## Suggested Scope

1. **Ambient glows** — Add 2-3 fixed-position blurred circles behind content using the status colors. Pure CSS, no JS. Small change to `_render_css()`.
2. **Doughnut chart** — Status distribution in the hero section (finished/in-progress/abandoned/blocked as a ring chart). Interactive legend and tooltips via Chart.js.
3. **Time-progression chart** — Stacked area or line chart showing quest status counts over monthly buckets. Shows how the project evolves over time — the key "health at a glance" visual.
4. **Gradient enhancements** — Add subtle gradient overlays to card surfaces and section headers for depth.

### Implementation notes

`render.py` changes:
- Bundle the minified Chart.js source (downloaded once, committed as a vendored asset or embedded as a Python string constant).
- Add a `_render_charts()` function that emits `<canvas>` elements and their Chart.js config as inline `<script>`.
- Compute monthly buckets from quest `created_at` / completion dates for the time-progression data.
- Wire chart colors to the existing CSS custom properties (`--status-finished`, etc.).

## Priority

Medium. The dashboard is functional without these, but they were part of the original vision and make the difference between "works" and "looks great."
