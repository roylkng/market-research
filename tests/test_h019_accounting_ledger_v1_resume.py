from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import h019_accounting_ledger_v1_resume as resume  # noqa: E402


def _frozen() -> dict[str, object]:
    return {
        "symbol": "TEST",
        "group": "EXIT_PROXY",
        "company": "Test Limited",
        "from_year": 2017,
        "to_year": 2018,
        "available_at": "2018-08-01T12:00:00+05:30",
        "report_url": "https://nsearchives.nseindia.com/annual_reports/test.pdf",
        "api_source_sha256": "a" * 64,
    }


def test_parser_failure_is_report_level_and_never_falls_back(monkeypatch, tmp_path: Path) -> None:
    def fail(*_args, **_kwargs):
        raise TypeError("malformed PDF font dictionary")

    monkeypatch.setattr(resume.v3, "extract_report", fail)
    frozen = _frozen()
    retained = {"sha256": "b" * 64}
    result = resume.safe_extract_report(
        {**frozen, "raw_path": "raw/x", "sha256": "b" * 64},
        frozen,
        retained,
        "c" * 64,
        tmp_path,
    )
    assert result["status"] == "PARSER_FAILED_CLOSED"
    assert result["exception_type"] == "TypeError"
    assert result["fallback_used"] is False
    assert result["symbol"] == "TEST"
    assert result["report_url"] == frozen["report_url"]


def test_unexpected_process_exception_remains_fatal(monkeypatch, tmp_path: Path) -> None:
    class UnexpectedError(RuntimeError):
        pass

    def fail(*_args, **_kwargs):
        raise UnexpectedError("unexpected invariant failure")

    monkeypatch.setattr(resume.v3, "extract_report", fail)
    frozen = _frozen()
    retained = {"sha256": "b" * 64}
    try:
        resume.safe_extract_report(
            {**frozen, "raw_path": "raw/x", "sha256": "b" * 64},
            frozen,
            retained,
            "c" * 64,
            tmp_path,
        )
    except UnexpectedError:
        pass
    else:
        raise AssertionError("unexpected exceptions must not be swallowed")


def test_fail_closed_error_is_bounded() -> None:
    frozen = _frozen()
    retained = {"sha256": "b" * 64}
    result = resume.parser_failed_closed(
        frozen,
        retained,
        "c" * 64,
        TypeError("x" * 5000),
    )
    assert len(result["error"]) == 1000
    assert result["fallback_used"] is False
