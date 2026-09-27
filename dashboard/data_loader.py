from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SYNTHETIC_DIR = PROJECT_ROOT / "data" / "processed"
REAL_DIR = PROJECT_ROOT / "data" / "processed" / "real"
REAL_INDEX_DIR = REAL_DIR / "index"

RAW_JSON_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "airfare_index.json"
)

LOCAL_PARQUET_PATH = (
    REAL_DIR
    / "clean_airfare_observations.parquet"
)

LOCAL_CSV_PATH = (
    REAL_DIR
    / "clean_airfare_observations.csv"
)


# ============================================================
# CLOUDFLARE R2 CONFIGURATION
# ============================================================

R2_BUCKET = os.getenv(
    "R2_BUCKET",
    "airfare-data",
)

R2_ACCOUNT_ID = os.getenv(
    "R2_ACCOUNT_ID",
    "",
).strip()

R2_ACCESS_KEY_ID = os.getenv(
    "R2_ACCESS_KEY_ID",
    "",
).strip()

R2_SECRET_ACCESS_KEY = os.getenv(
    "R2_SECRET_ACCESS_KEY",
    "",
).strip()

R2_ENDPOINT_URL = os.getenv(
    "R2_ENDPOINT_URL",
    (
        f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        if R2_ACCOUNT_ID
        else ""
    ),
).strip()

R2_CLEAN_PARQUET_KEY = (
    "processed/clean_airfare_observations.parquet"
)


# ============================================================
# PATH HELPERS
# ============================================================

def _path(
    mode: str,
    filename: str,
) -> Path:
    mode = mode.lower()

    if mode == "real":
        return REAL_DIR / filename

    if mode == "synthetic":
        return SYNTHETIC_DIR / filename

    raise ValueError(
        f"Unknown dashboard data mode: {mode}"
    )


def _index_path(
    mode: str,
    filename: str,
) -> Path:
    mode = mode.lower()

    if mode == "real":
        return REAL_INDEX_DIR / filename

    if mode == "synthetic":
        return (
            SYNTHETIC_DIR
            / "index"
            / filename
        )

    raise ValueError(
        f"Unknown dashboard data mode: {mode}"
    )


# ============================================================
# COLUMN NORMALISATION
# ============================================================

def _normalise_daily_index_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalise statistical index output to dashboard
    column names.
    """

    out = df.copy()

    if (
        "overall_airfare_index"
        not in out.columns
    ):
        for candidate in (
            "national_index",
            "airfare_index",
            "index_value",
            "index",
        ):
            if candidate in out.columns:
                out = out.rename(
                    columns={
                        candidate:
                        "overall_airfare_index"
                    }
                )
                break

    if "collection_date" in out.columns:
        out["collection_date"] = pd.to_datetime(
            out["collection_date"],
            errors="coerce",
        )

    if (
        "overall_airfare_index"
        in out.columns
    ):
        out[
            "overall_airfare_index"
        ] = pd.to_numeric(
            out["overall_airfare_index"],
            errors="coerce",
        )

    return out


def _normalise_lead_time_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalise lead-time output to dashboard
    column names.
    """

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
                    columns={
                        candidate:
                        "airfare_index"
                    }
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


def _normalise_observation_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert raw/API/processed observation fields into
    the canonical dashboard schema.

    No observations are deleted or aggregated here.
    """

    if df.empty:
        return df

    out = df.copy()

    # --------------------------------------------------------
    # Rename source/API fields
    # --------------------------------------------------------

    rename_map = {}

    if (
        "timestamp" in out.columns
        and "collection_timestamp"
        not in out.columns
    ):
        rename_map[
            "timestamp"
        ] = "collection_timestamp"

    if (
        "advance_window_days"
        in out.columns
        and "advance_days"
        not in out.columns
    ):
        rename_map[
            "advance_window_days"
        ] = "advance_days"

    if (
        "ota_source" in out.columns
        and "source" not in out.columns
    ):
        rename_map[
            "ota_source"
        ] = "source"

    if rename_map:
        out = out.rename(
            columns=rename_map
        )

    # --------------------------------------------------------
    # Route → origin / destination
    # --------------------------------------------------------

    if "route" in out.columns:

        route_parts = (
            out["route"]
            .astype("string")
            .str.strip()
            .str.upper()
            .str.split(
                "-",
                n=1,
                expand=True,
            )
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

    # --------------------------------------------------------
    # Taxes / fees
    # --------------------------------------------------------

    if (
        "taxes_fees" in out.columns
        and "taxes" not in out.columns
    ):
        out["taxes"] = pd.to_numeric(
            out["taxes_fees"],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Numeric fare fields
    # --------------------------------------------------------

    for column in (
        "base_fare",
        "taxes",
        "fees",
        "total_fare",
        "consumer_fare",
        "advance_days",
    ):
        if column in out.columns:
            out[column] = pd.to_numeric(
                out[column],
                errors="coerce",
            )

    # --------------------------------------------------------
    # Consumer fare
    #
    # Only construct it when it does not already exist.
    # --------------------------------------------------------

    if (
        "consumer_fare" not in out.columns
        and {
            "base_fare",
            "taxes",
        }.issubset(out.columns)
    ):
        out["consumer_fare"] = (
            out["base_fare"].fillna(0)
            + out["taxes"].fillna(0)
        )

    # --------------------------------------------------------
    # Datetime fields
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Preserve departure_time exactly as source field.
    #
    # Important for the T1/T2/T3/T4 differentiator.
    # --------------------------------------------------------

    if "departure_time" in out.columns:
        out["departure_time"] = (
            out["departure_time"]
            .astype("string")
            .str.strip()
        )

    return out


# ============================================================
# ARROW / MEMORY OPTIMISATION
# ============================================================

def _read_parquet_memory_efficient(
    path: str | Path,
) -> pd.DataFrame:
    """
    Read Parquet using pandas Arrow-backed dtypes when
    supported by the installed pandas version.

    Falls back to normal pandas dtypes if Arrow-backed
    dtype support is unavailable.
    """

    path = str(path)

    try:
        return pd.read_parquet(
            path,
            engine="pyarrow",
            dtype_backend="pyarrow",
        )

    except TypeError:
        return pd.read_parquet(
            path,
            engine="pyarrow",
        )


# ============================================================
# R2 CLIENT
# ============================================================

@st.cache_resource(
    show_spinner=False
)
def _get_r2_client():
    """
    Create a single cached Cloudflare R2 S3 client.
    """

    if not all(
        [
            R2_ACCOUNT_ID,
            R2_ACCESS_KEY_ID,
            R2_SECRET_ACCESS_KEY,
            R2_BUCKET,
            R2_ENDPOINT_URL,
        ]
    ):
        return None

    try:
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )

    except Exception as exc:
        raise RuntimeError(
            "Unable to initialise Cloudflare R2 client. "
            "Check R2 environment variables."
        ) from exc


# ============================================================
# R2 PARQUET DOWNLOAD
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def _download_r2_parquet_to_temp() -> str:
    """
    Download the small processed Parquet object from R2
    into the container's temporary directory.

    The Parquet is approximately a few MB, unlike the raw
    historical JSON which is hundreds of MB.
    """

    client = _get_r2_client()

    if client is None:
        raise RuntimeError(
            "Cloudflare R2 credentials are not configured."
        )

    try:
        temp_dir = Path(
            tempfile.gettempdir()
        ) / "airfarex"

        temp_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        local_path = (
            temp_dir
            / "clean_airfare_observations.parquet"
        )

        client.download_file(
            R2_BUCKET,
            R2_CLEAN_PARQUET_KEY,
            str(local_path),
        )

        return str(local_path)

    except Exception as exc:
        raise RuntimeError(
            "Unable to download processed airfare "
            "Parquet from Cloudflare R2.\n\n"
            f"Bucket: {R2_BUCKET}\n"
            f"Object: {R2_CLEAN_PARQUET_KEY}\n"
            f"Endpoint: {R2_ENDPOINT_URL}\n\n"
            f"Error: {exc}"
        ) from exc


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def _load_r2_clean_data() -> pd.DataFrame:
    """
    Load the processed clean observation layer from R2.
    """

    parquet_path = (
        _download_r2_parquet_to_temp()
    )

    df = _read_parquet_memory_efficient(
        parquet_path
    )

    return _normalise_observation_columns(
        df
    )


# ============================================================
# LOCAL PROCESSED DATA
# ============================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def _load_local_clean_parquet() -> pd.DataFrame:
    """
    Load local Parquet observation layer.
    """

    df = _read_parquet_memory_efficient(
        LOCAL_PARQUET_PATH
    )

    return _normalise_observation_columns(
        df
    )


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def _load_local_clean_csv() -> pd.DataFrame:
    """
    Compatibility fallback for environments where
    Parquet is not present.
    """

    df = pd.read_csv(
        LOCAL_CSV_PATH,
        low_memory=False,
    )

    return _normalise_observation_columns(
        df
    )


# ============================================================
# RAW OBSERVATIONS
# ============================================================

def load_raw_observations() -> pd.DataFrame:
    """
    Load raw observations only when the raw historical JSON
    is locally available.

    IMPORTANT:
    The 263 MB historical raw JSON is intentionally NOT loaded
    on Render. This prevents the dashboard from exhausting
    memory during startup.

    The raw JSON remains an archival/source object in R2.
    """

    if not RAW_JSON_PATH.exists():
        return pd.DataFrame()

    try:
        with RAW_JSON_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            "Unable to read raw airfare dataset:\n"
            f"{RAW_JSON_PATH}"
        ) from exc

    if isinstance(
        payload,
        dict,
    ):
        records = payload.get(
            "raw_fares",
            [],
        )

    elif isinstance(
        payload,
        list,
    ):
        records = payload

    else:
        records = []

    if not records:
        return pd.DataFrame()

    return _normalise_observation_columns(
        pd.DataFrame(records)
    )


# ============================================================
# FRIEND API FALLBACK
# ============================================================

FRIEND_API_URL = (
    "https://mospi-apix-api.onrender.com/"
    "api/fares/raw"
)

FRIEND_API_TIMEOUT = 120
FRIEND_API_RETRIES = 3


@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def _load_friend_api_observations() -> pd.DataFrame:
    """
    Last-resort fallback.

    This intentionally does NOT attempt to download the entire
    historical API universe. It retrieves the most recent API
    page only.

    The production Render dashboard should use R2 Parquet.
    """

    import requests

    try:
        response = requests.get(
            FRIEND_API_URL,
            params={
                "hours_back": 24,
                "page": 1,
                "size": 50000,
            },
            timeout=FRIEND_API_TIMEOUT,
        )

        response.raise_for_status()

        payload = response.json()

    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        raise RuntimeError(
            "Unable to fetch airfare observations "
            "from Friend API.\n"
            f"{FRIEND_API_URL}\n\n"
            f"Error: {exc}"
        ) from exc

    if isinstance(
        payload,
        list,
    ):
        records = payload

    elif isinstance(
        payload,
        dict,
    ):
        if isinstance(
            payload.get("data"),
            list,
        ):
            records = payload["data"]

        elif isinstance(
            payload.get("raw_fares"),
            list,
        ):
            records = payload["raw_fares"]

        elif isinstance(
            payload.get("fares"),
            list,
        ):
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


# ============================================================
# MAIN OBSERVATION LOADER
# ============================================================

def load_clean_data(
    mode: str = "real",
) -> pd.DataFrame:
    """
    Load the dashboard observation universe.

    REAL DATA PRIORITY:

    1. Local processed Parquet
    2. Local processed CSV
    3. Cloudflare R2 processed Parquet
    4. Local raw JSON
    5. Limited Friend API fallback

    The statistical methodology is not changed here.
    This function only controls where the dashboard obtains
    its observation layer.
    """

    if mode.lower() == "real":

        # ----------------------------------------------------
        # 1. Local Parquet
        # ----------------------------------------------------

        if LOCAL_PARQUET_PATH.exists():
            return _load_local_clean_parquet()

        # ----------------------------------------------------
        # 2. Local CSV
        # ----------------------------------------------------

        if LOCAL_CSV_PATH.exists():
            return _load_local_clean_csv()

        # ----------------------------------------------------
        # 3. Cloudflare R2 Parquet
        # ----------------------------------------------------

        if (
            R2_ACCOUNT_ID
            and R2_ACCESS_KEY_ID
            and R2_SECRET_ACCESS_KEY
        ):
            try:
                return _load_r2_clean_data()

            except Exception as exc:
                st.warning(
                    "Cloudflare R2 processed dataset could "
                    "not be loaded. Falling back to the "
                    "next available source.\n\n"
                    f"{exc}"
                )

        # ----------------------------------------------------
        # 4. Local raw JSON
        #
        # This is primarily for local development.
        # ----------------------------------------------------

        if RAW_JSON_PATH.exists():

            raw_df = (
                load_raw_observations()
            )

            if not raw_df.empty:
                return raw_df

        # ----------------------------------------------------
        # 5. Limited Friend API fallback
        # ----------------------------------------------------

        return (
            _load_friend_api_observations()
        )

    # ========================================================
    # SYNTHETIC DATA
    # ========================================================

    path = _path(
        "synthetic",
        "clean_airfare_observations.csv",
    )

    if not path.exists():
        raise FileNotFoundError(
            "Dashboard dataset not found:\n"
            f"{path}"
        )

    return _normalise_observation_columns(
        pd.read_csv(
            path,
            low_memory=False,
        )
    )


# ============================================================
# DAILY INDEX
# ============================================================

def load_daily_index(
    mode: str = "real",
) -> pd.DataFrame:

    if mode.lower() == "real":

        path = _index_path(
            "real",
            "real_daily_airfare_index.csv",
        )

    else:

        path = _index_path(
            "synthetic",
            "daily_airfare_index.csv",
        )

    if not path.exists():
        raise FileNotFoundError(
            "Daily index file not found:\n"
            f"{path}"
        )

    return _normalise_daily_index_columns(
        pd.read_csv(path)
    )


# ============================================================
# ROUTE INDICES
# ============================================================

def load_route_indices(
    mode: str = "real",
) -> pd.DataFrame:

    if mode.lower() == "real":

        path = _index_path(
            "real",
            "real_route_indices.csv",
        )

    else:

        path = _index_path(
            "synthetic",
            "route_indices.csv",
        )

    if not path.exists():
        raise FileNotFoundError(
            "Route index file not found:\n"
            f"{path}"
        )

    df = pd.read_csv(path)

    if "collection_date" in df.columns:

        df[
            "collection_date"
        ] = pd.to_datetime(
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

        path = _index_path(
            "real",
            "real_lead_time_contributions.csv",
        )

    else:

        path = _index_path(
            "synthetic",
            "advance_window_indices.csv",
        )

    if not path.exists():
        raise FileNotFoundError(
            "Lead-time index file not found:\n"
            f"{path}"
        )

    return _normalise_lead_time_columns(
        pd.read_csv(path)
    )


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

        df[
            "collection_date"
        ] = pd.to_datetime(
            df["collection_date"],
            errors="coerce",
        )

    return df


# ============================================================
# REAL COVERAGE
# ============================================================

def load_real_coverage() -> pd.DataFrame:

    path = (
        REAL_INDEX_DIR
        / "real_coverage_report.csv"
    )

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "collection_date" in df.columns:

        df[
            "collection_date"
        ] = pd.to_datetime(
            df["collection_date"],
            errors="coerce",
        )

    return df


# ============================================================
# REAL METADATA
# ============================================================

def load_real_metadata() -> dict:

    path = (
        REAL_INDEX_DIR
        / "real_index_metadata.json"
    )

    if not path.exists():
        return {}

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}