"""AirFareX lightweight web frontend API.

This adapter reads existing AirFareX published artifacts and observation-store
functions. It does not run scraping or recalculate/publish the airfare index.
Run from the repository root with: uvicorn web_migration.main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import json
import os
import sys

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Locate the existing repository root without assuming where this folder sits.
_HERE = Path(__file__).resolve().parent
_candidates = [_HERE, *_HERE.parents]
PROJECT_ROOT = next((p for p in _candidates if (p / "dashboard" / "data_loader.py").exists()), _HERE.parent)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STATIC_DIR = _HERE / "static"
INDEX_DIR = PROJECT_ROOT / "data" / "processed" / "real" / "index"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "real"

app = FastAPI(title="AirFareX API", version="1.0.0", docs_url="/api/docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("AIRFAREX_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy/date scalar values to JSON-safe primitives."""
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    try:
        import math
        if isinstance(value, float) and not math.isfinite(value):
            return None
    except Exception:
        pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _records(frame, limit: int | None = None) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    data = frame.tail(limit) if limit else frame
    return [{str(k): _json_value(v) for k, v in row.items()} for row in data.to_dict(orient="records")]


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"data": value}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _read_csv(path: Path):
    import pandas as pd
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@lru_cache(maxsize=1)
def _published_data():
    """Cache published artifacts in-process; refresh endpoint clears this cache."""
    try:
        from dashboard.data_loader import load_daily_index, load_route_indices, load_advance_window_indices
        daily = load_daily_index()
        routes = load_route_indices()
        lead = load_advance_window_indices()
    except Exception as exc:
        raise RuntimeError(f"Could not load AirFareX published artifacts: {exc}") from exc

    # Match the data contract used by the existing Streamlit dashboard.
    if "date" in daily.columns and "collection_date" not in daily.columns:
        daily = daily.rename(columns={"date": "collection_date"})
    for col in ("national_index", "index_value", "airfare_index"):
        if "overall_airfare_index" not in daily.columns and col in daily.columns:
            daily = daily.rename(columns={col: "overall_airfare_index"})
            break
    if "date" in routes.columns and "collection_date" not in routes.columns:
        routes = routes.rename(columns={"date": "collection_date"})
    if "index" in routes.columns and "route_index" not in routes.columns:
        routes = routes.rename(columns={"index": "route_index"})
    if "date" in lead.columns and "collection_date" not in lead.columns:
        lead = lead.rename(columns={"date": "collection_date"})
    for col in ("mean_stratum_index", "lead_time_index", "mean_index", "advance_window_index", "index"):
        if "airfare_index" not in lead.columns and col in lead.columns:
            lead = lead.rename(columns={col: "airfare_index"})
            break
    for frame in (daily, routes, lead):
        if "collection_date" in frame.columns:
            frame["collection_date"] = frame["collection_date"].astype(str)
    return daily, routes, lead


def _observation_dimensions() -> dict:
    try:
        from dashboard.observation_store import observation_dimensions
        dims = observation_dimensions() or {}
        return {k: list(v or []) for k, v in dims.items()}
    except Exception:
        return {"routes": [], "airlines": [], "sources": []}


def _metadata() -> dict:
    # Read the same metadata artifact as the Streamlit app; attempt store metadata
    # only when the published file is not available.
    result = _read_json(INDEX_DIR / "real_index_metadata.json")
    try:
        from dashboard.observation_store import observation_metadata
        live = observation_metadata() or {}
        for key, value in live.items():
            if result.get(key) in (None, ""):
                result[key] = _json_value(value)
    except Exception:
        pass
    return result


def _audit() -> list[dict]:
    return _records(_read_csv(REPORT_DIR / "real_index_audit.csv"))

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True, "service": "airfarex-api", "pipeline_root_found": (PROJECT_ROOT / "dashboard").exists()}

@app.get("/api/bootstrap")
def bootstrap():
    """Small first request: metadata and latest KPI values; no raw observations."""
    try:
        daily, routes, lead = _published_data()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    meta = _metadata()
    audits = _audit()
    daily_records = _records(daily, 45)
    latest = daily_records[-1] if daily_records else {}
    previous = daily_records[-2] if len(daily_records) > 1 else {}
    index_value = latest.get("overall_airfare_index")
    prev_value = previous.get("overall_airfare_index")
    change = None
    try:
        if prev_value not in (None, 0) and index_value is not None:
            change = (float(index_value) / float(prev_value) - 1) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    latest_audit = next((row for row in reversed(audits) if str(row.get("publication_status", "")).upper() == "PUBLISHABLE"), audits[-1] if audits else {})
    return {
        "product": "AirFareX",
        "kpis": {
            "latest_index": index_value,
            "previous_index": prev_value,
            "change_pct": change,
            "observations": meta.get("total_observations", meta.get("observations")),
            "routes": meta.get("routes"),
            "airlines": meta.get("airlines"),
            "sources": meta.get("sources"),
            "latest_date": latest.get("collection_date"),
            "publication_status": latest_audit.get("publication_status", "Unavailable"),
        },
        "dimensions": _observation_dimensions(),
        "available": {"daily": not daily.empty, "routes": not routes.empty, "lead_time": not lead.empty},
    }

@app.get("/api/index")
def index_data(limit: int = Query(365, ge=1, le=5000)):
    try:
        daily, _, _ = _published_data()
        return {"data": _records(daily, limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.get("/api/routes")
def routes_data(limit: int = Query(500, ge=1, le=5000)):
    try:
        _, routes, _ = _published_data()
        return {"data": _records(routes, limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.get("/api/lead-time")
def lead_time_data(limit: int = Query(500, ge=1, le=5000)):
    try:
        _, _, lead = _published_data()
        return {"data": _records(lead, limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.get("/api/audit")
def audit_data():
    return {"data": _audit(), "coverage": _records(_read_csv(INDEX_DIR / "real_coverage_report.csv")), "pipeline_report": _read_json(REPORT_DIR / "real_pipeline_report.json"), "metadata": _metadata()}

@app.get("/api/source-health")
def source_health():
    try:
        from dashboard.observation_store import source_summary, data_quality_summary
        sources = _records(source_summary())
        quality = data_quality_summary() or {}
        return {"sources": sources, "quality": {str(k): _json_value(v) for k, v in quality.items()}, "dimensions": _observation_dimensions(), "metadata": _metadata()}
    except Exception as exc:
        # Return real artifact metadata and a visible error instead of fabricated health metrics.
        return {"sources": [], "quality": {}, "dimensions": _observation_dimensions(), "metadata": _metadata(), "warning": str(exc)}

@app.get("/api/observations")
def observations(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=250), start_date: str | None = None, end_date: str | None = None, route: list[str] = Query(default=[]), airline: list[str] = Query(default=[]), source: list[str] = Query(default=[])):
    try:
        from dashboard.observation_store import query_observations
        result = query_observations(page=page, page_size=page_size, start_date=start_date, end_date=end_date, routes=route or None, airlines=airline or None, sources=source or None)
        # Current store contract used by app.py returns (total_rows, dataframe).
        total, frame = result
        return {"total": int(total or 0), "page": page, "page_size": page_size, "data": _records(frame)}
    except TypeError:
        # Some deployments use page_number rather than page; retry the compatible signature.
        try:
            total, frame = query_observations(page_number=page, page_size=page_size, start_date=start_date, end_date=end_date, routes=route or None, airlines=airline or None, sources=source or None)
            return {"total": int(total or 0), "page": page, "page_size": page_size, "data": _records(frame)}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Observation query failed: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Observation query failed: {exc}")

@app.post("/api/refresh")
def refresh():
    """Clear only in-process read caches; does not alter raw or historical data."""
    _published_data.cache_clear()
    return {"ok": True, "message": "Published artifact cache cleared. Pipeline data was not modified."}


@app.get("/api/metadata")
def metadata_compat():
    try:
        daily, routes, lead = _published_data()
        dates = []

        for frame in (daily, routes, lead):
            if "collection_date" in frame.columns:
                dates.extend(
                    frame["collection_date"].dropna().astype(str).tolist()
                )

        return {
            "dimensions": _observation_dimensions(),
            "min_date": min(dates) if dates else None,
            "max_date": max(dates) if dates else None,
            "metadata": _metadata(),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/api/dashboard")
def dashboard_compat(request: dict = Body(default={})):
    try:
        daily, routes, lead = _published_data()
        filters = request.get("filters") or {}
        page = request.get("page", "overview")

        def filter_dates(frame):
            result = frame.copy()

            if "collection_date" in result.columns:
                dates = result["collection_date"].astype(str)

                if filters.get("start_date"):
                    result = result[
                        dates >= str(filters["start_date"])
                    ]
                    dates = result["collection_date"].astype(str)

                if filters.get("end_date"):
                    result = result[
                        dates <= str(filters["end_date"])
                    ]

            return result

        d = filter_dates(daily)
        r = filter_dates(routes)
        l = filter_dates(lead)

        daily_rows = _records(d, 5000)
        route_rows = _records(r, 5000)
        lead_rows = _records(l, 5000)
        audit_rows = _audit()

        latest = daily_rows[-1] if daily_rows else {}
        previous = daily_rows[-2] if len(daily_rows) > 1 else {}

        latest_index = latest.get("overall_airfare_index")
        previous_index = previous.get("overall_airfare_index")
        daily_change = None

        try:
            if latest_index is not None and previous_index not in (None, 0):
                daily_change = (
                    float(latest_index) / float(previous_index) - 1
                ) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            pass

        def make_chart(rows, x_key, y_key, title):
            valid = [
                row for row in rows
                if row.get(x_key) is not None
                and row.get(y_key) is not None
            ]

            if not valid:
                return {
                    "data": [],
                    "layout": {"title": title}
                }

            return {
                "data": [{
                    "type": "scatter",
                    "mode": "lines+markers",
                    "name": title,
                    "x": [row[x_key] for row in valid],
                    "y": [row[y_key] for row in valid],
                }],
                "layout": {
                    "title": title,
                    "autosize": True,
                    "margin": {"t": 40, "r": 20, "b": 50, "l": 55},
                    "paper_bgcolor": "#ffffff",
                    "plot_bgcolor": "#ffffff",
                    "xaxis": {"title": x_key},
                    "yaxis": {"title": y_key},
                },
            }

        charts = {
            "chart-overall": make_chart(
                daily_rows, "collection_date",
                "overall_airfare_index", "Overall Airfare Index"
            ),
            "chart-daily": make_chart(
                daily_rows, "collection_date",
                "overall_airfare_index", "Daily Airfare Index"
            ),
            "chart-routes": make_chart(
                route_rows, "collection_date",
                "route_index", "Route-wise Airfare Index"
            ),
            "chart-route-movement": make_chart(
                route_rows, "collection_date",
                "route_index", "Route Index Movement"
            ),
            "chart-lead": make_chart(
                lead_rows, "collection_date",
                "airfare_index", "Lead-Time Price Index"
            ),
            "chart-lead-time": make_chart(
                lead_rows, "collection_date",
                "airfare_index", "Lead-Time Price Index"
            ),
        }

        source_rows = []
        quality_rows = []
        observation_rows = []

        try:
            from dashboard.observation_store import (
                source_summary,
                data_quality_summary,
                query_observations,
            )

            source_rows = _records(source_summary())

            quality = data_quality_summary()
            if hasattr(quality, "to_dict"):
                quality_rows = _records(quality)
            elif isinstance(quality, dict):
                quality_rows = [quality]

            result = query_observations(
                page=1,
                page_size=100,
                start_date=filters.get("start_date"),
                end_date=filters.get("end_date"),
                routes=filters.get("routes") or None,
                airlines=filters.get("airlines") or None,
                sources=filters.get("sources") or None,
            )

            _, observation_frame = result
            observation_rows = _records(observation_frame)

        except Exception:
            # Missing optional diagnostics must not fabricate data.
            pass

        metadata = _metadata()
        publish_status = next(
            (
                row.get("publication_status")
                for row in reversed(audit_rows)
                if str(row.get("publication_status", "")).upper()
                == "PUBLISHABLE"
            ),
            "Unavailable",
        )

        coverage_path = INDEX_DIR / "real_coverage_report.csv"

        return {
            "metrics": {
                "latest_index": latest_index,
                "previous_index": previous_index,
                "daily_change_pct": daily_change,
                "change_7d": None,
                "change_30d": None,
                "quality_score": None,
                "publication_status": publish_status,
            },
            "charts": charts,
            "tables": {
                "audit_trail": audit_rows[-250:],
                "route_ranking": route_rows[-250:],
                "route_explorer": route_rows[-250:],
                "lead_time_explorer": lead_rows[-250:],
                "data_quality": quality_rows,
                "anomalies": [],
                "source_summary": source_rows,
                "raw_observations": observation_rows,
                "latest_audit": audit_rows[-10:],
                "coverage_gate": _records(_read_csv(coverage_path)),
                "pipeline_stages": [],
                "provenance": [metadata] if metadata else [],
                "resilience_policy": [],
            },
            "audit_gates": [],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Dashboard data unavailable: {exc}",
        )


