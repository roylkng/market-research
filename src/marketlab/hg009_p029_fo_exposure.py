"""HG009 P029: original PRE-ENTRY NSE stock-futures presence as exposure only.

The original 2026-10-14 FO UDiFF archive was captured before Oct15 entry.
Stock-futures contract PRESENCE is not definitive CAS eligibility, not a
verified ISIN join, and not alpha. No stock price or future return is opened.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_futures import parse_fo_udiff_stock_futures
from marketlab.alpha_sc003_preopen import validate_sc003_ledger
from marketlab.hg009_controls import (
    load_hg009_inputs,
    verify_hg009_controls,
)

REPORT_ID = "HG009-P029-OCT14-PREENTRY-FO-EXPOSURE-v1"
DATE = "2026-10-14"
ENTRY = "2026-10-15"
ENTRY_OPEN_UTC = datetime(2026, 10, 15, 3, 45, tzinfo=UTC)
FO_SHA = "3e923241fa238ae1f2d2a86cc70ff63967d1fe9e0c96423716d1991bba372835"
FO_ATTEMPT_SHA = "8dd9753ebf55619461be5cff9cebe9476039236fe0b7ca2648ce55a7d9fd64fb"
FO_BLOB_PATH = Path(
    "research/prospective/ae001-sc003/raw/2026-10-14/"
    "futures-3e923241fa238ae1f2d2a86cc70ff63967d1fe9e0c96423716d1991bba372835.zip"
)
SOURCE_LEDGER = Path("research/prospective/ae001-sc003/source-ledger.json")
CONTROLS_PATH = Path(
    "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
)
FO_CSV_ROW_COUNT = 635
ORIGINAL_SELECTED_SHA = "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
ORIGINAL_CONTROLS_SHA = "8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8"


def _utc(value: object, *, label: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise AlphaContractError(f"P029 invalid {label} timestamp") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError(f"P029 {label} must be timezone-aware")
    return stamp.astimezone(UTC)


def build_preentry_fo_exposure(
    *,
    original: dict,
    selected: dict,
    controls: dict,
    source_ledger: dict,
    original_fo_raw: bytes,
) -> dict:
    verify_hg009_controls(controls, source=original, selected=selected)
    if (
        selected["cohort_sha256"] != ORIGINAL_SELECTED_SHA
        or controls["manifest_sha256"] != ORIGINAL_CONTROLS_SHA
    ):
        raise AlphaContractError("P029 original Oct14 HG009 identity changed")
    validate_sc003_ledger(source_ledger)
    attempts = [
        entry for entry in source_ledger["attempts"]
        if entry.get("attempt_sha256") == FO_ATTEMPT_SHA
    ]
    if len(attempts) != 1:
        raise AlphaContractError("P029 missing one exact historical FO receipt")
    attempt = attempts[0]
    if (
        attempt["target_session_date"] != DATE
        or attempt["source_status"] != "READY"
        or attempt["ready_before_preopen_cutoff"] is not True
        or attempt["raw_sha256"] != FO_SHA
        or attempt["raw_repo_path"] != str(FO_BLOB_PATH)
        or attempt["target_close_timestamp_utc"] != "2026-10-14T10:00:00Z"
    ):
        raise AlphaContractError("P029 original NSE FO receipt time/source drift")
    captured = _utc(attempt["captured_at_utc"], label="FO capture")
    if not (
        _utc(attempt["target_close_timestamp_utc"], label="NSE D close")
        < captured < ENTRY_OPEN_UTC
    ):
        raise AlphaContractError("P029 FO source was not available before entry")
    if (
        not isinstance(original_fo_raw, bytes)
        or hashlib.sha256(original_fo_raw).hexdigest() != FO_SHA
    ):
        raise AlphaContractError("P029 NSE original FO bytes SHA mismatch")
    contracts, diagnostics = parse_fo_udiff_stock_futures(
        original_fo_raw, session_date=date.fromisoformat(DATE),
    )
    if (
        len(contracts) != FO_CSV_ROW_COUNT
        or diagnostics.get("accepted_contract_row_count") != FO_CSV_ROW_COUNT
        or not contracts
    ):
        raise AlphaContractError("P029 original NSE futures contract counts changed")
    underlyings = Counter(row.symbol for row in contracts)
    if not underlyings or any(not k for k in underlyings):
        raise AlphaContractError("P029 original underlying symbols missing")
    arms = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    output = []
    summary = {}
    for arm, company_rows in arms.items():
        if len(company_rows) != 100:
            raise AlphaContractError("P029 fixed original 100-name arm changed")
        seen = set()
        observed = 0
        for company in sorted(company_rows, key=lambda x: (x["symbol"], x["isin"])):
            symbol, isin = company["symbol"], company["isin"]
            if (symbol, isin) in seen:
                raise AlphaContractError("P029 frozen symbol+ISIN duplicated")
            seen.add((symbol, isin))
            has_future = symbol in underlyings
            observed += int(has_future)
            output.append({
                "arm": arm,
                "original_symbol": symbol,
                "frozen_EQ_isin": isin,
                "original_oct14_FO_ticker_contract_present": has_future,
                "contract_rows_for_symbol": underlyings.get(symbol, 0),
                "source_FO_ticker_isin_independently_verified": False,
                "closing_auction_stock_eligibility_proven": False,
                "market_return_or_trade_inferred": False,
            })
        summary[arm] = {
            "fixed_original_company_count": len(company_rows),
            "oct14_futures_ticker_seen_count": observed,
            "oct14_futures_ticker_not_seen_count": 100 - observed,
            "oct14_futures_ticker_seen_fraction": round(observed / 100, 4),
            "stock_level_cas_eligibility_count_independently_verified": 0,
        }
    if len(output) != 300 or len({
        (r["original_symbol"], r["frozen_EQ_isin"]) for r in output
    }) != 300:
        raise AlphaContractError("P029 300 research identities not preserved")
    packet = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "method_date_ist": "2026-10-21",
        "original_source_session_date": DATE,
        "first_original_cohort_entry_date": ENTRY,
        "original_source_was_captured_before_cohort_entry": True,
        "original_source_FO_attempt_sha256": FO_ATTEMPT_SHA,
        "original_FO_raw_repo_path": str(FO_BLOB_PATH),
        "original_FO_raw_sha256": FO_SHA,
        "actual_original_source_captured_at_utc": captured.isoformat(),
        "original_accepted_FO_stock_contract_rows": len(contracts),
        "original_FO_stock_underlying_ticker_count": len(underlyings),
        "original_FO_parser_diagnostics": diagnostics,
        "frozen_cohort_sha256": ORIGINAL_SELECTED_SHA,
        "frozen_controls_sha256": ORIGINAL_CONTROLS_SHA,
        "fixed_company_count": 300,
        "original_group_exposure": summary,
        "original_company_exposure": output,
        "source_FO_file_does_not_contain_verified_issuer_ISIN": True,
        "absence_of_traded_FO_row_does_not_prove_ineligible_for_CAS": True,
        "CAS_eligibility_requiring_separate_original_exchange_list": True,
        "method_created_after_original_H1_was_seen": True,
        "prohibited_as_posthoc_original_H1_feature_or_confirmation": True,
        "no_postentry_market_price_source_read": True,
        "causal_or_after_cost_alpha_proven": False,
        "company_expected_stock_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["report_sha256"] = digest(packet)
    return packet


def materialize(root: Path) -> dict:
    original, selected = load_hg009_inputs(root)
    controls = json.loads((root / CONTROLS_PATH).read_text("utf-8"))
    source_ledger = json.loads((root / SOURCE_LEDGER).read_text("utf-8"))
    raw = (root / FO_BLOB_PATH).read_bytes()
    return build_preentry_fo_exposure(
        original=original,
        selected=selected,
        controls=controls,
        source_ledger=source_ledger,
        original_fo_raw=raw,
    )


def validate(packet: dict, root: Path) -> None:
    unsigned = copy.deepcopy(packet)
    expected = unsigned.pop("report_sha256", None)
    if expected != digest(unsigned):
        raise AlphaContractError("P029 signed original FO report changed")
    if packet != materialize(root):
        raise AlphaContractError("P029 original NSE futures bytes did not reproduce")
