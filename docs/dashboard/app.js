const STATUS_ORDER = ["in_progress", "blocked", "abandoned", "finished", "unknown"];
const STATUS_LABELS = {
  in_progress: "In Progress",
  blocked: "Blocked",
  abandoned: "Abandoned",
  finished: "Finished",
  unknown: "Unknown",
};

const STATUS_COLORS = {
  in_progress: "#60a5fa",
  blocked: "#f59e0b",
  abandoned: "#f87171",
  finished: "#34d399",
  unknown: "#a78bfa",
};

let statusChartInstance = null;
let trendChartInstance = null;

function setBannerState(type, message) {
  const banner = document.getElementById("stateBanner");
  banner.className = `state-banner ${type}`;
  banner.textContent = message;
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

function formatTimestamp(value) {
  if (!value) {
    return "Not available";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(parsed);
}

function statusLabel(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.unknown;
}

function statusClass(status) {
  return `badge-${STATUS_ORDER.includes(status) ? status : "unknown"}`;
}

function numberOrDash(value) {
  return Number.isFinite(value) ? String(value) : "-";
}

function safeTrendPoints(data) {
  const points = data?.trends?.points;
  if (!Array.isArray(points)) {
    return [];
  }
  return points.filter((point) => point && typeof point.period === "string");
}

function applySummary(summary) {
  const byStatus = summary.by_status || {};
  document.getElementById("kpi-total").textContent = String(summary.total || 0);
  document.getElementById("kpi-finished").textContent = String(byStatus.finished || 0);
  document.getElementById("kpi-in-progress").textContent = String(byStatus.in_progress || 0);
  document.getElementById("kpi-blocked").textContent = String(byStatus.blocked || 0);
  document.getElementById("kpi-abandoned").textContent = String(byStatus.abandoned || 0);
}

function buildQuestCard(quest) {
  const status = STATUS_ORDER.includes(quest.status) ? quest.status : "unknown";
  const card = document.createElement("article");
  card.className = "quest-card";

  const title = quest.title || quest.slug || quest.quest_id || "Untitled Quest";
  const pitch = quest.elevator_pitch || "No summary recorded yet.";
  const completionText = quest.completed_date
    ? formatDate(quest.completed_date)
    : quest.status === "finished"
      ? "Completed date missing"
      : "Not finished yet";

  card.innerHTML = `
    <div class="quest-card-header">
      <h3 class="quest-title"></h3>
      <span class="status-badge ${statusClass(status)}"></span>
    </div>
    <p class="quest-pitch"></p>
    <p class="quest-meta">
      <span><b>Quest ID:</b> ${quest.quest_id || "Not available"}</span>
      <span><b>Completion Date:</b> ${completionText}</span>
      <span><b>Iterations:</b> plan ${numberOrDash(quest.plan_iteration)} / fix ${numberOrDash(quest.fix_iteration)}</span>
    </p>
  `;

  card.querySelector(".quest-title").textContent = title;
  card.querySelector(".status-badge").textContent = statusLabel(status);
  card.querySelector(".quest-pitch").textContent = pitch;

  return card;
}

function renderQuestCards(quests) {
  const questGrid = document.getElementById("questGrid");
  questGrid.innerHTML = "";

  const sorted = [...quests].sort((a, b) => {
    const aDate = a.completed_date || a.updated_at || "";
    const bDate = b.completed_date || b.updated_at || "";
    if (aDate !== bDate) {
      return bDate.localeCompare(aDate);
    }
    return (a.title || "").localeCompare(b.title || "");
  });

  for (const quest of sorted) {
    questGrid.appendChild(buildQuestCard(quest));
  }

  document.getElementById("questCountLabel").textContent = `${sorted.length} quests represented`;
}

function teardownCharts() {
  if (statusChartInstance) {
    statusChartInstance.destroy();
    statusChartInstance = null;
  }
  if (trendChartInstance) {
    trendChartInstance.destroy();
    trendChartInstance = null;
  }
}

function renderCharts(data) {
  teardownCharts();

  const statusCanvas = document.getElementById("statusChart");
  const trendCanvas = document.getElementById("trendChart");

  if (typeof window.Chart !== "function") {
    const fallback = document.createElement("p");
    fallback.className = "fallback-note";
    fallback.textContent = "Charts unavailable: Chart.js failed to load from CDN.";
    statusCanvas.closest(".panel").appendChild(fallback.cloneNode(true));
    trendCanvas.closest(".panel").appendChild(fallback);
    return;
  }

  const summaryCounts = STATUS_ORDER.map((status) => data.summary.by_status?.[status] || 0);

  statusChartInstance = new window.Chart(statusCanvas, {
    type: "doughnut",
    data: {
      labels: STATUS_ORDER.map((status) => STATUS_LABELS[status]),
      datasets: [
        {
          data: summaryCounts,
          backgroundColor: STATUS_ORDER.map((status) => STATUS_COLORS[status]),
          borderWidth: 1,
          borderColor: "rgba(15, 23, 42, 0.85)",
          hoverOffset: 8,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#cbd5e1",
            boxWidth: 14,
            padding: 16,
          },
        },
      },
    },
  });

  const trendPoints = safeTrendPoints(data);

  trendChartInstance = new window.Chart(trendCanvas, {
    type: "line",
    data: {
      labels: trendPoints.map((point) => point.period),
      datasets: STATUS_ORDER.map((status) => ({
        label: STATUS_LABELS[status],
        data: trendPoints.map((point) => point[status] || 0),
        borderColor: STATUS_COLORS[status],
        backgroundColor: STATUS_COLORS[status],
        fill: false,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 3,
      })),
    },
    options: {
      maintainAspectRatio: false,
      interaction: {
        mode: "nearest",
        intersect: false,
      },
      scales: {
        x: {
          ticks: {
            color: "#cbd5e1",
          },
          grid: {
            color: "rgba(148, 163, 184, 0.16)",
          },
        },
        y: {
          beginAtZero: true,
          precision: 0,
          ticks: {
            color: "#cbd5e1",
            stepSize: 1,
          },
          grid: {
            color: "rgba(148, 163, 184, 0.16)",
          },
        },
      },
      plugins: {
        legend: {
          labels: {
            color: "#cbd5e1",
            padding: 12,
            boxWidth: 12,
          },
        },
      },
    },
  });
}

function validateData(data) {
  if (!data || typeof data !== "object") {
    throw new Error("invalid_json");
  }
  if (!data.summary || typeof data.summary !== "object") {
    throw new Error("invalid_json");
  }
  if (!Array.isArray(data.quests)) {
    throw new Error("invalid_json");
  }
  if (!data.summary.by_status || typeof data.summary.by_status !== "object") {
    throw new Error("invalid_json");
  }
}

function renderDashboard(data) {
  applySummary(data.summary);
  document.getElementById("generatedAt").textContent = formatTimestamp(data.generated_at);

  const main = document.getElementById("dashboardMain");
  main.classList.remove("hidden");

  if (!data.quests.length) {
    setBannerState("is-empty", "No quests available yet. Generate data after quest activity to populate this dashboard.");
    document.getElementById("chartsSection").classList.add("hidden");
    document.getElementById("questGrid").innerHTML = "";
    document.getElementById("questCountLabel").textContent = "0 quests represented";
    teardownCharts();
    return;
  }

  document.getElementById("chartsSection").classList.remove("hidden");
  renderCharts(data);
  renderQuestCards(data.quests);
  setBannerState("is-ready", "");
}

async function loadDashboardData() {
  setBannerState("is-loading", "Loading dashboard data...");

  let response;
  try {
    response = await fetch("./dashboard-data.json", { cache: "no-store" });
  } catch (error) {
    throw new Error("fetch_failure");
  }

  if (!response.ok) {
    throw new Error("fetch_failure");
  }

  const body = await response.text();
  let payload;
  try {
    payload = JSON.parse(body);
  } catch (error) {
    throw new Error("invalid_json");
  }

  validateData(payload);
  return payload;
}

async function init() {
  try {
    const data = await loadDashboardData();
    renderDashboard(data);
  } catch (error) {
    const main = document.getElementById("dashboardMain");
    main.classList.add("hidden");

    if (error.message === "invalid_json") {
      setBannerState("is-error", "Data format invalid. Regenerate dashboard-data.json and retry.");
      return;
    }

    setBannerState("is-error", "Dashboard data unavailable. Ensure dashboard-data.json exists and is served correctly.");
  }
}

document.addEventListener("DOMContentLoaded", init);
