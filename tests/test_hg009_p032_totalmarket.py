"""P032: NSE index CSV industry evidence is partial, never legacy alpha."""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p032_totalmarket import (
    SOURCE_URL,
    _read_official_csv,
    analyze,
    archive,
    replay_all,
)

ROOT = Path(__file__).resolve().parents[1]
UTC_TIMESTAMP = "2026-10-21T09:45:00+00:00"


def _synthetic_csv(*, invalid_isin: bool = False, missing_sector: bool = False) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=[
            "Company Name", "Industry", "Symbol", "Series", "ISIN Code"
        ],
    )
    writer.writeheader()
    for i in range(749):
        writer.writerow({
            "Company Name": f"Synthetic Issuer {i}",
            "Industry": "Synthetic Test Industry",
            "Symbol": f"TEST{i:04d}",
            "Series": "EQ",
            "ISIN Code": f"INE{i:09d}",
        })
    writer.writerow({
        "Company Name": "Synthetic ABCAPITAL Source",
        "Industry": "" if missing_sector else "Finance",
        "Symbol": "ABCAPITAL",
        "Series": "EQ",
        "ISIN Code": "INE000000009" if invalid_isin else "INE674K01013",
    })
    return buffer.getvalue().encode("utf-8")


def test_official_index_csv_is_single_level_partial_and_matches_original_ISIN():
    output = analyze(
        root=ROOT,
        original_csv=_synthetic_csv(),
        first_retrieved_at_utc=UTC_TIMESTAMP,
    )
    assert output["index_original_EQ_company_count"] == 750
    assert output["exact_symbol_isin_matches"] == 1
    assert output["per_arm"]["SELECTED"] == {
        "denominator": 100, "exact_matched": 1, "missing": 99,
    }
    assert len(output["details"]) == 300
    selected = next(x for x in output["details"] if x["symbol"] == "ABCAPITAL")
    assert selected["original_NSE_index_industry_if_exact"] == "Finance"
    assert selected["known_before_2026_10_15_open"] is False
    assert selected["four_tier_issuer_industry_verified"] is False
    assert output["source_is_only_NIFTY_TOTAL_MARKET_750_NOT_ALL_LISTINGS"]
    assert output["source_industry_is_single_level_not_four_level"]
    assert output["no_retroactive_oct15_sector_alpha"]
    assert output["live_capital_allowed"] is False
    assert output["source_url"] == SOURCE_URL


def test_symbol_match_wrong_ISIN_is_not_assigned_industry():
    output = analyze(
        root=ROOT,
        original_csv=_synthetic_csv(invalid_isin=True),
        first_retrieved_at_utc=UTC_TIMESTAMP,
    )
    assert output["exact_symbol_isin_matches"] == 0
    item = next(x for x in output["details"] if x["symbol"] == "ABCAPITAL")
    assert item["original_NSE_index_industry_if_exact"] is None


def test_empty_industry_duplicate_and_small_catalog_fail_closed():
    with pytest.raises(AlphaContractError, match="invalid"):
        _read_official_csv(_synthetic_csv(missing_sector=True))
    original = _synthetic_csv().decode("utf-8")
    raw = original + original.splitlines()[-1] + "\n"
    with pytest.raises(AlphaContractError, match="invalid"):
        _read_official_csv(raw.encode())
    with pytest.raises(AlphaContractError, match="size"):
        _read_official_csv(b"Symbol,Series,Industry,ISIN Code\n")


def test_immutable_original_source_replays_without_current_quotes(tmp_path: Path):
    # Link the original frozen 2,319 company source and source-only manifest
    # from repo to temporary sandbox fixture. No live exchange source here.
    (tmp_path / "research/hg009").mkdir(parents=True)
    sources = (
        "original-hg001-d001-router-20261005.json.gz",
        "hg009-d001-100-experimental-companies-v1.json",
        "hg009-p001-matched-300-company-controls-v1.json",
    )
    for name in sources:
        source = ROOT / "research/hg009" / name
        (tmp_path / "research/hg009" / name).write_bytes(source.read_bytes())
    report = archive(
        root=tmp_path, raw=_synthetic_csv(),
        first_retrieved_at_utc=UTC_TIMESTAMP,
    )
    assert report["source_byte_count"] == len(_synthetic_csv())
    status = replay_all(tmp_path)
    assert status["original_evidence_count"] == 1
    assert status["source_evidence"][0]["exact_frozen_matches"] == 1
    assert status["new_independent_cohort_released"] is False
    receipt = next((tmp_path / "research/hg009/p032-totalmarket/receipts").glob("*.json"))
    tampered = json.loads(receipt.read_text("utf-8"))
    tampered["exact_symbol_isin_matches"] = 50
    receipt.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="signed receipt modified"):
        replay_all(tmp_path)


def test_offline_check_never_calls_network():
    run = subprocess.run(
        [sys.executable, "scripts/capture_hg009_p032_totalmarket.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    j = json.loads(run.stdout)
    assert j["live_capital_allowed"] is False
    assert j["new_independent_cohort_released"] is False
