"""Check original Oct14 NSE futures source is not a return signal."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p029_fo_exposure import (
    FO_BLOB_PATH,
    build_preentry_fo_exposure,
    materialize,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p029-preentry-fo-microstructure-v1.json"


def test_preentry_futures_report_does_not_certify_cas_or_alpha():
    row = materialize(ROOT)
    assert row["original_source_session_date"] == "2026-10-14"
    assert row["first_original_cohort_entry_date"] == "2026-10-15"
    assert row["original_accepted_FO_stock_contract_rows"] == 635
    assert row["original_FO_stock_underlying_ticker_count"] >= 150
    assert row["fixed_company_count"] == 300
    assert len(row["original_company_exposure"]) == 300
    assert row["original_source_was_captured_before_cohort_entry"] is True
    assert row["prohibited_as_posthoc_original_H1_feature_or_confirmation"] is True
    assert row["no_postentry_market_price_source_read"] is True
    assert row["live_capital_allowed"] is False
    for arm, counts in row["original_group_exposure"].items():
        assert arm in {"SELECTED", "ONE_LANE", "ZERO_LANE"}
        assert counts["fixed_original_company_count"] == 100
        assert counts["oct14_futures_ticker_seen_count"] + (
            counts["oct14_futures_ticker_not_seen_count"]
        ) == 100
        assert counts["stock_level_cas_eligibility_count_independently_verified"] == 0
    for issuer in row["original_company_exposure"]:
        assert issuer["closing_auction_stock_eligibility_proven"] is False
        assert issuer["source_FO_ticker_isin_independently_verified"] is False
        assert issuer["market_return_or_trade_inferred"] is False


def test_original_byte_change_or_source_receipt_change_fails_closed():
    from marketlab.hg009_controls import load_hg009_inputs
    from marketlab.hg009_p029_fo_exposure import CONTROLS_PATH, SOURCE_LEDGER

    source, selected = load_hg009_inputs(ROOT)
    controls = json.loads((ROOT / CONTROLS_PATH).read_text("utf-8"))
    ledger = json.loads((ROOT / SOURCE_LEDGER).read_text("utf-8"))
    raw = (ROOT / FO_BLOB_PATH).read_bytes()
    args = dict(original=source, selected=selected, controls=controls)
    with pytest.raises(AlphaContractError, match="bytes SHA mismatch"):
        build_preentry_fo_exposure(
            **args, source_ledger=ledger, original_fo_raw=raw + b"altered",
        )
    changed = copy.deepcopy(ledger)
    receipt = next(x for x in changed["attempts"] if x["target_session_date"] == "2026-10-14")
    receipt["captured_at_utc"] = "2026-10-15T09:00:00Z"
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        build_preentry_fo_exposure(
            **args, source_ledger=changed, original_fo_raw=raw,
        )


def test_sealed_original_source_and_standalone_cli():
    row = materialize(ROOT)
    assert row == json.loads(OUTPUT.read_text("utf-8"))
    validate(row, ROOT)
    result = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p029.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["state"] == "VERIFIED"
    assert parsed["actual_CAS_eligible_count_verified"] == 0
