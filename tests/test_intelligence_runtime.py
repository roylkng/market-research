from __future__ import annotations

import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import pytest

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_runtime import build_report, collect_source, compare_reported_values
from marketlab.intelligence_sources import (
    SourceBlocked,
    approved_url,
    extract_claims,
    normalized_html,
    parse_rss,
)
from marketlab.intelligence_store import ResearchStore, digest

T = datetime(2026, 9, 17, 4, 30, tzinfo=UTC)


def panel_seed():
    members = [{"symbol": f"TEST{i:03}", "isin": f"INX{i:09}", "company_name": f"Test {i} Ltd.",
                "series": "EQ", "constituent_industry": "Synthetic"} for i in range(100)]
    members[0]["symbol"] = "TCS"
    members[0]["company_name"] = "Tata Consultancy Services Ltd."
    raw = json.dumps({"members": members}).encode()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return raw, blob


def init_panel(store):
    raw, blob = panel_seed()
    return store.bootstrap_panel(raw, expected_blob=blob, source_path="synthetic.json", panel_id="TEST")


def source():
    return {"source_id": "test-source", "subject": "TCS", "kind": "html",
            "url": "https://www.tcs.com/test", "publisher": "Test publisher",
            "publication_date": "2026-07-09", "period_end": "2026-06-30",
            "required_markers": ["Test quarterly report"], "facets": ["financials"],
            "fields": [{"concept": "revenue", "facet": "financials", "unit": "million",
                        "currency": "USD", "basis": "CONSOLIDATED",
                        "pattern": r"Revenue (?P<value>[\d,]+) million"}]}


class Fetcher:
    def __init__(self, raw=b"<html>Test quarterly report Revenue 7,624 million</html>",
                 when=None, error=None):
        self.raw, self.error = raw, error
        self.when = when or datetime.now(UTC).isoformat()

    def fetch(self, url):
        if self.error:
            raise self.error
        return self.raw, {"resolved_url": url, "observed_at": self.when,
                          "status_code": 200, "content_type": "text/html"}


def test_panel_is_exactly_100_unique_identities_and_not_recommendations(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        assert len(panel["members"]) == 100
        assert panel["legacy_experiments_modified"] is False
        assert len(store.records("panel")) == 1
        init_panel(store)
        assert len(store.records("panel")) == 1


def test_panel_bad_blob_rejected(tmp_path):
    with ResearchStore(tmp_path) as store:
        raw, _ = panel_seed()
        with pytest.raises(EvidenceError, match="blob"):
            store.bootstrap_panel(raw, expected_blob="f" * 40, source_path="test", panel_id="TEST")


def test_duplicate_panel_is_rejected(tmp_path):
    raw, _ = panel_seed()
    data = json.loads(raw)
    data["members"][-1] = data["members"][0]
    raw = json.dumps(data).encode()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    with ResearchStore(tmp_path) as store, pytest.raises(EvidenceError, match="Duplicate"):
        store.bootstrap_panel(raw, expected_blob=blob, source_path="test", panel_id="TEST")


def test_database_reopens_and_rejects_record_mutation(tmp_path):
    with ResearchStore(tmp_path) as store:
        store.append("fact", "one", {"a": 1})
    with ResearchStore(tmp_path) as store:
        assert store.records("fact") == [{"a": 1}]
        with pytest.raises(EvidenceError, match="Immutable"):
            store.append("fact", "one", {"a": 2})
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store.connection.execute("DELETE FROM records")


def test_raw_hashes_and_corruption(tmp_path):
    with ResearchStore(tmp_path) as store:
        key = store.save_object(b"hello")
        assert store.save_object(b"hello") == key
        assert store.read_object(key) == b"hello"
        (store.objects / key).write_bytes(b"changed")
        with pytest.raises(EvidenceError, match="digest"):
            store.read_object(key)
        with pytest.raises(EvidenceError):
            store.read_object("../../file")


def test_real_path_extracts_only_source_backed_claim_and_replays_idempotently(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        result = collect_source(store, source(), panel, Fetcher())
        assert result["status"] == "DOCUMENT_PARSED"
        row = store.records("evidence")[0]
        text = store.read_object(store.records("document")[0]["text_sha256"]).decode()
        assert text[row["span_start"]:row["span_end"]] == row["evidence"]["quote"]
        assert row["evidence"]["value"] == "7624"
        first_seen = row["evidence"]["first_seen_at"]
        collect_source(store, source(), panel, Fetcher())
        assert len(store.records("evidence")) == 1
        assert store.records("evidence")[0]["evidence"]["first_seen_at"] == first_seen


def test_source_failure_is_persisted_not_no_news(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        result = collect_source(store, source(), panel, Fetcher(error=SourceBlocked("403")))
        assert result["status"] == "SOURCE_BLOCKED"
        assert len(store.records("attempt")) == 1
        assert not store.records("evidence")


def test_parse_failure_keeps_raw_and_never_partial_facts(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        result = collect_source(store, source(), panel, Fetcher(raw=b"<html>Changed layout</html>"))
        assert result["status"] == "PARSE_FAILED"
        assert store.read_object(result["raw_sha256"])
        assert store.records("evidence") == []


def test_every_company_has_all_nine_coverage_slots_and_no_forecast(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        report = build_report(store, panel, {"sources": [source()]}, as_of=T.isoformat())
        assert len(report["packets"]) == 100
        assert len(report["research_queue"]) == 900
        for packet in report["packets"]:
            assert len(packet["coverage"]) == 9
            assert all(c["state"] == "NOT_COLLECTED" for c in packet["coverage"])
            assert packet["forecast"] is None and packet["investment_rank"] is None


def test_old_publication_acquired_now_does_not_enter_past_packet(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        collect_source(store, source(), panel, Fetcher())
        report = build_report(store, panel, {"sources": [source()]}, as_of="2026-07-10T12:00:00Z")
        assert report["active_evidence_count"] == 0
        assert report["source_attempts"] == []


def test_latest_failed_attempt_does_not_hide_behind_success(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        collect_source(store, source(), panel, Fetcher())
        collect_source(store, source(), panel, Fetcher(error=SourceBlocked("403")))
        report = build_report(store, panel, {"sources": [source()]}, as_of=datetime.now(UTC).isoformat())
        packet = next(p for p in report["packets"] if p["symbol"] == "TCS")
        assert packet["coverage"][0]["state"] == "DEGRADED_SOURCE"
        assert packet["evidence"]


@pytest.mark.parametrize("url", ["http://www.tcs.com/", "https://www.tcs.com.evil.test/",
    "https://user:secret@www.tcs.com/", "https://127.0.0.1/", "https://www.tcs.com:8443/"])
def test_request_allowlist(url):
    with pytest.raises(SourceBlocked):
        approved_url(url)


def test_document_text_does_not_keep_scripts():
    text = normalized_html(b"<html><script>Revenue 99 million</script>Revenue 10 million</html>")
    assert text == "Revenue 10 million"


def test_ambiguous_or_missing_numeric_fact_rejected():
    for text in ("Test quarterly report Revenue 10 million Revenue 11 million",
                 "Test quarterly report No results"):
        with pytest.raises(EvidenceError):
            extract_claims(text, source())


def test_radar_keeps_unresolved_and_outside_panel_entries():
    raw = b'''<rss><channel><item><title>Tata Consultancy Services Limited</title>
    <guid>one</guid><link>https://nsearchives.nseindia.com/one.pdf</link>
    <pubDate>Thu, 17 Sep 2026 10:00:00 +0530</pubDate></item>
    <item><title>Unknown Company</title><guid>two</guid></item></channel></rss>'''
    members = json.loads(panel_seed()[0])["members"]
    rows = parse_rss(raw, members=members, source_id="NSE", observed_at=T.isoformat())
    assert len(rows) == 2
    assert rows[0]["symbols"] == ["TCS"]
    assert rows[1]["identity_state"] == "UNRESOLVED"
    assert rows[1]["publication_state"] == "UNRESOLVED"
    assert rows[1]["attachment_state"] == "BLOCKED_UNREVIEWED_LINK"


@pytest.mark.parametrize("raw", [b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>',
    b'<html>blocked</html>', b'\xff\xfe<\x00r\x00s\x00s\x00/\x00>'])
def test_untrusted_xml_rejected(raw):
    with pytest.raises((EvidenceError, ET.ParseError)):
        parse_rss(raw, members=[], source_id="NSE", observed_at=T.isoformat())


def test_comparable_arithmetic_and_basis_guard():
    rows = [{"source_id": s, "concept": "revenue", "basis": "IFRS", "unit": "million",
             "currency": "USD", "period_end": p, "evidence": {"identifier": s, "value": v}}
            for s, p, v in [("current", "2026-06-30", "7624"), ("prior", "2025-06-30", "7421")]]
    spec = {"current": "current", "prior": "prior", "concept": "revenue", "operation": "growth_pct"}
    result = compare_reported_values(spec, rows)
    assert float(result["value"]) == pytest.approx((7624 / 7421 - 1) * 100)
    rows[1]["currency"] = "INR"
    assert compare_reported_values(spec, rows)["value"] is None
    assert compare_reported_values(spec, rows)["status"] == "BASIS_UNIT_OR_CURRENCY_MISMATCH"


def test_report_is_deterministic(tmp_path):
    with ResearchStore(tmp_path) as store:
        panel = init_panel(store)
        a = build_report(store, panel, {"sources": []}, as_of=T.isoformat())
        b = build_report(store, panel, {"sources": []}, as_of=T.isoformat())
        assert digest(a) == digest(b)
