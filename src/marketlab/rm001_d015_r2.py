from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import parse_constituent_csv
from marketlab.rm001_d015_r1 import parse_security_master_all_series

D015_R2_DIAGNOSTIC_ID = "RM001-D015-R2-v1"
PARENT_RAW_SHA256 = (
    "c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f"
)
SECURITY_RAW_SHA256 = (
    "0dab1d451f2ab9015671bba26e1bc441d3d5569528e64150b5700a5772fbd786"
)
PARENT_ROW_COUNT = 755
PARENT_EQ_COUNT = 745
PARENT_NON_EQ_COUNT = 10


def build_d015_r2_report(
    *,
    parent_raw: bytes,
    security_raw: bytes,
) -> dict[str, Any]:
    parent_sha = sha256_bytes(parent_raw)
    security_sha = sha256_bytes(security_raw)

    parent = parse_constituent_csv(parent_raw)
    parent_rows = parent["rows"]
    security_rows, security_diagnostics = parse_security_master_all_series(
        security_raw
    )

    security_by_triplet: dict[
        tuple[str, str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in security_rows:
        security_by_triplet[
            (row["symbol"], row["isin"], row["series"])
        ].append(row)

    parent_eq = [row for row in parent_rows if row["series"] == "EQ"]
    parent_non_eq = [row for row in parent_rows if row["series"] != "EQ"]

    joined = 0
    eq_confirmed = 0
    non_eq_confirmed = 0
    missing = []
    ambiguous = []
    non_eq_correspondence = []

    for row in parent_rows:
        key = (row["symbol"], row["isin"], row["series"])
        matches = security_by_triplet.get(key, [])
        if len(matches) == 0:
            missing.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                }
            )
            continue
        if len(matches) != 1:
            ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                    "security_match_count": len(matches),
                }
            )
            continue

        joined += 1
        match = matches[0]
        if row["series"] == "EQ":
            eq_confirmed += 1
        else:
            non_eq_confirmed += 1
            non_eq_correspondence.append(
                {
                    "company_name": row["company_name"],
                    "industry": row["industry"],
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "parent_series": row["series"],
                    "security_series": match["series"],
                    "security_name": match["security_name"],
                    "deletion_flag": match["deletion_flag"],
                }
            )

    parent_count = len(parent_rows)
    join_coverage = (
        0.0 if parent_count == 0 else joined / parent_count
    )
    eq_confirmation_fraction = (
        0.0 if not parent_eq else eq_confirmed / len(parent_eq)
    )
    non_eq_confirmation_fraction = (
        0.0 if not parent_non_eq else non_eq_confirmed / len(parent_non_eq)
    )

    parent_triplet_counts = Counter(
        (row["symbol"], row["isin"], row["series"])
        for row in parent_rows
    )
    security_triplet_counts = Counter(
        (row["symbol"], row["isin"], row["series"])
        for row in security_rows
    )
    parent_duplicate_triplet_count = sum(
        1 for value in parent_triplet_counts.values() if value > 1
    )
    security_duplicate_triplet_count = sum(
        1 for value in security_triplet_counts.values() if value > 1
    )

    eq_identity_counts = Counter(
        (row["symbol"], row["isin"]) for row in parent_eq
    )
    eq_symbol_isins: dict[str, set[str]] = defaultdict(set)
    eq_isin_symbols: dict[str, set[str]] = defaultdict(set)
    for row in parent_eq:
        eq_symbol_isins[row["symbol"]].add(row["isin"])
        eq_isin_symbols[row["isin"]].add(row["symbol"])

    projected_duplicate_count = sum(
        1 for count in eq_identity_counts.values() if count > 1
    )
    projected_symbol_conflicts = sum(
        1 for values in eq_symbol_isins.values() if len(values) > 1
    )
    projected_isin_conflicts = sum(
        1 for values in eq_isin_symbols.values() if len(values) > 1
    )
    projected_industry_coverage = (
        0.0
        if not parent_eq
        else sum(bool(row["industry"]) for row in parent_eq) / len(parent_eq)
    )
    projected_isin_coverage = (
        0.0
        if not parent_eq
        else sum(bool(row["isin"]) for row in parent_eq) / len(parent_eq)
    )
    projected_identity_text_complete = all(
        row["company_name"] and row["symbol"] for row in parent_eq
    )

    gates = {
        "parent_raw_sha_exact": parent_sha == PARENT_RAW_SHA256,
        "security_raw_sha_exact": security_sha == SECURITY_RAW_SHA256,
        "parent_row_count_exact": parent_count == PARENT_ROW_COUNT,
        "parent_eq_row_count_exact": len(parent_eq) == PARENT_EQ_COUNT,
        "parent_non_eq_row_count_exact": (
            len(parent_non_eq) == PARENT_NON_EQ_COUNT
        ),
        "parent_duplicate_triplet_count_zero": (
            parent_duplicate_triplet_count == 0
        ),
        "triplet_join_coverage_100pct": join_coverage == 1.0,
        "missing_triplet_match_count_zero": len(missing) == 0,
        "ambiguous_triplet_match_count_zero": len(ambiguous) == 0,
        "eq_triplet_confirmation_fraction_100pct": (
            eq_confirmation_fraction == 1.0
        ),
        "non_eq_triplet_confirmation_fraction_100pct": (
            non_eq_confirmation_fraction == 1.0
        ),
        "projected_eq_row_count_exact": len(parent_eq) == PARENT_EQ_COUNT,
        "projected_eq_unique_identity_count_exact": (
            len(eq_identity_counts) == PARENT_EQ_COUNT
        ),
        "projected_eq_zero_duplicate_identities": (
            projected_duplicate_count == 0
        ),
        "projected_eq_zero_symbol_conflicts": projected_symbol_conflicts == 0,
        "projected_eq_zero_isin_conflicts": projected_isin_conflicts == 0,
        "projected_eq_industry_coverage_100pct": (
            projected_industry_coverage == 1.0
        ),
        "projected_eq_isin_coverage_100pct": projected_isin_coverage == 1.0,
        "projected_eq_identity_text_complete": (
            projected_identity_text_complete
        ),
    }
    passed = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D015_R2_DIAGNOSTIC_ID,
        "status": (
            "PASS_TRIPLET_EQ_PROJECTION_SEMANTICS"
            if passed
            else "FAIL_TRIPLET_EQ_PROJECTION_SEMANTICS"
        ),
        "evidence_class": "SOURCE_SEMANTICS_NO_RETURN_OUTCOMES",
        "parents": {
            "d015_status": "FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY",
            "d015_status_changed": False,
            "d015_r1_status": "FAIL_EQ_PROJECTION_SEMANTICS",
            "d015_r1_status_changed": False,
        },
        "parent_source": {
            "raw_sha256": parent_sha,
            "row_count": parent_count,
            "eq_row_count": len(parent_eq),
            "non_eq_row_count": len(parent_non_eq),
            "duplicate_triplet_count": parent_duplicate_triplet_count,
        },
        "security_source": {
            "raw_sha256": security_sha,
            "parsed_row_count": len(security_rows),
            "symbol_isin_duplicate_count": security_diagnostics[
                "duplicate_identity_count"
            ],
            "duplicate_triplet_count": security_duplicate_triplet_count,
            "series_counts": security_diagnostics["series_counts"],
        },
        "triplet_correspondence": {
            "key": ["symbol", "isin", "series"],
            "joined_count": joined,
            "join_coverage": join_coverage,
            "missing_count": len(missing),
            "ambiguous_count": len(ambiguous),
            "eq_confirmed_count": eq_confirmed,
            "eq_confirmation_fraction": eq_confirmation_fraction,
            "non_eq_confirmed_count": non_eq_confirmed,
            "non_eq_confirmation_fraction": non_eq_confirmation_fraction,
            "missing": missing[:25],
            "ambiguous": ambiguous[:25],
            "non_eq_correspondence": sorted(
                non_eq_correspondence,
                key=lambda item: (item["symbol"], item["isin"]),
            ),
        },
        "projected_eq_subset": {
            "filter_rule": 'Series == "EQ"',
            "row_count": len(parent_eq),
            "unique_identity_count": len(eq_identity_counts),
            "duplicate_identity_count": projected_duplicate_count,
            "symbol_conflict_count": projected_symbol_conflicts,
            "isin_conflict_count": projected_isin_conflicts,
            "industry_coverage": projected_industry_coverage,
            "isin_coverage": projected_isin_coverage,
            "identity_text_complete": projected_identity_text_complete,
        },
        "promotion_gates": gates,
        "prospective_eq_capture_authorized": passed,
        "historical_backfill_authorized": False,
        "rm001_factor_directly_allowed": False,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
