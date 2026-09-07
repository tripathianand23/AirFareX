from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


PROVENANCE_COLUMNS = [
    "raw_record_id",
    "source",
    "collection_timestamp",
    "ingestion_timestamp",
]


@dataclass(frozen=True)
class ProvenanceMetadata:
    raw_record_id: str
    source: str
    collection_timestamp: str
    ingestion_timestamp: str


def attach_provenance(
    df: pd.DataFrame,
    metadata: ProvenanceMetadata,
) -> pd.DataFrame:
    """
    Attach raw-response provenance metadata to canonical observations.

    Every observation generated from the same raw response receives
    the same raw_record_id.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    if not metadata.raw_record_id:
        raise ValueError("raw_record_id must not be empty.")

    if not metadata.source:
        raise ValueError("source must not be empty.")

    result = df.copy()

    result["raw_record_id"] = metadata.raw_record_id
    result["source"] = metadata.source
    result["collection_timestamp"] = metadata.collection_timestamp
    result["ingestion_timestamp"] = metadata.ingestion_timestamp

    return result


def validate_provenance(df: pd.DataFrame) -> None:
    """
    Validate that every observation contains usable provenance.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    missing = [
        column
        for column in PROVENANCE_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing provenance columns: {missing}"
        )

    for column in PROVENANCE_COLUMNS:
        if df[column].isna().any():
            raise ValueError(
                f"Provenance column '{column}' contains missing values."
            )

        if (df[column].astype(str).str.strip() == "").any():
            raise ValueError(
                f"Provenance column '{column}' contains empty values."
            )


def get_raw_record_ids(df: pd.DataFrame) -> list[str]:
    """
    Return unique raw_record_ids represented by the observations.
    """
    validate_provenance(df)

    return (
        df["raw_record_id"]
        .astype(str)
        .drop_duplicates()
        .tolist()
    )