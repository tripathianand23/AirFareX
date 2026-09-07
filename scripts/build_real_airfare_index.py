from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# PROJECT PATH
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# PROJECT IMPORTS
# ---------------------------------------------------------------------------

from src.airfare_ml.index.audit import (
    audit_all_dates,
    write_audit_outputs,
)
from src.airfare_ml.index.config_loader import (
    load_index_config,
)


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "index_methodology.yaml"
)

INDEX_CONFIG = load_index_config(CONFIG_PATH)


BASE_DATE = pd.Timestamp(
    INDEX_CONFIG.base_date
).date()

INDEX_BASE = INDEX_CONFIG.base_value

ADVANCE_WINDOWS = INDEX_CONFIG.advance_windows

EXPECTED_ROUTES = set(
    INDEX_CONFIG.route_universe
)

MIN_ROUTE_COVERAGE_RATIO = (
    INDEX_CONFIG.minimum_route_coverage_ratio
)

MIN_STRATUM_COVERAGE_RATIO = (
    INDEX_CONFIG.minimum_stratum_coverage_ratio
)


# ---------------------------------------------------------------------------
# METHODOLOGY GUARDS
# ---------------------------------------------------------------------------

if INDEX_CONFIG.route_weighting != "equal":
    raise ValueError(
        "Current index engine supports only equal route weighting."
    )

if INDEX_CONFIG.lead_time_weighting != "equal":
    raise ValueError(
        "Current index engine supports only equal lead-time weighting."
    )

if INDEX_CONFIG.representative_fare_method not in {
    "median",
}:
    raise ValueError(
        "Current index engine supports only "
        "representative_fare_method='median'."
    )


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "real"
    / "deduplicated"
    / "deduplicated_airfare_observations.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "real"
    / "index"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "data"
    / "reports"
    / "real"
)


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """
    Load and standardize the deduplicated canonical airfare dataset.
    """

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}"
        )

    df = pd.read_csv(INPUT_PATH)

    required_columns = {
        "collection_timestamp",
        "origin",
        "destination",
        "advance_days",
        "total_fare",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            "Input dataset is missing required columns: "
            + ", ".join(sorted(missing))
        )

    df["collection_timestamp"] = pd.to_datetime(
        df["collection_timestamp"],
        errors="coerce",
    )

    if df["collection_timestamp"].isna().any():
        raise ValueError(
            "Input contains invalid collection_timestamp values."
        )

    df["collection_date"] = (
        df["collection_timestamp"].dt.date
    )

    df["route"] = (
        df["origin"]
        .astype(str)
        .str.upper()
        .str.strip()
        + "_"
        + df["destination"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["advance_days"] = pd.to_numeric(
        df["advance_days"],
        errors="coerce",
    )

    df["total_fare"] = pd.to_numeric(
        df["total_fare"],
        errors="coerce",
    )

    df = df[
        df["advance_days"].isin(ADVANCE_WINDOWS)
    ].copy()

    df = df[
        df["total_fare"].notna()
        & (df["total_fare"] > 0)
    ].copy()

    return df


# ---------------------------------------------------------------------------
# ROUTE WEIGHTS
# ---------------------------------------------------------------------------

def build_equal_route_weights(
    routes,
) -> dict[str, float]:
    """
    Build transparent equal weights for the configured route universe.

    These are prototype weights only.
    They are NOT official MoSPI/CPI/DGCA weights.
    """

    routes = sorted(set(routes))

    if not routes:
        raise ValueError(
            "At least one route is required."
        )

    weight = 1.0 / len(routes)

    return {
        route: weight
        for route in routes
    }


# ---------------------------------------------------------------------------
# REPRESENTATIVE FARES
# ---------------------------------------------------------------------------

def build_representative_fares(
    df: pd.DataFrame,
    method: str,
) -> pd.DataFrame:
    """
    Calculate representative fare for each:

        collection_date × route × advance_window

    Currently supported:

        median

    Median is used as the prototype representative fare because
    it is robust to extreme observations.
    """

    if method != "median":
        raise ValueError(
            f"Unsupported representative fare method: {method}"
        )

    result = (
        df.groupby(
            [
                "collection_date",
                "route",
                "advance_days",
            ],
            as_index=False,
        )
        .agg(
            representative_fare=(
                "total_fare",
                "median",
            ),
            observation_count=(
                "total_fare",
                "size",
            ),
        )
    )

    return result


# ---------------------------------------------------------------------------
# STRATUM INDICES
# ---------------------------------------------------------------------------

def build_stratum_indices(
    representative: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate each route × lead-time stratum relative to BASE_DATE.
    """

    base = representative[
        representative["collection_date"] == BASE_DATE
    ][
        [
            "route",
            "advance_days",
            "representative_fare",
        ]
    ].rename(
        columns={
            "representative_fare":
                "base_representative_fare",
        }
    )

    if base.empty:
        raise ValueError(
            f"No observations found for base date {BASE_DATE}."
        )

    duplicate_base = base.duplicated(
        subset=[
            "route",
            "advance_days",
        ],
        keep=False,
    )

    if duplicate_base.any():
        raise ValueError(
            "Base-period strata are not unique."
        )

    merged = representative.merge(
        base,
        on=[
            "route",
            "advance_days",
        ],
        how="left",
        validate="many_to_one",
    )

    if merged[
        "base_representative_fare"
    ].isna().any():

        missing = (
            merged.loc[
                merged[
                    "base_representative_fare"
                ].isna(),
                [
                    "route",
                    "advance_days",
                ],
            ]
            .drop_duplicates()
            .sort_values(
                [
                    "route",
                    "advance_days",
                ]
            )
        )

        raise ValueError(
            "Missing base-period strata:\n"
            + missing.to_string(index=False)
        )

    if (
        merged["base_representative_fare"] <= 0
    ).any():
        raise ValueError(
            "Base representative fares must be positive."
        )

    merged["stratum_index"] = (
        merged["representative_fare"]
        / merged["base_representative_fare"]
        * INDEX_BASE
    )

    return merged


# ---------------------------------------------------------------------------
# COVERAGE EVALUATION
# ---------------------------------------------------------------------------

def evaluate_daily_coverage(
    stratum_indices: pd.DataFrame,
    expected_routes: set[str],
    expected_advance_windows: set[int],
) -> pd.DataFrame:
    """
    Evaluate route × lead-time coverage for every collection date.

    This is a deterministic statistical quality-control gate.
    It is not an ML model.
    """

    expected_routes = set(
        expected_routes
    )

    expected_advance_windows = set(
        expected_advance_windows
    )

    if not expected_routes:
        raise ValueError(
            "expected_routes cannot be empty."
        )

    if not expected_advance_windows:
        raise ValueError(
            "expected_advance_windows cannot be empty."
        )

    required_strata = (
        len(expected_routes)
        * len(expected_advance_windows)
    )

    records = []

    for collection_date, group in (
        stratum_indices.groupby(
            "collection_date"
        )
    ):

        routes_present = set(
            group["route"]
            .dropna()
            .astype(str)
            .unique()
        )

        windows_present = set(
            group["advance_days"]
            .dropna()
            .astype(int)
            .unique()
        )

        observed_strata = (
            group[
                [
                    "route",
                    "advance_days",
                ]
            ]
            .drop_duplicates()
            .shape[0]
        )

        route_coverage_ratio = (
            len(routes_present)
            / len(expected_routes)
        )

        lead_time_coverage_ratio = (
            len(windows_present)
            / len(expected_advance_windows)
        )

        stratum_coverage_ratio = (
            observed_strata
            / required_strata
        )

        missing_routes = sorted(
            expected_routes
            - routes_present
        )

        missing_windows = sorted(
            expected_advance_windows
            - windows_present
        )

        expected_strata = {
            (route, window)
            for route in expected_routes
            for window in expected_advance_windows
        }

        observed_strata_set = {
            (
                route,
                int(window),
            )
            for route, window
            in group[
                [
                    "route",
                    "advance_days",
                ]
            ].drop_duplicates().itertuples(
                index=False,
                name=None,
            )
        }

        complete_strata = (
            observed_strata_set
            >= expected_strata
        )

        coverage_complete = (
            route_coverage_ratio
            >= MIN_ROUTE_COVERAGE_RATIO
            and lead_time_coverage_ratio
            >= MIN_STRATUM_COVERAGE_RATIO
            and stratum_coverage_ratio
            >= MIN_STRATUM_COVERAGE_RATIO
            and complete_strata
        )

        coverage_status = (
            "PASS"
            if coverage_complete
            else "INSUFFICIENT_COVERAGE"
        )

        records.append(
            {
                "collection_date": collection_date,
                "routes_present": len(
                    routes_present
                ),
                "expected_routes": len(
                    expected_routes
                ),
                "route_coverage_ratio":
                    route_coverage_ratio,
                "lead_windows_present":
                    len(windows_present),
                "expected_lead_windows":
                    len(
                        expected_advance_windows
                    ),
                "lead_time_coverage_ratio":
                    lead_time_coverage_ratio,
                "observed_strata":
                    observed_strata,
                "required_strata":
                    required_strata,
                "stratum_coverage_ratio":
                    stratum_coverage_ratio,
                "missing_routes":
                    ",".join(missing_routes),
                "missing_lead_windows":
                    ",".join(
                        map(
                            str,
                            missing_windows,
                        )
                    ),
                "coverage_complete":
                    coverage_complete,
                "coverage_status":
                    coverage_status,
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# ROUTE INDICES
# ---------------------------------------------------------------------------

def build_route_indices(
    stratum_indices: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate lead-time stratum indices into an equal-weight route index.
    """

    result = (
        stratum_indices.groupby(
            [
                "collection_date",
                "route",
            ],
            as_index=False,
        )
        .agg(
            route_index=(
                "stratum_index",
                "mean",
            ),
            lead_time_strata=(
                "advance_days",
                "nunique",
            ),
            observations=(
                "observation_count",
                "sum",
            ),
        )
    )

    return result


# ---------------------------------------------------------------------------
# NATIONAL INDEX
# ---------------------------------------------------------------------------

def build_national_indices(
    route_indices: pd.DataFrame,
    coverage_report: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate route indices into the national prototype index.

    Equal route weighting is used across the configured route universe.

    A national index is published only when the coverage gate passes.
    """

    route_weights = (
        build_equal_route_weights(
            EXPECTED_ROUTES
        )
    )

    result = route_indices.copy()

    result["route_weight"] = (
        result["route"].map(
            route_weights
        )
    )

    if result[
        "route_weight"
    ].isna().any():

        unexpected = sorted(
            result.loc[
                result[
                    "route_weight"
                ].isna(),
                "route",
            ].unique()
        )

        raise ValueError(
            "Found routes outside EXPECTED_ROUTES: "
            + ", ".join(unexpected)
        )

    result["weighted_contribution"] = (
        result["route_index"]
        * result["route_weight"]
    )

    national = (
        result.groupby(
            "collection_date",
            as_index=False,
        )
        .agg(
            national_index=(
                "weighted_contribution",
                "sum",
            ),
            routes_present=(
                "route",
                "nunique",
            ),
            total_observations=(
                "observations",
                "sum",
            ),
        )
    )

    national = national.merge(
        coverage_report[
            [
                "collection_date",
                "expected_routes",
                "route_coverage_ratio",
                "lead_windows_present",
                "expected_lead_windows",
                "lead_time_coverage_ratio",
                "observed_strata",
                "required_strata",
                "stratum_coverage_ratio",
                "missing_routes",
                "missing_lead_windows",
                "coverage_complete",
                "coverage_status",
            ]
        ],
        on="collection_date",
        how="left",
        validate="one_to_one",
    )

    national["index_status"] = (
        national[
            "coverage_complete"
        ].map(
            {
                True: "VALID",
                False: "INSUFFICIENT_COVERAGE",
            }
        )
    )

    national.loc[
        ~national["coverage_complete"],
        "national_index",
    ] = float("nan")

    return (
        national
        .sort_values("collection_date")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# ROUTE CONTRIBUTIONS
# ---------------------------------------------------------------------------

def build_route_contributions(
    route_indices: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate route contributions to the national index.
    """

    route_weights = (
        build_equal_route_weights(
            EXPECTED_ROUTES
        )
    )

    result = route_indices.copy()

    result["route_weight"] = (
        result["route"].map(
            route_weights
        )
    )

    result["weighted_contribution"] = (
        result["route_index"]
        * result["route_weight"]
    )

    return (
        result
        .sort_values(
            [
                "collection_date",
                "route",
            ]
        )
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# LEAD-TIME CONTRIBUTIONS
# ---------------------------------------------------------------------------

def build_lead_time_contributions(
    stratum_indices: pd.DataFrame,
    coverage_report: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate lead-time contribution to national movement.

    Each configured lead-time window receives equal weight.
    """

    valid_dates = set(
        coverage_report.loc[
            coverage_report[
                "coverage_complete"
            ],
            "collection_date",
        ]
    )

    df = stratum_indices[
        stratum_indices[
            "collection_date"
        ].isin(valid_dates)
    ].copy()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "collection_date",
                "advance_days",
                "mean_stratum_index",
                "mean_movement_pct",
                "lead_time_weight",
                "contribution_to_national_index",
                "route_count",
            ]
        )

    result = (
        df.groupby(
            [
                "collection_date",
                "advance_days",
            ],
            as_index=False,
        )
        .agg(
            mean_stratum_index=(
                "stratum_index",
                "mean",
            ),
            mean_movement_pct=(
                "stratum_index",
                lambda s:
                    s.mean() - INDEX_BASE,
            ),
            route_count=(
                "route",
                "nunique",
            ),
        )
    )

    lead_weight = (
        1.0
        / len(ADVANCE_WINDOWS)
    )

    result["lead_time_weight"] = (
        lead_weight
    )

    result[
        "contribution_to_national_index"
    ] = (
        result["mean_movement_pct"]
        * result["lead_time_weight"]
    )

    return (
        result
        .sort_values(
            [
                "collection_date",
                "advance_days",
            ]
        )
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def main() -> None:

    print("=" * 80)
    print("REAL AIRFARE PRICE INDEX")
    print("=" * 80)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------------------------
    # 1
    # -----------------------------------------------------------------------

    print(
        "\n[1/9] Loading deduplicated data..."
    )

    df = load_data()

    print(
        f"Observations: {len(df):,}"
    )

    print(
        f"Collection dates: "
        f"{df['collection_date'].min()} → "
        f"{df['collection_date'].max()}"
    )

    # -----------------------------------------------------------------------
    # 2
    # -----------------------------------------------------------------------

    print(
        "\n[2/9] Building representative fares..."
    )

    representative = (
        build_representative_fares(
            df,
            method=(
                INDEX_CONFIG
                .representative_fare_method
            ),
        )
    )

    print(
        f"Route × lead-time × date strata: "
        f"{len(representative):,}"
    )

    # -----------------------------------------------------------------------
    # 3
    # -----------------------------------------------------------------------

    print(
        "\n[3/9] Building stratum indices..."
    )

    stratum_indices = (
        build_stratum_indices(
            representative
        )
    )

    # -----------------------------------------------------------------------
    # 4
    # -----------------------------------------------------------------------

    print(
        "\n[4/9] Evaluating coverage..."
    )

    coverage_report = (
        evaluate_daily_coverage(
            stratum_indices=stratum_indices,
            expected_routes=EXPECTED_ROUTES,
            expected_advance_windows=set(
                ADVANCE_WINDOWS
            ),
        )
    )

    print(
        coverage_report[
            [
                "collection_date",
                "routes_present",
                "expected_routes",
                "observed_strata",
                "required_strata",
                "coverage_status",
            ]
        ].to_string(index=False)
    )

    # -----------------------------------------------------------------------
    # 5
    # -----------------------------------------------------------------------

    print(
        "\n[5/9] Building route indices..."
    )

    route_indices = (
        build_route_indices(
            stratum_indices
        )
    )

    # -----------------------------------------------------------------------
    # 6
    # -----------------------------------------------------------------------

    print(
        "\n[6/9] Building national index..."
    )

    national_indices = (
        build_national_indices(
            route_indices,
            coverage_report,
        )
    )

    print(
        national_indices[
            [
                "collection_date",
                "national_index",
                "routes_present",
                "observed_strata",
                "index_status",
            ]
        ].to_string(index=False)
    )

    # -----------------------------------------------------------------------
    # 7
    # -----------------------------------------------------------------------

    print(
        "\n[7/9] Building contribution outputs..."
    )

    route_contributions = (
        build_route_contributions(
            route_indices
        )
    )

    lead_time_contributions = (
        build_lead_time_contributions(
            stratum_indices,
            coverage_report,
        )
    )

    print(
        "\nLead-time contribution summary:"
    )

    latest_valid_dates = (
        coverage_report.loc[
            coverage_report[
                "coverage_complete"
            ],
            "collection_date",
        ]
    )

    if not latest_valid_dates.empty:

        latest_valid_date = max(
            latest_valid_dates
        )

        latest_lead = (
            lead_time_contributions[
                lead_time_contributions[
                    "collection_date"
                ]
                == latest_valid_date
            ]
        )

        print(
            latest_lead[
                [
                    "advance_days",
                    "mean_movement_pct",
                    "lead_time_weight",
                    "contribution_to_national_index",
                    "route_count",
                ]
            ].to_string(index=False)
        )

    # -----------------------------------------------------------------------
    # 8
    # -----------------------------------------------------------------------

    print(
        "\n[8/9] Running automated statistical audit..."
    )

    validated_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "real"
        / "validated"
        / "validated_airfare_observations.csv"
    )

    deduplicated_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "real"
        / "deduplicated"
        / "deduplicated_airfare_observations.csv"
    )

    validated = pd.read_csv(
        validated_path,
        parse_dates=[
            "collection_timestamp"
        ],
    )

    deduplicated = pd.read_csv(
        deduplicated_path,
        parse_dates=[
            "collection_timestamp"
        ],
    )

    audit_report = audit_all_dates(
        validated=validated,
        deduplicated=deduplicated,
        representative=representative,
        stratum_indices=stratum_indices,
        national_indices=national_indices,
        coverage_report=coverage_report,
        lead_time_contributions=(
            lead_time_contributions
        ),
        base_date=BASE_DATE,
        index_base=INDEX_BASE,
        expected_routes=len(
            EXPECTED_ROUTES
        ),
        required_strata=(
            len(EXPECTED_ROUTES)
            * len(ADVANCE_WINDOWS)
        ),
    )

    audit_csv_path, audit_json_path = (
        write_audit_outputs(
            audit_report,
            REPORT_DIR,
        )
    )

    print(
        "\nAutomated publication audit:"
    )

    print(
        audit_report[
            [
                "collection_date",
                "national_index",
                "movement_from_base_pct",
                "publication_status",
            ]
        ].to_string(index=False)
    )

    print("\nAudit outputs:")

    print(
        f"  {audit_csv_path}"
    )

    print(
        f"  {audit_json_path}"
    )

    # -----------------------------------------------------------------------
    # 9
    # -----------------------------------------------------------------------

    print(
        "\n[9/9] Writing outputs..."
    )

    representative.to_csv(
        OUTPUT_DIR
        / "real_daily_route_fares.csv",
        index=False,
    )

    stratum_indices.to_csv(
        OUTPUT_DIR
        / "real_stratum_indices.csv",
        index=False,
    )

    route_indices.to_csv(
        OUTPUT_DIR
        / "real_route_indices.csv",
        index=False,
    )

    national_indices.to_csv(
        OUTPUT_DIR
        / "real_daily_airfare_index.csv",
        index=False,
    )

    route_contributions.to_csv(
        OUTPUT_DIR
        / "real_route_contributions.csv",
        index=False,
    )

    lead_time_contributions.to_csv(
        OUTPUT_DIR
        / "real_lead_time_contributions.csv",
        index=False,
    )

    coverage_report.to_csv(
        OUTPUT_DIR
        / "real_coverage_report.csv",
        index=False,
    )

    # -----------------------------------------------------------------------
    # METADATA
    # -----------------------------------------------------------------------

    metadata = {
        "project": "Real-time Airfare Price Index",
        "problem_statement": "SIH 26056",
        "status": "prototype",

        "index_base": INDEX_BASE,
        "base_date": str(BASE_DATE),

        "representative_fare_method": (
            INDEX_CONFIG
            .representative_fare_method
        ),

        "lead_time_aggregation": (
            INDEX_CONFIG
            .lead_time_weighting
        ),

        "route_weighting": (
            INDEX_CONFIG
            .route_weighting
        ),

        "route_weights": (
            "equal_across_configured_prototype_routes"
        ),

        "official_weights_used": (
            INDEX_CONFIG
            .official_weights_used
        ),

        "expected_routes": sorted(
            EXPECTED_ROUTES
        ),

        "expected_advance_windows": (
            list(ADVANCE_WINDOWS)
        ),

        "coverage_policy": (
            "strict_complete_route_x_lead_time"
        ),

        "minimum_route_coverage_ratio": (
            MIN_ROUTE_COVERAGE_RATIO
        ),

        "minimum_stratum_coverage_ratio": (
            MIN_STRATUM_COVERAGE_RATIO
        ),

        "input_observations": int(
            len(df)
        ),

        "strata": int(
            len(representative)
        ),

        "valid_national_index_dates": int(
            coverage_report[
                "coverage_complete"
            ].sum()
        ),

        "insufficient_coverage_dates": int(
            (
                ~coverage_report[
                    "coverage_complete"
                ]
            ).sum()
        ),
    }

    metadata_path = (
        OUTPUT_DIR
        / "real_index_metadata.json"
    )

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            metadata,
            f,
            indent=2,
        )

    # -----------------------------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("REAL INDEX COMPLETE")
    print("=" * 80)

    print("\nNational index:")

    print(
        national_indices.to_string(
            index=False
        )
    )

    print("\nOutputs:")

    output_files = [
        "real_daily_route_fares.csv",
        "real_stratum_indices.csv",
        "real_route_indices.csv",
        "real_daily_airfare_index.csv",
        "real_route_contributions.csv",
        "real_lead_time_contributions.csv",
        "real_coverage_report.csv",
        "real_index_metadata.json",
    ]

    for filename in output_files:
        print(
            f"  {OUTPUT_DIR / filename}"
        )

    print("\nAudit reports:")

    print(
        f"  {audit_csv_path}"
    )

    print(
        f"  {audit_json_path}"
    )


if __name__ == "__main__":
    main()