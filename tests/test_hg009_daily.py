"""HG009 independent original-NSE source sharing does not produce fills."""

from __future__ import annotations

import copy
import csv
import io
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.h021_daily_prices import (
    build_daily_source_observation,
    official_market_transport_ready,
)
from marketlab.h021_entry_observation import EXPECTED_SELECTION
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_daily import (
    build_hg009_daily_source_observation,
    validate_hg009_daily_snapshot,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.collect_h021_daily_official import load_frozen_sources
from scripts.verify_hg009_daily import verify_daily_observations

ROOT = Path(__file__).resolve().parents[1]
SESSION = "2026-10-15"
CAPTURE = "2026-10-15T12:00:00Z"
H021_SEALED = "2026-10-15T12:01:00Z"
HG009_SEALED = "2026-10-15T12:02:00Z"
FIELDS = [
    "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb",
    "SctySrs", "OpnPric", "HghPric", "LwPric", "ClsPric",
    "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd",
]


def _inputs():
    router, selected = load_hg009_inputs(ROOT)
    controls = json.loads((
        ROOT / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    intent, universe, calendar = load_frozen_sources()
    return router, selected, controls, intent, universe, calendar


def _fake_market_zip(
    selected: dict,
    controls: dict,
    universe: dict,
    *,
    changed_isin: str | None = None,
    missing_eq: str | None = None,
    duplicate_symbol: str | None = None,
) -> bytes:
    members = {row["symbol"]: row["isin"] for row in universe["members"]}
    frozen = [
        (row["symbol"], row["isin"]) for row in selected["selected"]
    ]
    for arm in ("ONE_LANE", "ZERO_LANE"):
        frozen += [
            (row["symbol"], row["isin"])
            for row in controls["controls"][arm]
        ]
    identities = [(symbol, members[symbol]) for symbol in EXPECTED_SELECTION]
    identities += frozen
    assert len(identities) == 310

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    for idx, (symbol, isin) in enumerate(identities):
        op = 100.0 + idx / 10
        writer.writerow({
            "TradDt": SESSION,
            "Sgmt": "CM",
            "Src": "NSE",
            "FinInstrmTp": "STK",
            "ISIN": "INE111A01019" if symbol == changed_isin else isin,
            "TckrSymb": symbol,
            "SctySrs": "BE" if symbol == missing_eq else "EQ",
            "OpnPric": op,
            "HghPric": op + 2,
            "LwPric": op - 1,
            "ClsPric": op + 1,
            "PrvsClsgPric": op - 0.2,
            "TtlTradgVol": 1000,
            "TtlTrfVal": 1000 * (op + 0.3),
            "TtlNbOfTxsExctd": 100,
        })
    if duplicate_symbol is not None:
        writer.writerow({
            "TradDt": SESSION, "Sgmt": "CM", "Src": "NSE",
            "FinInstrmTp": "STK", "ISIN": "INE222A01019",
            "TckrSymb": duplicate_symbol, "SctySrs": "EQ",
            "OpnPric": 180, "HghPric": 182, "LwPric": 179,
            "ClsPric": 181, "PrvsClsgPric": 179.4,
            "TtlTradgVol": 1000, "TtlTrfVal": 180300,
            "TtlNbOfTxsExctd": 100,
        })
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("BhavCopy_NSE_CM_0_0_0_20261015_F_0000.csv", output.getvalue())
    return buf.getvalue()


def _index() -> bytes:
    return (
        b"Index Name,Index Date,Open Index Value,Closing Index Value\n"
        b"Nifty 500,15-10-2026,23000,23050\n"
    )


def _source(raw: bytes, *, is_index: bool) -> dict:
    return {
        "url": (
            index_snapshot_url(date.fromisoformat(SESSION))
            if is_index else udiff_url(date.fromisoformat(SESSION))
        ),
        "status": "OK",
        "captured_at_utc": CAPTURE,
        "http_status": 200,
        "raw": raw,
        "error": None,
    }


def _build(
    *,
    changed_isin: str | None = None,
    missing_eq: str | None = None,
    duplicate_symbol: str | None = None,
):
    router, selected, controls, intent, universe, calendar = _inputs()
    original = _fake_market_zip(
        selected, controls, universe,
        changed_isin=changed_isin,
        missing_eq=missing_eq,
        duplicate_symbol=duplicate_symbol,
    )
    index = _index()
    h021 = build_daily_source_observation(
        intent, universe, calendar,
        session_date=SESSION,
        udiff_source=_source(original, is_index=False),
        index_source=_source(index, is_index=True),
        recorded_at_utc=H021_SEALED,
    )
    assert official_market_transport_ready(h021)
    kwargs = {
        "h021_observation": h021,
        "original_udiff_zip": original,
        "original_index_csv": index,
        "selected_manifest": selected,
        "controls_manifest": controls,
        "original_router": router,
        "calendar": calendar,
        "recorded_at_utc": HG009_SEALED,
    }
    return kwargs, build_hg009_daily_source_observation(**kwargs)


def test_valid_source_capture_all_three_arms_are_original_exact_300():
    kwargs, report = _build()
    assert kwargs["h021_observation"]["selected_company_count"] == 10
    assert report["date_ist"] == SESSION
    assert report["first_declared_entry_market_session"] == SESSION
    assert len(report["source_identity_rows"]) == 300
    assert report["original_EQ_market_universe_row_count"] == 310
    assert report["source_complete_for_all_300"] is True
    assert report["benchmark"]["basis"] == "PRICE_INDEX_NOT_TOTAL_RETURN"
    assert report["benchmark"]["open"] == 23000
    assert report["benchmark"]["close"] == 23050
    for arm in ("SELECTED", "ONE_LANE", "ZERO_LANE"):
        assert report["arm_coverage"][arm]["declared"] == 100
        assert report["arm_coverage"][arm]["observed_official_eq"] == 100
        assert report["arm_coverage"][arm]["missing_or_changed_identity"] == 0
    assert report["gross_holding_period_returns_calculated"] is False
    assert report["benchmark_excess_returns_calculated"] is False
    assert report["live_capital_allowed"] is False
    assert report["portfolio_eligibility_allowed"] is False
    validate_hg009_daily_snapshot(report)


def test_changed_isin_and_missing_eq_cannot_be_filled_from_other_series():
    _, changed = _build(changed_isin="ANANTRAJ")
    by_symbol = {
        row["symbol"]: row for row in changed["source_identity_rows"]
    }
    assert by_symbol["ANANTRAJ"]["state"] == (
        "ISIN_CHANGED_REQUIRES_ORIGINAL_ACTION"
    )
    assert by_symbol["ANANTRAJ"]["ohlcv"] is None
    assert changed["arm_coverage"]["SELECTED"]["observed_official_eq"] == 99

    _, missing = _build(missing_eq="SUVIDHAA")
    by_symbol = {
        row["symbol"]: row for row in missing["source_identity_rows"]
    }
    assert by_symbol["SUVIDHAA"]["state"] == (
        "MISSING_EQ_IDENTITY_NO_SUBSTITUTION"
    )
    assert by_symbol["SUVIDHAA"]["ohlcv"] is None
    assert missing["arm_coverage"]["SELECTED"]["observed_official_eq"] == 99


def test_multiple_eq_same_symbol_ambiguity_never_creates_fake_fill():
    _, artifact = _build(duplicate_symbol="ANANTRAJ")
    by_symbol = {
        row["symbol"]: row for row in artifact["source_identity_rows"]
    }
    assert by_symbol["ANANTRAJ"]["state"] == "MULTIPLE_EQ_ROWS_FAIL_CLOSED"
    assert by_symbol["ANANTRAJ"]["ohlcv"] is None


def test_market_raw_bytes_and_h021_source_hash_cannot_be_replaced():
    kwargs, report = _build()
    kwargs["original_udiff_zip"] += b"non-original-footer"
    with pytest.raises(AlphaContractError, match="original NSE source bytes changed"):
        build_hg009_daily_source_observation(**kwargs)
    kwargs, report = _build()
    kwargs["h021_observation"]["packet_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="modified after sealing"):
        build_hg009_daily_source_observation(**kwargs)
    assert report["no_future_prices_used_in_cohort_selection"]


def test_forged_capture_precedes_exchange_close_fails_closed():
    kwargs, _ = _build()
    h021 = copy.deepcopy(kwargs["h021_observation"])
    h021["stock_source"]["captured_at_utc"] = "2026-10-15T09:59:59Z"
    from marketlab.h021_entry_observation import _canonical_hash

    h021.pop("packet_sha256")
    h021["packet_sha256"] = _canonical_hash(h021)
    kwargs["h021_observation"] = h021
    with pytest.raises(
        AlphaContractError, match="timestamp chronology violated"
    ):
        build_hg009_daily_source_observation(**kwargs)


def test_market_row_price_or_future_return_promotion_fails_packet_signature():
    _, output = _build()
    output["source_identity_rows"][0]["ohlcv"]["close_inr"] = 99999999
    with pytest.raises(AlphaContractError, match="packet SHA"):
        validate_hg009_daily_snapshot(output)
    _, output = _build()
    output["gross_holding_period_returns_calculated"] = True
    output["packet_sha256"] = digest({
        k: v for k, v in output.items() if k != "packet_sha256"
    })
    with pytest.raises(AlphaContractError, match="may not authorize"):
        validate_hg009_daily_snapshot(output)


def test_source_replay_archive_is_valid_both_before_and_after_first_day():
    result = verify_daily_observations(ROOT)
    assert result["state"] in {
        "NO_PROSPECTIVE_MARKET_SOURCE_YET",
        "VERIFIED_ORIGINAL_NSE_REPLAY",
    }
    assert result["count"] >= 0
    assert result["count"] == len(result["verified"])
    assert result["no_stock_returns_scored"] is True
    assert result["live_capital_allowed"] is False


def test_direct_verifier_and_materializer_commands_do_not_require_scripts_package():
    verify = subprocess.run(
        [sys.executable, "scripts/verify_hg009_daily.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    payload = json.loads(verify.stdout)
    assert payload["live_capital_allowed"] is False
    assert payload["no_stock_returns_scored"] is True
    assert payload["count"] == len(payload["verified"])

    materialize = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_daily.py", "--help"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert "session-date" in materialize.stdout
