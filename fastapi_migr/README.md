# AirFareX Standalone FastAPI Dashboard

FastAPI migration for the AirFareX real-data statistical operations dashboard (`dashboard/app.py`).

## Features
- **Frontend Parity**: Replicates the exact visual appearance, colors, header glass card (`.top-shell`), sidebar controls, segmented control navigation, Plotly charts, dataframes, alert banners, and metrics of `dashboard/app.py`.
- **High Performance**: Solves Streamlit's slowness by replacing full-page script re-executions with asynchronous API endpoints, client-side tab switching, and DuckDB aggregations.
- **Dedicated High-Speed Endpoints**:
  - `GET /api/dashboard/bootstrap`: Headline KPIs, collection date bounds, and sidebar filter dimensions.
  - `GET /api/dashboard/overview`: Real-time Overview tab data, KPIs, Plotly chart specs, and data tables.
  - `GET /api/dashboard/index-analytics`: Daily, weekly, monthly, and audit trail views.
  - `GET /api/dashboard/route-intelligence`: Route KPIs, route index line chart, route explorer, ranking table, route × lead-time heatmap, and coverage table.
  - `GET /api/dashboard/route-explorer`: Route-specific index history records.
  - `GET /api/dashboard/lead-time`: Advance purchase window indices, statistical snapshot, and observed fare distributions.
  - `GET /api/dashboard/lead-time-explorer`: DuckDB aggregations for route × advance window fares.
  - `GET /api/dashboard/data-quality`: Operational QC score, metrics, and IQR anomaly candidates.
  - `GET /api/dashboard/source-health`: Source contribution, observation share chart, and concentration signals.
  - `GET /api/observations`: Paginated raw observation queries.
  - `GET /api/dashboard/automation`: 6 automated audit gate checks, publication gate status, audit record JSON, coverage gate, 10 pipeline stages, provenance table, and resilience rules.
  - `POST /api/dashboard/refresh`: Cache invalidation and dataset reloading.
- **Full Backward Compatibility**: Retains all original API routes (`/api/health`, `/api/overview/metadata`, `/api/filters`, `/api/index/daily`, `/api/index/routes`, `/api/index/lead-time`, `/api/index/metadata`, `/api/audit`, `/api/coverage`, `/api/analytics/sources`, `/api/analytics/quality`, `/api/analytics/routes`, `/api/analytics/lead-time`, `/api/analytics/route-lead`, `/api/automation/pipeline-report`, `/api/analytics/anomalies`).

## Run locally
From the project root (`~/airfare`):

```bash
python -m uvicorn fastapi_migr.api.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser at:
`http://127.0.0.1:8000`

## Run Tests
To run the automated test suite verifying all routes:

```bash
python -m pytest fastapi_migr/tests/test_api.py -v
```
