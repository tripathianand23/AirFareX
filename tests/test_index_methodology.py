from dataclasses import FrozenInstanceError

import pytest

from src.airfare_ml.index.methodology import (
    DEFAULT_INDEX_METHODOLOGY,
    IndexMethodology,
)

def test_default_methodology():
    methodology = DEFAULT_INDEX_METHODOLOGY

    assert methodology.advance_windows == (1, 7, 15, 30, 45)
    assert methodology.representative_fare_method == "median"
    assert methodology.lead_time_weighting == "equal"
    assert methodology.missing_route_policy == (
        "exclude_and_renormalize"
    )
    assert methodology.minimum_observations_per_stratum == 1
    assert methodology.index_base == 100.0


def test_custom_methodology():
    methodology = IndexMethodology(
        advance_windows=(1, 7, 14, 30),
        representative_fare_method="median",
        lead_time_weighting="equal",
        missing_route_policy="require_complete",
        minimum_observations_per_stratum=3,
        base_period_method="calendar_month",
        base_period="2026-07",
        index_base=100.0,
    )
    assert methodology.base_period_method == "calendar_month"
    assert methodology.advance_windows == (1, 7, 14, 30)
    assert methodology.minimum_observations_per_stratum == 3
    assert methodology.missing_route_policy == "require_complete"
    assert methodology.base_period == "2026-07"


def test_methodology_is_immutable():
    methodology = IndexMethodology()

    with pytest.raises(FrozenInstanceError):
        methodology.index_base = 200.0

    assert methodology.base_period_method == "first_observation"    