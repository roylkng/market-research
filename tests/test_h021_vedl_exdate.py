from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from marketlab.h021_vedl_exdate import (
    EXACT_NSE_API,
    _packet_sha,
    build_official_vedl_exdate_packet,
    verified_issuer_dividend_source,
)
from scripts import acquire_h021_vedl_nse_exdate as acquire


def _raw(ex_date: str = "14-Oct-2026", amount: str = "Rs 5") -> bytes:
    return json.dumps({"data": [
        {"symbol": "VEDL", "series": "EQ", "purpose": f"Interim Dividend - {amount} Per Share",
         "exDate": ex_date, "recordDate": "14-Oct-2026"},
        {"symbol": "TCS", "series": "EQ", "purpose": "Interim Dividend - Rs 12 Per Share",
         "exDate": "14-Oct-2026"}
    ]}, sort_keys=True).encode("utf-8")


def _receipt(raw: bytes | None, timestamp: str = "2026-10-12T15:30:00Z") -> dict:
    return {
        "url": EXACT_NSE_API, "captured_at_utc": timestamp,
        "status": "OK" if raw is not None else "NOT_PUBLISHED",
        "http_status": 200 if raw is not None else 404,
        "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "error": None if raw is not None else "NSE_HTTP404_NOT_PUBLISHED"
    }


def _build(raw: bytes | None, timestamp: str = "2026-10-12T15:30:00Z") -> dict:
    return build_official_vedl_exdate_packet(
        root=Path("."), raw=raw, source_receipt=_receipt(raw, timestamp)
    )


def test_issuer_original_and_nse_exdate_correlate_without_entitlement() -> None:
    original = verified_issuer_dividend_source(Path("."))
    assert original["original_board_reported_dividend_inr"] == 5
    assert original["original_board_reported_record_date_ist"] == "2026-10-14"
    packet = _build(_raw())
    assert packet["original_exchange_ex_date_verified"] is True
    assert packet["source_retrieved_before_oct14_ex_open"] is True
    assert packet["official_matching_row"]["exchange_ex_date"] == "2026-10-14"
    assert packet["official_matching_row"]["exchange_record_date_if_present"] == (
        "2026-10-14"
    )
    assert packet["packet_sha256"] == _packet_sha({
        k: v for k, v in packet.items() if k != "packet_sha256"
    })
    for flag in (
        "hypothetical_oct12_open_is_actual_trade",
        "dividend_cash_entitlement_assessed_or_paid",
        "all_h021_ten_company_actions_exhaustively_audited",
        "index_total_return_and_equity_dividends_comparable",
        "twenty_sixty_session_outcomes_opened",
        "stock_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert packet[flag] is False


@pytest.mark.parametrize("ex_date,amount", [
    ("13-Oct-2026", "Rs 5"),
    ("14-Oct-2026", "Rs 10"),
])
def test_contradictory_exchange_action_remains_unverified(
    ex_date: str, amount: str
) -> None:
    packet = _build(_raw(ex_date, amount))
    assert packet["source_state"] == "BLOCKED_AMBIGUOUS_OR_CONTRADICTORY_NSE_EVENT"
    assert packet["original_exchange_ex_date_verified"] is False
    assert packet["official_matching_row"] is None


def test_duplicate_same_event_is_blocked_instead_of_arbitrary_selection() -> None:
    obj = json.loads(_raw())
    obj["data"].append(obj["data"][0])
    data = json.dumps(obj).encode()
    assert _build(data)["source_state"] == "BLOCKED_AMBIGUOUS_OR_CONTRADICTORY_NSE_EVENT"


def test_absent_or_invalid_source_never_becomes_a_verified_dividend() -> None:
    assert _build(None)["source_retrieved_before_oct14_ex_open"] is False
    assert _build(None)["original_exchange_ex_date_verified"] is False
    empty = json.dumps({"data": []}).encode()
    assert _build(empty)["source_state"] == "ORIGINAL_NSE_EXDATE_ROW_MISSING"
    bad = b'{"error":"blocked"}'
    with pytest.raises(TypeError, match="event-row list"):
        _build(bad)


def test_late_retrieval_cannot_be_backdated_as_preex_source() -> None:
    packet = _build(_raw(), "2026-10-14T12:00:00Z")
    assert packet["original_exchange_ex_date_verified"] is True
    assert packet["source_retrieved_before_oct14_ex_open"] is False
    assert packet["dividend_cash_entitlement_assessed_or_paid"] is False


def test_unauthorized_url_or_bytes_do_not_pass_original_source_identity() -> None:
    raw = _raw()
    source = _receipt(raw)
    source["url"] = "https://example.com/substitute.json"
    with pytest.raises(ValueError, match="official VEDL corporate-action URL"):
        build_official_vedl_exdate_packet(
            root=Path("."), raw=raw, source_receipt=source
        )
    source = _receipt(raw)
    source["raw_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="successful receipt disagree"):
        build_official_vedl_exdate_packet(
            root=Path("."), raw=raw, source_receipt=source
        )


def test_retained_sha_and_prohibited_entitlement_promotion(tmp_path: Path) -> None:
    raw, source = _raw(), _receipt(_raw())
    packet = build_official_vedl_exdate_packet(
        root=Path("."), raw=raw, source_receipt=source
    )
    acquire.save_attempt(root=tmp_path, raw=raw, source_receipt=source, report=packet)
    assert json.loads((tmp_path / "event-date-screen.json").read_text()) == packet
    original = tmp_path / "raw" / "sha256" / f"{hashlib.sha256(raw).hexdigest()}.json"
    assert original.read_bytes() == raw
    packet["dividend_cash_entitlement_assessed_or_paid"] = True
    with pytest.raises(ValueError, match="cannot authorize capital"):
        acquire.save_attempt(
            root=tmp_path, raw=raw, source_receipt=source, report=packet
        )


def test_denied_public_site_exits_without_request_spam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Response:
        status_code = 403

    class Session:
        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url: str, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monkeypatch.setattr(acquire.requests, "Session", Session)
    receipt, original = acquire.probe_public_nse_actions()
    assert original is None
    assert receipt["status"] == "ACCESS_BLOCKED"
    assert receipt["http_status"] == 403
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
