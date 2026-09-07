import json

from src.airfare_ml.data.raw_storage import (
    RAW_SCHEMA_VERSION,
    calculate_payload_hash,
    create_raw_record,
    generate_raw_record_id,
    load_raw_record,
    save_raw_record,
)


def test_payload_hash_is_deterministic():

    payload_a = {
        "flight": "6E123",
        "price": 5800,
    }

    payload_b = {
        "price": 5800,
        "flight": "6E123",
    }

    assert calculate_payload_hash(payload_a) == (
        calculate_payload_hash(payload_b)
    )


def test_payload_hash_changes_when_payload_changes():

    payload_a = {
        "flight": "6E123",
        "price": 5800,
    }

    payload_b = {
        "flight": "6E123",
        "price": 5900,
    }

    assert calculate_payload_hash(payload_a) != (
        calculate_payload_hash(payload_b)
    )


def test_raw_record_creation():

    payload = {
        "flight": "6E123",
        "price": 5800,
    }

    record = create_raw_record(
        source="sample",
        payload=payload,
        collection_timestamp="2026-09-03T10:00:00",
        request_id="search_001",
        source_url="https://example.com",
        ingestion_timestamp="2026-09-03T10:01:00",
    )

    assert record.source == "sample"
    assert record.payload == payload
    assert record.request_id == "search_001"
    assert record.source_url == "https://example.com"
    assert record.schema_version == RAW_SCHEMA_VERSION
    assert len(record.payload_hash) == 64
    assert len(record.raw_record_id) == 64


def test_raw_record_id_is_deterministic():

    payload = {
        "flight": "6E123",
        "price": 5800,
    }

    payload_hash = calculate_payload_hash(payload)

    id_a = generate_raw_record_id(
        source="sample",
        collection_timestamp="2026-09-03T10:00:00",
        payload_hash=payload_hash,
    )

    id_b = generate_raw_record_id(
        source="sample",
        collection_timestamp="2026-09-03T10:00:00",
        payload_hash=payload_hash,
    )

    assert id_a == id_b


def test_save_and_load_raw_record(tmp_path):

    payload = {
        "flight": "6E123",
        "price": 5800,
    }

    record = create_raw_record(
        source="sample",
        payload=payload,
        collection_timestamp="2026-09-03T10:00:00",
        request_id="search_001",
        ingestion_timestamp="2026-09-03T10:01:00",
    )

    path = save_raw_record(
        record,
        root_dir=tmp_path,
    )

    assert path.exists()

    loaded = load_raw_record(path)

    assert loaded == record


def test_saved_file_is_valid_json(tmp_path):

    payload = {
        "flight": "6E123",
        "price": 5800,
    }

    record = create_raw_record(
        source="sample",
        payload=payload,
        collection_timestamp="2026-09-03T10:00:00",
        ingestion_timestamp="2026-09-03T10:01:00",
    )

    path = save_raw_record(
        record,
        root_dir=tmp_path,
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    assert data["source"] == "sample"
    assert data["payload"] == payload
    assert data["payload_hash"] == record.payload_hash