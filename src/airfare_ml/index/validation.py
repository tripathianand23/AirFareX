import pandas as pd


def validate_weights() -> dict:
    """
    Validate the configured route weights.

    Returns a dictionary so the result can be inspected directly
    by tests and reporting code.
    """
    from .config import ROUTE_WEIGHTS

    weights = list(ROUTE_WEIGHTS.values())

    negative_weights = any(weight < 0 for weight in weights)
    total_weight = sum(weights)

    weights_valid = (
        bool(weights)
        and not negative_weights
        and total_weight > 0
        and abs(total_weight - 1.0) <= 1e-9
    )

    return {
        "weights_valid": weights_valid,
        "negative_weights": negative_weights,
        "total_weight": total_weight,
    }


def validate_route_indices(indices: pd.DataFrame) -> dict:
    """
    Validate route-level index output.
    """
    required_columns = {
        "collection_date",
        "route",
        "advance_days",
        "representative_fare",
        "base_fare",
        "route_index",
    }

    missing_columns = sorted(
        required_columns - set(indices.columns)
    )

    if missing_columns:
        return {
            "all_passed": False,
            "missing_columns": missing_columns,
        }

    numeric_valid = (
        pd.to_numeric(
            indices["route_index"],
            errors="coerce",
        ).notna()
        & (indices["route_index"] > 0)
    ).all()

    base_fare_valid = (
        pd.to_numeric(
            indices["base_fare"],
            errors="coerce",
        ).notna()
        & (indices["base_fare"] > 0)
    ).all()

    all_passed = (
        len(indices) > 0
        and numeric_valid
        and base_fare_valid
    )

    return {
        "all_passed": bool(all_passed),
        "missing_columns": [],
        "positive_route_indices": bool(numeric_valid),
        "positive_base_fares": bool(base_fare_valid),
    }


def validate_weighted_index(weighted: pd.DataFrame) -> dict:
    """
    Validate national weighted airfare index output.
    """
    required_columns = {
        "collection_date",
        "advance_days",
        "airfare_index",
    }

    missing_columns = sorted(
        required_columns - set(weighted.columns)
    )

    if missing_columns:
        return {
            "all_passed": False,
            "missing_columns": missing_columns,
        }

    numeric_valid = pd.to_numeric(
        weighted["airfare_index"],
        errors="coerce",
    ).notna()

    positive_valid = (
        numeric_valid
        & (weighted["airfare_index"] > 0)
    ).all()

    all_passed = (
        len(weighted) > 0
        and positive_valid
    )

    return {
        "all_passed": bool(all_passed),
        "missing_columns": [],
        "positive_airfare_index": bool(positive_valid),
    }
