
import pandas as pd

from src.airfare_ml.index.audit import audit_all_dates


def _fixtures():
    validated = pd.DataFrame(
        {
            "collection_timestamp": pd.to_datetime(
                ["2026-09-04 10:00:00", "2026-09-05 10:00:00"]
            ),
            "invalid_fare": [False, False],
            "missing_required_value": [False, False],
            "invalid_route": [False, False],
            "invalid_advance_window": [False, False],
            "invalid_date_relationship": [False, False],
            "duplicate_observation": [False, False],
        }
    )

    deduplicated = pd.DataFrame(
        {
            "collection_timestamp": pd.to_datetime(
                ["2026-09-04 10:00:00", "2026-09-05 10:00:00"]
            ),
        }
    )

    representative = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-09-04", "2026-09-05", "2026-09-04", "2026-09-05"]
            ),
            "representative_fare": [100, 100, 110, 116.126067],
        }
    )

    stratum_indices = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-09-04", "2026-09-05"]
            ),
            "route": ["DEL_BOM", "DEL_BOM"],
            "advance_days": [1, 1],
            "stratum_index": [100, 116.126067],
        }
    )

    national_indices = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-09-04", "2026-09-05"]
            ),
            "national_index": [100.0, 116.126067],
            "index_status": ["VALID", "VALID"],
        }
    )

    coverage_report = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-09-04", "2026-09-05"]
            ),
            "routes_present": [20, 20],
            "expected_routes": [20, 20],
            "observed_strata": [100, 100],
            "required_strata": [100, 100],
            "coverage_complete": [True, True],
        }
    )

    lead = pd.DataFrame(
        {
            "collection_date": pd.to_datetime(
                ["2026-09-04", "2026-09-05"]
            ),
            "advance_days": [1, 1],
            "contribution_to_national_index": [0.0, 16.126067],
        }
    )

    return (
        validated,
        deduplicated,
        representative,
        stratum_indices,
        national_indices,
        coverage_report,
        lead,
    )


def test_publishable_date_passes_all_gates():
    args = _fixtures()
    report = audit_all_dates(
        validated=args[0],
        deduplicated=args[1],
        representative=args[2],
        stratum_indices=args[3],
        national_indices=args[4],
        coverage_report=args[5],
        lead_time_contributions=args[6],
        base_date="2026-09-04",
    )

    row = report.loc[report["collection_date"] == "2026-09-05"].iloc[0]

    assert row["publication_status"] == "PUBLISHABLE"
    assert row["coverage_complete"]
    assert row["index_calculation_pass"]
    assert row["contribution_reconciliation_pass"]


def test_incomplete_coverage_causes_hold():
    args = _fixtures()
    coverage = args[5].copy()
    coverage.loc[coverage["collection_date"] == pd.Timestamp("2026-09-05"),
                 "coverage_complete"] = False

    report = audit_all_dates(
        validated=args[0],
        deduplicated=args[1],
        representative=args[2],
        stratum_indices=args[3],
        national_indices=args[4],
        coverage_report=coverage,
        lead_time_contributions=args[6],
        base_date="2026-09-04",
    )

    row = report.loc[report["collection_date"] == "2026-09-05"].iloc[0]

    assert row["publication_status"] == "HOLD"
    assert "coverage" in row["failed_checks"]


def test_contribution_mismatch_causes_hold():
    args = _fixtures()
    lead = args[6].copy()
    lead.loc[lead["collection_date"] == pd.Timestamp("2026-09-05"),
              "contribution_to_national_index"] = 10.0

    report = audit_all_dates(
        validated=args[0],
        deduplicated=args[1],
        representative=args[2],
        stratum_indices=args[3],
        national_indices=args[4],
        coverage_report=args[5],
        lead_time_contributions=lead,
        base_date="2026-09-04",
    )

    row = report.loc[report["collection_date"] == "2026-09-05"].iloc[0]

    assert row["publication_status"] == "HOLD"
    assert "contribution_reconciliation" in row["failed_checks"]
