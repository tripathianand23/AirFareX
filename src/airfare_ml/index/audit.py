"""
Deterministic statistical audit and publication decision engine.

This module does not predict fares. It validates whether a reconstructed
airfare index is internally consistent and eligible for publication under
the configured prototype methodology.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math

import pandas as pd


DEFAULT_TOLERANCE = 1e-6


@dataclass(frozen=True)
class AuditResult:
    collection_date: str
    observations: int
    routes_present: int
    expected_routes: int
    observed_strata: int
    required_strata: int
    coverage_complete: bool

    structural_validation_pass: bool
    duplicate_qc_pass: bool
    representative_fares_pass: bool
    index_calculation_pass: bool
    contribution_reconciliation_pass: bool
    base_period_pass: bool

    national_index: float | None
    movement_from_base_pct: float | None
    publication_status: str
    failed_checks: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _is_finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _normalise_date(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


def _get_row(df: pd.DataFrame, collection_date: object) -> pd.Series | None:
    target = pd.Timestamp(collection_date).date()
    if "collection_date" not in df.columns:
        return None

    dates = pd.to_datetime(df["collection_date"], errors="coerce").dt.date
    matches = df.loc[dates == target]
    if matches.empty:
        return None
    return matches.iloc[0]


def audit_date(
    *,
    collection_date: object,
    validated: pd.DataFrame,
    deduplicated: pd.DataFrame,
    representative: pd.DataFrame,
    stratum_indices: pd.DataFrame,
    national_indices: pd.DataFrame,
    coverage_report: pd.DataFrame,
    lead_time_contributions: pd.DataFrame,
    base_date: object,
    index_base: float = 100.0,
    expected_routes: int | None = None,
    required_strata: int | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> AuditResult:
    """
    Audit one collection date.

    Publication is allowed only when every hard quality gate passes.
    """
    date_str = _normalise_date(collection_date)
    failed: list[str] = []
    warnings: list[str] = []

    coverage = _get_row(coverage_report, collection_date)
    national = _get_row(national_indices, collection_date)

    if coverage is None:
        coverage_complete = False
        routes_present = 0
        expected_route_count = expected_routes or 0
        observed_strata = 0
        required_strata_count = required_strata or 0
        failed.append("coverage_report_missing")
    else:
        coverage_complete = bool(coverage.get("coverage_complete", False))
        routes_present = int(coverage.get("routes_present", 0))
        expected_route_count = int(
            coverage.get("expected_routes", expected_routes or 0)
        )
        observed_strata = int(coverage.get("observed_strata", 0))
        required_strata_count = int(
            coverage.get("required_strata", required_strata or 0)
        )

        if not coverage_complete:
            failed.append("coverage")

    date_mask_validated = (
        pd.to_datetime(validated["collection_timestamp"], errors="coerce")
        .dt.date == pd.Timestamp(collection_date).date()
    ) if "collection_timestamp" in validated.columns else pd.Series(False, index=validated.index)

    date_validated = validated.loc[date_mask_validated].copy()

    structural_columns = [
        "invalid_fare",
        "missing_required_value",
        "invalid_route",
        "invalid_advance_window",
        "invalid_date_relationship",
    ]
    present_structural = [
        column for column in structural_columns
        if column in date_validated.columns
    ]
    structural_pass = (
        bool((~date_validated[present_structural].any(axis=1)).all())
        if present_structural and not date_validated.empty
        else bool(date_validated.empty or not present_structural)
    )
    if not structural_pass:
        failed.append("structural_validation")

    duplicate_qc_pass = True
    if "duplicate_observation" in date_validated.columns:
        duplicate_qc_pass = not bool(
            date_validated["duplicate_observation"].fillna(False).any()
        )
    if not duplicate_qc_pass:
        # Duplicate flags are expected before deduplication. The gate below
        # therefore checks the deduplicated result separately.
        warnings.append("validated_duplicate_flags_present_before_deduplication")

    dedup_dates = (
        pd.to_datetime(deduplicated["collection_timestamp"], errors="coerce").dt.date
        == pd.Timestamp(collection_date).date()
    ) if "collection_timestamp" in deduplicated.columns else pd.Series(False, index=deduplicated.index)
    dedup_date = deduplicated.loc[dedup_dates]
    dedup_has_duplicates = bool(
        dedup_date.duplicated().any()
    )
    if dedup_has_duplicates:
        duplicate_qc_pass = False
        failed.append("post_dedup_duplicates")

    rep_date = representative[
        pd.to_datetime(representative["collection_date"], errors="coerce").dt.date
        == pd.Timestamp(collection_date).date()
    ].copy() if "collection_date" in representative.columns else pd.DataFrame()

    representative_fares_pass = (
        not rep_date.empty
        and rep_date["representative_fare"].map(_is_finite_positive).all()
    ) if "representative_fare" in rep_date.columns else False
    if not representative_fares_pass:
        failed.append("representative_fares")

    national_index = None
    if national is None:
        index_calculation_pass = False
        failed.append("national_index_missing")
    else:
        raw_index = national.get("national_index")
        national_index = (
            float(raw_index)
            if _is_finite_positive(raw_index)
            else None
        )
        index_calculation_pass = (
            bool(national.get("index_status") == "VALID")
            and national_index is not None
            and math.isfinite(national_index)
        )
        if not index_calculation_pass:
            failed.append("index_calculation")

    base_timestamp = pd.Timestamp(base_date).date()
    base_rows = representative[
        pd.to_datetime(representative["collection_date"], errors="coerce").dt.date
        == base_timestamp
    ] if "collection_date" in representative.columns else pd.DataFrame()

    base_period_pass = (
        not base_rows.empty
        and "representative_fare" in base_rows.columns
        and base_rows["representative_fare"].map(_is_finite_positive).all()
    )
    if not base_period_pass:
        failed.append("base_period")

    contribution_date = lead_time_contributions[
        pd.to_datetime(
            lead_time_contributions["collection_date"], errors="coerce"
        ).dt.date == pd.Timestamp(collection_date).date()
    ].copy() if "collection_date" in lead_time_contributions.columns else pd.DataFrame()

    contribution_reconciliation_pass = False
    movement_from_base_pct = None

    if index_calculation_pass and national_index is not None:
        movement_from_base_pct = national_index - index_base

        if not contribution_date.empty:
            contribution_sum = float(
                contribution_date["contribution_to_national_index"].sum()
            )
            contribution_reconciliation_pass = (
                abs(contribution_sum - movement_from_base_pct)
                <= tolerance
            )

    if not contribution_reconciliation_pass:
        failed.append("contribution_reconciliation")

    # A coverage failure is already a hard publication failure, even if an
    # index value happened to be computable.
    publication_status = "PUBLISHABLE" if not failed else "HOLD"

    return AuditResult(
        collection_date=date_str,
        observations=int(len(dedup_date)),
        routes_present=routes_present,
        expected_routes=expected_route_count,
        observed_strata=observed_strata,
        required_strata=required_strata_count,
        coverage_complete=coverage_complete,
        structural_validation_pass=structural_pass,
        duplicate_qc_pass=duplicate_qc_pass,
        representative_fares_pass=representative_fares_pass,
        index_calculation_pass=index_calculation_pass,
        contribution_reconciliation_pass=contribution_reconciliation_pass,
        base_period_pass=base_period_pass,
        national_index=national_index,
        movement_from_base_pct=movement_from_base_pct,
        publication_status=publication_status,
        failed_checks=tuple(failed),
        warnings=tuple(warnings),
    )


def audit_all_dates(
    *,
    validated: pd.DataFrame,
    deduplicated: pd.DataFrame,
    representative: pd.DataFrame,
    stratum_indices: pd.DataFrame,
    national_indices: pd.DataFrame,
    coverage_report: pd.DataFrame,
    lead_time_contributions: pd.DataFrame,
    base_date: object,
    index_base: float = 100.0,
    expected_routes: int | None = None,
    required_strata: int | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> pd.DataFrame:
    """Run the publication audit for every collection date."""
    if "collection_date" not in coverage_report.columns:
        raise ValueError("coverage_report must contain collection_date")

    dates = sorted(
        pd.to_datetime(
            coverage_report["collection_date"], errors="coerce"
        ).dropna().dt.date.unique()
    )

    results = [
        audit_date(
            collection_date=date,
            validated=validated,
            deduplicated=deduplicated,
            representative=representative,
            stratum_indices=stratum_indices,
            national_indices=national_indices,
            coverage_report=coverage_report,
            lead_time_contributions=lead_time_contributions,
            base_date=base_date,
            index_base=index_base,
            expected_routes=expected_routes,
            required_strata=required_strata,
            tolerance=tolerance,
        )
        for date in dates
    ]

    return pd.DataFrame([result.to_dict() for result in results])


def write_audit_outputs(
    audit_report: pd.DataFrame,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write CSV plus a compact JSON publication/audit report."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "real_index_audit.csv"
    json_path = output_dir / "real_index_audit.json"

    audit_report.to_csv(csv_path, index=False)

    payload = {
        "audit_type": "deterministic_statistical_publication_audit",
        "publication_policy": "all_hard_checks_must_pass",
        "dates": audit_report.to_dict(orient="records"),
    }

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)

    return csv_path, json_path
