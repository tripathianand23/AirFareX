import pytest

from src.airfare_ml.data.source_registry import (
    build_default_registry,
    get_source_config,
)


def test_default_registry_contains_sample_source():
    registry = build_default_registry()

    assert "sample" in registry
    assert registry["sample"].adapter == "sample"
    assert registry["sample"].enabled is True


def test_get_source_config():
    registry = build_default_registry()

    config = get_source_config(
        "sample",
        registry,
    )

    assert config.name == "sample"
    assert config.adapter == "sample"


def test_unknown_source_rejected():
    registry = build_default_registry()

    with pytest.raises(
        KeyError,
        match="Unknown source",
    ):
        get_source_config(
            "does_not_exist",
            registry,
        )