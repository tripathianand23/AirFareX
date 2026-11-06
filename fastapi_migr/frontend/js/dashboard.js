/**
 * AirFareX Dashboard Client Controller
 * 1:1 Parity with Streamlit Dashboard Architecture
 */

// Global State
const state = {
    currentTab: 'overview',
    filters: {
        startDate: null,
        endDate: null,
        routes: [],
        airlines: [],
        sources: [],
    },
    filterBounds: {
        minDate: null,
        maxDate: null,
    },
    rawPage: 1,
    rawPageSize: 50,
    rawTotalPages: 1,
    tabDataCache: {},
    renderedTabKeys: {},
    loadingTabKeys: {},
};

// Formal label dictionary matching dashboard/app.py
const FORMAL_LABELS = {
    "collection_date": "Collection Date",
    "collection_timestamp": "Collection Timestamp",
    "overall_airfare_index": "Airfare Index",
    "daily_change_pct": "Daily Change (%)",
    "coverage_status": "Coverage Status",
    "publication_status": "Publication Status",
    "route_index": "Route Index",
    "advance_days": "Advance Days",
    "airfare_index": "Airfare Index",
    "observed_days": "Observed Days",
    "observations": "Observations",
    "median_fare": "Median Fare (INR)",
    "mean_fare": "Mean Fare (INR)",
    "minimum_fare": "Minimum Fare (INR)",
    "maximum_fare": "Maximum Fare (INR)",
    "min_fare": "Minimum Fare (INR)",
    "max_fare": "Maximum Fare (INR)",
    "routes_present": "Routes Present",
    "expected_routes": "Expected Routes",
    "route_coverage_ratio": "Route Coverage Ratio",
    "lead_windows_present": "Lead Windows Present",
    "expected_lead_windows": "Expected Lead Windows",
    "lead_time_coverage_ratio": "Lead-Time Coverage Ratio",
    "observed_strata": "Observed Strata",
    "required_strata": "Required Strata",
    "stratum_coverage_ratio": "Stratum Coverage Ratio",
    "index_status": "Index Status",
    "status": "Status",
    "source": "Source",
    "origin": "Origin",
    "destination": "Destination",
    "total_fare": "Total Fare (INR)",
    "base_fare": "Base Fare (INR)",
    "taxes": "Taxes & Fees (INR)",
    "fees": "Fees (INR)",
    "departure_time": "Departure Time",
    "flight_number": "Flight Number",
    "airline": "Airline",
    "anomaly_flag": "Anomaly Flag",
    "week": "Week",
    "month": "Month",
    "share_pct": "Share (%)",
    "latest_index": "Latest Index",
    "change_pct": "Period Change (%)",
    "median_index": "Median Index",
    "missing_routes": "Missing Routes",
    "missing_lead_windows": "Missing Lead Windows",
    "coverage_complete": "Coverage Complete",
    "pipeline_metric": "Pipeline Metric",
    "value": "Value",
    "metric": "Pipeline Metric",
    "failure": "Failure",
    "class": "Class",
    "action": "Action",
};

// Helpers
function formatLabel(key) {
    if (!key) return "";
    const k = String(key).toLowerCase();
    if (FORMAL_LABELS[k]) return FORMAL_LABELS[k];
    if (FORMAL_LABELS[key]) return FORMAL_LABELS[key];
    return String(key).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function formatRoute(val) {
    if (!val) return "—";
    const str = String(val);
    if (str.includes("_")) {
        const parts = str.split("_");
        if (parts.length === 2 && parts[0] && parts[1]) {
            return `${parts[0].toUpperCase()} → ${parts[1].toUpperCase()}`;
        }
    }
    return str;
}

function formatValue(val, key) {
    if (val === null || val === undefined || val === "") return "—";
    const k = String(key || "").toLowerCase();
    if (k.includes("route") && typeof val === "string") {
        return formatRoute(val);
    }
    if (typeof val === "boolean") {
        return val ? "True" : "False";
    }
    if (typeof val === "number") {
        if (Number.isInteger(val)) {
            return val.toLocaleString("en-IN");
        }
        return val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return String(val);
}

function formatPct(val) {
    if (val === null || val === undefined || isNaN(val)) return "—";
    const sign = val > 0 ? "+" : "";
    return `${sign}${Number(val).toFixed(2)}%`;
}

function showLoading(show) {
    const el = document.getElementById("loading-badge");
    if (el) el.style.display = show ? "flex" : "none";
}

// API request wrapper with browser-memory response caching.
const API_CACHE_TTL_MS = 300000;

async function apiGet(endpoint, params = {}) {
    const url = new URL(endpoint, window.location.origin);

    for (const [k, v] of Object.entries(params)) {
        if (Array.isArray(v)) {
            v.forEach(x => url.searchParams.append(k, x));
        } else if (v !== null && v !== undefined && v !== "") {
            url.searchParams.set(k, v);
        }
    }

    // The complete URL is the cache key, including filters and pagination.
    const cacheKey = url.toString();
    const cached = state.tabDataCache[cacheKey];

    if (cached && cached.promise) {
        return cached.promise;
    }

    if (cached && cached.data !== undefined) {
        if (Date.now() - cached.savedAt < API_CACHE_TTL_MS) {
            return cached.data;
        }
        delete state.tabDataCache[cacheKey];
    }

    const request = (async () => {
        const res = await fetch(cacheKey);

        if (!res.ok) {
            throw new Error(`API call failed: ${res.status} ${res.statusText}`);
        }

        return res.json();
    })();

    // Store the in-flight promise too, preventing duplicate simultaneous requests.
    state.tabDataCache[cacheKey] = {
        promise: request,
        savedAt: Date.now()
    };

    try {
        const data = await request;
        state.tabDataCache[cacheKey] = {
            data,
            savedAt: Date.now()
        };
        return data;
    } catch (error) {
        delete state.tabDataCache[cacheKey];
        throw error;
    }
}

function getFilterParams() {
    const p = {};
    if (state.filters.startDate) p.start_date = state.filters.startDate;
    if (state.filters.endDate) p.end_date = state.filters.endDate;
    if (state.filters.routes.length) p.routes = state.filters.routes;
    if (state.filters.airlines.length) p.airlines = state.filters.airlines;
    if (state.filters.sources.length) p.sources = state.filters.sources;
    return p;
}

// Table Renderer matching Streamlit st.dataframe
function renderTable(containerId, records, customColumns = null) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!records || !records.length) {
        container.innerHTML = '<div class="st-alert st-alert-info"><span>ℹ️</span><span>No records available.</span></div>';
        return;
    }

    const cols = customColumns || Object.keys(records[0]);
    let html = `
        <div class="st-dataframe-container">
            <div class="st-dataframe-scroll">
                <table class="st-dataframe">
                    <thead>
                        <tr>
                            ${cols.map(c => `<th>${formatLabel(c)}</th>`).join("")}
                        </tr>
                    </thead>
                    <tbody>
    `;

    for (const row of records) {
        html += "<tr>";
        for (const col of cols) {
            html += `<td>${formatValue(row[col], col)}</td>`;
        }
        html += "</tr>";
    }

    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// Streamlit placeholder color map (what Streamlit's React frontend would replace)
// Source: Streamlit static/js/index.CxIUUfab.js mF() function
const STREAMLIT_COLOR_MAP = {
    "#000001": "#0068c9",  // Streamlit Blue (light theme cat[0])
    "#000002": "#83c9ff",  // Sky Blue (cat[1])
    "#000003": "#ff2b2b",  // Red (cat[2])
    "#000004": "#ffabab",  // Soft Red (cat[3])
    "#000005": "#29b09d",  // Teal (cat[4])
    "#000006": "#7defa1",  // Mint (cat[5])
    "#000007": "#ff8700",  // Orange (cat[6])
    "#000008": "#ffd16a",  // Amber (cat[7])
    "#000009": "#6d3fc0",  // Purple (cat[8])
    "#000010": "#d5dae5",  // Slate (cat[9])
    // Sequential fallbacks
    "#000011": "#0d0887", "#000012": "#46039f", "#000013": "#7201a8",
    "#000014": "#9c179e", "#000015": "#bd3786", "#000016": "#d8576b",
    "#000017": "#ed7953", "#000018": "#fb9f3a", "#000019": "#fdca26", "#000020": "#f0f921",
};

function fixStreamlitColors(figSpec) {
    if (!figSpec || !figSpec.data) return figSpec;
    // Deep clone to avoid mutating cached data
    const spec = JSON.parse(JSON.stringify(figSpec));
    const jsonStr = JSON.stringify(spec);
    const fixed = jsonStr.replace(/#00000[0-9]|#000010|#00001[0-9]|#000020/gi, match => {
        return STREAMLIT_COLOR_MAP[match.toLowerCase()] || match;
    });
    return JSON.parse(fixed);
}

// Plotly Plotter with transparent background and Streamlit styles
function renderPlotly(containerId, figSpec) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!figSpec || !figSpec.data) {
        container.innerHTML =
            '<div class="st-alert st-alert-info"><span>ℹ️</span><span>No chart data available.</span></div>';
        return;
    }

    const cleanSpec = fixStreamlitColors(figSpec);

    // Give the route x lead-time heatmap its own readable dimensions.
    const isRouteLeadHeatmap = containerId === "rt-heatmap-chart";
    const chartHeight = isRouteLeadHeatmap
        ? Math.max(560, Number(cleanSpec.layout?.height) || 680)
        : 420;

    container.style.width = "100%";
    container.style.height = `${chartHeight}px`;
    container.style.minHeight = `${chartHeight}px`;

    const layout = {
        ...cleanSpec.layout,
        height: chartHeight,
        autosize: true,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: {
            family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            size: 13,
            color: '#475569',
        },
        margin: isRouteLeadHeatmap
            ? { l: 105, r: 85, t: 45, b: 85 }
            : {
                l: 60,
                r: 35,
                t: 65,
                b: 65,
            },
    };

    const plotConfig = {
        responsive: true,
        displayModeBar: false,
    };

    // Reuse an initialized Plotly graph instead of rebuilding it.
    const renderPromise = container.data
        ? Plotly.react(container, cleanSpec.data, layout, plotConfig)
        : Plotly.newPlot(container, cleanSpec.data, layout, plotConfig);

    renderPromise.catch(error => {
        console.error(`Plotly rendering failed for ${containerId}:`, error);
    });
}

// Custom Multi-select Component Setup
function setupMultiSelect(containerId, options, onSelectionChange) {
    const box = document.getElementById(containerId);
    if (!box) return;

    const toggle = box.querySelector(".multi-select-toggle");
    const dropdown = box.querySelector(".multi-select-dropdown");
    const searchInput = box.querySelector(".multi-select-search");
    const optionsContainer = box.querySelector(".multi-select-options");

    let selectedValues = [];

    function renderOptions(filterText = "") {
        const filtered = options.filter(opt =>
            opt.toLowerCase().includes(filterText.toLowerCase())
        );

        optionsContainer.innerHTML = filtered.map(opt => `
            <div class="multi-select-option" data-value="${opt}">
                <input type="checkbox" ${selectedValues.includes(opt) ? "checked" : ""}>
                <span>${opt}</span>
            </div>
        `).join("");
    }

    function renderToggle() {
        if (!selectedValues.length) {
            toggle.innerHTML = `<span class="multi-select-placeholder">Choose ${containerId.split("-")[0]}</span>`;
            return;
        }

        toggle.innerHTML = selectedValues.map(val => `
            <span class="chip">
                <span>${val}</span>
                <span class="chip-remove" data-remove="${val}">&times;</span>
            </span>
        `).join("");
    }

    renderOptions();
    renderToggle();

    // Toggle dropdown open/close
    toggle.addEventListener("click", (e) => {
        if (e.target.classList.contains("chip-remove")) {
            const valToRemove = e.target.getAttribute("data-remove");
            selectedValues = selectedValues.filter(x => x !== valToRemove);
            renderToggle();
            renderOptions(searchInput.value);
            onSelectionChange(selectedValues);
            return;
        }
        dropdown.classList.toggle("open");
        if (dropdown.classList.contains("open")) {
            searchInput.focus();
        }
    });

    // Close when clicking outside
    document.addEventListener("click", (e) => {
        if (!box.contains(e.target)) {
            dropdown.classList.remove("open");
        }
    });

    // Search filter
    searchInput.addEventListener("input", (e) => {
        renderOptions(e.target.value);
    });

    // Option selection
    optionsContainer.addEventListener("click", (e) => {
        const optionEl = e.target.closest(".multi-select-option");
        if (!optionEl) return;
        const val = optionEl.getAttribute("data-value");
        if (selectedValues.includes(val)) {
            selectedValues = selectedValues.filter(x => x !== val);
        } else {
            selectedValues.push(val);
        }
        renderToggle();
        renderOptions(searchInput.value);
        onSelectionChange(selectedValues);
    });
}

// ---------------------------------------------------------
// Tab Data Loaders
// ---------------------------------------------------------

async function loadOverviewTab() {
    showLoading(true);
    try {
        const requestFilters = JSON.stringify(getFilterParams());
        const data = await apiGet("/api/dashboard/overview", getFilterParams());
        if (requestFilters !== JSON.stringify(getFilterParams())) return;

        // Headline overview KPIs
        const kpis = data.kpis || {};
        document.getElementById("ov-latest-index").textContent = kpis.current_index != null ? kpis.current_index.toFixed(2) : "—";

        const deltaEl = document.getElementById("ov-period-change");
        if (kpis.period_change != null) {
            deltaEl.textContent = formatPct(kpis.period_change);
            deltaEl.className = "st-metric-delta " + (kpis.period_change >= 0 ? "positive" : "negative");
        } else {
            deltaEl.textContent = "—";
            deltaEl.className = "st-metric-delta";
        }

        document.getElementById("ov-prev-index").textContent = kpis.previous_index != null ? kpis.previous_index.toFixed(2) : "—";
        document.getElementById("ov-total-obs").textContent = (kpis.total_observations || 0).toLocaleString("en-IN");
        document.getElementById("ov-total-routes").textContent = (kpis.total_routes || 0).toLocaleString("en-IN");
        const retentionEl = document.getElementById("ov-retention-rate");
        retentionEl.textContent = kpis.retention_rate_percent != null
            ? `${Number(kpis.retention_rate_percent).toFixed(2)}%`
            : "—";
        document.getElementById("ov-source-count").textContent = (kpis.source_count || 0).toLocaleString("en-IN");

        // Movement callout
        document.getElementById("ov-movement-callout").innerHTML = `
            <b>Base = 100</b> · Latest movement ${formatPct(kpis.period_change)} ·
            7-day movement ${formatPct(kpis.change_7d)} · 30-day movement ${formatPct(kpis.change_30d)}
        `;

        // Main index chart & table
        renderPlotly("ov-overall-chart", data.overall_chart);
        renderTable("ov-overall-table", data.overall_table);

        // Route movers
        renderPlotly("ov-route-pulse-chart", data.route_pulse_chart);
        renderTable("ov-route-pulse-table", data.route_pulse_table);

        // Lead time chart & table
        renderPlotly("ov-lead-chart", data.lead_chart);
        renderTable("ov-lead-table", data.lead_table);

        // Source coverage
        renderPlotly("ov-source-pie-chart", data.source_chart);

        // Quality
        const q = data.quality || {};
        renderPlotly("ov-quality-gauge", q.chart);
        renderTable("ov-quality-table", q.table);
        document.getElementById("ov-qa-missing").textContent = q.missing_pct != null ? `${q.missing_pct.toFixed(1)}%` : "—";
        document.getElementById("ov-qa-duplicates").textContent = q.duplicate_pct != null ? `${q.duplicate_pct.toFixed(1)}%` : "—";
        document.getElementById("ov-qa-quality").textContent = q.score != null ? `${q.score.toFixed(1)}%` : "—";

    } finally {
        showLoading(false);
    }
}

async function loadIndexAnalyticsTab() {
    showLoading(true);
    try {
        const requestFilters = JSON.stringify(getFilterParams());
        const data = await apiGet("/api/dashboard/index-analytics", getFilterParams());
        if (requestFilters !== JSON.stringify(getFilterParams())) return;
        if (data.empty) {
            document.getElementById("idx-main-chart").innerHTML = '<div class="st-alert st-alert-info"><span>ℹ️</span><span>No index data available.</span></div>';
            return;
        }

        renderPlotly("idx-main-chart", data.chart);
        renderTable("idx-main-table", data.index_table);
        renderTable("idx-weekly-table", data.weekly_table);
        renderTable("idx-monthly-table", data.monthly_table);
        renderTable("idx-audit-trail-table", data.audit_trail);
    } finally {
        showLoading(false);
    }
}

async function loadRouteIntelligenceTab() {
    showLoading(true);
    try {
        const requestFilters = JSON.stringify(getFilterParams());
        const data = await apiGet("/api/dashboard/route-intelligence", getFilterParams());
        if (requestFilters !== JSON.stringify(getFilterParams())) return;
        if (data.empty) {
            document.getElementById("rt-indices-chart").innerHTML = '<div class="st-alert st-alert-info"><span>ℹ️</span><span>No route-level index data available.</span></div>';
            return;
        }

        const kpis = data.kpis || {};
        document.getElementById("rt-analysed").textContent = (kpis.routes_analysed || 0).toLocaleString("en-IN");
        document.getElementById("rt-largest-inc").textContent = kpis.largest_increase || "—";
        document.getElementById("rt-largest-dec").textContent = kpis.largest_decrease || "—";
        document.getElementById("rt-median-idx").textContent = kpis.median_route_index != null ? kpis.median_route_index.toFixed(2) : "—";

        renderPlotly("rt-indices-chart", data.route_chart);

        // Populate Route Explorer Select
        const explorerSelect = document.getElementById("route-explorer-select");
        const prevVal = explorerSelect.value;
        explorerSelect.innerHTML = '<option value="All Routes">All Routes</option>' +
            (data.explorer_routes || []).map(r => `<option value="${r}">${formatRoute(r)}</option>`).join("");
        if (prevVal && (data.explorer_routes || []).includes(prevVal)) {
            explorerSelect.value = prevVal;
        }

        // Load route explorer initial records
        await loadRouteExplorerRecords();

        renderTable("rt-ranking-table", data.ranking_table);
        renderPlotly("rt-heatmap-chart", data.heatmap_chart);
        renderTable("rt-heatmap-table", data.heatmap_table);
        renderTable("rt-coverage-table", data.coverage_table);
    } finally {
        showLoading(false);
    }
}

async function loadRouteExplorerRecords() {
    const route = document.getElementById("route-explorer-select").value;
    const params = { ...getFilterParams(), route };
    const requestKey = JSON.stringify(params);
    const res = await apiGet("/api/dashboard/route-explorer", params);
    const currentKey = JSON.stringify({
        ...getFilterParams(),
        route: document.getElementById("route-explorer-select").value
    });
    if (requestKey !== currentKey) return;
    renderTable("rt-explorer-table", res.items);
    document.getElementById("rt-explorer-caption").textContent = `Showing ${(res.total || 0).toLocaleString("en-IN")} route-index records. Use the route selector above to inspect a specific route.`;
}

async function loadLeadTimeTab() {
    showLoading(true);
    try {
        const requestFilters = JSON.stringify(getFilterParams());
        const data = await apiGet("/api/dashboard/lead-time", getFilterParams());
        if (requestFilters !== JSON.stringify(getFilterParams())) return;
        if (data.empty) {
            document.getElementById("lead-main-chart").innerHTML = '<div class="st-alert st-alert-info"><span>ℹ️</span><span>No lead-time contribution data available.</span></div>';
            return;
        }

        renderPlotly("lead-main-chart", data.chart);
        renderTable("lead-chart-table", data.chart_table);
        renderTable("lead-snapshot-table", data.snapshot_table);
        renderTable("lead-distribution-table", data.distribution_table);

        // Populate Lead-time explorer selects
        const advSelect = document.getElementById("lead-filter-advance");
        const prevAdv = advSelect.value;
        advSelect.innerHTML = '<option value="All Lead Times">All Lead Times</option>' +
            (data.lead_options || []).map(o => `<option value="T+${o}">T+${o}</option>`).join("");
        if (prevAdv) advSelect.value = prevAdv;

        const rtSelect = document.getElementById("lead-filter-route");
        const prevRt = rtSelect.value;
        rtSelect.innerHTML = '<option value="All Routes">All Routes</option>' +
            (data.route_options || []).map(r => `<option value="${r}">${formatRoute(r)}</option>`).join("");
        if (prevRt) rtSelect.value = prevRt;

        await loadLeadTimeExplorerRecords();
    } finally {
        showLoading(false);
    }
}

async function loadLeadTimeExplorerRecords() {
    const leadTime = document.getElementById("lead-filter-advance").value;
    const route = document.getElementById("lead-filter-route").value;
    const params = { ...getFilterParams(), lead_time: leadTime, route };
    const requestKey = JSON.stringify(params);
    const res = await apiGet("/api/dashboard/lead-time-explorer", params);
    const currentKey = JSON.stringify({
        ...getFilterParams(),
        lead_time: document.getElementById("lead-filter-advance").value,
        route: document.getElementById("lead-filter-route").value
    });
    if (requestKey !== currentKey) return;
    renderTable("lead-explorer-table", res.items);
    document.getElementById("lead-explorer-caption").textContent = `Showing ${(res.total || 0).toLocaleString("en-IN")} lead-time fare records. Use the filters above to inspect a specific lead-time window or route.`;
}

async function loadDataQualityTab(anomalyDate = null) {
    showLoading(true);

    try {
        const params = {
            ...getFilterParams(),
            ...(anomalyDate ? { anomaly_date: anomalyDate } : {})
        };

        const requestKey = JSON.stringify(params);
        const data = await apiGet("/api/dashboard/data-quality", params);

        const currentParams = {
            ...getFilterParams(),
            ...(anomalyDate ? { anomaly_date: anomalyDate } : {})
        };

        if (requestKey !== JSON.stringify(currentParams)) return;

        const k = data.kpis || {};
        const dc = data.data_centre || {};
        const pipeline = dc.pipeline || {};

        // Existing data-quality KPIs.
        document.getElementById("dq-total-obs").textContent =
            (k.total_observations || 0).toLocaleString("en-IN");

        document.getElementById("dq-missing-fare").textContent =
            `${(k.missing_fare_pct || 0).toFixed(2)}%`;

        document.getElementById("dq-dup-rate").textContent =
            `${(k.duplicate_pct || 0).toFixed(2)}%`;

        document.getElementById("dq-score").textContent =
            `${(k.quality_score || 0).toFixed(1)}/100`;

        document.getElementById("dq-status").textContent = k.status || "—";

        // Processed observation dataset metrics.
        document.getElementById("dc-completeness").textContent =
            k.fare_completeness_pct != null
                ? `${Number(k.fare_completeness_pct).toFixed(2)}%`
                : "—";

        document.getElementById("dc-retention").textContent =
            pipeline.retention_rate_percent != null
                ? `${Number(pipeline.retention_rate_percent).toFixed(2)}%`
                : "—";

        document.getElementById("dc-routes").textContent =
            (dc.route_count || 0).toLocaleString("en-IN");

        document.getElementById("dc-sources").textContent =
            (dc.source_count || 0).toLocaleString("en-IN");

        document.getElementById("dc-airlines").textContent =
            (dc.airline_count || 0).toLocaleString("en-IN");

        const formatTimestamp = value =>
            value ? String(value).replace("T", " ").slice(0, 19) : "—";

        document.getElementById("dc-earliest").textContent =
            formatTimestamp(dc.earliest_observation);

        document.getElementById("dc-latest").textContent =
            formatTimestamp(dc.latest_observation);

        // Actual pipeline report counts.
        const fmt = value =>
            value != null ? Number(value).toLocaleString("en-IN") : "—";

        document.getElementById("dc-normalized").textContent =
            fmt(pipeline.normalized_rows);

        document.getElementById("dc-before-dedup").textContent =
            fmt(pipeline.original_rows);

        document.getElementById("dc-duplicates-removed").textContent =
            fmt(pipeline.duplicate_rows);

        document.getElementById("dc-after-dedup").textContent =
            fmt(pipeline.deduplicated_rows);

        document.getElementById("dc-pipeline-status").textContent =
            pipeline.available
                ? `Pipeline report available · Final clean rows: ${fmt(pipeline.final_clean_rows)} · Duplicate groups: ${fmt(pipeline.duplicate_groups)}`
                : "Pipeline report unavailable. Pipeline metrics are not estimated.";

        // Anomaly analysis results.
        const anom = data.anomalies || {};

        document.getElementById("anom-count").textContent =
            (anom.count || 0).toLocaleString("en-IN");

        document.getElementById("anom-rate").textContent =
            `${(anom.rate || 0).toFixed(2)}%`;

        document.getElementById("anom-reviewed").textContent =
            (anom.reviewed || 0).toLocaleString("en-IN");

        const caption = document.getElementById("anom-analysis-caption");

        if (caption) {
            caption.textContent = anomalyDate
                ? `Selected date: ${anom.selected_date || anomalyDate} · ${fmt(anom.available_for_date)} matching records · ${fmt(anom.reviewed)} reviewed (maximum 20,000).`
                : `Latest sample · ${fmt(anom.reviewed)} reviewed (maximum 1,000).`;
        }

        const alertContainer = document.getElementById("anom-alert-container");

        if (anom.count === 0) {
            alertContainer.innerHTML =
                '<div class="st-alert st-alert-success"><span>✓</span><span>No potential fare anomalies detected in the reviewed sample.</span></div>';
        } else {
            alertContainer.innerHTML =
                '<div class="st-alert st-alert-warning"><span>⚠️</span><span>Flagged observations are review candidates. Extreme prices are not automatically deleted because they may represent genuine market behaviour.</span></div>';
        }

        renderTable("anom-table", anom.flagged);

    } catch (err) {
        console.error("Data Quality load failed:", err);

        const alertContainer = document.getElementById("anom-alert-container");
        if (alertContainer) {
            alertContainer.innerHTML =
                '<div class="st-alert st-alert-warning"><span>⚠️</span><span>Data Quality could not be loaded. Check the API response and try again.</span></div>';
        }
    } finally {
        showLoading(false);
    }
}

async function loadSourceHealthTab() {
    showLoading(true);
    try {
        const requestFilters = JSON.stringify(getFilterParams());
        const data = await apiGet("/api/dashboard/source-health", getFilterParams());
        if (requestFilters !== JSON.stringify(getFilterParams())) return;
        if (data.empty) {
            document.getElementById("sh-share-chart").innerHTML = '<div class="st-alert st-alert-info"><span>ℹ️</span><span>No source observations available for the selected filters.</span></div>';
            return;
        }

        const k = data.kpis || {};
        document.getElementById("sh-total-obs").textContent = (k.total_observations || 0).toLocaleString("en-IN");
        document.getElementById("sh-obs-sources").textContent = `${k.observed_sources || 0}/${k.configured_sources || 0}`;
        document.getElementById("sh-coverage").textContent = k.source_coverage_pct != null ? `${k.source_coverage_pct.toFixed(1)}%` : "—";
        document.getElementById("sh-largest-share").textContent = k.largest_source_share != null ? `${k.largest_source_share.toFixed(1)}%` : "—";

        renderPlotly("sh-share-chart", data.chart);
        renderTable("sh-share-table", data.coverage_table);

        const share = k.largest_source_share || 0;
        let concAlert = "";
        if (share > 80) {
            concAlert = '<div class="st-alert st-alert-warning"><span>⚠️</span><span>Very high source concentration. Independent observation channels should be added.</span></div>';
        } else if (share > 50) {
            concAlert = '<div class="st-alert st-alert-warning"><span>⚠️</span><span>Source concentration is high. Diversification would improve resilience.</span></div>';
        } else {
            concAlert = '<div class="st-alert st-alert-success"><span>✓</span><span>No single source contributes more than half of the observed records.</span></div>';
        }
        document.getElementById("sh-concentration-alert").innerHTML = concAlert;
        document.getElementById("sh-obs-window").textContent = `${k.earliest_date} → ${k.latest_date}`;

        renderTable("sh-coverage-table", data.coverage_table);
    } finally {
        showLoading(false);
    }
}

async function loadRawExplorerTab() {
    showLoading(true);
    try {
        const params = {
            ...getFilterParams(),
            page: state.rawPage,
            page_size: state.rawPageSize,
        };
        const requestKey = JSON.stringify(params);
        const data = await apiGet("/api/observations", params);
        const currentKey = JSON.stringify({
            ...getFilterParams(),
            page: state.rawPage,
            page_size: state.rawPageSize
        });
        if (requestKey !== currentKey) return;

        state.rawTotalPages = Math.max(1, data.total_pages || 1);

        document.getElementById("raw-matching-obs").textContent = (data.total || 0).toLocaleString("en-IN");
        document.getElementById("raw-page-indicator").textContent = `${data.page || 1} / ${state.rawTotalPages}`;
        document.getElementById("raw-rows-loaded").textContent = (data.items || []).length.toLocaleString("en-IN");

        const displayCols = [
            "collection_timestamp",
            "origin",
            "destination",
            "airline",
            "source",
            "advance_days",
            "base_fare",
            "taxes",
            "fees",
            "total_fare",
            "departure_time",
            "flight_number",
        ];

        renderTable("raw-data-table", data.items, displayCols);

        document.getElementById("raw-page-status").textContent = `Page ${data.page} of ${state.rawTotalPages}`;
        document.getElementById("raw-prev-btn").disabled = data.page <= 1;
        document.getElementById("raw-next-btn").disabled = data.page >= state.rawTotalPages;
    } finally {
        showLoading(false);
    }
}

async function loadAutomationTab() {
    showLoading(true);
    try {
        const data = await apiGet("/api/dashboard/automation");

        // Audit gate cards
        const gatesContainer = document.getElementById("auto-gates-container");
        gatesContainer.innerHTML = (data.gates || []).map(g => {
            const cls = g.status === "PASS" ? "st-alert-success" : g.status === "FAIL" ? "st-alert-error" : "st-alert-info";
            const icon = g.status === "PASS" ? "✓" : g.status === "FAIL" ? "✕" : "•";
            return `<div class="st-alert ${cls}"><span>${icon}</span><span><b>${g.label}</b>: ${g.status}</span></div>`;
        }).join("");

        // Failed / warning banners
        const failedEl = document.getElementById("auto-failed-banner");
        if (data.failed_checks) {
            failedEl.innerHTML = `<div class="st-alert st-alert-error"><span>✕</span><span>Failed Checks: ${data.failed_checks}</span></div>`;
        } else {
            failedEl.innerHTML = "";
        }

        const warnEl = document.getElementById("auto-warnings-banner");
        if (data.warnings) {
            warnEl.innerHTML = `<div class="st-alert st-alert-warning"><span>⚠️</span><span>Audit Warnings: ${data.warnings}</span></div>`;
        } else {
            warnEl.innerHTML = "";
        }

        // Publication Status Banner
        const pubBanner = document.getElementById("auto-pub-banner");
        if (data.publication_status === "PUBLISHABLE") {
            pubBanner.className = "st-alert st-alert-success";
            pubBanner.innerHTML = "<span>🟢</span><span><b>LATEST INDEX: PUBLISHABLE</b> — automated statistical gates passed.</span>";
        } else if (data.publication_status === "HOLD") {
            pubBanner.className = "st-alert st-alert-warning";
            pubBanner.innerHTML = "<span>🟡</span><span><b>LATEST INDEX: HOLD</b> — coverage or statistical gates require review.</span>";
        } else {
            pubBanner.className = "st-alert st-alert-info";
            pubBanner.innerHTML = "<span>⚪</span><span><b>LATEST INDEX: AUDIT STATUS UNAVAILABLE.</b></span>";
        }

        // Latest audit summary card — values come directly from the audit API.
        const audit = data.latest_audit || {};
        const auditContainer = document.getElementById("auto-audit-json");

        const escapeAuditHtml = (value) => String(value ?? "—").replace(
            /[&<>"']/g,
            char => ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;"
            })[char]
        );

        const auditNumber = (key) => {
            const value = Number(audit[key]);
            return audit[key] !== null && audit[key] !== undefined && Number.isFinite(value)
                ? value
                : null;
        };

        const formatAuditDate = (value) => {
            if (!value) return "Date unavailable";
            const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
            if (!match) return escapeAuditHtml(value);

            const date = new Date(
                Number(match[1]),
                Number(match[2]) - 1,
                Number(match[3])
            );

            return date.toLocaleDateString("en-IN", {
                day: "2-digit",
                month: "long",
                year: "numeric"
            });
        };

        const observations = auditNumber("observations");
        const nationalIndex = auditNumber("national_index");
        const movement = auditNumber("movement_from_base_pct");
        const routes = auditNumber("routes_present");
        const expectedRoutes = auditNumber("expected_routes");

        const status = String(
            data.publication_status || audit.publication_status || "UNAVAILABLE"
        ).toUpperCase();

        const statusClass = status === "PUBLISHABLE"
            ? "audit-status-publishable"
            : status === "HOLD"
                ? "audit-status-hold"
                : "audit-status-unavailable";

        const movementClass = movement === null
            ? ""
            : movement >= 0
                ? "audit-positive"
                : "audit-negative";

        const metric = (label, value, extraClass = "") => `
            <div class="audit-summary-metric">
                <span class="audit-summary-label">${label}</span>
                <strong class="audit-summary-value ${extraClass}">${value}</strong>
            </div>
        `;

        auditContainer.innerHTML = `
            <div class="audit-summary-card">
                <div class="audit-summary-header">
                    <div>
                        <div class="audit-summary-eyebrow">LATEST VERIFIED AUDIT</div>
                        <div class="audit-summary-date">
                            ${formatAuditDate(audit.collection_date)}
                        </div>
                    </div>
                    <span class="audit-status-pill ${statusClass}">
                        <span class="audit-status-dot"></span>
                        ${escapeAuditHtml(status)}
                    </span>
                </div>

                <div class="audit-summary-grid">
                    ${metric(
                        "Observations",
                        observations === null ? "—" : observations.toLocaleString("en-IN")
                    )}
                    ${metric(
                        "National Airfare Index",
                        nationalIndex === null ? "—" : nationalIndex.toFixed(2)
                    )}
                    ${metric(
                        "Movement from Base Period",
                        movement === null ? "—" : `${movement >= 0 ? "+" : ""}${movement.toFixed(2)}%`,
                        movementClass
                    )}
                    ${metric(
                        "Route Coverage",
                        routes === null || expectedRoutes === null
                            ? "—"
                            : `${routes.toLocaleString("en-IN")} / ${expectedRoutes.toLocaleString("en-IN")}`
                    )}
                </div>

                <details class="audit-full-details">
                    <summary>View Full Audit Details</summary>
                    <pre>${escapeAuditHtml(JSON.stringify(audit, null, 2))}</pre>
                </details>
            </div>
        `;

        // Coverage Gate Table
        renderTable("auto-coverage-table", data.coverage_table);

        // Pipeline Stages
        const stagesContainer = document.getElementById("auto-pipeline-stages");
        stagesContainer.innerHTML = (data.pipeline_stages || []).map(s => {
            const chipClass = s.status === "Implemented" ? "status-implemented" : s.status === "Current layer" ? "status-current" : "status-service";
            return `
                <div class="pipeline-stage-row">
                    <div><b>${s.number}</b></div>
                    <div>
                        <b>${s.stage}</b>
                        <div style="font-size: 0.8rem; color: #64748b; margin-top: 2px;">${s.description}</div>
                    </div>
                    <div>
                        <span class="pipeline-status-chip ${chipClass}">${s.status}</span>
                    </div>
                </div>
            `;
        }).join("");

        // Pipeline Provenance
        renderTable("auto-provenance-table", data.provenance_table, ["metric", "value"]);

        // Resilience Policy
        renderTable("auto-resilience-table", data.resilience_policy, ["failure", "class", "action"]);

    } finally {
        showLoading(false);
    }
}


// ---------------------------------------------------------
// India Route Map — official geography, curved routes, aircraft
// ---------------------------------------------------------

let indiaMapInstance = null;
let indiaMapRouteLayer = null;
let indiaMapAirportLookup = {};
let indiaMapRoutes = [];
let indiaMapRoutePaths = {};
let indiaMapAircraftMarker = null;
let indiaMapAnimationFrame = null;
let indiaMapDetailRequestId = 0;

function indiaMapSetText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value == null ? "—" : String(value);
}

function indiaMapFormatNumber(value, digits = 2) {
    const number = Number(value);
    return Number.isFinite(number)
        ? number.toLocaleString("en-IN", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits
        })
        : "—";
}

function indiaMapRouteLabel(route) {
    return `${route.origin} → ${route.destination}`;
}

function indiaMapDistanceKm(origin, destination) {
    if (!origin || !destination) return null;

    const rad = degrees => degrees * Math.PI / 180;
    const dLat = rad(destination.lat - origin.lat);
    const dLon = rad(destination.lon - origin.lon);
    const lat1 = rad(origin.lat);
    const lat2 = rad(destination.lat);

    const a = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;

    return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Quadratic Bezier route arcs. Reciprocal directions use opposite offsets.
function indiaMapBuildArc(origin, destination) {
    const meanLat = (origin.lat + destination.lat) / 2;
    const longitudeScale = Math.max(
        0.25,
        Math.cos(meanLat * Math.PI / 180)
    );

    const x1 = origin.lon * longitudeScale;
    const y1 = origin.lat;
    const x2 = destination.lon * longitudeScale;
    const y2 = destination.lat;

    const dx = x2 - x1;
    const dy = y2 - y1;
    const length = Math.hypot(dx, dy);

    if (!length) {
        return [[origin.lat, origin.lon], [destination.lat, destination.lon]];
    }

    const offset = Math.min(1.65, Math.max(0.38, length * 0.105));

    const controlX = (x1 + x2) / 2 + (-dy / length) * offset;
    const controlY = (y1 + y2) / 2 + (dx / length) * offset;

    const points = [];
    const samples = 64;

    for (let index = 0; index <= samples; index++) {
        const t = index / samples;
        const oneMinus = 1 - t;

        const x = oneMinus * oneMinus * x1
            + 2 * oneMinus * t * controlX
            + t * t * x2;

        const y = oneMinus * oneMinus * y1
            + 2 * oneMinus * t * controlY
            + t * t * y2;

        points.push([y, x / longitudeScale]);
    }

    return points;
}

function indiaMapStopAircraft() {
    if (indiaMapAnimationFrame !== null) {
        cancelAnimationFrame(indiaMapAnimationFrame);
        indiaMapAnimationFrame = null;
    }

    if (indiaMapAircraftMarker && indiaMapInstance) {
        indiaMapInstance.removeLayer(indiaMapAircraftMarker);
    }

    indiaMapAircraftMarker = null;
}

function indiaMapStartAircraft(route, points) {
    indiaMapStopAircraft();

    if (!route || !points || points.length < 3 || !indiaMapInstance) return;

    const planeIcon = L.divIcon({
        className: "afx-plane-marker-wrap",
        html: '<div class="afx-plane-glyph" aria-label="Animated aircraft">✈</div>',
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });

    indiaMapAircraftMarker = L.marker(points[0], {
        pane: "indiaAircraftPane",
        icon: planeIcon,
        keyboard: false,
        interactive: false,
        zIndexOffset: 1000
    }).addTo(indiaMapInstance);

    let startTime = null;
    const duration = 9500;

    const animate = timestamp => {
        const mapTab = document.getElementById("tab-india-route-map");

        if (!mapTab || !mapTab.classList.contains("active")) {
            indiaMapAnimationFrame = null;
            return;
        }

        if (document.hidden) {
            indiaMapAnimationFrame = requestAnimationFrame(animate);
            return;
        }

        if (startTime === null) startTime = timestamp;

        const progress = ((timestamp - startTime) % duration) / duration;
        const position = progress * (points.length - 1);
        const index = Math.floor(position);
        const fraction = position - index;

        const current = points[index];
        const next = points[Math.min(index + 1, points.length - 1)];
        const previous = points[Math.max(0, index - 1)];

        const lat = current[0] + (next[0] - current[0]) * fraction;
        const lon = current[1] + (next[1] - current[1]) * fraction;

        indiaMapAircraftMarker.setLatLng([lat, lon]);

        const tangentLon = (next[1] - previous[1])
            * Math.cos(lat * Math.PI / 180);
        const tangentScreenLat = -(next[0] - previous[0]);
        const angle = Math.atan2(
            tangentScreenLat,
            tangentLon
        ) * 180 / Math.PI;

        const glyph = indiaMapAircraftMarker.getElement()
            ?.querySelector(".afx-plane-glyph");

        if (glyph) glyph.style.transform = `rotate(${angle}deg)`;

        indiaMapAnimationFrame = requestAnimationFrame(animate);
    };

    indiaMapAnimationFrame = requestAnimationFrame(animate);
}

function indiaMapAirportPopup(airport) {
    const wrapper = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = `${airport.code} — ${airport.city}`;
    wrapper.appendChild(heading);

    const name = document.createElement("div");
    name.textContent = airport.name;
    wrapper.appendChild(name);

    const coordinates = document.createElement("small");
    coordinates.textContent =
        `${airport.lat.toFixed(4)}° N, ${airport.lon.toFixed(4)}° E`;
    wrapper.appendChild(coordinates);

    return wrapper;
}

function indiaMapAddAirportMarkers(airports) {
    airports.forEach(airport => {
        const marker = L.circleMarker(
            [airport.lat, airport.lon],
            {
                pane: "indiaAirportsPane",
                radius: 6.5,
                color: "#F0D6AC",
                weight: 2,
                fillColor: "#F2E7D5",
                fillOpacity: 1
            }
        );

        marker.bindTooltip(
            `${airport.code} · ${airport.city}`,
            {
                permanent: true,
                direction: "right",
                offset: [7, 0],
                className: "afx-map-airport-label"
            }
        );

        marker.bindPopup(indiaMapAirportPopup(airport));
        marker.addTo(indiaMapInstance);
    });
}

function indiaMapSetAirportDetail(prefix, airport) {
    indiaMapSetText(
        `afx-detail-${prefix}-code`,
        airport ? airport.code : "—"
    );
    indiaMapSetText(
        `afx-detail-${prefix}-name`,
        airport ? `${airport.name} · ${airport.city}` : "—"
    );
    indiaMapSetText(
        `afx-detail-${prefix}-coords`,
        airport
            ? `${airport.lat.toFixed(4)}° N, ${airport.lon.toFixed(4)}° E`
            : "—"
    );
}

function indiaMapClearRouteDetail(message) {
    indiaMapDetailRequestId++;

    indiaMapSetText("afx-detail-route-title", "Select a monitored route");
    indiaMapSetText("afx-detail-route-subtitle", message);
    indiaMapSetText("afx-detail-collection-date", "—");

    indiaMapSetAirportDetail("origin", null);
    indiaMapSetAirportDetail("destination", null);

    [
        "index", "previous-index", "movement", "rank",
        "observations", "strata", "link-index", "distance",
        "previous-date", "fare-observations"
    ].forEach(key => indiaMapSetText(`afx-detail-${key}`, "—"));

    renderPlotly("afx-map-history-chart", null);
    renderTable("afx-map-history-table", []);
    renderTable("afx-map-fare-table", []);
}

async function indiaMapLoadRouteDetail(route) {
    const requestId = ++indiaMapDetailRequestId;
    const label = indiaMapRouteLabel(route);

    indiaMapSetText("afx-detail-route-title", label);
    indiaMapSetText("afx-detail-route-subtitle", "Loading route statistics and observed fares…");
    indiaMapSetText("afx-detail-collection-date", "Loading…");

    try {
        const params = {
            ...getFilterParams(),
            route: route.route
        };

        const data = await apiGet(
            "/api/dashboard/india-route-map/route-detail",
            params
        );

        const select = document.getElementById("afx-map-route-select");

        if (
            requestId !== indiaMapDetailRequestId
            || !select
            || select.value !== route.route
        ) return;

        if (data.empty) {
            indiaMapSetText(
                "afx-detail-route-subtitle",
                "No route detail records match the current filters."
            );
            return;
        }

        const origin = indiaMapAirportLookup[data.origin];
        const destination = indiaMapAirportLookup[data.destination];

        indiaMapSetText("afx-detail-route-title", label);
        indiaMapSetText(
            "afx-detail-route-subtitle",
            `${origin?.city || data.origin} → ${destination?.city || data.destination}`
        );
        indiaMapSetText("afx-detail-collection-date", data.collection_date);
        indiaMapSetText(
            "afx-detail-previous-date",
            data.previous_collection_date || "—"
        );

        indiaMapSetAirportDetail("origin", origin);
        indiaMapSetAirportDetail("destination", destination);

        indiaMapSetText("afx-detail-index", indiaMapFormatNumber(data.route_index));
        indiaMapSetText(
            "afx-detail-previous-index",
            indiaMapFormatNumber(data.previous_route_index)
        );
        indiaMapSetText(
            "afx-detail-movement",
            data.change_pct == null
                ? "—"
                : `${Number(data.change_pct) > 0 ? "+" : ""}${indiaMapFormatNumber(data.change_pct)}%`
        );
        indiaMapSetText(
            "afx-detail-rank",
            data.route_rank
                ? `${data.route_rank} of ${data.routes_ranked}`
                : "—"
        );
        indiaMapSetText(
            "afx-detail-observations",
            data.observations == null
                ? "—"
                : Number(data.observations).toLocaleString("en-IN")
        );
        indiaMapSetText("afx-detail-strata", data.lead_time_strata ?? "—");
        indiaMapSetText(
            "afx-detail-link-index",
            indiaMapFormatNumber(data.route_link_index)
        );
        indiaMapSetText(
            "afx-detail-fare-observations",
            data.fare_observation_total == null
                ? "—"
                : Number(data.fare_observation_total).toLocaleString("en-IN")
        );

        const distance = indiaMapDistanceKm(origin, destination);
        indiaMapSetText(
            "afx-detail-distance",
            distance == null
                ? "—"
                : `${Math.round(distance).toLocaleString("en-IN")} km`
        );

        indiaMapSetText(
            "afx-detail-route-subtitle",
            `${origin?.name || data.origin} → ${destination?.name || data.destination}`
        );

        renderPlotly("afx-map-history-chart", data.history_chart);
        renderTable(
            "afx-map-history-table",
            data.history_table,
            ["collection_date", "previous_collection_date", "route_index", "route_link_index", "observations", "lead_time_strata"]
        );
        renderTable(
            "afx-map-fare-table",
            data.fare_table,
            ["advance_days", "median_fare", "observations"]
        );

    } catch (error) {
        if (requestId !== indiaMapDetailRequestId) return;
        console.error("Selected route detail failed:", error);
        indiaMapSetText(
            "afx-detail-route-subtitle",
            `Route detail unavailable: ${error.message}`
        );
    }
}

function indiaMapRenderRoutes() {
    if (!indiaMapInstance || !indiaMapRouteLayer) return;

    indiaMapStopAircraft();
    indiaMapRouteLayer.clearLayers();
    indiaMapRoutePaths = {};

    const select = document.getElementById("afx-map-route-select");
    const selected = select ? select.value : "All Routes";

    const drawRoute = (route, isSelected) => {
        const origin = indiaMapAirportLookup[route.origin];
        const destination = indiaMapAirportLookup[route.destination];

        if (!origin || !destination) return;

        const points = indiaMapBuildArc(origin, destination);
        indiaMapRoutePaths[route.route] = points;

        if (isSelected) {
            L.polyline(points, {
                pane: "indiaRoutesPane",
                color: "#F0D6AC",
                weight: 13,
                opacity: 0.22,
                lineCap: "round",
                lineJoin: "round",
                interactive: false
            }).addTo(indiaMapRouteLayer);
        }

        const hitTarget = L.polyline(points, {
            pane: "indiaRoutesPane",
            color: "#FFFFFF",
            weight: 20,
            opacity: 0.01,
            lineCap: "round",
            interactive: true
        });

        hitTarget.on("click", () => {
            if (select) {
                select.value = route.route;
                indiaMapRenderRoutes();
            }
        });

        hitTarget.addTo(indiaMapRouteLayer);

        const line = L.polyline(points, {
            pane: "indiaRoutesPane",
            color: isSelected ? "#F0D6AC" : "#75AFCB",
            weight: isSelected ? 5.6 : 2.2,
            opacity: isSelected ? 1 : 0.78,
            dashArray: isSelected ? null : "6 7",
            lineCap: "round",
            lineJoin: "round"
        });

        line.bindTooltip(indiaMapRouteLabel(route), {
            sticky: true,
            className: "afx-map-route-tooltip"
        });

        const popup = document.createElement("div");
        const heading = document.createElement("strong");
        heading.textContent = indiaMapRouteLabel(route);
        popup.appendChild(heading);

        const details = document.createElement("div");
        details.textContent =
            `Route index: ${indiaMapFormatNumber(route.route_index)} · `
            + `Observations: ${Number(route.observations || 0).toLocaleString("en-IN")}`;
        popup.appendChild(details);

        line.bindPopup(popup);

        line.on("click", () => {
            if (select) {
                select.value = route.route;
                indiaMapRenderRoutes();
            }
        });

        line.addTo(indiaMapRouteLayer);
    };

    if (selected === "All Routes") {
        indiaMapRoutes.forEach(route => drawRoute(route, false));
        indiaMapClearRouteDetail(
            "Select a route from the map or dropdown to inspect its historical index and observed fare structure."
        );
        indiaMapSetText("afx-map-selected-route", "All routes");
        indiaMapSetText("afx-map-selected-index", "—");
        indiaMapSetText(
            "afx-map-detail",
            "Showing all monitored directional connections. Select a route to highlight its curved path and animate the aircraft."
        );
        return;
    }

    indiaMapRoutes
        .filter(route => route.route !== selected)
        .forEach(route => drawRoute(route, false));

    const selectedRoute = indiaMapRoutes.find(
        route => route.route === selected
    );

    if (!selectedRoute) {
        indiaMapClearRouteDetail("The selected route is not available in the current filtered dataset.");
        return;
    }

    drawRoute(selectedRoute, true);

    indiaMapSetText(
        "afx-map-selected-route",
        indiaMapRouteLabel(selectedRoute)
    );
    indiaMapSetText(
        "afx-map-selected-index",
        indiaMapFormatNumber(selectedRoute.route_index)
    );

    const changeText = selectedRoute.change_pct == null
        ? "Previous observation unavailable"
        : `Movement: ${Number(selectedRoute.change_pct) > 0 ? "+" : ""}${indiaMapFormatNumber(selectedRoute.change_pct)}%`;

    indiaMapSetText(
        "afx-map-detail",
        `${indiaMapRouteLabel(selectedRoute)} · Index: ${indiaMapFormatNumber(selectedRoute.route_index)} · `
        + `Observations: ${Number(selectedRoute.observations || 0).toLocaleString("en-IN")} · `
        + `Collection date: ${selectedRoute.collection_date} · ${changeText}`
    );

    indiaMapStartAircraft(
        selectedRoute,
        indiaMapRoutePaths[selectedRoute.route]
    );

    indiaMapLoadRouteDetail(selectedRoute);
}

async function loadIndiaRouteMapTab() {
    showLoading(true);

    try {
        if (!window.L) {
            throw new Error("Leaflet could not be loaded. Check the Leaflet CDN connection.");
        }

        const requestSignature = JSON.stringify(getFilterParams());

        const [
            routeData,
            outlineResponse,
            stateResponse,
            riverResponse,
            locResponse,
            airportResponse
        ] = await Promise.all([
            apiGet("/api/dashboard/india-route-map", getFilterParams()),
            fetch("/data/india-soi-outline.geojson"),
            fetch("/data/india-states.geojson"),
            fetch("/data/india-rivers.geojson"),
            fetch("/data/india-loc-approx.geojson"),
            fetch("/data/india-airports.json")
        ]);

        const responses = [
            outlineResponse,
            stateResponse,
            riverResponse,
            locResponse,
            airportResponse
        ];

        for (const response of responses) {
            if (!response.ok) {
                throw new Error(`Geographic asset failed: HTTP ${response.status}`);
            }
        }

        const [
            outline,
            states,
            rivers,
            loc,
            airports
        ] = await Promise.all([
            outlineResponse.json(),
            stateResponse.json(),
            riverResponse.json(),
            locResponse.json(),
            airportResponse.json()
        ]);

        if (requestSignature !== JSON.stringify(getFilterParams())) return;

        if (routeData.empty || !routeData.routes?.length) {
            indiaMapSetText("afx-map-route-count", "0");
            indiaMapSetText(
                "afx-map-detail",
                "No monitored routes match the current dashboard filters."
            );
            indiaMapClearRouteDetail("No route records match the current filters.");
            return;
        }

        indiaMapRoutes = routeData.routes;
        indiaMapAirportLookup = Object.fromEntries(
            airports.map(airport => [airport.code, airport])
        );

        const select = document.getElementById("afx-map-route-select");
        if (!select) return;

        const previousSelection = select.value || "All Routes";
        select.replaceChildren();

        const allOption = document.createElement("option");
        allOption.value = "All Routes";
        allOption.textContent = "All monitored routes";
        select.appendChild(allOption);

        indiaMapRoutes.forEach(route => {
            const option = document.createElement("option");
            option.value = route.route;
            option.textContent = indiaMapRouteLabel(route);
            select.appendChild(option);
        });

        select.value = indiaMapRoutes.some(
            route => route.route === previousSelection
        ) ? previousSelection : "All Routes";

        if (!select.dataset.mapBound) {
            select.addEventListener("change", indiaMapRenderRoutes);
            select.dataset.mapBound = "true";
        }

        indiaMapSetText("afx-map-route-count", indiaMapRoutes.length);
        indiaMapSetText("afx-map-airport-count", airports.length);

        const mapElement = document.getElementById("afx-india-route-map");
        if (!mapElement) return;

        if (!indiaMapInstance) {
            indiaMapInstance = L.map(mapElement, {
                zoomControl: true,
                scrollWheelZoom: false,
                preferCanvas: true,
                minZoom: 3,
                maxZoom: 8,
                maxBounds: [[4.5, 65], [39.5, 100]],
                maxBoundsViscosity: 0.88,
                attributionControl: true
            });

            indiaMapInstance.createPane("indiaOutlinePane");
            indiaMapInstance.getPane("indiaOutlinePane").style.zIndex = 380;

            indiaMapInstance.createPane("indiaStatesPane");
            indiaMapInstance.getPane("indiaStatesPane").style.zIndex = 390;

            indiaMapInstance.createPane("indiaRiversPane");
            indiaMapInstance.getPane("indiaRiversPane").style.zIndex = 400;

            indiaMapInstance.createPane("indiaLocPane");
            indiaMapInstance.getPane("indiaLocPane").style.zIndex = 410;

            indiaMapInstance.createPane("indiaRoutesPane");
            indiaMapInstance.getPane("indiaRoutesPane").style.zIndex = 420;

            indiaMapInstance.createPane("indiaAirportsPane");
            indiaMapInstance.getPane("indiaAirportsPane").style.zIndex = 430;

            indiaMapInstance.createPane("indiaAircraftPane");
            indiaMapInstance.getPane("indiaAircraftPane").style.zIndex = 650;

            const outlineLayer = L.geoJSON(outline, {
                pane: "indiaOutlinePane",
                style: {
                    color: "#E4D6C3",
                    weight: 2.1,
                    opacity: 1,
                    fillColor: "#263440",
                    fillOpacity: 0.98,
                    lineJoin: "round"
                }
            }).addTo(indiaMapInstance);

            L.geoJSON(states, {
                pane: "indiaStatesPane",
                style: {
                    color: "#C9BBA8",
                    weight: 0.8,
                    opacity: 0.82,
                    fillOpacity: 0,
                    lineJoin: "round"
                },
                onEachFeature: (feature, layer) => {
                    const name = feature.properties.name_en
                        || feature.properties.name
                        || "Indian administrative area";

                    layer.bindTooltip(name, {
                        sticky: true,
                        className: "afx-map-state-tooltip"
                    });
                }
            }).addTo(indiaMapInstance);

            L.geoJSON(rivers, {
                pane: "indiaRiversPane",
                style: {
                    color: "#8295A0",
                    weight: 1.1,
                    opacity: 0.9
                },
                onEachFeature: (feature, layer) => {
                    const name = feature.properties.name_en
                        || feature.properties.name;

                    if (name) {
                        layer.bindTooltip(name, {
                            sticky: true,
                            className: "afx-map-river-tooltip"
                        });
                    }
                }
            }).addTo(indiaMapInstance);

            L.geoJSON(loc, {
                pane: "indiaLocPane",
                style: {
                    color: "#D69B70",
                    weight: 2.3,
                    opacity: 0.96,
                    dashArray: "2 7",
                    lineCap: "round"
                },
                onEachFeature: (feature, layer) => {
                    layer.bindTooltip(
                        "Approximate Line of Control · UN Geospatial classification",
                        {
                            sticky: true,
                            className: "afx-map-loc-tooltip"
                        }
                    );
                    layer.bindPopup(
                        "Approximate Line of Control. This is a separately classified approximate line, not an international boundary."
                    );
                }
            }).addTo(indiaMapInstance);

            indiaMapRouteLayer = L.layerGroup().addTo(indiaMapInstance);
            indiaMapAddAirportMarkers(airports);

            const bounds = outlineLayer.getBounds();
            if (bounds.isValid()) {
                indiaMapInstance.fitBounds(bounds, {
                    padding: [6, 6],
                    maxZoom: 5.0
                });

                indiaMapInstance.setZoom(
                    Math.min(6, indiaMapInstance.getZoom() + 1),
                    { animate: false }
                );
            } else {
                indiaMapInstance.setView([22.5, 82], 4);
            }
        }

        indiaMapRenderRoutes();

        requestAnimationFrame(() => {
            if (indiaMapInstance) {
                indiaMapInstance.invalidateSize();
            }
        });

    } catch (error) {
        console.error("India Route Map failed:", error);
        indiaMapSetText(
            "afx-map-detail",
            `Map unavailable: ${error.message}`
        );
        indiaMapSetText(
            "afx-detail-route-subtitle",
            `Map unavailable: ${error.message}`
        );
    } finally {
        showLoading(false);
    }
}

function loadTabData(tabId) {
    const loaders = {
        "overview": loadOverviewTab,
        "index-analytics": loadIndexAnalyticsTab,
        "route-intelligence": loadRouteIntelligenceTab,
        "india-route-map": loadIndiaRouteMapTab,
        "lead-time": loadLeadTimeTab,
        "data-quality": loadDataQualityTab,
        "source-health": loadSourceHealthTab,
        "raw-explorer": loadRawExplorerTab,
        "automation": loadAutomationTab
    };

    const loader = loaders[tabId];
    if (!loader) return Promise.resolve();

    const filterSignature = JSON.stringify(getFilterParams());
    const renderKey = `${tabId}|${filterSignature}`;
    const previous = state.renderedTabKeys[tabId];

    if (
        previous &&
        previous.key === renderKey &&
        Date.now() - previous.loadedAt < API_CACHE_TTL_MS
    ) {
        return Promise.resolve();
    }

    if (state.loadingTabKeys[renderKey]) {
        return state.loadingTabKeys[renderKey];
    }

    const pending = Promise.resolve()
        .then(() => loader())
        .then(() => {
            if (filterSignature === JSON.stringify(getFilterParams())) {
                state.renderedTabKeys[tabId] = {
                    key: renderKey,
                    loadedAt: Date.now()
                };
            }
        })
        .finally(() => {
            delete state.loadingTabKeys[renderKey];
        });

    state.loadingTabKeys[renderKey] = pending;
    return pending;
}

// ---------------------------------------------------------
// Tab Switching Router
// ---------------------------------------------------------

function switchTab(tabId) {
    state.currentTab = tabId;

    // Update navigation state.
    document.querySelectorAll(".nav-item").forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
    });

    // Preserve tab DOM and visibility; only load when filters/data require it.
    document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.toggle("active", content.id === `tab-${tabId}`);
    });

    loadTabData(tabId).catch(err => {
        console.error(`Failed to load ${tabId}:`, err);
    });
}

// ---------------------------------------------------------
// Application Bootstrapper
// ---------------------------------------------------------

async function bootstrap() {
    showLoading(true);
    try {
        const meta = await apiGet("/api/dashboard/bootstrap");

        // Header KPIs
        document.getElementById("hdr-headline-index").textContent = meta.headline_index != null ? meta.headline_index.toFixed(2) : "—";
        document.getElementById("hdr-latest-date").textContent = meta.latest_date || "—";
        document.getElementById("hdr-routes").textContent = (meta.routes_count || 0).toLocaleString("en-IN");
        document.getElementById("hdr-lead-windows").textContent = (meta.lead_windows_count || 0).toLocaleString("en-IN");

        // Setup date bounds
        const startInput = document.getElementById("filter-start-date");
        const endInput = document.getElementById("filter-end-date");
        if (startInput && meta.min_date) {
            startInput.min = meta.min_date;
            startInput.value = meta.min_date;
            state.filters.startDate = meta.min_date;
            state.filterBounds.minDate = meta.min_date;
        }
        if (endInput && meta.max_date) {
            endInput.max = meta.max_date;
            endInput.value = meta.max_date;
            state.filters.endDate = meta.max_date;
            state.filterBounds.maxDate = meta.max_date;
        }

        // Multi-selects
        setupMultiSelect("routes-multiselect", meta.routes || [], (selected) => {
            state.filters.routes = selected;
            switchTab(state.currentTab);
        });

        setupMultiSelect("airlines-multiselect", meta.airlines || [], (selected) => {
            state.filters.airlines = selected;
            switchTab(state.currentTab);
        });

        setupMultiSelect("sources-multiselect", meta.sources || [], (selected) => {
            state.filters.sources = selected;
            switchTab(state.currentTab);
        });

        // Date input events
        if (startInput) {
            startInput.addEventListener("change", (e) => {
                state.filters.startDate = e.target.value;
                switchTab(state.currentTab);
            });
        }
        if (endInput) {
            endInput.addEventListener("change", (e) => {
                state.filters.endDate = e.target.value;
                switchTab(state.currentTab);
            });
        }

        // Date-specific anomaly analysis runs only after an explicit button click.
        const anomalyDateInput = document.getElementById("anom-date");
        const anomalyDateButton = document.getElementById("anom-date-analyse");

        if (anomalyDateInput) {
            if (meta.min_date) anomalyDateInput.min = meta.min_date;

            if (meta.max_date) {
                anomalyDateInput.max = meta.max_date;
                anomalyDateInput.value = meta.max_date;
            }
        }

        if (anomalyDateButton && anomalyDateInput) {
            anomalyDateButton.addEventListener("click", () => {
                if (!anomalyDateInput.value) {
                    anomalyDateInput.reportValidity();
                    return;
                }

                loadDataQualityTab(anomalyDateInput.value);
            });
        }

        // Navigation click listeners
        document.querySelectorAll(".nav-item").forEach(btn => {
            btn.addEventListener("click", () => {
                switchTab(btn.getAttribute("data-tab"));
            });
        });

        // Route Explorer select listener
        document.getElementById("route-explorer-select").addEventListener("change", () => {
            loadRouteExplorerRecords();
        });

        // Lead-Time Explorer select listeners
        document.getElementById("lead-filter-advance").addEventListener("change", () => {
            loadLeadTimeExplorerRecords();
        });
        document.getElementById("lead-filter-route").addEventListener("change", () => {
            loadLeadTimeExplorerRecords();
        });

        // Raw Explorer pagination listeners
        document.getElementById("raw-page-size").addEventListener("change", (e) => {
            state.rawPageSize = parseInt(e.target.value, 10);
            state.rawPage = 1;
            loadRawExplorerTab();
        });
        document.getElementById("raw-page-number").addEventListener("change", (e) => {
            state.rawPage = Math.max(1, parseInt(e.target.value, 10));
            loadRawExplorerTab();
        });
        document.getElementById("raw-prev-btn").addEventListener("click", () => {
            if (state.rawPage > 1) {
                state.rawPage--;
                document.getElementById("raw-page-number").value = state.rawPage;
                loadRawExplorerTab();
            }
        });
        document.getElementById("raw-next-btn").addEventListener("click", () => {
            if (state.rawPage < state.rawTotalPages) {
                state.rawPage++;
                document.getElementById("raw-page-number").value = state.rawPage;
                loadRawExplorerTab();
            }
        });

        // Refresh button: clear browser cache and request backend refresh.
        const refreshButton = document.getElementById("btn-refresh");
        if (refreshButton) {
            refreshButton.addEventListener("click", async () => {
                refreshButton.disabled = true;
                showLoading(true);

                try {
                    const response = await fetch("/api/dashboard/refresh", {
                        method: "POST",
                        cache: "no-store"
                    });

                    if (!response.ok) {
                        throw new Error(`Refresh failed: ${response.status}`);
                    }

                    state.tabDataCache = {};
                    state.renderedTabKeys = {};
                    state.loadingTabKeys = {};

                    // A clean page load resets all in-memory browser state.
                    window.location.reload();
                } catch (err) {
                    console.error("Dashboard refresh failed:", err);
                    refreshButton.disabled = false;
                    showLoading(false);
                    alert("Dashboard refresh failed. Check the browser console.");
                }
            });
        }

        // Initial tab load
        await loadTabData(state.currentTab);

    } catch (err) {
        console.error("Dashboard initialization failed:", err);
    } finally {
        showLoading(false);
    }
}

// Start application
window.addEventListener("DOMContentLoaded", bootstrap);

(() => {
    const intro = document.getElementById("airfarex-intro");
    const aircraft = intro?.querySelector(".airfarex-intro-aircraft");
    if (!intro || !aircraft) return;

    let finished = false;
    const finishIntro = () => {
        if (finished) return;
        finished = true;
        intro.classList.add("is-leaving");
        window.setTimeout(() => intro.remove(), 750);
    };

    // Reveal the real dashboard after the aircraft completes its bottom-left
    // to top-right flight. The timeout is a fallback for animation interruptions.
    aircraft.addEventListener("animationend", finishIntro, { once: true });
    window.setTimeout(finishIntro, 4400);
})();
