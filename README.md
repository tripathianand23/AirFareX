# AirFareX rebuilt standalone frontend

This package replaces only the frontend files under `fastapi_migr/frontend/`.
It is based on the uploaded original `app (1).py` reference and the API snapshot supplied in `airfarex_migration_snapshot.zip`.

## Install

From `~/airfare`:

```bash
unzip -o ~/Downloads/AirFareX-Rebuilt-Frontend.zip -d fastapi_migr
```

This replaces:
- `fastapi_migr/frontend/index.html`
- `fastapi_migr/frontend/css/dashboard.css`
- `fastapi_migr/frontend/js/dashboard.js`

It does not replace `fastapi_migr/api/main.py`, `dashboard/app.py`, any data module, pipeline script, dataset, or root requirements file.

The supplied API already mounts `/static` and serves `frontend/index.html` at `/`, so no API edits are required for this frontend.

## Run

```bash
cd ~/airfare
conda activate base
python -m uvicorn fastapi_migr.api.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## What is aligned to the original

- Warm `#f9f1f0` background and centered content width.
- Original aircraft background image extracted from the uploaded original dashboard source.
- Single continuous glass header and four headline KPI cards.
- Horizontal segmented navigation with the original eight section labels.
- Overview section with six KPI cards, movement callout, national index, route movement, lead-time, source coverage and quality panels.
- Remaining seven sections are present and wired to the corresponding API routes in the supplied snapshot.
- Weekly and monthly index summaries use median aggregation by Pandas weekly (`W`) and monthly (`M`) periods, matching the original helper functions.
- Route movement compares each route's first and last valid route index, matching `build_route_movers`.
- Raw explorer requests only one page at a time from `/api/observations`.

## Known data limitation — not hidden

The supplied migration ZIP contains only `fastapi_migr/`; it does not contain the underlying data files, the clean Parquet store, the deployed service's object-store credentials, or the deployed dashboard runtime.

The previously tested local API snapshot returned:
- daily index latest date: 2026-10-02
- headline `overall_airfare_index`: 205.9123
- observation-store rows: 1,023,464

The original dashboard screenshot supplied in the conversation showed:
- latest date: 2026-10-29
- headline index: 303.15
- observation count: 2,472,411

The frontend cannot safely recreate the latter values. The local FastAPI process must be connected to the same current index artifacts and observation Parquet data that the original dashboard is using. Do not hardcode screenshot values.

## Validation still required

1. Confirm the local FastAPI process is using the same data artifacts as the original dashboard.
2. Compare every section and metric against the original dashboard for the same data snapshot.
3. Verify browser console and API responses for every page.
4. Validate export behaviour and any original download controls not exposed in the supplied API snapshot.

Plotly and Google Fonts are loaded from CDNs; network access is needed for those external assets.
