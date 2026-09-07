from __future__ import annotations

import pandas as pd

from src.airfare_ml.data.adapters.base import BaseSourceAdapter


class SampleSourceAdapter(BaseSourceAdapter):
    """
    Sample adapter used only for testing the source-adapter architecture.
    """

    source_name = "sample"

    def parse(self, raw_data) -> pd.DataFrame:
        if not isinstance(raw_data, list):
            raise TypeError("raw_data must be a list of dictionaries.")

        records = []

        for item in raw_data:
            records.append(
                {
                    "collection_timestamp": item["collected_at"],
                    "source": self.source_name,
                    "origin": item["from"],
                    "destination": item["to"],
                    "travel_date": item["flight_date"],
                    "airline": item["carrier"],
                    "flight_number": item.get("flight_no"),
                    "departure_time": item.get("departure_time"),
                    "arrival_time": item.get("arrival_time"),
                    "fare_class": item.get("fare_class"),
                    "cabin": item.get("cabin"),
                    "stops": item.get("stops"),
                    "advance_days": item["advance_days"],
                    "base_fare": item.get("base_fare"),
                    "taxes": item.get("taxes"),
                    "fees": item.get("fees"),
                    "total_fare": item["price"],
                    "currency": item.get("currency", "INR"),
                    "availability": item.get("availability"),
                    "baggage": item.get("baggage"),
                    "refundable": item.get("refundable"),
                    "changeable": item.get("changeable"),
                    "fare_basis": item.get("fare_basis"),
                    "offer_id": item.get("offer_id"),
                    "search_id": item.get("search_id"),
                    "source_url": item.get("source_url"),
                    "raw_record_id": item.get("raw_record_id"),
                    "ingestion_timestamp": item.get(
                        "ingestion_timestamp"
                    ),
                }
            )

        return pd.DataFrame(records)