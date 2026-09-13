from __future__ import annotations

from pathlib import Path

import json

import pandas as pd


class RealAirfareJsonAdapter:
    """
    Adapter for the scraper's airfare_index.json structure.

    Supported structures:

    1. Object format:
    {
        "daily_index": [...],
        "raw_fares": [...]
    }

    2. Array format:
    [
        {...},
        {...}
    ]

    Only raw airfare observations are converted into the
    standardized AirfareX observation format.
    """

    source_name = "real_scraper"

    def parse_file(self, path: str | Path) -> pd.DataFrame:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"Raw airfare file not found: {path}"
            )

        # ---------------------------------------------------------
        # LOAD JSON
        # ---------------------------------------------------------
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        # ---------------------------------------------------------
        # SUPPORT BOTH JSON FORMATS
        # ---------------------------------------------------------
        #
        # Format A:
        # {
        #     "daily_index": [...],
        #     "raw_fares": [...]
        # }
        #
        # Format B:
        # [
        #     {...},
        #     {...}
        # ]
        #
        if isinstance(payload, list):
            raw_fares = payload

        elif isinstance(payload, dict):
            if "raw_fares" not in payload:
                raise ValueError(
                    "Missing required 'raw_fares' section."
                )

            raw_fares = payload["raw_fares"]

        else:
            raise ValueError(
                "Expected top-level JSON object or array."
            )

        # ---------------------------------------------------------
        # VALIDATE RAW FARES
        # ---------------------------------------------------------
        if not isinstance(raw_fares, list):
            raise ValueError(
                "'raw_fares' must be a list."
            )

        if not raw_fares:
            raise ValueError(
                "'raw_fares' is empty."
            )

        # ---------------------------------------------------------
        # CONVERT RAW RECORDS
        # ---------------------------------------------------------
        records = []

        for row in raw_fares:

            if not isinstance(row, dict):
                continue

            # -----------------------------------------------------
            # ROUTE
            # -----------------------------------------------------
            route = str(
                row.get("route", "")
            ).strip()

            if "-" in route:
                origin, destination = route.split(
                    "-", 1
                )
            else:
                origin = ""
                destination = ""

            # -----------------------------------------------------
            # COLLECTION TIMESTAMP
            # -----------------------------------------------------
            timestamp = row.get("timestamp")

            if timestamp:
                collection_timestamp = pd.to_datetime(
                    timestamp,
                    errors="coerce"
                )
            else:
                collection_timestamp = pd.NaT

            # -----------------------------------------------------
            # ADVANCE WINDOW
            # -----------------------------------------------------
            advance_days = pd.to_numeric(
                row.get("advance_window_days"),
                errors="coerce"
            )

            # -----------------------------------------------------
            # TRAVEL DATE
            # -----------------------------------------------------
            travel_date = pd.NaT

            if (
                pd.notna(collection_timestamp)
                and pd.notna(advance_days)
            ):
                travel_date = (
                    collection_timestamp.normalize()
                    + pd.Timedelta(
                        days=int(advance_days)
                    )
                )

            # -----------------------------------------------------
            # FARES
            # -----------------------------------------------------
            base_fare = pd.to_numeric(
                row.get("base_fare"),
                errors="coerce"
            )

            taxes_fees = pd.to_numeric(
                row.get("taxes_fees"),
                errors="coerce"
            )

            total_fare = pd.to_numeric(
                row.get("total_fare"),
                errors="coerce"
            )

            ota_source = str(
                row.get("ota_source", self.source_name)
            ).strip()

            if ota_source.lower() == "cleartrip":
                if pd.notna(base_fare) and base_fare == 0:
                    base_fare = float("nan")

                if pd.notna(taxes_fees) and taxes_fees == 0:
                    taxes_fees = float("nan")

            # -----------------------------------------------------
            # STANDARDIZED AIRFARE OBSERVATION
            # -----------------------------------------------------
            records.append(
                {
                    "collection_timestamp":
                        collection_timestamp,

                    "source": ota_source,

                    "origin":
                        origin.strip().upper(),

                    "destination":
                        destination.strip().upper(),

                    "travel_date":
                        travel_date,

                    "airline": str(
                        row.get("airline", "")
                    ).strip(),

                    "flight_number": None,
                    "departure_time": None,
                    "arrival_time": None,
                    "fare_class": None,
                    "cabin": None,
                    "stops": None,

                    "advance_days":
                        advance_days,

                    "base_fare":
                        base_fare,

                    "taxes":
                        taxes_fees,

                    "fees": 0.0,

                    "total_fare":
                        total_fare,

                    "currency": "INR",

                    "availability":
                        "available",

                    "baggage": None,
                    "refundable": None,
                    "changeable": None,
                    "fare_basis": None,
                    "offer_id": None,
                    "search_id": None,
                    "source_url": None,

                    "raw_record_id": (
                        f"{self.source_name}:"
                        f"{row.get('id')}"
                    ),

                    "ingestion_timestamp":
                        pd.Timestamp.utcnow(),
                }
            )

        # ---------------------------------------------------------
        # CREATE DATAFRAME
        # ---------------------------------------------------------
        df = pd.DataFrame(records)

        if df.empty:
            raise ValueError(
                "Adapter produced zero observations."
            )

        return df