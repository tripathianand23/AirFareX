from __future__ import annotations

# ============================================================
# AIRFARE PRICE INDEX — REAL-DATA STATISTICAL OPERATIONS APP
# SIH 2026 | Problem Statement 26056
#
# Architecture:
#   processed observations
#        ↓
#   precomputed statistical index
#        ↓
#   coverage + audit gates
#        ↓
#   operational dashboard
#
# IMPORTANT:
# - This UI does NOT recalculate the headline index.
# - It consumes the statistical engine's published artifacts.
# - Sidebar filters affect exploratory diagnostics only.
# - "PUBLISHABLE" is driven by the automated audit output.
# ============================================================

import sys
import json
from pathlib import Path

# Make project root importable when Streamlit executes this file directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (
    load_clean_data,
    load_raw_observations,
    load_daily_index,
    load_route_indices,
    load_advance_window_indices,
)

from dashboard.metrics import (
    latest_index,
    previous_index,
    index_change_percent,
    latest_collection_date,
    observation_count,
    route_count,
    airline_count,
    source_count,
)

from dashboard.charts import (
    create_overall_index_chart,
    create_route_index_chart,
    create_lead_time_chart,
)

from dashboard.monitoring import (
    calculate_data_quality,
    calculate_source_coverage,
    calculate_route_coverage,
    detect_fare_anomalies,
)


def display_chart_data_table(title, df, column_map=None, round_digits=2):
    """Render a compact, user-facing data table directly below a chart."""
    if df is None or df.empty:
        return
    table = df.copy()
    if column_map:
        table = table.rename(columns=column_map)
    numeric_cols = table.select_dtypes(include="number").columns
    if len(numeric_cols):
        table[numeric_cols] = table[numeric_cols].round(round_digits)
    st.markdown(f"#### {title}")
    st.dataframe(table, use_container_width=True, hide_index=True)



# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="AirfareX",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

REAL_INDEX_DIR = PROJECT_ROOT / "data" / "processed" / "real" / "index"
REAL_REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "real"

REAL_AUDIT_PATH = REAL_REPORT_DIR / "real_index_audit.csv"
REAL_COVERAGE_PATH = REAL_INDEX_DIR / "real_coverage_report.csv"
REAL_METADATA_PATH = REAL_INDEX_DIR / "real_index_metadata.json"
REAL_PIPELINE_REPORT_PATH = REAL_REPORT_DIR / "real_pipeline_report.json"

st.markdown(
    """
    <style>
    /* ========================================================
       AIRFAREX SIH PRESENTATION UI
       Visual layer only — data/statistical logic is unchanged.
       ======================================================== */
    .stApp {
        background:#f6f8fb;
        color:#172033;
    }

    [data-testid="stAppViewContainer"] {
        background:#f6f8fb;
    }

    [data-testid="stHeader"] {
        background:transparent;
    }

    [data-testid="stSidebar"] {
        background:#eef2f7;
        border-right:1px solid #dbe2ea;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top:1.5rem;
    }

    .sidebar-brand {
        display:flex;
        align-items:center;
        gap:.45rem;
        font-size:1.18rem;
        line-height:1.2;
        font-weight:800;
        color:#16243a;
        padding:.25rem 0 .7rem 0;
        white-space:nowrap;
    }

    .block-container {
        max-width:1500px;
        padding-top:1.0rem;
        padding-bottom:2.5rem;
    }

    /* Hero */
    .hero {
        position:relative;
        min-height:150px;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        text-align:center;
        padding:1.7rem 2rem;
        margin:0 0 1.1rem 0;
        border-radius:0 0 14px 14px;
        overflow:hidden;
        color:#fff;
        border:0;
        box-shadow:0 8px 24px rgba(25,55,90,.10);
        background:
            linear-gradient(90deg, rgba(11,43,75,.97) 0%, rgba(18,59,95,.88) 48%, rgba(18,59,95,.52) 100%),
            url("https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1800&q=85");
        background-size:cover;
        background-position:center 58%;
    }

    .hero h1 {
        margin:0;
        font-size:3.25rem;
        line-height:1.08;
        letter-spacing:-.035em;
        text-align:center;
        width:100%;
        font-weight:800;
    }

    .badge {
        display:inline-block;
        padding:.25rem .62rem;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.28);
        font-size:.69rem;
        margin:.65rem .28rem 0 0;
        background:rgba(255,255,255,.10);
        color:#fff;
    }

    .real-badge {
        display:inline-block;
        padding:.3rem .68rem;
        border-radius:999px;
        border:1px solid #c7d5e6;
        color:#244b73;
        background:#fff;
        font-size:.72rem;
        font-weight:700;
    }

    .section-note { color:#657386; font-size:.86rem; }

    /* Reference-style KPI cards */
    .judge-strip {
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:.7rem;
        margin:.15rem 0 1rem 0;
    }

    .judge-card {
        min-height:78px;
        padding:.78rem .9rem;
        border:1px solid #dfe5ec;
        border-radius:11px;
        background:#fff;
        box-shadow:0 2px 8px rgba(20,38,60,.035);
    }

    .judge-card .label {
        font-size:.66rem;
        text-transform:uppercase;
        letter-spacing:.075em;
        color:#718096;
        font-weight:700;
    }

    .judge-card .value {
        font-size:1.18rem;
        font-weight:750;
        color:#16243a;
        margin-top:.2rem;
    }

    .metric-strip .status-chip {
        display:none;
    }

    .status-chip {
        display:inline-block;
        padding:.3rem .62rem;
        border-radius:999px;
        margin:.1rem .2rem .1rem 0;
        font-size:.7rem;
        border:1px solid #dbe2ea;
        background:#fff;
        color:#536174;
    }

    .status-good { background:#f0f7f2; color:#2f6f45; border-color:#cfe4d5; }
    .status-warn { background:#fff8e8; color:#8a6514; border-color:#ead9a7; }
    .status-bad { background:#fff1f1; color:#9b3b3b; border-color:#ebcaca; }
    .status-neutral { background:#f7f9fb; color:#596779; }

    .metric-strip { padding:.25rem 0 .35rem 0; }

    .callout {
        padding:.78rem 1rem;
        border-left:3px solid #4d83b5;
        border-radius:8px;
        background:#edf5fc;
        color:#3d5268;
        margin:.8rem 0 1rem 0;
        font-size:.82rem;
    }

    .movement-callout {
        font-size:1.02rem;
        font-weight:600;
        line-height:1.5;
        padding:.9rem 1.05rem;
    }

    .gate {
        padding:1rem 1.1rem;
        border-radius:10px;
        margin:.7rem 0 1rem 0;
        border:1px solid #dfe5ec;
        background:#fff;
    }

    /* Streamlit native metric cards */
    [data-testid="stMetric"] {
        background:#fff;
        border:1px solid #dfe5ec;
        border-radius:11px;
        padding:.72rem .85rem;
        box-shadow:0 2px 8px rgba(20,38,60,.035);
        min-height:92px;
        box-sizing:border-box;
    }

    [data-testid="stMetricLabel"] {
        color:#69778a;
        font-size:.78rem;
    }

    [data-testid="stMetricValue"] {
        color:#16243a;
        font-size:1.85rem;
        line-height:1.1;
    }

    /* Keep the Latest Index card aligned with the other KPI cards.
       Its movement value is shown compactly on the right side. */
    [data-testid="column"]:first-child [data-testid="stMetric"] {
        position:relative;
        padding-right:5.8rem;
    }

    [data-testid="column"]:first-child [data-testid="stMetricDelta"] {
        position:absolute;
        right:.75rem;
        top:50%;
        transform:translateY(-50%);
        margin:0;
        font-size:.82rem;
        line-height:1.15;
        white-space:nowrap;
        text-align:right;
    }

    /* Inputs */
    [data-testid="stSidebar"] label {
        color:#344257 !important;
        font-weight:600;
        font-size:.82rem;
    }

    [data-testid="stSidebar"] [data-baseweb="select"],
    [data-testid="stSidebar"] input {
        background:#fff !important;
    }

    /* Tables / tabs */
    [data-testid="stDataFrame"] {
        border:1px solid #dfe5ec;
        border-radius:10px;
        overflow:hidden;
        background:#fff;
    }

    button[data-baseweb="tab"] {
        font-weight:650;
        color:#5c6a7d;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color:#0f5d96;
    }

    @media (max-width:1100px) {
        .judge-strip { grid-template-columns:repeat(2,1fr); }
        .hero h1 { font-size:2rem; }
    }

    @media (max-width:700px) {
        .judge-strip { grid-template-columns:1fr; }
        .hero { padding:1.2rem; min-height:125px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# REAL-DATA LOADERS
# ============================================================

@st.cache_data(show_spinner="Loading real statistical datasets...")
def load_dashboard_data():
    clean = load_clean_data()
    raw = load_raw_observations()
    daily = load_daily_index()
    routes = load_route_indices()
    lead = load_advance_window_indices()
    return clean, raw, daily, routes, lead


@st.cache_data(show_spinner=False)
def load_real_artifacts():
    """Load audit, coverage, metadata and pipeline provenance artifacts."""

    audit = pd.read_csv(REAL_AUDIT_PATH) if REAL_AUDIT_PATH.exists() else pd.DataFrame()
    coverage = pd.read_csv(REAL_COVERAGE_PATH) if REAL_COVERAGE_PATH.exists() else pd.DataFrame()

    metadata = {}
    if REAL_METADATA_PATH.exists():
        try:
            metadata = json.loads(REAL_METADATA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            metadata = {}

    pipeline_report = {}
    if REAL_PIPELINE_REPORT_PATH.exists():
        try:
            pipeline_report = json.loads(
                REAL_PIPELINE_REPORT_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            pipeline_report = {}

    return audit, coverage, metadata, pipeline_report


def normalize_daily_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the statistical engine's national_index column to the
    dashboard contract overall_airfare_index.

    The statistical engine remains the source of truth.
    """
    out = df.copy()

    rename_candidates = {
        "national_index": "overall_airfare_index",
        "index_value": "overall_airfare_index",
        "airfare_index": "overall_airfare_index",
    }

    if "overall_airfare_index" not in out.columns:
        for source, target in rename_candidates.items():
            if source in out.columns:
                out = out.rename(columns={source: target})
                break

    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(
            out["collection_date"], errors="coerce"
        )

    if "overall_airfare_index" in out.columns:
        out["overall_airfare_index"] = pd.to_numeric(
            out["overall_airfare_index"], errors="coerce"
        )

    return out


def normalize_route_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "date" in out.columns and "collection_date" not in out.columns:
        out = out.rename(columns={"date": "collection_date"})

    if "index" in out.columns and "route_index" not in out.columns:
        out = out.rename(columns={"index": "route_index"})

    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(
            out["collection_date"], errors="coerce"
        )

    if "route_index" in out.columns:
        out["route_index"] = pd.to_numeric(
            out["route_index"], errors="coerce"
        )

    return out


def normalize_lead_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "date" in out.columns and "collection_date" not in out.columns:
        out = out.rename(columns={"date": "collection_date"})

    for candidate in (
        "mean_stratum_index",
        "lead_time_index",
        "mean_index",
        "advance_window_index",
        "index",
    ):
        if "airfare_index" not in out.columns and candidate in out.columns:
            out = out.rename(columns={candidate: "airfare_index"})
            break

    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(
            out["collection_date"], errors="coerce"
        )

    if "airfare_index" in out.columns:
        out["airfare_index"] = pd.to_numeric(
            out["airfare_index"], errors="coerce"
        )

    return out


clean_data, raw_data, daily_index, route_indices, advance_indices = load_dashboard_data()
audit_data, coverage_data, metadata, pipeline_report = load_real_artifacts()

daily_index = normalize_daily_index(daily_index)
route_indices = normalize_route_index(route_indices)
advance_indices = normalize_lead_index(advance_indices)


# ============================================================
# VALIDATION OF DASHBOARD CONTRACT
# ============================================================

if "collection_date" not in daily_index.columns:
    st.error("Real index artifact is missing `collection_date`.")
    st.stop()

if "overall_airfare_index" not in daily_index.columns:
    st.error(
        "Real index artifact does not contain a recognized national index "
        "column (`national_index` / `overall_airfare_index`)."
    )
    st.stop()


# ============================================================
# HELPERS
# ============================================================

def add_route(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if {"origin", "destination"}.issubset(out.columns):
        out["route"] = (
            out["origin"].astype(str).str.upper().str.strip()
            + "_"
            + out["destination"].astype(str).str.upper().str.strip()
        )
    return out


def filter_dates(
    df: pd.DataFrame,
    start,
    end,
    column="collection_date",
) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df.copy()

    out = df.copy()
    values = pd.to_datetime(out[column], errors="coerce")

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)

    return out.loc[
        (values >= start_ts) & (values <= end_ts)
    ].copy()


def safe_pct_change(values: pd.Series, periods: int = 1) -> float:
    s = pd.to_numeric(values, errors="coerce").dropna()
    if len(s) <= periods:
        return float("nan")

    previous = s.iloc[-1 - periods]
    current = s.iloc[-1]

    if previous == 0:
        return float("nan")

    return float((current / previous - 1) * 100)


def format_change(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:+.2f}%"


def weekly_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "overall_airfare_index" not in df.columns:
        return pd.DataFrame(columns=["week", "airfare_index"])

    out = df.copy()
    out["collection_date"] = pd.to_datetime(
        out["collection_date"], errors="coerce"
    )
    out["week"] = out["collection_date"].dt.to_period("W").astype(str)

    return (
        out.dropna(subset=["week", "overall_airfare_index"])
        .groupby("week", as_index=False)["overall_airfare_index"]
        .median()
        .rename(columns={"overall_airfare_index": "airfare_index"})
    )


def monthly_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "overall_airfare_index" not in df.columns:
        return pd.DataFrame(columns=["month", "airfare_index"])

    out = df.copy()
    out["collection_date"] = pd.to_datetime(
        out["collection_date"], errors="coerce"
    )
    out["month"] = out["collection_date"].dt.to_period("M").astype(str)

    return (
        out.dropna(subset=["month", "overall_airfare_index"])
        .groupby("month", as_index=False)["overall_airfare_index"]
        .median()
        .rename(columns={"overall_airfare_index": "airfare_index"})
    )


def build_route_movers(route_df: pd.DataFrame) -> pd.DataFrame:
    required = {"route", "collection_date", "route_index"}

    if route_df.empty or not required.issubset(route_df.columns):
        return pd.DataFrame(
            columns=["route", "change_pct", "latest_index"]
        )

    d = route_df.copy()
    d["collection_date"] = pd.to_datetime(
        d["collection_date"], errors="coerce"
    )
    d["route_index"] = pd.to_numeric(
        d["route_index"], errors="coerce"
    )

    d = d.dropna(
        subset=["route", "collection_date", "route_index"]
    )

    rows = []

    for route, group in d.sort_values("collection_date").groupby("route"):
        group = group.drop_duplicates(
            "collection_date",
            keep="last",
        )

        if len(group) < 2:
            continue

        first = float(group["route_index"].iloc[0])
        last = float(group["route_index"].iloc[-1])

        change = (
            ((last / first) - 1) * 100
            if first
            else float("nan")
        )

        rows.append(
            {
                "route": route,
                "change_pct": change,
                "latest_index": last,
                "observed_days": len(group),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "route",
                "change_pct",
                "latest_index",
                "observed_days",
            ]
        )

    return pd.DataFrame(rows).sort_values(
        "change_pct",
        ascending=False,
    )


def build_route_lead_heatmap(clean_df: pd.DataFrame) -> pd.DataFrame:
    required = {
        "route",
        "advance_days",
        "total_fare",
    }

    if clean_df.empty or not required.issubset(clean_df.columns):
        return pd.DataFrame()

    d = clean_df.copy()
    d["advance_days"] = pd.to_numeric(
        d["advance_days"], errors="coerce"
    )
    d["total_fare"] = pd.to_numeric(
        d["total_fare"], errors="coerce"
    )

    d = d.dropna(
        subset=[
            "route",
            "advance_days",
            "total_fare",
        ]
    )

    if d.empty:
        return pd.DataFrame()

    return (
        d.groupby(
            ["route", "advance_days"]
        )["total_fare"]
        .median()
        .unstack("advance_days")
        .sort_index()
    )


def render_status_chip(
    label: str,
    value: str,
    state: str = "neutral",
):
    cls = {
        "good": "status-good",
        "warn": "status-warn",
        "bad": "status-bad",
        "neutral": "status-neutral",
    }.get(state, "status-neutral")

    st.markdown(
        f'<span class="status-chip {cls}">'
        f'<b>{label}</b>&nbsp; {value}</span>',
        unsafe_allow_html=True,
    )


def audit_latest_status() -> dict:
    """Return the latest audit row for the latest collection date."""

    if audit_data.empty:
        return {}

    out = audit_data.copy()

    date_col = next(
        (
            c
            for c in [
                "collection_date",
                "date",
            ]
            if c in out.columns
        ),
        None,
    )

    if date_col is None:
        return {}

    out["_date"] = pd.to_datetime(
        out[date_col],
        errors="coerce",
    )

    out = out.dropna(subset=["_date"]).sort_values("_date")

    if out.empty:
        return {}

    return out.iloc[-1].to_dict()


def bool_value(row: dict, key: str) -> bool | None:
    if key not in row:
        return None

    value = row[key]

    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    if str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "pass",
        "passed",
    }:
        return True

    if str(value).strip().lower() in {
        "false",
        "0",
        "no",
        "fail",
        "failed",
    }:
        return False

    return None


def audit_gate_state(value: bool | None) -> str:
    if value is True:
        return "good"
    if value is False:
        return "bad"
    return "neutral"


def latest_publishable_date() -> str:
    if audit_data.empty:
        return "—"

    out = audit_data.copy()

    date_col = (
        "collection_date"
        if "collection_date" in out.columns
        else "date"
        if "date" in out.columns
        else None
    )

    if date_col is None or "publication_status" not in out.columns:
        return "—"

    out["_date"] = pd.to_datetime(
        out[date_col],
        errors="coerce",
    )

    publishable = out[
        out["publication_status"]
        .astype(str)
        .str.upper()
        .eq("PUBLISHABLE")
    ]

    if publishable.empty:
        return "None"

    return str(
        publishable["_date"].max().date()
    )


def metadata_value(*keys, default="—"):
    for key in keys:
        if key in metadata and metadata[key] not in (None, ""):
            return metadata[key]
    return default


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    '<div class="sidebar-brand">✈️ <span>Airfare Index</span></div>',
    unsafe_allow_html=True,
)
st.sidebar.divider()

# Observation filters should cover the complete scraped observation
# universe, not only the dates for which a precomputed index exists.
valid_dates = (
    pd.to_datetime(
        clean_data["collection_timestamp"],
        errors="coerce",
    )
    .dropna()
    if "collection_timestamp" in clean_data.columns
    else pd.Series(dtype="datetime64[ns]")
)

if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()

    selected_dates = st.sidebar.date_input(
        "Collection date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    selected_dates = None

clean_with_route = add_route(clean_data)

available_routes = (
    sorted(clean_with_route["route"].dropna().unique())
    if "route" in clean_with_route
    else []
)

available_airlines = (
    sorted(
        clean_data["airline"]
        .dropna()
        .astype(str)
        .unique()
    )
    if "airline" in clean_data
    else []
)

available_sources = (
    sorted(
        clean_data["source"]
        .dropna()
        .astype(str)
        .unique()
    )
    if "source" in clean_data
    else []
)

selected_routes = st.sidebar.multiselect(
    "Routes",
    available_routes,
)

selected_airlines = st.sidebar.multiselect(
    "Airlines",
    available_airlines,
)

selected_sources = st.sidebar.multiselect(
    "Sources",
    available_sources,
)

st.sidebar.divider()


st.sidebar.caption(
    "Filters below affect exploratory views only. "
    "They never recalculate the headline index."
)

if st.sidebar.button(
    "🔄 Refresh statistical datasets",
    use_container_width=True,
):
    st.cache_data.clear()
    st.rerun()


# ============================================================
# FILTER DATA
# ============================================================

filtered_clean = clean_with_route.copy()
filtered_daily = daily_index.copy()
filtered_routes = route_indices.copy()
filtered_advance = advance_indices.copy()

if selected_dates is not None and len(selected_dates) == 2:
    start_date, end_date = selected_dates

    filtered_clean = filter_dates(
        filtered_clean,
        start_date,
        end_date,
        "collection_timestamp",
    )

    filtered_daily = filter_dates(
        filtered_daily,
        start_date,
        end_date,
    )

    filtered_routes = filter_dates(
        filtered_routes,
        start_date,
        end_date,
    )

    filtered_advance = filter_dates(
        filtered_advance,
        start_date,
        end_date,
    )

if selected_routes:
    if "route" in filtered_clean.columns:
        filtered_clean = filtered_clean[
            filtered_clean["route"].isin(selected_routes)
        ]

    if "route" in filtered_routes.columns:
        filtered_routes = filtered_routes[
            filtered_routes["route"].isin(selected_routes)
        ]

    if "route" in filtered_advance.columns:
        filtered_advance = filtered_advance[
            filtered_advance["route"].isin(selected_routes)
        ]

if selected_airlines and "airline" in filtered_clean.columns:
    filtered_clean = filtered_clean[
        filtered_clean["airline"].isin(selected_airlines)
    ]

if selected_sources and "source" in filtered_clean.columns:
    filtered_clean = filtered_clean[
        filtered_clean["source"].isin(selected_sources)
    ]


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>AirfareX</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

latest_audit = audit_latest_status()

# Publication status is taken directly from the latest audit record.
publication_status = str(latest_audit.get("publication_status", "UNKNOWN")).strip().upper()

latest_idx_value = (
    pd.to_numeric(
        daily_index["overall_airfare_index"],
        errors="coerce",
    )
    .dropna()
    .iloc[-1]
    if not daily_index.empty
    and daily_index["overall_airfare_index"].notna().any()
    else float("nan")
)

latest_idx_date = (
    pd.to_datetime(
        daily_index["collection_date"],
        errors="coerce",
    )
    .max()
    if not daily_index.empty
    else pd.NaT
)

expected_routes = metadata_value(
    "expected_routes",
    "route_universe",
    default=[],
)

expected_windows = metadata_value(
    "advance_windows",
    default=[],
)

if isinstance(expected_routes, str):
    expected_routes = [x.strip() for x in expected_routes.split(",") if x.strip()]

if isinstance(expected_windows, str):
    expected_windows = [x.strip() for x in expected_windows.split(",") if x.strip()]

st.markdown(
    f"""
    <div class="judge-strip">
        <div class="judge-card">
            <div class="label">Headline index</div>
            <div class="value">{latest_idx_value:.2f}</div>
        </div>
        <div class="judge-card">
            <div class="label">Latest date</div>
            <div class="value">{latest_idx_date.date() if pd.notna(latest_idx_date) else "—"}</div>
        </div>
        <div class="judge-card">
            <div class="label">Routes</div>
            <div class="value">{len(expected_routes) if expected_routes else route_count(clean_data)}</div>
        </div>
        <div class="judge-card">
            <div class="label">Lead windows</div>
            <div class="value">{len(expected_windows) if expected_windows else 5}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# NAVIGATION
# ============================================================

pages = st.tabs(
    [
        "📊 Overview",
        "📈 Index Analytics",
        "🗺 Route Intelligence",
        "⏱ Lead-Time Analysis",
        "🛡 Data Quality",
        "📡 Source Health",
        "🔎 Raw Data Explorer",
        "⚙️ Automation Control Center",
        "📘 Methodology",
    ]
)


# ============================================================
# OVERVIEW
# ============================================================

with pages[0]:
    if filtered_daily.empty:
        st.warning(
            "No precomputed index observations are available "
            "for the selected date range."
        )
    else:
        current = latest_index(filtered_daily)
        previous = previous_index(filtered_daily)

        period_change_value = index_change_percent(
            current,
            previous,
        )

        change_7d = safe_pct_change(
            filtered_daily["overall_airfare_index"],
            7,
        )

        change_30d = safe_pct_change(
            filtered_daily["overall_airfare_index"],
            30,
        )

        quality = calculate_data_quality(
            filtered_clean
        )

        quality_score = max(
            0.0,
            100.0
            - float(quality.get("missing_fare_pct", 0) or 0)
            - float(quality.get("duplicate_pct", 0) or 0),
        )

        # --------------------------------------------------------
        # Reference-style KPI row
        # --------------------------------------------------------
        st.markdown("### Airfare Price Index at a Glance")

        c1, c2, c3, c4, c5, c6 = st.columns(6)

        c1.metric(
            "Latest Index",
            f"{current:.2f}",
            format_change(period_change_value),
        )

        c2.metric(
            "Previous Index",
            f"{previous:.2f}" if pd.notna(previous) else "—",
        )

        c3.metric(
            "Total Observations",
            f"{observation_count(clean_data):,}",
        )

        c4.metric(
            "Total Routes",
            f"{route_count(clean_data):,}",
        )

        c5.metric(
            "Total Airlines",
            f"{airline_count(clean_data):,}",
        )

        c6.metric(
            "Total Sources",
            f"{source_count(clean_data):,}",
        )

        st.markdown(
            f'<div class="callout movement-callout"><b>Base = 100</b> · Latest movement {format_change(period_change_value)} · '
            f'7-day movement {format_change(change_7d)} · 30-day movement {format_change(change_30d)}</div>',
            unsafe_allow_html=True,
        )

        # --------------------------------------------------------
        # Main index chart
        # --------------------------------------------------------
        st.markdown("### Airfare Price Index (India)")

        fig = create_overall_index_chart(
            filtered_daily
        )

        fig.update_layout(
            height=390,
            margin=dict(l=10, r=15, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            key="overview_index_chart",
        )

        overall_table = filtered_daily.copy()
        keep = [c for c in ["collection_date", "overall_airfare_index"] if c in overall_table.columns]
        if keep:
            display_chart_data_table(
                "Index Data",
                overall_table[keep].tail(30),
                {"collection_date": "Collection Date", "overall_airfare_index": "Airfare Index"},
            )

        # --------------------------------------------------------
        # Secondary analytical panels
        # --------------------------------------------------------
        left, right = st.columns([1.15, .85])

        with left:
            st.markdown("### Route-wise Index")

            movers = build_route_movers(
                filtered_routes
            )

            if not movers.empty:
                top = (
                    movers
                    .head(10)
                    .sort_values("change_pct")
                )

                pulse = px.bar(
                    top,
                    x="change_pct",
                    y="route",
                    orientation="h",
                    text="change_pct",
                    labels={
                        "change_pct": "Period Change (%)",
                        "route": "Route",
                    },
                )

                pulse.update_traces(
                    texttemplate="%{text:.1f}%",
                    textposition="outside",
                )

                pulse.update_layout(
                    height=350,
                    margin=dict(l=5, r=35, t=15, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )

                st.plotly_chart(
                    pulse,
                    use_container_width=True,
                    key="overview_route_pulse",
                )
                display_chart_data_table(
                    "Route Movement Data",
                    top[[c for c in ["route", "latest_index", "change_pct", "observed_days"] if c in top.columns]],
                    {"route": "Route", "latest_index": "Latest Index", "change_pct": "Period Change (%)", "observed_days": "Observed Days"},
                )
            else:
                st.info("Insufficient route history for movement analysis.")

        with right:
            st.markdown("### Lead Time Price Index")

            if filtered_advance.empty:
                st.info("No lead-time contribution data available.")
            else:
                lead_fig = create_lead_time_chart(
                    filtered_advance
                )

                lead_fig.update_layout(
                    height=350,
                    margin=dict(l=5, r=15, t=15, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )

                st.plotly_chart(
                    lead_fig,
                    use_container_width=True,
                    key="overview_lead_time_chart",
                )
                lead_table = filtered_advance.copy()
                keep = [c for c in ["collection_date", "advance_days", "airfare_index"] if c in lead_table.columns]
                if keep:
                    display_chart_data_table(
                        "Lead-Time Index Data",
                        lead_table[keep].tail(30),
                        {"collection_date": "Collection Date", "advance_days": "Advance Days", "airfare_index": "Airfare Index"},
                    )

        # --------------------------------------------------------
        # Source coverage + data quality
        # --------------------------------------------------------
        left, right = st.columns([1.15, .85])

        with left:
            st.markdown("### Source Coverage")

            source_values = (
                filtered_clean["source"].dropna().astype(str)
                if "source" in filtered_clean.columns
                else pd.Series(dtype=str)
            )
            source_counts = source_values.value_counts()

            if not source_counts.empty:
                source_df = (
                    source_counts
                    .rename("observations")
                    .reset_index()
                )
                source_df.columns = ["source", "observations"]

                source_fig = px.pie(
                    source_df,
                    names="source",
                    values="observations",
                    hole=.58,
                )
                source_fig.update_traces(
                    textposition="inside",
                    textinfo="percent",
                    hovertemplate="%{label}<br>%{value:,} observations<extra></extra>",
                )
                source_fig.update_layout(
                    height=330,
                    margin=dict(l=5, r=5, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=True,
                    legend=dict(orientation="v"),
                )
                st.plotly_chart(
                    source_fig,
                    use_container_width=True,
                    key="overview_source_coverage",
                )
                source_table = source_df.copy()
                source_table["share_pct"] = source_table["observations"] / source_table["observations"].sum() * 100
                display_chart_data_table(
                    "Source Coverage Data",
                    source_table[["source", "observations", "share_pct"]],
                    {"source": "Source", "observations": "Observations", "share_pct": "Share (%)"},
                )
            else:
                st.info("No source observations available for the selected filters.")

        with right:
            st.markdown("### Data Quality")

            quality_fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=quality_score,
                    number={"suffix": "%", "font": {"size": 34}},
                    title={"text": "Valid observations"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"thickness": .22},
                        "steps": [
                            {"range": [0, 80], "color": "#e7edf3"},
                            {"range": [80, 95], "color": "#dfeaf4"},
                            {"range": [95, 100], "color": "#d8eadf"},
                        ],
                        "threshold": {
                            "line": {"width": 3},
                            "thickness": .75,
                            "value": quality_score,
                        },
                    },
                )
            )
            quality_fig.update_layout(
                height=250,
                margin=dict(l=20, r=20, t=25, b=5),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(
                quality_fig,
                use_container_width=True,
                key="overview_quality_gauge",
            )
            quality_table = pd.DataFrame([
                {
                    "Metric": "Valid observations",
                    "Value": f"{quality_score:.2f}%",
                    "Description": "100% minus missing-fare and duplicate rates",
                },
                {
                    "Metric": "Missing fare",
                    "Value": f"{float(quality.get('missing_fare_pct', 0) or 0):.2f}%",
                    "Description": "Share of observations without a valid fare",
                },
                {
                    "Metric": "Duplicate rate",
                    "Value": f"{float(quality.get('duplicate_pct', 0) or 0):.2f}%",
                    "Description": "Share identified as duplicate observations",
                },
            ])
            display_chart_data_table("Data Quality Data", quality_table)

            qa1, qa2, qa3 = st.columns(3)
            qa1.metric(
                "Missing",
                f"{float(quality.get('missing_fare_pct', 0) or 0):.1f}%",
            )
            qa2.metric(
                "Duplicates",
                f"{float(quality.get('duplicate_pct', 0) or 0):.1f}%",
            )
            qa3.metric(
                "Quality",
                f"{quality_score:.1f}%",
            )



# ============================================================
# INDEX ANALYTICS
# ============================================================

with pages[1]:
    st.subheader("Index Analytics")

    st.markdown(
        '<div class="section-note">'
        'Daily, weekly and monthly diagnostic views of the precomputed '
        'national statistical index.'
        '</div>',
        unsafe_allow_html=True,
    )

    if filtered_daily.empty:
        st.info("No index data available.")
    else:
        st.plotly_chart(
            create_overall_index_chart(
                filtered_daily
            ),
            use_container_width=True,
            key="analytics_index_chart",
        )

        overall_analytics_table = filtered_daily.copy()
        keep = [c for c in ["collection_date", "overall_airfare_index"] if c in overall_analytics_table.columns]
        if keep:
            display_chart_data_table("Index Analytics Data", overall_analytics_table[keep].tail(30), {"collection_date": "Collection Date", "overall_airfare_index": "Airfare Index"})

        weekly = weekly_index(
            filtered_daily
        )

        monthly = monthly_index(
            filtered_daily
        )

        left, right = st.columns(2)

        with left:
            st.markdown("#### Weekly View")
            st.dataframe(
                weekly.tail(12),
                use_container_width=True,
                hide_index=True,
            )

        with right:
            st.markdown("#### Monthly View")
            st.dataframe(
                monthly.tail(12),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Daily Index Audit Trail")

        movement = filtered_daily.copy()

        movement["collection_date"] = pd.to_datetime(
            movement["collection_date"],
            errors="coerce",
        )

        movement["daily_change_pct"] = (
            movement["overall_airfare_index"]
            .pct_change()
            * 100
        )

        display_cols = [
            c
            for c in [
                "collection_date",
                "overall_airfare_index",
                "daily_change_pct",
                "status",
                "coverage_status",
                "publication_status",
            ]
            if c in movement.columns
        ]

        st.dataframe(
            movement[display_cols].tail(60),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "The index values above come directly from the precomputed "
            "statistical index artifact."
        )


# ============================================================
# ROUTE INTELLIGENCE
# ============================================================

with pages[2]:
    st.subheader("Route Intelligence")

    st.markdown(
        '<div class="section-note">'
        'Route-level diagnostics for movement, dispersion and observed '
        'fare structure. These views do not redefine the national index.'
        '</div>',
        unsafe_allow_html=True,
    )

    if filtered_routes.empty:
        st.info("No route-level index data available.")
    else:
        movement_table = build_route_movers(
            filtered_routes
        )

        if not movement_table.empty:
            strongest = movement_table.iloc[0]
            weakest = movement_table.iloc[-1]

            r1, r2, r3, r4 = st.columns(4)

            r1.metric(
                "Routes Analysed",
                f"{len(movement_table):,}",
            )

            r2.metric(
                "Largest Increase",
                f"{strongest['route']} "
                f"{strongest['change_pct']:+.2f}%",
            )

            r3.metric(
                "Largest Decrease",
                f"{weakest['route']} "
                f"{weakest['change_pct']:+.2f}%",
            )

            r4.metric(
                "Median Latest Route Index",
                f"{movement_table['latest_index'].median():.2f}",
            )

        st.plotly_chart(
            create_route_index_chart(
                filtered_routes
            ),
            use_container_width=True,
            key="route_index_chart",
        )

        route_chart_table = filtered_routes.copy()
        keep = [c for c in ["collection_date", "route", "airfare_index"] if c in route_chart_table.columns]
        if keep:
            display_chart_data_table("Route Index Data", route_chart_table[keep].tail(50), {"collection_date": "Collection Date", "route": "Route", "airfare_index": "Route Index"})

        if not movement_table.empty:
            st.subheader("Route Movement Ranking")

            ranking = movement_table.copy()

            ranking["latest_index"] = (
                ranking["latest_index"].round(2)
            )

            ranking["change_pct"] = (
                ranking["change_pct"].round(2)
            )

            st.dataframe(
                ranking.rename(
                    columns={
                        "route": "Route",
                        "latest_index": "Latest Index",
                        "change_pct": "Period Change (%)",
                        "observed_days": "Observed Days",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.subheader(
            "Route × Lead-Time Observed Fare Structure"
        )

        heatmap_data = build_route_lead_heatmap(
            filtered_clean
        )

        if heatmap_data.empty:
            st.info(
                "Insufficient fare observations "
                "for the route × lead-time matrix."
            )
        else:
            heatmap = px.imshow(
                heatmap_data,
                text_auto=".0f",
                aspect="auto",
                labels={
                    "x": "Advance Days",
                    "y": "Route",
                    "color": "Median Fare (INR)",
                },
            )

            heatmap.update_layout(
                height=max(
                    360,
                    42 * len(heatmap_data) + 120,
                ),
                margin=dict(
                    l=10,
                    r=10,
                    t=35,
                    b=10,
                ),
            )

            st.plotly_chart(
                heatmap,
                use_container_width=True,
                key="route_lead_heatmap",
            )

            heatmap_table = heatmap_data.reset_index()
            display_chart_data_table("Route × Lead-Time Fare Data", heatmap_table)

            st.caption(
                "Exploratory median fare matrix. It is not a second "
                "national-index calculation."
            )

        st.subheader("Observed Route Coverage")

        coverage = calculate_route_coverage(
            filtered_clean
        )

        if coverage.empty:
            st.info(
                "No route coverage data available."
            )
        else:
            st.dataframe(
                coverage,
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# LEAD-TIME ANALYSIS
# ============================================================

with pages[3]:
    st.subheader("Lead-Time Analysis")

    st.markdown(
        '<div class="section-note">'
        'Configured advance-purchase windows: 1, 7, 15, 30 and 45 days. '
        'The index engine currently uses equal lead-time weighting.'
        '</div>',
        unsafe_allow_html=True,
    )

    if filtered_advance.empty:
        st.info(
            "No lead-time contribution data available."
        )
    else:
        st.plotly_chart(
            create_lead_time_chart(
                filtered_advance
            ),
            use_container_width=True,
            key="lead_time_chart",
        )

        lead_chart_table = filtered_advance.copy()
        keep = [c for c in ["collection_date", "advance_days", "airfare_index"] if c in lead_chart_table.columns]
        if keep:
            display_chart_data_table("Lead-Time Chart Data", lead_chart_table.tail(50)[keep], {"collection_date": "Collection Date", "advance_days": "Advance Days", "airfare_index": "Airfare Index"})

        if {
            "advance_days",
            "airfare_index",
        }.issubset(filtered_advance.columns):

            snapshot = filtered_advance.copy()

            if "collection_date" in snapshot.columns:
                snapshot["collection_date"] = pd.to_datetime(
                    snapshot["collection_date"],
                    errors="coerce",
                )

                latest_date = snapshot[
                    "collection_date"
                ].max()

                snapshot = snapshot[
                    snapshot["collection_date"]
                    == latest_date
                ]

            snapshot["advance_days"] = pd.to_numeric(
                snapshot["advance_days"],
                errors="coerce",
            )

            snapshot["airfare_index"] = pd.to_numeric(
                snapshot["airfare_index"],
                errors="coerce",
            )

            snapshot = snapshot.dropna(
                subset=[
                    "advance_days",
                    "airfare_index",
                ]
            )

            snapshot = (
                snapshot
                .groupby("advance_days", as_index=False)[
                    "airfare_index"
                ]
                .median()
                .sort_values("advance_days")
            )

            if not snapshot.empty:
                st.subheader(
                    "Latest Lead-Time Statistical Snapshot"
                )

                st.dataframe(
                    snapshot.rename(
                        columns={
                            "advance_days": "Advance Days",
                            "airfare_index": "Median Index",
                        }
                    ).round(2),
                    use_container_width=True,
                    hide_index=True,
                )

        st.subheader(
            "Observed Fare Distribution by Lead Time"
        )

        if {
            "advance_days",
            "total_fare",
        }.issubset(filtered_clean.columns):

            lead_fares = filtered_clean.copy()

            lead_fares["advance_days"] = pd.to_numeric(
                lead_fares["advance_days"],
                errors="coerce",
            )

            lead_fares["total_fare"] = pd.to_numeric(
                lead_fares["total_fare"],
                errors="coerce",
            )

            lead_fares = lead_fares.dropna(
                subset=[
                    "advance_days",
                    "total_fare",
                ]
            )

            if not lead_fares.empty:
                lead_summary = (
                    lead_fares
                    .groupby("advance_days")["total_fare"]
                    .agg(
                        [
                            "count",
                            "median",
                            "mean",
                            "min",
                            "max",
                        ]
                    )
                    .reset_index()
                    .sort_values("advance_days")
                )

                st.dataframe(
                    lead_summary.rename(
                        columns={
                            "advance_days": "Advance Days",
                            "count": "Observations",
                            "median": "Median Fare (INR)",
                            "mean": "Mean Fare (INR)",
                            "min": "Minimum Fare (INR)",
                            "max": "Maximum Fare (INR)",
                        }
                    ).round(2),
                    use_container_width=True,
                    hide_index=True,
                )

        st.info(
            "**Interpretation caution:** differences across lead-time "
            "windows show lead-time differentiated price movement. "
            "They should not be called demand elasticity without a "
            "proper longitudinal identification design."
        )


# ============================================================
# DATA QUALITY
# ============================================================

with pages[4]:
    st.subheader("Data Quality Command Center")

    st.markdown(
        '<div class="section-note">'
        'Operational QC signals derived from the processed observation '
        'layer and automated validation outputs.'
        '</div>',
        unsafe_allow_html=True,
    )

    quality = calculate_data_quality(
        filtered_clean
    )

    total_obs = int(
        quality.get(
            "total_observations",
            len(filtered_clean),
        )
    )

    missing_pct = float(
        quality.get(
            "missing_fare_pct",
            0,
        )
        or 0
    )

    duplicate_pct = float(
        quality.get(
            "duplicate_pct",
            0,
        )
        or 0
    )

    quality_score = max(
        0.0,
        min(
            100.0,
            100.0
            - missing_pct
            - duplicate_pct,
        ),
    )

    q1, q2, q3, q4, q5 = st.columns(5)

    q1.metric(
        "Dashboard Observations",
        f"{total_obs:,}",
    )

    q2.metric(
        "Missing Fare",
        f"{missing_pct:.2f}%",
    )

    q3.metric(
        "Duplicate Rate",
        f"{duplicate_pct:.2f}%",
    )

    q4.metric(
        "Operational Quality Score",
        f"{quality_score:.1f}/100",
    )

    q5.metric(
        "Status",
        (
            "Healthy"
            if quality_score >= 99
            else "Review"
            if quality_score >= 97
            else "Attention"
        ),
    )

    st.caption(
        "The composite Quality Score is an engineering monitoring "
        "metric, not an official statistical quality standard."
    )

    st.divider()

    st.markdown("#### Automated Audit Gates")

    audit_checks = [
        ("Structural validation", "structural_validation_pass"),
        ("Duplicate QC", "duplicate_qc_pass"),
        ("Representative fares", "representative_fares_pass"),
        ("Index calculation", "index_calculation_pass"),
        ("Contribution reconciliation", "contribution_reconciliation_pass"),
        ("Base-period check", "base_period_pass"),
    ]

    gate_cols = st.columns(3)

    for i, (label, key) in enumerate(audit_checks):
        value = bool_value(
            latest_audit,
            key,
        )

        with gate_cols[i % 3]:
            if value is True:
                st.success(
                    f"✓ {label}: PASS"
                )
            elif value is False:
                st.error(
                    f"✕ {label}: FAIL"
                )
            else:
                st.info(
                    f"• {label}: NOT AVAILABLE"
                )

    if latest_audit.get("failed_checks"):
        st.error(
            f"Failed checks: {latest_audit['failed_checks']}"
        )

    if latest_audit.get("warnings"):
        st.warning(
            f"Audit warnings: {latest_audit['warnings']}"
        )

    st.divider()

    st.subheader("Potential Fare Anomalies")

    anomaly_data = detect_fare_anomalies(
        filtered_clean
    )

    if anomaly_data.empty:
        st.info(
            "No anomaly-monitoring data available."
        )
    else:
        anomaly_count = (
            int(
                anomaly_data["anomaly_flag"].sum()
            )
            if "anomaly_flag" in anomaly_data
            else 0
        )

        anomaly_rate = (
            anomaly_count
            / len(anomaly_data)
            * 100
            if len(anomaly_data)
            else 0
        )

        a1, a2, a3 = st.columns(3)

        a1.metric(
            "Potential Anomalies",
            f"{anomaly_count:,}",
        )

        a2.metric(
            "Anomaly Rate",
            f"{anomaly_rate:.2f}%",
        )

        a3.metric(
            "Records Reviewed",
            f"{len(anomaly_data):,}",
        )

        flagged = (
            anomaly_data[
                anomaly_data["anomaly_flag"]
            ].copy()
            if "anomaly_flag" in anomaly_data
            else pd.DataFrame()
        )

        if flagged.empty:
            st.success(
                "No potential fare anomalies detected."
            )
        else:
            st.warning(
                "Flagged observations are review candidates. "
                "Extreme prices are not automatically deleted because "
                "they may represent genuine market behaviour."
            )

            cols = [
                c
                for c in [
                    "collection_timestamp",
                    "origin",
                    "destination",
                    "airline",
                    "flight_number",
                    "advance_days",
                    "base_fare",
                    "taxes",
                    "consumer_fare",
                    "total_fare",
                    "route",
                    "anomaly_flag",
                ]
                if c in flagged.columns
            ]

            anomaly_display = flagged[cols].head(100).copy()
            anomaly_display = anomaly_display.rename(columns={
                "base_fare": "Base Fare (INR)",
                "taxes": "Taxes & Fees (INR)",
                "consumer_fare": "Consumer Fare (INR)",
                "total_fare": "Source Total (INR)",
            })

            st.caption(
                "Consumer Fare = Base Fare + Taxes & Fees. "
                "Source Total is retained separately for reconciliation."
            )
            st.dataframe(
                anomaly_display,
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# SOURCE HEALTH
# ============================================================

with pages[5]:
    st.subheader("Source Health & Observation Coverage")

    st.markdown(
        '<div class="section-note">'
        'This view reports observed source contribution from the processed '
        'dataset. It does not fabricate API latency or source success rates.'
        '</div>',
        unsafe_allow_html=True,
    )

    if filtered_clean.empty:
        st.info(
            "No source observations available."
        )
    else:
        source_values = (
            filtered_clean["source"]
            .dropna()
            .astype(str)
            if "source" in filtered_clean.columns
            else pd.Series(dtype=str)
        )

        observed_sources = int(
            source_values.nunique()
        )

        full_source_values = (
            clean_data["source"]
            .dropna()
            .astype(str)
            if "source" in clean_data.columns
            else pd.Series(dtype=str)
        )

        configured_sources = int(
            full_source_values.nunique()
        )

        latest_obs_date = (
            pd.to_datetime(
                filtered_clean["collection_timestamp"],
                errors="coerce",
            ).max()
            if "collection_timestamp"
            in filtered_clean.columns
            else pd.NaT
        )

        earliest_obs_date = (
            pd.to_datetime(
                filtered_clean["collection_timestamp"],
                errors="coerce",
            ).min()
            if "collection_timestamp"
            in filtered_clean.columns
            else pd.NaT
        )

        source_counts = (
            source_values.value_counts()
        )

        source_share = (
            source_counts
            / source_counts.sum()
            * 100
            if not source_counts.empty
            else pd.Series(dtype=float)
        )

        concentration = (
            float(source_share.iloc[0])
            if not source_share.empty
            else 0.0
        )

        s1, s2, s3, s4 = st.columns(4)

        s1.metric(
            "Observed Sources",
            f"{observed_sources}/{configured_sources}",
        )

        s2.metric(
            "Source Coverage",
            (
                f"{observed_sources / configured_sources * 100:.1f}%"
                if configured_sources
                else "—"
            ),
        )

        s3.metric(
            "Largest Source Share",
            f"{concentration:.1f}%",
        )

        s4.metric(
            "Latest Observation",
            (
                str(latest_obs_date.date())
                if pd.notna(latest_obs_date)
                else "—"
            ),
        )

        st.divider()

        left, right = st.columns(
            [1.3, 1]
        )

        with left:
            st.markdown(
                "#### Observation Share by Source"
            )

            source_df = (
                source_counts
                .rename("observations")
                .reset_index()
            )

            source_df.columns = [
                "source",
                "observations",
            ]

            source_df["share_pct"] = (
                source_df["observations"]
                / source_df["observations"].sum()
                * 100
            )

            source_fig = px.bar(
                source_df.sort_values(
                    "observations"
                ),
                x="observations",
                y="source",
                orientation="h",
                text="share_pct",
                labels={
                    "observations": "Observations",
                    "source": "Source",
                },
            )

            source_fig.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
            )

            source_fig.update_layout(
                height=370,
                margin=dict(
                    l=10,
                    r=35,
                    t=25,
                    b=10,
                ),
            )

            st.plotly_chart(
                source_fig,
                use_container_width=True,
                key="source_share_chart",
            )

            display_chart_data_table(
                "Observation Share Data",
                source_df[["source", "observations", "share_pct"]],
                {"source": "Source", "observations": "Observations", "share_pct": "Share (%)"},
            )

        with right:
            st.markdown(
                "#### Source Concentration Signal"
            )

            if concentration > 80:
                st.warning(
                    "Very high source concentration. "
                    "Independent observation channels should be added."
                )
            elif concentration > 50:
                st.warning(
                    "Source concentration is high. "
                    "Diversification would improve resilience."
                )
            else:
                st.success(
                    "No single source contributes more than half "
                    "of the observed records."
                )

            st.metric(
                "Observation Window",
                (
                    f"{earliest_obs_date.date()} → "
                    f"{latest_obs_date.date()}"
                    if pd.notna(earliest_obs_date)
                    and pd.notna(latest_obs_date)
                    else "—"
                ),
            )

            st.caption(
                "This is an observed concentration signal, not a "
                "formal reliability score."
            )

        st.subheader(
            "Source × Route Observation Coverage"
        )

        if {
            "source",
            "route",
        }.issubset(filtered_clean.columns):

            matrix = pd.crosstab(
                filtered_clean["source"],
                filtered_clean["route"],
            )

            if not matrix.empty:
                fig = px.imshow(
                    matrix,
                    aspect="auto",
                    text_auto=True,
                    labels={
                        "x": "Route",
                        "y": "Source",
                        "color": "Observations",
                    },
                )

                fig.update_layout(
                    height=max(
                        350,
                        45 * len(matrix) + 100,
                    )
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="source_route_heatmap",
                )

                coverage_table = matrix.reset_index()
                display_chart_data_table("Source × Route Coverage Data", coverage_table)

        source_coverage = (
            calculate_source_coverage(
                filtered_clean
            )
        )

        if not source_coverage.empty:
            st.dataframe(
                source_coverage,
                use_container_width=True,
                hide_index=True,
            )

        st.info(
            "**No fake runtime health:** live collector health will be "
            "displayed here only after actual collection-cycle telemetry "
            "is connected to the ingestion service."
        )


# ============================================================
# RAW DATA EXPLORER
# ============================================================

with pages[6]:
    st.subheader("Raw Airfare Data Explorer")
    st.markdown(
        '<div class="section-note">'
        'This view reads the raw_fares section directly from ' 
        '<code>data/raw/airfare_index.json</code>. No deduplication or ' 
        'cleaning is applied here, so the raw observation count is preserved.'
        '</div>',
        unsafe_allow_html=True,
    )

    raw_view = raw_data.copy()

    if raw_view.empty:
        st.warning("No raw airfare observations were found.")
    else:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Raw Observations", f"{len(raw_view):,}")
        r2.metric("Airlines", f"{raw_view['airline'].nunique():,}" if 'airline' in raw_view else "—")
        r3.metric("Routes", f"{raw_view['route'].nunique():,}" if 'route' in raw_view else "—")
        r4.metric("Sources", f"{raw_view['source'].nunique():,}" if 'source' in raw_view else "—")

        st.markdown("#### Explore the complete raw observation set")

        c1, c2, c3 = st.columns(3)
        raw_routes = sorted(raw_view['route'].dropna().astype(str).unique()) if 'route' in raw_view else []
        raw_airlines = sorted(raw_view['airline'].dropna().astype(str).unique()) if 'airline' in raw_view else []
        raw_sources = sorted(raw_view['source'].dropna().astype(str).unique()) if 'source' in raw_view else []

        route_filter = c1.multiselect("Route", raw_routes, key="raw_routes")
        airline_filter = c2.multiselect("Airline", raw_airlines, key="raw_airlines")
        source_filter = c3.multiselect("Source", raw_sources, key="raw_sources")

        if route_filter:
            raw_view = raw_view[raw_view['route'].isin(route_filter)]
        if airline_filter:
            raw_view = raw_view[raw_view['airline'].isin(airline_filter)]
        if source_filter:
            raw_view = raw_view[raw_view['source'].isin(source_filter)]

        if 'collection_timestamp' in raw_view.columns and not raw_view.empty:
            min_ts = raw_view['collection_timestamp'].min()
            max_ts = raw_view['collection_timestamp'].max()
            if pd.notna(min_ts) and pd.notna(max_ts):
                date_range = st.date_input(
                    "Collection date",
                    value=(min_ts.date(), max_ts.date()),
                    min_value=min_ts.date(),
                    max_value=max_ts.date(),
                    key="raw_date_range",
                )
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start, end = date_range
                    raw_view = raw_view[
                        (raw_view['collection_timestamp'].dt.date >= start)
                        & (raw_view['collection_timestamp'].dt.date <= end)
                    ]

        st.caption(
            f"Showing {len(raw_view):,} matching observations. "
            "The table is paginated for browser performance; no raw records are deleted."
        )

        page_size = st.selectbox(
            "Rows per page",
            [25, 50, 100, 250, 500],
            index=2,
            key="raw_page_size",
        )
        total_pages = max(1, (len(raw_view) + page_size - 1) // page_size)
        page_number = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key="raw_page_number",
        )
        start = (int(page_number) - 1) * page_size
        end = start + page_size

        display_cols = [
            'id', 'timestamp', 'route', 'airline', 'advance_window_days',
            'base_fare', 'taxes_fees', 'consumer_fare', 'total_fare', 'ota_source'
        ]
        display_cols = [c for c in display_cols if c in raw_view.columns]

        page_df = raw_view.iloc[start:end][display_cols].copy()
        page_df = page_df.rename(columns={
            'advance_window_days': 'Advance Days',
            'base_fare': 'Base Fare (INR)',
            'taxes_fees': 'Taxes & Fees (INR)',
            'consumer_fare': 'Consumer Fare (INR)',
            'total_fare': 'Source Total (INR)',
            'ota_source': 'Source',
        })

        st.dataframe(
            page_df,
            use_container_width=True,
            hide_index=True,
        )

        st.info(
            "Raw data is preserved separately from the clean statistical dataset. "
            "The headline index continues to use the precomputed statistical artifacts."
        )


# ============================================================
# AUTOMATION CONTROL CENTER
# ============================================================

with pages[7]:
    st.subheader(
        "Smart Automation Control Center"
    )

    st.markdown(
        '<div class="section-note">'
        'The control center is audit-driven: it reports what the pipeline '
        'actually produced instead of inventing source execution metrics.'
        '</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Publication gate
    # --------------------------------------------------------

    if publication_status == "PUBLISHABLE":
        st.success(
            "🟢 LATEST INDEX: PUBLISHABLE — automated statistical gates passed."
        )
    elif publication_status == "HOLD":
        st.warning(
            "🟡 LATEST INDEX: HOLD — coverage or statistical gates require review."
        )
    else:
        st.info(
            "⚪ LATEST INDEX: AUDIT STATUS UNAVAILABLE."
        )

    st.markdown("#### Latest Audit Record")

    if latest_audit:
        audit_display = {
            k: v
            for k, v in latest_audit.items()
            if k != "_date"
        }

        st.json(audit_display)

    else:
        st.warning(
            "No automated audit artifact was found."
        )

    st.divider()

    # --------------------------------------------------------
    # Coverage gate
    # --------------------------------------------------------

    st.markdown(
        "#### Coverage Gate"
    )

    if not coverage_data.empty:
        coverage_display = coverage_data.copy()

        date_col = (
            "collection_date"
            if "collection_date"
            in coverage_display.columns
            else None
        )

        if date_col:
            coverage_display[date_col] = pd.to_datetime(
                coverage_display[date_col],
                errors="coerce",
            )

        st.dataframe(
            coverage_display.tail(30),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "No real coverage report found."
        )

    st.divider()

    # --------------------------------------------------------
    # Actual processing architecture
    # --------------------------------------------------------

    st.markdown(
        "#### Automated Statistical Pipeline"
    )

    pipeline_stages = [
        (
            "01",
            "Raw Collection",
            "Source-specific collectors acquire airfare observations.",
            "Collection service",
        ),
        (
            "02",
            "Raw Preservation",
            "Raw payloads are retained with provenance and hashes.",
            "Implemented",
        ),
        (
            "03",
            "Normalization",
            "Source records are mapped to the canonical airfare schema.",
            "Implemented",
        ),
        (
            "04",
            "Validation",
            "Schema, fare, route, date and structural rules are checked.",
            "Implemented",
        ),
        (
            "05",
            "Deduplication",
            "Repeated business observations are collapsed before indexing.",
            "Implemented",
        ),
        (
            "06",
            "Representative Fare",
            "Median fare is calculated within route × lead-time × date strata.",
            "Implemented",
        ),
        (
            "07",
            "Index Generation",
            "Stratum → route → national index is generated.",
            "Implemented",
        ),
        (
            "08",
            "Coverage Gate",
            "Incomplete route × lead-time dates are held from publication.",
            "Implemented",
        ),
        (
            "09",
            "Statistical Audit",
            "Independent audit checks determine PUBLISHABLE vs HOLD.",
            "Implemented",
        ),
        (
            "10",
            "Dashboard",
            "Audited statistical artifacts are exposed for monitoring.",
            "Current layer",
        ),
    ]

    for (
        number,
        stage,
        description,
        status,
    ) in pipeline_stages:

        p1, p2, p3 = st.columns(
            [0.55, 2.8, 1.4]
        )

        p1.markdown(
            f"**{number}**"
        )

        p2.markdown(
            f"**{stage}**  \n"
            f"<span style='opacity:.68'>{description}</span>",
            unsafe_allow_html=True,
        )

        if status == "Implemented":
            p3.success(
                status
            )
        elif status == "Current layer":
            p3.info(
                status
            )
        else:
            p3.warning(
                status
            )

    st.divider()

    # --------------------------------------------------------
    # Real pipeline provenance
    # --------------------------------------------------------

    st.markdown(
        "#### Pipeline Provenance"
    )

    if pipeline_report:
        report_keys = [
            "input_rows",
            "normalized_rows",
            "validated_rows",
            "deduplicated_rows",
            "clean_rows",
            "removed_rows",
            "retention_rate",
        ]

        provenance_rows = []

        for key in report_keys:
            if key in pipeline_report:
                provenance_rows.append(
                    [
                        key.replace("_", " ").title(),
                        pipeline_report[key],
                    ]
                )

        if provenance_rows:
            st.dataframe(
                pd.DataFrame(
                    provenance_rows,
                    columns=[
                        "Pipeline Metric",
                        "Value",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.json(
                pipeline_report
            )

    else:
        st.info(
            "Pipeline report artifact not found."
        )

    st.divider()

    # --------------------------------------------------------
    # Retry architecture — configuration only
    # --------------------------------------------------------

    st.markdown(
        "#### Resilience Policy"
    )

    resilience = pd.DataFrame(
        [
            [
                "Timeout",
                "Transient",
                "Bounded retry",
            ],
            [
                "Connection failure",
                "Transient",
                "Bounded retry",
            ],
            [
                "Rate limit",
                "Transient",
                "Respect rate limit / retry-after",
            ],
            [
                "Upstream 5xx",
                "Transient",
                "Retry then mark failed",
            ],
            [
                "Authentication / configuration",
                "Permanent",
                "Stop retrying + alert",
            ],
        ],
        columns=[
            "Failure",
            "Class",
            "Action",
        ],
    )

    st.dataframe(
        resilience,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "These are configured resilience rules. They are not presented "
        "as evidence that a retry event occurred in the current dataset."
    )


# ============================================================
# METHODOLOGY
# ============================================================

with pages[8]:
    st.subheader(
        "Methodology & Statistical Transparency"
    )

    st.markdown(
        '<div class="section-note">'
        'Current engineering specification for the prototype index. '
        'This is not an official MoSPI, CPI or DGCA methodology.'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        "#### Measurement Pipeline"
    )

    st.markdown(
        """
        <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 18px 0;">
            <div class="status-chip status-neutral"><b>01</b>&nbsp; Raw collection</div>
            <div>→</div>
            <div class="status-chip status-neutral"><b>02</b>&nbsp; Preservation</div>
            <div>→</div>
            <div class="status-chip status-neutral"><b>03</b>&nbsp; Normalization</div>
            <div>→</div>
            <div class="status-chip status-good"><b>04</b>&nbsp; Validation</div>
            <div>→</div>
            <div class="status-chip status-good"><b>05</b>&nbsp; Deduplication</div>
            <div>→</div>
            <div class="status-chip status-good"><b>06</b>&nbsp; Representative fare</div>
            <div>→</div>
            <div class="status-chip status-good"><b>07</b>&nbsp; Route index</div>
            <div>→</div>
            <div class="status-chip status-good"><b>08</b>&nbsp; National index</div>
            <div>→</div>
            <div class="status-chip status-good"><b>09</b>&nbsp; Audit gate</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "#### Current Engine Configuration"
    )

    config_rows = [
        [
            "Index base",
            metadata_value(
                "index_base",
                "base_value",
                default=100,
            ),
        ],
        [
            "Base date",
            metadata_value(
                "base_date",
                default="2026-09-04",
            ),
        ],
        [
            "Representative fare",
            metadata_value(
                "representative_fare_method",
                default="median",
            ),
        ],
        [
            "Route weighting",
            metadata_value(
                "route_weighting",
                default="equal",
            ),
        ],
        [
            "Lead-time weighting",
            metadata_value(
                "lead_time_weighting",
                default="equal",
            ),
        ],
        [
            "Official weights used",
            metadata_value(
                "official_weights_used",
                default=False,
            ),
        ],
        [
            "Coverage rule",
            "Complete route × lead-time coverage",
        ],
    ]

    st.dataframe(
        pd.DataFrame(
            config_rows,
            columns=[
                "Parameter",
                "Current Setting",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.markdown(
        "#### Configured Route Universe"
    )

    if expected_routes:
        route_config = pd.DataFrame(
            {
                "Route": expected_routes,
                "Prototype Weight": [
                    1 / len(expected_routes)
                    for _ in expected_routes
                ],
            }
        )

        route_config[
            "Prototype Weight (%)"
        ] = (
            route_config["Prototype Weight"]
            * 100
        )

        st.dataframe(
            route_config[
                [
                    "Route",
                    "Prototype Weight (%)",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.warning(
        "The route weights shown above are equal prototype weights. "
        "They are NOT official CPI, DGCA or MoSPI weights."
    )

    st.divider()

    st.markdown(
        "#### Statistical Safeguards"
    )

    safeguards = [
        (
            "Schema validation",
            "Required fields and expected structure are checked.",
        ),
        (
            "Fare validity",
            "Invalid or non-positive fares are excluded from the analytical layer.",
        ),
        (
            "Duplicate detection",
            "Repeated business observations are identified before indexing.",
        ),
        (
            "Date consistency",
            "Collection date, travel date and advance days are checked.",
        ),
        (
            "Median estimator",
            "Median is used as a robust representative fare.",
        ),
        (
            "Coverage gate",
            "Incomplete route × lead-time dates are held rather than silently published.",
        ),
        (
            "Contribution reconciliation",
            "Component contributions are reconciled against national movement.",
        ),
        (
            "Automated audit",
            "Publication status is determined by explicit statistical gates.",
        ),
    ]

    for title, description in safeguards:
        st.markdown(
            f"""
            <div style="padding:.7rem .8rem;
                        border-bottom:1px solid rgba(128,128,128,.15);">
                <b>✓ {title}</b><br>
                <span style="opacity:.72;">{description}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    left, right = st.columns(2)

    with right:
        st.markdown(
            "#### This Prototype IS NOT"
        )

        st.warning(
            "An official CPI component, official DGCA index, or "
            "official MoSPI statistical series."
        )

    st.divider()

    st.markdown(
        "#### Production Readiness"
    )

    readiness = pd.DataFrame(
        [
            [
                "Raw preservation",
                "Implemented",
            ],
            [
                "Source adapters",
                "Implemented",
            ],
            [
                "Normalization",
                "Implemented",
            ],
            [
                "Validation",
                "Implemented",
            ],
            [
                "Deduplication",
                "Implemented",
            ],
            [
                "Statistical index",
                "Implemented",
            ],
            [
                "Coverage gate",
                "Implemented",
            ],
            [
                "Automated audit",
                "Implemented",
            ],
            [
                "Live collection orchestration",
                "Next integration",
            ],
            [
                "Authoritative weighting",
                "Pending validation",
            ],
            [
                "Historical benchmark backtesting",
                "Next statistical validation",
            ],
        ],
        columns=[
            "Capability",
            "Status",
        ],
    )

    st.dataframe(
        readiness,
        use_container_width=True,
        hide_index=True,
    )