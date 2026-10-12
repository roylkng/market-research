"""Explain absent NSE EQ-series rows without inventing zero turnover or delisting.

HG007-P041 found ORBTEXP missing 11 and RETAIL missing five of the 20
original historical EQ sessions. Reuse the exact same original full-market
NSE UDiFF bytes to see whether other exchange series contain their symbols.

No alternate series is converted into an EQ open, tradable ticket, stock
return or proof of a delisting, suspension or ticker renaming.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from marketlab.hg007_28_liquidity import (
    AUDIT_ID as ALL28_SOURCE_ID,
    validate_twenty_day_all_28,
)
from marketlab.hg007_liquidity_history import (
    LAST_SESSION,
    SOURCE_SHA,
    pinned_window_and_context,
    validated_historical_source,
)
from marketlab.marketdata import udiff_url

AUDIT_ID = "HG007-P042-2026-10-12-ORIGINAL-NSE-ABSENT-EQ-SERIES-REVIEW-v1"
P041_PATH = Path(
    "research/hg007/twenty-session-liquidity/twenty-session-28-stock-v1.json"
)
P041_GIT_BLOB = "a01b9823a29cdfe94f5e2f21e84159b66a949c75"
EXPECTED_GAPS = {"ORBTEXP": 11, "RETAIL": 5}
MAX_UNCOMPRESSED_UDIFF_BYTES = 30_000_000
REQUIRED_COLUMNS = frozenset({
    "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
    "SctySrs", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd",
})


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _digest(obj: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _source28(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = (root / P041_PATH).read_bytes()
    if _git_blob(raw) != P041_GIT_BLOB:
        raise ValueError("original all-28 source evidence Git blob changed")
    packet = json.loads(raw)
    if not isinstance(packet, dict):
        raise TypeError("P041 original source packet must be a JSON object")
    validate_twenty_day_all_28(packet)
    if (
        packet.get("audit_id") != ALL28_SOURCE_ID
        or packet.get("original_outside_u001_symbol_count") != 28
        or packet.get("complete_20_session_equity_company_count") != 26
        or packet.get("incomplete_or_changed_identity_company_count") != 2
        or packet.get("source_window_last_session") != LAST_SESSION
    ):
        raise ValueError("original all-28 session/accounting contract changed")
    by_symbol = {row["symbol"]: row for row in packet["casework"]}
    actual_gaps = {
        symbol: len(row["missing_or_invalid_session_rows"])
        for symbol, row in by_symbol.items() if not row["exact_20_session_coverage_complete"]
    }
    if actual_gaps != EXPECTED_GAPS:
        raise ValueError("source P041 original EQ gap identities or counts changed")
    return packet, {
        "path": str(P041_PATH),
        "git_blob_sha": P041_GIT_BLOB,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _original_full_market_rows(
    raw_zip: bytes, *, session: str, symbols: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Include NSE CM STK rows in *any series*, never just EQ."""
    if not isinstance(raw_zip, bytes) or not raw_zip:
        raise ValueError("original exchange source bytes required")
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            listed = archive.infolist()
            if (
                len(listed) != 1
                or not listed[0].filename.lower().endswith(".csv")
                or listed[0].file_size > MAX_UNCOMPRESSED_UDIFF_BYTES
            ):
                raise ValueError("unexpected NSE single-CSV UDiFF archive")
            csv_bytes = archive.read(listed[0])
    except (zipfile.BadZipFile, RuntimeError, KeyError, OSError) as exc:
        raise ValueError("original NSE UDiFF ZIP cannot be read") from exc
    try:
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("original UDiFF source is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
        raise ValueError("original NSE cash-market source schema missing required fields")

    target: dict[str, list[dict[str, Any]]] = {name: [] for name in symbols}
    for row in reader:
        symbol = str(row.get("TckrSymb") or "").strip().upper()
        if (
            symbol not in symbols
            or str(row.get("TradDt") or "").strip() != session
            or str(row.get("Sgmt") or "").strip().upper() != "CM"
            or str(row.get("Src") or "").strip().upper() != "NSE"
            or str(row.get("FinInstrmTp") or "").strip().upper() != "STK"
        ):
            continue
        isin = str(row.get("ISIN") or "").strip()
        series = str(row.get("SctySrs") or "").strip().upper()
        if not isin or not series:
            raise ValueError(f"{session}/{symbol}: original stock row identity/series blank")
        numeric: dict[str, float | None] = {}
        for field, label in [
            ("TtlTradgVol", "reported_shares_traded"),
            ("TtlTrfVal", "reported_traded_value_inr"),
            ("TtlNbOfTxsExctd", "reported_transaction_count"),
        ]:
            try:
                number = float(str(row.get(field) or "").strip())
            except (TypeError, ValueError):
                number = None
            if number is not None and (not math.isfinite(number) or number < 0):
                number = None
            numeric[label] = number
        target[symbol].append({
            "symbol": symbol,
            "isin": isin,
            "exchange_series": series,
            **numeric,
            "valid_positive_executed_turnover": (
                all(value is not None and value > 0 for value in numeric.values())
                and bool(numeric["reported_shares_traded"].is_integer())
                and bool(numeric["reported_transaction_count"].is_integer())
            ),
        })
    return target


def build_missing_eq_series_review(root: Path) -> dict[str, Any]:
    original, p041_receipt = _source28(root)
    wanted = set(EXPECTED_GAPS)
    p041_casework = {case["symbol"]: case for case in original["casework"]}
    dates, _five_ids, _p035, oct9_original, calendar_provenance = (
        pinned_window_and_context(root)
    )
    if [d["date"] for d in dates] != [
        row["session"] for row in p041_casework["RETAIL"]["daily_source_rows"]
    ]:
        raise ValueError("original 20 dates changed between NSE and P041")
    source_receipts: list[dict[str, Any]] = []
    per_name: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in wanted}
    for entry in dates:
        day = entry["date"]
        if day == LAST_SESSION:
            raw = oct9_original
            sha = SOURCE_SHA
        else:
            raw, receipt = validated_historical_source(root, day, entry["close_utc"])
            if raw is None:
                raise ValueError(f"{day}: original full NSE source missing")
            sha = receipt["source_sha256"]
        prior_entry = next(
            item for item in original["twenty_original_nse_whole_market_source_receipts"]
            if item["date"] == day
        )
        if prior_entry["original_sha256"] != sha:
            raise ValueError(f"{day}: full NSE source changed from all-28 audit")
        source_receipts.append({
            "date": day,
            "original_udiff_sha256": sha,
            "exact_official_url": udiff_url(date.fromisoformat(day)),
            "official_original_from_prior_28_source": True,
        })
        exact_rows = _original_full_market_rows(
            raw, session=day, symbols=wanted
        )
        for symbol in sorted(wanted):
            from_p041 = next(
                item for item in p041_casework[symbol]["daily_source_rows"]
                if item["session"] == day
            )
            matched = exact_rows[symbol]
            eq_rows = [row for row in matched if row["exchange_series"] == "EQ"]
            alternate = [row for row in matched if row["exchange_series"] != "EQ"]
            if from_p041["state"] == "EXACT_NSE_EQ_OHLC_AND_TURNOVER_OBSERVED":
                if (
                    len(eq_rows) != 1
                    or eq_rows[0]["isin"] != from_p041["isin"]
                    or eq_rows[0]["reported_traded_value_inr"] is None
                    or not math.isclose(
                        eq_rows[0]["reported_traded_value_inr"],
                        from_p041["traded_value_inr"],
                        rel_tol=0, abs_tol=0.02,
                    )
                ):
                    raise ValueError(f"{symbol}/{day}: original EQ row disagrees with P041")
                continue
            if from_p041["state"] != "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION":
                raise ValueError("P041 missing-session classification no longer matches")
            if eq_rows:
                raise ValueError(f"{symbol}/{day}: original EQ row wrongly recorded missing")
            verified_isins = p041_casework[symbol]["observed_isins"]
            if len(verified_isins) != 1:
                raise ValueError(f"{symbol}: prior EQ ISIN not stable")
            alternate_isins = sorted({row["isin"] for row in alternate})
            matching_identity = all(
                row["isin"] == verified_isins[0] for row in alternate
            )
            if not alternate:
                reason = "NO_SAME_SYMBOL_STK_ROW_IN_OFFICIAL_NSE_CM_SOURCE"
            elif not matching_identity:
                reason = "NON_EQ_ISIN_DIFFERS_IDENTITY_REVIEW_REQUIRED"
            elif any(row["valid_positive_executed_turnover"] for row in alternate):
                reason = "OFFICIAL_NON_EQ_SERIES_TURNOVER_OBSERVED_NOT_EQ_TRADE"
            else:
                reason = "OFFICIAL_NON_EQ_ROW_PRESENT_WITH_UNVERIFIED_TURNOVER"
            per_name[symbol].append({
                "symbol": symbol,
                "session_date": day,
                "source_p041_state": from_p041["state"],
                "classification": reason,
                "historically_observed_eq_isin": verified_isins[0],
                "same_symbol_non_eq_rows": alternate,
                "non_eq_isin_matches_prior_eq_isin": matching_identity if alternate else None,
                "other_ticker_names_or_unreported_series_excluded": True,
                "no_stock_trading_on_exchange_proven": False,
                "new_eq_series_price_or_turnover_imputed": False,
                "equity_returns_calculated": False,
            })
    for symbol, expected_count in EXPECTED_GAPS.items():
        if len(per_name[symbol]) != expected_count:
            raise ValueError(f"{symbol}: exact EQ missing-day count changed")

    counts = {
        symbol: dict(sorted({
            s: sum(row["classification"] == s for row in per_name[symbol])
            for s in sorted({row["classification"] for row in per_name[symbol]})
        }.items()))
        for symbol in sorted(wanted)
    }
    packet = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "ORIGINAL_NSE_SERIES_GAP_DISCOVERY_NOT_SUSPENSION_OR_INVESTMENT_SIGNAL",
        "source_cutoff_session": LAST_SESSION,
        "original_hg002_company_count_preserved": 28,
        "examined_names_missing_equity_series": sorted(wanted),
        "source_session_count": 20,
        "source_previous_p041": p041_receipt,
        "source_prior_market_calendar": calendar_provenance,
        "source_original_twenty_equity_files": source_receipts,
        "original_eq_missing_observations": sum(EXPECTED_GAPS.values()),
        "missing_eq_observations_by_symbol": EXPECTED_GAPS,
        "findings": [
            {
                "symbol": symbol,
                "missing_eq_day_count": len(per_name[symbol]),
                "missing_eq_day_evidence": per_name[symbol],
                "source_classification_counts": counts[symbol],
                "series_change_is_suspension_proof": False,
                "current_tradability_proven": False,
                "company_buy_or_alpha_thesis_changed": False,
            }
            for symbol in sorted(wanted)
        ],
        "original_selection_modified": False,
        "missing_eq_days_treated_as_zero_turnover": False,
        "off_equity_series_rows_counted_in_equity_turnover": False,
        "executability_verified": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _digest(packet)
    return packet


def validate_missing_eq_series_review(packet: dict[str, Any]) -> None:
    if packet.get("audit_id") != AUDIT_ID:
        raise ValueError("unrecognized original EQ absence review")
    claimed = packet.get("packet_sha256")
    if not isinstance(claimed, str) or _digest({
        k: v for k, v in packet.items() if k != "packet_sha256"
    }) != claimed:
        raise ValueError("original NSE non-EQ source observations tampered")
    if (
        packet.get("original_hg002_company_count_preserved") != 28
        or packet.get("source_session_count") != 20
        or packet.get("examined_names_missing_equity_series") != sorted(EXPECTED_GAPS)
        or len(packet.get("findings", [])) != 2
        or packet.get("original_eq_missing_observations") != 16
    ):
        raise ValueError("original HG002 and exact missing EQ session accounting changed")
    for field in (
        "original_selection_modified",
        "missing_eq_days_treated_as_zero_turnover",
        "off_equity_series_rows_counted_in_equity_turnover",
        "executability_verified", "return_outcomes_opened",
        "portfolio_eligibility_allowed", "live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise ValueError(f"source-only missing-EQ review cannot authorize {field}")
