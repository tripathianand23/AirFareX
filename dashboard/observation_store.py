# ============================================================
# OBSERVATION STORE
# DuckDB-backed observation access for AirFareX
# ============================================================

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence

import duckdb
import pandas as pd
import streamlit as st


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOCAL_PARQUET = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "real"
    / "clean_airfare_observations.parquet"
)

R2_BUCKET = os.getenv("R2_BUCKET", "airfare-data")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_ENDPOINT_URL = os.getenv(
    "R2_ENDPOINT_URL",
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
)

R2_PARQUET_KEY = (
    "processed/clean_airfare_observations.parquet"
)


# ============================================================
# PARQUET PATH RESOLUTION
# ============================================================

def _resolve_parquet_path() -> Path:
    """
    Resolve the clean Parquet dataset.

    Local development uses the local Parquet file.

    Render uses Cloudflare R2 as the source of truth and downloads
    the Parquet dataset to /tmp for DuckDB to read.
    """
    prefer_r2 = os.getenv("RENDER", "").lower() == "true"

    # Local development: use the local dataset when available.
    if LOCAL_PARQUET.exists() and not prefer_r2:
        return LOCAL_PARQUET

    # If R2 is not configured, fall back to local data when available.
    if not (
        R2_ACCOUNT_ID
        and R2_ACCESS_KEY_ID
        and R2_SECRET_ACCESS_KEY
    ):
        if LOCAL_PARQUET.exists():
            return LOCAL_PARQUET

        raise RuntimeError(
            "Local Parquet dataset is unavailable and "
            "Cloudflare R2 credentials are not configured."
        )

    # Render/container cache.
    cache_dir = Path("/tmp/airfarex")
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached_parquet = cache_dir / "clean_airfare_observations.parquet"

    if cached_parquet.exists():
        return cached_parquet

    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

    s3.download_file(
        R2_BUCKET,
        R2_PARQUET_KEY,
        str(cached_parquet),
    )

    return cached_parquet


# ============================================================
# DUCKDB CONNECTION
# ============================================================

def _connection():
    """
    Create a DuckDB connection and expose the Parquet dataset
    as a lazy view.

    DuckDB reads the Parquet file directly instead of loading the
    complete 797k+ row dataset into Pandas.
    """

    path = _resolve_parquet_path()

    conn = duckdb.connect(database=":memory:")

    conn.execute(
        "SET memory_limit='180MB'"
    )

    conn.execute(
        "SET threads=1"
    )

    # Escape single quotes in the filesystem path.
    parquet_path = str(path).replace("'", "''")

    # IMPORTANT:
    # Do not use read_parquet(?) here.
    # DuckDB does not allow prepared parameters in CREATE VIEW.
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW observations AS
        SELECT *
        FROM read_parquet('{parquet_path}')
        """
    )

    return conn


# ============================================================
# METADATA
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def observation_metadata():
    """
    Return lightweight dataset metadata using DuckDB.
    """

    conn = _connection()

    result = conn.execute(
        """
        SELECT
            COUNT(*) AS observations,

            COUNT(
                DISTINCT CASE
                    WHEN origin IS NOT NULL
                     AND destination IS NOT NULL
                    THEN UPPER(
                        TRIM(origin)
                        || '-'
                        || TRIM(destination)
                    )
                END
            ) AS routes,

            COUNT(DISTINCT airline) AS airlines,

            COUNT(DISTINCT source) AS sources,

            MIN(collection_timestamp) AS min_timestamp,

            MAX(collection_timestamp) AS max_timestamp

        FROM observations
        """
    ).fetchone()

    observations = int(result[0] or 0)
    routes = int(result[1] or 0)
    airlines = int(result[2] or 0)
    sources = int(result[3] or 0)
    min_timestamp = result[4]
    max_timestamp = result[5]

    return {
        "observations": observations,
        "routes": routes,
        "airlines": airlines,
        "sources": sources,
        "min_timestamp": min_timestamp,
        "max_timestamp": max_timestamp,

        # Compatibility aliases
        "total_observations": observations,
        "first_collection": min_timestamp,
        "last_collection": max_timestamp,
    }


# ============================================================
# DIMENSIONS
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def observation_dimensions():
    """
    Return distinct dashboard filter dimensions.
    """

    conn = _connection()

    routes = conn.execute(
        """
        SELECT DISTINCT
            UPPER(
                TRIM(origin)
                || '-'
                || TRIM(destination)
            ) AS route
        FROM observations
        WHERE origin IS NOT NULL
          AND destination IS NOT NULL
        ORDER BY route
        """
    ).fetchdf()

    airlines = conn.execute(
        """
        SELECT DISTINCT airline
        FROM observations
        WHERE airline IS NOT NULL
        ORDER BY airline
        """
    ).fetchdf()

    sources = conn.execute(
        """
        SELECT DISTINCT source
        FROM observations
        WHERE source IS NOT NULL
        ORDER BY source
        """
    ).fetchdf()

    conn.close()
    return {
        "routes": routes["route"].tolist(),
        "airlines": airlines["airline"].tolist(),
        "sources": sources["source"].tolist(),
    }


# ============================================================
# FILTER BUILDER
# ============================================================

def _build_where(
    start_date=None,
    end_date=None,
    routes: Optional[Sequence[str]] = None,
    airlines: Optional[Sequence[str]] = None,
    sources: Optional[Sequence[str]] = None,
):
    """
    Build a safe SQL WHERE clause and parameter list.
    """

    conditions = []
    params = []

    if start_date is not None:
        conditions.append(
            "CAST(collection_timestamp AS DATE) >= ?"
        )
        params.append(start_date)

    if end_date is not None:
        conditions.append(
            "CAST(collection_timestamp AS DATE) <= ?"
        )
        params.append(end_date)

    if routes:
        placeholders = ", ".join(
            ["?"] * len(routes)
        )

        conditions.append(
            f"""
            UPPER(
                TRIM(origin)
                || '-'
                || TRIM(destination)
            ) IN ({placeholders})
            """
        )

        params.extend(routes)

    if airlines:
        placeholders = ", ".join(
            ["?"] * len(airlines)
        )

        conditions.append(
            f"airline IN ({placeholders})"
        )

        params.extend(airlines)

    if sources:
        placeholders = ", ".join(
            ["?"] * len(sources)
        )

        conditions.append(
            f"source IN ({placeholders})"
        )

        params.extend(sources)

    if conditions:
        where_sql = "WHERE " + "\nAND ".join(
            conditions
        )
    else:
        where_sql = ""

    return where_sql, params


# ============================================================
# OBSERVATION QUERY
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def query_observations(
    page=1,
    page_size=100,
    start_date=None,
    end_date=None,
    routes=None,
    airlines=None,
    sources=None,
    columns=None,
    limit=None,
):
    """
    Paginated observation query for the Raw Data Explorer.

    Returns:
        total_rows, page_dataframe
    """

    conn = _connection()

    page = max(int(page), 1)
    page_size = max(int(page_size), 1)

    where_sql, params = _build_where(
        start_date=start_date,
        end_date=end_date,
        routes=routes,
        airlines=airlines,
        sources=sources,
    )

    # --------------------------------------------------------
    # Total matching rows
    # --------------------------------------------------------

    total_rows = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM observations
        {where_sql}
        """,
        params,
    ).fetchone()[0]

    # --------------------------------------------------------
    # Columns
    # --------------------------------------------------------

    if columns:
        select_sql = ", ".join(
            f'"{column}"'
            for column in columns
        )
    else:
        select_sql = "*"

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    offset = (page - 1) * page_size

    query = f"""
        SELECT
            {select_sql}
        FROM observations
        {where_sql}
        ORDER BY collection_timestamp DESC
        LIMIT ?
        OFFSET ?
    """

    query_params = list(params)
    query_params.extend(
        [
            page_size,
            offset,
        ]
    )

    df = conn.execute(
        query,
        query_params,
    ).fetchdf()

    conn.close()
    return int(total_rows), df
# ============================================================
# SOURCE SUMMARY
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def source_summary(
    start_date=None,
    end_date=None,
    routes=None,
    airlines=None,
    sources=None,
):
    """

    Aggregate observations by source without loading the
    complete dataset into Pandas.
    """

    conn = _connection()

    where_sql, params = _build_where(
        start_date=start_date,
        end_date=end_date,
        routes=routes,
        airlines=airlines,
        sources=sources,
    )

    source_condition = (
        f"{where_sql} AND source IS NOT NULL"
        if where_sql
        else "WHERE source IS NOT NULL"
    )

    result = conn.execute(
        f"""
        SELECT
            source,
            COUNT(*) AS observations
        FROM observations
        {source_condition}
        GROUP BY source
        ORDER BY observations DESC
        """,
        params,
    ).fetchdf()
    conn.close()
    return result

# ============================================================
# DATA QUALITY SUMMARY
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def data_quality_summary(
    start_date=None,
    end_date=None,
    routes=None,
    airlines=None,
    sources=None,
):
    """
    Calculate lightweight data-quality metrics directly in DuckDB.

    This avoids loading the complete observation dataset into Pandas.
    """

    conn = _connection()

    where_sql, params = _build_where(
        start_date=start_date,
        end_date=end_date,
        routes=routes,
        airlines=airlines,
        sources=sources,
    )

    result = conn.execute(
        f"""
        WITH filtered AS (
            SELECT *
            FROM observations
            {where_sql}
        )

        SELECT
            COUNT(*) AS total_observations,

            COUNT(*) FILTER (
                WHERE total_fare IS NULL
            ) AS missing_total_fare,

            COUNT(*) - COUNT(
                DISTINCT
                CONCAT_WS(
                    '||',
                    COALESCE(CAST(collection_timestamp AS VARCHAR), ''),
                    COALESCE(CAST(source AS VARCHAR), ''),
                    COALESCE(CAST(origin AS VARCHAR), ''),
                    COALESCE(CAST(destination AS VARCHAR), ''),
                    COALESCE(CAST(travel_date AS VARCHAR), ''),
                    COALESCE(CAST(airline AS VARCHAR), ''),
                    COALESCE(CAST(departure_time AS VARCHAR), ''),
                    COALESCE(CAST(advance_days AS VARCHAR), ''),
                    COALESCE(CAST(base_fare AS VARCHAR), ''),
                    COALESCE(CAST(taxes AS VARCHAR), ''),
                    COALESCE(CAST(fees AS VARCHAR), ''),
                    COALESCE(CAST(total_fare AS VARCHAR), ''),
                    COALESCE(CAST(currency AS VARCHAR), ''),
                    COALESCE(CAST(flight_number AS VARCHAR), ''),
                    COALESCE(CAST(arrival_time AS VARCHAR), '')
                )
            ) AS duplicate_rows

        FROM filtered
        """,
        params,
    ).fetchone()

    total = int(result[0] or 0)
    missing = int(result[1] or 0)
    duplicates = int(result[2] or 0)

    conn.close()

    return {
        "total_observations": total,
        "missing_total_fare": missing,
        "duplicate_rows": duplicates,
        "missing_fare_pct": (
            missing / total * 100
            if total
            else 0.0
        ),
        "duplicate_pct": (
            duplicates / total * 100
            if total
            else 0.0
        ),
    }

# ============================================================
# ROUTE SUMMARY
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def route_lead_summary(
    start_date=None,
    end_date=None,
    routes=None,
    airlines=None,
    sources=None,
):
    """
    Aggregate median observed fare by route and
    advance-purchase window.
    """

    conn = _connection()

    where_sql, params = _build_where(
        start_date=start_date,
        end_date=end_date,
        routes=routes,
        airlines=airlines,
        sources=sources,
    )

    extra_conditions = """
        origin IS NOT NULL
        AND destination IS NOT NULL
        AND advance_days IS NOT NULL
        AND total_fare IS NOT NULL
    """

    if where_sql:
        final_where = f"""
            {where_sql}
            AND {extra_conditions}
        """
    else:
        final_where = f"""
            WHERE {extra_conditions}
        """

    result = conn.execute(
        f"""
        SELECT
            UPPER(
                TRIM(origin)
                || '-'
                || TRIM(destination)
            ) AS route,
            advance_days,
            COUNT(*) AS observations,
            MEDIAN(total_fare) AS median_fare
        FROM observations
        {final_where}
        GROUP BY
            route,
            advance_days
        ORDER BY
            route,
            advance_days
        """,
        params,
    ).fetchdf()
    conn.close()
    return result


# ============================================================
# LEAD-TIME SUMMARY
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def lead_time_summary(
    start_date=None,
    end_date=None,
    routes=None,
    airlines=None,
    sources=None,
):
    """
    Aggregate fare statistics by advance-purchase window.

    This replaces the previous full-Pandas lead_fares calculation.
    """

    conn = _connection()

    where_sql, params = _build_where(
        start_date=start_date,
        end_date=end_date,
        routes=routes,
        airlines=airlines,
        sources=sources,
    )

    result = conn.execute(
        f"""
        SELECT
            advance_days,
            COUNT(*) AS observations,
            MEDIAN(total_fare) AS median_fare,
            AVG(total_fare) AS mean_fare,
            MIN(total_fare) AS min_fare,
            MAX(total_fare) AS max_fare
        FROM observations
        {where_sql}
        {"AND" if where_sql else "WHERE"}
            advance_days IS NOT NULL
        AND total_fare IS NOT NULL
        GROUP BY advance_days
        ORDER BY advance_days
        """,
        params,
    ).fetchdf()
    conn.close()
    return result


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def route_summary(
    start_date=None,
    end_date=None,
    routes=None,
    airlines=None,
    sources=None,
):
    """
    Aggregate observations by route.
    """

    conn = _connection()

    where_sql, params = _build_where(
        start_date=start_date,
        end_date=end_date,
        routes=routes,
        airlines=airlines,
        sources=sources,
    )

    if where_sql:
        final_where = f"""
            {where_sql}
            AND origin IS NOT NULL
            AND destination IS NOT NULL
            AND total_fare IS NOT NULL
        """
    else:
        final_where = """
            WHERE origin IS NOT NULL
            AND destination IS NOT NULL
            AND total_fare IS NOT NULL
        """

    result = conn.execute(
        f"""
        SELECT
            UPPER(
                TRIM(origin)
                || '-'
                || TRIM(destination)
            ) AS route,
            COUNT(*) AS observations,
            MEDIAN(total_fare) AS median_fare,
            AVG(total_fare) AS mean_fare
        FROM observations
        {final_where}
        GROUP BY route
        ORDER BY observations DESC
        """,
        params,
    ).fetchdf()
    conn.close()
    return result
