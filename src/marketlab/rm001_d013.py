from __future__ import annotations

import hashlib
import io
import math
import statistics
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcements import announcement_rows, official_timestamp
from marketlab.rm001_d010 import (
    _annual_member,
    _normalize_identifier,
    _parse_float,
    _xlsx_table,
)
from marketlab.rm001_d010_r1 import parse_submission_timestamp
from marketlab.rm001_d010_r2 import parse_reporting_date
from marketlab.rm001_size_source import (
    SecurityMasterEqRow,
    parse_security_master_eq,
    security_master_url,
)

D013_ID = "RM001-D013-v1"
IST = ZoneInfo("Asia/Kolkata")
PUBLIC_SAMPLE_PER_YEAR = 40
MIN_MATCH_FRACTION_EACH_YEAR = 0.90
IST_MEDIAN_ABS_DELTA_MAX_SECONDS = 60.0
IST_P95_ABS_DELTA_MAX_SECONDS = 300.0
MATCH_DELTA_MIN_SECONDS = -60.0
MATCH_DELTA_MAX_SECONDS = 900.0
UTC_MEDIAN_ABS_DELTA_MIN_SECONDS = 14_400.0
AVAILABILITY_BUFFER = timedelta(minutes=15)
SECURITY_LOOKBACK_DAYS = 10
MIN_ISIN_JOIN_COVERAGE = 0.99
MIN_NIC_FILING_COVERAGE = 0.99
MAX_RAW_TURNOVER_PERCENT = 100.5
NIC_SUM_TOLERANCE = 1e-12
MAX_CARRY_DAYS_FROM_PERIOD_END = 550

FY_ARCHIVES = {
    "FY2023-24": {
        "url": (
            "https://nsearchives.nseindia.com/web/sites/default/files/"
            "inline-files/BRSR_Data_Dump.zip"
        ),
        "sha256": (
            "f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef"
        ),
    },
    "FY2024-25": {
        "url": (
            "https://nsearchives.nseindia.com/web/mediaattachment/2026-04/"
            "BRSR_DUMP_FY24-25_20260414130852.zip"
        ),
        "sha256": (
            "c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42"
        ),
    },
}

_GENERAL_REQUIRED = {
    "appid",
    "tlasubmitteddt",
    "symbsymbol",
    "corporateidentitynumbercinofthelistedentity",
    "currentfinancialyearstartdate",
    "currentfinancialyearenddate",
}
_PRODUCT_REQUIRED = {
    "appid",
    "symbsymbol",
    "productservicesoldbytheentity",
    "niccodesoldbytheentity",
    "percentageoftotalturnovercontributedsoldbytheentity",
}


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


def _parsed_submission_datetime(value: object) -> datetime | None:
    parsed_text = parse_submission_timestamp(value)
    if parsed_text is None:
        return None
    try:
        return datetime.fromisoformat(parsed_text)
    except ValueError as exc:
        raise AlphaContractError(
            f"D013 R1 submission timestamp became unparsable: {parsed_text}"
        ) from exc


def _filing_sample_score(filing: dict[str, Any]) -> str:
    payload = "|".join(
        (
            filing["year"],
            filing["stable_identity"],
            filing["reporting_period_start"],
            filing["reporting_period_end"],
            filing["app_id"],
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_turnover_percent(value: object) -> float | None:
    parsed = _parse_float(value)
    if parsed is None or not math.isfinite(parsed) or parsed < 0:
        return None
    return float(parsed)


def _nic_exposure(
    product_rows: list[dict[str, str | None]],
) -> dict[str, Any]:
    explicit = []
    for row in product_rows:
        nic = _normalize_identifier(row.get("niccodesoldbytheentity"))
        if not nic:
            continue
        explicit.append(
            {
                "nic": nic,
                "turnover_percent": _normalize_turnover_percent(
                    row.get(
                        "percentageoftotalturnovercontributedsoldbytheentity"
                    )
                ),
                "product_service": " ".join(
                    str(row.get("productservicesoldbytheentity") or "").split()
                ),
            }
        )

    distinct = sorted({row["nic"] for row in explicit})
    if not distinct:
        return {
            "status": "NO_EXPLICIT_NIC",
            "explicit_rows": explicit,
            "distinct_nic_count": 0,
            "weights": {},
        }
    if len(distinct) == 1:
        return {
            "status": "READY_SINGLE_NIC",
            "explicit_rows": explicit,
            "distinct_nic_count": 1,
            "weights": {distinct[0]: 1.0},
        }

    if any(row["turnover_percent"] is None for row in explicit):
        return {
            "status": "MULTI_NIC_INCOMPLETE_TURNOVER",
            "explicit_rows": explicit,
            "distinct_nic_count": len(distinct),
            "weights": {},
        }

    raw_by_nic: dict[str, float] = defaultdict(float)
    for row in explicit:
        raw_by_nic[row["nic"]] += float(row["turnover_percent"])
    total = sum(raw_by_nic.values())
    if total <= 0:
        return {
            "status": "MULTI_NIC_NONPOSITIVE_TURNOVER_TOTAL",
            "explicit_rows": explicit,
            "distinct_nic_count": len(distinct),
            "raw_turnover_total": total,
            "weights": {},
        }
    if total > MAX_RAW_TURNOVER_PERCENT + 1e-12:
        return {
            "status": "MULTI_NIC_TURNOVER_TOTAL_EXCEEDS_MAX",
            "explicit_rows": explicit,
            "distinct_nic_count": len(distinct),
            "raw_turnover_total": total,
            "weights": {},
        }

    weights = {
        nic: raw_by_nic[nic] / total
        for nic in sorted(raw_by_nic)
    }
    if abs(sum(weights.values()) - 1.0) > NIC_SUM_TOLERANCE:
        raise AlphaContractError("D013 normalized NIC weights do not sum to one")
    return {
        "status": "READY_MULTI_NIC",
        "explicit_rows": explicit,
        "distinct_nic_count": len(distinct),
        "raw_turnover_total": total,
        "weights": weights,
    }


def parse_brsr_archive(
    *,
    year: str,
    raw: bytes,
) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise AlphaContractError(f"D013 {year} archive is invalid") from exc

    with archive:
        general_name = _annual_member(archive, kind="general")
        product_name = _annual_member(archive, kind="product")
        general_raw = archive.read(general_name)
        product_raw = archive.read(product_name)

    general_headers, general_rows = _xlsx_table(general_raw)
    product_headers, product_rows = _xlsx_table(product_raw)
    if not _GENERAL_REQUIRED.issubset(set(general_headers)):
        raise AlphaContractError(f"D013 {year} entity header contract changed")
    if not _PRODUCT_REQUIRED.issubset(set(product_headers)):
        raise AlphaContractError(f"D013 {year} product header contract changed")

    product_by_app: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    for row in product_rows:
        app_id = _normalize_identifier(row.get("appid"))
        if app_id:
            product_by_app[app_id].append(row)

    filings = []
    for row in general_rows:
        identity = _stable_identity(row)
        app_id = _normalize_identifier(row.get("appid"))
        symbol = str(row.get("symbsymbol") or "").strip().upper()
        submission = _parsed_submission_datetime(row.get("tlasubmitteddt"))
        period_start = parse_reporting_date(
            row.get("currentfinancialyearstartdate")
        )
        period_end = parse_reporting_date(
            row.get("currentfinancialyearenddate")
        )
        nic = _nic_exposure(product_by_app.get(app_id, []))
        filings.append(
            {
                "year": year,
                "stable_identity": identity,
                "app_id": app_id,
                "symbol": symbol,
                "cin": str(
                    row.get(
                        "corporateidentitynumbercinofthelistedentity"
                    )
                    or ""
                ).strip().upper(),
                "submission_timestamp_raw": str(
                    row.get("tlasubmitteddt") or ""
                ).strip(),
                "submission_timestamp_parsed": (
                    None if submission is None else submission.isoformat()
                ),
                "submission_timestamp_has_timezone": (
                    False if submission is None else submission.tzinfo is not None
                ),
                "reporting_period_start": period_start,
                "reporting_period_end": period_end,
                "nic": nic,
            }
        )

    return {
        "year": year,
        "general_workbook_path": general_name,
        "product_workbook_path": product_name,
        "general_record_count": len(general_rows),
        "product_record_count": len(product_rows),
        "filings": filings,
    }


def deterministic_public_time_sample(
    filings: list[dict[str, Any]],
    *,
    per_year: int = PUBLIC_SAMPLE_PER_YEAR,
) -> list[dict[str, Any]]:
    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for filing in filings:
        if not (
            filing["stable_identity"]
            and filing["app_id"]
            and filing["symbol"]
            and filing["submission_timestamp_parsed"]
            and filing["reporting_period_start"]
            and filing["reporting_period_end"]
            and filing["nic"]["distinct_nic_count"] > 0
        ):
            continue
        scored = {
            **filing,
            "sample_score": _filing_sample_score(filing),
        }
        by_year[filing["year"]].append(scored)

    selected = []
    for year in sorted(FY_ARCHIVES):
        candidates = sorted(
            by_year.get(year, []),
            key=lambda row: (
                row["sample_score"],
                row["stable_identity"],
                row["app_id"],
            ),
        )
        selected.extend(candidates[:per_year])
    return selected


def _announcement_is_brsr(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("desc", "attchmntText")
    ).casefold()
    return (
        "brsr" in text
        or (
            "business responsibility" in text
            and "sustainability" in text
        )
    )


def _submission_candidates(
    filing: dict[str, Any],
) -> tuple[datetime, datetime]:
    parsed = datetime.fromisoformat(filing["submission_timestamp_parsed"])
    if parsed.tzinfo is not None:
        aware = parsed.astimezone(UTC)
        return aware, aware
    ist = parsed.replace(tzinfo=IST).astimezone(UTC)
    utc = parsed.replace(tzinfo=UTC)
    return ist, utc


def match_public_announcement(
    *,
    filing: dict[str, Any],
    payload: Any,
) -> dict[str, Any]:
    tla_ist, tla_utc = _submission_candidates(filing)
    candidates = []
    for raw in announcement_rows(payload):
        symbol = str(raw.get("symbol") or "").strip().upper()
        seq_id = str(raw.get("seq_id") or "").strip()
        if symbol != filing["symbol"] or not seq_id:
            continue
        if not _announcement_is_brsr(raw):
            continue
        published = official_timestamp(raw)
        ist_distance = abs((published - tla_ist).total_seconds())
        candidates.append(
            {
                "seq_id": seq_id,
                "exchange_published_at_utc": published.isoformat(),
                "description": " ".join(
                    str(raw.get("desc") or "").split()
                ),
                "attachment_text": " ".join(
                    str(raw.get("attchmntText") or "").split()
                ),
                "ist_abs_delta_seconds": ist_distance,
                "ist_signed_delta_seconds": (
                    published - tla_ist
                ).total_seconds(),
                "utc_abs_delta_seconds": abs(
                    (published - tla_utc).total_seconds()
                ),
            }
        )

    if not candidates:
        return {
            "status": "NO_BRSR_ANNOUNCEMENT_MATCH",
            "candidate_count": 0,
        }

    candidates.sort(
        key=lambda row: (
            row["ist_abs_delta_seconds"],
            row["exchange_published_at_utc"],
            row["seq_id"],
        )
    )
    if (
        len(candidates) > 1
        and abs(
            candidates[0]["ist_abs_delta_seconds"]
            - candidates[1]["ist_abs_delta_seconds"]
        )
        <= 1e-9
    ):
        return {
            "status": "AMBIGUOUS_EQUAL_DISTANCE_MATCH",
            "candidate_count": len(candidates),
            "candidates": candidates[:10],
        }

    return {
        "status": "MATCHED",
        "candidate_count": len(candidates),
        "match": candidates[0],
    }


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise AlphaContractError("D013 percentile requires observations")
    if not 0.0 <= percentile <= 1.0:
        raise AlphaContractError("D013 percentile must be in [0,1]")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return float(ordered[rank - 1])


def evaluate_public_time_semantics(
    *,
    sample: list[dict[str, Any]],
    matches: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_year_total: dict[str, int] = defaultdict(int)
    by_year_matched: dict[str, int] = defaultdict(int)
    ist_abs = []
    utc_abs = []
    signed = []
    reused_seq: dict[str, list[str]] = defaultdict(list)
    rows = []

    for filing in sample:
        key = filing["sample_score"]
        by_year_total[filing["year"]] += 1
        result = matches.get(key, {"status": "NO_QUERY_RESULT"})
        row = {
            "year": filing["year"],
            "stable_identity": filing["stable_identity"],
            "app_id": filing["app_id"],
            "symbol": filing["symbol"],
            "reporting_period_start": filing["reporting_period_start"],
            "reporting_period_end": filing["reporting_period_end"],
            "submission_timestamp_raw": filing["submission_timestamp_raw"],
            "sample_score": key,
            **result,
        }
        if result.get("status") == "MATCHED":
            by_year_matched[filing["year"]] += 1
            match = result["match"]
            ist_abs.append(float(match["ist_abs_delta_seconds"]))
            utc_abs.append(float(match["utc_abs_delta_seconds"]))
            signed.append(float(match["ist_signed_delta_seconds"]))
            reused_seq[str(match["seq_id"])].append(key)
        rows.append(row)

    match_fraction = {
        year: (
            0.0
            if by_year_total[year] == 0
            else by_year_matched[year] / by_year_total[year]
        )
        for year in sorted(FY_ARCHIVES)
    }
    reused = {
        seq_id: keys
        for seq_id, keys in reused_seq.items()
        if len(keys) > 1
    }

    median_ist = (
        statistics.median(ist_abs) if ist_abs else None
    )
    p95_ist = (
        _nearest_rank_percentile(ist_abs, 0.95)
        if ist_abs
        else None
    )
    median_utc = (
        statistics.median(utc_abs) if utc_abs else None
    )
    gates = {
        "minimum_match_fraction_each_year": all(
            match_fraction.get(year, 0.0)
            >= MIN_MATCH_FRACTION_EACH_YEAR
            for year in FY_ARCHIVES
        ),
        "ist_median_abs_delta_within_60s": (
            median_ist is not None
            and median_ist <= IST_MEDIAN_ABS_DELTA_MAX_SECONDS
        ),
        "ist_p95_abs_delta_within_300s": (
            p95_ist is not None
            and p95_ist <= IST_P95_ABS_DELTA_MAX_SECONDS
        ),
        "all_signed_deltas_within_buffer_contract": (
            bool(signed)
            and min(signed) >= MATCH_DELTA_MIN_SECONDS
            and max(signed) <= MATCH_DELTA_MAX_SECONDS
        ),
        "utc_median_abs_delta_at_least_4h": (
            median_utc is not None
            and median_utc >= UTC_MEDIAN_ABS_DELTA_MIN_SECONDS
        ),
        "zero_reused_announcement_sequence_ids": not reused,
    }
    return {
        "sample_count": len(sample),
        "matched_count": len(ist_abs),
        "match_fraction_by_year": match_fraction,
        "ist_median_abs_delta_seconds": median_ist,
        "ist_p95_abs_delta_seconds": p95_ist,
        "ist_min_signed_delta_seconds": min(signed) if signed else None,
        "ist_max_signed_delta_seconds": max(signed) if signed else None,
        "utc_median_abs_delta_seconds": median_utc,
        "reused_announcement_sequence_ids": reused,
        "gates": gates,
        "pass": all(gates.values()),
        "rows": rows,
        "percentile_method": "NEAREST_RANK",
    }


def attach_historical_availability(
    filings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for filing in filings:
        parsed_text = filing.get("submission_timestamp_parsed")
        if not parsed_text:
            result.append(
                {
                    **filing,
                    "available_at_utc": None,
                    "availability_status": "UNPARSEABLE_SUBMISSION_TIME",
                }
            )
            continue
        parsed = datetime.fromisoformat(str(parsed_text))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
        available = parsed.astimezone(UTC) + AVAILABILITY_BUFFER
        period_start = filing.get("reporting_period_start")
        period_end = filing.get("reporting_period_end")
        result.append(
            {
                **filing,
                "available_at_utc": available.isoformat(),
                "availability_status": (
                    "READY"
                    if period_start and period_end
                    else "UNPARSEABLE_REPORTING_PERIOD"
                ),
            }
        )
    return result


def build_prior_security_sources(
    *,
    filings: list[dict[str, Any]],
    fetcher,
) -> dict[str, Any]:
    target_dates = sorted(
        {
            datetime.fromisoformat(filing["available_at_utc"])
            .astimezone(IST)
            .date()
            .isoformat()
            for filing in filings
            if filing.get("available_at_utc")
        }
    )
    resolved: dict[str, dict[str, Any]] = {}
    source_cache: dict[str, dict[str, Any]] = {}

    for target_text in target_dates:
        target = date.fromisoformat(target_text)
        chosen = None
        for offset in range(1, SECURITY_LOOKBACK_DAYS + 1):
            candidate = target - timedelta(days=offset)
            candidate_text = candidate.isoformat()
            cached = source_cache.get(candidate_text)
            if cached is None:
                url = security_master_url(candidate)
                raw = fetcher(url)
                if raw is None:
                    cached = {
                        "status": "UNAVAILABLE",
                        "session_date": candidate_text,
                        "source_url": url,
                    }
                else:
                    raw_sha = hashlib.sha256(raw).hexdigest()
                    try:
                        rows, diagnostics = parse_security_master_eq(
                            raw,
                            session_date=candidate,
                        )
                    except AlphaContractError as exc:
                        cached = {
                            "status": "PARSER_REJECTED",
                            "session_date": candidate_text,
                            "source_url": url,
                            "raw_sha256": raw_sha,
                            "error": str(exc),
                        }
                    else:
                        by_symbol: dict[str, list[SecurityMasterEqRow]] = defaultdict(list)
                        for row in rows:
                            by_symbol[row.symbol].append(row)
                        cached = {
                            "status": "READY",
                            "session_date": candidate_text,
                            "source_url": url,
                            "raw_sha256": raw_sha,
                            "diagnostics": diagnostics,
                            "rows_by_symbol": {
                                symbol: [
                                    {
                                        "symbol": row.symbol,
                                        "isin": row.isin,
                                        "security_name": row.security_name,
                                    }
                                    for row in values
                                ]
                                for symbol, values in sorted(by_symbol.items())
                            },
                        }
                source_cache[candidate_text] = cached
            if cached["status"] == "READY":
                chosen = cached
                break
        resolved[target_text] = (
            chosen
            if chosen is not None
            else {
                "status": "NO_PRIOR_SECURITY_MASTER_WITHIN_LOOKBACK",
                "target_date": target_text,
            }
        )

    return {
        "target_dates": resolved,
        "source_cache": source_cache,
    }


def attach_isin(
    filings: list[dict[str, Any]],
    security_sources: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ready = 0
    ambiguous = 0
    no_symbol = 0
    unresolved = 0
    result = []

    target_dates = security_sources["target_dates"]
    for filing in filings:
        available_text = filing.get("available_at_utc")
        symbol = str(filing.get("symbol") or "")
        if not available_text:
            result.append(
                {
                    **filing,
                    "isin": None,
                    "isin_status": "NO_AVAILABLE_AT",
                }
            )
            unresolved += 1
            continue
        if not symbol:
            result.append(
                {
                    **filing,
                    "isin": None,
                    "isin_status": "NO_SYMBOL",
                }
            )
            no_symbol += 1
            continue
        target_date = (
            datetime.fromisoformat(available_text).astimezone(IST).date().isoformat()
        )
        source = target_dates.get(target_date)
        if source is None or source.get("status") != "READY":
            result.append(
                {
                    **filing,
                    "isin": None,
                    "isin_status": "NO_PRIOR_SECURITY_MASTER",
                }
            )
            unresolved += 1
            continue
        candidates = source["rows_by_symbol"].get(symbol, [])
        if len(candidates) == 1:
            result.append(
                {
                    **filing,
                    "isin": candidates[0]["isin"],
                    "isin_status": "READY",
                    "isin_security_master_session": source["session_date"],
                    "isin_security_master_sha256": source["raw_sha256"],
                }
            )
            ready += 1
        elif len(candidates) > 1:
            result.append(
                {
                    **filing,
                    "isin": None,
                    "isin_status": "AMBIGUOUS_SYMBOL_MULTIPLE_ISIN",
                    "isin_candidates": candidates,
                }
            )
            ambiguous += 1
        else:
            result.append(
                {
                    **filing,
                    "isin": None,
                    "isin_status": "SYMBOL_NOT_IN_PRIOR_SECURITY_MASTER",
                    "isin_security_master_session": source["session_date"],
                    "isin_security_master_sha256": source["raw_sha256"],
                }
            )
            unresolved += 1

    total = len(filings)
    return result, {
        "filing_count": total,
        "ready_count": ready,
        "exact_join_coverage": 0.0 if total == 0 else ready / total,
        "ambiguous_join_count": ambiguous,
        "missing_symbol_count": no_symbol,
        "unresolved_count": unresolved,
    }


def _expiry_at_utc(filing: dict[str, Any]) -> datetime:
    period_end = date.fromisoformat(filing["reporting_period_end"])
    expiry_day = period_end + timedelta(days=MAX_CARRY_DAYS_FROM_PERIOD_END + 1)
    return datetime.combine(expiry_day, time.min, tzinfo=IST).astimezone(UTC)


def select_filing_asof(
    filings: list[dict[str, Any]],
    *,
    as_of_utc: datetime,
) -> dict[str, Any] | None:
    if as_of_utc.tzinfo is None:
        raise AlphaContractError("D013 as-of time must be timezone-aware")
    as_of = as_of_utc.astimezone(UTC)
    eligible = []
    for filing in filings:
        if filing.get("availability_status") != "READY":
            continue
        if filing.get("isin_status") != "READY":
            continue
        if not filing["nic"]["weights"]:
            continue
        available = datetime.fromisoformat(filing["available_at_utc"]).astimezone(UTC)
        if available > as_of:
            continue
        if as_of >= _expiry_at_utc(filing):
            continue
        eligible.append(filing)
    if not eligible:
        return None

    latest_period_end = max(filing["reporting_period_end"] for filing in eligible)
    period_rows = [
        filing
        for filing in eligible
        if filing["reporting_period_end"] == latest_period_end
    ]
    period_rows.sort(
        key=lambda row: (
            row["available_at_utc"],
            row["app_id"],
        )
    )
    if (
        len(period_rows) >= 2
        and period_rows[-1]["available_at_utc"]
        == period_rows[-2]["available_at_utc"]
        and period_rows[-1]["app_id"] == period_rows[-2]["app_id"]
    ):
        raise AlphaContractError("D013 as-of selector has an exact filing tie")
    return period_rows[-1]


def audit_timeline(
    filings: list[dict[str, Any]],
) -> dict[str, Any]:
    by_identity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for filing in filings:
        if filing["stable_identity"]:
            by_identity[filing["stable_identity"]].append(filing)

    checks = 0
    future_selection = 0
    expired_selection = 0
    identity_mismatch = 0
    invalid_nic_vector = 0
    selection_ties = 0

    for identity, rows in sorted(by_identity.items()):
        event_times = set()
        for row in rows:
            if row.get("available_at_utc"):
                event_times.add(
                    datetime.fromisoformat(row["available_at_utc"]).astimezone(UTC)
                    + timedelta(seconds=1)
                )
            if (
                row.get("reporting_period_end")
                and row.get("availability_status") == "READY"
            ):
                event_times.add(_expiry_at_utc(row) + timedelta(seconds=1))

        for event_time in sorted(event_times):
            checks += 1
            try:
                selected = select_filing_asof(rows, as_of_utc=event_time)
            except AlphaContractError:
                selection_ties += 1
                continue
            if selected is None:
                continue
            available = datetime.fromisoformat(
                selected["available_at_utc"]
            ).astimezone(UTC)
            if available > event_time:
                future_selection += 1
            if event_time >= _expiry_at_utc(selected):
                expired_selection += 1
            if selected["stable_identity"] != identity:
                identity_mismatch += 1
            weights = selected["nic"]["weights"]
            if (
                not weights
                or abs(sum(float(v) for v in weights.values()) - 1.0)
                > NIC_SUM_TOLERANCE
            ):
                invalid_nic_vector += 1

    gates = {
        "zero_selection_ties": selection_ties == 0,
        "zero_future_filing_selection": future_selection == 0,
        "zero_expired_filing_selection": expired_selection == 0,
        "zero_identity_mismatch": identity_mismatch == 0,
        "zero_invalid_nic_vectors": invalid_nic_vector == 0,
    }
    return {
        "identity_count": len(by_identity),
        "audit_event_count": checks,
        "selection_tie_count": selection_ties,
        "future_selection_count": future_selection,
        "expired_selection_count": expired_selection,
        "identity_mismatch_count": identity_mismatch,
        "invalid_nic_vector_count": invalid_nic_vector,
        "gates": gates,
        "pass": all(gates.values()),
    }


def build_d013_report(
    *,
    archives: dict[str, bytes],
    announcement_payloads: dict[str, Any],
    announcement_raw_sha256: dict[str, str],
    security_fetcher,
) -> dict[str, Any]:
    year_reports = {}
    filings = []
    for year in sorted(FY_ARCHIVES):
        raw = archives.get(year)
        if raw is None:
            raise AlphaContractError(f"D013 missing frozen archive {year}")
        observed = hashlib.sha256(raw).hexdigest()
        if observed != FY_ARCHIVES[year]["sha256"]:
            raise AlphaContractError(
                f"D013 {year} archive SHA mismatch: {observed}"
            )
        parsed = parse_brsr_archive(year=year, raw=raw)
        year_reports[year] = {
            key: value
            for key, value in parsed.items()
            if key != "filings"
        }
        filings.extend(parsed["filings"])

    sample = deterministic_public_time_sample(filings)
    matches = {
        filing["sample_score"]: match_public_announcement(
            filing=filing,
            payload=announcement_payloads.get(filing["sample_score"], []),
        )
        for filing in sample
    }
    timing = evaluate_public_time_semantics(
        sample=sample,
        matches=matches,
    )

    total_filings = len(filings)
    explicit_nic_filings = sum(
        filing["nic"]["distinct_nic_count"] > 0
        for filing in filings
    )
    multi_nic_filings = [
        filing
        for filing in filings
        if filing["nic"]["distinct_nic_count"] > 1
    ]
    transformable_multi = sum(
        filing["nic"]["status"] == "READY_MULTI_NIC"
        for filing in multi_nic_filings
    )
    period_parseable = sum(
        bool(
            filing["reporting_period_start"]
            and filing["reporting_period_end"]
        )
        for filing in filings
    )
    nic_metrics = {
        "filing_count": total_filings,
        "explicit_nic_filing_count": explicit_nic_filings,
        "explicit_nic_filing_coverage": (
            0.0 if total_filings == 0 else explicit_nic_filings / total_filings
        ),
        "multi_nic_filing_count": len(multi_nic_filings),
        "transformable_multi_nic_filing_count": transformable_multi,
        "multi_nic_transformable_fraction": (
            1.0
            if not multi_nic_filings
            else transformable_multi / len(multi_nic_filings)
        ),
        "reporting_period_parseable_count": period_parseable,
        "reporting_period_parseable_fraction": (
            0.0 if total_filings == 0 else period_parseable / total_filings
        ),
    }

    if timing["pass"]:
        available_filings = attach_historical_availability(filings)
        security_sources = build_prior_security_sources(
            filings=available_filings,
            fetcher=security_fetcher,
        )
        joined_filings, identity_metrics = attach_isin(
            available_filings,
            security_sources,
        )
        timeline = audit_timeline(joined_filings)
    else:
        joined_filings = []
        security_sources = {
            "target_dates": {},
            "source_cache": {},
            "status": "SKIPPED_PUBLIC_TIME_NOT_PROVEN",
        }
        identity_metrics = {
            "status": "SKIPPED_PUBLIC_TIME_NOT_PROVEN",
            "filing_count": total_filings,
            "ready_count": 0,
            "exact_join_coverage": 0.0,
            "ambiguous_join_count": 0,
            "missing_symbol_count": 0,
            "unresolved_count": total_filings,
        }
        timeline = {
            "status": "SKIPPED_PUBLIC_TIME_NOT_PROVEN",
            "pass": False,
            "gates": {},
        }

    gates = {
        "public_time_semantics": timing["pass"],
        "minimum_exact_symbol_isin_coverage": (
            timing["pass"]
            and identity_metrics["exact_join_coverage"]
            >= MIN_ISIN_JOIN_COVERAGE
        ),
        "zero_ambiguous_symbol_isin_joins": (
            timing["pass"]
            and identity_metrics["ambiguous_join_count"] == 0
        ),
        "minimum_explicit_nic_filing_coverage": (
            nic_metrics["explicit_nic_filing_coverage"]
            >= MIN_NIC_FILING_COVERAGE
        ),
        "all_multi_nic_filings_transformable": (
            nic_metrics["multi_nic_transformable_fraction"] == 1.0
        ),
        "all_reporting_periods_parseable": (
            nic_metrics["reporting_period_parseable_fraction"] == 1.0
        ),
        "timeline_deterministic": bool(timeline.get("pass")),
    }
    passed = all(gates.values())

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D013_ID,
        "evidence_class": "SOURCE_TIMELINE_NO_RETURN_OUTCOMES",
        "parent_d010_status": "FAIL_SOURCE_FEASIBILITY",
        "parent_r1_status": "FAIL_DUPLICATE_SEMANTICS",
        "parent_r2_status": "PASS_PERIOD_PARTITION_SEMANTICS",
        "parent_r2_result_sha256": (
            "18741e771f314c91e895c4c017e2f079553292b9c30991ffe0a432cf4e5f87d5"
        ),
        "year_reports": year_reports,
        "filing_count": total_filings,
        "public_time": timing,
        "announcement_raw_sha256": dict(
            sorted(announcement_raw_sha256.items())
        ),
        "nic": nic_metrics,
        "identity": identity_metrics,
        "timeline": timeline,
        "security_source_summary": {
            "target_date_count": len(security_sources["target_dates"]),
            "queried_calendar_date_count": len(
                security_sources["source_cache"]
            ),
            "ready_source_count": sum(
                row.get("status") == "READY"
                for row in security_sources["source_cache"].values()
            ),
            "source_hashes": {
                day: row.get("raw_sha256")
                for day, row in sorted(
                    security_sources["source_cache"].items()
                )
                if row.get("raw_sha256")
            },
        },
        "gates": gates,
        "status": (
            "PASS_PERIOD_PARTITIONED_ASOF_TIMELINE"
            if passed
            else "FAIL_PERIOD_PARTITIONED_ASOF_TIMELINE"
        ),
        "d014_authorized": passed,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["result_sha256"] = digest(report)
    return report
