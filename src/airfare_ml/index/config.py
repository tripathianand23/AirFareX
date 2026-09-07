from dataclasses import dataclass


ADVANCE_WINDOWS = [1, 7, 15, 30, 45]


# PROVISIONAL DEVELOPMENT WEIGHTS
#
# These are NOT official DGCA weights.
# They are only being used to develop and test
# the index engine until real traffic-based weights
# are provided.

ROUTE_WEIGHTS = {
    "DEL_BOM": 0.20,
    "DEL_BLR": 0.20,
    "BOM_BLR": 0.15,
    "DEL_CCU": 0.10,
    "BLR_HYD": 0.10,
    "MAA_DEL": 0.10,
    "BOM_DEL": 0.05,
    "BLR_DEL": 0.04,
    "HYD_DEL": 0.03,
    "CCU_DEL": 0.03,
}


@dataclass(frozen=True)
class IndexConfig:
    base_index: float = 100.0
    representative_stat: str = "median"
    min_route_observations: int = 1
    missing_route_policy: str = "exclude_and_renormalize"


def validate_route_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise ValueError("Route weights cannot be empty.")

    if any(weight < 0 for weight in weights.values()):
        raise ValueError("Route weights cannot be negative.")

    total = sum(weights.values())

    if total <= 0:
        raise ValueError("Sum of route weights must be greater than zero.")

    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            f"Route weights must sum to 1.0, got {total:.6f}"
        )


validate_route_weights(ROUTE_WEIGHTS)
