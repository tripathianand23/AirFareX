from __future__ import annotations

from src.airfare_ml.data.source_config import (
    SourceConfig,
    create_source_registry,
)


DEFAULT_SOURCE_CONFIGS = [
    SourceConfig(
        name="sample",
        adapter="sample",
        enabled=True,
    ),
]


def build_default_registry():
    """
    Build the project's default source registry.

    Real production sources will be added only after
    their access method and response structure are verified.
    """
    return create_source_registry(DEFAULT_SOURCE_CONFIGS)


def get_source_config(
    source_name: str,
    registry=None,
) -> SourceConfig:
    """
    Retrieve configuration for a source.
    """
    if registry is None:
        registry = build_default_registry()

    try:
        return registry[source_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown source: {source_name}"
        ) from exc