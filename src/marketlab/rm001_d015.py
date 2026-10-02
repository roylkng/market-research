from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

D015_DIAGNOSTIC_ID = "RM001-D015-v1"
SOURCE_URL = (
    "https://nsearchives.nseindia.com/content/indices/"
    "ind_niftytotalmarket_list.csv"
)
REQUIRED_COLUMNS = (
    "Company Name",
    "Industry",
    "Symbol",
    "Series",
    "ISIN Code",
)
MIN_ROW_COUNT = 700
MIN_IDENTITY_COUNT = 700
MIN_INDUSTRY_COVERAGE = 0.99
MIN_EQ_COVERAGE = 0.99
MIN_INDUSTRY_LABEL_COUNT = 10
MAX_INDUSTRY_LABEL_COUNT = 40


def parse_constituent_csv(raw: bytes) -> dict[str, Any]:
    if not raw:
        raise AlphaContractError("D015 source bytes are empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("D015 CSV must be UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise AlphaContractError("D015 CSV has no header")

    normalized_header = tuple(str(value).strip() for value in reader.fieldnames)
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized_header]
    if missing:
        raise AlphaContractError(
            f"D015 required columns missing: {missing}; "
            f"observed={list(normalized_header)}"
        )

    rows = []
    for raw_row in reader:
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if not any(row.values()):
            continue
        rows.append(
            {
                "company_name": row["Company Name"],
                "industry": row["Industry"],
                "symbol": row["Symbol"].upper(),
                "series": row["Series"].upper(),
                "isin": row["ISIN Code"].upper(),
            }
        )
    if not rows:
        raise AlphaContractError("D015 CSV contains no data rows")

    return {
        "required_columns": list(REQUIRED_COLUMNS),
        "observed_columns": list(normalized_header),
        "rows": rows,
    }


def build_d015_report(*, raw: bytes, source_url: str = SOURCE_URL) -> dict[str, Any]:
    parsed = parse_constituent_csv(raw)
    rows = parsed["rows"]
    total = len(rows)

    identity_counts: dict[tuple[str, str], int] = defaultdict(int)
    symbol_to_isins: dict[str, set[str]] = defaultdict(set)
    isin_to_symbols: dict[str, set[str]] = defaultdict(set)

    missing_company = 0
    missing_symbol = 0
    missing_isin = 0
    missing_industry = 0
    eq_count = 0
    industries: set[str] = set()

    for row in rows:
        company = row["company_name"]
        symbol = row["symbol"]
        isin = row["isin"]
        industry = row["industry"]
        series = row["series"]

        if not company:
            missing_company += 1
        if not symbol:
            missing_symbol += 1
        if not isin:
            missing_isin += 1
        if not industry:
            missing_industry += 1
        else:
            industries.add(industry)
        if series == "EQ":
            eq_count += 1

        if symbol and isin:
            identity_counts[(symbol, isin)] += 1
            symbol_to_isins[symbol].add(isin)
            isin_to_symbols[isin].add(symbol)

    duplicate_identities = sorted(
        [
            {"symbol": identity[0], "isin": identity[1], "row_count": count}
            for identity, count in identity_counts.items()
            if count > 1
        ],
        key=lambda item: (item["symbol"], item["isin"]),
    )
    symbol_conflicts = sorted(
        [
            {"symbol": symbol, "isins": sorted(isins)}
            for symbol, isins in symbol_to_isins.items()
            if len(isins) > 1
        ],
        key=lambda item: item["symbol"],
    )
    isin_conflicts = sorted(
        [
            {"isin": isin, "symbols": sorted(symbols)}
            for isin, symbols in isin_to_symbols.items()
            if len(symbols) > 1
        ],
        key=lambda item: item["isin"],
    )

    industry_coverage = (total - missing_industry) / total
    isin_coverage = (total - missing_isin) / total
    eq_coverage = eq_count / total
    unique_identity_count = len(identity_counts)
    industry_label_count = len(industries)

    gates = {
        "minimum_row_count": total >= MIN_ROW_COUNT,
        "minimum_unique_identity_count": unique_identity_count >= MIN_IDENTITY_COUNT,
        "zero_duplicate_identities": len(duplicate_identities) == 0,
        "zero_symbol_to_multiple_isin_conflicts": len(symbol_conflicts) == 0,
        "zero_isin_to_multiple_symbol_conflicts": len(isin_conflicts) == 0,
        "minimum_industry_coverage": industry_coverage >= MIN_INDUSTRY_COVERAGE,
        "required_isin_coverage": isin_coverage == 1.0,
        "minimum_eq_series_coverage": eq_coverage >= MIN_EQ_COVERAGE,
        "industry_label_count_range": (
            MIN_INDUSTRY_LABEL_COUNT
            <= industry_label_count
            <= MAX_INDUSTRY_LABEL_COUNT
        ),
        "zero_missing_company_names": missing_company == 0,
        "zero_missing_symbols": missing_symbol == 0,
    }
    passed = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D015_DIAGNOSTIC_ID,
        "status": (
            "PASS_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY"
            if passed
            else "FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY"
        ),
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "source_url": source_url,
        "raw_sha256": sha256_bytes(raw),
        "raw_byte_count": len(raw),
        "required_columns": parsed["required_columns"],
        "observed_columns": parsed["observed_columns"],
        "row_count": total,
        "unique_identity_count": unique_identity_count,
        "duplicate_identity_count": len(duplicate_identities),
        "symbol_to_multiple_isin_conflict_count": len(symbol_conflicts),
        "isin_to_multiple_symbol_conflict_count": len(isin_conflicts),
        "missing_company_name_count": missing_company,
        "missing_symbol_count": missing_symbol,
        "missing_isin_count": missing_isin,
        "missing_industry_count": missing_industry,
        "industry_coverage": industry_coverage,
        "isin_coverage": isin_coverage,
        "eq_series_count": eq_count,
        "eq_series_coverage": eq_coverage,
        "industry_label_count": industry_label_count,
        "industry_labels": sorted(industries),
        "promotion_gates": gates,
        "prospective_capture_design_authorized": passed,
        "historical_backfill_authorized": False,
        "rm001_factor_directly_allowed": False,
        "return_labels_opened": False,
        "alpha_outcomes_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "duplicate_identities": duplicate_identities[:25],
        "symbol_conflicts": symbol_conflicts[:25],
        "isin_conflicts": isin_conflicts[:25],
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
