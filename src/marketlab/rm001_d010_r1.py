from __future__ import annotations

import io
import math
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_d010 import (
    _annual_member,
    _normalize_identifier,
    _xlsx_table,
)

R1_ID = "RM001-D010-R1-v1"
EXCEL_EPOCH = datetime(1899, 12, 30)

_REQUIRED_GENERAL = {
    "appid",
    "tlasubmitteddt",
    "symbsymbol",
    "corporateidentitynumbercinofthelistedentity",
    "currentfinancialyearstartdate",
    "currentfinancialyearenddate",
}
_REQUIRED_PRODUCT = {
    "appid",
    "symbsymbol",
    "niccodesoldbytheentity",
}


def parse_submission_timestamp(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    iso_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(iso_raw)
        return parsed.isoformat()
    except ValueError:
        pass

    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue

    try:
        serial = float(raw)
    except ValueError:
        return None
    if not math.isfinite(serial) or serial <= 0 or serial > 1_000_000:
        return None
    return (EXCEL_EPOCH + timedelta(days=serial)).isoformat()


def _stable_identity(row: dict[str, str | None]) -> str:
    cin = str(
        row.get("corporateidentitynumbercinofthelistedentity") or ""
    ).strip().upper()
    symbol = str(row.get("symbsymbol") or "").strip().upper()
    if cin:
        return f"CIN:{cin}"
    if symbol:
        return f"SYMBOL:{symbol}"
    return ""


def analyze_duplicate_rows(
    *,
    year: str,
    general_rows: list[dict[str, str | None]],
    product_rows: list[dict[str, str | None]],
) -> dict[str, Any]:
    identities: dict[str, list[dict[str, Any]]] = defaultdict(list)
    app_to_identities: dict[str, set[str]] = defaultdict(set)

    for row in general_rows:
        identity = _stable_identity(row)
        if not identity:
            continue
        app_id = _normalize_identifier(row.get("appid"))
        record = {
            "app_id": app_id,
            "submission_timestamp_raw": str(
                row.get("tlasubmitteddt") or ""
            ).strip(),
            "submission_timestamp": parse_submission_timestamp(
                row.get("tlasubmitteddt")
            ),
            "symbol": str(row.get("symbsymbol") or "").strip().upper(),
            "cin": str(
                row.get("corporateidentitynumbercinofthelistedentity") or ""
            ).strip().upper(),
            "financial_year_start": str(
                row.get("currentfinancialyearstartdate") or ""
            ).strip(),
            "financial_year_end": str(
                row.get("currentfinancialyearenddate") or ""
            ).strip(),
        }
        identities[identity].append(record)
        if app_id:
            app_to_identities[app_id].add(identity)

    app_conflicts = {
        app_id: sorted(values)
        for app_id, values in app_to_identities.items()
        if len(values) > 1
    }

    nic_by_app: dict[str, set[str]] = defaultdict(set)
    product_rows_by_app: dict[str, int] = defaultdict(int)
    orphan_product_rows = 0
    for row in product_rows:
        app_id = _normalize_identifier(row.get("appid"))
        if not app_id:
            continue
        product_rows_by_app[app_id] += 1
        if app_id not in app_to_identities:
            orphan_product_rows += 1
            continue
        nic = _normalize_identifier(row.get("niccodesoldbytheentity"))
        if nic:
            nic_by_app[app_id].add(nic)

    duplicate_groups = []
    total_duplicate_filings = 0
    excess_duplicate_records = 0
    parseable_timestamp_records = 0
    explicit_nic_records = 0
    deterministic_groups = 0
    timestamp_collision_groups = 0
    reporting_period_conflict_groups = 0
    symbol_change_groups = 0
    nic_change_groups = 0

    for identity, raw_records in sorted(identities.items()):
        if len(raw_records) <= 1:
            continue
        total_duplicate_filings += len(raw_records)
        excess_duplicate_records += len(raw_records) - 1

        records = []
        for record in raw_records:
            app_id = record["app_id"]
            nic_codes = sorted(nic_by_app.get(app_id, set()))
            enriched = {
                **record,
                "nic_codes": nic_codes,
                "nic_count": len(nic_codes),
                "product_row_count": product_rows_by_app.get(app_id, 0),
            }
            records.append(enriched)
            if record["submission_timestamp"] is not None:
                parseable_timestamp_records += 1
            if nic_codes:
                explicit_nic_records += 1

        app_ids = [record["app_id"] for record in records]
        parsed_timestamps = [
            record["submission_timestamp"]
            for record in records
            if record["submission_timestamp"] is not None
        ]
        periods = {
            (
                record["financial_year_start"],
                record["financial_year_end"],
            )
            for record in records
        }
        symbols = {
            record["symbol"] for record in records if record["symbol"]
        }
        nic_sets = {
            tuple(record["nic_codes"])
            for record in records
        }

        gates = {
            "all_app_ids_present": all(bool(value) for value in app_ids),
            "app_ids_unique_within_identity": (
                len(set(app_ids)) == len(app_ids)
            ),
            "all_submission_timestamps_parseable": (
                len(parsed_timestamps) == len(records)
            ),
            "submission_timestamps_unique": (
                len(set(parsed_timestamps)) == len(records)
            ),
            "reporting_period_consistent": len(periods) == 1,
            "every_filing_has_explicit_nic": all(
                bool(record["nic_codes"]) for record in records
            ),
            "no_app_id_identity_conflict": all(
                app_id not in app_conflicts for app_id in app_ids if app_id
            ),
        }
        deterministic = all(gates.values())
        if deterministic:
            deterministic_groups += 1
        if not gates["submission_timestamps_unique"]:
            timestamp_collision_groups += 1
        if not gates["reporting_period_consistent"]:
            reporting_period_conflict_groups += 1
        if len(symbols) > 1:
            symbol_change_groups += 1
        if len(nic_sets) > 1:
            nic_change_groups += 1

        records.sort(
            key=lambda record: (
                record["submission_timestamp"] or "",
                record["app_id"],
            )
        )
        duplicate_groups.append(
            {
                "stable_identity": identity,
                "filing_count": len(records),
                "symbols": sorted(symbols),
                "symbol_changed": len(symbols) > 1,
                "nic_changed_across_filings": len(nic_sets) > 1,
                "gates": gates,
                "deterministic_amendment_chain": deterministic,
                "records": records,
            }
        )

    def fraction(numerator: int, denominator: int) -> float:
        return 0.0 if denominator == 0 else numerator / denominator

    duplicate_group_count = len(duplicate_groups)
    metrics = {
        "year": year,
        "general_record_count": len(general_rows),
        "stable_identity_count": len(identities),
        "duplicate_group_count": duplicate_group_count,
        "duplicate_filing_record_count": total_duplicate_filings,
        "excess_duplicate_record_count": excess_duplicate_records,
        "deterministic_amendment_group_count": deterministic_groups,
        "deterministic_amendment_group_fraction": fraction(
            deterministic_groups,
            duplicate_group_count,
        ),
        "duplicate_filing_parseable_timestamp_fraction": fraction(
            parseable_timestamp_records,
            total_duplicate_filings,
        ),
        "duplicate_filing_explicit_nic_fraction": fraction(
            explicit_nic_records,
            total_duplicate_filings,
        ),
        "timestamp_collision_group_count": timestamp_collision_groups,
        "reporting_period_conflict_group_count": (
            reporting_period_conflict_groups
        ),
        "symbol_change_group_count": symbol_change_groups,
        "nic_change_group_count": nic_change_groups,
        "app_id_identity_conflict_count": len(app_conflicts),
        "orphan_product_row_count": orphan_product_rows,
        "duplicate_groups": duplicate_groups,
    }
    metrics["gates"] = {
        "at_least_one_duplicate_group": duplicate_group_count > 0,
        "all_duplicate_groups_deterministic": (
            deterministic_groups == duplicate_group_count
            and duplicate_group_count > 0
        ),
        "all_duplicate_filings_timestamp_parseable": (
            parseable_timestamp_records == total_duplicate_filings
            and total_duplicate_filings > 0
        ),
        "all_duplicate_filings_have_explicit_nic": (
            explicit_nic_records == total_duplicate_filings
            and total_duplicate_filings > 0
        ),
        "zero_timestamp_collisions": timestamp_collision_groups == 0,
        "zero_app_id_identity_conflicts": len(app_conflicts) == 0,
    }
    metrics["year_pass"] = all(metrics["gates"].values())
    return metrics


def parse_r1_annual_archive(
    *,
    year: str,
    raw: bytes,
) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError(
            f"R1 {year} annual archive is invalid"
        ) from exc

    with archive:
        general_name = _annual_member(archive, kind="general")
        product_name = _annual_member(archive, kind="product")
        general_raw = archive.read(general_name)
        product_raw = archive.read(product_name)

    general_headers, general_rows = _xlsx_table(general_raw)
    product_headers, product_rows = _xlsx_table(product_raw)
    if not _REQUIRED_GENERAL.issubset(set(general_headers)):
        raise AlphaContractError(
            f"R1 {year} entity table header contract changed"
        )
    if not _REQUIRED_PRODUCT.issubset(set(product_headers)):
        raise AlphaContractError(
            f"R1 {year} product table header contract changed"
        )

    report = analyze_duplicate_rows(
        year=year,
        general_rows=general_rows,
        product_rows=product_rows,
    )
    report["general_workbook_path"] = general_name
    report["product_workbook_path"] = product_name
    return report


def build_r1_report(
    *,
    fy2023_24_raw: bytes,
    fy2024_25_raw: bytes,
) -> dict[str, Any]:
    years = {
        "FY2023-24": parse_r1_annual_archive(
            year="FY2023-24",
            raw=fy2023_24_raw,
        ),
        "FY2024-25": parse_r1_annual_archive(
            year="FY2024-25",
            raw=fy2024_25_raw,
        ),
    }
    passed = all(report["year_pass"] for report in years.values())
    failure_reasons = []
    for year, report in years.items():
        for gate, value in report["gates"].items():
            if not value:
                failure_reasons.append(f"{year}:{gate}")

    result: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": R1_ID,
        "evidence_class": "SOURCE_SEMANTICS_NO_RETURN_OUTCOMES",
        "parent_d010_status": "FAIL_SOURCE_FEASIBILITY",
        "parent_d010_result_sha256": (
            "21aff20c7c3300ecf104d049fdbcad3749bb160735f478643a40bab36618a976"
        ),
        "d010_status_changed": False,
        "d011_authorized": False,
        "years": years,
        "status": (
            "PASS_DUPLICATE_SEMANTICS"
            if passed
            else "FAIL_DUPLICATE_SEMANTICS"
        ),
        "failure_reasons": failure_reasons,
        "d012_authorized": passed,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result
