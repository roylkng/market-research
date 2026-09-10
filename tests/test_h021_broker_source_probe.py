from __future__ import annotations

from scripts.probe_h021_broker_revision_pages import extract_revision_snippets


def test_extracts_dated_upward_eps_revision() -> None:
    html = """
    <html><body>
    20 May 2026 GE Vernova T&D India Ltd.
    We revise our FY27/28E EPS estimates upward by +3.7%/+4.8%, factoring in strong execution momentum.
    </body></html>
    """
    rows = extract_revision_snippets(html)
    assert rows
    assert any("EPS estimates upward" in row["revision_text"] for row in rows)
    assert any(row["nearby_date_text"] == "20 May 2026" for row in rows)


def test_extracts_downward_revision() -> None:
    html = """
    <html><body>
    18 Mar 2026 V-Guard Industries.
    We revise our FY26E & FY27E EPS estimates downward by 3.3% and 12.0%, respectively.
    </body></html>
    """
    rows = extract_revision_snippets(html)
    assert rows
    assert any("downward" in row["revision_text"].lower() for row in rows)


def test_no_revision_text_returns_empty() -> None:
    assert extract_revision_snippets("<html><body>Revenue grew 20% year on year.</body></html>") == []
