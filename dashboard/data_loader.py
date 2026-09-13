from __future__ import annotations

from pathlib import Path
import json
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SYNTHETIC_DIR = PROJECT_ROOT / "data" / "processed"
REAL_DIR = PROJECT_ROOT / "data" / "processed" / "real"
REAL_INDEX_DIR = REAL_DIR / "index"
RAW_JSON_PATH = PROJECT_ROOT / "data" / "raw" / "airfare_index.json"


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

def load_clean_data(mode: str = "real") -> pd.DataFrame:
    """
    Load the dashboard observation universe.

    For real data, prefer the complete dashboard observation file when
    available. If it does not exist, fall back to the processed clean file.
    If neither exists, fall back to the complete raw observation universe.

    This prevents the dashboard from silently displaying only the smaller
    deduplicated/processed subset when the complete raw dataset is present.
    """
    if mode.lower() == "real":
        preferred_paths = [
            REAL_DIR / "dashboard_airfare_observations.csv",
            REAL_DIR / "clean_airfare_observations.csv",
        ]

        for path in preferred_paths:
            if path.exists():
                return _normalise_observation_columns(
                    pd.read_csv(path)
                )

        return load_raw_observations()

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
            f"Daily index file not found:\n{path}"
        )

    return _normalise_daily_index_columns(
        pd.read_csv(path)
    )


# ============================================================
# ROUTE INDICES
# ============================================================

def load_route_indices(mode: str = "real") -> pd.DataFrame:
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
            f"Lead-time index file not found:\n{path}"
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
