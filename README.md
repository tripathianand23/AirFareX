# Real-Time Airfare Price Index for India

> **Smart India Hackathon 2026 — Problem Statement 26056**
> Development of a Real-time Airfare Price Index for India through Automated Web Scraping of Airline and Online Travel Aggregator Portals for Augmentation of the Consumer Price Index (CPI)

## Overview

`airfare-ml` is a statistical data engineering and automation system designed to collect, normalize, validate, deduplicate, monitor, and aggregate airfare observations into a daily Airfare Price Index for India.

The system focuses on **statistical measurement and smart automation**, rather than airfare price prediction.

Its primary objective is to establish a reproducible pipeline:

**Data Collection → Raw Storage → Normalization → Validation → Deduplication → Data Quality → Coverage → Index Calculation → Audit → Publication → Dashboard**

---

## Key Objectives

* Automate airfare data collection from multiple sources.
* Preserve raw observations and provenance.
* Convert heterogeneous source data into a canonical airfare schema.
* Detect structurally invalid and duplicate observations.
* Monitor route and advance-purchase coverage.
* Calculate a configurable airfare price index.
* Generate route-level and lead-time-level analytics.
* Apply publication gates before releasing index values.
* Maintain audit trails and reproducibility.
* Provide a Streamlit dashboard for statistical and operational monitoring.

---

## System Architecture

```text
                   ┌─────────────────────┐
                   │ Airline / OTA Sources│
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Source Adapters     │
                   │ & Source Registry   │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Raw Data Storage     │
                   │ + Provenance        │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Normalization       │
                   │ Canonical Schema    │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Validation          │
                   │ + Data Quality      │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Deduplication       │
                   │ + Cleaning          │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Coverage Monitoring │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Index Engine        │
                   │ Route + Lead Time   │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Audit & Publication │
                   │ Gates               │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Streamlit Dashboard │
                   └─────────────────────┘
```

---

## Repository Structure

```text
airfare-ml/
│
├── config/
│   └── index_methodology.yaml
│
├── dashboard/
│
├── data/
│   ├── raw/
│   ├── synthetic/
│   └── processed/
│
├── src/
│   └── airfare_ml/
│       ├── data/
│       │   ├── adapters/
│       │   ├── batch_ingestion.py
│       │   ├── cleaning.py
│       │   ├── collection_status.py
│       │   ├── ingestion.py
│       │   ├── profiling.py
│       │   ├── provenance.py
│       │   ├── raw_storage.py
│       │   ├── retry.py
│       │   ├── schema.py
│       │   ├── source_config.py
│       │   ├── source_registry.py
│       │   └── validation.py
│       │
│       ├── features/
│       ├── models/
│       └── index/
│           ├── aggregation.py
│           ├── audit.py
│           ├── calculation.py
│           ├── config.py
│           ├── config_loader.py
│           ├── contributions.py
│           ├── methodology.py
│           ├── series.py
│           └── validation.py
│
├── scripts/
│   ├── run_real_pipeline.py
│   └── build_real_airfare_index.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── notebooks/
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## Data Pipeline

### 1. Collection

Source adapters collect airfare observations from configured sources.

The source registry allows sources to be enabled or disabled through configuration.

### 2. Raw Storage

Raw observations are preserved before transformation.

Each raw record can contain:

* `raw_record_id`
* `source`
* `collection_timestamp`
* `ingestion_timestamp`
* `request_id`
* `source_url`
* `payload_hash`
* `schema_version`
* `payload`

Payload hashes are generated using SHA-256 to support provenance and reproducibility.

### 3. Normalization

Different source formats are transformed into a common canonical airfare schema.

Important fields include:

* origin
* destination
* airline
* travel date
* advance days
* base fare
* taxes
* fees
* total fare
* currency
* availability
* baggage
* refundability
* source information

### 4. Validation

The validation layer checks:

* Required fields
* Fare validity
* Route validity
* Advance-window validity
* Collection/travel-date relationship
* Duplicate observations
* Structural validity

Expected advance windows currently include:

```text
T+1
T+7
T+15
T+30
T+45
```

### 5. Deduplication

Raw row count is not treated as the number of independent airfare observations.

Business-level duplicate detection is applied before index calculation to prevent repeated OTA or ingestion records from disproportionately influencing the index.

### 6. Coverage

The system monitors coverage across:

```text
Route × Advance Window
```

The current prototype uses a 20-route universe and five advance windows.

A daily index is considered publishable only when the configured coverage requirements are satisfied.

---

## Index Methodology

The current prototype methodology is configuration-driven.

### Base

```text
Base value = 100
Base date  = 2026-09-04
```

### Representative Fare

The current prototype uses the:

```text
Median
```

fare as the representative fare for each route and advance-window stratum.

The median provides robustness against extreme airfare observations while retaining legitimate high-price observations.

### Route Weights

Current prototype:

```text
Equal route weights
```

### Lead-Time Weights

Current prototype:

```text
Equal advance-window weights
```

### Advance Windows

```text
1, 7, 15, 30, 45 days
```

> **Important:** These are prototype methodology choices and are not claimed to be official MoSPI/CPI weights or methodology.

---

## Publication Gate

The system does not automatically publish an index value when required data is missing.

Publication checks include:

* Route coverage
* Route × advance-window coverage
* Structural validity
* Duplicate quality checks
* Representative fare validity
* Index calculation validity
* Contribution reconciliation
* Base-period validity

Possible outcomes include:

```text
PUBLISHABLE
HOLD
```

Incomplete observations therefore result in a controlled **HOLD** rather than fabricated or imputed index values.

---

## Current Real Dataset

The current real-data pipeline contains approximately:

```text
54,787 raw airfare records
15,457 observations after business-level deduplication
20 routes
5 advance windows
4 data sources
4 airlines
```

Current sources represented in the dataset include:

* EaseMyTrip
* Yatra
* Akasa Air Direct
* SpiceJet Direct

The dataset covers routes involving major Indian aviation markets including Delhi, Mumbai, Bengaluru, Chennai, Hyderabad, Kolkata, Goa, and Ahmedabad.

---

## Example Index Output

Using the current prototype methodology:

| Date       |  Index | Publication Status |
| ---------- | -----: | ------------------ |
| 2026-09-02 |      — | HOLD               |
| 2026-09-03 |      — | HOLD               |
| 2026-09-04 | 100.00 | PUBLISHABLE        |
| 2026-09-05 | 116.13 | PUBLISHABLE        |

These values are **prototype outputs from the current dataset and methodology**.

They must not be interpreted as official CPI or official MoSPI statistics.

---

## Lead-Time Analysis

The system also decomposes daily index movement by advance-purchase window.

For the current prototype data, the movement from September 4 to September 5 was approximately:

| Advance Window | Movement |
| -------------- | -------: |
| T+1            |  +46.30% |
| T+7            |   +2.64% |
| T+15           |  +20.51% |
| T+30           |   +2.77% |
| T+45           |   +8.40% |

This is interpreted as **differentiated price movement across booking horizons**, not price elasticity.

---

## Data Quality & Governance

The project treats data quality as a first-class component of the statistical system.

Current checks include:

* Missing required fields
* Invalid fares
* Invalid routes
* Invalid advance windows
* Invalid date relationships
* Duplicate detection
* Route coverage
* Stratum coverage
* Source distribution
* Contribution reconciliation
* Publication eligibility

Future quality intelligence can include:

* MAD-based anomaly detection
* IQR-based outlier detection
* Robust z-scores
* Rolling-median monitoring
* Distribution drift
* Sudden route-level movements
* Source concentration monitoring
* Cross-source consistency checks

Machine-learning-based anomaly detection can be introduced later if deterministic statistical quality controls prove insufficient.

---

## Dashboard

The Streamlit dashboard is organized into:

1. Overview
2. Index Analytics
3. Route Intelligence
4. Lead-Time Analysis
5. Data Quality
6. Source Health
7. Automation Control Center
8. Methodology

The dashboard is designed to distinguish between:

* Governed/precomputed headline statistics
* Exploratory filtered analytics
* Actual operational telemetry
* Prototype methodology assumptions

The system does not fabricate unavailable operational metrics.

Where telemetry is unavailable, the dashboard should explicitly indicate:

```text
Telemetry not yet available
```

---

## Configuration

Index methodology is controlled through:

```text
config/index_methodology.yaml
```

This allows methodology parameters to be changed without rewriting the calculation engine.

Configuration includes:

* Base date
* Base value
* Representative fare method
* Advance windows
* Route universe
* Route weights
* Lead-time weights
* Coverage thresholds
* Publication requirements
* Prototype/official status

---

## Running the Project

### 1. Create and activate the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the test suite

```bash
python -m pytest -q
```

The project should maintain a green test suite before major changes are merged.

### 4. Run the real-data pipeline

```bash
python scripts/run_real_pipeline.py
```

### 5. Build the airfare index

```bash
python scripts/build_real_airfare_index.py
```

### 6. Launch the Streamlit dashboard

```bash
streamlit run dashboard/app.py
```

---

## Testing

The project uses `pytest` for unit and integration testing.

The existing test suite covers areas including:

* Schema validation
* Data validation
* Cleaning
* Deduplication
* Source adapters
* Retry behavior
* Ingestion
* Configuration loading
* Index calculation
* Aggregation
* Contributions
* Series generation
* Audit checks

Run:

```bash
python -m pytest -q
```

---

## Design Principles

### 1. No fabricated statistics

Missing data is not silently replaced with invented observations.

### 2. Reproducibility

Raw data, configuration, transformations, and methodology are preserved so that results can be reproduced.

### 3. Auditability

Every publishable index is subjected to automated validation and audit checks.

### 4. Configuration-driven methodology

Statistical assumptions are externalized into configuration rather than hidden inside application code.

### 5. Source independence

The system is designed to support multiple sources rather than relying on a single provider.

### 6. Statistical robustness

Median-based aggregation, business-level deduplication, coverage gates, and explicit quality checks reduce the risk of biased measurements.

### 7. Controlled publication

An index value is published only when the required quality and coverage conditions are satisfied.

---

## Current Limitations

The current implementation is a prototype and has several limitations:

* Current route weights are equal rather than authoritative CPI weights.
* Current lead-time weights are equal.
* Some raw records do not contain flight or offer identifiers.
* Some sources combine taxes and fees.
* Current real-data coverage spans a limited time period.
* Source concentration is currently uneven.
* Production-grade scraping/API integrations require further development.
* Historical benchmark validation is still required.
* Revision and publication policies require further formalization.
* Official MoSPI/CPI integration has not been established.

---

## Roadmap

### Phase 1 — Dashboard Completion

* Complete migration to real processed outputs.
* Remove remaining synthetic/demo operational metrics.
* Normalize data-loader column differences.
* Improve index, route, lead-time, quality, and source-health views.

### Phase 2 — Data Quality Intelligence

* Robust anomaly detection
* Route-level anomaly monitoring
* Source-level anomaly monitoring
* Distribution drift
* Duplicate-rate monitoring
* Missing-field monitoring
* Source concentration monitoring

### Phase 3 — Index Robustness

Sensitivity analysis across:

* Median vs trimmed mean
* Equal vs traffic-based route weights
* Lead-time weighting
* Outlier treatment
* Source exclusions
* Route exclusions
* Missing strata
* Alternative base periods

### Phase 4 — Authoritative Route Weights

Investigate authoritative aviation traffic data and evaluate whether it provides a statistically compatible basis for route weighting.

### Phase 5 — Backtesting

Where a comparable historical benchmark is available:

* MAE
* RMSE
* Correlation
* Directional accuracy
* Month-over-month movement error
* Turning-point agreement
* Route stability
* Base-period robustness

### Phase 6 — Revision & Publication Framework

Implement:

* Data freeze windows
* Late-arrival handling
* Revision windows
* Correction workflows
* Versioned outputs
* Revision history
* Reproducible reprocessing

### Phase 7 — Production Deployment

Target architecture:

```text
Scheduler
    ↓
Source Registry
    ↓
Collectors
    ↓
Raw Object Storage
    ↓
Normalization
    ↓
Validation
    ↓
Deduplication
    ↓
Data Quality
    ↓
Coverage Gate
    ↓
Index Engine
    ↓
Audit
    ↓
Publication
    ↓
API
    ↓
Dashboard
```

---

## Important Statistical Disclaimer

This repository contains a **prototype Airfare Price Index system** developed for Smart India Hackathon.

The current index values, weights, route universe, base period, and methodology are experimental and configurable.

They are **not official MoSPI statistics, not an official CPI component, and not an official Government of India index**.

Any future official implementation would require appropriate methodological validation, authoritative weighting, data governance, source agreements/compliance, historical benchmarking, and institutional approval.

---

## Project Philosophy

> **Our intelligence is operational and statistical, not predictive.**

The primary intelligence of this system comes from:

**Smart Automation + Data Engineering + Statistical Measurement + Data Quality + Governance + Auditability**

rather than attempting to predict future airfare prices.

