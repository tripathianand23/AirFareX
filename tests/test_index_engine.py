import pandas as pd
import pytest

from src.airfare_ml.index.aggregation import (
    aggregate_daily_route_fares,
)

from src.airfare_ml.index.calculation import (
    calculate_route_indices,
    calculate_weighted_index,
)

from src.airfare_ml.index.validation import (
    validate_weights,
    validate_route_indices,
    validate_weighted_index,
)


def make_test_data():
    return pd.DataFrame(
        {
            "collection_timestamp": [
                "2026-07-01 10:00:00",
                "2026-07-01 11:00:00",
                "2026-07-01 10:00:00",
                "2026-07-02 10:00:00",
            ],
            "origin": [
                "DEL",
                "DEL",
                "BOM",
                "DEL",
            ],
            "destination": [
                "BOM",
                "BOM",
                "BLR",
                "BOM",
            ],
            "advance_days": [
                1,
                1,
                1,
                1,
            ],
            "total_fare": [
                8000,
                9000,
                7000,
                8800,
            ],
        }
    )


def test_weights_sum_to_one():
    result = validate_weights()

    assert result["weights_valid"] is True
    assert result["negative_weights"] is False


def test_daily_aggregation_uses_median():
    df = make_test_data()

    result = aggregate_daily_route_fares(df)

    del_bom = result[
        (result["route"] == "DEL_BOM")
        & (result["advance_days"] == 1)
    ]

    assert len(del_bom) == 2

    first_day = del_bom.iloc[0]

    assert first_day["representative_fare"] == 8500


def test_route_index_base_is_100():
    df = make_test_data()

    daily = aggregate_daily_route_fares(df)

    indices = calculate_route_indices(daily)

    first_observation = (
        indices[
            (indices["route"] == "DEL_BOM")
            & (indices["advance_days"] == 1)
        ]
        .sort_values("collection_date")
        .iloc[0]
    )

    assert first_observation["route_index"] == pytest.approx(
        100.0
    )


def test_route_index_increases_when_price_increases():
    df = make_test_data()

    daily = aggregate_daily_route_fares(df)

    indices = calculate_route_indices(daily)

    del_bom = indices[
        (indices["route"] == "DEL_BOM")
        & (indices["advance_days"] == 1)
    ].sort_values("collection_date")

    assert (
        del_bom.iloc[1]["route_index"]
        > del_bom.iloc[0]["route_index"]
    )


def test_weighted_index_is_positive():
    df = make_test_data()

    daily = aggregate_daily_route_fares(df)

    route_indices = calculate_route_indices(daily)

    weighted = calculate_weighted_index(
        route_indices
    )

    assert (weighted["airfare_index"] > 0).all()


def test_route_index_validation():
    df = make_test_data()

    daily = aggregate_daily_route_fares(df)

    indices = calculate_route_indices(daily)

    checks = validate_route_indices(indices)

    assert checks["all_passed"] is True


def test_weighted_index_validation():
    df = make_test_data()

    daily = aggregate_daily_route_fares(df)

    route_indices = calculate_route_indices(daily)

    weighted = calculate_weighted_index(
        route_indices
    )

    checks = validate_weighted_index(weighted)

    assert checks["all_passed"] is True