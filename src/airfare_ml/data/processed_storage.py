from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.airfare_ml.data.provenance import validate_provenance
from src.airfare_ml.data.schema import add_missing_optional_columns, enforce_column_order


class ProcessedStorageError(Exception):
    """Raised when processed observation storage cannot be completed."""


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ProcessedStorageError(
            f"Missing required columns for processed storage: {missing}"
        )


def prepare_observations_for_storage(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and standardize canonical observations before persistence."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    _require_columns(df, ["collection_timestamp", "source", "ingestion_timestamp"])

    prepared = add_missing_optional_columns(df.copy())
    prepared = enforce_column_order(prepared)
    validate_provenance(prepared)

    prepared["collection_timestamp"] = pd.to_datetime(
        prepared["collection_timestamp"], errors="raise", utc=True
    )
    prepared["ingestion_timestamp"] = pd.to_datetime(
        prepared["ingestion_timestamp"], errors="raise", utc=True
    )
    prepared["collection_date"] = prepared["collection_timestamp"].dt.date.astype(str)
    return prepared


def save_processed_observations(
    df: pd.DataFrame,
    *,
    root_dir: str | Path = "data/processed/observations",
    source: str | None = None,
    collection_date: str | None = None,
) -> Path:
    """Persist one source/date partition as Parquet."""
    prepared = prepare_observations_for_storage(df)

    sources = prepared["source"].dropna().astype(str).unique().tolist()
    if source is not None:
        if not source.strip():
            raise ValueError("source must not be empty.")
        if sources != [source]:
            raise ProcessedStorageError(
                "When source is supplied, the DataFrame must contain only that source."
            )
    else:
        if len(sources) != 1:
            raise ProcessedStorageError(
                "Processed storage requires one source per partition."
            )
        source = sources[0]

    dates = prepared["collection_date"].unique().tolist()
    if collection_date is not None:
        if not collection_date.strip():
            raise ValueError("collection_date must not be empty.")
        if dates != [collection_date]:
            raise ProcessedStorageError(
                "When collection_date is supplied, the DataFrame must contain only that date."
            )
    else:
        if len(dates) != 1:
            raise ProcessedStorageError(
                "Processed storage requires one collection date per partition."
            )
        collection_date = dates[0]

    output_dir = (
        Path(root_dir) / f"source={source}" / f"collection_date={collection_date}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    final_path = output_dir / "observations.parquet"
    temp_path = output_dir / "observations.tmp.parquet"

    try:
        prepared.to_parquet(temp_path, index=False)
        temp_path.replace(final_path)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise ProcessedStorageError(
            f"Unable to persist processed observations: {exc}"
        ) from exc

    return final_path


def load_processed_observations(path: str | Path) -> pd.DataFrame:
    """Load a persisted processed-observation Parquet file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    return prepare_observations_for_storage(pd.read_parquet(path))
