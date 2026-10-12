"""Reconcile first *later-complete* NSE P004 packet with original 404 and P018.

P019 neither rewrites the immutable 17:33 IST original NSE attempt nor
accepts a retrospective substituted price. It joins original stock bytes
with independently SHA-matched primary+mirror 12 October Nifty500 CSV.
No stock benchmark excess, total return, order fills or live capital.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from marketlab.h021_entry_observation import (
    ENTRY_DAY,
    EXPECTED_SELECTION,
    _canonical_hash,
    validate_entry_observation,
)
from marketlab.h021_first_entry_intent import git_blob_sha
from marketlab.h021_index_recovery import (
    ORIGINAL_FIRST_PACKET,
    ORIGINAL_PACKET_BLOB,
    ORIGINAL_PACKET_SHA,
    ORIGINAL_STOCK_SHA,
    validate_recovery,
)

RECONCILIATION_ID = "H021-P019-2026-10-12-FIRST-COMPLETE-OFFICIAL-ENTRY-RECONCILIATION-v1"
RECOVERY_PATH = Path(
    "research/prospective/h021/index-recovery/"
    "2026-10-12-official-index-supplement-v1.json"
)
RECOVERY_BLOB = "68d9c6530cef3bdb0339777582a055d70279fe14"
RECOVERY_DIGEST = "8e8194a7eb0a9e575b3d924a75f2f78ff1796f24db409936c52fb38fc14eb612"
NSE_INDEX_CSV_SHA = "fc847998c9d8bfa461ddad1770dc610086eadea3d442f1dfe515ae76b83c7f25"


def _source(root: Path, path: Path, expected_blob: str) -> dict[str, Any]:
    raw = (root / path).read_bytes()
    if git_blob_sha(raw) != expected_blob:
        raise ValueError(f"frozen H021 original source Git blob mismatch: {path}")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("H021 original source must be JSON object")
    return data


def load_pinned_reconciliation_sources(root: Path) -> tuple[dict, dict]:
    original = _source(root, ORIGINAL_FIRST_PACKET, ORIGINAL_PACKET_BLOB)
    validate_entry_observation(original)
    if original.get("packet_sha256") != ORIGINAL_PACKET_SHA or (
        original.get("source_receipts", {}).get("index", {}).get("status")
        != "NOT_PUBLISHED"
    ):
        raise ValueError("first original NSE index source must remain HTTP404")
    supplement = _source(root, RECOVERY_PATH, RECOVERY_BLOB)
    validate_recovery(supplement)
    if (
        supplement.get("packet_sha256") != RECOVERY_DIGEST
        or supplement.get("source_state") != "OFFICIAL_DUAL_HOSTS_AGREE"
        or supplement.get("verified_primary_or_agreed_dual_index_source") is not True
        or supplement.get("benchmark", {}).get("corroborated_recovery_open") != 21936.25
        or supplement.get("benchmark", {}).get("corroborated_recovery_close") != 21822.75
        or supplement.get("source_receipts", {}).get("primary", {}).get("raw_sha256")
        != NSE_INDEX_CSV_SHA
        or supplement.get("source_receipts", {}).get("nse_archive_mirror", {}).get(
            "raw_sha256"
        ) != NSE_INDEX_CSV_SHA
    ):
        raise ValueError("source only recovered Oct12 index changed or uncorroborated")
    raw_csv = (
        root
        / "research/prospective/h021/index-recovery/raw/sha256"
        / f"{NSE_INDEX_CSV_SHA}.csv"
    ).read_bytes()
    if hashlib.sha256(raw_csv).hexdigest() != NSE_INDEX_CSV_SHA:
        raise ValueError("recovered original official NSE index raw source was modified")
    return original, supplement


def reconcile_source_packet(
    *,
    first_attempt: dict[str, Any],
    source_supplement: dict[str, Any],
    later_complete: dict[str, Any],
) -> dict[str, Any]:
    validate_entry_observation(first_attempt)
    validate_entry_observation(later_complete)
    validate_recovery(source_supplement)
    if (
        first_attempt.get("packet_sha256") != ORIGINAL_PACKET_SHA
        or source_supplement.get("packet_sha256") != RECOVERY_DIGEST
        or later_complete.get("source_observation_status")
        != "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
        or first_attempt.get("source_observation_status")
        != "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"
        or later_complete.get("session_date_ist") != ENTRY_DAY
        or later_complete.get("source_intent_id") != first_attempt.get("source_intent_id")
        or later_complete.get("observed_official_stock_open_count") != 10
    ):
        raise ValueError("later official complete source cannot replace original first attempt")
    rows_a = first_attempt.get("stock_observations")
    rows_b = later_complete.get("stock_observations")
    if not isinstance(rows_a, list) or not isinstance(rows_b, list) or len(rows_a) != 10:
        raise ValueError("original ten NSE equity rows are missing")
    for symbol, old, new in zip(EXPECTED_SELECTION, rows_a, rows_b, strict=True):
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise TypeError("source first-entry row must be object")
        if old.get("symbol") != symbol or new.get("symbol") != symbol:
            raise ValueError("frozen H021 ten-company selection changed")
        if (
            old.get("isin") != new.get("isin")
            or old.get("source_sha256") != ORIGINAL_STOCK_SHA
            or new.get("source_sha256") != ORIGINAL_STOCK_SHA
            or old.get("open_price_inr") != new.get("open_price_inr")
            or old.get("high_price_inr") != new.get("high_price_inr")
            or old.get("low_price_inr") != new.get("low_price_inr")
            or old.get("close_price_inr") != new.get("close_price_inr")
            or new.get("actual_trade_fill_confirmed") is not False
        ):
            raise ValueError(f"{symbol}: later source cannot revise first observed stock")
    index = later_complete.get("source_receipts", {}).get("index", {})
    original = source_supplement.get("source_receipts", {}).get("primary", {})
    mirrored = source_supplement.get("source_receipts", {}).get(
        "nse_archive_mirror", {}
    )
    benchmark = later_complete.get("benchmark_observation", {})
    if (
        not isinstance(index, dict) or not isinstance(benchmark, dict)
        or source_supplement.get("source_state") != "OFFICIAL_DUAL_HOSTS_AGREE"
        or source_supplement.get("verified_primary_or_agreed_dual_index_source") is not True
        or index.get("status") != "OK"
        or index.get("raw_sha256") != NSE_INDEX_CSV_SHA
        or original.get("raw_sha256") != NSE_INDEX_CSV_SHA
        or mirrored.get("raw_sha256") != NSE_INDEX_CSV_SHA
        or benchmark.get("source_sha256") != NSE_INDEX_CSV_SHA
        or benchmark.get("open_index_value")
        != source_supplement.get("benchmark", {}).get("corroborated_recovery_open")
        or benchmark.get("close_index_value")
        != source_supplement.get("benchmark", {}).get("corroborated_recovery_close")
        or benchmark.get("status") != "OFFICIAL_PRICE_INDEX_OHLC_OBSERVED"
    ):
        raise ValueError("new P004 official benchmark differs from two NSE source hosts")
    captured = datetime.fromisoformat(index["captured_at_utc"])
    first_index_capture = datetime.fromisoformat(original["captured_at_utc"])
    if captured < first_index_capture:
        raise ValueError("later P004 full source cannot backdate the verified index")
    report = {
        "schema_version": 1,
        "review_id": RECONCILIATION_ID,
        "classification": "SOURCE_RECONCILIATION_NOT_H021_RETURN_OR_ORDER",
        "session_date_ist": ENTRY_DAY,
        "source_first_attempt_sha256": ORIGINAL_PACKET_SHA,
        "source_later_complete_packet_sha256": later_complete["packet_sha256"],
        "source_later_packet_recorded_at_utc": later_complete["recorded_at_utc"],
        "source_index_supplement_sha256": RECOVERY_DIGEST,
        "official_original_udiff_sha256": ORIGINAL_STOCK_SHA,
        "official_original_index_sha256": NSE_INDEX_CSV_SHA,
        "selected_symbols_unchanged": list(EXPECTED_SELECTION),
        "all_ten_original_open_high_low_close_observations_identical": True,
        "nifty500_open_from_agreed_official_sources": 21936.25,
        "nifty500_close_from_agreed_official_sources": 21822.75,
        "original_index_404_receipt_retained": True,
        "index_later_retrieval_timestamp_not_backdated": True,
        "stock_and_benchmark_source_complete": True,
        "nifty500_is_price_index_not_tri": True,
        "first_executable_fill_verified": False,
        "dividend_cash_entitlement_verified": False,
        "share_actions_adjusted": False,
        "nifty500_tri_total_return_basis_verified": False,
        "horizon_20_60_calendar_and_returns_verified": False,
        "benchmark_excess_calculated": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    report["packet_sha256"] = _canonical_hash(report)
    return report


def validate_reconciliation(report: dict[str, Any]) -> None:
    digest = report.get("packet_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or (
        _canonical_hash({k: v for k, v in report.items() if k != "packet_sha256"})
        != digest
    ):
        raise ValueError("original official H021 source reconciliation hash mismatch")
    if (
        report.get("review_id") != RECONCILIATION_ID
        or report.get("source_first_attempt_sha256") != ORIGINAL_PACKET_SHA
        or report.get("source_index_supplement_sha256") != RECOVERY_DIGEST
        or report.get("source_later_complete_packet_sha256") is None
    ):
        raise ValueError("not first H021 NSE equity/index data-completeness proof")
    for flag in (
        "first_executable_fill_verified",
        "dividend_cash_entitlement_verified",
        "share_actions_adjusted",
        "nifty500_tri_total_return_basis_verified",
        "horizon_20_60_calendar_and_returns_verified",
        "benchmark_excess_calculated",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if report.get(flag) is not False:
            raise ValueError(f"source-only H021 P019 cannot authorize {flag}")
