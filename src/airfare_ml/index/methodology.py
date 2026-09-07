"""
Methodological configuration for the Airfare Price Index.

This module contains explicit, configurable assumptions used by the
index calculation pipeline.

Important:
    These settings represent the current proposed methodology for the
    SIH prototype. They are NOT official MoSPI/CPI methodology.
"""

from dataclasses import dataclass
from typing import Literal


RepresentativeFareMethod = Literal[
    "median",
    "trimmed_mean",
]


MissingRoutePolicy = Literal[
    "exclude_and_renormalize",
    "require_complete",
]


BasePeriodMethod = Literal[
    "first_observation",
    "calendar_month",
]


@dataclass(frozen=True)
class IndexMethodology:
    advance_windows: tuple[int, ...] = (1, 7, 15, 30, 45)

    representative_fare_method: RepresentativeFareMethod = "median"

    lead_time_weighting: Literal["equal"] = "equal"

    missing_route_policy: MissingRoutePolicy = (
        "exclude_and_renormalize"
    )

    minimum_observations_per_stratum: int = 1

    base_period_method: BasePeriodMethod = (
        "first_observation"
    )

    base_period: str | None = None

    index_base: float = 100.0


DEFAULT_INDEX_METHODOLOGY = IndexMethodology()