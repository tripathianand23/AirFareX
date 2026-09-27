from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import streamlit as st
from io import BytesIO
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SYNTHETIC_DIR = PROJECT_ROOT / "data" / "processed"
REAL_DIR = PROJECT_ROOT / "data" / "processed" / "real"
REAL_INDEX_DIR = REAL_DIR / "index"
RAW_JSON_PATH = PROJECT_ROOT / "data" / "raw" / "airfare_index.json"

# ============================================================
# CLOUDFLARE R2
# ============================================================

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "airfare-data").strip()

R2_ENDPOINT = os.getenv(
    "R2_ENDPOINT",
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    if R2_ACCOUNT_ID
    else "",
).strip()

R2_ENABLED = bool(
    R2_ACCOUNT_ID
    and R2_ACCESS_KEY_ID
    and R2_SECRET_ACCESS_KEY
    and R2_BUCKET
    and R2_ENDPOINT
)

R2_CLEAN_PARQUET_KEY = "processed/clean_airfare_observations.parquet"
R2_RAW_JSON_KEY = "raw/airfare_index.json"


# ============================================================
# CLOUDFLARE R2 HELPERS
# ============================================================

@st.cache_resource(show_spinner=False)
def _get_r2_client():
    """Create a Cloudflare R2 S3-compatible client."""
    if not R2_ENABLED:
        return None

    import boto3

    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _r2_enabled() -> bool:
    return R2_ENABLED


@st.cache_data(ttl=900, show_spinner=False)
def _read_r2_bytes(remote_key: str) -> bytes:
    """Read one object from Cloudflare R2."""
    client = _get_r2_client()

    if client is None:
        raise RuntimeError("Cloudflare R2 is not configured.")

    response = client.get_object(
        Bucket=R2_BUCKET,
        Key=remote_key,
    )

    return response["Body"].read()


@st.cache_data(ttl=900, show_spinner=False)
def _read_r2_dataframe(remote_key: str) -> pd.DataFrame:
    """Read CSV or Parquet data from R2."""
    payload = _read_r2_bytes(remote_key)

    if remote_key.lower().endswith(".parquet"):
        return pd.read_parquet(BytesIO(payload))

    if remote_key.lower().endswith(".csv"):
        return pd.read_csv(BytesIO(payload))

    raise ValueError(
        f"Unsupported R2 tabular file: {remote_key}"
    )


@st.cache_data(ttl=900, show_spinner=False)
def _read_r2_json(remote_key: str):
    """Read JSON data from R2."""
    payload = _read_r2_bytes(remote_key)

    return json.loads(
        payload.decode("utf-8")
    )


def _r2_object_exists(remote_key: str) -> bool:
    """Check whether an object exists in R2."""
    client = _get_r2_client()

    if client is None:
        return False

    try:
        client.head_object(
            Bucket=R2_BUCKET,
            Key=remote_key,
        )
        return True
    except Exception:
        return False

    
# ============================================================
# PATH HELPERS
# ============================================================

def _path(mode: str, filename: str) -> Path:
    mode = mode.lower()

    if mode == "real":
        return REAL_DIR / filename

    if mode == "synthetic":
        return SYNTHETIC_DIR / filename

    raise ValueError(f"Unknown dashboard data mode: {mode}")


def _index_path(mode: str, filename: str) -> Path:
    mode = mode.lower()

    if mode == "real":
        return REAL_INDEX_DIR / filename

    if mode == "synthetic":
        return SYNTHETIC_DIR / "index" / filename

    raise ValueError(f"Unknown dashboard data mode: {mode}")


# ============================================================
# COLUMN NORMALISATION
# ============================================================

def _normalise_daily_index_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise statistical index output to dashboard column names."""
    out = df.copy()

    if "overall_airfare_index" not in out.columns:
        for candidate in (
            "national_index",
            "airfare_index",
            "index_value",
            "index",
        ):
            if candidate in out.columns:
                out = out.rename(
                    columns={candidate: "overall_airfare_index"}
                )
                break

    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(
            out["collection_date"],
            errors="coerce",
        )

    if "overall_airfare_index" in out.columns:
        out["overall_airfare_index"] = pd.to_numeric(
            out["overall_airfare_index"],
            errors="coerce",
        )

    return out


def _normalise_lead_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise lead-time output to dashboard column names."""
    out = df.copy()

    if "airfare_index" not in out.columns:
        for candidate in (
            "mean_stratum_index",
            "lead_time_index",
            "mean_index",
            "advance_window_index",
            "index",
        ):
            if candidate in out.columns:
                out = out.rename(
                    columns={candidate: "airfare_index"}
                )
                break

    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(
            out["collection_date"],
            errors="coerce",
        )

    if "airfare_index" in out.columns:
        out["airfare_index"] = pd.to_numeric(
            out["airfare_index"],
            errors="coerce",
        )

    return out


def _normalise_observation_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise observation data into the dashboard's canonical schema.

    Raw airfare_index.json is intentionally mapped at the dashboard
    boundary. The source values are preserved; no fares are invented.
    """
    out = df.copy()

    rename_map = {}

    if "timestamp" in out.columns and "collection_timestamp" not in out.columns:
        rename_map["timestamp"] = "collection_timestamp"

    if (
        "advance_window_days" in out.columns
        and "advance_days" not in out.columns
    ):
        rename_map["advance_window_days"] = "advance_days"

    if "ota_source" in out.columns and "source" not in out.columns:
        rename_map["ota_source"] = "source"

    if rename_map:
        out = out.rename(columns=rename_map)
        # Friend API provides route as "ORIGIN-DESTINATION".
    # Dashboard/monitoring expects separate origin and destination columns.
    if "route" in out.columns:
        route_parts = (
            out["route"]
            .astype("string")
            .str.strip()
            .str.upper()
            .str.split("-", n=1, expand=True)
        )

        if "origin" not in out.columns:
            out["origin"] = (
                route_parts[0]
                if 0 in route_parts.columns
                else pd.NA
            )

        if "destination" not in out.columns:
            out["destination"] = (
                route_parts[1]
                if 1 in route_parts.columns
                else pd.NA
            )    

    # Source contains one combined taxes_fees field. Keep the original
    # value as taxes while explicitly mapping consumer fare to source total.
    if "taxes_fees" in out.columns and "taxes" not in out.columns:
        out["taxes"] = pd.to_numeric(
            out["taxes_fees"],
            errors="coerce",
        )

    if "total_fare" in out.columns:
        out["total_fare"] = pd.to_numeric(
            out["total_fare"],
            errors="coerce",
        )

    if "base_fare" in out.columns:
        out["base_fare"] = pd.to_numeric(
            out["base_fare"],
            errors="coerce",
        )

    if "taxes" in out.columns:
        out["taxes"] = pd.to_numeric(
            out["taxes"],
            errors="coerce",
        )

    if "consumer_fare" not in out.columns:
        if {"base_fare", "taxes"}.issubset(out.columns):
            out["consumer_fare"] = (
                out["base_fare"].fillna(0)
                + out["taxes"].fillna(0)
            )

    if "advance_days" in out.columns:
        out["advance_days"] = pd.to_numeric(
            out["advance_days"],
            errors="coerce",
        )

    for column in (
        "collection_timestamp",
        "travel_date",
        "ingestion_timestamp",
    ):
        if column in out.columns:
            out[column] = pd.to_datetime(
                out[column],
                errors="coerce",
            )

    return out


# ============================================================
# RAW OBSERVATIONS
# ============================================================

def load_raw_observations() -> pd.DataFrame:
    """
    Load the complete raw_fares observation universe directly from
    data/raw/airfare_index.json.

    No deduplication, filtering, cleaning, sampling, or aggregation is
    performed here. This keeps the dashboard's Raw Data Explorer faithful
    to the source dataset.
    """
    if not RAW_JSON_PATH.exists():
        return pd.DataFrame()

    try:
        with RAW_JSON_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Unable to read raw airfare dataset:\n{RAW_JSON_PATH}"
        ) from exc

    if isinstance(payload, dict):
        records = payload.get("raw_fares", [])
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    if not records:
        return pd.DataFrame()

    return _normalise_observation_columns(
        pd.DataFrame(records)
    )


# ============================================================
# OBSERVATIONS USED BY EXPLORATORY DASHBOARD VIEWS
# ============================================================

FRIEND_API_URL = "https://mospi-apix-api.onrender.com/api/fares/raw"
FRIEND_API_HOURS_BACK = 720  # 30day(s)

@st.cache_data(ttl=900, show_spinner=False)

def _load_friend_api_observations() -> pd.DataFrame:
    """
    Fetch airfare observations from the Friend API.

    Used primarily by deployed environments where the large local
    generated datasets are intentionally not stored in GitHub.

    The API response is normalized through the same dashboard
    boundary normalization used by local JSON/CSV data.
    """
    import requests

    try:
        response = requests.get(
            FRIEND_API_URL,
            params={"hours_back": FRIEND_API_HOURS_BACK},
            timeout=120,
        )
        response.raise_for_status()

        payload = response.json()

    except requests.RequestException as exc:
        raise RuntimeError(
            "Unable to fetch airfare observations from Friend API:\n"
            f"{FRIEND_API_URL}\n\n"
            f"Error: {exc}"
        ) from exc

    # Support common API response shapes.
    if isinstance(payload, list):
        records = payload

    elif isinstance(payload, dict):
        if isinstance(payload.get("raw_fares"), list):
            records = payload["raw_fares"]

        elif isinstance(payload.get("data"), list):
            records = payload["data"]

        elif isinstance(payload.get("fares"), list):
            records = payload["fares"]

        else:
            records = []

    else:
        records = []

    if not records:
        return pd.DataFrame()

    return _normalise_observation_columns(
        pd.DataFrame(records)
    )
    FRIEND_API_URL = "https://mospi-apix-api.onrender.com/api/fares/raw"

# Friend API has a 50,000-record page limit.
# Fetch each calendar date separately and follow all pages.
FRIEND_API_START_DATE = "2026-09-02"
FRIEND_API_PAGE_SIZE = 50000
FRIEND_API_TIMEOUT = 120
FRIEND_API_RETRIES = 3


@st.cache_data(ttl=900, show_spinner=False)
def _load_friend_api_observations() -> pd.DataFrame:
    """
    Fetch complete historical airfare observations from Friend API.

    Uses date-based pagination instead of hours_back because the API
    caps responses at 50,000 records.
    """
    from datetime import date, timedelta
    import os
    import time
    import requests

    configured_start = os.getenv(
        "FRIEND_API_START_DATE",
        FRIEND_API_START_DATE,
    ).strip()

    try:
        start_date = date.fromisoformat(configured_start)
    except ValueError as exc:
        raise RuntimeError(
            "Invalid FRIEND_API_START_DATE. Expected YYYY-MM-DD, "
            f"received: {configured_start!r}"
        ) from exc

    end_date = date.today()

    if start_date > end_date:
        raise RuntimeError(
            f"FRIEND_API_START_DATE cannot be later than today: "
            f"{start_date} > {end_date}"
        )

    all_records = []
    session = requests.Session()

    current_date = start_date

    while current_date <= end_date:
        date_string = current_date.isoformat()
        page = 1

        while True:
            params = {
                "date": date_string,
                "page": page,
                "size": FRIEND_API_PAGE_SIZE,
            }

            payload = None
            last_error = None

            for attempt in range(1, FRIEND_API_RETRIES + 1):
                try:
                    response = session.get(
                        FRIEND_API_URL,
                        params=params,
                        timeout=FRIEND_API_TIMEOUT,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    break

                except (requests.RequestException, ValueError) as exc:
                    last_error = exc

                    if attempt < FRIEND_API_RETRIES:
                        time.sleep(2 * attempt)

            if payload is None:
                raise RuntimeError(
                    "Unable to fetch airfare observations from Friend API.\n"
                    f"Date: {date_string}\n"
                    f"Page: {page}\n"
                    f"URL: {FRIEND_API_URL}\n"
                    f"Error: {last_error}"
                )

            if isinstance(payload, list):
                records = payload
                pagination = {
                    "has_next": False,
                    "total_pages": 1,
                }

            elif isinstance(payload, dict):
                if isinstance(payload.get("data"), list):
                    records = payload["data"]
                elif isinstance(payload.get("raw_fares"), list):
                    records = payload["raw_fares"]
                elif isinstance(payload.get("fares"), list):
                    records = payload["fares"]
                else:
                    records = []

                pagination = payload.get("pagination") or {}

            else:
                records = []
                pagination = {}

            all_records.extend(records)

            has_next = bool(
                pagination.get("has_next", False)
            )

            total_pages = int(
                pagination.get("total_pages") or 1
            )

            if not has_next and page >= total_pages:
                break

            page += 1

        current_date += timedelta(days=1)

    if not all_records:
        return pd.DataFrame()

    return _normalise_observation_columns(
        pd.DataFrame(all_records)
    )

def load_clean_data(mode: str = "real") -> pd.DataFrame:
    """
    Load the dashboard observation dataset.

    Priority for REAL data:
      1. Cloudflare R2 processed Parquet
      2. Local processed Parquet/CSV
      3. Local raw JSON
      4. Cloudflare R2 raw JSON
      5. Friend API
    """

    if mode.lower() == "real":

        # --------------------------------------------------------
        # 1. CLOUDflare R2 — PRIMARY DEPLOYED DATA SOURCE
        # --------------------------------------------------------
        if _r2_enabled():
            try:
                r2_df = _read_r2_dataframe(
                    "processed/clean_airfare_observations.parquet"
                )

                if not r2_df.empty:
                    return _normalise_observation_columns(r2_df)

            except Exception as exc:
                raise RuntimeError(
                    "Cloudflare R2 is configured but the clean "
                    "Parquet dataset could not be loaded.\n"
                    f"Bucket: {R2_BUCKET}\n"
                    f"Object: processed/clean_airfare_observations.parquet\n"
                    f"Error: {exc}"
                ) from exc

        # --------------------------------------------------------
        # 2. LOCAL processed data — mainly for local development
        # --------------------------------------------------------
        preferred_paths = [
            REAL_DIR / "dashboard_airfare_observations.parquet",
            REAL_DIR / "dashboard_airfare_observations.csv",
            REAL_DIR / "clean_airfare_observations.parquet",
            REAL_DIR / "clean_airfare_observations.csv",
        ]

        for path in preferred_paths:
            if path.exists():

                if path.suffix.lower() == ".parquet":
                    return _normalise_observation_columns(
                        pd.read_parquet(path)
                    )

                return _normalise_observation_columns(
                    pd.read_csv(path)
                )

        # --------------------------------------------------------
        # 3. Local / R2 raw JSON
        # --------------------------------------------------------
        if RAW_JSON_PATH.exists() or _r2_enabled():
            try:
                raw_df = load_raw_observations()

                if not raw_df.empty:
                    return raw_df

            except Exception:
                pass

        # --------------------------------------------------------
        # 4. Friend API fallback
        # --------------------------------------------------------
        return _load_friend_api_observations()

    # ------------------------------------------------------------
    # SYNTHETIC DATA
    # ------------------------------------------------------------
    path = _path(
        "synthetic",
        "clean_airfare_observations.csv",
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Dashboard dataset not found:\n{path}"
        )

    return _normalise_observation_columns(
        pd.read_csv(path)
    )
# ============================================================
# DAILY INDEX
# ============================================================

def load_daily_index(mode: str = "real") -> pd.DataFrame:
    if mode.lower() == "real":

        remote_key = "index/real_daily_airfare_index.csv"

        if _r2_enabled() and _r2_object_exists(remote_key):
            df = _read_r2_dataframe(remote_key)

        else:
            path = _index_path(
                "real",
                "real_daily_airfare_index.csv",
            )

            if not path.exists():
                raise FileNotFoundError(
                    f"Daily index file not found locally or in R2:\n{path}"
                )

            df = pd.read_csv(path)

    else:
        path = _index_path(
            "synthetic",
            "daily_airfare_index.csv",
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Daily index file not found:\n{path}"
            )

        df = pd.read_csv(path)

    return _normalise_daily_index_columns(df)


# ============================================================
# ROUTE INDICES
# ============================================================

def load_route_indices(mode: str = "real") -> pd.DataFrame:
    if mode.lower() == "real":

        remote_key = "index/real_route_indices.csv"

        if _r2_enabled() and _r2_object_exists(remote_key):
            df = _read_r2_dataframe(remote_key)

        else:
            path = _index_path(
                "real",
                "real_route_indices.csv",
            )

            if not path.exists():
                raise FileNotFoundError(
                    f"Route index file not found locally or in R2:\n{path}"
                )

            df = pd.read_csv(path)

    else:
        path = _index_path(
            "synthetic",
            "route_indices.csv",
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Route index file not found:\n{path}"
            )

        df = pd.read_csv(path)

    if "collection_date" in df.columns:
        df["collection_date"] = pd.to_datetime(
            df["collection_date"],
            errors="coerce",
        )

    return df


# ============================================================
# ADVANCE-WINDOW / LEAD-TIME DATA
# ============================================================

def load_advance_window_indices(
    mode: str = "real",
) -> pd.DataFrame:

    if mode.lower() == "real":

        remote_key = "index/real_lead_time_contributions.csv"

        if _r2_enabled() and _r2_object_exists(remote_key):
            df = _read_r2_dataframe(remote_key)

        else:
            path = _index_path(
                "real",
                "real_lead_time_contributions.csv",
            )

            if not path.exists():
                raise FileNotFoundError(
                    f"Lead-time index file not found locally or in R2:\n{path}"
                )

            df = pd.read_csv(path)

    else:
        path = _index_path(
            "synthetic",
            "advance_window_indices.csv",
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Lead-time index file not found:\n{path}"
            )

        df = pd.read_csv(path)

    return _normalise_lead_time_columns(df)


# ============================================================
# REAL INDEX AUDIT
# ============================================================

def load_real_audit() -> pd.DataFrame:
    path = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / "real"
        / "real_index_audit.csv"
    )

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "collection_date" in df.columns:
        df["collection_date"] = pd.to_datetime(
            df["collection_date"],
            errors="coerce",
        )

    return df


# ============================================================
# REAL COVERAGE
# ============================================================

def load_real_coverage() -> pd.DataFrame:
    path = REAL_INDEX_DIR / "real_coverage_report.csv"

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "collection_date" in df.columns:
        df["collection_date"] = pd.to_datetime(
            df["collection_date"],
            errors="coerce",
        )

    return df


# ============================================================
# REAL METADATA
# ============================================================

def load_real_metadata() -> dict:
    path = REAL_INDEX_DIR / "real_index_metadata.json"

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
