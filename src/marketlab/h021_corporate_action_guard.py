"""Conservative corporate-action *risk screen* for H021 future stock returns.

Never promote empty, partial, malformed, stale, or blocked NSE responses to
corporate-action adjusted price returns. This module does NOT adjust prices,
construct holdings, estimate returns, or authorize capital.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
AUDIT_ID = "H021-P010-SHARE-AND-DIVIDEND-HAZARD-SCREEN-v1"
SHARE_EVENT_TERMS = (
    "bonus",
    "stock split",
    "split",
    "sub-division",
    "subdivision",
    "consolidation",
    "right issue",
    "rights issue",
    "rights",
    "demerger",
    "de-merger",
    "spin off",
    "spin-off",
    "merger",
    "amalgamation",
    "scheme of arrangement",
    "capital reduction",
    "reduction of capital",
    "face value",
    "buyback",
    "buy-back",
    "preferential allotment",
    "warrant conversion",
    "conversion of warrant",
)
CASH_EVENT_TERMS = ("dividend", "distribution of cash")
IST = ZoneInfo("Asia/Kolkata")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _parse_capture_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("corporate-action capture timestamp missing")
    try:
        instant = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("corporate-action source timestamp is invalid") from exc
    if instant.tzinfo is None:
        raise ValueError("corporate-action source timestamp must include timezone")
    return instant.astimezone(UTC)


def _parse_action_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    for pattern in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value.strip(), pattern).date()
            return parsed
        except ValueError:
            pass
    return None


def _official_source_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and parts.hostname == "www.nseindia.com"
        and parts.username is None
        and parts.password is None
        and parts.port in (None, 443)
        and parts.path == "/api/corporates-corporateActions"
        and not parts.fragment
    )


def _source_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        candidate = value
    elif isinstance(value, dict):
        if isinstance(value.get("data"), list):
            candidate = value["data"]
        elif isinstance(value.get("records"), list):
            candidate = value["records"]
        else:
            raise TypeError("NSE corporate-action response missing data/records list")
    else:
        raise TypeError("NSE corporate-action response must be a list or object")
    if any(not isinstance(row, dict) for row in candidate):
        raise ValueError("NSE corporate-action response contains malformed rows")
    return candidate


def screen_h021_corporate_actions(
    *,
    symbols_to_isins: dict[str, str],
    interval_start: str,
    interval_end: str,
    raw_source: bytes | None,
    source_receipt: dict[str, Any] | None,
    prepared_at_utc: str,
) -> dict[str, Any]:
    """Screen original NSE event bytes; no source can establish return clearance.

    Corporate-action API observations are often paginated or incomplete.
    Therefore even a fully parsed empty response cannot by itself prove
    exhaustive exchange-event coverage, corporate-action price conversion,
    or dividend-adjusted total-return comparability.
    """
    if not isinstance(symbols_to_isins, dict) or not symbols_to_isins:
        raise ValueError("H021 selected symbols are required")
    if any(
        not isinstance(symbol, str)
        or not symbol
        or symbol != symbol.strip().upper()
        or not isinstance(isin, str)
        or len(isin) != 12
        for symbol, isin in symbols_to_isins.items()
    ):
        raise ValueError("symbols/ISINs must be exact frozen uppercase identities")
    start = date.fromisoformat(interval_start)
    end = date.fromisoformat(interval_end)
    if end < start:
        raise ValueError("corporate-action screen interval is backwards")
    prepared = _parse_capture_time(prepared_at_utc)
    original_source_state = "NO_ORIGINAL_SOURCE"
    source_sha = None
    captured_at = None
    source_url = None
    original_row_count = None
    hazards: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    if raw_source is not None or source_receipt is not None:
        if not isinstance(source_receipt, dict):
            raise TypeError("original NSE source receipt required with source bytes")
        source_url = source_receipt.get("url")
        if not _official_source_url(source_url):
            raise ValueError("unsupported corporate-action official NSE URL")
        captured = _parse_capture_time(source_receipt.get("captured_at_utc"))
        captured_at = captured.isoformat().replace("+00:00", "Z")
        if prepared < captured:
            raise ValueError("audit timestamp precedes original NSE source capture")
        status = source_receipt.get("status")
        http_code = source_receipt.get("http_status")
        if status == "OK":
            if http_code != 200 or not isinstance(raw_source, bytes) or not raw_source:
                raise ValueError("successful NSE corporate-action response needs original bytes")
            source_sha = hashlib.sha256(raw_source).hexdigest()
            if source_receipt.get("raw_sha256") != source_sha:
                raise ValueError("original NSE corporate-action bytes SHA-256 mismatch")
            if captured < datetime.combine(end, time(15, 30), tzinfo=IST).astimezone(UTC):
                original_source_state = "BLOCKED_SOURCE_CAPTURE_BEFORE_INTERVAL_END"
            else:
                try:
                    parsed = json.loads(raw_source)
                    rows = _source_rows(parsed)
                except (UnicodeDecodeError, ValueError, TypeError):
                    original_source_state = "BLOCKED_UNVERIFIABLE_SOURCE_SCHEMA"
                else:
                    original_source_state = "SOURCE_SCREENED_COVERAGE_NOT_CERTIFIED"
                    original_row_count = len(rows)
                    for row in rows:
                        symbol = row.get("symbol") or row.get("Symbol")
                        if symbol not in symbols_to_isins:
                            continue
                        reason = str(row.get("subject") or row.get("purpose") or "").strip()
                        event_date = _parse_action_date(
                            row.get("exDate") or row.get("ex_date") or row.get("date")
                        )
                        if not reason or event_date is None:
                            unknown.append({
                                "symbol": symbol,
                                "status": "BLOCKED_UNKNOWN_EVENT_SEMANTICS_OR_DATE",
                                "source_row": row,
                            })
                            continue
                        if not (start <= event_date <= end):
                            continue
                        folded = reason.casefold()
                        share = any(term in folded for term in SHARE_EVENT_TERMS)
                        cash = any(term in folded for term in CASH_EVENT_TERMS)
                        event_isin = row.get("isin") or row.get("ISIN")
                        if event_isin is not None and event_isin != symbols_to_isins[symbol]:
                            unknown.append({
                                "symbol": symbol,
                                "status": "BLOCKED_EVENT_ISIN_MISMATCH",
                                "subject": reason,
                                "ex_date": event_date.isoformat(),
                            })
                            continue
                        if share or cash:
                            hazards.append({
                                "symbol": symbol,
                                "subject": reason,
                                "ex_date": event_date.isoformat(),
                                "classification": (
                                    "SHARE_BASIS_ACTION" if share else "CASH_DIVIDEND_ACTION"
                                ),
                                "event_isin_confirmed": event_isin is not None,
                            })
                        else:
                            unknown.append({
                                "symbol": symbol,
                                "status": "BLOCKED_UNCLASSIFIED_CORPORATE_EVENT",
                                "subject": reason,
                                "ex_date": event_date.isoformat(),
                            })
        else:
            if (
                status not in {"NOT_PUBLISHED", "ACCESS_BLOCKED", "FETCH_FAILED"}
                or raw_source is not None
                or not isinstance(source_receipt.get("error"), str)
                or not source_receipt["error"]
            ):
                raise ValueError("invalid blocked NSE source evidence")
            original_source_state = "BLOCKED_" + status

    per_symbol: list[dict[str, Any]] = []
    for symbol, isin in sorted(symbols_to_isins.items()):
        subject_hazards = [x for x in hazards if x["symbol"] == symbol]
        uncertainty = [x for x in unknown if x["symbol"] == symbol]
        if subject_hazards or uncertainty:
            state = "BLOCKED_ACTION_OR_IDENTITY_HAZARD"
        else:
            state = "BLOCKED_MISSING_OR_UNVERIFIED_COMPLETE_SOURCE"
        per_symbol.append({
            "symbol": symbol,
            "isin": isin,
            "state": state,
            "source_reported_hazards": subject_hazards,
            "source_unknown_events": uncertainty,
            "full_interval_corporate_action_coverage_verified": False,
            "stock_share_change_adjustments_verified": False,
            "cash_dividend_treatment_verified": False,
            "raw_price_return_eligible": False,
        })
    output: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": AUDIT_ID,
        "classification": "INDEPENDENT_H021_SOURCE_HAZARD_SCREEN_NOT_RETURN_CLEARANCE",
        "interval_start": interval_start,
        "interval_end": interval_end,
        "prepared_at_utc": prepared.isoformat().replace("+00:00", "Z"),
        "source_state": original_source_state,
        "source_url": source_url,
        "source_sha256": source_sha,
        "source_captured_at_utc": captured_at,
        "source_returned_row_count": original_row_count,
        "selected_symbol_count": len(symbols_to_isins),
        "corporate_event_hazard_count": len(hazards),
        "unclassified_event_count": len(unknown),
        "symbol_states": per_symbol,
        "separately_verified_exhaustive_source_coverage": False,
        "share_adjustment_factors_verified": False,
        "dividends_total_return_basis_verified": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["packet_sha256"] = _digest(output)
    return output


def require_h021_price_basis_clearance(report: dict[str, Any]) -> None:
    """A source *screen* can never be substituted for price-return clearance."""
    if report.get("audit_id") != AUDIT_ID:
        raise ValueError("unrecognized H021 corporate-action screening protocol")
    original = report.get("packet_sha256")
    if not isinstance(original, str) or _digest(
        {k: v for k, v in report.items() if k != "packet_sha256"}
    ) != original:
        raise ValueError("H021 corporate-action source screen was modified")
    if (
        report.get("separately_verified_exhaustive_source_coverage") is not True
        or report.get("share_adjustment_factors_verified") is not True
        or report.get("dividends_total_return_basis_verified") is not True
    ):
        raise ValueError("H021 raw stock price return basis remains unverified")
    raise ValueError(
        "H021 P010 is only a hazard screen; independent reviewed return-basis "
        "protocol required before opening 20/60-session results"
    )
