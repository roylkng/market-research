"""Fail-closed source-integrity tests for 300-filing HG009 replay."""

from __future__ import annotations

import copy
import hashlib
import xml.etree.ElementTree as ET

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p004_original_replay import (
    DECISION_CUTOFF,
    PINNED,
    check_hash,
    original_utc,
    replay_xbrl_fact,
)

XML = (
    b'<xbrl xmlns:t="http://test/financial">'
    b'<t:CashFlowsFromUsedInOperatingActivities contextRef="FourD" unitRef="INR">'
    b'4172700000</t:CashFlowsFromUsedInOperatingActivities>'
    b'<t:CashFlowsFromUsedInOperatingActivities contextRef="OldD" unitRef="INR">'
    b'2000000000</t:CashFlowsFromUsedInOperatingActivities>'
    b'</xbrl>'
)


def record(value: float = 4172700000, *, concept: str = "CashFlowsFromUsedInOperatingActivities"):
    return {
        "facts": {
            "operating_cash_flow": {
                "status": "READY",
                "selected_concept": concept,
                "context_refs": ["FourD"],
                "unit_ref": "INR",
                "value": value,
            }
        }
    }


def test_original_xbrl_replay_matches_exact_context_and_unit():
    value = replay_xbrl_fact(ET.fromstring(XML), record(), "operating_cash_flow")
    assert value == 417.27


def test_numeric_mutation_and_context_change_fail():
    with pytest.raises(AlphaContractError, match="original number"):
        replay_xbrl_fact(ET.fromstring(XML), record(100), "operating_cash_flow")
    changed = record()
    changed["facts"]["operating_cash_flow"]["context_refs"] = ["WrongContext"]
    with pytest.raises(AlphaContractError):
        replay_xbrl_fact(ET.fromstring(XML), changed, "operating_cash_flow")


def test_replay_fails_on_unit_or_missing_source():
    changed = record()
    changed["facts"]["operating_cash_flow"]["unit_ref"] = "USD"
    with pytest.raises(AlphaContractError, match="XBRL quantity"):
        replay_xbrl_fact(ET.fromstring(XML), changed, "operating_cash_flow")
    changed = record()
    changed["facts"]["operating_cash_flow"]["status"] = "MISSING"
    with pytest.raises(AlphaContractError, match="not ready"):
        replay_xbrl_fact(ET.fromstring(XML), changed, "operating_cash_flow")


def test_cohort_digest_pin_is_not_resealable():
    original = {"one": 1}
    expected = digest(original)
    check_hash({**original, "test_sha": expected}, "test_sha", expected)
    tampered = copy.deepcopy(original)
    tampered["one"] = 2
    tampered["test_sha"] = digest(tampered)
    with pytest.raises(AlphaContractError, match="pinned source panel signature"):
        check_hash(tampered, "test_sha", expected)


def test_raw_sha_has_immutable_semantics():
    raw = XML
    correct = hashlib.sha256(raw).hexdigest()
    assert correct != hashlib.sha256(raw + b"tampered").hexdigest()


def test_only_exact_utc_clock_is_admissible():
    assert original_utc(DECISION_CUTOFF).isoformat() == "2026-10-15T13:00:00+00:00"
    for value in ("2026-10-15T15:00:00+02:00", "2026-10-15T13:00:00", "bogus"):
        with pytest.raises(AlphaContractError, match="UTC"):
            original_utc(value)


def test_l001_snapshot_pins_are_nonempty_and_distinct():
    assert set(PINNED) == {"cohort", "census", "fa001", "ss001", "gf001"}
    assert len(set(PINNED.values())) == 5
    assert all(len(sha) == 64 for sha in PINNED.values())
