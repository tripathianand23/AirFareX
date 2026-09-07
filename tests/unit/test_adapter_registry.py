import pytest

from src.airfare_ml.data.adapters.registry import (
    create_adapter,
    get_adapter_class,
)
from src.airfare_ml.data.adapters.sample_adapter import (
    SampleSourceAdapter,
)


def test_get_sample_adapter_class():
    adapter_class = get_adapter_class("sample")

    assert adapter_class is SampleSourceAdapter


def test_create_sample_adapter():
    adapter = create_adapter("sample")

    assert isinstance(
        adapter,
        SampleSourceAdapter,
    )


def test_unknown_adapter_rejected():
    with pytest.raises(
        KeyError,
        match="Unknown adapter",
    ):
        get_adapter_class("does_not_exist")


def test_empty_adapter_name_rejected():
    with pytest.raises(
        ValueError,
        match="adapter_name",
    ):
        get_adapter_class("")