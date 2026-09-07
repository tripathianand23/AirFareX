import pandas as pd
import pytest

from src.airfare_ml.index.aggregation import (
    aggregate_daily_route_fares,
)
from src.airfare_ml.index.calculation import (
    calculate_route_indices,
    calculate_weighted_index,
)
from src.airfare_ml.index.methodology import (
    DEFAULT_INDEX_METHODOLOGY,
    IndexMethodology,
)
from src.airfare_ml.index.series import (
    build_overall_index,
)


def make_sample_observations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "collection_timestamp": [
                "2026-07-01 10:00:00",
                "2026-07-01 10:05:00",
                "2026-07-02 10:00:00",
                "2026-07-02 10:05:00",
                "2026-07-01 10:00:00",
                "2026-07-01 10:05:00",
                "2026-07-02 10:00:00",
                "2026-07-02 10:05:00",
            ],
            "origin": [
                "DEL",
                "DEL",
                "DEL",
                "DEL",
                "BOM",
                "BOM",
                "BOM",
                "BOM",
            ],
            "destination": [
                "BOM",
                "BOM",
                "BOM",
                "BOM",
                "BLR",
                "BLR",
                "BLR",
                "BLR",
            ],
            "advance_days": [
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,
            ],
            "total_fare": [
                500,
                600,
                550,
                650,
                400,
                500,
                440,
                540,
            ],
        }
    )


def test_representative_fare_is_median():
    observations = make_sample_observations()

    result = aggregate_daily_route_fares(
        observations
    )

    del_bom_day_1 = result[
        (result["route"] == "DEL_BOM")
        & (result["collection_date"] == "2026-07-01")
        & (result["advance_days"] == 1)
    ].iloc[0]

    assert del_bom_day_1["representative_fare"] == 550
    assert del_bom_day_1["observation_count"] == 2


def test_first_observation_is_current_prototype_base():
    observations = make_sample_observations()

    daily = aggregate_daily_route_fares(
        observations
    )

    route_indices = calculate_route_indices(
        daily
    )

    base_rows = route_indices[
        route_indices["collection_date"]
        == pd.Timestamp("2026-07-01")
    ]

    assert not base_rows.empty

    assert all(
    value == pytest.approx(100.0)
    for value in base_rows["route_index"]
    )


def test_index_base_is_configurable():
    observations = make_sample_observations()

    daily = aggregate_daily_route_fares(
        observations
    )

    methodology = DEFAULT_INDEX_METHODOLOGY

    route_indices = calculate_route_indices(
        daily,
        methodology=methodology,
    )

    assert route_indices["route_index"].notna().all()
    assert methodology.index_base == 100.0


def test_missing_routes_are_renormalized():
    observations = make_sample_observations()

    daily = aggregate_daily_route_fares(
        observations
    )

    route_indices = calculate_route_indices(
        daily
    )

    # Keep only one configured route.
    route_indices = route_indices[
        route_indices["route"] == "DEL_BOM"
    ].copy()

    result = calculate_weighted_index(
        route_indices
    )

    assert not result.empty

    # With only one available route, its weight is
    # fully renormalized to 100% of the available weight.
    assert result["airfare_index"].iloc[0] == pytest.approx(
        100.0
    )


def test_equal_lead_time_weighting():
    data = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                [
                    "2026-07-01",
                    "2026-07-01",
                    "2026-07-01",
                ]
            ),
            "advance_days": [1, 7, 15],
            "airfare_index": [
                90.0,
                100.0,
                110.0,
            ],
        }
    )

    result = build_overall_index(data)

    assert len(result) == 1

    assert result[
        "overall_airfare_index"
    ].iloc[0] == pytest.approx(100.0)


def test_calendar_month_base_uses_reference_period_median():
    observations = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                [
                    "2026-07-01",
                    "2026-07-02",
                    "2026-07-03",
                    "2026-08-01",
                ]
            ),
            "route": [
                "DEL_BOM",
                "DEL_BOM",
                "DEL_BOM",
                "DEL_BOM",
            ],
            "advance_days": [
                1,
                1,
                1,
                1,
            ],
            "representative_fare": [
                500.0,
                600.0,
                550.0,
                660.0,
            ],
        }
    )

    methodology = IndexMethodology(
        base_period_method="calendar_month",
        base_period="2026-07",
    )

    result = calculate_route_indices(
        observations,
        methodology=methodology,
    )

    july = result[
        result["collection_date"]
        .dt.to_period("M")
        == "2026-07"
    ]

    august = result[
        result["collection_date"]
        .dt.to_period("M")
        == "2026-08"
    ]

    assert not july.empty
    assert not august.empty

    # July median = median(500, 600, 550) = 550.
    assert july[
    "route_index"
    ].median() == pytest.approx(100.0)

    august_index = august[
        "route_index"
    ].iloc[0]

    assert august_index == pytest.approx(
        660.0 / 550.0 * 100.0
    )


def test_calendar_month_requires_base_period():
    observations = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-07-01"]
            ),
            "route": ["DEL_BOM"],
            "advance_days": [1],
            "representative_fare": [500.0],
        }
    )

    methodology = IndexMethodology(
        base_period_method="calendar_month",
        base_period=None,
    )

    with pytest.raises(
        ValueError,
        match="base_period must be provided",
    ):
        calculate_route_indices(
            observations,
            methodology=methodology,
        )


def test_calendar_month_rejects_missing_reference_period():
    observations = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-07-01"]
            ),
            "route": ["DEL_BOM"],
            "advance_days": [1],
            "representative_fare": [500.0],
        }
    )

    methodology = IndexMethodology(
        base_period_method="calendar_month",
        base_period="2025-01",
    )

    with pytest.raises(
        ValueError,
        match="No observations found",
    ):
        calculate_route_indices(
            observations,
            methodology=methodology,
        )


def test_calendar_month_rejects_invalid_period():
    observations = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-07-01"]
            ),
            "route": ["DEL_BOM"],
            "advance_days": [1],
            "representative_fare": [500.0],
        }
    )

    methodology = IndexMethodology(
        base_period_method="calendar_month",
        base_period="invalid-period",
    )

    with pytest.raises(
        ValueError,
        match="YYYY-MM",
    ):
        calculate_route_indices(
            observations,
            methodology=methodology,
        )
