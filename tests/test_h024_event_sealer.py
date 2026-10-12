from __future__ import annotations

import csv
import gzip
import importlib.util
import io
from pathlib import Path

import pytest


def _load_sealer_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "seal_h024_prospective_events.py"
    spec = importlib.util.spec_from_file_location("seal_h024_prospective_events", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _security_master_gzip(rows: list[dict[str, str]]) -> bytes:
    fieldnames = [
        "TckrSymb",
        "SctySrs",
        "FinInstrmNm",
        "ISIN",
        "SctyTpFlg",
        "CallAuctnInd",
        "PrtdToTrad",
        "SctyStsNrmlMkt",
        "ElgbltyNrmlMkt",
        "ListgDt",
        "DelFlg",
        "Xchg",
        "FinInstrmTp",
        "InstrmTp",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return gzip.compress(buffer.getvalue().encode("utf-8"))


def _row(symbol: str, *, series: str = "EQ", isin: str = "INE000A01001") -> dict[str, str]:
    return {
        "TckrSymb": symbol,
        "SctySrs": series,
        "FinInstrmNm": f"{symbol} Limited",
        "ISIN": isin,
        "SctyTpFlg": "EQ",
        "CallAuctnInd": "0",
        "PrtdToTrad": "1",
        "SctyStsNrmlMkt": "1",
        "ElgbltyNrmlMkt": "1",
        "ListgDt": "20200101",
        "DelFlg": "N",
        "Xchg": "NSE",
        "FinInstrmTp": "STK",
        "InstrmTp": "EQ",
    }


def test_security_master_parser_keeps_only_requested_eq_rows() -> None:
    sealer = _load_sealer_module()
    raw = _security_master_gzip(
        [
            _row("AAA"),
            _row("AAA", series="BE", isin="INE000A01002"),
            _row("BBB"),
        ]
    )

    parsed = sealer._parse_security_master(raw, symbols={"AAA"})

    assert list(parsed) == ["AAA"]
    assert parsed["AAA"]["ISIN"] == "INE000A01001"
    assert parsed["AAA"]["SctySrs"] == "EQ"
    assert parsed["AAA"]["PrtdToTrad"] == "1"


def test_security_master_parser_fails_on_duplicate_requested_eq_row() -> None:
    sealer = _load_sealer_module()
    raw = _security_master_gzip(
        [_row("AAA", isin="INE000A01001"), _row("AAA", isin="INE000A01002")]
    )

    with pytest.raises(sealer.H024EventSealerError, match="duplicate.*AAA"):
        sealer._parse_security_master(raw, symbols={"AAA"})


def test_report_url_accepts_only_approved_nse_https_hosts() -> None:
    sealer = _load_sealer_module()

    assert (
        sealer._find_report_url(
            {"filePath": "https://nsearchives.nseindia.com/content/cm/security.csv.gz"}
        )
        == "https://nsearchives.nseindia.com/content/cm/security.csv.gz"
    )
    with pytest.raises(sealer.H024EventSealerError, match="unapproved"):
        sealer._find_report_url({"url": "https://example.com/security.csv.gz"})


def test_listing_date_parser_is_fail_closed_for_unknown_formats() -> None:
    sealer = _load_sealer_module()

    assert sealer._parse_listing_date("20260916").isoformat() == "2026-09-16"
    assert sealer._parse_listing_date("16-09-2026").isoformat() == "2026-09-16"
    assert sealer._parse_listing_date("") is None
    assert sealer._parse_listing_date("16/Sep/2026") is None


def test_preentry_source_gate_rejects_delayed_action_and_insufficient_lead() -> None:
    from datetime import UTC, datetime, timedelta

    module = _load_sealer_module()
    first_open = datetime(2026, 10, 12, 3, 45, 0, tzinfo=UTC)
    assert module._preentry_source_gate(
        checked_at_utc=first_open - timedelta(minutes=5),
        official_entry_open_utc=first_open,
        minimum_lead_seconds=45,
    ) == "TIMING_SOURCE_READY"
    for late in (
        first_open - timedelta(seconds=45),
        first_open - timedelta(seconds=25),
        first_open,
        first_open + timedelta(hours=7),
    ):
        assert module._preentry_source_gate(
            checked_at_utc=late,
            official_entry_open_utc=first_open,
            minimum_lead_seconds=45,
        ) == "PREENTRY_SOURCE_CUTOFF_MISSED"
    with pytest.raises(module.H024EventSealerError, match="timing source gate"):
        module._preentry_source_gate(
            checked_at_utc=datetime(2026, 10, 12, 3, 20),
            official_entry_open_utc=first_open,
            minimum_lead_seconds=45,
        )


def test_official_security_master_http_404_is_an_unavailable_source_not_retry(
    tmp_path: Path,
) -> None:
    from datetime import date

    module = _load_sealer_module()
    calls = []

    class Response:
        status_code = 404

    class FakeSession:
        def get(self, url: str, **kwargs: object) -> Response:
            calls.append((url, kwargs))
            return Response()

    with pytest.raises(module.H024SecurityMasterHTTP404, match="HTTP 404"):
        module._download_security_master(
            FakeSession(),
            entry_day=date(2026, 10, 12),
            raw_dir=tmp_path,
            attempts=4,
            timeout=5,
        )
    assert len(calls) == 1
    assert calls[0][0] == module.REPORTS_ENDPOINT
    assert calls[0][1]["params"]["date"] == "12-Oct-2026"
    assert not list(tmp_path.glob("*.gz"))


def test_blocked_source_receipt_cannot_be_mistaken_for_prospective_event() -> None:
    from datetime import UTC, datetime

    module = _load_sealer_module()
    report = module._source_block_report(
        planned_session="2026-10-12",
        official_entry_open_utc=datetime(2026, 10, 12, 3, 45, tzinfo=UTC),
        started_at_utc="2026-10-12T10:24:23Z",
        due_symbols={"WSI"},
        reason="PREENTRY_SOURCE_CUTOFF_MISSED",
        signal_ledger_sha256="a" * 64,
        event_ledger_sha256="b" * 64,
        source_detail="OFFICIAL_SESSION_NOT_OBSERVED_BEFORE_ENTRY_OPEN",
    )
    assert report["report_state"] == "BLOCKED_PROSPECTIVE_SOURCE_NO_EVENT_SEALED"
    assert report["due_symbol_count"] == 1
    assert report["blocked_due_symbols"] == ["WSI"]
    assert report["official_entry_open_utc"] == "2026-10-12T03:45:00Z"
    assert report["sealed_event_count"] == 0
    assert report["original_event_ledger_sha256"] == "b" * 64
    assert report["prior_day_security_master_substituted"] is False
    assert report["past_session_reclassification_permitted"] is False
    assert report["outcome_data_attached"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False
    with pytest.raises(module.H024EventSealerError, match="unsupported"):
        module._source_block_report(
            planned_session="2026-10-12",
            official_entry_open_utc=datetime(2026, 10, 12, 3, 45, tzinfo=UTC),
            started_at_utc="2026-10-12T03:44:00Z",
            due_symbols={"WSI"},
            reason="ASSUME_PREVIOUS_SESSION_SECURITY_MASTER_ACCEPTABLE",
            signal_ledger_sha256="a" * 64,
            event_ledger_sha256="b" * 64,
            source_detail="invalid",
        )


def test_delayed_real_sealer_main_never_issues_source_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from argparse import Namespace
    from datetime import UTC, datetime

    module = _load_sealer_module()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 12, 10, 24, 23, tzinfo=UTC).astimezone(tz or UTC)

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(
        module, "parse_args",
        lambda: Namespace(
            state_dir=tmp_path,
            raw_dir=tmp_path / "raw",
            report=tmp_path / "report.json",
            entry_session="2026-10-12",
            lookback_days=35,
            timeout_seconds=30,
            attempts=4,
            final_refresh_seconds_before_open=45,
            max_completed_sessions=260,
        ),
    )
    monkeypatch.setattr(
        module, "_load_or_initialize",
        lambda path, factory: {"ledger_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        module, "_load_json",
        lambda path: {"ledger_sha256": "b" * 64},
    )
    for check_name in (
        "validate_source_ledger",
        "validate_evidence_ledger",
        "validate_signal_ledger",
        "validate_scan_ledger",
        "validate_event_ledger",
    ):
        monkeypatch.setattr(module, check_name, lambda payload: None)
    monkeypatch.setattr(
        module, "due_event_keys",
        lambda **kwargs: [("WSI", "2026-10-12")],
    )
    monkeypatch.setattr(
        module, "_entry_open_for_session",
        lambda *args: datetime(2026, 10, 12, 3, 45, tzinfo=UTC),
    )

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("post-entry NSE source fetch is forbidden")

    monkeypatch.setattr(module, "discovery_session", unexpected_fetch)
    monkeypatch.setattr(module, "_download_security_master", unexpected_fetch)
    assert module.main() == 0
    report = __import__("json").loads(
        (tmp_path / "report.json").read_text(encoding="utf-8")
    )
    assert report["blocking_reason"] == "PREENTRY_SOURCE_CUTOFF_MISSED"
    assert report["sealed_event_count"] == 0
    assert report["blocked_due_symbols"] == ["WSI"]
    assert report["prior_signal_backdated_to_entry"] is False


def test_timely_run_404_is_a_source_only_report_not_an_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from argparse import Namespace
    from datetime import UTC, datetime

    module = _load_sealer_module()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 12, 3, 0, tzinfo=UTC).astimezone(tz or UTC)

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(
        module, "parse_args",
        lambda: Namespace(
            state_dir=tmp_path,
            raw_dir=tmp_path / "raw",
            report=tmp_path / "report.json",
            entry_session="2026-10-12",
            lookback_days=35,
            timeout_seconds=30,
            attempts=4,
            final_refresh_seconds_before_open=45,
            max_completed_sessions=260,
        ),
    )
    monkeypatch.setattr(
        module, "_load_or_initialize",
        lambda path, factory: {"ledger_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        module, "_load_json",
        lambda path: {"ledger_sha256": "b" * 64},
    )
    for check_name in (
        "validate_source_ledger",
        "validate_evidence_ledger",
        "validate_signal_ledger",
        "validate_scan_ledger",
        "validate_event_ledger",
    ):
        monkeypatch.setattr(module, check_name, lambda payload: None)
    monkeypatch.setattr(module, "due_event_keys", lambda **kwargs: [("WSI", "2026-10-12")])
    monkeypatch.setattr(
        module, "_entry_open_for_session",
        lambda *args: datetime(2026, 10, 12, 3, 45, tzinfo=UTC),
    )
    monkeypatch.setattr(module, "discovery_session", lambda timeout: object())

    def unavailable(*args, **kwargs):
        raise module.H024SecurityMasterHTTP404("HTTP 404 at exact NSE report")

    monkeypatch.setattr(module, "_download_security_master", unavailable)
    assert module.main() == 0
    report = __import__("json").loads((tmp_path / "report.json").read_text())
    assert report["blocking_reason"] == "OFFICIAL_SECURITY_MASTER_HTTP_404"
    assert report["sealed_event_count"] == 0
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False
