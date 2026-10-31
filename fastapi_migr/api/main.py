import json
import logging
import os
import sys
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Optional

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

MIGRATION_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MIGRATION_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------
# Existing AirFareX data layer
# ---------------------------------------------------------

from dashboard import observation_store as obs
from dashboard import data_loader as loader
from dashboard import charts
from dashboard import metrics

# Re-enable logging
logging.disable(logging.NOTSET)

# ---------------------------------------------------------
# CRITICAL: Reset Plotly template
# Streamlit's import sets pio.templates.default = "streamlit"
# which uses placeholder colors (#000001–#000010). Streamlit's
# own React frontend replaces them at render time, but we
# serve vanilla Plotly.js, so we must reset to a real template.
# ---------------------------------------------------------
import plotly.io as pio
pio.templates.default = "plotly_white"

# Vibrant Streamlit-brand color palette (light-theme categorical)
_ST_COLORS = [
    "#0068c9",  # Streamlit Blue
    "#83c9ff",  # Sky Blue
    "#ff2b2b",  # Red
    "#ffabab",  # Soft Red
    "#29b09d",  # Teal
    "#7defa1",  # Mint
    "#ff8700",  # Orange
    "#ffd16a",  # Amber
    "#6d3fc0",  # Purple
    "#d5dae5",  # Slate
]

_PLOTLY_COLORS = [
    "#636efa", "#EF553B", "#00cc96", "#ab63fa", "#FFA15A",
    "#19d3f3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
]

_RICH_ROUTE_COLORS = [
    "#0068c9", "#ff2b2b", "#29b09d", "#ff8700", "#6d3fc0",
    "#83c9ff", "#ffabab", "#7defa1", "#ffd16a", "#d5dae5",
    "#EF553B", "#00cc96", "#ab63fa", "#FFA15A", "#19d3f3",
    "#FF6692", "#B6E880", "#FF97FF", "#FECB52", "#636efa",
]

# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="AirFareX API",
    description="FastAPI backend for the AirFareX real-data statistical operations dashboard.",
    version="1.0.0",
)


# ---------------------------------------------------------
# Serialization and formatting helpers
# ---------------------------------------------------------

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, date)):
            return str(obj)[:10]
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return None if np.isnan(obj) else float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if pd.isna(obj):
            return None
        return super().default(obj)


def json_safe(val: Any) -> Any:
    """Recursively convert NumPy/Pandas objects to JSON-safe Python types."""
    if isinstance(val, (pd.Timestamp, date)):
        return str(val)[:10]
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        return None if np.isnan(val) else float(val)
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return None
    if isinstance(val, dict):
        return {k: json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [json_safe(v) for v in val]
    if pd.isna(val):
        return None
    return val


def dataframe_records(df: Optional[pd.DataFrame]) -> list[dict]:
    """Convert a Pandas DataFrame into JSON-safe records with proper null handling."""
    if df is None or df.empty:
        return []
    records = df.replace({np.nan: None}).to_dict(orient="records")
    return json_safe(records)


def filter_arguments(
    start_date: Optional[date],
    end_date: Optional[date],
    routes: Optional[list[str]],
    airlines: Optional[list[str]],
    sources: Optional[list[str]],
):
    return {
        "start_date": start_date,
        "end_date": end_date,
        "routes": routes,
        "airlines": airlines,
        "sources": sources,
    }


# ---------------------------------------------------------
# Domain calculations matching dashboard/app.py exactly
# ---------------------------------------------------------

_HIDE_DATES = {
    pd.Timestamp("2026-09-02").date(),
    pd.Timestamp("2026-09-03").date(),
}


def _hide_incomplete_dates(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty or "collection_date" not in df.columns:
        return df if df is not None else pd.DataFrame()
    dates = pd.to_datetime(df["collection_date"], errors="coerce")
    return df[~dates.dt.date.isin(_HIDE_DATES)].copy()


def filter_dates(
    df: Optional[pd.DataFrame],
    start,
    end,
    column="collection_date",
) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return df if df is not None else pd.DataFrame()
    out = df.copy()
    values = pd.to_datetime(out[column], errors="coerce")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return out.loc[(values >= start_ts) & (values <= end_ts)].copy()


def safe_pct_change(values: pd.Series, periods: int = 1) -> Optional[float]:
    s = pd.to_numeric(values, errors="coerce").dropna()
    if len(s) <= periods:
        return None
    previous = float(s.iloc[-1 - periods])
    current = float(s.iloc[-1])
    if previous == 0:
        return None
    return float((current / previous - 1) * 100)


def format_change(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:+.2f}%"


def _formal_display_label(value: Any) -> str:
    if value is None:
        return ""
    value = str(value)
    special = {
        "collection_date": "Collection Date",
        "collection_timestamp": "Collection Timestamp",
        "overall_airfare_index": "Overall Airfare Index",
        "daily_change_pct": "Daily Change (%)",
        "coverage_status": "Coverage Status",
        "publication_status": "Publication Status",
        "route_index": "Route Index",
        "advance_days": "Advance Days",
        "airfare_index": "Airfare Index",
        "observed_days": "Observed Days",
        "observations": "Observations",
        "median_fare": "Median Fare",
        "mean_fare": "Mean Fare",
        "minimum_fare": "Minimum Fare",
        "maximum_fare": "Maximum Fare",
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
        "total_fare": "Total Fare",
        "base_fare": "Base Fare",
        "taxes": "Taxes",
        "fees": "Fees",
        "departure_time": "Departure Time",
        "flight_number": "Flight Number",
        "airline": "Airline",
        "anomaly_flag": "Anomaly Flag",
        "week": "Week",
        "month": "Month",
        "share_pct": "Share (%)",
    }
    if value in special:
        return special[value]
    return value.replace("_", " ").title()


def _formal_route_label(value: Any) -> str:
    if value is None:
        return ""
    value = str(value)
    if "_" in value:
        parts = [p.strip() for p in value.split("_")]
        if len(parts) == 2 and all(parts):
            return f"{parts[0].upper()}–{parts[1].upper()}"
    return value


def weekly_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "overall_airfare_index" not in df.columns:
        return pd.DataFrame(columns=["week", "airfare_index"])
    out = df.copy()
    out["collection_date"] = pd.to_datetime(out["collection_date"], errors="coerce")
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
    out["collection_date"] = pd.to_datetime(out["collection_date"], errors="coerce")
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
        return pd.DataFrame(columns=["route", "change_pct", "latest_index", "observed_days"])
    d = route_df.copy()
    d["collection_date"] = pd.to_datetime(d["collection_date"], errors="coerce")
    d["route_index"] = pd.to_numeric(d["route_index"], errors="coerce")
    d = d.dropna(subset=["route", "collection_date", "route_index"])
    rows = []
    for route, group in d.sort_values("collection_date").groupby("route"):
        group = group.drop_duplicates("collection_date", keep="last")
        if len(group) < 2:
            continue
        first = float(group["route_index"].iloc[0])
        last = float(group["route_index"].iloc[-1])
        change = ((last / first) - 1) * 100 if first else None
        rows.append({
            "route": route,
            "change_pct": change,
            "latest_index": last,
            "observed_days": len(group),
        })
    if not rows:
        return pd.DataFrame(columns=["route", "change_pct", "latest_index", "observed_days"])
    return pd.DataFrame(rows).sort_values("change_pct", ascending=False)


def audit_latest_status(audit_data: pd.DataFrame) -> dict:
    if audit_data.empty:
        return {}
    out = audit_data.copy()
    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(out["collection_date"], errors="coerce")
    out = out.sort_values("collection_date")
    if "publication_status" in out.columns:
        publishable = out[out["publication_status"].astype(str).str.strip().str.upper().eq("PUBLISHABLE")]
        if not publishable.empty:
            return publishable.iloc[-1].to_dict()
    return out.iloc[-1].to_dict()


def bool_value(row: dict, key: str) -> Optional[bool]:
    if key not in row:
        return None
    val = row[key]
    if pd.isna(val):
        return None
    if isinstance(val, bool):
        return val
    norm = str(val).strip().lower()
    if norm in {"true", "1", "yes", "pass", "passed"}:
        return True
    if norm in {"false", "0", "no", "fail", "failed"}:
        return False
    return None


def serialize_fig(fig) -> Optional[dict]:
    """Serialize Plotly figure to a JSON-safe dict."""
    if fig is None:
        return None
    return json.loads(fig.to_json())


# ---------------------------------------------------------
# Data Cache for Fast Repeated Serving
# ---------------------------------------------------------

class DashboardDataCache:
    def __init__(self):
        self.daily_index = None
        self.route_indices = None
        self.advance_indices = None
        self.audit_data = None
        self.coverage_data = None
        self.metadata = None
        self.obs_metadata = None
        self.obs_dimensions = None

    def refresh(self):
        self.daily_index = loader.load_daily_index("real")
        self.route_indices = loader.load_route_indices("real")
        self.advance_indices = loader.load_advance_window_indices("real")
        self.audit_data = loader.load_real_audit()
        self.coverage_data = loader.load_real_coverage()
        self.metadata = loader.load_real_metadata()
        self.obs_metadata = obs.observation_metadata()
        self.obs_dimensions = obs.observation_dimensions()

    def get_daily(self):
        if self.daily_index is None:
            self.refresh()
        return self.daily_index.copy()

    def get_routes(self):
        if self.route_indices is None:
            self.refresh()
        return self.route_indices.copy()

    def get_advance(self):
        if self.advance_indices is None:
            self.refresh()
        return self.advance_indices.copy()

    def get_audit(self):
        if self.audit_data is None:
            self.refresh()
        return self.audit_data.copy()

    def get_coverage(self):
        if self.coverage_data is None:
            self.refresh()
        return self.coverage_data.copy()

    def get_metadata(self):
        if self.metadata is None:
            self.refresh()
        return dict(self.metadata)

    def get_obs_metadata(self):
        if self.obs_metadata is None:
            self.refresh()
        return dict(self.obs_metadata)

    def get_obs_dimensions(self):
        if self.obs_dimensions is None:
            self.refresh()
        return dict(self.obs_dimensions)


data_cache = DashboardDataCache()


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "AirFareX API",
        "version": app.version,
    }


# ---------------------------------------------------------
# Overview and filters (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/overview/metadata")
def overview_metadata():
    return data_cache.get_obs_metadata()


@app.get("/api/filters")
def dashboard_filters():
    return data_cache.get_obs_dimensions()


# ---------------------------------------------------------
# Precomputed index artifacts (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/index/daily")
def daily_index():
    return dataframe_records(data_cache.get_daily())


@app.get("/api/index/routes")
def route_indices():
    return dataframe_records(data_cache.get_routes())


@app.get("/api/index/lead-time")
def lead_time_indices():
    return dataframe_records(data_cache.get_advance())


@app.get("/api/index/metadata")
def index_metadata():
    return data_cache.get_metadata()


# ---------------------------------------------------------
# Audit and coverage (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/audit")
def index_audit():
    return dataframe_records(data_cache.get_audit())


@app.get("/api/coverage")
def index_coverage():
    return dataframe_records(data_cache.get_coverage())


# ---------------------------------------------------------
# Raw observations explorer (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/observations")
def observations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    if start_date and end_date and start_date > end_date:
        return {"error": "start_date cannot be later than end_date."}

    total, df = obs.query_observations(
        page=page,
        page_size=page_size,
        **filter_arguments(start_date, end_date, routes, airlines, sources),
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": dataframe_records(df),
    }


# ---------------------------------------------------------
# Filtered analytics (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/analytics/sources")
def source_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    return dataframe_records(
        obs.source_summary(
            **filter_arguments(start_date, end_date, routes, airlines, sources)
        )
    )


@app.get("/api/analytics/quality")
def quality_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    return obs.data_quality_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )


@app.get("/api/analytics/routes")
def route_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    return dataframe_records(
        obs.route_summary(
            **filter_arguments(start_date, end_date, routes, airlines, sources)
        )
    )


@app.get("/api/analytics/lead-time")
def lead_time_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    return dataframe_records(
        obs.lead_time_summary(
            **filter_arguments(start_date, end_date, routes, airlines, sources)
        )
    )


@app.get("/api/analytics/route-lead")
def route_lead_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    return dataframe_records(
        obs.route_lead_summary(
            **filter_arguments(start_date, end_date, routes, airlines, sources)
        )
    )


# ---------------------------------------------------------
# Pipeline provenance report (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/automation/pipeline-report")
def pipeline_provenance():
    report_path = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / "real"
        / "real_pipeline_report.json"
    )

    if not report_path.exists():
        return {
            "available": False,
            "message": "Pipeline report artifact not found.",
        }

    try:
        with report_path.open("r", encoding="utf-8") as file:
            report = json.load(file)

        return {
            "available": True,
            "report": report,
        }
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "message": str(exc),
        }


# ---------------------------------------------------------
# Anomaly detection (Preserving Existing Routes)
# ---------------------------------------------------------

@app.get("/api/analytics/anomalies")
def fare_anomalies():
    from dashboard.observation_store import _connection

    conn = _connection()
    try:
        conn.execute(
            """
            CREATE OR REPLACE TEMP TABLE anomaly_bounds AS
            SELECT
                UPPER(TRIM(origin) || '_' || TRIM(destination)) AS route,
                quantile_cont(TRY_CAST(total_fare AS DOUBLE), 0.25) AS q1,
                quantile_cont(TRY_CAST(total_fare AS DOUBLE), 0.75) AS q3
            FROM observations
            WHERE origin IS NOT NULL
              AND destination IS NOT NULL
              AND total_fare IS NOT NULL
              AND TRY_CAST(total_fare AS DOUBLE) IS NOT NULL
            GROUP BY
                UPPER(TRIM(origin) || '_' || TRIM(destination))
            """
        )

        stats = conn.execute(
            """
            WITH valid AS (
                SELECT
                    total_fare,
                    UPPER(TRIM(origin) || '_' || TRIM(destination)) AS route
                FROM observations
                WHERE origin IS NOT NULL
                  AND destination IS NOT NULL
                  AND total_fare IS NOT NULL
                  AND TRY_CAST(total_fare AS DOUBLE) IS NOT NULL
            )
            SELECT
                COUNT(*) AS records_reviewed,
                SUM(
                    CASE
                        WHEN TRY_CAST(v.total_fare AS DOUBLE)
                             < (b.q1 - 1.5 * (b.q3 - b.q1))
                          OR TRY_CAST(v.total_fare AS DOUBLE)
                             > (b.q3 + 1.5 * (b.q3 - b.q1))
                        THEN 1
                        ELSE 0
                    END
                ) AS anomaly_count
            FROM valid v
            INNER JOIN anomaly_bounds b ON v.route = b.route
            """
        ).fetchone()

        records_reviewed = int(stats[0] or 0)
        anomaly_count = int(stats[1] or 0)
        anomaly_rate = (
            anomaly_count / records_reviewed * 100
            if records_reviewed else 0.0
        )

        flagged = conn.execute(
            """
            SELECT
                o.collection_timestamp,
                o.origin,
                o.destination,
                o.airline,
                o.advance_days,
                o.base_fare,
                o.taxes,
                o.total_fare,
                UPPER(TRIM(o.origin) || '_' || TRIM(o.destination)) AS route,
                TRUE AS anomaly_flag
            FROM observations o
            INNER JOIN anomaly_bounds b
                ON UPPER(TRIM(o.origin) || '_' || TRIM(o.destination)) = b.route
            WHERE o.origin IS NOT NULL
              AND o.destination IS NOT NULL
              AND o.total_fare IS NOT NULL
              AND TRY_CAST(o.total_fare AS DOUBLE) IS NOT NULL
              AND (
                  TRY_CAST(o.total_fare AS DOUBLE)
                      < (b.q1 - 1.5 * (b.q3 - b.q1))
                  OR
                  TRY_CAST(o.total_fare AS DOUBLE)
                      > (b.q3 + 1.5 * (b.q3 - b.q1))
              )
            ORDER BY o.collection_timestamp DESC
            LIMIT 100
            """
        ).fetchdf()

        return {
            "records_reviewed": records_reviewed,
            "anomaly_count": anomaly_count,
            "anomaly_rate": round(anomaly_rate, 4),
            "flagged_records_limit": 100,
            "flagged_records": dataframe_records(flagged),
        }
    finally:
        conn.close()


# =========================================================
# HIGH-SPEED DEDICATED DASHBOARD ENDPOINTS
# =========================================================

@app.get("/api/dashboard/bootstrap")
def dashboard_bootstrap():
    """Initial load metadata for header KPIs, filters, and publication status."""
    daily = data_cache.get_daily()
    audit_data = data_cache.get_audit()
    meta = data_cache.get_metadata()
    obs_meta = data_cache.get_obs_metadata()
    obs_dims = data_cache.get_obs_dimensions()

    latest_audit = audit_latest_status(audit_data)
    publication_status = str(latest_audit.get("publication_status", "UNKNOWN")).strip().upper()

    latest_idx_val = None
    if not daily.empty and "overall_airfare_index" in daily.columns:
        valid_idx = pd.to_numeric(daily["overall_airfare_index"], errors="coerce").dropna()
        if not valid_idx.empty:
            latest_idx_val = round(float(valid_idx.iloc[-1]), 2)

    latest_date_str = None
    if not daily.empty and "collection_date" in daily.columns:
        dates = pd.to_datetime(daily["collection_date"], errors="coerce").dropna()
        if not dates.empty:
            latest_date_str = str(dates.max().date())

    exp_routes = meta.get("expected_routes") or meta.get("route_universe") or []
    if isinstance(exp_routes, str):
        exp_routes = [x.strip() for x in exp_routes.split(",") if x.strip()]
    routes_count = len(exp_routes) if exp_routes else int(obs_meta.get("routes", 0))

    exp_windows = meta.get("advance_windows") or meta.get("expected_advance_windows") or []
    if isinstance(exp_windows, str):
        exp_windows = [x.strip() for x in exp_windows.split(",") if x.strip()]
    windows_count = len(exp_windows) if exp_windows else 5

    # Determine collection date range bounds
    valid_min = obs_meta.get("min_timestamp")
    valid_max = obs_meta.get("max_timestamp")
    min_date = str(pd.Timestamp(valid_min).date()) if valid_min else None
    max_obs_date = pd.Timestamp(valid_max).date() if valid_max else None

    daily_dates = pd.to_datetime(daily["collection_date"], errors="coerce").dropna()
    max_idx_date = daily_dates.max().date() if not daily_dates.empty else None

    if max_obs_date and max_idx_date:
        max_date = str(max(max_obs_date, max_idx_date))
    else:
        max_date = str(max_obs_date or max_idx_date) if (max_obs_date or max_idx_date) else None

    return {
        "headline_index": latest_idx_val,
        "latest_date": latest_date_str,
        "routes_count": routes_count,
        "lead_windows_count": windows_count,
        "publication_status": publication_status,
        "min_date": min_date,
        "max_date": max_date,
        "routes": obs_dims.get("routes", []),
        "airlines": obs_dims.get("airlines", []),
        "sources": obs_dims.get("sources", []),
    }


@app.get("/api/dashboard/overview")
def dashboard_overview(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    """Data for Overview Tab."""
    daily = data_cache.get_daily()
    filtered_daily = _hide_incomplete_dates(daily)
    if start_date and end_date:
        filtered_daily = filter_dates(filtered_daily, start_date, end_date)

    route_idx = data_cache.get_routes()
    filtered_routes = _hide_incomplete_dates(route_idx)
    if start_date and end_date:
        filtered_routes = filter_dates(filtered_routes, start_date, end_date)
    if routes:
        if "route" in filtered_routes.columns:
            filtered_routes = filtered_routes[filtered_routes["route"].isin(routes)]

    adv_idx = data_cache.get_advance()
    filtered_advance = _hide_incomplete_dates(adv_idx)
    if start_date and end_date:
        filtered_advance = filter_dates(filtered_advance, start_date, end_date)
    if routes and "route" in filtered_advance.columns:
        filtered_advance = filtered_advance[filtered_advance["route"].isin(routes)]

    obs_meta = data_cache.get_obs_metadata()

    # 1. KPIs
    current = metrics.latest_index(filtered_daily) if not filtered_daily.empty else None
    previous = metrics.previous_index(filtered_daily) if not filtered_daily.empty else None
    period_change = metrics.index_change_percent(current, previous) if (current is not None and previous is not None) else None

    change_7d = safe_pct_change(filtered_daily["overall_airfare_index"], 7) if not filtered_daily.empty else None
    change_30d = safe_pct_change(filtered_daily["overall_airfare_index"], 30) if not filtered_daily.empty else None

    # Quality calculation
    quality = obs.data_quality_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )
    missing_pct = float(quality.get("missing_fare_pct", 0) or 0)
    dup_pct = float(quality.get("duplicate_pct", 0) or 0)
    quality_score = max(0.0, 100.0 - missing_pct - dup_pct)

    # 2. Main Index Chart
    overall_chart_fig = None
    overall_table = []
    if not filtered_daily.empty and "overall_airfare_index" in filtered_daily.columns:
        c_fig = charts.create_overall_index_chart(filtered_daily)
        c_fig.update_traces(line_color="#0068c9", marker_color="#0068c9")
        c_fig.update_layout(
            height=390,
            margin=dict(l=10, r=15, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=_ST_COLORS,
        )
        overall_chart_fig = serialize_fig(c_fig)

        keep_cols = [c for c in ["collection_date", "overall_airfare_index"] if c in filtered_daily.columns]
        sub = filtered_daily[keep_cols].tail(30).copy()
        if "overall_airfare_index" in sub.columns:
            sub["overall_airfare_index"] = sub["overall_airfare_index"].round(2)
        overall_table = dataframe_records(sub)

    # 3. Route movers
    movers = build_route_movers(filtered_routes)
    movers_chart_fig = None
    movers_table = []
    if not movers.empty:
        top_movers = movers.head(10).sort_values("change_pct").copy()
        top_movers["color"] = top_movers["change_pct"].apply(
            lambda x: "#29b09d" if (x is not None and x >= 0) else "#ff2b2b"
        )
        pulse_fig = px.bar(
            top_movers,
            x="change_pct",
            y="route",
            orientation="h",
            text="change_pct",
            labels={"change_pct": "Period Change (%)", "route": "Route"},
            color="color",
            color_discrete_map="identity",
        )
        pulse_fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        pulse_fig.update_layout(
            height=350,
            margin=dict(l=5, r=35, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
        )
        movers_chart_fig = serialize_fig(pulse_fig)

        t_keep = [c for c in ["route", "latest_index", "change_pct", "observed_days"] if c in top_movers.columns]
        sub_m = top_movers[t_keep].copy()
        if "change_pct" in sub_m.columns:
            sub_m["change_pct"] = sub_m["change_pct"].round(2)
        if "latest_index" in sub_m.columns:
            sub_m["latest_index"] = sub_m["latest_index"].round(2)
        movers_table = dataframe_records(sub_m)

    # 4. Lead time chart
    lead_chart_fig = None
    lead_table = []
    if not filtered_advance.empty and {"collection_date", "airfare_index", "advance_days"}.issubset(filtered_advance.columns):
        l_fig = charts.create_lead_time_chart(filtered_advance)
        l_fig.update_traces(line=dict(width=2))
        # Explicitly remap each advance_days group to vibrant colors
        lead_color_map = {1: "#0068c9", 7: "#ff2b2b", 15: "#29b09d", 30: "#ff8700", 45: "#6d3fc0"}
        for trace in l_fig.data:
            try:
                adv = int(trace.name)
                if adv in lead_color_map:
                    trace.line.color = lead_color_map[adv]
                    trace.marker.color = lead_color_map[adv]
            except (ValueError, AttributeError):
                pass
        l_fig.update_layout(
            height=350,
            margin=dict(l=5, r=15, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=list(lead_color_map.values()),
        )
        lead_chart_fig = serialize_fig(l_fig)

        l_keep = [c for c in ["collection_date", "advance_days", "airfare_index"] if c in filtered_advance.columns]
        sub_l = filtered_advance[l_keep].tail(30).copy()
        if "airfare_index" in sub_l.columns:
            sub_l["airfare_index"] = sub_l["airfare_index"].round(2)
        lead_table = dataframe_records(sub_l)

    # 5. Source coverage
    source_df = obs.source_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )
    source_fig = None
    if not source_df.empty:
        # Source-specific color mapping matching airfarex.in screenshots
        _SOURCE_COLORS = {
            "EaseMyTrip": "#1f77b4",
            "Yatra": "#83c9ff",
            "Cleartrip": "#ff2b2b",
            "Ixigo": "#ff9da6",
            "IndiGo Direct": "#29b09d",
            "MakeMyTrip": "#00cc96",
            "Goibibo": "#ff8700",
            "Air India Direct": "#ffd16a",
            "Akasa Direct": "#6d3fc0",
            "Air India Express Direct": "#aec7e8",
            "SpiceJet Direct": "#7defa1",
        }
        colors = [_SOURCE_COLORS.get(str(s), _ST_COLORS[i % len(_ST_COLORS)])
                  for i, s in enumerate(source_df["source"].tolist())]
        s_fig = px.pie(
            source_df,
            names="source",
            values="observations",
            hole=0.58,
            color_discrete_sequence=colors,
        )
        s_fig.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="%{label}<br>%{value:,} observations<extra></extra>",
        )
        s_fig.update_layout(
            margin=dict(l=10, r=10, t=25, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        source_fig = serialize_fig(s_fig)

    # 6. Quality gauge
    quality_fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=round(quality_score, 2),
            number={"suffix": "%", "font": {"size": 48, "color": "#475569"}},
            title={"text": "Valid observations", "font": {"size": 13, "color": "#657386"}},
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#dfe5ec",
                    "tickfont": {"size": 10, "color": "#657386"},
                },
                "bar": {"color": "#09ab3b", "thickness": 0.72},
                "bgcolor": "#eef2f7",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 100], "color": "#e7edf3"},
                ],
                "threshold": {
                    "line": {"color": "#09ab3b", "width": 3},
                    "thickness": 0.75,
                    "value": quality_score,
                },
            },
        )
    )
    quality_fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=40, b=5),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    quality_chart_fig = serialize_fig(quality_fig)

    quality_breakdown_table = [
        {
            "Metric": "Valid observations",
            "Value": f"{quality_score:.2f}%",
            "Description": "100% minus missing-fare and duplicate rates",
        },
        {
            "Metric": "Missing fare",
            "Value": f"{missing_pct:.2f}%",
            "Description": "Share of observations without a valid fare",
        },
        {
            "Metric": "Duplicate rate",
            "Value": f"{dup_pct:.2f}%",
            "Description": "Share identified as duplicate observations",
        },
    ]

    return {
        "kpis": {
            "current_index": round(current, 2) if current is not None else None,
            "period_change": period_change,
            "previous_index": round(previous, 2) if previous is not None else None,
            "total_observations": obs_meta.get("observations", 0),
            "total_routes": obs_meta.get("routes", 0),
            "airline_count": obs_meta.get("airlines", 0),
            "source_count": obs_meta.get("sources", 0),
            "change_7d": change_7d,
            "change_30d": change_30d,
        },
        "quality": {
            "score": round(quality_score, 1),
            "missing_pct": round(missing_pct, 1),
            "duplicate_pct": round(dup_pct, 1),
            "table": quality_breakdown_table,
            "chart": quality_chart_fig,
        },
        "overall_chart": overall_chart_fig,
        "overall_table": overall_table,
        "route_pulse_chart": movers_chart_fig,
        "route_pulse_table": movers_table,
        "lead_chart": lead_chart_fig,
        "lead_table": lead_table,
        "source_chart": source_fig,
    }


@app.get("/api/dashboard/index-analytics")
def dashboard_index_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Data for Index Analytics Tab."""
    daily = data_cache.get_daily()
    filtered_daily = _hide_incomplete_dates(daily)
    if start_date and end_date:
        filtered_daily = filter_dates(filtered_daily, start_date, end_date)

    if filtered_daily.empty:
        return {"empty": True}

    # Chart
    c_fig = charts.create_overall_index_chart(filtered_daily)
    c_fig.update_traces(line_color="#0068c9", marker_color="#0068c9")
    c_fig.update_layout(
        height=390,
        margin=dict(l=10, r=15, t=15, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=_ST_COLORS,
    )

    keep_cols = [c for c in ["collection_date", "overall_airfare_index"] if c in filtered_daily.columns]
    idx_table = filtered_daily[keep_cols].tail(30).copy()
    if "overall_airfare_index" in idx_table.columns:
        idx_table["overall_airfare_index"] = idx_table["overall_airfare_index"].round(2)

    weekly = weekly_index(filtered_daily).tail(12)
    if "airfare_index" in weekly.columns:
        weekly["airfare_index"] = weekly["airfare_index"].round(2)

    monthly = monthly_index(filtered_daily).tail(12)
    if "airfare_index" in monthly.columns:
        monthly["airfare_index"] = monthly["airfare_index"].round(2)

    # Daily movement audit trail
    movement = filtered_daily.copy()
    movement["collection_date"] = pd.to_datetime(movement["collection_date"], errors="coerce")
    movement["daily_change_pct"] = movement["overall_airfare_index"].pct_change() * 100

    display_cols = [
        c for c in [
            "collection_date",
            "overall_airfare_index",
            "daily_change_pct",
            "status",
            "coverage_status",
            "publication_status",
        ] if c in movement.columns
    ]
    trail = movement[display_cols].tail(60).copy()
    if "overall_airfare_index" in trail.columns:
        trail["overall_airfare_index"] = trail["overall_airfare_index"].round(2)
    if "daily_change_pct" in trail.columns:
        trail["daily_change_pct"] = trail["daily_change_pct"].round(2)

    return {
        "empty": False,
        "chart": serialize_fig(c_fig),
        "index_table": dataframe_records(idx_table),
        "weekly_table": dataframe_records(weekly),
        "monthly_table": dataframe_records(monthly),
        "audit_trail": dataframe_records(trail),
    }


@app.get("/api/dashboard/route-intelligence")
def dashboard_route_intelligence(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    """Data for Route Intelligence Tab."""
    route_idx = data_cache.get_routes()
    filtered_routes = _hide_incomplete_dates(route_idx)
    if start_date and end_date:
        filtered_routes = filter_dates(filtered_routes, start_date, end_date)
    if routes and "route" in filtered_routes.columns:
        filtered_routes = filtered_routes[filtered_routes["route"].isin(routes)]

    if filtered_routes.empty:
        return {"empty": True}

    movers = build_route_movers(filtered_routes)

    kpis = {}
    if not movers.empty:
        strongest = movers.iloc[0]
        weakest = movers.iloc[-1]
        kpis = {
            "routes_analysed": len(movers),
            "largest_increase": f"{_formal_route_label(strongest['route'])} {strongest['change_pct']:+.2f}%",
            "largest_decrease": f"{_formal_route_label(weakest['route'])} {weakest['change_pct']:+.2f}%",
            "median_route_index": round(float(movers["latest_index"].median()), 2),
        }

    # Line chart of route indices
    _route_fig = charts.create_route_index_chart(filtered_routes)
    # Remap each route trace to the rich color palette explicitly
    for i, trace in enumerate(_route_fig.data):
        color = _RICH_ROUTE_COLORS[i % len(_RICH_ROUTE_COLORS)]
        trace.line.color = color
        if hasattr(trace, "marker") and trace.marker is not None:
            trace.marker.color = color
    _route_fig.update_layout(colorway=_RICH_ROUTE_COLORS)
    route_chart_fig = serialize_fig(_route_fig)

    # Route Explorer list
    available_explorer_routes = sorted(
        filtered_routes["route"].dropna().astype(str).unique().tolist()
    )

    # Route movement ranking table
    ranking_table = []
    if not movers.empty:
        ranking = movers.copy()
        ranking["latest_index"] = ranking["latest_index"].round(2)
        ranking["change_pct"] = ranking["change_pct"].round(2)
        ranking_table = dataframe_records(ranking)

    # Route x Lead heatmap
    route_lead_df = obs.route_lead_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )
    heatmap_fig = None
    heatmap_table = []
    if not route_lead_df.empty:
        heatmap_data = (
            route_lead_df.pivot(index="route", columns="advance_days", values="median_fare")
            .sort_index()
        )
        heatmap_data = heatmap_data.reindex(
            columns=[c for c in [1, 7, 15, 30, 45] if c in heatmap_data.columns]
        )

        h_fig = px.imshow(
            heatmap_data,
            text_auto=".0f",
            aspect="auto",
            labels={"x": "Advance Days", "y": "Route", "color": "Median Fare (INR)"},
        )
        h_fig.update_layout(
            height=max(360, 42 * len(heatmap_data) + 120),
            margin=dict(l=10, r=10, t=35, b=10),
        )
        heatmap_fig = serialize_fig(h_fig)
        heatmap_table = dataframe_records(heatmap_data.reset_index())

    # Observed Route Coverage
    coverage_df = obs.route_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )
    coverage_table = []
    if not coverage_df.empty:
        sub_c = coverage_df.copy()
        if "median_fare" in sub_c.columns:
            sub_c["median_fare"] = sub_c["median_fare"].round(2)
        if "mean_fare" in sub_c.columns:
            sub_c["mean_fare"] = sub_c["mean_fare"].round(2)
        coverage_table = dataframe_records(sub_c)

    return {
        "empty": False,
        "kpis": kpis,
        "route_chart": route_chart_fig,
        "explorer_routes": available_explorer_routes,
        "ranking_table": ranking_table,
        "heatmap_chart": heatmap_fig,
        "heatmap_table": heatmap_table,
        "coverage_table": coverage_table,
    }


@app.get("/api/dashboard/route-explorer")
def dashboard_route_explorer(
    route: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Filter records for Route Explorer table."""
    route_idx = data_cache.get_routes()
    filtered = _hide_incomplete_dates(route_idx)
    if start_date and end_date:
        filtered = filter_dates(filtered, start_date, end_date)

    if route and route != "All Routes" and "route" in filtered.columns:
        filtered = filtered[filtered["route"].astype(str).eq(route)]

    keep = [c for c in ["collection_date", "route", "airfare_index"] if c in filtered.columns]
    sub = filtered[keep].copy() if keep else filtered.copy()
    if "collection_date" in sub.columns:
        sub["collection_date"] = pd.to_datetime(sub["collection_date"], errors="coerce")
        sub = sub.sort_values("collection_date", ascending=False)
    if "airfare_index" in sub.columns:
        sub["airfare_index"] = sub["airfare_index"].round(2)

    return {
        "total": len(sub),
        "items": dataframe_records(sub),
    }


@app.get("/api/dashboard/lead-time")
def dashboard_lead_time(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    """Data for Lead-Time Analysis Tab."""
    adv_idx = data_cache.get_advance()
    filtered_advance = _hide_incomplete_dates(adv_idx)
    if start_date and end_date:
        filtered_advance = filter_dates(filtered_advance, start_date, end_date)
    if routes and "route" in filtered_advance.columns:
        filtered_advance = filtered_advance[filtered_advance["route"].isin(routes)]

    if filtered_advance.empty:
        return {"empty": True}

    # Chart
    l_fig = charts.create_lead_time_chart(filtered_advance)
    # Assign explicit Streamlit-brand colors per advance window
    _lead_color_map = {1: "#0068c9", 7: "#ff2b2b", 15: "#29b09d", 30: "#ff8700", 45: "#6d3fc0"}
    for trace in l_fig.data:
        try:
            adv = int(trace.name)
            if adv in _lead_color_map:
                trace.line.color = _lead_color_map[adv]
                if hasattr(trace, "marker"):
                    trace.marker.color = _lead_color_map[adv]
        except (ValueError, AttributeError):
            pass
    l_fig.update_layout(
        height=390,
        margin=dict(l=10, r=15, t=15, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(_lead_color_map.values()),
    )

    keep = [c for c in ["collection_date", "advance_days", "airfare_index"] if c in filtered_advance.columns]
    chart_table = filtered_advance.tail(50)[keep].copy()
    if "airfare_index" in chart_table.columns:
        chart_table["airfare_index"] = chart_table["airfare_index"].round(2)

    # Statistical snapshot
    snapshot_table = []
    if {"advance_days", "airfare_index"}.issubset(filtered_advance.columns):
        snap = filtered_advance.copy()
        if "collection_date" in snap.columns:
            snap["collection_date"] = pd.to_datetime(snap["collection_date"], errors="coerce")
            latest_d = snap["collection_date"].max()
            snap = snap[snap["collection_date"] == latest_d]
        snap["advance_days"] = pd.to_numeric(snap["advance_days"], errors="coerce")
        snap["airfare_index"] = pd.to_numeric(snap["airfare_index"], errors="coerce")
        snap = snap.dropna(subset=["advance_days", "airfare_index"])
        snap = snap.groupby("advance_days", as_index=False)["airfare_index"].median().sort_values("advance_days")
        if not snap.empty:
            snap["airfare_index"] = snap["airfare_index"].round(2)
            snapshot_table = dataframe_records(snap.rename(columns={"airfare_index": "median_index"}))

    # Observed Fare Distribution by Lead Time
    fare_summary_df = obs.lead_time_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )
    distribution_table = []
    if not fare_summary_df.empty:
        sub_d = fare_summary_df.copy()
        for col in ["median_fare", "mean_fare", "min_fare", "max_fare"]:
            if col in sub_d.columns:
                sub_d[col] = sub_d[col].round(2)
        distribution_table = dataframe_records(sub_d)

    # Lead-Time Fare Explorer options
    adv_options = sorted(filtered_advance["advance_days"].dropna().astype(int).unique().tolist())
    route_options = data_cache.get_obs_dimensions().get("routes", [])

    return {
        "empty": False,
        "chart": serialize_fig(l_fig),
        "chart_table": dataframe_records(chart_table),
        "snapshot_table": snapshot_table,
        "distribution_table": distribution_table,
        "lead_options": adv_options,
        "route_options": route_options,
    }


@app.get("/api/dashboard/lead-time-explorer")
def dashboard_lead_time_explorer(
    lead_time: Optional[str] = None,
    route: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """DuckDB aggregation for Lead-Time Fare Data Explorer table."""
    from dashboard.observation_store import _connection

    conn = _connection()
    try:
        where_parts = [
            "origin IS NOT NULL",
            "destination IS NOT NULL",
            "total_fare IS NOT NULL",
            "TRY_CAST(total_fare AS DOUBLE) IS NOT NULL",
        ]

        if start_date:
            where_parts.append(f"TRY_CAST(collection_timestamp AS TIMESTAMP) >= '{start_date} 00:00:00'")
        if end_date:
            where_parts.append(f"TRY_CAST(collection_timestamp AS TIMESTAMP) <= '{end_date} 23:59:59'")

        if lead_time and lead_time != "All Lead Times":
            days = lead_time.replace("T+", "").strip()
            where_parts.append(f"TRY_CAST(advance_days AS INTEGER) = {int(days)}")

        if route and route != "All Routes":
            clean_route = route.replace("–", "_").replace("-", "_").strip()
            where_parts.append(f"UPPER(TRIM(origin) || '_' || TRIM(destination)) = '{clean_route}'")

        sql = f"""
            SELECT
                strftime(TRY_CAST(collection_timestamp AS TIMESTAMP), '%Y-%m-%d') AS collection_date,
                UPPER(TRIM(origin) || '_' || TRIM(destination)) AS route,
                TRY_CAST(advance_days AS INTEGER) AS advance_days,
                COUNT(*) AS observations,
                ROUND(median(TRY_CAST(total_fare AS DOUBLE)), 2) AS median_fare,
                ROUND(avg(TRY_CAST(total_fare AS DOUBLE)), 2) AS mean_fare,
                ROUND(min(TRY_CAST(total_fare AS DOUBLE)), 2) AS minimum_fare,
                ROUND(max(TRY_CAST(total_fare AS DOUBLE)), 2) AS maximum_fare
            FROM observations
            WHERE {' AND '.join(where_parts)}
            GROUP BY 1, 2, 3
            ORDER BY 1 DESC, 2, 3
            LIMIT 500
        """

        df = conn.execute(sql).fetchdf()
        return {
            "total": len(df),
            "items": dataframe_records(df),
        }
    finally:
        conn.close()


@app.get("/api/dashboard/data-quality")
def dashboard_data_quality(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    """Data for Data Quality Tab."""
    quality = obs.data_quality_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )

    total_obs = int(quality.get("total_observations", 0) or 0)
    missing_pct = float(quality.get("missing_fare_pct", 0) or 0)
    dup_pct = float(quality.get("duplicate_pct", 0) or 0)
    quality_score = max(0.0, min(100.0, 100.0 - missing_pct - dup_pct))

    status_label = "Healthy" if quality_score >= 99 else "Review" if quality_score >= 97 else "Attention"

    # Anomalies
    anomalies_data = fare_anomalies()

    return {
        "kpis": {
            "total_observations": total_obs,
            "missing_fare_pct": round(missing_pct, 2),
            "duplicate_pct": round(dup_pct, 2),
            "quality_score": round(quality_score, 1),
            "status": status_label,
        },
        "anomalies": {
            "count": anomalies_data.get("anomaly_count", 0),
            "rate": anomalies_data.get("anomaly_rate", 0.0),
            "reviewed": anomalies_data.get("records_reviewed", 0),
            "flagged": anomalies_data.get("flagged_records", []),
        },
    }


@app.get("/api/dashboard/source-health")
def dashboard_source_health(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    routes: Optional[list[str]] = Query(None),
    airlines: Optional[list[str]] = Query(None),
    sources: Optional[list[str]] = Query(None),
):
    """Data for Source Health Tab."""
    source_df = obs.source_summary(
        **filter_arguments(start_date, end_date, routes, airlines, sources)
    )

    if source_df.empty:
        return {"empty": True}

    source_df["observations"] = pd.to_numeric(source_df["observations"], errors="coerce").fillna(0)
    observed_sources = int(source_df["source"].nunique())

    dimensions = data_cache.get_obs_dimensions()
    configured_sources = len(dimensions.get("sources", [])) or observed_sources

    total_obs = int(source_df["observations"].sum())
    if total_obs > 0:
        source_df["share_pct"] = source_df["observations"] / total_obs * 100
    else:
        source_df["share_pct"] = 0.0

    concentration = float(source_df["share_pct"].max()) if not source_df.empty else 0.0

    obs_meta = data_cache.get_obs_metadata()
    earliest_ts = obs_meta.get("min_timestamp")
    latest_ts = obs_meta.get("max_timestamp")

    # Chart
    source_chart_data = source_df[["source", "observations", "share_pct"]].copy()
    source_fig = px.bar(
        source_chart_data.sort_values("observations"),
        x="observations",
        y="source",
        orientation="h",
        text="share_pct",
        labels={"observations": "Observations", "source": "Source"},
        color_discrete_sequence=["#0068c9"],
    )
    source_fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    source_fig.update_layout(
        height=370,
        margin=dict(l=10, r=35, t=25, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=_ST_COLORS,
    )

    coverage_table = source_chart_data.copy()
    coverage_table["share_pct"] = coverage_table["share_pct"].round(2)

    return {
        "empty": False,
        "kpis": {
            "total_observations": total_obs,
            "observed_sources": observed_sources,
            "configured_sources": configured_sources,
            "source_coverage_pct": round(observed_sources / configured_sources * 100, 1) if configured_sources else None,
            "largest_source_share": round(concentration, 1),
            "earliest_date": str(earliest_ts)[:10] if earliest_ts else "—",
            "latest_date": str(latest_ts)[:10] if latest_ts else "—",
        },
        "chart": serialize_fig(source_fig),
        "coverage_table": dataframe_records(coverage_table),
    }


@app.get("/api/dashboard/automation")
def dashboard_automation():
    """Data for Automation Control Center Tab."""
    audit_data = data_cache.get_audit()
    coverage_data = data_cache.get_coverage()
    pipeline_report_res = pipeline_provenance()

    latest_audit = audit_latest_status(audit_data)
    pub_status = str(latest_audit.get("publication_status", "UNKNOWN")).strip().upper()

    audit_checks = [
        {"label": "Structural validation", "key": "structural_validation_pass"},
        {"label": "Duplicate QC", "key": "duplicate_qc_pass"},
        {"label": "Representative fares", "key": "representative_fares_pass"},
        {"label": "Index calculation", "key": "index_calculation_pass"},
        {"label": "Contribution reconciliation", "key": "contribution_reconciliation_pass"},
        {"label": "Base-period check", "key": "base_period_pass"},
    ]

    for check in audit_checks:
        val = bool_value(latest_audit, check["key"])
        check["status"] = "PASS" if val is True else "FAIL" if val is False else "NOT AVAILABLE"

    failed_checks = latest_audit.get("failed_checks")
    failed_display = str(failed_checks).replace("_", " ").title() if failed_checks else None

    warnings_val = latest_audit.get("warnings")
    warnings_display = str(warnings_val).replace("_", " ").title() if warnings_val else None

    # Coverage table
    coverage_display = []
    if not coverage_data.empty:
        c_sub = coverage_data.tail(30).copy()
        coverage_display = dataframe_records(c_sub)

    # Clean audit dict with title case keys
    audit_clean = {
        str(k).replace("_", " ").strip().title(): json_safe(v)
        for k, v in latest_audit.items()
        if k != "_date"
    }

    # Pipeline stages
    pipeline_stages = [
        {"number": "01", "stage": "Raw Collection", "description": "Source-specific collectors acquire airfare observations.", "status": "Collection service"},
        {"number": "02", "stage": "Raw Preservation", "description": "Raw payloads are retained with provenance and hashes.", "status": "Implemented"},
        {"number": "03", "stage": "Normalization", "description": "Source records are mapped to the canonical airfare schema.", "status": "Implemented"},
        {"number": "04", "stage": "Validation", "description": "Schema, fare, route, date and structural rules are checked.", "status": "Implemented"},
        {"number": "05", "stage": "Deduplication", "description": "Repeated business observations are collapsed before indexing.", "status": "Implemented"},
        {"number": "06", "stage": "Representative Fare", "description": "Median fare is calculated within route × lead-time × date strata.", "status": "Implemented"},
        {"number": "07", "stage": "Index Generation", "description": "Stratum → route → national index is generated.", "status": "Implemented"},
        {"number": "08", "stage": "Coverage Gate", "description": "Incomplete route × lead-time dates are held from publication.", "status": "Implemented"},
        {"number": "09", "stage": "Statistical Audit", "description": "Independent audit checks determine PUBLISHABLE vs HOLD.", "status": "Implemented"},
        {"number": "10", "stage": "Dashboard", "description": "Audited statistical artifacts are exposed for monitoring.", "status": "Current layer"},
    ]

    # Pipeline provenance rows
    provenance_rows = []
    if pipeline_report_res.get("available") and "report" in pipeline_report_res:
        rep = pipeline_report_res["report"]
        report_keys = [
            "input_rows",
            "normalized_rows",
            "validated_rows",
            "deduplicated_rows",
            "clean_rows",
            "removed_rows",
            "retention_rate",
        ]
        for k in report_keys:
            if k in rep:
                provenance_rows.append({"metric": k.replace("_", " ").title(), "value": rep[k]})

    # Resilience rules
    resilience_policy = [
        {"failure": "Timeout", "class": "Transient", "action": "Bounded retry"},
        {"failure": "Connection failure", "class": "Transient", "action": "Bounded retry"},
        {"failure": "Rate limit", "class": "Transient", "action": "Respect rate limit / retry-after"},
        {"failure": "Upstream 5xx", "class": "Transient", "action": "Retry then mark failed"},
        {"failure": "Authentication / configuration", "class": "Permanent", "action": "Stop retrying + alert"},
    ]

    return {
        "publication_status": pub_status,
        "gates": audit_checks,
        "failed_checks": failed_display,
        "warnings": warnings_display,
        "latest_audit": audit_clean,
        "coverage_table": coverage_display,
        "pipeline_stages": pipeline_stages,
        "provenance_table": provenance_rows,
        "resilience_policy": resilience_policy,
    }


@app.post("/api/dashboard/refresh")
def dashboard_refresh():
    """Clear memory caches and reload artifacts."""
    data_cache.refresh()
    return {"status": "refreshed"}


# ---------------------------------------------------------
# Standalone dashboard frontend static mount
# ---------------------------------------------------------

FRONTEND_ROOT = MIGRATION_ROOT / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_ROOT),
    name="static",
)


@app.get("/", include_in_schema=False)
def dashboard_home():
    return FileResponse(FRONTEND_ROOT / "index.html")
