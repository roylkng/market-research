from __future__ import annotations

import copy
import hashlib
import json

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_news import setup
from marketlab.company_change_news_review import admit, review_packet, validate_review
from marketlab.company_change_store import EvidenceStore

NOW = "2026-11-08T01:00:00Z"
TEXT = "TEST LIMITED received a letter of award. The work is not yet started. Consideration is USD 26 million, subject to conditions."


def sample(store):
    setup(store)
    capture = store.capture(b"original exchange document", {"url": "https://nsearchives.nseindia.com/sample.pdf"})
    reading = {"symbol": "TEST", "isin": "INE000A01001", "url": "https://nsearchives.nseindia.com/sample.pdf",
               "raw_sha256": capture["raw_sha256"], "text_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
               "text": TEXT, "capture_id": capture["id"], "known_at": NOW, "published_at": "2026-11-07T10:00:00Z"}
    reading["reading_sha256"] = canonical_hash(reading)
    store.db.execute("INSERT INTO cc_news_readings VALUES (?,?,?,?,?)", (reading["reading_sha256"], "candidate", "recipe", NOW, json.dumps(reading)))
    store.db.commit()
    proposal = {"source": {k: reading[k] for k in ("symbol", "isin", "url", "raw_sha256", "text_sha256")},
                "category": "ORDER", "stage": "LETTER_OF_AWARD", "actor_scope": "ISSUER",
                "claims": [], "interpretation": "Award reported, not recognized earnings or proof of commencement.",
                "next_check": "Check execution, margins and collections before estimating cash effects."}
    for field, quote in (("event", "received a letter of award"), ("stage", "The work is not yet started"), ("actor", "TEST LIMITED")):
        start = TEXT.index(quote)
        proposal["claims"].append({"field": field, "start": start, "end": start + len(quote), "quote": quote})
    return reading, proposal


def test_source_review_is_separate_from_financial_truth_and_idempotent(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, proposal = sample(store)
        before = copy.deepcopy(proposal)
        one = admit(store, [proposal], "assistant-source-review")
        assert one == admit(store, [proposal], "assistant-source-review")
        assert proposal == before
        assert one[0]["reading_sha256"] == reading["reading_sha256"]
        assert not one[0]["independently_verified"] and not one[0]["buy_approved"]
        assert one[0]["forecast_earnings_effect"] is None
        assert store.db.execute("SELECT COUNT(*) FROM extractions").fetchone()[0] == 0
        assert store.db.execute("SELECT COUNT(*) FROM cc_news_reviews").fetchone()[0] == 1
        assert store.read_blob(reading["raw_sha256"]) == b"original exchange document"


@pytest.mark.parametrize("field", ["symbol", "isin", "url", "raw_sha256", "text_sha256"])
def test_no_cross_source_event_admission(tmp_path, field):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, proposal = sample(store)
        proposal["source"][field] = "different"
        with pytest.raises(ChangeError, match="unavailable"):
            admit(store, [proposal], "assistant-source-review")


@pytest.mark.parametrize("fault", ["quote", "offset", "boolean_offset", "missing_actor", "target_price", "bad_stage"])
def test_missing_evidence_and_unsupported_forecasts_are_rejected(tmp_path, fault):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, proposal = sample(store)
        if fault == "quote":
            proposal["claims"][0]["quote"] = "has completed a huge order"
        elif fault == "offset":
            proposal["claims"][0]["end"] = 999999
        elif fault == "boolean_offset":
            proposal["claims"][0]["start"] = True
        elif fault == "missing_actor":
            proposal["claims"][2]["field"] = "amount"
        elif fault == "target_price":
            proposal["target_price"] = 10000
        else:
            proposal["stage"] = "GUARANTEED_PROFIT"
        with pytest.raises(ChangeError):
            validate_review(reading, proposal)


def test_whole_package_fails_atomically_and_duplicate_rejected(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, proposal = sample(store)
        bad = copy.deepcopy(proposal)
        bad["claims"][0]["quote"] = "fabricated result"
        with pytest.raises(ChangeError):
            admit(store, [proposal, bad], "assistant-source-review")
        assert store.db.execute("SELECT COUNT(*) FROM cc_news_reviews").fetchone()[0] == 0
        with pytest.raises(ChangeError, match="duplicate"):
            admit(store, [proposal, proposal], "assistant-source-review")
        assert store.db.execute("SELECT COUNT(*) FROM cc_news_reviews").fetchone()[0] == 0


def test_review_clock_and_named_attestation_required(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        _, proposal = sample(store)
        with pytest.raises(ChangeError, match="attestation"):
            admit(store, [proposal], "")
        store.clock = lambda: "2026-11-06T00:00:00Z"
        with pytest.raises(ChangeError, match="predates"):
            admit(store, [proposal], "assistant-source-review")


def test_text_or_retained_review_corruption_is_detected(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, proposal = sample(store)
        changed = copy.deepcopy(reading)
        changed["text"] += "tampered"
        with pytest.raises(ChangeError, match="integrity"):
            validate_review(changed, proposal)
        admitted = admit(store, [proposal], "assistant-source-review")[0]
        admitted["stage"] = "COMPLETED"
        store.db.execute("UPDATE cc_news_reviews SET payload=?", (json.dumps(admitted),))
        store.db.commit()
        with pytest.raises(ChangeError, match="integrity"):
            admit(store, [proposal], "assistant-source-review")


def test_provider_packet_cannot_call_or_approve_a_model(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        reading, _ = sample(store)
        packet = review_packet(reading)
        assert packet["text"] == TEXT
        assert packet["model_called"] is False
        assert packet["automatic_review_approval"] is False
        assert "untrusted" in packet["instructions"]
        assert "UNRESOLVED" in packet["allowed_stages"]
