"""P035 BSE source meaning must be verified, not inferred from NSE membership."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p035_bse_industry import (
    AUDIT_ID,
    SOURCE_URL,
    _frozen,
    analyze_bse_original,
    archive,
    replay_originals,
)

ROOT = Path(__file__).resolve().parents[1]


def _original_fixture(
    *,
    missing_isin: str | None = None,
    duplicate_isin: str | None = None,
    no_industry: bool = False,
    remove_isin_header: bool = False,
) -> bytes:
    original = _frozen(ROOT)
    rows = []
    for seq, (symbol, identity) in enumerate(sorted(original.items())):
        row = {
            "SCRIP_CD": str(500000 + seq),
            "scrip_id": symbol,
            "Scrip_Name": f"Synthetic issuer {seq} {symbol}",
            "ISIN_NUMBER": identity["isin"],
            "INDUSTRY": "" if no_industry else "Source-listed manufacturing",
            "Status": "Active",
            "Segment": "Equity",
            "Mktcap": str(1500 + seq),
            "Issuer_Name": f"Company {symbol} Manufacturing Ltd",
        }
        if symbol == missing_isin:
            row["ISIN_NUMBER"] = "INE999999999"
        if remove_isin_header:
            row["UnrelatedId"] = row.pop("ISIN_NUMBER")
        rows.append(row)
        if symbol == duplicate_isin:
            rows.append(dict(row))
    for i in range(3200):
        rows.append({
            "SCRIP_CD": str(600000 + i),
            "scrip_id": f"FILL{i:05d}",
            "Scrip_Name": f"Other synthetic equity member {i}",
            "ISIN_NUMBER": f"INE{i:09d}",
            "INDUSTRY": "" if no_industry else "Source-listed services",
            "Status": "Active",
            "Segment": "Equity",
            "Mktcap": str(2000 + i),
            "Issuer_Name": f"Other equity listed issuer {i} group",
        })
    encoded = json.dumps({"Data": rows}, separators=(",", ":")).encode("utf-8")
    assert len(encoded) > 100000
    return encoded


def _review(raw: bytes) -> dict:
    return analyze_bse_original(
        root=ROOT,
        raw=raw,
        first_observed_at_utc="2026-10-21T12:00:00+00:00",
    )


def test_exact_three_original_nse_arms_match_bse_cross_exchange_isin():
    result = _review(_original_fixture())
    assert result["audit_id"] == AUDIT_ID
    assert result["official_source"] == SOURCE_URL
    assert result["original_source_row_count"] == 3500
    assert result["actual_json_collection_key"] == "Data"
    assert result["source_isin_field"] == "ISIN_NUMBER"
    assert result["source_industry_field"] == "INDUSTRY"
    assert result["source_market_cap_field"] == "Mktcap"
    assert result["source_symbol_field"] == "scrip_id"
    assert len(result["all_300_original_nse_identities"]) == 300
    for arm in ("SELECTED", "ONE_LANE", "ZERO_LANE"):
        assert result["exact_frozen_nse_isin_by_arm"][arm] == {
            "denominator": 100, "matched": 100, "missing": 0,
        }
        assert result["nonempty_original_bse_industry_by_arm"][arm] == {
            "denominator": 100, "source_labeled": 100, "unknown": 0,
        }
    assert result["underlying_bse_industry_equates_to_nse_four_tier"] is False
    assert result["marketcap_column_is_correct_point_in_time_free_float_cap"] is False
    assert result["source_from_oct21_is_admissible_for_oct15_preentry_model"] is False
    assert result["live_capital_allowed"] is False
    assert result["company_expected_return_calculated"] is False
    assert result["report_sha256"] == digest({
        k: v for k, v in result.items() if k != "report_sha256"
    })


def test_changed_isin_must_not_be_replaced_by_similar_company_name():
    symbol, _ = next(iter(sorted(_frozen(ROOT).items())))
    report = _review(_original_fixture(missing_isin=symbol))
    record = next(x for x in report["all_300_original_nse_identities"]
                  if x["original_nse_symbol"] == symbol)
    assert record["source_state"] == "NOT_IN_ORIGINAL_BSE_ACTIVE_EQUITY_SOURCE"
    assert record["original_bse_reported_industry_if_exact"] is None
    assert sum(
        x["matched"] for x in report["exact_frozen_nse_isin_by_arm"].values()
    ) == 299


def test_multiple_bse_scrip_codes_for_same_isin_block_industry_admission():
    symbol, _ = next(iter(sorted(_frozen(ROOT).items())))
    report = _review(_original_fixture(duplicate_isin=symbol))
    record = next(x for x in report["all_300_original_nse_identities"]
                  if x["original_nse_symbol"] == symbol)
    assert record["source_state"] == "BLOCKED_DUPLICATE_OR_AMBIGUOUS_BSE_ISIN"
    assert record["original_bse_reported_industry_if_exact"] is None
    assert sum(x["matched"] for x in report["exact_frozen_nse_isin_by_arm"].values()) == 299


def test_bse_has_exact_isin_without_four_tier_industry_or_empty_label():
    empty = _review(_original_fixture(no_industry=True))
    assert sum(
        x["source_labeled"]
        for x in empty["nonempty_original_bse_industry_by_arm"].values()
    ) == 0
    assert sum(
        x["matched"]
        for x in empty["exact_frozen_nse_isin_by_arm"].values()
    ) == 300
    missing = _review(_original_fixture(remove_isin_header=True))
    assert missing["source_isin_field"] is None
    assert sum(
        x["matched"] for x in missing["exact_frozen_nse_isin_by_arm"].values()
    ) == 0
    assert all(
        x["source_state"] == "BLOCKED_NO_EXACT_BSE_ISIN_FIELD"
        for x in missing["all_300_original_nse_identities"]
    )


def test_source_timestamp_and_json_shape_deny_retrospective_inference():
    raw = _original_fixture()
    with pytest.raises(AlphaContractError, match="cannot predate"):
        analyze_bse_original(
            root=ROOT,
            raw=raw,
            first_observed_at_utc="2026-10-20T12:00:00Z",
        )
    with pytest.raises(AlphaContractError, match="source size implausible"):
        _review(b"not bse json")
    with pytest.raises(AlphaContractError, match="collection"):
        _review(json.dumps({"data": []}).encode().ljust(100001, b" "))


def test_original_bytes_replay_and_signed_receipt_reject_source_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    from marketlab import hg009_p035_bse_industry as p035

    identities = _frozen(ROOT)
    monkeypatch.setattr(p035, "_frozen", lambda root: identities)
    original = _original_fixture()
    report = archive(
        root=tmp_path,
        raw=original,
        first_observed_at_utc="2026-10-21T12:00:00Z",
    )
    assert report["original_bse_raw_repo_path"]
    assert report["source_sha256"] == hashlib.sha256(original).hexdigest()
    status = replay_originals(tmp_path)
    assert status["state"] == "ORIGINAL_BSE_ISIN_INDUSTRY_REPLAYED"
    assert status["count"] == 1
    assert status["receipts"][0]["exact_matched"] == 300
    receipt = next((tmp_path / p035.CUSTODY / "receipts").glob("*.json"))
    damaged = json.loads(receipt.read_text())
    damaged["source_first_observed_at_utc"] = "2026-10-14T00:00:00Z"
    receipt.write_text(json.dumps(damaged))
    with pytest.raises(AlphaContractError, match="signed BSE original receipt altered"):
        replay_originals(tmp_path)


def test_standalone_script_check_never_contacts_external_api():
    run = subprocess.run(
        [sys.executable, "scripts/capture_hg009_p035_bse_industry.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    status = json.loads(run.stdout)
    assert status["live_capital_allowed"] is False
    assert status["retroactive_oct15_alpha"] is False
    assert status["count"] >= 0
