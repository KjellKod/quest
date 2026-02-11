# Quest Dashboard

Static executive dashboard for Quest portfolio tracking, served from `docs/dashboard/`.

## What It Shows

- KPI summary: total, finished, in-progress, blocked, abandoned
- Status distribution chart (doughnut)
- Monthly final-status-over-time chart (line)
- Quest cards with title, elevator pitch, status, completion date, and iteration counts

## Data Pipeline

Generate dashboard data from journal + active/archive state files:

```bash
python3 scripts/generate_quest_dashboard_data.py
```

This writes:

- `docs/dashboard/dashboard-data.json`

## Local Preview

Serve `docs/` as static files (recommended for fetch behavior):

```bash
cd docs
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000/dashboard/`

## GitHub Pages Deployment

1. Open repository settings on GitHub.
2. Navigate to `Settings -> Pages`.
3. Set **Build and deployment** source to:
   - `Deploy from a branch`
   - Branch: `main`
   - Folder: `/docs`
4. Save and wait for Pages publish.

Expected URL format:

- `https://<org-or-user>.github.io/<repo>/dashboard/`

Example for this repository:

- `https://kjellkod.github.io/quest/dashboard/`

## Update Workflow

When quest journal/state data changes:

1. Regenerate JSON:

```bash
python3 scripts/generate_quest_dashboard_data.py
```

2. Validate JSON:

```bash
python3 -m json.tool docs/dashboard/dashboard-data.json >/dev/null
```

3. Commit the updated data and dashboard assets.
