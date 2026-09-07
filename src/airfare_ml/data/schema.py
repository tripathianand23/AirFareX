from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd


CANONICAL_COLUMNS = [
    "collection_timestamp",
    "source",
    "origin",
    "destination",
    "travel_date",
    "airline",
    
    "departure_time",
    "arrival_time",
    "fare_class",
    "cabin",
    "stops",
    "advance_days",
    "base_fare",
    "taxes",
    "fees",
    "total_fare",
    "currency",
    "availability",
    "baggage",
    "refundable",
    "changeable",
    "fare_basis",
    "offer_id",
    "search_id",
    "source_url",
    "raw_record_id",
    "ingestion_timestamp",
]


REQUIRED_COLUMNS = [
    "collection_timestamp",
    "source",
    "origin",
    "destination",
    "travel_date",
    "airline",
    "advance_days",
    "base fare",
    "currency",
    "ingestion_timestamp",
]


OPTIONAL_COLUMNS = [
    column
    for column in CANONICAL_COLUMNS
    if column not in REQUIRED_COLUMNS
]


def validate_schema(df: pd.DataFrame) -> None:
    """
    Validate that a dataframe follows the canonical airfare schema.

    Raises:
        TypeError: if input is not a pandas DataFrame.
        ValueError: if required columns are missing.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame.")

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required canonical columns: {missing}"
        )


def add_missing_optional_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add optional canonical columns that are absent.

    Existing columns are never overwritten.
    """

    result = df.copy()

    for column in OPTIONAL_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA

    return result[CANONICAL_COLUMNS]


def enforce_column_order(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return dataframe using the canonical column order.

    Raises:
        ValueError: if required columns are missing.
    """

    validate_schema(df)

    result = df.copy()

    for column in OPTIONAL_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA

    return result[CANONICAL_COLUMNS]