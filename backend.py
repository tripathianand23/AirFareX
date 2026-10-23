"""Optional FastAPI bridge for the HTML frontend.

Place this file in the AirFareX project root (beside the existing app.py and
 dashboard/ package). It imports existing data/statistics modules; it does not
 import or edit the Streamlit app and does not implement a replacement index.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


def _load_modules():
    try:
        from dashboard.observation_store import observation_metadata, observation_dimensions, query_observations, source_summary, route_summary, lead_time_summary, route_lead_summary, data_quality_summary
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
