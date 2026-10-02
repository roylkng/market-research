from __future__ import annotations

import math
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_d010_r1 import parse_r1_annual_archive

R2_ID = "RM001-D010-R2-v1"
EXCEL_EPOCH = date(1899, 12, 30)
EXPECTED_CONFLICT_GROUP_COUNT = 1
PERIOD_DAYS_MIN = 330
PERIOD_DAYS_MAX = 370


def parse_reporting_date(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    iso_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(iso_raw).date().isoformat()
    except ValueError:
        pass

    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = time.strptime(raw, fmt)
        except ValueError:
            continue
        return (
            f"{parsed.tm_year:04d}-{parsed.tm_mon:02d}-{parsed.tm_mday:02d}"
        )

    try:
        serial = float(raw)
    except ValueError:
        return None
    if not math.isfinite(serial) or serial <= 0 or serial > 1_000_000:
        return None
    whole_days = math.floor(serial)
    return (EXCEL_EPOCH + timedelta(days=whole_days)).isoformat()


def _period_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def analyze_cross_period_group(group: dict[str, Any]) -> dict[str, Any]:
    records = group.get("records")
    if not isinstance(records, list) or len(records) < 2:
        raise AlphaContractError("R2 candidate requires at least two filing records")

    normalized_records = []
    period_to_records: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    parseable_period_records = 0
    filing_after_period_end_records = 0

    for record in records:
        raw_start = str(record.get("financial_year_start") or "").strip()
        raw_end = str(record.get("financial_year_end") or "").strip()
        start = parse_reporting_date(raw_start)
        end = parse_reporting_date(raw_end)
        submission = str(record.get("submission_timestamp") or "").strip()
        submission_date = None
        if submission:
            try:
                submission_date = datetime.fromisoformat(submission).date()
            except ValueError:
                submission_date = None

        normalized = {
            **record,
            "financial_year_start_raw": raw_start,
            "financial_year_end_raw": raw_end,
            "financial_year_start_normalized": start,
            "financial_year_end_normalized": end,
        }
        normalized_records.append(normalized)

        if start is not None and end is not None:
            parseable_period_records += 1
            period_to_records[(start, end)].append(normalized)
            if submission_date is not None and submission_date >= date.fromisoformat(end):
                filing_after_period_end_records += 1

    periods = []
    for (start, end), period_records in sorted(period_to_records.items()):
        length_days = _period_days(start, end)
        app_ids = [str(row.get("app_id") or "") for row in period_records]
        timestamps = [
            str(row.get("submission_timestamp") or "")
            for row in period_records
            if row.get("submission_timestamp")
        ]
        period = {
            "financial_year_start": start,
            "financial_year_end": end,
            "period_length_days": length_days,
            "filing_count": len(period_records),
            "app_ids": app_ids,
            "submission_timestamps": timestamps,
            "symbols": sorted(
                {
                    str(row.get("symbol") or "")
                    for row in period_records
                    if row.get("symbol")
                }
            ),
            "nic_sets": sorted(
                {
                    tuple(row.get("nic_codes") or [])
                    for row in period_records
                }
            ),
            "all_app_ids_present": all(bool(value) for value in app_ids),
            "app_ids_unique": len(set(app_ids)) == len(app_ids),
            "all_timestamps_parseable": (
                len(timestamps) == len(period_records)
            ),
            "timestamps_unique": len(set(timestamps)) == len(period_records),
            "every_filing_has_explicit_nic": all(
                bool(row.get("nic_codes")) for row in period_records
            ),
            "all_filings_on_or_after_period_end": all(
                row.get("submission_timestamp")
                and datetime.fromisoformat(
                    str(row["submission_timestamp"])
                ).date()
                >= date.fromisoformat(end)
                for row in period_records
            ),
        }
        period["period_valid"] = (
            start < end
            and PERIOD_DAYS_MIN <= length_days <= PERIOD_DAYS_MAX
            and period["all_app_ids_present"]
            and period["app_ids_unique"]
            and period["all_timestamps_parseable"]
            and period["timestamps_unique"]
            and period["every_filing_has_explicit_nic"]
            and period["all_filings_on_or_after_period_end"]
        )
        periods.append(period)

    non_overlapping = True
    for previous, current in pairwise(periods):
        if date.fromisoformat(current["financial_year_start"]) <= date.fromisoformat(
            previous["financial_year_end"]
        ):
            non_overlapping = False
            break

    all_app_ids = [
        str(row.get("app_id") or "")
        for row in normalized_records
        if row.get("app_id")
    ]
    all_timestamps = [
        str(row.get("submission_timestamp") or "")
        for row in normalized_records
        if row.get("submission_timestamp")
    ]
    cross_period_app_ids_unique = len(set(all_app_ids)) == len(all_app_ids)
    cross_period_timestamps_unique = (
        len(all_timestamps) == len(normalized_records)
        and len(set(all_timestamps)) == len(normalized_records)
    )

    symbols = sorted(
        {
            str(row.get("symbol") or "")
            for row in normalized_records
            if row.get("symbol")
        }
    )
    period_nic_sets = [
        {
            tuple(row.get("nic_codes") or [])
            for row in period_records
        }
        for period_records in period_to_records.values()
    ]

    gates = {
        "all_period_dates_parseable": (
            parseable_period_records == len(normalized_records)
        ),
        "at_least_two_distinct_periods": len(periods) >= 2,
        "all_periods_valid": bool(periods)
        and all(period["period_valid"] for period in periods),
        "periods_non_overlapping": non_overlapping,
        "cross_period_app_ids_unique": cross_period_app_ids_unique,
        "cross_period_submission_timestamps_unique": (
            cross_period_timestamps_unique
        ),
        "all_filings_on_or_after_period_end": (
            filing_after_period_end_records == len(normalized_records)
        ),
    }

    return {
        "stable_identity": group.get("stable_identity"),
        "filing_count": len(normalized_records),
        "distinct_period_count": len(periods),
        "symbols": symbols,
        "symbol_changed": len(symbols) > 1,
        "nic_changed_between_periods": len(
            {
                tuple(sorted(value))
                for value in period_nic_sets
            }
        ) > 1,
        "periods": periods,
        "gates": gates,
        "candidate_pass": all(gates.values()),
    }


def build_r2_report(*, fy2024_25_raw: bytes) -> dict[str, Any]:
    r1_year = parse_r1_annual_archive(
        year="FY2024-25",
        raw=fy2024_25_raw,
    )
    candidates = [
        group
        for group in r1_year["duplicate_groups"]
        if not group["gates"]["reporting_period_consistent"]
    ]

    candidate_reports = [
        analyze_cross_period_group(group)
        for group in candidates
    ]
    candidate_count_matches = len(candidates) == EXPECTED_CONFLICT_GROUP_COUNT
    all_candidates_pass = (
        bool(candidate_reports)
        and all(report["candidate_pass"] for report in candidate_reports)
    )
    passed = candidate_count_matches and all_candidates_pass

    result: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": R2_ID,
        "evidence_class": "SOURCE_SEMANTICS_NO_RETURN_OUTCOMES",
        "parent_r1_status": "FAIL_DUPLICATE_SEMANTICS",
        "parent_r1_result_sha256": (
            "eedc9bba0dfcb15a394af800cdc84f2e20ab48b95632d8941e5af169e1291522"
        ),
        "d010_status_changed": False,
        "r1_status_changed": False,
        "d011_authorized": False,
        "reproduced_r1_fy2024_duplicate_group_count": r1_year[
            "duplicate_group_count"
        ],
        "reproduced_r1_reporting_period_conflict_group_count": r1_year[
            "reporting_period_conflict_group_count"
        ],
        "expected_candidate_count": EXPECTED_CONFLICT_GROUP_COUNT,
        "candidate_count": len(candidates),
        "candidate_count_matches_frozen_expectation": candidate_count_matches,
        "candidates": candidate_reports,
        "status": (
            "PASS_CROSS_PERIOD_SEMANTICS"
            if passed
            else "FAIL_CROSS_PERIOD_SEMANTICS"
        ),
        "d012_period_keyed_authorized": passed,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result
