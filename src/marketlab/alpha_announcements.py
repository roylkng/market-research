from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.preparation import PreparationError, _parse_exchange_timestamp

D003_AUDIT_ID = "AE001-D003-v1"
WINDOW_START = date(2026, 9, 15)
WINDOW_END = date(2026, 9, 21)
IST = ZoneInfo("Asia/Kolkata")
SYMBOL_SAMPLE = (
    "RELIANCE",
    "TCS",
    "INFY",
    "LT",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "MARUTI",
)


class AnnouncementAuditError(ValueError):
    """Raised when NSE corporate-announcement source evidence is inconsistent."""


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AnnouncementAuditError(
            "announcement audit payload must be finite canonical JSON"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def announcement_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("records") or []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise AnnouncementAuditError(
        "NSE corporate-announcement payload is not a row list"
    )


def official_timestamp(row: dict[str, Any]) -> datetime:
    last_error: Exception | None = None
    for key in ("exchdisstime", "an_dt", "sort_date", "dt"):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            parsed = _parse_exchange_timestamp(value)
        except PreparationError as exc:
            last_error = exc
            continue
        if parsed.tzinfo is None:
            raise AnnouncementAuditError(
                "NSE announcement timestamp must include timezone"
            )
        return parsed.astimezone(UTC)
    raise AnnouncementAuditError(
        f"announcement row has no parseable official timestamp: {last_error}"
    )


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def canonical_announcement(row: dict[str, Any]) -> dict[str, Any]:
    symbol = _clean(row.get("symbol")).upper()
    seq_id = _clean(row.get("seq_id"))
    if not symbol:
        raise AnnouncementAuditError("announcement row is missing symbol")
    if not seq_id:
        raise AnnouncementAuditError(
            f"{symbol}: announcement row is missing seq_id"
        )
    published = official_timestamp(row)
    semantic = {
        "symbol": symbol,
        "seq_id": seq_id,
        "exchange_published_at_utc": (
            published.isoformat().replace("+00:00", "Z")
        ),
        "desc": _clean(row.get("desc")),
        "attchmntText": _clean(row.get("attchmntText")),
        "attchmntFile": _clean(row.get("attchmntFile")),
    }
    return {
        **semantic,
        "announcement_id": canonical_hash(semantic),
    }


def normalize_announcement_payload(
    payload: Any,
    *,
    requested_start: date,
    requested_end: date,
) -> list[dict[str, Any]]:
    if requested_start > requested_end:
        raise AnnouncementAuditError(
            "announcement request window is reversed"
        )
    rows = []
    seen_ids: set[str] = set()
    seen_seq: dict[tuple[str, str], str] = {}
    for raw in announcement_rows(payload):
        row = canonical_announcement(raw)
        published_day = datetime.fromisoformat(
            row["exchange_published_at_utc"]
        ).astimezone(IST).date()
        if not requested_start <= published_day <= requested_end:
            raise AnnouncementAuditError(
                f"{row['symbol']}/{row['seq_id']}: timestamp outside requested window"
            )
        identity = row["announcement_id"]
        if identity in seen_ids:
            raise AnnouncementAuditError(
                f"duplicate canonical announcement identity: {identity}"
            )
        seen_ids.add(identity)
        seq_key = (row["symbol"], row["seq_id"])
        previous = seen_seq.get(seq_key)
        if previous is not None and previous != identity:
            raise AnnouncementAuditError(
                f"conflicting announcement rows for {seq_key}"
            )
        seen_seq[seq_key] = identity
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row["exchange_published_at_utc"],
            row["symbol"],
            row["seq_id"],
            row["announcement_id"],
        )
    )
    return rows


def build_d003_audit(
    *,
    full_payload: Any,
    full_raw_sha256: str,
    daily_payloads: dict[str, Any],
    daily_raw_sha256: dict[str, str],
    symbol_payloads: dict[str, Any],
    symbol_raw_sha256: dict[str, str],
    generated_at_utc: str,
) -> dict[str, Any]:
    expected_days = [
        date.fromordinal(WINDOW_START.toordinal() + offset)
        for offset in range((WINDOW_END - WINDOW_START).days + 1)
    ]
    expected_day_keys = [day.isoformat() for day in expected_days]
    if sorted(daily_payloads) != expected_day_keys:
        raise AnnouncementAuditError(
            "D003 daily payloads do not exactly cover frozen window"
        )
    if sorted(daily_raw_sha256) != expected_day_keys:
        raise AnnouncementAuditError(
            "D003 daily raw hashes do not exactly cover frozen window"
        )
    if tuple(sorted(symbol_payloads)) != tuple(sorted(SYMBOL_SAMPLE)):
        raise AnnouncementAuditError(
            "D003 symbol payloads do not exactly match frozen sample"
        )
    if tuple(sorted(symbol_raw_sha256)) != tuple(sorted(SYMBOL_SAMPLE)):
        raise AnnouncementAuditError(
            "D003 symbol raw hashes do not exactly match frozen sample"
        )

    full_rows = normalize_announcement_payload(
        full_payload,
        requested_start=WINDOW_START,
        requested_end=WINDOW_END,
    )
    full_by_id = {row["announcement_id"]: row for row in full_rows}

    daily_rows: list[dict[str, Any]] = []
    daily_counts: dict[str, int] = {}
    daily_ids: set[str] = set()
    for day in expected_days:
        key = day.isoformat()
        rows = normalize_announcement_payload(
            daily_payloads[key],
            requested_start=day,
            requested_end=day,
        )
        daily_counts[key] = len(rows)
        for row in rows:
            identity = row["announcement_id"]
            if identity in daily_ids:
                raise AnnouncementAuditError(
                    f"D003 announcement repeated across daily queries: {identity}"
                )
            daily_ids.add(identity)
            daily_rows.append(row)

    full_ids = set(full_by_id)
    full_vs_daily = {
        "full_count": len(full_ids),
        "daily_union_count": len(daily_ids),
        "missing_from_full_count": len(daily_ids - full_ids),
        "extra_in_full_count": len(full_ids - daily_ids),
        "exact_identity_match": full_ids == daily_ids,
    }

    symbol_reconciliation = {}
    symbol_pass = True
    for symbol in SYMBOL_SAMPLE:
        scoped = normalize_announcement_payload(
            symbol_payloads[symbol],
            requested_start=WINDOW_START,
            requested_end=WINDOW_END,
        )
        unexpected = [
            row for row in scoped if row["symbol"] != symbol
        ]
        if unexpected:
            raise AnnouncementAuditError(
                f"{symbol}: symbol-scoped response contains other symbols"
            )
        scoped_ids = {row["announcement_id"] for row in scoped}
        market_ids = {
            identity
            for identity, row in full_by_id.items()
            if row["symbol"] == symbol
        }
        match = scoped_ids == market_ids
        symbol_pass = symbol_pass and match
        symbol_reconciliation[symbol] = {
            "whole_market_count": len(market_ids),
            "symbol_scoped_count": len(scoped_ids),
            "missing_from_whole_market_count": len(scoped_ids - market_ids),
            "extra_in_whole_market_count": len(market_ids - scoped_ids),
            "exact_identity_match": match,
            "raw_sha256": symbol_raw_sha256[symbol],
        }

    symbol_counts = Counter(row["symbol"] for row in full_rows)
    subject_counts = Counter(row["desc"] for row in full_rows)
    thresholds = {
        str(threshold): len(full_rows) > threshold
        for threshold in (100, 200, 500, 1000)
    }

    generated = datetime.fromisoformat(generated_at_utc)
    if generated.tzinfo is None:
        raise AnnouncementAuditError(
            "D003 generated_at_utc must be timezone-aware"
        )

    passed = full_vs_daily["exact_identity_match"] and symbol_pass
    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": D003_AUDIT_ID,
        "status": "PASS" if passed else "FAIL",
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
        "generated_at_utc": generated.astimezone(UTC).isoformat(),
        "full_query_raw_sha256": full_raw_sha256,
        "daily_query_raw_sha256": dict(sorted(daily_raw_sha256.items())),
        "full_vs_daily": full_vs_daily,
        "daily_counts": daily_counts,
        "max_daily_count": max(daily_counts.values(), default=0),
        "distinct_symbol_count": len(symbol_counts),
        "max_rows_for_one_symbol": max(symbol_counts.values(), default=0),
        "most_active_symbols": [
            {"symbol": symbol, "count": count}
            for symbol, count in symbol_counts.most_common(25)
        ],
        "most_common_subjects": [
            {"subject": subject, "count": count}
            for subject, count in subject_counts.most_common(25)
        ],
        "full_count_exceeds_threshold": thresholds,
        "symbol_reconciliation": symbol_reconciliation,
        "primary_gates": {
            "full_vs_daily_exact": full_vs_daily[
                "exact_identity_match"
            ],
            "all_symbol_scoped_exact": symbol_pass,
        },
        "market_return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = canonical_hash(report)
    return report
