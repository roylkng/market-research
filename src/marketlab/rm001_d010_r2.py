from __future__ import annotations

import io
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_d010 import (
    _annual_member,
    _xlsx_table,
)
from marketlab.rm001_d010_r1 import (
    analyze_duplicate_rows,
)

R2_ID = "RM001-D010-R2-v1"
TARGET_START = "2024-04-01"
TARGET_END = "2025-03-31"

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


def parse_reporting_date(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        pass

    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            parsed = time.strptime(raw, fmt)
        except ValueError:
            continue
        return (
            f"{parsed.tm_year:04d}-{parsed.tm_mon:02d}-{parsed.tm_mday:02d}"
        )

    iso_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(iso_raw)
    except ValueError:
        return None
    return parsed.date().isoformat()


def _period_overlap(
    left: tuple[str, str],
    right: tuple[str, str],
) -> bool:
    left_start = date.fromisoformat(left[0])
    left_end = date.fromisoformat(left[1])
    right_start = date.fromisoformat(right[0])
    right_end = date.fromisoformat(right[1])
    return not (left_end < right_start or right_end < left_start)


def analyze_cross_period_groups(
    *,
    year: str,
    general_rows: list[dict[str, str | None]],
    product_rows: list[dict[str, str | None]],
    target_start: str,
    target_end: str,
) -> dict[str, Any]:
    r1 = analyze_duplicate_rows(
        year=year,
        general_rows=general_rows,
        product_rows=product_rows,
    )

    conflict_groups = []
    total_records = 0
    parseable_period_records = 0
    explicit_nic_records = 0
    overlapping_period_pairs = 0
    deterministic_groups = 0
    target_period_group_count = 0
    target_period_record_count = 0

    for group in r1["duplicate_groups"]:
        enriched_records = []
        parsed_periods = set()
        raw_periods = set()

        for record in group["records"]:
            raw_pair = (
                str(record.get("financial_year_start") or "").strip(),
                str(record.get("financial_year_end") or "").strip(),
            )
            raw_periods.add(raw_pair)
            parsed_start = parse_reporting_date(raw_pair[0])
            parsed_end = parse_reporting_date(raw_pair[1])
            parsed_pair = (
                (parsed_start, parsed_end)
                if parsed_start is not None and parsed_end is not None
                else None
            )
            if parsed_pair is not None:
                parsed_periods.add(parsed_pair)
            enriched_records.append(
                {
                    **record,
                    "reporting_period_start": parsed_start,
                    "reporting_period_end": parsed_end,
                }
            )

        if len(raw_periods) <= 1:
            continue

        total_records += len(enriched_records)
        partitions: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        unparseable_records = 0
        invalid_period_records = 0

        for record in enriched_records:
            start = record["reporting_period_start"]
            end = record["reporting_period_end"]
            if start is None or end is None:
                unparseable_records += 1
                continue
            parseable_period_records += 1
            if date.fromisoformat(end) < date.fromisoformat(start):
                invalid_period_records += 1
                continue
            partitions[(start, end)].append(record)
            if record["nic_codes"]:
                explicit_nic_records += 1

        periods = sorted(partitions)
        group_overlap_pairs = []
        for index, left in enumerate(periods):
            for right in periods[index + 1 :]:
                if _period_overlap(left, right):
                    group_overlap_pairs.append([list(left), list(right)])
        overlapping_period_pairs += len(group_overlap_pairs)

        partition_reports = []
        for period in periods:
            records = partitions[period]
            timestamps = [
                record["submission_timestamp"]
                for record in records
                if record["submission_timestamp"] is not None
            ]
            app_ids = [record["app_id"] for record in records]
            partition_gates = {
                "all_app_ids_present": all(bool(value) for value in app_ids),
                "app_ids_unique": len(set(app_ids)) == len(app_ids),
                "all_submission_timestamps_parseable": (
                    len(timestamps) == len(records)
                ),
                "submission_timestamps_unique": (
                    len(set(timestamps)) == len(records)
                ),
                "every_filing_has_explicit_nic": all(
                    bool(record["nic_codes"]) for record in records
                ),
            }
            deterministic_partition = all(partition_gates.values())
            records = sorted(
                records,
                key=lambda record: (
                    record["submission_timestamp"] or "",
                    record["app_id"],
                ),
            )
            partition_reports.append(
                {
                    "reporting_period_start": period[0],
                    "reporting_period_end": period[1],
                    "filing_count": len(records),
                    "matches_frozen_archive_target_period": (
                        period == (target_start, target_end)
                    ),
                    "gates": partition_gates,
                    "deterministic_partition": deterministic_partition,
                    "records": records,
                }
            )

        target_partitions = [
            partition
            for partition in partition_reports
            if partition["matches_frozen_archive_target_period"]
        ]
        target_period_group_count += int(bool(target_partitions))
        target_period_record_count += sum(
            int(partition["filing_count"])
            for partition in target_partitions
        )

        all_records_have_nic = all(
            bool(record["nic_codes"]) for record in enriched_records
        )
        all_records_have_app = all(
            bool(record["app_id"]) for record in enriched_records
        )
        all_records_have_timestamp = all(
            record["submission_timestamp"] is not None
            for record in enriched_records
        )
        all_timestamps = [
            record["submission_timestamp"]
            for record in enriched_records
            if record["submission_timestamp"] is not None
        ]

        gates = {
            "at_least_two_distinct_parseable_periods": len(periods) >= 2,
            "all_reporting_periods_parseable": (
                unparseable_records == 0
                and len(periods) >= 2
            ),
            "all_reporting_periods_valid": invalid_period_records == 0,
            "reporting_periods_non_overlapping": len(group_overlap_pairs) == 0,
            "all_app_ids_present": all_records_have_app,
            "all_submission_timestamps_parseable": all_records_have_timestamp,
            "submission_timestamps_unique_across_group": (
                len(all_timestamps) == len(set(all_timestamps))
            ),
            "every_filing_has_explicit_nic": all_records_have_nic,
            "all_period_partitions_deterministic": all(
                partition["deterministic_partition"]
                for partition in partition_reports
            ),
            "no_app_id_identity_conflict": (
                r1["app_id_identity_conflict_count"] == 0
            ),
        }
        deterministic = all(gates.values())
        if deterministic:
            deterministic_groups += 1

        symbols = sorted(
            {
                str(record.get("symbol") or "")
                for record in enriched_records
                if str(record.get("symbol") or "")
            }
        )
        nic_sets_by_period = {
            f"{partition['reporting_period_start']}__{partition['reporting_period_end']}": sorted(
                {
                    nic
                    for record in partition["records"]
                    for nic in record["nic_codes"]
                }
            )
            for partition in partition_reports
        }

        conflict_groups.append(
            {
                "stable_identity": group["stable_identity"],
                "filing_count": len(enriched_records),
                "symbols": symbols,
                "symbol_changed": len(symbols) > 1,
                "raw_reporting_period_count": len(raw_periods),
                "parseable_reporting_period_count": len(periods),
                "unparseable_period_record_count": unparseable_records,
                "invalid_period_record_count": invalid_period_records,
                "overlapping_period_pairs": group_overlap_pairs,
                "target_period_partition_count": len(target_partitions),
                "target_period_filing_count": sum(
                    int(partition["filing_count"])
                    for partition in target_partitions
                ),
                "nic_sets_by_period": nic_sets_by_period,
                "gates": gates,
                "deterministic_period_partition": deterministic,
                "partitions": partition_reports,
            }
        )

    conflict_group_count = len(conflict_groups)

    def fraction(numerator: int, denominator: int) -> float:
        return 0.0 if denominator == 0 else numerator / denominator

    report = {
        "year": year,
        "target_period": {
            "start": target_start,
            "end": target_end,
        },
        "cross_period_conflict_group_count": conflict_group_count,
        "cross_period_filing_record_count": total_records,
        "parseable_period_record_fraction": fraction(
            parseable_period_records,
            total_records,
        ),
        "explicit_nic_record_fraction": fraction(
            explicit_nic_records,
            total_records,
        ),
        "overlapping_period_pair_count": overlapping_period_pairs,
        "deterministic_period_partition_group_count": deterministic_groups,
        "deterministic_period_partition_group_fraction": fraction(
            deterministic_groups,
            conflict_group_count,
        ),
        "target_period_group_count": target_period_group_count,
        "target_period_record_count": target_period_record_count,
        "app_id_identity_conflict_count": r1[
            "app_id_identity_conflict_count"
        ],
        "conflict_groups": conflict_groups,
    }
    report["gates"] = {
        "at_least_one_cross_period_group": conflict_group_count > 0,
        "all_cross_period_groups_deterministic": (
            deterministic_groups == conflict_group_count
            and conflict_group_count > 0
        ),
        "all_period_records_parseable": (
            parseable_period_records == total_records
            and total_records > 0
        ),
        "all_conflict_filings_have_explicit_nic": (
            explicit_nic_records == total_records
            and total_records > 0
        ),
        "zero_overlapping_period_pairs": overlapping_period_pairs == 0,
        "zero_app_id_identity_conflicts": (
            r1["app_id_identity_conflict_count"] == 0
        ),
    }
    report["pass"] = all(report["gates"].values())
    return report


def parse_r2_archive(
    *,
    raw: bytes,
) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError("R2 annual archive is invalid") from exc

    with archive:
        general_name = _annual_member(archive, kind="general")
        product_name = _annual_member(archive, kind="product")
        general_raw = archive.read(general_name)
        product_raw = archive.read(product_name)

    general_headers, general_rows = _xlsx_table(general_raw)
    product_headers, product_rows = _xlsx_table(product_raw)
    if not _REQUIRED_GENERAL.issubset(set(general_headers)):
        raise AlphaContractError("R2 entity table header contract changed")
    if not _REQUIRED_PRODUCT.issubset(set(product_headers)):
        raise AlphaContractError("R2 product table header contract changed")

    report = analyze_cross_period_groups(
        year="FY2024-25",
        general_rows=general_rows,
        product_rows=product_rows,
        target_start=TARGET_START,
        target_end=TARGET_END,
    )
    report["general_workbook_path"] = general_name
    report["product_workbook_path"] = product_name
    return report


def build_r2_report(*, fy2024_25_raw: bytes) -> dict[str, Any]:
    year_report = parse_r2_archive(raw=fy2024_25_raw)
    passed = bool(year_report["pass"])
    failure_reasons = [
        gate
        for gate, value in year_report["gates"].items()
        if not value
    ]
    result: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": R2_ID,
        "evidence_class": "SOURCE_SEMANTICS_NO_RETURN_OUTCOMES",
        "parent_d010_status": "FAIL_SOURCE_FEASIBILITY",
        "parent_r1_status": "FAIL_DUPLICATE_SEMANTICS",
        "parent_d010_result_sha256": (
            "21aff20c7c3300ecf104d049fdbcad3749bb160735f478643a40bab36618a976"
        ),
        "parent_r1_result_sha256": (
            "eedc9bba0dfcb15a394af800cdc84f2e20ab48b95632d8941e5af169e1291522"
        ),
        "d010_status_changed": False,
        "r1_status_changed": False,
        "year_report": year_report,
        "status": (
            "PASS_PERIOD_PARTITION_SEMANTICS"
            if passed
            else "FAIL_PERIOD_PARTITION_SEMANTICS"
        ),
        "failure_reasons": failure_reasons,
        "d013_authorized": passed,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result
