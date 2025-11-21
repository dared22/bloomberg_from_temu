const apiBase = "";
const searchInput = document.getElementById("search");
const regionSelect = document.getElementById("region-filter");
const sentimentSelect = document.getElementById("sentiment-filter");
const refreshBtn = document.getElementById("refresh-btn");
const articleContainer = document.getElementById("articles");
const articleCount = document.getElementById("article-count");
const emptyState = document.getElementById("empty-state");
const statusBanner = document.getElementById("status-banner");
const chartCanvas = document.getElementById("sentimentChart");
if (chartCanvas) {
  chartCanvas.style.display = "block";
  chartCanvas.parentElement.style.padding = "10px 12px 12px";
}

const sentimentColors = {
  bearish: "#e74c3c",
  neutral: "#9fa6b2",
  bullish: "#2563eb",
};

let chartInstance = null;
let state = {
  data: {},
  running: false,
  lastUpdated: null,
  progress: { processed: 0, total: 0 },
};
let lastRenderedUpdate = null;

async function fetchJSON(path, options = {}) {
  const res = await fetch(`${apiBase}${path}`, options);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

function normalizeSentiment(a) {
  const s = (a.nbimSentiment || a.sentiment || "neutral").toLowerCase().trim();
  return ["bearish", "neutral", "bullish"].includes(s) ? s : "neutral";
}

function flattenArticles(data) {
  const all = [];
  Object.entries(data || {}).forEach(([region, items]) => {
    (items || []).forEach((a) => {
      all.push({
        ...a,
        region,
        sentiment: normalizeSentiment(a),
      });
    });
  });
  return all;
}

function setStatusBanner(running, lastUpdated, error) {
  if (error) {
    statusBanner.style.display = "block";
    statusBanner.textContent = `Error: ${error}`;
    statusBanner.style.background = "#fff1f2";
    statusBanner.style.color = "#991b1b";
    statusBanner.style.borderColor = "#fecdd3";
    setRefreshState(false);
    return;
  }

  statusBanner.style.display = "block";
  statusBanner.style.background = "#f0f4ff";
  statusBanner.style.color = "#1e3a8a";
  statusBanner.style.borderColor = "#dbeafe";

  if (running) {
    statusBanner.textContent = "Refreshing in the background – showing cached results…";
    setRefreshState(true);
  } else if (lastUpdated) {
    statusBanner.textContent = `Latest classifier run: ${new Date(lastUpdated).toLocaleString()}`;
    setRefreshState(false);
  } else {
    statusBanner.textContent = "No cached data found yet.";
    setRefreshState(false);
  }
}

function renderChart(data) {
  const regions = Object.keys(data || {});
  const sentiments = ["bearish", "neutral", "bullish"];

  const countsByRegion = regions.map((region) => {
    const tallies = { bearish: 0, neutral: 0, bullish: 0 };
    (data[region] || []).forEach((a) => {
      tallies[normalizeSentiment(a)] += 1;
    });
    return tallies;
  });

  const datasets = sentiments.map((s) => ({
    label: s.charAt(0).toUpperCase() + s.slice(1),
    data: countsByRegion.map((c) => c[s]),
    backgroundColor: sentimentColors[s],
    borderRadius: 6,
    barThickness: 32,
  }));

  if (chartInstance) {
    chartInstance.data.labels = regions;
    chartInstance.data.datasets = datasets;
    chartInstance.update();
    return;
  }

  chartInstance = new Chart(chartCanvas, {
    type: "bar",
    data: {
      labels: regions,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0, color: "#9fa6b2" }, grid: { color: "#eceae6" } },
        x: { stacked: false, ticks: { color: "#0b1c38" }, grid: { display: false } },
      },
      plugins: {
        legend: { position: "top", labels: { usePointStyle: true, boxWidth: 12 } },
      },
    },
  });
}

function populateRegionFilter(data) {
  const regions = Object.keys(data || {});
  regionSelect.innerHTML = "";
  const allOpt = document.createElement("option");
  allOpt.value = "all";
  allOpt.textContent = "All Regions";
  regionSelect.appendChild(allOpt);

  regions.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    regionSelect.appendChild(opt);
  });
}

function escapeHTML(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

function renderArticles(data) {
  const articles = flattenArticles(data);
  const query = (searchInput.value || "").toLowerCase();
  const regionFilter = regionSelect.value || "all";
  const sentimentFilter = sentimentSelect.value || "all";

  const filtered = articles.filter((a) => {
    const haystack = [
      a.title || "",
      a.summary || "",
      a.whyItMatters || a.why_it_matters || "",
      a.source || "",
      (a.tags || []).join(" "),
    ]
      .join(" ")
      .toLowerCase();

    if (query && !haystack.includes(query)) return false;
    if (regionFilter !== "all" && a.region !== regionFilter) return false;
    if (sentimentFilter !== "all" && a.sentiment !== sentimentFilter) return false;
    return true;
  });

  articleContainer.innerHTML = "";
  articleCount.textContent = `(${filtered.length} articles)`;

  if (!filtered.length) {
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";

  filtered.forEach((a) => {
    const card = document.createElement("div");
    card.className = "article-card";

    const header = document.createElement("div");
    header.className = "article-header";

    const title = document.createElement("div");
    title.className = "article-title";
    title.textContent = a.title || "Untitled";

    const pill = document.createElement("span");
    pill.className = "sentiment-pill";
    pill.dataset.tone = a.sentiment;
    pill.textContent = a.sentiment;

    header.appendChild(title);
    header.appendChild(pill);

    const summary = document.createElement("div");
    summary.className = "article-summary";
    summary.textContent = a.summary || "";

    card.appendChild(header);
    card.appendChild(summary);

    const whyText = a.whyItMatters || a.why_it_matters;
    if (whyText) {
      const why = document.createElement("div");
      why.className = "article-why";
      const label = document.createElement("div");
      label.className = "label";
      label.textContent = "Why it matters";
      const body = document.createElement("p");
      body.textContent = whyText;
      why.appendChild(label);
      why.appendChild(body);
      card.appendChild(why);
    }

    const meta = document.createElement("div");
    meta.className = "article-meta";
    const regionSpan = document.createElement("span");
    regionSpan.textContent = `🌍 ${a.region || ""}`;
    const dateSpan = document.createElement("span");
    dateSpan.textContent = `📅 ${a.date || ""}`;
    meta.appendChild(regionSpan);
    meta.appendChild(dateSpan);
    card.appendChild(meta);

    const tagsWrap = document.createElement("div");
    tagsWrap.className = "article-tags";
    (a.tags || []).forEach((t) => {
      const chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.textContent = t;
      tagsWrap.appendChild(chip);
    });
    card.appendChild(tagsWrap);

    const source = document.createElement("div");
    source.className = "article-source";
    source.textContent = `Source: ${a.source || ""}`;
    card.appendChild(source);

    if (a.url) {
      const link = document.createElement("a");
      link.className = "article-link";
      link.href = a.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Open article";
      card.appendChild(link);
    }

    articleContainer.appendChild(card);
  });
}

function renderAll(data, running, lastUpdated, error) {
  populateRegionFilter(data);
  renderChart(data);
  renderArticles(data);
  setStatusBanner(running, lastUpdated, error);
}

async function loadNews() {
  const payload = await fetchJSON("/api/news");
  state = {
    data: payload.data || {},
    running: payload.running,
    lastUpdated: payload.lastUpdated,
    progress: payload.progress || { processed: 0, total: 0 },
    error: payload.error,
  };
  lastRenderedUpdate = payload.lastUpdated;
  renderAll(state.data, state.running, state.lastUpdated, state.error);
}

function setRefreshState(running) {
  if (!refreshBtn) return;
  refreshBtn.disabled = running;
  refreshBtn.textContent = running ? "Updating…" : "Update";
}

async function triggerRefresh() {
  try {
    setRefreshState(true);
    await fetchJSON("/api/refresh", { method: "POST" });
  } catch (e) {
    console.error("Refresh failed", e);
    setRefreshState(false);
  }
}

async function pollStatus() {
  try {
    const status = await fetchJSON("/api/status");
    setStatusBanner(status.running, status.lastUpdated, status.error);

    if (!status.running && status.lastUpdated && status.lastUpdated !== lastRenderedUpdate) {
      await loadNews();
    }
  } catch (e) {
    console.error("Status polling failed", e);
  }
}

function bindControls() {
  [searchInput, regionSelect, sentimentSelect].forEach((el) => {
    el.addEventListener("input", () => renderArticles(state.data));
    el.addEventListener("change", () => renderArticles(state.data));
  });
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      triggerRefresh();
    });
  }
}

async function init() {
  bindControls();
  await loadNews(); // cached first
  triggerRefresh(); // kick off background run
  setInterval(pollStatus, 4000);
}

init().catch((err) => {
  console.error(err);
  setStatusBanner(false, null, err.message || "Failed to load data");
});
