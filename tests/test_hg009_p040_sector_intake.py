"""Fail-closed original receipt tests, no external HTTP."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/hg009_p040_sector_intake.py"
SPEC = importlib.util.spec_from_file_location("hg009_p040_sector_intake", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("url", [
    "http://www.nseindia.com/a", "https://127.0.0.1/a",
    "https://localhost/a", "https://nseindia.com.evil.test/a",
    "https://user:secret@nseindia.com/a", "https://nseindia.com:8443/a",
    "https://example.com/report.pdf", "file:///etc/passwd",
])
def test_reject_unapproved_urls(url):
    with pytest.raises(ValueError):
        MODULE.validate_source_url(url)


def test_accept_official_host():
    assert MODULE.validate_source_url(
        "https://nsearchives.nseindia.com/corporate/report.pdf"
    ) == "https://nsearchives.nseindia.com/corporate/report.pdf"


def test_receipt_is_not_classification(tmp_path):
    url = "https://www.nseindia.com/example.pdf"
    first = MODULE.persist(tmp_path, "ACE", "INE731H01025", "SELECTED",
                           url, b"original bytes", "2026-10-23T00:00:00+00:00",
                           "a" * 64)
    receipt = json.loads(first.read_text())
    assert receipt["classification"] is None
    assert receipt["classification_verified"] is False
    assert receipt["preentry_eligible"] is False
    assert receipt["trial_admitted"] is False
    assert (tmp_path / "raw" / MODULE.digest(b"original bytes")).read_bytes() == b"original bytes"
    second = MODULE.persist(tmp_path, "ACE", "INE731H01025", "SELECTED",
                            url, b"original bytes", "2026-10-24T00:00:00+00:00",
                            "a" * 64)
    assert first == second
    assert json.loads(first.read_text())["first_retrieved_at_utc"] == "2026-10-23T00:00:00+00:00"


def test_reject_duplicate_identity():
    row = {"original_symbol": "ABC", "frozen_isin": "INE000000001", "arm": "SELECTED"}
    with pytest.raises(ValueError):
        MODULE.identities({"future_source_collection_queue": [row] * 300})


def test_reject_unknown_identity_before_network(tmp_path, monkeypatch):
    rows = [{"original_symbol": f"S{i}", "frozen_isin": f"INEX{i:09d}", "arm": "SELECTED"}
            for i in range(300)]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"future_source_collection_queue": rows}))
    csv_file = tmp_path / "sources.csv"
    csv_file.write_text("symbol,isin,url\nNOTIN,INE000000001,https://nseindia.com/a\n")
    monkeypatch.setattr(MODULE, "fetch_original", lambda _: pytest.fail("should not fetch"))
    with pytest.raises(ValueError, match="not in frozen cohort"):
        MODULE.run(csv_file, tmp_path / "out", queue)
