"""P031: verified NSE four-tier issuer industry source, not posthoc alpha."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p031_industry import (
    ORIGINAL_ENTRY_DATE,
    build_coverage_status,
    classify_raw_quote,
    frozen_members,
    load_verified_receipts,
    record_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
SYMBOL = "ABCAPITAL"
ISIN = "INE674K01013"
OBSERVED = "2026-10-21T09:20:15+00:00"


def _legacy(*, isin: str = ISIN) -> bytes:
    return json.dumps({
        "info": {"symbol": SYMBOL, "isin": isin},
        "metadata": {"symbol": SYMBOL, "isin": isin, "series": "EQ"},
        "industryInfo": {
            "macro": "Financial Services",
            "sector": "Financial Services",
            "industry": "Non Banking Financial Company",
            "basicIndustry": "Diversified Financial Services",
        },
        "priceInfo": {"lastPrice": 99999999},
    }).encode()


def _modern(*, isin: str = ISIN) -> bytes:
    return json.dumps({
        "equityResponse": [{
            "metaData": {
                "symbol": SYMBOL,
                "isinCode": isin,
                "series": "EQ",
            },
            "secInfo": {
                "macro": "Financial Services",
                "sector": "Financial Services",
                "industryInfo": "Non Banking Financial Company",
                "basicIndustry": "Diversified Financial Services",
            },
            "tradeInfo": {"totalMarketCap": 999999999999},
        }],
    }).encode()


def test_original_300_members_are_immutable_and_no_new_selected_names():
    members = frozen_members(ROOT)
    assert len(members) == 300
    assert members[SYMBOL] == (ISIN, "SELECTED")
    assert len({isin for isin, arm in members.values()}) == 300
    assert ORIGINAL_ENTRY_DATE == "2026-10-15"


@pytest.mark.parametrize("raw", [_legacy(), _modern()])
def test_legacy_and_nextgen_NSE_quote_same_four_levels_without_stock_price(raw):
    result = classify_raw_quote(
        raw, symbol=SYMBOL, isin=ISIN, captured_at_utc=OBSERVED,
    )
    assert result["symbol"] == SYMBOL
    assert result["isin"] == ISIN
    assert result["original_NSE_four_tier_industry"] == {
        "macro": "Financial Services",
        "sector": "Financial Services",
        "industry": "Non Banking Financial Company",
        "basicIndustry": "Diversified Financial Services",
    }
    assert result["captured_at_utc"] == OBSERVED
    assert "99999999" not in json.dumps(result)
    assert result["original_oct15_sector_feature_repaired"] is False
    assert result["later_industry_membership_is_not_proof_of_earlier_state"]
    assert result["live_capital_allowed"] is False


@pytest.mark.parametrize("raw", [_legacy(isin="INE000000009"), _modern(isin="INE000000009")])
def test_wrong_ISIN_fails_even_for_same_original_NSE_symbol(raw):
    with pytest.raises(AlphaContractError, match="ISIN mismatch"):
        classify_raw_quote(
            raw, symbol=SYMBOL, isin=ISIN, captured_at_utc=OBSERVED,
        )


def test_pre_method_timestamp_or_incomplete_four_tier_blocks():
    data = json.loads(_modern())
    data["equityResponse"][0]["secInfo"]["basicIndustry"] = ""
    with pytest.raises(AlphaContractError, match="four-tier"):
        classify_raw_quote(
            json.dumps(data).encode(),
            symbol=SYMBOL, isin=ISIN, captured_at_utc=OBSERVED,
        )
    with pytest.raises(AlphaContractError, match="before method"):
        classify_raw_quote(
            _legacy(), symbol=SYMBOL, isin=ISIN,
            captured_at_utc="2026-10-14T12:00:00+00:00",
        )
    with pytest.raises(AlphaContractError, match="lacks offset"):
        classify_raw_quote(
            _modern(), symbol=SYMBOL, isin=ISIN,
            captured_at_utc="2026-10-21T10:01:05",
        )


def test_verified_original_gzip_replay_and_tamper_detection(tmp_path: Path):
    raw = _modern()
    item = {
        **classify_raw_quote(
            raw, symbol=SYMBOL, isin=ISIN, captured_at_utc=OBSERVED,
        ),
        "state": "VERIFIED_FOUR_TIER_NSE_EQ",
        "http_status": 200,
    }
    path = record_receipt(tmp_path, item, raw=raw)
    assert path.exists()
    assert str(path.relative_to(tmp_path)).startswith(
        "research/hg009/p031-industry/receipts/2026-10-21/"
    )
    members = {SYMBOL: (ISIN, "SELECTED")}
    verified, failures = load_verified_receipts(tmp_path, members)
    assert not failures
    assert verified[SYMBOL]["receipt_sha256"]
    assert verified[SYMBOL]["original_NSE_four_tier_industry"]["sector"] == (
        "Financial Services"
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["receipt_sha256"] == digest({
        k: v for k, v in record.items() if k != "receipt_sha256"
    })
    source_path = tmp_path / record["original_raw_repo_path"]
    source_path.write_bytes(b"not the signed compressed NSE source")
    with pytest.raises(AlphaContractError, match="gzip invalid"):
        load_verified_receipts(tmp_path, members)


def test_failed_source_does_not_become_verified_sector(tmp_path: Path):
    bad = {
        "symbol": SYMBOL, "isin": ISIN,
        "captured_at_utc": OBSERVED,
        "state": "BLOCKED_NSE_ACCESS_OR_RATE_LIMIT",
        "source_raw_sha256": None,
        "live_capital_allowed": False,
    }
    path = record_receipt(tmp_path, bad, raw=None)
    good, failures = load_verified_receipts(
        tmp_path, {SYMBOL: (ISIN, "SELECTED")}
    )
    assert not good
    assert failures[SYMBOL]["BLOCKED_NSE_ACCESS_OR_RATE_LIMIT"] == 1
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["state"] = "VERIFIED_FOUR_TIER_NSE_EQ"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="receipt was modified"):
        load_verified_receipts(tmp_path, {SYMBOL: (ISIN, "SELECTED")})


def test_zero_or_partial_coverage_cannot_register_next_alpha_cohort():
    current = build_coverage_status(ROOT)
    assert current["audit_id"].startswith("HG009-P031")
    assert current["full_market_company_count"] == 300
    assert current["no_original_Oct15_H1_alpha_ranking_rewritten"]
    assert current["historical_Oct15_sector_regression_eligible"] is False
    assert current["another_independent_new_cohort_registered"] is False
    assert current["sector_and_size_beta_cashflow_causal_alpha_ready"] is False
    assert current["live_capital_allowed"] is False
    assert current["verified_original_NSE_issuer_four_tier_count"] <= 300


def test_direct_offline_CLI_replays_source_without_network_or_writes():
    result = subprocess.run(
        [sys.executable, "scripts/capture_hg009_p031_industry.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    answer = json.loads(result.stdout)
    assert answer["state"] == "REPLAY_ONLY"
    assert answer["status"]["live_capital_allowed"] is False
    assert answer["status"]["historical_Oct15_sector_regression_eligible"] is False
    assert not answer["attempted"]
