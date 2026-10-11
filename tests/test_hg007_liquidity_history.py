from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

import pytest

from marketlab.hg007_liquidity_history import (
    CALENDAR_PATH,
    FIRST_SESSION,
    LAST_SESSION,
    ORIGINAL_ZIP,
    P035_FILE,
    PRICE_FILE,
    ROOT,
    _five_bars,
    build_twenty_session_liquidity,
    pinned_window_and_context,
    validate_twenty_session_liquidity,
    validated_historical_source,
)
from scripts import acquire_hg007_liquidity_history as acquire


def _copy_pinned_sources(dest: Path) -> None:
    for item in (CALENDAR_PATH, P035_FILE, PRICE_FILE, ORIGINAL_ZIP):
        target = dest / item
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(item).read_bytes())


def _synthetic_day(day: str, ids: dict[str, str], *, bad_isin: str | None = None) -> bytes:
    out = io.StringIO()
    cols = [
        "TradDt","Sgmt","Src","FinInstrmTp","ISIN","TckrSymb","SctySrs",
        "OpnPric","HghPric","LwPric","ClsPric","PrvsClsgPric",
        "TtlTradgVol","TtlTrfVal","TtlNbOfTxsExctd",
    ]
    writer = csv.DictWriter(out, fieldnames=cols)
    writer.writeheader()
    for i, (symbol, isin) in enumerate(ids.items()):
        close = 100 + i
        volume = 10000 + i * 1000
        writer.writerow({
            "TradDt":day, "Sgmt":"CM", "Src":"NSE", "FinInstrmTp":"STK",
            "ISIN":"INENOPE00001" if symbol == bad_isin else isin,
            "TckrSymb":symbol, "SctySrs":"EQ",
            "OpnPric":close,"HghPric":close + 2,"LwPric":close - 2,
            "ClsPric":close,"PrvsClsgPric":close,
            "TtlTradgVol":volume,"TtlTrfVal":close * volume,
            "TtlNbOfTxsExctd":500 + i,
        })
    compressed = io.BytesIO()
    with zipfile.ZipFile(compressed, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("BhavCopy_NSE_CM_0_0_0_" + day.replace("-", "") + "_F_0000.csv", out.getvalue())
    return compressed.getvalue()


def _receipt(day: str, raw: bytes) -> dict:
    from marketlab.marketdata import udiff_url

    return {
        "date": day, "url": udiff_url(date.fromisoformat(day)),
        "state": "ORIGINAL_NSE_EQ_ZIP_RETAINED", "http_status":200,
        "reason":None, "captured_at_utc":"2026-10-11T12:00:00Z",
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "raw_bytes":len(raw),
    }


def _all_20(dest: Path) -> list[str]:
    sessions, ids, _prior, _last, _sources = pinned_window_and_context(dest)
    for source in sessions[:-1]:
        d = source["date"]
        raw = _synthetic_day(d, ids)
        acquire._retain(dest, d, source["close_utc"], raw, _receipt(d, raw), ids)
    return [x["date"] for x in sessions]


def test_frozen_window_has_20_real_calendar_sessions() -> None:
    sessions, ids, _p035, last, provenance = pinned_window_and_context(Path("."))
    assert len(sessions) == 20
    assert sessions[0]["date"] == FIRST_SESSION
    assert sessions[-1]["date"] == LAST_SESSION
    assert tuple(ids) == ("ANANTRAJ","DEVX","INOXGREEN","NPST","SAMBHV")
    assert provenance["oct9_original_udiff_sha256"] == hashlib.sha256(last).hexdigest()
    assert "2026-10-02" not in [s["date"] for s in sessions]


def test_no_sources_refuses_to_publish_any_partial_distribution(tmp_path: Path) -> None:
    _copy_pinned_sources(tmp_path)
    result = build_twenty_session_liquidity(tmp_path)
    validate_twenty_session_liquidity(result)
    assert result["source_status"] == "INCOMPLETE_ORIGINAL_HISTORICAL_MARKET_EVIDENCE"
    assert result["observed_complete_session_count"] == 1
    assert len(result["missing_or_inconsistent_sessions"]) == 19
    assert result["source_session_rows"] == []
    assert result["company_distribution"] == []
    assert result["session_distribution_matured"] is False
    assert result["live_capital_allowed"] is False


def test_all_20_original_date_isin_bars_form_descriptive_lower_tail(
    tmp_path: Path,
) -> None:
    _copy_pinned_sources(tmp_path)
    dates = _all_20(tmp_path)
    result = build_twenty_session_liquidity(tmp_path)
    validate_twenty_session_liquidity(result)
    assert [row["session_date"] for row in result["source_session_rows"]] == dates
    assert result["observed_complete_session_count"] == 20
    assert result["source_status"] == "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE"
    assert len(result["company_distribution"]) == 5
    assert len(result["missing_or_inconsistent_sessions"]) == 0
    by = {row["symbol"]: row for row in result["company_distribution"]}
    devx = by["DEVX"]
    assert devx["session_count"] == 20
    assert devx["twenty_session_traded_value_p10_nearest_rank_inr_crore"] > 0
    assert devx["twenty_session_traded_value_p25_nearest_rank_inr_crore"] > 0
    assert devx["twenty_session_traded_value_median_inr_crore"] > 0
    assert devx["oct9_day_traded_value_inr_crore"] == pytest.approx(.612414613)
    assert devx["oct9_to_trailing_20_session_median_turnover_ratio"] > 0
    assert devx["ten_lakh_ticket_divided_by_one_pct_of_historical_median"] > 0
    for company in result["company_distribution"]:
        assert company["bid_ask_and_market_depth_verified"] is False
        assert company["order_execution_or_cost_validated"] is False
        assert company["one_pct_median_quotient_predicts_execution_time"] is False
    for flag in (
        "equity_total_return_calculated","future_daily_turnover_assumed_repeatable",
        "execution_days_or_fill_probability_estimated","market_impact_slippage_model_verified",
        "portfolio_eligibility_allowed","investment_recommendations_created",
        "live_capital_allowed",
    ):
        assert result[flag] is False


def test_original_day_corruption_blocks_medians(tmp_path: Path) -> None:
    _copy_pinned_sources(tmp_path)
    dates = _all_20(tmp_path)
    day = dates[4]
    raw, src = validated_historical_source(
        tmp_path, day, "2026-10-11T08:00:00Z"
    )
    assert src["source_sha256"] == hashlib.sha256(raw).hexdigest()
    location = tmp_path / ROOT / "raw" / "sha256" / f"{src['source_sha256']}.zip"
    location.write_bytes(raw + b"corrupt")
    blocked = build_twenty_session_liquidity(tmp_path)
    validate_twenty_session_liquidity(blocked)
    assert blocked["observed_complete_session_count"] == 19
    assert blocked["company_distribution"] == []
    assert blocked["missing_or_inconsistent_sessions"][0]["date"] == day


def test_wrong_historical_isin_refuses_silent_identity_substitution(tmp_path: Path) -> None:
    _copy_pinned_sources(tmp_path)
    sessions, ids, _p, _last, _prov = pinned_window_and_context(tmp_path)
    raw = _synthetic_day(sessions[0]["date"], ids, bad_isin="DEVX")
    with pytest.raises(ValueError, match="source ISIN changed"):
        _five_bars(raw, sessions[0]["date"], ids)
    with pytest.raises(ValueError, match="source ISIN changed"):
        acquire._retain(
            tmp_path, sessions[0]["date"], sessions[0]["close_utc"],
            raw, _receipt(sessions[0]["date"], raw), ids,
        )


def test_study_validation_catches_tamper_and_false_trade_permission(tmp_path: Path) -> None:
    _copy_pinned_sources(tmp_path)
    _all_20(tmp_path)
    p = build_twenty_session_liquidity(tmp_path)
    p["company_distribution"][1]["twenty_session_traded_value_median_inr_crore"] = 999
    with pytest.raises(ValueError, match="content was altered"):
        validate_twenty_session_liquidity(p)


def test_blocked_official_endpoint_does_not_retry_or_follow_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class FakeResponse:
        status_code = 403
        content = b"Blocked"
    def get(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url,kwargs))
        return FakeResponse()
    monkeypatch.setattr(acquire.requests, "get", get)
    state, raw = acquire._download_source("2026-09-10", attempts=3, sleep_seconds=0)
    assert state["state"] == "ACCESS_BLOCKED_NO_BYPASS"
    assert raw is None
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False


def test_bounded_source_capture_and_append_only_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _copy_pinned_sources(tmp_path)
    _sessions, ids, _p, _b, _prov = pinned_window_and_context(tmp_path)

    class FakeResponse:
        status_code = 200
        url = None
        def __init__(self, url: str) -> None:
            self.url = url
            day = url.split("_")[6]
            self.content = _synthetic_day(f"{day[:4]}-{day[4:6]}-{day[6:]}", ids)

    monkeypatch.setattr(acquire.requests, "get", lambda url, **kwargs: FakeResponse(url))
    status = acquire.acquire_history(
        tmp_path, attempt_key="test-run-100", attempts_per_date=1, sleep_seconds=0
    )
    assert status["completed_official_sessions"] == 20
    assert status["study_source_state"] == "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE"
    report = json.loads(
        (tmp_path / ROOT / "twenty-session-liquidity-v1.json").read_text()
    )
    validate_twenty_session_liquidity(report)
    assert len(list((tmp_path / ROOT / "receipts").glob("*.json"))) == 19
    assert len(list((tmp_path / ROOT / "attempts").glob("*.json"))) == 1
    with pytest.raises(FileExistsError):
        acquire.acquire_history(
            tmp_path, attempt_key="test-run-100", attempts_per_date=1, sleep_seconds=0
        )
    second = acquire.acquire_history(
        tmp_path, attempt_key="test-run-101", attempts_per_date=1, sleep_seconds=0
    )
    assert second["completed_official_sessions"] == 20
    assert len(list((tmp_path / ROOT / "receipts").glob("*.json"))) == 19
    assert len(list((tmp_path / ROOT / "attempts").glob("*.json"))) == 2
