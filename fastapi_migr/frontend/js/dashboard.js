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
            return `${parts[0].toUpperCase()}–${parts[1].toUpperCase()}`;
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

// API request wrapper
async function apiGet(endpoint, params = {}) {
    const url = new URL(endpoint, window.location.origin);
    for (const [k, v] of Object.entries(params)) {
        if (Array.isArray(v)) {
            v.forEach(x => url.searchParams.append(k, x));
        } else if (v !== null && v !== undefined && v !== "") {
            url.searchParams.set(k, v);
        }
    }
    const res = await fetch(url.toString());
    if (!res.ok) {
        throw new Error(`API call failed: ${res.status} ${res.statusText}`);
    }
    return res.json();
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

    container.style.width = "100%";
    container.style.height = "420px";
    container.style.minHeight = "420px";

    const layout = {
        ...cleanSpec.layout,
        height: 420,
        autosize: true,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: {
            family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            size: 13,
            color: '#475569',
        },
        margin: {
            l: 60,
            r: 35,
            t: 65,
            b: 65,
        },
    };

    Plotly.newPlot(containerId, cleanSpec.data, layout, {
        responsive: true,
        displayModeBar: false,
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
        const data = await apiGet("/api/dashboard/overview", getFilterParams());

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
        document.getElementById("ov-airline-count").textContent = (kpis.airline_count || 0).toLocaleString("en-IN");
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
        const data = await apiGet("/api/dashboard/index-analytics", getFilterParams());
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
        const data = await apiGet("/api/dashboard/route-intelligence", getFilterParams());
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
    const res = await apiGet("/api/dashboard/route-explorer", params);
    renderTable("rt-explorer-table", res.items);
    document.getElementById("rt-explorer-caption").textContent = `Showing ${(res.total || 0).toLocaleString("en-IN")} route-index records. Use the route selector above to inspect a specific route.`;
}

async function loadLeadTimeTab() {
    showLoading(true);
    try {
        const data = await apiGet("/api/dashboard/lead-time", getFilterParams());
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
    const res = await apiGet("/api/dashboard/lead-time-explorer", params);
    renderTable("lead-explorer-table", res.items);
    document.getElementById("lead-explorer-caption").textContent = `Showing ${(res.total || 0).toLocaleString("en-IN")} lead-time fare records. Use the filters above to inspect a specific lead-time window or route.`;
}

async function loadDataQualityTab() {
    showLoading(true);
    try {
        const data = await apiGet("/api/dashboard/data-quality", getFilterParams());

        const k = data.kpis || {};
        document.getElementById("dq-total-obs").textContent = (k.total_observations || 0).toLocaleString("en-IN");
        document.getElementById("dq-missing-fare").textContent = `${(k.missing_fare_pct || 0).toFixed(2)}%`;
        document.getElementById("dq-dup-rate").textContent = `${(k.duplicate_pct || 0).toFixed(2)}%`;
        document.getElementById("dq-score").textContent = `${(k.quality_score || 0).toFixed(1)}/100`;
        document.getElementById("dq-status").textContent = k.status || "—";

        const anom = data.anomalies || {};
        document.getElementById("anom-count").textContent = (anom.count || 0).toLocaleString("en-IN");
        document.getElementById("anom-rate").textContent = `${(anom.rate || 0).toFixed(2)}%`;
        document.getElementById("anom-reviewed").textContent = (anom.reviewed || 0).toLocaleString("en-IN");

        const alertContainer = document.getElementById("anom-alert-container");
        if (anom.count === 0) {
            alertContainer.innerHTML = '<div class="st-alert st-alert-success"><span>✓</span><span>No potential fare anomalies detected.</span></div>';
        } else {
            alertContainer.innerHTML = '<div class="st-alert st-alert-warning"><span>⚠️</span><span>Flagged observations are review candidates. Extreme prices are not automatically deleted because they may represent genuine market behaviour.</span></div>';
        }

        renderTable("anom-table", anom.flagged);
    } finally {
        showLoading(false);
    }
}

async function loadSourceHealthTab() {
    showLoading(true);
    try {
        const data = await apiGet("/api/dashboard/source-health", getFilterParams());
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
        const data = await apiGet("/api/observations", params);

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

        // Latest audit JSON view
        document.getElementById("auto-audit-json").textContent = JSON.stringify(data.latest_audit || {}, null, 2);

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
// Tab Switching Router
// ---------------------------------------------------------

function switchTab(tabId) {
    state.currentTab = tabId;

    // Update nav pill classes
    document.querySelectorAll(".nav-item").forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
    });

    // Update section visibility
    document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.toggle("active", content.id === `tab-${tabId}`);
    });

    // Load data for the selected tab
    switch (tabId) {
        case "overview":
            loadOverviewTab();
            break;
        case "index-analytics":
            loadIndexAnalyticsTab();
            break;
        case "route-intelligence":
            loadRouteIntelligenceTab();
            break;
        case "lead-time":
            loadLeadTimeTab();
            break;
        case "data-quality":
            loadDataQualityTab();
            break;
        case "source-health":
            loadSourceHealthTab();
            break;
        case "raw-explorer":
            loadRawExplorerTab();
            break;
        case "automation":
            loadAutomationTab();
            break;
    }
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
        if (meta.min_date) {
            startInput.min = meta.min_date;
            startInput.value = meta.min_date;
            state.filters.startDate = meta.min_date;
            state.filterBounds.minDate = meta.min_date;
        }
        if (meta.max_date) {
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
        startInput.addEventListener("change", (e) => {
            state.filters.startDate = e.target.value;
            switchTab(state.currentTab);
        });
        endInput.addEventListener("change", (e) => {
            state.filters.endDate = e.target.value;
            switchTab(state.currentTab);
        });

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

        // Refresh button
        document.getElementById("btn-refresh").addEventListener("click", async () => {
            showLoading(true);
            try {
                await fetch("/api/dashboard/refresh", { method: "POST" });
                await bootstrap();
            } finally {
                showLoading(false);
            }
        });

        // Initial tab load
        await loadOverviewTab();

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
