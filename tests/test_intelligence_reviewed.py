from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_reviewed import build_reviewed_report, import_reviewed_capture
from marketlab.intelligence_runtime import collect_source
from marketlab.intelligence_sources import SourceBlocked
from marketlab.intelligence_store import ResearchStore


def panel():
    return {"panel_id": "TEST", "members": [{"symbol": "TCS", "company_name": "TCS", "isin": "TEST"}]}


def capture():
    return {"capture_method": "WEB_ASSISTED_EXCERPT", "original_document_bytes_retained": False,
            "original_document_sha256": None, "window_complete": False,
            "source_id": "test", "subject": "TCS", "publisher": "Synthetic test publisher",
            "source_url": "https://www.tcs.com/test", "reviewed_by": "Synthetic reviewer",
            "source_locator": "Synthetic fixture, not live company evidence",
            "observed_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "publication_date": "2026-07-09", "claims": [{"concept": "revenue", "facet": "financials",
                "period_end": "2026-06-30", "unit": "million", "currency": "USD",
                "basis": "SYNTHETIC", "value": "123", "quote": "Revenue 123 million",
                "role": "REPORTED_FACT"}]}


def test_import_preserves_excerpt_not_original_provenance(tmp_path):
    with ResearchStore(tmp_path) as store:
        c = capture()
        first = import_reviewed_capture(store, c, panel())
        second = import_reviewed_capture(store, c, panel())
        assert first == second
        assert len(store.records("evidence")) == 1
        row = store.records("evidence")[0]
        assert row["original_document_sha256"] is None
        assert row["artifact_kind"] == "WEB_ASSISTED_EXCERPT"
        assert store.read_object(row["evidence"]["content_sha256"]) == b"Revenue 123 million"


@pytest.mark.parametrize("field,value", [
    ("capture_method", "ORIGINAL_HTML"), ("original_document_bytes_retained", True),
    ("original_document_sha256", "a" * 64), ("window_complete", True),
    ("subject", "UNKNOWN"), ("source_url", "https://evil.example/test"),
])
def test_reviewed_capture_cannot_promote_provenance(tmp_path, field, value):
    with ResearchStore(tmp_path) as store:
        c = capture()
        c[field] = value
        with pytest.raises(EvidenceError):
            import_reviewed_capture(store, c, panel())
        assert not store.records("evidence")


def test_changed_number_or_overlong_excerpt_is_rejected(tmp_path):
    with ResearchStore(tmp_path) as store:
        c = capture()
        c["claims"][0]["value"] = "999"
        with pytest.raises(EvidenceError, match="not present"):
            import_reviewed_capture(store, c, panel())
        c = capture()
        c["claims"][0]["quote"] = "words " * 26 + "123"
        with pytest.raises(EvidenceError, match="allowance"):
            import_reviewed_capture(store, c, panel())


def test_reviewed_import_cannot_backdate_company_evidence(tmp_path):
    with ResearchStore(tmp_path) as store:
        c = capture()
        c["observed_at"] = "2026-07-10T12:00:00Z"
        import_reviewed_capture(store, c, panel())
        past = build_reviewed_report(store, panel(), {"sources": []}, as_of="2026-07-11T12:00:00Z")
        assert not past["active_evidence_count"]
        assert not past["reviewed_source_imports"]


def test_future_observation_and_duplicate_claim_fail(tmp_path):
    with ResearchStore(tmp_path) as store:
        c = capture()
        c["observed_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        with pytest.raises(EvidenceError, match="future"):
            import_reviewed_capture(store, c, panel())
        c = capture()
        c["claims"].append(deepcopy(c["claims"][0]))
        with pytest.raises(EvidenceError, match="Duplicate"):
            import_reviewed_capture(store, c, panel())


def test_import_does_not_clear_failed_automated_source(tmp_path):
    class Blocked:
        def fetch(self, url):
            raise SourceBlocked("403")
    config = {"sources": [{"source_id": "test", "subject": "TCS", "kind": "html",
                          "url": "https://www.tcs.com/test", "facets": ["financials"]}]}
    with ResearchStore(tmp_path) as store:
        collect_source(store, config["sources"][0], panel(), Blocked())
        import_reviewed_capture(store, capture(), panel())
        report = build_reviewed_report(store, panel(), config, as_of=datetime.now(UTC).isoformat())
        assert report["active_evidence_count"] == 1
        assert report["packets"][0]["coverage"][0]["state"] == "DEGRADED_SOURCE"
        assert report["source_status_counts"] == {"SOURCE_BLOCKED": 1}
        assert report["reviewed_source_imports"][0]["automated_source_recovered"] is False
        assert report["packets"][0]["forecast"] is None
