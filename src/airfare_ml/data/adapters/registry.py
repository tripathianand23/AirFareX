from __future__ import annotations

from typing import Type

from src.airfare_ml.data.adapters.base import BaseSourceAdapter
from src.airfare_ml.data.adapters.sample_adapter import (
    SampleSourceAdapter,
)


ADAPTER_REGISTRY: dict[str, Type[BaseSourceAdapter]] = {
    "sample": SampleSourceAdapter,
}


def get_adapter_class(
    adapter_name: str,
) -> Type[BaseSourceAdapter]:
    """
    Return the adapter class registered under adapter_name.
    """
    if not adapter_name.strip():
        raise ValueError(
            "adapter_name must not be empty."
        )

    try:
        return ADAPTER_REGISTRY[adapter_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown adapter: {adapter_name}"
        ) from exc


def create_adapter(
    adapter_name: str,
) -> BaseSourceAdapter:
    """
    Instantiate a registered source adapter.
    """
    adapter_class = get_adapter_class(adapter_name)
    return adapter_class()