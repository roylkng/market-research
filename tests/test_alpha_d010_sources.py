from datetime import date

from marketlab.alpha_d010_sources import (
    ProbeResponse,
    inspect_csv_response,
    render_url,
    summarize_discovery,
)


def test_d010_csv_inspection_accepts_real_csv_shape():
    response = ProbeResponse(
        status_code=200,
        content_type="text/csv",
        body=b"SYMBOL,QTY\nSBIN,100\nINFY,200\n",
    )
    result = inspect_csv_response(
        response,
        url="https://nsearchives.nseindia.com/x.csv",
    )
    assert result["status"] == "READY"
    assert result["header"] == ["SYMBOL", "QTY"]
    assert result["data_row_count"] == 2
    assert len(result["raw_sha256"]) == 64


def test_d010_rejects_html_even_with_http_200():
    response = ProbeResponse(
        status_code=200,
        content_type="text/html",
        body=b"<html><body>not found</body></html>",
    )
    result = inspect_csv_response(response, url="https://example.com/x.csv")
    assert result["status"] == "HTML_RESPONSE"


def test_d010_url_render_is_frozen_ddmmyyyy():
    assert render_url(
        "https://x/shortselling_{ddmmyyyy}.csv",
        date(2026, 9, 25),
    ).endswith("shortselling_25092026.csv")


def test_d010_promotes_only_one_pattern_ready_all_sessions(monkeypatch):
    from marketlab import alpha_d010_sources as module

    monkeypatch.setattr(
        module,
        "SOURCE_FAMILIES",
        {
            "CM_SHORT_SELLING": ("https://x/{ddmmyyyy}", "https://y/{ddmmyyyy}"),
        },
    )
    attempts = []
    for session in module.PROBE_DATES:
        attempts.append(
            {
                "family": "CM_SHORT_SELLING",
                "pattern_index": 0,
                "session_date": session.isoformat(),
                "response": {"status": "READY"},
            }
        )
        attempts.append(
            {
                "family": "CM_SHORT_SELLING",
                "pattern_index": 1,
                "session_date": session.isoformat(),
                "response": {"status": "HTTP_NOT_READY"},
            }
        )
    report = summarize_discovery(attempts)
    family = report["families"]["CM_SHORT_SELLING"]
    assert family["status"] == "PROMOTE_P1"
    assert family["selected_pattern_index"] == 0
    assert report["all_families_promote_p1"] is True
