import pandas as pd

from .config import (
    IndexConfig,
    ROUTE_WEIGHTS,
    validate_route_weights,
)

from .methodology import (
    DEFAULT_INDEX_METHODOLOGY,
    IndexMethodology,
)


def _calculate_base_prices(
    data: pd.DataFrame,
    methodology: IndexMethodology,
) -> pd.DataFrame:
    """
    Calculate base fares for each route and advance window.

    first_observation:
        Uses the first chronological representative fare.

    calendar_month:
        Uses the median representative fare within the
        configured reference month.
    """
    group_columns = [
        "route",
        "advance_days",
    ]

    if methodology.base_period_method == "first_observation":
        base_prices = (
            data.sort_values(
                [
                    "route",
                    "advance_days",
                    "collection_date",
                ]
            )
            .groupby(group_columns)["representative_fare"]
            .first()
            .rename("base_fare")
            .reset_index()
        )

        return base_prices

    if methodology.base_period_method == "calendar_month":
        if not methodology.base_period:
            raise ValueError(
                "base_period must be provided when "
                "base_period_method='calendar_month'."
            )

        try:
            base_period = pd.Period(
                methodology.base_period,
                freq="M",
            )
        except ValueError as exc:
            raise ValueError(
                "base_period must be in YYYY-MM format; "
                f"received: {methodology.base_period!r}"
            ) from exc

        period_start = base_period.start_time
        period_end = base_period.end_time

        reference_data = data[
            (
                data["collection_date"]
                >= period_start
            )
            & (
                data["collection_date"]
                <= period_end
            )
        ].copy()

        if reference_data.empty:
            raise ValueError(
                "No observations found in configured "
                f"base period: {methodology.base_period}"
            )

        base_prices = (
            reference_data.groupby(group_columns)[
                "representative_fare"
            ]
            .median()
            .rename("base_fare")
            .reset_index()
        )

        return base_prices

    raise ValueError(
        "Unsupported base period method: "
        f"{methodology.base_period_method}"
    )


def calculate_route_indices(
    daily_fares: pd.DataFrame,
    config: IndexConfig | None = None,
    methodology: IndexMethodology | None = None,
) -> pd.DataFrame:
    """
    Calculate route-level price indices.

    Base prices are calculated according to the configured
    methodology.
    """
    if config is None:
        config = IndexConfig()

    if methodology is None:
        methodology = DEFAULT_INDEX_METHODOLOGY

    required = {
        "collection_date",
        "route",
        "advance_days",
        "representative_fare",
    }

    missing = required - set(daily_fares.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = daily_fares.copy()

    data["collection_date"] = pd.to_datetime(
        data["collection_date"]
    )

    data = data[
        data["route"].isin(ROUTE_WEIGHTS)
    ].copy()

    data = data[
        data["advance_days"].isin(
            methodology.advance_windows
        )
    ].copy()

    if data.empty:
        raise ValueError(
            "No observations match configured routes "
            "and advance windows."
        )

    base_prices = _calculate_base_prices(
        data,
        methodology,
    )

    data = data.merge(
        base_prices,
        on=[
            "route",
            "advance_days",
        ],
        how="left",
    )

    data["route_index"] = (
        data["representative_fare"]
        / data["base_fare"]
        * methodology.index_base
    )

    return data


def calculate_weighted_index(
    route_indices: pd.DataFrame,
    weights: dict[str, float] | None = None,
    methodology: IndexMethodology | None = None,
) -> pd.DataFrame:
    """
    Calculate weighted national airfare index.

    Missing routes are handled according to the configured
    methodology.
    """
    if weights is None:
        weights = ROUTE_WEIGHTS

    if methodology is None:
        methodology = DEFAULT_INDEX_METHODOLOGY

    validate_route_weights(weights)

    data = route_indices.copy()

    data["weight"] = data["route"].map(weights)

    data = data.dropna(
        subset=[
            "route_index",
            "weight",
        ]
    )

    def weighted_average(
        group: pd.DataFrame,
    ) -> float:

        if (
            methodology.missing_route_policy
            == "require_complete"
        ):
            expected_routes = set(weights)
            observed_routes = set(
                group["route"]
            )

            if not expected_routes.issubset(
                observed_routes
            ):
                return float("nan")

        elif (
            methodology.missing_route_policy
            != "exclude_and_renormalize"
        ):
            raise ValueError(
                "Unsupported missing route policy: "
                f"{methodology.missing_route_policy}"
            )

        total_weight = group["weight"].sum()

        if total_weight <= 0:
            return float("nan")

        return (
            (
                group["route_index"]
                * group["weight"]
            ).sum()
            / total_weight
        )

    result = (
        data.groupby(
            [
                "collection_date",
                "advance_days",
            ]
        )
        .apply(
            weighted_average,
            include_groups=False,
        )
        .rename("airfare_index")
        .reset_index()
    )

    return result.sort_values(
        [
            "collection_date",
            "advance_days",
        ]
    ).reset_index(drop=True)
