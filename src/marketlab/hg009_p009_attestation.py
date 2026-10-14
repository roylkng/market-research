"""P008/P009 independent original NSE issuer filing byte-attestation.

The earliest verified October 14 issuer receipt for each of three audited
FY26 statements is source-pinned and independently replayed from complete
original HTML bytes. This is not normalized owner FCF or stock fair value.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p008_capture import EXPECTED_ROWS, validate_issuer_html
from marketlab.hg009_p008_underwriting import load_sources

ATTESTATION_ID = "HG009-P009-FIRST-NSE-FY26-FILING-ATTESTATION-v1"
SOURCES = {
    "ACUTAAS": {
        "raw_sha256": "d2051e30328859b10f5e40a3161dd69ecbdfdce59f9cd73d8fd2e126a1149b57",
        "receipt_path": "research/hg009/p008-originals/attempts/38617239523-1-ACUTAAS.json",
        "receipt_sha256": "1bca47b38040fb76b08f6aa33c02be986f921376e4835c94145b1f47f9cd42c0",
    },
    "ACE": {
        "raw_sha256": "6e58fccb3104932bd45f5311cd5ff47ad59e47547066e2217e9b12fc68c05f72",
        "receipt_path": "research/hg009/p008-originals/attempts/38617239523-1-ACE.json",
        "receipt_sha256": "c4db3be5282274afd3abb982bc905deb167824eae0acabfa50fe853c7a929017",
    },
    "TRAVELFOOD": {
        "raw_sha256": "0c7173926ba43378626ce876ef417a7ea210a18fa731ab5d4b33f4d63b5dd2a9",
        "receipt_path": "research/hg009/p008-originals/attempts/38617239523-1-TRAVELFOOD.json",
        "receipt_sha256": "7dd6f771fdb40f019cbe49c36fadf338bd79ea0ee49838545f75a9c24d609a65",
    },
}


def _original_receipt(root: Path, facts: dict, pinned: dict) -> dict[str, Any]:
    symbol = facts["symbol"]
    receipt = json.loads((root / pinned["receipt_path"]).read_text("utf-8"))
    if not isinstance(receipt, dict):
        raise AlphaContractError(f"P009 source receipt invalid for {symbol}")
    unsigned = copy.deepcopy(receipt)
    sig = unsigned.pop("receipt_sha256", None)
    if sig != pinned["receipt_sha256"] or digest(unsigned) != sig:
        raise AlphaContractError(f"P009 original {symbol} receipt hash changed")
    expected_path = (
        f"research/hg009/p008-originals/{symbol}/"
        f"{pinned['raw_sha256']}.html.gz"
    )
    if (
        receipt.get("symbol") != symbol
        or receipt.get("isin") != facts["isin"]
        or receipt.get("source_url") != facts["original_url"]
        or receipt.get("original_exchange_url") != facts["original_url"]
        or receipt.get("state") != "ORIGINAL_RAW_ARCHIVED_WITH_VERIFIED_ROWS"
        or receipt.get("raw_sha256") != pinned["raw_sha256"]
        or receipt.get("http_status") != 200
        or receipt.get("original_raw_repo_path") != expected_path
        or receipt.get("financial_values_are_normalized_owner_fcf") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError(f"P009 original {symbol} receipt identity drift")
    try:
        original_raw = gzip.decompress((root / expected_path).read_bytes())
    except (FileNotFoundError, OSError) as exc:
        raise AlphaContractError(f"P009 archived original {symbol} is unreadable") from exc
    if (
        hashlib.sha256(original_raw).hexdigest() != pinned["raw_sha256"]
        or receipt.get("raw_byte_count") != len(original_raw)
    ):
        raise AlphaContractError(f"P009 original {symbol} raw file hash changed")
    reverified = validate_issuer_html(
        original_raw,
        facts,
        observed_at_utc=receipt["captured_at_utc"],
    )
    if (
        reverified["raw_sha256"] != pinned["raw_sha256"]
        or reverified["validation_state"]
        != "ORIGINAL_NSE_FY26_CASHFLOW_SOURCE_BYTES_ROW_MATCHED"
    ):
        raise AlphaContractError(f"P009 source {symbol} did not replay exact rows")
    return {
        "symbol": symbol,
        "isin": facts["isin"],
        "original_exchange_url": receipt["original_exchange_url"],
        "original_fy26_period": facts["period_end"],
        "reported_accounting_basis": facts["reporting_basis"],
        "first_verified_capture_utc": receipt["captured_at_utc"],
        "original_nse_sha256": pinned["raw_sha256"],
        "first_verified_receipt_sha256": sig,
        "source_receipt_path": pinned["receipt_path"],
        "original_archive_path": expected_path,
        "original_uncompressed_byte_count": len(original_raw),
        "source_field_names_replayed": sorted(EXPECTED_ROWS),
        "source_field_count_replayed": len(EXPECTED_ROWS),
        "source_review_state": "ORIGINAL_FY26_NSE_NINE_ROW_VALUES_REPLAYED",
        "field_values_are_not_normalized_owner_cash": True,
        "parent_cash_minorities_and_dilution_not_fully_reconciled": True,
        "capital_allowed": False,
    }


def build_original_attestation(root: Path) -> dict[str, Any]:
    frozen = load_sources(root)[0]["new_fy26"]
    rows = {row["symbol"]: row for row in frozen["numeric_facts"]}
    if set(rows) != set(SOURCES) or len(rows) != 3:
        raise AlphaContractError("P009 frozen original three NSE FY26 sources changed")
    verified = [
        _original_receipt(root, rows[symbol], SOURCES[symbol])
        for symbol in sorted(rows)
    ]
    if any(x["source_field_count_replayed"] != 9 for x in verified):
        raise AlphaContractError("P009 original NSE cashflow evidence cells missing")
    result: dict[str, Any] = {
        "schema_version": 1,
        "attestation_id": ATTESTATION_ID,
        "source_cutoff_and_initial_capture_day": "2026-10-14",
        "frozen_original_fy26_issuers_count": 3,
        "original_statement_financial_fields_replayed_count": 27,
        "original_nse_filing_sources": verified,
        "historical_fiscal_period_end": "2026-03-31",
        "issuer_byte_attestation_successful_count": len(verified),
        "reviewed_original_fy26_files_not_current_share_capital": True,
        "all_ten_original_issuer_source_proofs_complete": False,
        "normalized_parent_owner_fcf_valuations_complete": 0,
        "risk_adjusted_expected_return_valuations_complete": 0,
        "paper_investment_eligible_count": 0,
        "original_price_per_share_predictions_created": False,
        "live_capital_allowed": False,
    }
    result["attestation_sha256"] = digest(result)
    return result


def validate_original_attestation(packet: dict, *, root: Path) -> None:
    unsigned = copy.deepcopy(packet)
    sha = unsigned.pop("attestation_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("P009 original issuer attestation SHA changed")
    if packet != build_original_attestation(root):
        raise AlphaContractError("P009 original signed issuer-source proof not replayable")
