"""Optional FastAPI bridge for the HTML frontend.

Place this file in the AirFareX project root (beside the existing app.py and
 dashboard/ package). It imports existing data/statistics modules; it does not
 import or edit the Streamlit app and does not implement a replacement index.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from functools import lru_cache
from threading import RLock
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="AirFareX existing-data bridge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _records(df: Any, limit: int = 500) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    frame = df.head(limit).copy()
    frame = frame.astype(object).where(pd.notna(frame), None)
    return frame.to_dict(orient="records")


def _figure(fig: Any) -> dict | None:
    if fig is None:
        return None
    try:
        return json.loads(fig.to_json())
    except Exception:
        return None


@lru_cache(maxsize=1)
def _load_modules():
    try:
        from dashboard.observation_store import observation_metadata, route_coverage_summary, observation_dimensions, query_observations, source_summary, route_summary, lead_time_summary, route_lead_summary, data_quality_summary
        from dashboard.data_loader import load_clean_data, load_raw_observations, load_daily_index, load_route_indices, load_advance_window_indices
        from dashboard.metrics import latest_index, previous_index, index_change_percent, latest_collection_date, observation_count, route_count, airline_count, source_count
        from dashboard.charts import create_overall_index_chart, create_route_index_chart, create_lead_time_chart
        from dashboard.monitoring import calculate_data_quality, calculate_source_coverage, calculate_route_coverage, detect_fare_anomalies
        return locals()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Existing AirFareX dashboard modules could not be imported: {exc}. Run this bridge from the project root with its existing dependencies installed.")


@app.get('/api/health')
def health():
    return {'service':'AirFareX HTML bridge','statistical_logic':'existing project modules only'}


@app.get('/api/metadata')
def metadata():
    m = _load_modules()
    try:
        meta = m['observation_metadata']()
        dims = m['observation_dimensions']()
        return {'min_date': str(pd.to_datetime(meta.get('min_timestamp'), errors='coerce').date()) if meta.get('min_timestamp') else None,
                'max_date': str(pd.to_datetime(meta.get('max_timestamp'), errors='coerce').date()) if meta.get('max_timestamp') else None,
                'dimensions': {'routes': list(dims.get('routes', [])), 'airlines': list(dims.get('airlines', [])), 'sources': list(dims.get('sources', []))}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Could not read existing observation metadata: {exc}')


@app.post('/api/refresh')
def refresh():
    # Re-read data on the next request. No files are deleted or rewritten here.
    return {'ok': True, 'message': 'Refresh requested; existing source modules will be queried again.'}


@app.post('/api/dashboard')
def dashboard(payload: dict):
    m = _load_modules()
    page = payload.get('page', 'overview')
    filters = payload.get('filters') or {}
    try:
        daily = m['load_daily_index']()
        routes = m['load_route_indices']()
        lead = m['load_advance_window_indices']()
        clean = m['load_clean_data']()
        raw = m['load_raw_observations']()
        # Preserve the uploaded app's rule: date/route/airline/source filters are exploratory only;
        # published index artifacts remain the source of headline index values.
        daily = daily.copy() if isinstance(daily, pd.DataFrame) else pd.DataFrame()
        routes = routes.copy() if isinstance(routes, pd.DataFrame) else pd.DataFrame()
        lead = lead.copy() if isinstance(lead, pd.DataFrame) else pd.DataFrame()
        def date_filter(df):
            if not isinstance(df, pd.DataFrame) or df.empty or 'collection_date' not in df: return df
            out=df.copy(); dates=pd.to_datetime(out['collection_date'],errors='coerce')
            if filters.get('start_date'): out=out.loc[dates >= pd.Timestamp(filters['start_date'])]; dates=pd.to_datetime(out['collection_date'],errors='coerce')
            if filters.get('end_date'): out=out.loc[dates <= pd.Timestamp(filters['end_date'])]
            return out
        daily_view=date_filter(daily)
        route_view=date_filter(routes)
        lead_view=date_filter(lead)
        # Figures use the project's original chart functions, not newly calculated index series.
        overall_fig=m['create_overall_index_chart'](daily_view) if not daily_view.empty else None
        route_fig=m['create_route_index_chart'](route_view) if not route_view.empty else None
        lead_fig=m['create_lead_time_chart'](lead_view) if not lead_view.empty else None
        metrics={}
        if not daily.empty:
            current=m['latest_index'](daily); previous=m['previous_index'](daily)
            metrics={'latest_index': round(float(current),2) if pd.notna(current) else None,
                     'previous_index': round(float(previous),2) if pd.notna(previous) else None,
                     'daily_change_pct': m['index_change_percent'](current,previous),
                     'publication_status':'Published artifact'}
        # Query helper is the source of truth for filtered raw observations where supported.
        try:
            obs=m['query_observations'](start_date=filters.get('start_date'), end_date=filters.get('end_date'), routes=filters.get('routes') or None, airlines=filters.get('airlines') or None, sources=filters.get('sources') or None)
        except Exception:
            obs=raw
        tables={'raw_observations':_records(obs), 'route_explorer':_records(route_view), 'lead_time_explorer':_records(lead_view)}
        try: tables['source_summary']=_records(m['source_summary'](start_date=filters.get('start_date'),end_date=filters.get('end_date'),routes=filters.get('routes') or None,airlines=filters.get('airlines') or None,sources=filters.get('sources') or None))
        except Exception: pass
        try: tables['route_ranking']=_records(m['route_summary'](start_date=filters.get('start_date'),end_date=filters.get('end_date'),routes=filters.get('routes') or None,airlines=filters.get('airlines') or None,sources=filters.get('sources') or None))
        except Exception: pass
        try: tables['data_quality']=_records(m['data_quality_summary'](start_date=filters.get('start_date'),end_date=filters.get('end_date'),routes=filters.get('routes') or None,airlines=filters.get('airlines') or None,sources=filters.get('sources') or None))
        except Exception: pass
        try:
            from pathlib import Path
            audit_path=ROOT/'data'/'reports'/'real_index_audit.csv'
            tables['latest_audit']=_records(pd.read_csv(audit_path).tail(1)) if audit_path.exists() else []
            cov_path=ROOT/'data'/'processed'/'real'/'index'/'real_coverage_report.csv'
            tables['coverage_gate']=_records(pd.read_csv(cov_path).tail(20)) if cov_path.exists() else []
            pipe_path=ROOT/'data'/'reports'/'real_pipeline_report.json'
            if pipe_path.exists(): tables['pipeline_stages']=[json.loads(pipe_path.read_text(encoding='utf-8'))]
        except Exception: pass
        charts={}
        for key,fig in [('chart-overall',overall_fig),('chart-routes',route_fig),('chart-lead',lead_fig),('chart-daily',overall_fig),('chart-period',overall_fig),('chart-route-movement',route_fig),('chart-route-lead',None),('chart-lead-time',lead_fig),('chart-lead-coverage',None),('chart-quality',None),('chart-anomalies',None),('chart-source',None),('chart-source-health',None),('chart-observation-coverage',None)]:
            val=_figure(fig)
            if val: charts[key]=val
        return JSONResponse({'page':page,'metrics':metrics,'charts':charts,'tables':tables,'audit_gates':[],'notes':'Only existing project data and chart functions are used. Empty sections mean their existing data/artifact was not available through the current source module.'})
    except HTTPException: raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Existing AirFareX data operation failed: {exc}')



# -------------------------------------------------------------------
# Frontend API compatibility layer
# Uses existing AirFareX loaders, metrics, observation store and charts.
# Does not modify frontend files or statistical index calculations.
# -------------------------------------------------------------------

from fastapi import Query
from datetime import date
import math


_API_CONTEXT_LOCK = RLock()

_API_CONTEXT_FILES = [
    ROOT / "data" / "processed" / "real" / "index" / "real_daily_airfare_index.csv",
    ROOT / "data" / "processed" / "real" / "index" / "real_route_indices.csv",
    ROOT / "data" / "processed" / "real" / "index" / "real_lead_time_contributions.csv",
]

_API_CONTEXT_CACHE = {
    "signature": None,
    "frames": None,
}

_API_COVERAGE_FILES = [
    ROOT / "data" / "processed" / "real" / "clean_airfare_observations.parquet",
    Path("/tmp/airfarex/clean_airfare_observations.parquet"),
]

_API_COVERAGE_CACHE = {
    "signature": None,
    "value": None,
}


def _api_file_signature(paths):
    signature = []

    for path in paths:
        try:
            stat = path.stat()
            signature.append((str(path), stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            signature.append((str(path), None, None))

    return tuple(signature)


def _api_context():
    """
    Reuse the three published index DataFrames in backend memory.
    Reload automatically when their source CSV files change.
    """
    m = _load_modules()
    signature = _api_file_signature(_API_CONTEXT_FILES)

    with _API_CONTEXT_LOCK:
        if signature != _API_CONTEXT_CACHE["signature"]:
            daily = m["load_daily_index"]()
            route_indices = m["load_route_indices"]()
            lead_indices = m["load_advance_window_indices"]()

            _API_CONTEXT_CACHE["frames"] = (
                daily if isinstance(daily, pd.DataFrame) else pd.DataFrame(),
                route_indices if isinstance(route_indices, pd.DataFrame) else pd.DataFrame(),
                lead_indices if isinstance(lead_indices, pd.DataFrame) else pd.DataFrame(),
            )
            _API_CONTEXT_CACHE["signature"] = signature

        daily, route_indices, lead_indices = _API_CONTEXT_CACHE["frames"]

    # These shared frames are treated as read-only by API endpoints.
    # Filtering helpers create their own copies before changing data.
    return m, daily, route_indices, lead_indices


def _api_route_coverage(m):
    """
    Cache the route-coverage summary instead of loading the clean
    observation dataset and recomputing coverage on every tab visit.
    """
    signature = _api_file_signature(_API_COVERAGE_FILES)

    with _API_CONTEXT_LOCK:
        if signature != _API_COVERAGE_CACHE["signature"]:
            coverage = m["route_coverage_summary"]()

            _API_COVERAGE_CACHE["value"] = coverage
            _API_COVERAGE_CACHE["signature"] = signature

        return _API_COVERAGE_CACHE["value"]


def _api_filters(start_date=None, end_date=None, routes=None,
                 airlines=None, sources=None):
    return {
        "start_date": start_date,
        "end_date": end_date,
        "routes": routes or None,
        "airlines": airlines or None,
        "sources": sources or None,
    }


def _api_observation_summary(m, filters):
    return m["query_observations"](
        page=1,
        page_size=1,
        start_date=filters["start_date"],
        end_date=filters["end_date"],
        routes=filters["routes"],
        airlines=filters["airlines"],
        sources=filters["sources"],
    )[0]


def _api_filter_dates(df, filters):
    if df is None or df.empty or "collection_date" not in df.columns:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    out = df.copy()
    dates = pd.to_datetime(out["collection_date"], errors="coerce")

    if filters.get("start_date"):
        out = out.loc[dates >= pd.Timestamp(filters["start_date"])].copy()
        dates = pd.to_datetime(out["collection_date"], errors="coerce")

    if filters.get("end_date"):
        out = out.loc[dates <= pd.Timestamp(filters["end_date"])].copy()

    return out


def _api_valid_index(df):
    if df is None or df.empty or "overall_airfare_index" not in df.columns:
        return pd.DataFrame()

    out = df.copy()
    out["overall_airfare_index"] = pd.to_numeric(
        out["overall_airfare_index"], errors="coerce"
    )
    out = out.dropna(subset=["overall_airfare_index"])

    if "index_status" in out.columns:
        out = out.loc[
            out["index_status"].astype(str).str.upper().eq("VALID")
        ]

    return out


def _api_quality(m, filters):
    result = m["data_quality_summary"](**filters)
    total = int(result.get("total_observations", 0) or 0)
    missing = float(result.get("missing_fare_pct", 0) or 0)
    duplicates = float(result.get("duplicate_pct", 0) or 0)
    score = max(0.0, 100.0 - missing - duplicates)

    return {
        "total_observations": total,
        "missing_fare_pct": missing,
        "duplicate_pct": duplicates,
        "quality_score": score,
        "status": "GOOD" if score >= 95 else "REVIEW" if score >= 80 else "POOR",
    }


def _api_json(data):
    from fastapi.encoders import jsonable_encoder
    return JSONResponse(content=jsonable_encoder(data))


def _api_plot(function, frame):
    if frame is None or frame.empty:
        return None
    return _figure(function(frame))


def _api_records(frame, limit=500):
    return _records(frame, limit=limit)


def _api_empty_chart():
    return None


@app.get("/api/dashboard/bootstrap")
def api_dashboard_bootstrap():
    m, daily, route_indices, lead_indices = _api_context()

    metadata = m["observation_metadata"]()
    dimensions = m["observation_dimensions"]()

    valid = _api_valid_index(daily)
    current = m["latest_index"](daily)
    latest_date = None

    if not valid.empty:
        latest_date = str(pd.to_datetime(
            valid.iloc[-1]["collection_date"], errors="coerce"
        ).date())

    min_date = metadata.get("min_timestamp")
    max_date = metadata.get("max_timestamp")

    return _api_json({
        "headline_index": round(float(current), 2) if pd.notna(current) else None,
        "latest_date": latest_date,
        "routes_count": int(metadata.get("routes", 0) or 0),
        "lead_windows_count": int(
            lead_indices["advance_days"].nunique()
            if not lead_indices.empty and "advance_days" in lead_indices.columns
            else 0
        ),
        "min_date": str(pd.to_datetime(min_date).date()) if min_date is not None else None,
        "max_date": str(pd.to_datetime(max_date).date()) if max_date is not None else None,
        "routes": dimensions.get("routes", []),
        "airlines": dimensions.get("airlines", []),
        "sources": dimensions.get("sources", []),
    })


@app.get("/api/dashboard/overview")
def api_dashboard_overview(
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, daily, route_indices, lead_indices = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)

    daily_view = _api_valid_index(_api_filter_dates(daily, filters))
    route_view = _api_filter_dates(route_indices, filters)
    lead_view = _api_filter_dates(lead_indices, filters)

    current = m["latest_index"](daily_view)
    previous = m["previous_index"](daily_view)
    change = m["index_change_percent"](current, previous)

    total = _api_observation_summary(m, filters)
    route_summary = m["route_summary"](**filters)
    source_summary = m["source_summary"](**filters)
    quality = _api_quality(m, filters)

    overall_chart = _api_plot(m["create_overall_index_chart"], daily_view)
    route_chart = _api_plot(m["create_route_index_chart"], route_view)
    lead_chart = _api_plot(m["create_lead_time_chart"], lead_view)

    source_chart = None
    if not source_summary.empty:
        import plotly.express as px
        source_chart = _figure(px.pie(
            source_summary,
            names="source",
            values="observations",
            title="Observations by Data Source",
        ))

    # Build a display table from the existing quality summary metrics.
    # data_quality_summary returns a dictionary, not a DataFrame.
    quality_table = pd.DataFrame([
        {"Metric": "Total Observations", "Value": quality["total_observations"]},
        {"Metric": "Missing Fare (%)", "Value": quality["missing_fare_pct"]},
        {"Metric": "Duplicate Rate (%)", "Value": quality["duplicate_pct"]},
        {"Metric": "Quality Score (%)", "Value": quality["quality_score"]},
        {"Metric": "Status", "Value": quality["status"]},
    ])

    import plotly.graph_objects as go

    quality_figure = go.Figure(
        data=[
            go.Bar(
                x=["Missing Fare", "Duplicates", "Quality Score"],
                y=[
                    quality["missing_fare_pct"],
                    quality["duplicate_pct"],
                    quality["quality_score"],
                ],
                text=[
                    f'{quality["missing_fare_pct"]:.2f}%',
                    f'{quality["duplicate_pct"]:.2f}%',
                    f'{quality["quality_score"]:.2f}%',
                ],
                textposition="auto",
                marker=dict(color=["#ff6b6b", "#f59e0b", "#16a34a"]),
            )
        ]
    )

    quality_figure.update_layout(
        title="Data Quality Metrics",
        yaxis_title="Percentage",
        yaxis=dict(range=[0, 100]),
        showlegend=False,
    )

    quality_chart = _figure(quality_figure)
    source_table = source_summary

    # The index artifacts remain authoritative; no index is reconstructed
    # from raw fares in this endpoint.
    return _api_json({
        "kpis": {
            "current_index": round(float(current), 2) if pd.notna(current) else None,
            "period_change": float(change) if pd.notna(change) else None,
            "previous_index": round(float(previous), 2) if pd.notna(previous) else None,
            "total_observations": int(total),
            "total_routes": int(len(route_summary)),
            "airline_count": len(filters["airlines"]) if filters["airlines"] else int(m["observation_metadata"]().get("airlines", 0)),
            "source_count": len(source_summary),
            "change_7d": None,
            "change_30d": None,
        },
        "overall_chart": overall_chart,
        "overall_table": _api_records(daily_view),
        "route_pulse_chart": route_chart,
        "route_pulse_table": _api_records(route_view),
        "lead_chart": lead_chart,
        "lead_table": _api_records(lead_view),
        "source_chart": source_chart,
        "quality": {
            "chart": quality_chart,
            "table": _api_records(quality_table, 100),
            "missing_pct": quality["missing_fare_pct"],
            "duplicate_pct": quality["duplicate_pct"],
            "score": quality["quality_score"],
        },
    })


@app.get("/api/dashboard/index-analytics")
def api_dashboard_index_analytics(
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, daily, _, _ = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    view = _api_valid_index(_api_filter_dates(daily, filters))

    if view.empty:
        return _api_json({
            "empty": True, "chart": None, "index_table": [],
            "weekly_table": [], "monthly_table": [], "audit_trail": [],
        })

    chart = _api_plot(m["create_overall_index_chart"], view)
    dates = pd.to_datetime(view["collection_date"], errors="coerce")
    temp = view.copy()
    temp["_date"] = dates

    weekly = (
        temp.set_index("_date")["overall_airfare_index"]
        .resample("W").mean().dropna().rename("mean_index").reset_index()
    )
    monthly = (
        temp.set_index("_date")["overall_airfare_index"]
        .resample("ME").mean().dropna().rename("mean_index").reset_index()
    )

    return _api_json({
        "empty": False,
        "chart": chart,
        "index_table": _api_records(view),
        "weekly_table": _api_records(weekly),
        "monthly_table": _api_records(monthly),
        "audit_trail": [],
    })


@app.get("/api/dashboard/route-intelligence")
def api_dashboard_route_intelligence(
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, _, route_indices, _ = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    view = _api_filter_dates(route_indices, filters)

    if view.empty:
        return _api_json({
            "empty": True,
            "kpis": {"routes_analysed": 0, "largest_increase": None,
                     "largest_decrease": None, "median_route_index": None},
            "route_chart": None, "explorer_routes": [], "ranking_table": [],
            "heatmap_chart": None, "heatmap_table": [], "coverage_table": [],
        })

    latest = view.sort_values("collection_date").groupby("route", as_index=False).tail(1)
    values = pd.to_numeric(latest.get("route_index"), errors="coerce").dropna()
    ranking = latest.sort_values("route_index", ascending=False)

    return _api_json({
        "empty": False,
        "kpis": {
            "routes_analysed": int(latest["route"].nunique()) if "route" in latest else 0,
            "largest_increase": None,
            "largest_decrease": None,
            "median_route_index": float(values.median()) if not values.empty else None,
        },
        "route_chart": _api_plot(m["create_route_index_chart"], view),
        "explorer_routes": sorted(view["route"].dropna().astype(str).unique().tolist()),
        "ranking_table": _api_records(ranking),
        "heatmap_chart": None,
        "heatmap_table": _api_records(view),
        "coverage_table": _api_records(_api_route_coverage(m)),
    })


@app.get("/api/dashboard/route-explorer")
def api_dashboard_route_explorer(
    route: str = "All Routes",
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    _, _, route_indices, _ = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    view = _api_filter_dates(route_indices, filters)

    if route and route != "All Routes" and "route" in view:
        view = view.loc[view["route"].astype(str) == route]

    return _api_json({"items": _api_records(view), "total": len(view)})


@app.get("/api/dashboard/lead-time")
def api_dashboard_lead_time(
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, _, _, lead_indices = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    view = _api_filter_dates(lead_indices, filters)

    if view.empty:
        return _api_json({
            "empty": True, "chart": None, "chart_table": [],
            "snapshot_table": [], "distribution_table": [],
            "lead_options": [], "route_options": [],
        })

    latest = view.sort_values("collection_date").groupby(
        "advance_days", as_index=False
    ).tail(1)

    return _api_json({
        "empty": False,
        "chart": _api_plot(m["create_lead_time_chart"], view),
        "chart_table": _api_records(view),
        "snapshot_table": _api_records(latest),
        "distribution_table": _api_records(view),
        "lead_options": sorted(
            pd.to_numeric(view["advance_days"], errors="coerce").dropna().astype(int).unique().tolist()
        ),
        "route_options": [],
    })


@app.get("/api/dashboard/lead-time-explorer")
def api_dashboard_lead_time_explorer(
    lead_time: str = "All Lead Times",
    route: str = "All Routes",
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, _, _, _ = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    view = m["route_lead_summary"](**filters)

    if lead_time and lead_time != "All Lead Times":
        try:
            days = int(str(lead_time).replace("T+", ""))
            view = view.loc[view["advance_days"] == days]
        except ValueError:
            pass

    if route and route != "All Routes":
        view = view.loc[view["route"].astype(str) == route]

    return _api_json({"items": _api_records(view), "total": len(view)})


@app.get("/api/dashboard/data-quality")
def api_dashboard_data_quality(
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, _, _, _ = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    quality = _api_quality(m, filters)

    # Query only a bounded sample for anomaly review; observations are never deleted.
    _, sample = m["query_observations"](
        page=1, page_size=20000, **filters
    )
    anomalies = m["detect_fare_anomalies"](sample)
    flagged = anomalies.loc[anomalies["anomaly_flag"]].copy() if (
        not anomalies.empty and "anomaly_flag" in anomalies.columns
    ) else pd.DataFrame()

    return _api_json({
        "kpis": quality,
        "anomalies": {
            "count": len(flagged),
            "rate": (len(flagged) / len(sample) * 100) if len(sample) else 0.0,
            "reviewed": len(sample),
            "flagged": _api_records(flagged, 500),
        },
    })


@app.get("/api/dashboard/source-health")
def api_dashboard_source_health(
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m, _, _, _ = _api_context()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    summary = m["source_summary"](**filters)
    total = int(summary["observations"].sum()) if not summary.empty else 0
    observed = len(summary)
    configured = int(m["observation_metadata"]().get("sources", 0) or 0)
    largest = (
        float(summary["observations"].max() / total * 100)
        if total else None
    )

    metadata = m["observation_metadata"]()
    earliest = metadata.get("min_timestamp")
    latest = metadata.get("max_timestamp")

    return _api_json({
        "empty": summary.empty,
        "kpis": {
            "total_observations": total,
            "observed_sources": observed,
            "configured_sources": configured,
            "source_coverage_pct": observed / configured * 100 if configured else 0.0,
            "largest_source_share": largest,
            "earliest_date": str(pd.to_datetime(earliest).date()) if earliest is not None else None,
            "latest_date": str(pd.to_datetime(latest).date()) if latest is not None else None,
        },
        "chart": None,
        "coverage_table": _api_records(summary),
    })


@app.get("/api/observations")
def api_observations(
    page: int = 1,
    page_size: int = 100,
    start_date: str | None = None,
    end_date: str | None = None,
    routes: list[str] | None = Query(None),
    airlines: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
):
    m = _load_modules()
    filters = _api_filters(start_date, end_date, routes, airlines, sources)
    total, frame = m["query_observations"](
        page=page,
        page_size=page_size,
        **filters,
    )
    pages = max(1, math.ceil(total / max(page_size, 1)))

    return _api_json({
        "total_pages": pages,
        "total": int(total),
        "page": max(1, page),
        "items": _api_records(frame, limit=max(page_size, 1)),
    })


@app.get("/api/dashboard/automation")
def api_dashboard_automation():
    m, daily, _, _ = _api_context()

    coverage_path = ROOT / "data" / "processed" / "real" / "index" / "real_coverage_report.csv"
    audit_candidates = [
        ROOT / "data" / "reports" / "real" / "real_index_audit.csv",
        ROOT / "data" / "reports" / "real_index_audit.csv",
    ]
    pipeline_path = ROOT / "data" / "reports" / "real_pipeline_report.json"

    coverage = pd.read_csv(coverage_path) if coverage_path.exists() else pd.DataFrame()
    audit_path = next((p for p in audit_candidates if p.exists()), None)
    audit = pd.read_csv(audit_path) if audit_path else pd.DataFrame()

    valid = _api_valid_index(daily)
    latest_audit = _api_records(audit.tail(1), 1)
    coverage_latest = _api_records(coverage.tail(1), 1)

    status = "UNAVAILABLE"
    gates = []

    if not coverage.empty:
        row = coverage.iloc[-1]
        coverage_status = str(row.get("coverage_status", "UNKNOWN")).upper()
        passed = coverage_status in ("PASS", "COMPLETE", "VALID")
        gates.append({
            "label": "Latest collection coverage",
            "status": "PASS" if passed else "FAIL",
        })
        status = "PUBLISHABLE" if passed and not valid.empty else "HOLD"

    if not valid.empty:
        gates.append({"label": "Valid published index available", "status": "PASS"})
    else:
        gates.append({"label": "Valid published index available", "status": "FAIL"})
        status = "HOLD"

    pipeline = []
    if pipeline_path.exists():
        try:
            pipeline_data = json.loads(pipeline_path.read_text(encoding="utf-8"))
            if isinstance(pipeline_data, list):
                pipeline = pipeline_data
            elif isinstance(pipeline_data, dict):
                pipeline = pipeline_data.get("pipeline_stages", [])
        except Exception:
            pipeline = []

    return _api_json({
        "gates": gates,
        "failed_checks": sum(g["status"] == "FAIL" for g in gates),
        "warnings": 0 if audit_path else 1,
        "publication_status": status,
        "latest_audit": latest_audit[0] if latest_audit else {},
        "coverage_table": coverage_latest,
        "pipeline_stages": pipeline,
        "provenance_table": [],
        "resilience_policy": [],
    })


@app.post("/api/dashboard/refresh")
def api_dashboard_refresh():
    # Explicit refresh invalidates backend memory caches.
    # Existing source files and statistical calculations are untouched.
    with _API_CONTEXT_LOCK:
        _API_CONTEXT_CACHE["signature"] = None
        _API_CONTEXT_CACHE["frames"] = None
        _API_COVERAGE_CACHE["signature"] = None
        _API_COVERAGE_CACHE["value"] = None

    return {"ok": True, "message": "Dashboard memory caches cleared."}


# Serve the existing AirFareX HTML frontend
FRONTEND_DIR = ROOT / "fastapi_migr" / "frontend"

if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend"
    )