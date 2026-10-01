from __future__ import annotations

import csv
import gzip
import io
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore

SECURITY_MASTER_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/cm/"
    "NSE_CM_security_{ddmmyyyy}.csv.gz"
)

D007_MIN_DAILY_JOIN_COVERAGE = 0.99
D007_MIN_DAILY_ISSUED_SIZE_COVERAGE = 0.99
D007_MIN_FREE_FLOAT_PROMOTION_COVERAGE = 0.95

_REQUIRED_FIELDS = {
    "TckrSymb",
    "SctySrs",
    "FinInstrmNm",
    "ISIN",
    "IssdCptl",
    "ParVal",
    "DelFlg",
}

_CLASSIFICATION_FIELDS = (
    "AsstClss",
    "ClssfctnTp",
    "FinInstrmClssfctn",
    "Indx",
)


@dataclass(frozen=True)
class SecurityMasterEqRow:
    session_date: str
    symbol: str
    isin: str
    security_name: str
    issued_size: float | None
    par_value_raw: float | None
    free_float_capital_raw: float | None
    deletion_flag: str
    asset_class_raw: str
    classification_type_raw: str
    financial_instrument_classification_raw: str
    index_raw: str


class SecurityMasterAcquisitionError(RuntimeError):
    """Raised when a frozen D007 security-master source cannot be audited."""


def security_master_url(session_date: date) -> str:
    return SECURITY_MASTER_URL_TEMPLATE.format(
        ddmmyyyy=session_date.strftime("%d%m%Y")
    )


def _optional_finite_positive(value: object) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def parse_security_master_eq(
    raw_gzip: bytes,
    *,
    session_date: date,
) -> tuple[list[SecurityMasterEqRow], dict[str, Any]]:
    try:
        decoded = gzip.decompress(raw_gzip).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise AlphaContractError("D007 security master must be valid UTF-8 gzip") from exc

    reader = csv.DictReader(io.StringIO(decoded))
    if reader.fieldnames is None:
        raise AlphaContractError("D007 security master has no header")
    fields = [str(field).strip() for field in reader.fieldnames]
    if not _REQUIRED_FIELDS.issubset(fields):
        raise AlphaContractError(
            f"D007 security-master header changed: {sorted(fields)}"
        )

    rows: list[SecurityMasterEqRow] = []
    seen: set[tuple[str, str]] = set()
    raw_row_count = 0
    dummy_row_count = 0
    eq_row_count = 0
    duplicate_identity_count = 0

    classification_nonempty = {field: 0 for field in _CLASSIFICATION_FIELDS}

    for raw in reader:
        raw_row_count += 1
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw.items()
            if key is not None
        }
        if row.get("SctySrs", "").upper() != "EQ":
            continue
        eq_row_count += 1
        symbol = row.get("TckrSymb", "").upper()
        isin = row.get("ISIN", "")
        if not symbol or not isin:
            raise AlphaContractError(
                f"{session_date}: D007 EQ row missing symbol/ISIN"
            )
        if isin.upper().startswith("DUMMY"):
            dummy_row_count += 1
            continue

        identity = (symbol, isin)
        if identity in seen:
            duplicate_identity_count += 1
            continue
        seen.add(identity)

        for field in _CLASSIFICATION_FIELDS:
            if row.get(field, ""):
                classification_nonempty[field] += 1

        rows.append(
            SecurityMasterEqRow(
                session_date=session_date.isoformat(),
                symbol=symbol,
                isin=isin,
                security_name=row.get("FinInstrmNm", ""),
                issued_size=_optional_finite_positive(row.get("IssdCptl")),
                par_value_raw=_optional_finite_positive(row.get("ParVal")),
                free_float_capital_raw=_optional_finite_positive(
                    row.get("FreeFltCptl")
                ),
                deletion_flag=row.get("DelFlg", ""),
                asset_class_raw=row.get("AsstClss", ""),
                classification_type_raw=row.get("ClssfctnTp", ""),
                financial_instrument_classification_raw=row.get(
                    "FinInstrmClssfctn", ""
                ),
                index_raw=row.get("Indx", ""),
            )
        )

    diagnostics = {
        "raw_row_count": raw_row_count,
        "eq_row_count_including_dummy": eq_row_count,
        "dummy_eq_row_count": dummy_row_count,
        "real_eq_unique_identity_count": len(rows),
        "duplicate_real_eq_identity_count": duplicate_identity_count,
        "classification_nonempty_counts": classification_nonempty,
    }
    return sorted(rows, key=lambda row: (row.symbol, row.isin)), diagnostics


def _market_identity_map(
    session: dict[str, Any],
) -> dict[tuple[str, str], DailyEquityObservation]:
    identities: dict[tuple[str, str], DailyEquityObservation] = {}
    for raw in session.get("equities", []):
        row = (
            raw
            if isinstance(raw, DailyEquityObservation)
            else DailyEquityObservation(**raw)
        )
        if row.isin.upper().startswith("DUMMY"):
            continue
        key = (row.symbol, row.isin)
        if key in identities:
            raise AlphaContractError(
                f"{session['session_date']}: duplicate market identity {key}"
            )
        identities[key] = row
    return identities


def audit_security_master_session(
    *,
    market_session: dict[str, Any],
    security_rows: list[SecurityMasterEqRow],
    parser_diagnostics: dict[str, Any],
    source_url: str,
    raw_sha256: str,
) -> dict[str, Any]:
    market = _market_identity_map(market_session)
    security = {
        (row.symbol, row.isin): row
        for row in security_rows
    }
    if len(security) != len(security_rows):
        raise AlphaContractError("D007 duplicate security identity escaped parser")

    common = sorted(set(market) & set(security))
    market_count = len(market)
    joined_count = len(common)
    join_coverage = (
        1.0 if market_count == 0 else joined_count / market_count
    )

    issued_ready = 0
    free_float_ready = 0
    market_cap_ready = 0
    market_caps = []
    for identity in common:
        security_row = security[identity]
        if security_row.issued_size is not None:
            issued_ready += 1
            cap = market[identity].close_price * security_row.issued_size
            if math.isfinite(cap) and cap > 0:
                market_cap_ready += 1
                market_caps.append(cap)
        if security_row.free_float_capital_raw is not None:
            free_float_ready += 1

    issued_coverage = (
        1.0 if joined_count == 0 else issued_ready / joined_count
    )
    market_cap_coverage = (
        1.0 if joined_count == 0 else market_cap_ready / joined_count
    )
    free_float_coverage = (
        1.0 if joined_count == 0 else free_float_ready / joined_count
    )

    result = {
        "session_date": str(market_session["session_date"]),
        "source_url": source_url,
        "raw_sha256": raw_sha256,
        **parser_diagnostics,
        "market_eq_identity_count": market_count,
        "exact_joined_identity_count": joined_count,
        "exact_join_coverage": join_coverage,
        "positive_issued_size_count": issued_ready,
        "positive_issued_size_coverage": issued_coverage,
        "positive_market_cap_count": market_cap_ready,
        "positive_market_cap_coverage": market_cap_coverage,
        "positive_free_float_capital_count": free_float_ready,
        "positive_free_float_capital_coverage": free_float_coverage,
        "market_cap_min_inr": min(market_caps) if market_caps else None,
        "market_cap_median_inr": (
            sorted(market_caps)[len(market_caps) // 2]
            if market_caps
            else None
        ),
        "market_cap_max_inr": max(market_caps) if market_caps else None,
        "total_size_session_pass": (
            parser_diagnostics["duplicate_real_eq_identity_count"] == 0
            and join_coverage >= D007_MIN_DAILY_JOIN_COVERAGE
            and issued_coverage >= D007_MIN_DAILY_ISSUED_SIZE_COVERAGE
            and market_cap_coverage >= D007_MIN_DAILY_ISSUED_SIZE_COVERAGE
        ),
    }
    return result


def run_d007_security_master_audit(
    *,
    market_panel: dict[str, Any],
    fetcher: Callable[[str], bytes | None],
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
) -> dict[str, Any]:
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("D007 market panel sessions are required")

    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise AlphaContractError("D007 capture timestamp must be timezone-aware")
    store = MarketArtifactStore(store_root) if store_root is not None else None

    session_results = []
    unavailable_sessions = []
    parser_rejected_sessions = []

    for market_session in sessions:
        day = date.fromisoformat(str(market_session["session_date"]))
        url = security_master_url(day)
        raw = fetcher(url)
        if raw is None:
            unavailable_sessions.append(day.isoformat())
            continue
        raw_sha = sha256_bytes(raw)
        if store is not None:
            store.retain(
                raw,
                source_url=url,
                captured_at=captured,
                suffix=".csv.gz",
            )
        try:
            rows, diagnostics = parse_security_master_eq(
                raw,
                session_date=day,
            )
        except AlphaContractError as exc:
            parser_rejected_sessions.append(
                {
                    "session_date": day.isoformat(),
                    "error": str(exc),
                    "raw_sha256": raw_sha,
                }
            )
            continue
        session_results.append(
            audit_security_master_session(
                market_session=market_session,
                security_rows=rows,
                parser_diagnostics=diagnostics,
                source_url=url,
                raw_sha256=raw_sha,
            )
        )

    expected_count = len(sessions)
    ready_count = len(session_results)
    min_join = min(
        (row["exact_join_coverage"] for row in session_results),
        default=0.0,
    )
    min_issued = min(
        (row["positive_issued_size_coverage"] for row in session_results),
        default=0.0,
    )
    min_market_cap = min(
        (row["positive_market_cap_coverage"] for row in session_results),
        default=0.0,
    )
    min_free_float = min(
        (row["positive_free_float_capital_coverage"] for row in session_results),
        default=0.0,
    )
    max_duplicate = max(
        (row["duplicate_real_eq_identity_count"] for row in session_results),
        default=0,
    )
    all_size_sessions_pass = (
        ready_count == expected_count
        and not unavailable_sessions
        and not parser_rejected_sessions
        and all(row["total_size_session_pass"] for row in session_results)
    )
    free_float_promoted = (
        ready_count == expected_count
        and min_free_float >= D007_MIN_FREE_FLOAT_PROMOTION_COVERAGE
    )

    result: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": "RM001-D007-v1",
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "market_panel_sha256": market_panel["panel_sha256"],
        "expected_session_count": expected_count,
        "ready_session_count": ready_count,
        "unavailable_sessions": unavailable_sessions,
        "parser_rejected_sessions": parser_rejected_sessions,
        "minimum_exact_join_coverage": min_join,
        "minimum_positive_issued_size_coverage": min_issued,
        "minimum_positive_market_cap_coverage": min_market_cap,
        "minimum_positive_free_float_capital_coverage": min_free_float,
        "maximum_duplicate_real_eq_identity_count": max_duplicate,
        "total_market_cap_source_passed": all_size_sessions_pass,
        "free_float_market_cap_source_passed": free_float_promoted,
        "sector_source_passed": False,
        "sector_source_reason": (
            "SECURITY_MASTER_COMPANY_INDUSTRY_FIELDS_NOT_MATERIALLY_POPULATED"
        ),
        "size_formula": "TOTAL_MARKET_CAP_INR = OFFICIAL_CLOSE * ISSD_CPTL",
        "issued_size_source_field": "IssdCptl",
        "par_value_used_in_size_formula": False,
        "session_results": session_results,
        "future_return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result
