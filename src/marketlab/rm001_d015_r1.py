from __future__ import annotations

import csv
import gzip
import io
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import parse_constituent_csv
from marketlab.rm001_size_source import security_master_url

D015_R1_DIAGNOSTIC_ID = "RM001-D015-R1-v1"
PARENT_RAW_SHA256 = (
    "c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f"
)
PARENT_ROW_COUNT = 755
PARENT_EQ_COUNT = 745
PARENT_NON_EQ_COUNT = 10
SECURITY_SESSION = date(2026, 10, 1)
SECURITY_URL = security_master_url(SECURITY_SESSION)
SECURITY_REQUIRED_FIELDS = (
    "TckrSymb",
    "SctySrs",
    "ISIN",
    "FinInstrmNm",
    "DelFlg",
)


def parse_security_master_all_series(
    raw_gzip: bytes,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    try:
        text = gzip.decompress(raw_gzip).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise AlphaContractError(
            "D015-R1 security master must be valid UTF-8 gzip"
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise AlphaContractError("D015-R1 security master has no header")
    fields = [str(field).strip() for field in reader.fieldnames]
    missing = [
        field for field in SECURITY_REQUIRED_FIELDS if field not in fields
    ]
    if missing:
        raise AlphaContractError(
            f"D015-R1 security-master required columns missing: {missing}"
        )

    rows: list[dict[str, str]] = []
    identity_counts: Counter[tuple[str, str]] = Counter()
    series_counts: Counter[str] = Counter()
    missing_identity_count = 0

    for raw in reader:
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw.items()
            if key is not None
        }
        symbol = row.get("TckrSymb", "").upper()
        isin = row.get("ISIN", "").upper()
        series = row.get("SctySrs", "").upper()
        if not symbol or not isin:
            missing_identity_count += 1
            continue
        identity_counts[(symbol, isin)] += 1
        series_counts[series] += 1
        rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "series": series,
                "security_name": row.get("FinInstrmNm", ""),
                "deletion_flag": row.get("DelFlg", ""),
            }
        )

    duplicate_identities = sorted(
        [
            {
                "symbol": identity[0],
                "isin": identity[1],
                "row_count": count,
            }
            for identity, count in identity_counts.items()
            if count > 1
        ],
        key=lambda item: (item["symbol"], item["isin"]),
    )
    diagnostics = {
        "parsed_row_count": len(rows),
        "missing_identity_row_count": missing_identity_count,
        "duplicate_identity_count": len(duplicate_identities),
        "duplicate_identities": duplicate_identities[:25],
        "series_counts": dict(sorted(series_counts.items())),
    }
    return rows, diagnostics


def build_d015_r1_report(
    *,
    parent_raw: bytes,
    security_raw: bytes,
) -> dict[str, Any]:
    parent_sha = sha256_bytes(parent_raw)
    parent = parse_constituent_csv(parent_raw)
    parent_rows = parent["rows"]

    security_rows, security_diagnostics = parse_security_master_all_series(
        security_raw
    )
    security_by_identity: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in security_rows:
        security_by_identity[(row["symbol"], row["isin"])].append(row)

    parent_eq = [row for row in parent_rows if row["series"] == "EQ"]
    parent_non_eq = [row for row in parent_rows if row["series"] != "EQ"]

    joined_count = 0
    series_agreement_count = 0
    parent_eq_confirmed_eq = 0
    parent_non_eq_confirmed_non_eq = 0
    parent_eq_security_non_eq_conflicts = []
    parent_non_eq_security_eq_conflicts = []
    missing_or_ambiguous = []
    non_eq_correspondence = []

    for row in parent_rows:
        identity = (row["symbol"], row["isin"])
        matches = security_by_identity.get(identity, [])
        if len(matches) != 1:
            missing_or_ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "parent_series": row["series"],
                    "security_match_count": len(matches),
                }
            )
            continue

        joined_count += 1
        security = matches[0]
        if security["series"] == row["series"]:
            series_agreement_count += 1

        if row["series"] == "EQ":
            if security["series"] == "EQ":
                parent_eq_confirmed_eq += 1
            else:
                parent_eq_security_non_eq_conflicts.append(
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                        "parent_series": row["series"],
                        "security_series": security["series"],
                    }
                )
        else:
            if security["series"] != "EQ":
                parent_non_eq_confirmed_non_eq += 1
            else:
                parent_non_eq_security_eq_conflicts.append(
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                        "parent_series": row["series"],
                        "security_series": security["series"],
                    }
                )
            non_eq_correspondence.append(
                {
                    "company_name": row["company_name"],
                    "industry": row["industry"],
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "parent_series": row["series"],
                    "security_series": security["series"],
                    "security_name": security["security_name"],
                    "deletion_flag": security["deletion_flag"],
                    "series_agrees": security["series"] == row["series"],
                }
            )

    parent_count = len(parent_rows)
    identity_join_coverage = (
        0.0 if parent_count == 0 else joined_count / parent_count
    )
    series_agreement_coverage = (
        0.0 if parent_count == 0 else series_agreement_count / parent_count
    )
    parent_eq_confirmed_fraction = (
        0.0
        if len(parent_eq) == 0
        else parent_eq_confirmed_eq / len(parent_eq)
    )
    parent_non_eq_confirmed_fraction = (
        0.0
        if len(parent_non_eq) == 0
        else parent_non_eq_confirmed_non_eq / len(parent_non_eq)
    )

    eq_identity_counts: Counter[tuple[str, str]] = Counter(
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
    projected_name_symbol_complete = all(
        row["company_name"] and row["symbol"] for row in parent_eq
    )

    gates = {
        "parent_raw_sha_exact": parent_sha == PARENT_RAW_SHA256,
        "parent_row_count_exact": parent_count == PARENT_ROW_COUNT,
        "parent_eq_row_count_exact": len(parent_eq) == PARENT_EQ_COUNT,
        "parent_non_eq_row_count_exact": (
            len(parent_non_eq) == PARENT_NON_EQ_COUNT
        ),
        "security_duplicate_identity_count_zero": (
            security_diagnostics["duplicate_identity_count"] == 0
        ),
        "exact_identity_join_coverage_100pct": identity_join_coverage == 1.0,
        "series_agreement_coverage_100pct": (
            series_agreement_coverage == 1.0
        ),
        "parent_eq_confirmed_eq_fraction_100pct": (
            parent_eq_confirmed_fraction == 1.0
        ),
        "parent_non_eq_confirmed_non_eq_fraction_100pct": (
            parent_non_eq_confirmed_fraction == 1.0
        ),
        "zero_parent_eq_security_non_eq_conflicts": (
            len(parent_eq_security_non_eq_conflicts) == 0
        ),
        "zero_parent_non_eq_security_eq_conflicts": (
            len(parent_non_eq_security_eq_conflicts) == 0
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
        "projected_eq_name_symbol_complete": projected_name_symbol_complete,
    }
    passed = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D015_R1_DIAGNOSTIC_ID,
        "status": (
            "PASS_EQ_PROJECTION_SEMANTICS"
            if passed
            else "FAIL_EQ_PROJECTION_SEMANTICS"
        ),
        "evidence_class": "SOURCE_SEMANTICS_NO_RETURN_OUTCOMES",
        "parent": {
            "diagnostic_id": "RM001-D015-v1",
            "status": "FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY",
            "status_changed_by_r1": False,
            "raw_sha256": parent_sha,
            "row_count": parent_count,
            "eq_row_count": len(parent_eq),
            "non_eq_row_count": len(parent_non_eq),
        },
        "security_source": {
            "session_date": SECURITY_SESSION.isoformat(),
            "source_url": SECURITY_URL,
            "raw_sha256": sha256_bytes(security_raw),
            **security_diagnostics,
        },
        "correspondence": {
            "joined_identity_count": joined_count,
            "identity_join_coverage": identity_join_coverage,
            "series_agreement_count": series_agreement_count,
            "series_agreement_coverage": series_agreement_coverage,
            "parent_eq_confirmed_eq_count": parent_eq_confirmed_eq,
            "parent_eq_confirmed_eq_fraction": parent_eq_confirmed_fraction,
            "parent_non_eq_confirmed_non_eq_count": (
                parent_non_eq_confirmed_non_eq
            ),
            "parent_non_eq_confirmed_non_eq_fraction": (
                parent_non_eq_confirmed_fraction
            ),
            "missing_or_ambiguous_count": len(missing_or_ambiguous),
            "missing_or_ambiguous": missing_or_ambiguous[:25],
            "parent_eq_security_non_eq_conflicts": (
                parent_eq_security_non_eq_conflicts[:25]
            ),
            "parent_non_eq_security_eq_conflicts": (
                parent_non_eq_security_eq_conflicts[:25]
            ),
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
            "name_symbol_complete": projected_name_symbol_complete,
        },
        "promotion_gates": gates,
        "prospective_eq_capture_authorized": passed,
        "d015_status_changed": False,
        "historical_backfill_authorized": False,
        "rm001_factor_directly_allowed": False,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
