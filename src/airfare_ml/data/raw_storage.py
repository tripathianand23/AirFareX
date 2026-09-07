from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RAW_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class RawRecord:
    """
    Immutable representation of a raw source response.

    The payload is intentionally preserved without normalization.
    """

    raw_record_id: str
    source: str
    collection_timestamp: str
    ingestion_timestamp: str
    request_id: str | None
    source_url: str | None
    payload_hash: str
    schema_version: str
    payload: Any


def _canonical_json(payload: Any) -> str:
    """
    Serialize a payload deterministically.

    This ensures semantically identical JSON objects produce
    the same hash even when dictionary key order differs.
    """

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def calculate_payload_hash(payload: Any) -> str:
    """
    Calculate a SHA-256 hash of the canonical payload representation.
    """

    canonical = _canonical_json(payload)

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def generate_raw_record_id(
    source: str,
    collection_timestamp: str,
    payload_hash: str,
) -> str:
    """
    Generate a deterministic raw record identifier.
    """

    value = (
        f"{source}|"
        f"{collection_timestamp}|"
        f"{payload_hash}"
    )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def create_raw_record(
    *,
    source: str,
    payload: Any,
    collection_timestamp: str,
    request_id: str | None = None,
    source_url: str | None = None,
    ingestion_timestamp: str | None = None,
) -> RawRecord:
    """
    Create a RawRecord while preserving the original payload.
    """

    payload_hash = calculate_payload_hash(payload)

    raw_record_id = generate_raw_record_id(
        source=source,
        collection_timestamp=collection_timestamp,
        payload_hash=payload_hash,
    )

    if ingestion_timestamp is None:
        ingestion_timestamp = datetime.now(
            timezone.utc
        ).isoformat()

    return RawRecord(
        raw_record_id=raw_record_id,
        source=source,
        collection_timestamp=collection_timestamp,
        ingestion_timestamp=ingestion_timestamp,
        request_id=request_id,
        source_url=source_url,
        payload_hash=payload_hash,
        schema_version=RAW_SCHEMA_VERSION,
        payload=payload,
    )


def save_raw_record(
    record: RawRecord,
    root_dir: str | Path = "data/raw",
) -> Path:
    """
    Save a raw record as JSON.

    Records are partitioned by source and collection date.
    """

    root = Path(root_dir)

    collection_date = (
        record.collection_timestamp[:10]
    )

    output_dir = (
        root
        / record.source
        / collection_date
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{record.raw_record_id}.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            asdict(record),
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    return output_path


def load_raw_record(
    path: str | Path,
) -> RawRecord:
    """
    Load a previously stored raw record.
    """

    path = Path(path)

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return RawRecord(**data)