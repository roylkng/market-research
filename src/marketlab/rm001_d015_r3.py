from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import digest
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import parse_constituent_csv
from marketlab.rm001_d015_r1 import parse_security_master_all_series

D015_R3_DIAGNOSTIC_ID = "RM001-D015-R3-v1"
PARENT_RAW_SHA256 = (
    "c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f"
)
SECURITY_RAW_SHA256 = (
    "0dab1d451f2ab9015671bba26e1bc441d3d5569528e64150b5700a5772fbd786"
)
PARENT_ROW_COUNT = 755
PARENT_EQ_COUNT = 745
PARENT_NON_EQ_COUNT = 10
ORDINARY_EQ_COUNT = 740
DUMMY_EQ_COUNT = 5

R2_MISSING_IDENTITIES = {
    ("DUMMYHEG", "DUM545A01024", "EQ"),
    ("DUMMYINGL1", "DU1560A01023", "EQ"),
    ("DUMMYINGL2", "DU2560A01023", "EQ"),
    ("DUMMYINXGN", "DUM510W01014", "EQ"),
    ("DUMMYTRVN", "DUM256C01024", "EQ"),
}


def _identity_diagnostics(rows: list[dict[str, str]]) -> dict[str, Any]:
    identity_counts = Counter((row["symbol"], row["isin"]) for row in rows)
    symbol_isins: dict[str, set[str]] = defaultdict(set)
    isin_symbols: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        symbol_isins[row["symbol"]].add(row["isin"])
        isin_symbols[row["isin"]].add(row["symbol"])
    return {
        "row_count": len(rows),
        "unique_identity_count": len(identity_counts),
        "duplicate_identity_count": sum(
            count > 1 for count in identity_counts.values()
        ),
        "symbol_conflict_count": sum(
            len(values) > 1 for values in symbol_isins.values()
        ),
        "isin_conflict_count": sum(
            len(values) > 1 for values in isin_symbols.values()
        ),
        "industry_coverage": (
            0.0
            if not rows
            else sum(bool(row["industry"]) for row in rows) / len(rows)
        ),
        "isin_coverage": (
            0.0
            if not rows
            else sum(bool(row["isin"]) for row in rows) / len(rows)
        ),
        "identity_text_complete": all(
            row["company_name"] and row["symbol"] for row in rows
        ),
    }


def build_d015_r3_report(
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
    security_by_identity: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in security_rows:
        security_by_triplet[
            (row["symbol"], row["isin"], row["series"])
        ].append(row)
        security_by_identity[(row["symbol"], row["isin"])].append(row)

    parent_eq = [row for row in parent_rows if row["series"] == "EQ"]
    parent_non_eq = [row for row in parent_rows if row["series"] != "EQ"]
    dummy_eq = [
        row for row in parent_eq if row["symbol"].startswith("DUMMY")
    ]
    ordinary_eq = [
        row for row in parent_eq if not row["symbol"].startswith("DUMMY")
    ]

    ordinary_missing = []
    ordinary_ambiguous = []
    ordinary_matched = []
    for row in ordinary_eq:
        key = (row["symbol"], row["isin"], row["series"])
        matches = security_by_triplet.get(key, [])
        if len(matches) == 1:
            ordinary_matched.append(row)
        elif not matches:
            ordinary_missing.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                }
            )
        else:
            ordinary_ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                    "security_match_count": len(matches),
                }
            )

    dummy_diagnostics = []
    dummy_exact_match_total = 0
    dummy_identity_any_series_match_total = 0
    for row in dummy_eq:
        triplet = (row["symbol"], row["isin"], row["series"])
        identity = (row["symbol"], row["isin"])
        exact_matches = security_by_triplet.get(triplet, [])
        identity_matches = security_by_identity.get(identity, [])
        dummy_exact_match_total += len(exact_matches)
        dummy_identity_any_series_match_total += len(identity_matches)
        dummy_diagnostics.append(
            {
                "company_name": row["company_name"],
                "industry": row["industry"],
                "symbol": row["symbol"],
                "isin": row["isin"],
                "series": row["series"],
                "exact_triplet_match_count": len(exact_matches),
                "same_symbol_isin_any_series_match_count": len(
                    identity_matches
                ),
                "same_identity_series": sorted(
                    {match["series"] for match in identity_matches}
                ),
            }
        )

    non_eq_missing = []
    non_eq_ambiguous = []
    non_eq_matched = []
    for row in parent_non_eq:
        key = (row["symbol"], row["isin"], row["series"])
        matches = security_by_triplet.get(key, [])
        if len(matches) == 1:
            non_eq_matched.append(row)
        elif not matches:
            non_eq_missing.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                }
            )
        else:
            non_eq_ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                    "security_match_count": len(matches),
                }
            )

    projected = _identity_diagnostics(ordinary_matched)
    observed_dummy_set = {
        (row["symbol"], row["isin"], row["series"]) for row in dummy_eq
    }

    ordinary_match_fraction = (
        0.0
        if not ordinary_eq
        else len(ordinary_matched) / len(ordinary_eq)
    )
    non_eq_match_fraction = (
        0.0
        if not parent_non_eq
        else len(non_eq_matched) / len(parent_non_eq)
    )

    gates = {
        "parent_raw_sha_exact": parent_sha == PARENT_RAW_SHA256,
        "security_raw_sha_exact": security_sha == SECURITY_RAW_SHA256,
        "parent_row_count_exact": len(parent_rows) == PARENT_ROW_COUNT,
        "parent_eq_row_count_exact": len(parent_eq) == PARENT_EQ_COUNT,
        "parent_non_eq_row_count_exact": (
            len(parent_non_eq) == PARENT_NON_EQ_COUNT
        ),
        "ordinary_eq_row_count_exact": len(ordinary_eq) == ORDINARY_EQ_COUNT,
        "ordinary_eq_exact_match_fraction_100pct": (
            ordinary_match_fraction == 1.0
        ),
        "ordinary_eq_missing_count_zero": len(ordinary_missing) == 0,
        "ordinary_eq_ambiguous_count_zero": len(ordinary_ambiguous) == 0,
        "dummy_eq_row_count_exact": len(dummy_eq) == DUMMY_EQ_COUNT,
        "dummy_identity_set_matches_r2_missing_exactly": (
            observed_dummy_set == R2_MISSING_IDENTITIES
        ),
        "dummy_exact_triplet_match_count_total_zero": (
            dummy_exact_match_total == 0
        ),
        "dummy_same_identity_any_series_match_count_total_zero": (
            dummy_identity_any_series_match_total == 0
        ),
        "non_eq_exact_match_fraction_100pct": (
            non_eq_match_fraction == 1.0
        ),
        "non_eq_missing_count_zero": len(non_eq_missing) == 0,
        "non_eq_ambiguous_count_zero": len(non_eq_ambiguous) == 0,
        "projected_tradable_eq_row_count_exact": (
            projected["row_count"] == ORDINARY_EQ_COUNT
        ),
        "projected_tradable_eq_unique_identity_count_exact": (
            projected["unique_identity_count"] == ORDINARY_EQ_COUNT
        ),
        "projected_tradable_eq_zero_duplicate_identities": (
            projected["duplicate_identity_count"] == 0
        ),
        "projected_tradable_eq_zero_symbol_conflicts": (
            projected["symbol_conflict_count"] == 0
        ),
        "projected_tradable_eq_zero_isin_conflicts": (
            projected["isin_conflict_count"] == 0
        ),
        "projected_tradable_eq_industry_coverage_100pct": (
            projected["industry_coverage"] == 1.0
        ),
        "projected_tradable_eq_isin_coverage_100pct": (
            projected["isin_coverage"] == 1.0
        ),
        "projected_tradable_eq_identity_text_complete": (
            projected["identity_text_complete"]
        ),
    }
    passed = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D015_R3_DIAGNOSTIC_ID,
        "status": (
            "PASS_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS"
            if passed
            else "FAIL_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS"
        ),
        "evidence_class": "SOURCE_SEMANTICS_NO_RETURN_OUTCOMES",
        "parents": {
            "d015_status": "FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY",
            "d015_status_changed": False,
            "d015_r1_status": "FAIL_EQ_PROJECTION_SEMANTICS",
            "d015_r1_status_changed": False,
            "d015_r2_status": "FAIL_TRIPLET_EQ_PROJECTION_SEMANTICS",
            "d015_r2_status_changed": False,
            "d015_r2_report_sha256": (
                "71cf04c4ed5c61248a7581bb5c000141150af7ef361dc0493e1510205c3b865b"
            ),
        },
        "semantic_basis": {
            "classification": "DOCUMENTED_INDEX_DUMMY_PLACEHOLDER",
            "parent_series_required": "EQ",
            "symbol_prefix_required": "DUMMY",
            "exact_triplet_match_count_required": 0,
            "same_symbol_isin_any_series_match_count_required": 0,
            "fallback_allowed": False,
        },
        "parent_source": {
            "raw_sha256": parent_sha,
            "row_count": len(parent_rows),
            "eq_row_count": len(parent_eq),
            "non_eq_row_count": len(parent_non_eq),
        },
        "security_source": {
            "raw_sha256": security_sha,
            "parsed_row_count": len(security_rows),
            "symbol_isin_duplicate_count": security_diagnostics[
                "duplicate_identity_count"
            ],
            "series_counts": security_diagnostics["series_counts"],
        },
        "ordinary_eq_correspondence": {
            "row_count": len(ordinary_eq),
            "matched_count": len(ordinary_matched),
            "match_fraction": ordinary_match_fraction,
            "missing_count": len(ordinary_missing),
            "ambiguous_count": len(ordinary_ambiguous),
            "missing": ordinary_missing[:25],
            "ambiguous": ordinary_ambiguous[:25],
        },
        "dummy_placeholders": {
            "row_count": len(dummy_eq),
            "exact_triplet_match_count_total": dummy_exact_match_total,
            "same_identity_any_series_match_count_total": (
                dummy_identity_any_series_match_total
            ),
            "identity_set_matches_r2_missing_exactly": (
                observed_dummy_set == R2_MISSING_IDENTITIES
            ),
            "rows": sorted(
                dummy_diagnostics,
                key=lambda item: (item["symbol"], item["isin"]),
            ),
        },
        "non_eq_correspondence": {
            "row_count": len(parent_non_eq),
            "matched_count": len(non_eq_matched),
            "match_fraction": non_eq_match_fraction,
            "missing_count": len(non_eq_missing),
            "ambiguous_count": len(non_eq_ambiguous),
        },
        "projected_tradable_eq_subset": {
            "filter_rule": (
                'Series == "EQ" AND NOT Symbol.startswith("DUMMY") '
                "AND exactly_one_same_snapshot_security_triplet"
            ),
            **projected,
        },
        "promotion_gates": gates,
        "prospective_industry_capture_design_authorized": passed,
        "future_dummy_count_frozen": False,
        "historical_backfill_authorized": False,
        "rm001_factor_directly_allowed": False,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
