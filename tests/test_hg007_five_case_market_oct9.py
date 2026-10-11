from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_five_case_market_oct9 import (
    EXPECTED_NAMES,
    PINNED_ORIGINAL_NSE_SHA256,
    SOURCE_URL,
    build_five_case_price_context,
    load_frozen_five_sources,
    validate_five_case_price_context,
)
from scripts import acquire_hg007_five_case_oct9 as downloader

FIXTURE_ISINS = {
    "ANANTRAJ": "INE0000T0001",
    "DEVX": "INE0000T0002",
    "INOXGREEN": "INE510W01014",
    "NPST": "INE0000T0004",
    "SAMBHV": "INE0000T0005",
}


def _udiff(
    *,
    missing: str | None = None,
    extra_duplicate: str | None = None,
    bad_date: bool = False,
) -> bytes:
    output = io.StringIO()
    fields = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
        "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
        "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    actual_close = {
        "ANANTRAJ": 510.0,
        "DEVX": 33.0,
        "INOXGREEN": 128.92,
        "NPST": 1500.0,
        "SAMBHV": 160.41,
    }
    for sym in EXPECTED_NAMES:
        if sym == missing:
            continue
        rows = 2 if sym == extra_duplicate else 1
        for _ in range(rows):
            price = actual_close[sym]
            writer.writerow({
                "TradDt": "2026-10-08" if bad_date else "2026-10-09",
                "Sgmt": "CM", "Src": "NSE", "FinInstrmTp": "STK",
                "ISIN": FIXTURE_ISINS[sym],
                "TckrSymb": sym, "SctySrs": "EQ",
                "OpnPric": str(price),
                "HghPric": str(price + 1),
                "LwPric": str(price - 1),
                "ClsPric": str(price),
                "PrvsClsgPric": str(price + 2),
                "TtlTradgVol": "145000", "TtlTrfVal": str(145000 * price),
                "TtlNbOfTxsExctd": "3400",
            })
    output_zip = io.BytesIO()
    with zipfile.ZipFile(output_zip, "w") as archive:
        archive.writestr("BhavCopy_NSE_CM_0_0_0_20261009_F_0000.csv", output.getvalue())
    return output_zip.getvalue()


def _inputs(raw: bytes):
    hg005, ss002, p033, provenance = load_frozen_five_sources(Path("."))
    adapted = deepcopy(ss002)
    adapted["official_bhavcopy_sha256"] = hashlib.sha256(raw).hexdigest()
    return hg005, adapted, p033, provenance


def _built(raw: bytes) -> dict:
    h, s, p, provenance = _inputs(raw)
    return build_five_case_price_context(
        h, s, p,
        udiff_raw=raw,
        captured_at_utc="2026-10-10T11:00:00Z",
        provenance=provenance,
    )


def test_original_sources_are_pinned_and_selection_not_changed() -> None:
    h, s, p, provenance = load_frozen_five_sources(Path("."))
    assert tuple(h["symbols"]) == EXPECTED_NAMES
    assert [row["symbol"] for row in p["casework"]] == list(EXPECTED_NAMES)
    assert s["official_bhavcopy_sha256"] == PINNED_ORIGINAL_NSE_SHA256
    assert len(provenance) == 3


def test_five_rows_are_source_only_and_original_two_overlap_exact_p007() -> None:
    raw = _udiff()
    report = _built(raw)
    assert report["five_case_count"] == 5
    assert [r["symbol"] for r in report["price_context_rows"]] == list(EXPECTED_NAMES)
    by_symbol = {row["symbol"]: row for row in report["price_context_rows"]}
    assert by_symbol["INOXGREEN"]["official_oct9_close_inr"] == 128.92
    assert by_symbol["SAMBHV"]["official_oct9_close_inr"] == 160.41
    assert by_symbol["INOXGREEN"]["frozen_hg005_oct1_close_inr_not_current"] == 159
    assert by_symbol["INOXGREEN"][
        "oct1_to_oct9_unadjusted_price_reference_change_pct"
    ] == pytest.approx(-18.918238993710702)
    assert by_symbol["DEVX"]["official_oct9_total_traded_shares"] == 145000
    assert all(row["company_current_fully_diluted_share_count_verified"] is False
               for row in report["price_context_rows"])
    assert all(row["independent_share_identity_review_complete"] is False
               for row in report["price_context_rows"])
    assert report["expected_returns_calculated"] is False
    assert report["stock_current_fd_capital_approved"] is False
    assert report["investment_recommendations_created"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False


def test_mismatched_source_sha_and_missing_symbol_fail_closed() -> None:
    raw = _udiff()
    h, s, p, provenance = _inputs(raw)
    with pytest.raises(ValueError, match="differ from source-sealed"):
        build_five_case_price_context(
            h, s, p, udiff_raw=raw + b"altered",
            captured_at_utc="2026-10-10T11:00:00Z",
            provenance=provenance,
        )
    raw_missing = _udiff(missing="NPST")
    h, s, p, provenance = _inputs(raw_missing)
    with pytest.raises(ValueError, match="missing original five-case symbols"):
        build_five_case_price_context(
            h, s, p, udiff_raw=raw_missing,
            captured_at_utc="2026-10-10T11:00:00Z",
            provenance=provenance,
        )


def test_inconsistent_p007_overlap_or_duplicate_source_rejected() -> None:
    raw = _udiff()
    h, s, p, provenance = _inputs(raw)
    s["case_prices_inr"]["INOXGREEN"] = 120.0
    with pytest.raises(ValueError, match="official close differs"):
        build_five_case_price_context(
            h, s, p, udiff_raw=raw,
            captured_at_utc="2026-10-10T11:00:00Z",
            provenance=provenance,
        )
    dup = _udiff(extra_duplicate="DEVX")
    h, s, p, provenance = _inputs(dup)
    with pytest.raises(ValueError, match="duplicate UDiFF EQ identity"):
        build_five_case_price_context(
            h, s, p, udiff_raw=dup,
            captured_at_utc="2026-10-10T11:00:00Z",
            provenance=provenance,
        )


def test_never_observe_future_or_pretend_a_test_zip_is_original_nse() -> None:
    raw = _udiff()
    h, s, p, provenance = _inputs(raw)
    with pytest.raises(ValueError, match="cannot predate session close"):
        build_five_case_price_context(
            h, s, p, udiff_raw=raw,
            captured_at_utc="2026-10-09T09:59:59Z",
            provenance=provenance,
        )
    with pytest.raises(ValueError, match="not a source-approved"):
        validate_five_case_price_context(_built(raw))


def test_official_download_access_controls_and_exact_source(monkeypatch) -> None:
    calls = []

    class Blocked:
        status_code = 403
        url = SOURCE_URL
        content = b"Forbidden"

    def fetch(url: str, **kwargs):
        calls.append((url, kwargs))
        return Blocked()

    monkeypatch.setattr(downloader.requests, "get", fetch)
    receipt, raw = downloader.acquire(timeout=7)
    assert receipt["status"] == "ACCESS_BLOCKED"
    assert raw is None
    assert receipt["source_sha256"] is None
    assert receipt["research_price_context_published"] is False
    assert len(calls) == 1
    assert calls[0][0] == SOURCE_URL
    assert calls[0][1]["allow_redirects"] is False


def test_official_source_digest_mismatch_keeps_price_context_closed(monkeypatch) -> None:
    sample = _udiff()

    class WrongOriginal:
        status_code = 200
        url = SOURCE_URL
        content = sample

    monkeypatch.setattr(
        downloader.requests, "get", lambda url, **kwargs: WrongOriginal()
    )
    receipt, raw = downloader.acquire(timeout=7)
    assert receipt["status"] == "SOURCE_DIGEST_MISMATCH"
    assert raw is None
    assert receipt["source_sha256"] == hashlib.sha256(sample).hexdigest()
    assert receipt["research_price_context_published"] is False
    assert receipt["live_capital_allowed"] is False


def test_output_flags_cannot_be_promoted_without_market_source() -> None:
    report = _built(_udiff())
    # Strong validator accepts only the exact source hash and no capital flags.
    report["source_original_zip_sha256"] = PINNED_ORIGINAL_NSE_SHA256
    report["live_capital_allowed"] = True
    with pytest.raises(ValueError, match="may not authorize"):
        validate_five_case_price_context(report)
