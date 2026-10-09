from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_d007_a001 import assess_a001_readiness

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "research/ss001-d007-l001-p2-queue-result-v1.json"
L002_PATH = ROOT / "research/ss001-d007-l002-p0-result-v1.json"


def _inputs() -> tuple[dict, dict]:
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    l002 = json.loads(L002_PATH.read_text(encoding="utf-8"))
    return queue, l002


def test_committed_source_stays_blocked_and_has_no_capitalization() -> None:
    queue, l002 = _inputs()
    state = assess_a001_readiness(queue, l002)
    assert state["status"] == "SOURCE_EVIDENCE_PENDING"
    assert state["issuer_count"] == 12
    assert state["pending_l002_page_count"] == 1240
    assert state["validated_l002_page_count"] == 0
    assert state["r001_transport_validated_count"] is None
    assert state["share_action_clearance_proven"] is False
    assert state["market_capitalization_calculated"] is False
    assert state["portfolio_eligibility_allowed"] is False
    assert len(state["readiness_sha256"]) == 64


def test_fake_ready_flag_cannot_bypass_missing_pages() -> None:
    queue, l002 = _inputs()
    l002["semantic_audit_complete"] = True
    state = assess_a001_readiness(queue, l002)
    assert state["status"] == "SOURCE_EVIDENCE_PENDING"
    assert state["share_action_clearance_proven"] is False


def test_complete_transport_without_reassembly_stays_blocked() -> None:
    queue, l002 = _inputs()
    transport = {
        "source_queue_sha256": queue["queue_sha256"],
        "validated_request_count": 1240,
        "runtime_model_config_sha256": "a" * 64,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    state = assess_a001_readiness(queue, l002, transport)
    assert state["status"] == "L002_REASSEMBLY_REQUIRED"
    assert state["market_capitalization_calculated"] is False


def test_l002_complete_still_requires_independent_semantic_review() -> None:
    queue, l002 = _inputs()
    complete = copy.deepcopy(l002)
    for row in complete["issuer_pending_pages"]:
        row["pending_pages"] = 0
    complete["fresh_remaining_response_count"] = 0
    complete["fresh_validated_response_count"] = 1240
    state = assess_a001_readiness(queue, complete)
    assert state["status"] == "SEMANTIC_REVIEW_PENDING"
    complete["semantic_audit_complete"] = True
    state = assess_a001_readiness(queue, complete)
    assert state["status"] == "INDEPENDENT_REVIEW_LEDGER_REQUIRED"
    assert state["share_action_clearance_proven"] is False


def test_missing_page_or_source_hash_fails_closed() -> None:
    queue, l002 = _inputs()
    changed = copy.deepcopy(l002)
    changed["issuer_pending_pages"][0]["pending_pages"] -= 1
    with pytest.raises(AlphaContractError, match="page coverage does not reconcile"):
        assess_a001_readiness(queue, changed)

    changed = copy.deepcopy(queue)
    changed["queue_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="queue SHA mismatch"):
        assess_a001_readiness(changed, l002)


def test_unsupported_share_clearance_claim_is_rejected() -> None:
    queue, l002 = _inputs()
    changed = copy.deepcopy(l002)
    changed["share_action_clearance_proven"] = True
    with pytest.raises(AlphaContractError, match="share_action_clearance_proven=false"):
        assess_a001_readiness(queue, changed)
