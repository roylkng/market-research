"""P033 validates individually proven official NSE rows, not guessed sectors."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p032_totalmarket import _read_official_csv
from marketlab.hg009_p033_rowwise import (
    SOURCE,
    analyze,
    archive,
    parse_nse_totalmarket_rows,
    replay_all,
)

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = "2026-10-21T11:40:00+00:00"


def _source(*, bad: int = 0, mismatch: bool = False, duplicate: bool = False):
    out = io.StringIO()
    cols = ["Company Name", "Industry", "Symbol", "Series", "ISIN Code"]
    writer = csv.DictWriter(out, fieldnames=cols)
    writer.writeheader()
    for i in range(749):
        writer.writerow({
            "Company Name": f"Synthetic NSE index issuer {i}",
            "Industry": "" if i < bad else "Synthetic Industry",
            "Symbol": f"TEST{i:04d}",
            "Series": "EQ",
            "ISIN Code": f"INE{i:09d}",
        })
    writer.writerow({
        "Company Name": "Synthetic ABCAPITAL test issuer",
        "Industry": "Financial Services",
        "Symbol": "ABCAPITAL",
        "Series": "EQ",
        "ISIN Code": "INE111111111" if mismatch else "INE674K01013",
    })
    if duplicate:
        writer.writerow({
            "Company Name": "Duplicate ABCAPITAL",
            "Industry": "Financial Services",
            "Symbol": "ABCAPITAL",
            "Series": "EQ",
            "ISIN Code": "INE674K01013",
        })
    return out.getvalue().encode()


def test_one_bad_constituent_does_not_erase_749_clean_original_rows():
    data = _source(bad=1)
    with pytest.raises(AlphaContractError, match="invalid"):
        _read_official_csv(data)
    parsed = parse_nse_totalmarket_rows(data)
    assert parsed["total_official_constituent_rows"] == 750
    assert parsed["valid_unique_original_EQ_rows"] == 749
    assert parsed["invalid_or_ambiguous_rows"] == 1
    assert parsed["rejected_reason_counts"] == {"INVALID_INDUSTRY": 1}
    assert parsed["verified"]["ABCAPITAL"] == {
        "symbol": "ABCAPITAL",
        "isin": "INE674K01013",
        "industry": "Financial Services",
        "series": "EQ",
    }


def test_same_symbol_without_same_isin_remains_unclassified():
    report = analyze(
        root=ROOT, raw=_source(bad=1, mismatch=True),
        first_observed_at_utc=OBSERVED,
    )
    company = next(x for x in report["frozen_300_company_industry_rows"]
                   if x["symbol"] == "ABCAPITAL")
    assert company["official_industry_if_verified"] is None
    assert company["classification"] == "SOURCE_NOT_AVAILABLE_OR_IDENTITY_CONFLICT"
    assert report["frozen_300_exact_symbol_isin_matches"] == 0
    assert report["new_independent_trial_registration_ready"] is False


def test_exact_match_uses_source_date_only_for_future_trial():
    report = analyze(
        root=ROOT, raw=_source(bad=1), first_observed_at_utc=OBSERVED
    )
    company = next(x for x in report["frozen_300_company_industry_rows"]
                   if x["symbol"] == "ABCAPITAL")
    assert company["official_industry_if_verified"] == "Financial Services"
    assert company["first_verified_at_utc"] == OBSERVED
    assert company["was_proven_before_original_oct15_entry"] is False
    assert report["frozen_300_exact_symbol_isin_matches"] == 1
    assert report["coverage_by_arm"]["SELECTED"]["verified"] == 1
    assert report["coverage_by_arm"]["ZERO_LANE"]["verified"] == 0
    assert report["one_tier_industry_source_coverage_ready"] is False
    assert report["new_independent_trial_registration_ready"] is False
    assert report["live_capital_allowed"] is False


def test_duplicate_symbol_is_ambiguous_and_not_accepted():
    parsed = parse_nse_totalmarket_rows(_source(duplicate=True))
    assert parsed["total_official_constituent_rows"] == 751
    assert parsed["invalid_or_ambiguous_rows"] == 2
    assert "ABCAPITAL" not in parsed["verified"]
    assert parsed["rejected_reason_counts"] == {
        "DUPLICATE_EQ_SYMBOL_AMBIGUOUS": 2
    }
    assert len(parsed["verified"]) == 749


def test_too_many_invalid_or_bad_csv_schema_fail_closed():
    with pytest.raises(AlphaContractError, match="too incomplete"):
        parse_nse_totalmarket_rows(_source(bad=21))
    with pytest.raises(AlphaContractError, match="source bytes"):
        parse_nse_totalmarket_rows(b"<html>HTTP 403</html>")
    with pytest.raises(AlphaContractError, match="before method"):
        analyze(root=ROOT, raw=_source(), first_observed_at_utc="2026-10-20T12:00:00Z")


def test_actual_original_source_receipt_bytes_replay_and_tamper(tmp_path: Path):
    (tmp_path / "research/hg009").mkdir(parents=True)
    for name in (
        "original-hg001-d001-router-20261005.json.gz",
        "hg009-d001-100-experimental-companies-v1.json",
        "hg009-p001-matched-300-company-controls-v1.json",
    ):
        src = ROOT / "research/hg009" / name
        dst = tmp_path / "research/hg009" / name
        dst.write_bytes(src.read_bytes())
    raw = _source(bad=1)
    original = archive(
        tmp_path, raw=raw, first_observed_at_utc=OBSERVED,
    )
    assert original["source_original_sha256"] == hashlib.sha256(raw).hexdigest()
    assert original["source_rejected_rows"] == 1
    assert original["original_source_repo_path"].startswith(
        "research/hg009/p033-totalmarket-rowwise/originals/sha256/"
    )
    assert replay_all(tmp_path)["source_replays_verified"] == 1
    path = tmp_path / original["original_source_repo_path"]
    assert gzip.decompress(path.read_bytes()) == raw
    path.write_bytes(gzip.compress(raw + b"tampered", mtime=0))
    with pytest.raises(AlphaContractError, match="replay differs"):
        replay_all(tmp_path)


def test_failed_original_source_is_recorded_without_any_sector(tmp_path: Path, monkeypatch):
    from scripts import capture_hg009_p033_rowwise as runner

    invalid = b"source returned an NSE access error, not a company industry file"

    class FakeClient:
        count = 0

        def __init__(self, **kwargs):
            pass

        def archive_bytes(self, url):
            assert url == SOURCE
            FakeClient.count += 1
            return invalid

    monkeypatch.setattr(runner, "NSEClient", FakeClient)
    result = runner.run(tmp_path)
    assert result["state"] == "ORIGINAL_NSE_SOURCE_UNVERIFIED"
    assert result["industry_rows_admitted"] == 0
    assert result["raw_sha256"] == hashlib.sha256(invalid).hexdigest()
    assert result["live_capital_allowed"] is False
    assert runner.run(tmp_path)["state"] == "ONE_SOURCE_PROBE_ALREADY_RECORDED_TODAY"
    assert FakeClient.count == 1
    assert runner.run(tmp_path, check=True)["replayed_failure_receipts"] == 1


def test_standalone_offline_verifier_does_not_make_nse_request():
    run = subprocess.run(
        [sys.executable, "scripts/capture_hg009_p033_rowwise.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    status = json.loads(run.stdout)
    assert status["live_capital_allowed"] is False
    assert status["new_cohort_activated"] is False
