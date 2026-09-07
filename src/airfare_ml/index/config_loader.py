from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class IndexConfig:
    base_value: float
    base_date: str
    representative_fare_method: str
    route_weighting: str
    lead_time_weighting: str
    advance_windows: tuple[int, ...]
    require_complete_routes: bool
    require_complete_strata: bool
    minimum_route_coverage_ratio: float
    minimum_stratum_coverage_ratio: float
    route_universe: tuple[str, ...]
    official_weights_used: bool


def load_index_config(path: str | Path) -> IndexConfig:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Index configuration file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Configuration must contain a YAML mapping.")

    try:
        index = config["index"]
        coverage = config["coverage"]
        advance_windows_raw = config["advance_windows"]
        route_universe_raw = config["route_universe"]
        weights = config["weights"]
    except KeyError as exc:
        raise ValueError(
            f"Missing required configuration section: {exc}"
        ) from exc

    advance_windows = tuple(
        int(value)
        for value in advance_windows_raw
    )

    route_universe = tuple(
        str(route)
        for route in route_universe_raw
    )

    if not advance_windows:
        raise ValueError("advance_windows cannot be empty.")

    if not route_universe:
        raise ValueError("route_universe cannot be empty.")

    if len(set(advance_windows)) != len(advance_windows):
        raise ValueError(
            "advance_windows must contain unique values."
        )

    if len(set(route_universe)) != len(route_universe):
        raise ValueError(
            "route_universe must contain unique routes."
        )

    route_coverage = float(
        coverage["minimum_route_coverage_ratio"]
    )

    stratum_coverage = float(
        coverage["minimum_stratum_coverage_ratio"]
    )

    if not 0.0 <= route_coverage <= 1.0:
        raise ValueError(
            "minimum_route_coverage_ratio must be between 0 and 1."
        )

    if not 0.0 <= stratum_coverage <= 1.0:
        raise ValueError(
            "minimum_stratum_coverage_ratio must be between 0 and 1."
        )

    return IndexConfig(
        base_value=float(index["base_value"]),
        base_date=str(index["base_date"]),
        representative_fare_method=str(
            index["representative_fare_method"]
        ),
        route_weighting=str(
            index["route_weighting"]
        ),
        lead_time_weighting=str(
            index["lead_time_weighting"]
        ),
        advance_windows=advance_windows,
        require_complete_routes=bool(
            coverage["require_complete_routes"]
        ),
        require_complete_strata=bool(
            coverage["require_complete_strata"]
        ),
        minimum_route_coverage_ratio=route_coverage,
        minimum_stratum_coverage_ratio=stratum_coverage,
        route_universe=route_universe,
        official_weights_used=bool(
            weights["official_weights_used"]
        ),
    )
